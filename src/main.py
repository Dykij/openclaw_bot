import asyncio
import json
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()

import structlog
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    ForceReply,
    Message,
)
from prometheus_client import start_http_server
from watchdog.observers import Observer

from src.archivist_telegram import TelegramArchivist
from src.boot import (
    PROMPT_COUNTER,
    ConfigReloader,
    acquire_lock,
    configure_llm_and_pipeline,
    release_lock,
    setup_structlog,
)
from src.bot_commands import (
    cmd_agent,
    cmd_agents,
    cmd_help,
    cmd_history,
    cmd_models,
    cmd_openrouter_test,
    cmd_perf,
    cmd_research,
    cmd_start,
    cmd_status,
    cmd_tailscale,
    cmd_test,
    cmd_test_all_models,
    handle_callback_query,
    handle_document,
    handle_photo,
    handle_unknown_command,
    handle_voice,
)
from src.tailscale_monitor import TailscaleMonitor
from src.intent_classifier import classify_intent
from src.memory_gc import MemoryGarbageCollector
from src.pipeline_executor import PipelineExecutor
from src.safety_guardrails import HallucinationDetector, PromptInjectionDefender

setup_structlog()
logger = structlog.get_logger("OpenClawGateway")


# Removed old logging setup


class OpenClawGateway:
    def __init__(self, config_path: str = "config/openclaw_config.json"):
        self.config_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.loads(os.path.expandvars(f.read()))

        self.bot_token = self.config["system"]["telegram"]["bot_token"]
        self.admin_id = int(self.config["system"]["telegram"]["admin_chat_id"])
        self.vllm_url = self.config["system"].get("vllm_base_url", "http://localhost:8000/v1")

        # Initialize vLLM model manager ONLY when local models are enabled.
        # Cloud-Only mode (use_local_models=false) skips all vLLM/WSL setup.
        vllm_cfg = self.config["system"]
        or_cfg = vllm_cfg.get("openrouter", {})
        self._use_local_models = or_cfg.get("use_local_models", True)
        self._cloud_only = (
            or_cfg.get("force_cloud", False)
            and or_cfg.get("enabled", False)
            and bool(or_cfg.get("api_key", ""))
            and not self._use_local_models
        )

        if self._cloud_only:
            logger.info("Cloud-Only mode: vLLM/WSL/Ollama disabled. All inference via OpenRouter.")
            self.vllm_manager = None
        else:
            from src.vllm_manager import VLLMModelManager
            self.vllm_manager = VLLMModelManager(
                port=vllm_cfg.get("vllm_port", 8000),
                gpu_memory_utilization=vllm_cfg.get("vllm_gpu_memory_utilization", 0.90),
                max_model_len=vllm_cfg.get("vllm_max_model_len", 8192),
                quantization=vllm_cfg.get("vllm_quantization"),
                vllm_extra_args=vllm_cfg.get("vllm_extra_args"),
            )

        # Initialize Tailscale monitor
        self.tailscale = TailscaleMonitor(self.config)

        self.bot = Bot(token=self.bot_token)
        self.dp = Dispatcher()
        self.archivist = TelegramArchivist(self.bot_token, str(self.admin_id))
        self.pipeline = PipelineExecutor(self.config, self.vllm_url, self.vllm_manager)
        self.memory_gc = MemoryGarbageCollector(self.vllm_url)
        self._intent_cache: dict = {}  # Simple cache for intent classification
        self.processed_task_hashes = set()

        # Safety Guardrails (zero-VRAM heuristic checks)
        self.injection_defender = PromptInjectionDefender(strictness="medium")
        self.hallucination_detector = HallucinationDetector()

        # Pipeline history & performance metrics storage
        self._pipeline_history: list = []
        self._perf_metrics: list = []

        # Watchdog for Config
        self._observer = Observer()
        self._observer.schedule(
            ConfigReloader(self.reload_config),
            os.path.dirname(self.config_path) or ".",
            recursive=False,
        )
        self._observer.start()

        # Start Prometheus metrics server on port 9090 (8000 is reserved for vLLM)
        try:
            start_http_server(9090)
            logger.info("Prometheus metrics server started on port 9090")
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")

        # Register Handlers (delegating to gateway_commands module)
        # NOTE: async wrappers required — plain lambdas returning coroutines are NOT awaited by aiogram
        def _aw(fn):
            async def wrapper(event):
                await fn(self, event)
            return wrapper

        self.dp.message.register(_aw(cmd_start), Command("start"))
        self.dp.message.register(_aw(cmd_help), Command("help"))
        self.dp.message.register(_aw(cmd_status), Command("status"))
        self.dp.message.register(_aw(cmd_models), Command("models"))
        self.dp.message.register(_aw(cmd_test), Command("test"))
        self.dp.message.register(_aw(cmd_test_all_models), Command("test_all_models"))
        self.dp.message.register(_aw(cmd_research), Command("research"))
        self.dp.message.register(_aw(cmd_tailscale), Command("tailscale"))
        self.dp.message.register(_aw(handle_photo), F.photo)
        self.dp.message.register(_aw(handle_voice), F.voice)
        self.dp.message.register(_aw(handle_document), F.document)
        self.dp.message.register(_aw(cmd_history), Command("history"))
        self.dp.message.register(_aw(cmd_perf), Command("perf"))
        self.dp.message.register(_aw(cmd_agents), Command("agents"))
        self.dp.message.register(_aw(cmd_agent), Command("agent"))
        self.dp.message.register(_aw(cmd_openrouter_test), Command("openrouter_test"))
        
        # Заглушка для неизвестных команд
        self.dp.message.register(_aw(handle_unknown_command), F.text.startswith('/'))
        
        # Перехват только текста, который НЕ является командой
        self.dp.message.register(self.handle_prompt, F.text & ~F.text.startswith('/'))
        
        # Callback query handler for inline buttons
        self.dp.callback_query.register(_aw(handle_callback_query))

        # Background logic
        self._bg_tasks = set()

    async def _scheduled_memory_gc(self):
        """Background task to run Memory GC every 24 hours."""
        logger.info("Memory GC background loop started (24h interval)")
        while True:
            try:
                # Wait 24 hours (86400 seconds)
                await asyncio.sleep(86400)
                logger.info("Triggering scheduled Memory GC compression...")
                from src.memory_gc import MemoryGarbageCollector
                gc = MemoryGarbageCollector(self.vllm_url)
                
                # Logic: Find stale conversation artifacts and zip/summarize them
                # We can also append the persistent summary to Cold_Memory.md
                memory_bank_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".memory-bank")
                cold_memory_path = os.path.join(memory_bank_dir, "Cold_Memory.md")
                
                if gc.persistent_summary:
                    with open(cold_memory_path, "a", encoding="utf-8") as f:
                        f.write(f"\n\n### Archived Context ({time.strftime('%Y-%m-%d %H:%M:%S')})\n")
                        f.write(gc.persistent_summary)
                    logger.info("Persistent summary archived to Cold_Memory.md")

                logger.info("Scheduled Memory GC completed.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Memory GC loop error", error=str(e))
                await asyncio.sleep(3600)  # Retry in an hour on error

    async def _poll_remote_tasks(self):
        """
        Background task to poll for commands from a remote registry.
        Enables operation behind NAT/Firewall without open ports (Phase 2.3).
        Uses ClawHubClient for structured API communication.
        """
        poll_url = self.config["system"].get("polling_gateway_url")
        if not poll_url:
            logger.info("Polling Gateway: Disabled (no URL in config)")
            return

        interval = self.config["system"].get("polling_interval_sec", 30)
        logger.info("Polling Gateway: Active", url=poll_url, interval=interval)

        from src.clawhub.client import ClawHubClient

        client = ClawHubClient(base_url=poll_url, bot_id=str(self.admin_id))
        await client.initialize()

        while True:
            try:
                tasks = await client.poll_tasks()
                if isinstance(tasks, list) and tasks:
                    for task in tasks:
                        import hashlib
                        task_hash = hashlib.sha256(task.get('prompt', '').encode()).hexdigest()
                        if task_hash in self.processed_task_hashes:
                            continue

                        self.processed_task_hashes.add(task_hash)
                        logger.info("Polling Gateway: Received new task", task_hash=task_hash[:8])

                        class MockMessage:
                            def __init__(self, prompt, admin_id, bot):
                                self.text = prompt
                                self.from_user = type('MockUser', (), {'id': admin_id})()
                                self.reply_to_message = None
                                self.bot = bot
                            async def reply(self, text, *args, **kwargs):
                                logger.info("Polling Result", result=text)
                                class MockStatus:
                                    async def edit_text(self, *a, **k): return True
                                return MockStatus()
                            async def answer(self, text, *args, **kwargs):
                                logger.info("Polling Result (Answer)", result=text)

                        mock_msg = MockMessage(task.get('prompt'), self.admin_id, self.bot)
                        asyncio.create_task(self.handle_prompt(mock_msg))

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Polling Gateway Error", error=str(e))
                await asyncio.sleep(interval * 2)

    async def reload_config(self):
        try:
            # AutoRollback: create checkpoint before config reload
            from src.auto_rollback import AutoRollback
            rollback = AutoRollback(os.path.dirname(os.path.abspath(self.config_path)))
            try:
                rollback.create_checkpoint("pre-config-reload")
            except Exception:
                pass  # Git may not be available

            with open(self.config_path, "r", encoding="utf-8") as f:
                new_config = json.loads(os.path.expandvars(f.read()))

            self.config = new_config
            self.pipeline.config = new_config
            logger.info("Configuration successfully hot-reloaded.")

            try:
                rollback.finalize("config-reload-success")
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            try:
                rollback.rollback()
                logger.info("Config rollback successful after error")
            except Exception:
                pass

    def get_nim_models(self) -> list:
        # Placeholder: returns empty list (models fetched at runtime via NGC API)
        return []

    async def handle_prompt(self, message: Message):
        if message.from_user.id != self.admin_id:
            return

        # --- Phase 8: HITL edit reply interception ---
        _hitl_edits = getattr(self, "_pending_hitl_edits", {})
        user_id = message.from_user.id
        if user_id in _hitl_edits:
            from src.llm_gateway import resolve_approval
            req_id = _hitl_edits.pop(user_id)
            resolve_approval(req_id, "edited", edited_prompt=message.text)
            await message.reply("✏️ Промпт обновлён. Запрос продолжает выполнение.")
            return

        PROMPT_COUNTER.inc()
        prompt = message.text
        logger.info("received_prompt", prompt=prompt)
        try:
            await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        except Exception:
            pass
        try:
            await self._handle_prompt_inner(message, prompt)
        except Exception as exc:
            logger.error("handle_prompt unhandled error", error=str(exc), exc_info=True)
            try:
                await message.reply(f"❌ Внутренняя ошибка бота: {exc}")
            except Exception:
                pass

    async def _handle_prompt_inner(self, message: Message, prompt: str):

        # Safety: Prompt Injection Detection
        injection_result = self.injection_defender.analyze(prompt)
        if injection_result.is_injection:
            logger.warning("Prompt injection detected", severity=injection_result.severity,
                          patterns=injection_result.patterns_matched)
            if injection_result.severity in ("high", "critical"):
                await message.reply(
                    f"🛡️ *Заблокировано*: обнаружена попытка prompt injection "
                    f"(severity: {injection_result.severity})",
                    parse_mode="Markdown",
                )
                return
            # Medium/low: warn but proceed
            await message.reply(
                f"⚠️ Предупреждение: подозрительный паттерн в запросе "
                f"(confidence: {injection_result.confidence:.0%}). Обрабатываю с осторожностью.",
            )

        # Check if it's a reply to ask_user
        is_reply = False
        if message.reply_to_message and getattr(message.reply_to_message.from_user, "id", None) == message.bot.id:
            if hasattr(self, 'pending_ask_user') and message.from_user.id in self.pending_ask_user:
                is_reply = True
                context = self.pending_ask_user.pop(message.from_user.id)
                brigade = context["brigade"]
                original_prompt = context["original_prompt"]
                prompt = f"Ранее я просил: {original_prompt}\nТвой вопрос ко мне. Вот мой ответ/уточнение: {prompt}\nПродолжай задачу с учетом этих новых данных."
                logger.info("Resuming pipeline with user clarification", brigade=brigade)

        # Session Management: Context Auto-Reset
        if not hasattr(self, '_session_msg_count'):
            self._session_msg_count = 0
        self._session_msg_count += 1
        
        reset_limit = self.config.get("system", {}).get("session_management", {}).get("auto_reset_context_messages", 15)
        if self._session_msg_count >= reset_limit:
            self._session_msg_count = 0
            if hasattr(self, 'memory_gc'):
                self.memory_gc._persistent_summary = ""
                self.memory_gc._compression_count = 0
            logger.info("Session context auto-reset triggered (reached max msgs)", limit=reset_limit)
            await message.reply(f"🔄 **Внимание:** Достигнут лимит сессии ({reset_limit} сообщений). Окно контекста и память очищены для экономии VRAM.", parse_mode="Markdown")

        # 1. Intent Classification (LLM-based with keyword fallback)
        if not is_reply:
            brigade = await classify_intent(self, prompt)

        # 2. Execute Pipeline (Chain-of-Agents) or Fast Path (single model)
        is_fast_path = (brigade == "General")
        actual_brigade = "OpenClaw" if is_fast_path else brigade

        route_label = f"{actual_brigade} ⚡" if is_fast_path else actual_brigade
        _b = self.archivist.escape_markdown(route_label)
        status_msg = await message.reply(
            f"🤖 *Pipeline \\({_b}\\)* запущен\\.\\.\\.\n_Маршрутизация задачи в бригаду\\.\\.\\._",
            parse_mode="MarkdownV2",
        )

        await self.archivist.send_status(
            f"Router ({actual_brigade})", "Intent Classification",
            f"Задача направлена в бригаду {actual_brigade}" + (" (fast path)" if is_fast_path else "")
        )

        async def update_status(role, model, text):
            try:
                b = self.archivist.escape_markdown(actual_brigade)
                r = self.archivist.escape_markdown(role)
                m = self.archivist.escape_markdown(model)
                t = self.archivist.escape_markdown(text)
                await status_msg.edit_text(
                    f"🏴 *{b}* \\| ⚙️ `{r}` \\(`{m}`\\)\n_{t}_", parse_mode="MarkdownV2"
                )
            except Exception:
                pass  # Telegram rate limit on edits

        # Periodic typing indicator (Telegram resets after ~5s)
        typing_stop = asyncio.Event()
        async def _keep_typing():
            while not typing_stop.is_set():
                try:
                    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(typing_stop.wait(), timeout=4)
                    break
                except asyncio.TimeoutError:
                    pass
        typing_task = asyncio.create_task(_keep_typing())

        _pipeline_start = time.time()
        try:
            result = await self.pipeline.execute_stream(
                prompt=prompt,
                brigade=actual_brigade,
                status_callback=update_status,
                task_type="general" if is_fast_path else None,
            )
        finally:
            typing_stop.set()
            typing_task.cancel()

        # Phase 3.4: Self-Healing Logic (One-time retry on failure)
        if result.get("status") == "error":
            logger.warning("Pipeline execution failed. Attempting self-healing retry...", brigade=actual_brigade)
            typing_stop.clear()
            typing_task = asyncio.create_task(_keep_typing())
            try:
                result = await self.pipeline.execute_stream(
                    prompt=prompt,
                    brigade=actual_brigade,
                    status_callback=update_status,
                    task_type="general" if is_fast_path else None,
                )
            finally:
                typing_stop.set()
                typing_task.cancel()

        if result.get("status") == "ask_user":
            question = result.get("question", "Оркестратору нужно уточнение.")
            if not hasattr(self, 'pending_ask_user'):
                self.pending_ask_user = {}
                
            self.pending_ask_user[message.from_user.id] = {
                "original_prompt": prompt,
                "brigade": actual_brigade
            }
            
            markup = ForceReply(selective=True)
            try:
                await status_msg.edit_text(
                    f"❓ *Вопрос от Оркестратора:*\n\n{question}",
                    parse_mode="Markdown"
                )
                await message.reply("Ответьте на это сообщение для продолжения (Reply):", reply_markup=markup)
            except Exception:
                await message.reply(
                    f"❓ *Вопрос от Оркестратора:*\n\n{question}",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
                
            await self.archivist.send_status(
                f"Router ({actual_brigade})", "Clarification Loop", "Пайплайн приостановлен. Ожидается ответ пользователя."
            )
            return

        llm_response = result["final_response"]
        chain_str = " → ".join(result["chain_executed"])
        display_brigade = f"{actual_brigade} ⚡" if is_fast_path else actual_brigade
        _pipeline_elapsed = time.time() - _pipeline_start

        # Safety: Hallucination Detection on output
        hall_result = self.hallucination_detector.detect(llm_response, prompt)
        if hall_result.overall_risk == "high":
            llm_response += "\n\n⚠️ _Внимание: обнаружен высокий риск галлюцинации. Проверьте факты._"
            logger.warning("Hallucination risk HIGH", flags=hall_result.flags,
                          suspicious=hall_result.suspicious_claims[:3])

        # Record pipeline history
        self._pipeline_history.append({
            "timestamp": time.strftime("%H:%M:%S"),
            "brigade": actual_brigade,
            "prompt": prompt[:80],
            "chain": chain_str,
            "duration_sec": _pipeline_elapsed,
            "status": result.get("status", "completed"),
            "hallucination_risk": hall_result.overall_risk,
        })
        # Keep last 50 entries
        if len(self._pipeline_history) > 50:
            self._pipeline_history = self._pipeline_history[-50:]

        # Record perf metrics from pipeline steps
        for step in result.get("steps", []):
            resp_len = len(step.get("response", ""))
            est_tokens = resp_len // 4  # rough estimate
            self._perf_metrics.append({
                "role": step.get("role", "?"),
                "model": step.get("model", "?"),
                "tokens": est_tokens,
                "duration_sec": step.get("duration_sec", _pipeline_elapsed / max(len(result.get("steps", [{}])), 1)),
            })
        if len(self._perf_metrics) > 500:
            self._perf_metrics = self._perf_metrics[-500:]

        # 3. Send final response with progressive streaming edits
        stream = result.get("stream")
        if stream:
            accumulated = ""
            header = f"🏴 *Бригада:* {display_brigade} | *Pipeline:* `{chain_str}`\n\n"
            last_edit_time = 0
            try:
                async for chunk in stream:
                    accumulated += chunk
                    now = time.time()
                    # Edit message no more than once per second (Telegram rate limit)
                    if now - last_edit_time >= 1.0:
                        try:
                            await status_msg.edit_text(header + accumulated + "▌", parse_mode="Markdown")
                        except Exception:
                            try:
                                await status_msg.edit_text(
                                    f"🏴 Бригада: {display_brigade} | Pipeline: {chain_str}\n\n{accumulated}▌"
                                )
                            except Exception:
                                pass
                        last_edit_time = now
            except Exception as e:
                logger.warning("Stream interrupted", error=str(e))

            # Final edit without cursor
            try:
                await status_msg.edit_text(header + accumulated, parse_mode="Markdown")
            except Exception:
                await status_msg.edit_text(
                    f"🏴 Бригада: {display_brigade} | Pipeline: {chain_str}\n\n{accumulated}"
                )
        else:
            try:
                await status_msg.edit_text(
                    f"🏴 *Бригада:* {display_brigade} | *Pipeline:* `{chain_str}`\n\n{llm_response}",
                    parse_mode="Markdown",
                )
            except Exception:
                await status_msg.edit_text(
                    f"🏴 Бригада: {display_brigade} | Pipeline: {chain_str}\n\n{llm_response}"
                )

        # 4. Final Report (для логов Архивариуса)
        roles = list(self.config["brigades"][actual_brigade]["roles"].keys())
        await self.archivist.send_summary(
            f"Pipeline завершён ({actual_brigade})",
            f"Промпт: {prompt}\n\n"
            f"*Pipeline:* {chain_str}\n"
            f"*Ответ:* {llm_response}\n\n"
            f"*Бригада:* {actual_brigade} (Ролей: {len(roles)})\n"
            f"*GC Stats:* {self.memory_gc.get_stats()}",
        )

    async def _preload_model(self, model_name: str):
        """Pre-load default vLLM model at startup to avoid cold start delays."""
        try:
            logger.info("Pre-loading default model at startup", model=model_name)
            await self.vllm_manager.ensure_model_loaded(model_name)
            logger.info("Default model pre-loaded successfully", model=model_name)
        except Exception as e:
            logger.warning("Failed to pre-load default model", model=model_name, error=str(e))

    async def run(self):
        logger.info("Starting OpenClaw Gateway...")
        logger.info("vLLM URL", vllm_url=self.vllm_url)
        logger.info("Admin ID", admin_id=self.admin_id)

        # Delegate heavy init to boot module
        await configure_llm_and_pipeline(self)

        # Support ENV vars from start_wsl.sh
        use_webhook_env = os.environ.get("USE_WEBHOOK")
        if use_webhook_env == "1":
            use_webhook = True
            self.webhook_url = os.environ.get("WEBHOOK_URL", "")
        else:
            use_webhook = self.config["system"]["telegram"].get("use_webhook", False)
            self.webhook_url = self.config["system"]["telegram"].get("webhook_url", "")

        try:
            if use_webhook and self.webhook_url:
                from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
                from aiohttp import web

                logger.info("starting_webhook", url=self.webhook_url)
                await self.bot.set_webhook(self.webhook_url, drop_pending_updates=True)

                app = web.Application()
                webhook_requests_handler = SimpleRequestHandler(dispatcher=self.dp, bot=self.bot)
                webhook_requests_handler.register(app, path="/webhook")
                setup_application(app, self.dp, bot=self.bot)

                runner = web.AppRunner(app)
                await runner.setup()
                port = self.config["system"]["telegram"].get("webhook_port", 8080)
                site = web.TCPSite(runner, "0.0.0.0", port)
                await site.start()
                logger.info("Webhook server listening", port=port)

                # Keep process alive
                await asyncio.Event().wait()
            else:
                logger.info("starting_polling")
                await self.bot.delete_webhook(drop_pending_updates=True)
                # Register bot commands in Telegram menu ("Меню" button)
                await self.bot.set_my_commands([
                    BotCommand(command="start", description="Главное меню"),
                    BotCommand(command="help", description="Список всех команд"),
                    BotCommand(command="status", description="Статус системы"),
                    BotCommand(command="models", description="Список моделей"),
                    BotCommand(command="test", description="VRAM тест"),
                    BotCommand(command="test_all_models", description="Тест всех 20 ролей"),
                ])
                logger.info("Bot commands registered in Telegram menu")
                await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error("startup_failed", error=str(e))
        finally:
            self._observer.stop()
            self._observer.join()
            await self.bot.session.close()


if __name__ == "__main__":
    acquire_lock()
    print("-" * 30)
    print("🚀 OpenClaw Gateway Starting...")
    print(f"🚀 Running on Python {sys.version}")
    print("-" * 30)
    try:
        gateway = OpenClawGateway()
        asyncio.run(gateway.run())
    except KeyboardInterrupt:
        print("\n🛑 OpenClaw Gateway stopped by user (Graceful Shutdown).")
    finally:
        release_lock()
