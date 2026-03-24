import asyncio
import atexit
import json
import os
import sys
import time
from typing import Optional

import structlog
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    ForceReply,
    Message,
)
from prometheus_client import Counter, Gauge, start_http_server
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.archivist_telegram import TelegramArchivist
from src.gateway_commands import (
    cmd_agent,
    cmd_agents,
    cmd_help,
    cmd_models,
    cmd_research,
    cmd_start,
    cmd_status,
    cmd_test,
    cmd_test_all_models,
    handle_callback_query,
    handle_photo,
    handle_unknown_command,
)
from src.agent_personas import AgentPersonaManager
from src.intent_classifier import classify_intent
from src.memory_gc import MemoryGarbageCollector
from src.pipeline_executor import PipelineExecutor

# Prometheus metrics
PROMPT_COUNTER = Counter("openclaw_prompts_total", "Total prompts received")
VRAM_GAUGE = Gauge("openclaw_vram_usage_mb", "Estimated VRAM usage")
MODEL_LOAD_GAUGE = Gauge("openclaw_model_loaded", "Is a model currently loaded")

# Structured Logging Setup
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger("OpenClawGateway")


class ConfigReloader(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        if event.src_path.endswith("config/openclaw_config.json"):
            logger.info("Config changed, reloading...")
            self.callback()


LOCK_FILE = "/tmp/openclaw_bot.lock"


def acquire_lock():
    """Prevent multiple bot instances from running."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())

            try:
                import psutil

                if psutil.pid_exists(old_pid):
                    print(f"❌ Bot is already running (PID {old_pid})! Exiting.")
                    sys.exit(1)
            except ImportError:
                # UNIX fallback
                try:
                    os.kill(old_pid, 0)
                    print(f"❌ Bot is already running (PID {old_pid})! Exiting.")
                    sys.exit(1)
                except OSError:
                    pass
            print(f"⚠️ Stale lock file found (PID {old_pid} dead). Removing...")
        except (ValueError, FileNotFoundError):
            pass

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(release_lock)


def release_lock():
    """Remove lock file on exit."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except OSError:
        pass


# Removed old logging setup


class OpenClawGateway:
    def __init__(self, config_path: str = "config/openclaw_config.json"):
        self.config_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.bot_token = self.config["system"]["telegram"]["bot_token"]
        self.admin_id = int(self.config["system"]["telegram"]["admin_chat_id"])
        self.vllm_url = self.config["system"].get("vllm_base_url", "http://localhost:8000/v1")

        # Initialize vLLM model manager for dynamic model swapping
        from src.vllm_manager import VLLMModelManager
        vllm_cfg = self.config["system"]
        self.vllm_manager = VLLMModelManager(
            port=vllm_cfg.get("vllm_port", 8000),
            gpu_memory_utilization=vllm_cfg.get("vllm_gpu_memory_utilization", 0.90),
            max_model_len=vllm_cfg.get("vllm_max_model_len", 8192),
            quantization=vllm_cfg.get("vllm_quantization"),
            vllm_extra_args=vllm_cfg.get("vllm_extra_args"),
        )

        self.bot = Bot(token=self.bot_token)
        self.dp = Dispatcher()
        self.archivist = TelegramArchivist(self.bot_token, str(self.admin_id))
        self.pipeline = PipelineExecutor(self.config, self.vllm_url, self.vllm_manager)
        self.memory_gc = MemoryGarbageCollector(self.vllm_url)
        self._intent_cache: dict = {}  # Simple cache for intent classification
        self.processed_task_hashes = set()

        # Agent persona system — loads personas from agents/ at repo root
        try:
            self.persona_manager = AgentPersonaManager()
            logger.info(
                "Agent persona manager initialised",
                count=len(self.persona_manager.registry.list_unique()),
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Agent persona manager failed to init (%s: %s). "
                "Check that the agents/ directory exists and contains valid .md files.",
                type(exc).__name__, exc,
            )
            self.persona_manager = None

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
        self.dp.message.register(lambda m: cmd_start(self, m), Command("start"))
        self.dp.message.register(lambda m: cmd_help(self, m), Command("help"))
        self.dp.message.register(lambda m: cmd_status(self, m), Command("status"))
        self.dp.message.register(lambda m: cmd_models(self, m), Command("models"))
        self.dp.message.register(lambda m: cmd_test(self, m), Command("test"))
        self.dp.message.register(lambda m: cmd_test_all_models(self, m), Command("test_all_models"))
        self.dp.message.register(lambda m: cmd_research(self, m), Command("research"))
        self.dp.message.register(lambda m: cmd_agents(self, m), Command("agents"))
        self.dp.message.register(lambda m: cmd_agent(self, m), Command("agent"))
        self.dp.message.register(lambda m: handle_photo(self, m), F.photo)
        
        # Заглушка для неизвестных команд
        self.dp.message.register(lambda m: handle_unknown_command(self, m), F.text.startswith('/'))
        
        # Перехват только текста, который НЕ является командой
        self.dp.message.register(self.handle_prompt, F.text & ~F.text.startswith('/'))
        
        # Callback query handler for inline buttons
        self.dp.callback_query.register(lambda cb: handle_callback_query(self, cb))

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
                memory_bank_dir = os.path.join(os.getcwd(), ".memory-bank")
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
        """
        poll_url = self.config["system"].get("polling_gateway_url")
        if not poll_url:
            logger.info("Polling Gateway: Disabled (no URL in config)")
            return

        interval = self.config["system"].get("polling_interval_sec", 30)
        logger.info("Polling Gateway: Active", url=poll_url, interval=interval)

        import aiohttp
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(poll_url, timeout=10) as resp:
                        if resp.status == 200:
                            tasks = await resp.json()
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
                                            # Create an awaitable object for edit_text
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
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            self.pipeline.config = self.config
            logger.info("Configuration successfully hot-reloaded.")
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")

    def get_nim_models(self) -> list:
        # Placeholder: returns empty list (models fetched at runtime via NGC API)
        return []

    async def handle_prompt(self, message: Message):
        if message.from_user.id != self.admin_id:
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

        # 1b. Agent persona augmentation — prepend active persona to prompt if set
        augmented_prompt = prompt
        if self.persona_manager:
            augmentation = self.persona_manager.get_persona_augmentation(message.chat.id)
            if augmentation:
                augmented_prompt = f"{augmentation}\n\n[USER REQUEST]\n{prompt}"
                logger.info(
                    "Persona active",
                    persona=self.persona_manager.active_persona(message.chat.id).name,
                )

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
        typing_active = True
        async def _keep_typing():
            while typing_active:
                try:
                    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
                except Exception:
                    pass
                await asyncio.sleep(4)
        typing_task = asyncio.create_task(_keep_typing())

        try:
            result = await self.pipeline.execute_stream(
                prompt=augmented_prompt,
                brigade=actual_brigade,
                status_callback=update_status,
                task_type="general" if is_fast_path else None,
            )
        finally:
            typing_active = False
            typing_task.cancel()

        # Phase 3.4: Self-Healing Logic (One-time retry on failure)
        if result.get("status") == "error":
            logger.warning("Pipeline execution failed. Attempting self-healing retry...", brigade=actual_brigade)
            typing_active = True
            typing_task = asyncio.create_task(_keep_typing())
            try:
                result = await self.pipeline.execute_stream(
                    prompt=augmented_prompt,
                    brigade=actual_brigade,
                    status_callback=update_status,
                    task_type="general" if is_fast_path else None,
                )
            finally:
                typing_active = False
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

        # Start background tasks
        memory_task = asyncio.create_task(self._scheduled_memory_gc())
        poll_task = asyncio.create_task(self._poll_remote_tasks())
        self._bg_tasks.add(memory_task)
        self._bg_tasks.add(poll_task)
        memory_task.add_done_callback(self._bg_tasks.discard)
        poll_task.add_done_callback(self._bg_tasks.discard)

        # Start vLLM health monitoring
        self.vllm_manager.start_health_monitor()

        # Pre-load default model to avoid cold start on first message
        default_model = self.config.get("system", {}).get("model_router", {}).get("general", "Qwen/Qwen2.5-14B-Instruct-AWQ")
        preload_task = asyncio.create_task(self._preload_model(default_model))
        self._bg_tasks.add(preload_task)
        preload_task.add_done_callback(self._bg_tasks.discard)

        # Start Brigade REST API (FastAPI / uvicorn) so the TypeScript
        # OpenClaw gateway can call brigade pipelines via HTTP.
        brigade_port = int(os.environ.get("BRIGADE_API_PORT", "8765"))
        try:
            from src.brigade_api import run_brigade_api
            brigade_task = asyncio.create_task(
                run_brigade_api(self.config, self.vllm_url, self.vllm_manager, port=brigade_port)
            )
            self._bg_tasks.add(brigade_task)
            brigade_task.add_done_callback(self._bg_tasks.discard)
            logger.info("Brigade API started", port=brigade_port, url=f"http://127.0.0.1:{brigade_port}/brigade/docs")
        except Exception as e:
            logger.error("Brigade API failed to start", error=str(e))

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
