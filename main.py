import asyncio
import atexit
import json
import logging
import os
import subprocess
import sys

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from archivist_telegram import TelegramArchivist
from memory_gc import MemoryGarbageCollector
from risk_manager import RiskManager

LOCK_FILE = os.path.join(os.path.dirname(__file__), ".bot.lock")

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

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("OpenClawGateway")


class OpenClawGateway:
    def __init__(self, config_path: str = "openclaw_config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.bot_token = self.config["system"]["telegram"]["bot_token"]
        self.admin_id = int(self.config["system"]["telegram"]["admin_chat_id"])
        self.ollama_url = self.config["system"].get("ollama_url", "http://192.168.0.212:11434")

        self.bot = Bot(token=self.bot_token)
        self.dp = Dispatcher()
        self.archivist = TelegramArchivist(self.bot_token, str(self.admin_id))

        # Register Handlers
        self.dp.message.register(self.cmd_start, Command("start"))
        self.dp.message.register(self.cmd_status, Command("status"))
        self.dp.message.register(self.cmd_models, Command("models"))
        self.dp.message.register(self.cmd_test, Command("test"))
        self.dp.message.register(self.cmd_test_all_models, Command("test_all_models"))
        self.dp.message.register(self.handle_prompt)

    async def cmd_start(self, message: Message):
        if message.from_user.id != self.admin_id:
            await message.reply("⛔ Access Denied. Locked to Admin.")
            return
        await message.reply(
            "🦞 *OpenClaw v2026: Dual-Brigade Online*\n\n"
            f"🛠️ GPU: {self.config['system']['hardware']['target_gpu']}\n"
            f"🧠 Моделей: 16 уникальных / 20 ролей\n"
            f"📡 Ollama: `{self.ollama_url}`\n\n"
            "*Команды:*\n"
            "/status — статус системы\n"
            "/models — список моделей и ролей\n"
            "/test — запуск VRAM-теста\n\n"
            "Отправь задачу текстом для роутинга в бригаду.",
            parse_mode="Markdown"
        )

    async def cmd_status(self, message: Message):
        if message.from_user.id != self.admin_id:
            return

        # Check Ollama connectivity
        import aiohttp
        ollama_status = "❌ Недоступен"
        model_count = 0
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        model_count = len(data.get('models', []))
                        ollama_status = f"✅ Online ({model_count} моделей)"
        except Exception:
            pass

        # Count roles
        total_roles = sum(
            len(brigade['roles'])
            for brigade in self.config['brigades'].values()
        )

        status_msg = (
            f"🛠️ *System Status:*\n\n"
            f"📦 Framework: `{self.config['system']['framework']}` v{self.config['system']['version']}\n"
            f"🎮 GPU: `{self.config['system']['hardware']['target_gpu']}`\n"
            f"💾 VRAM: {self.config['system']['hardware']['vram_limit_gb']}GB (max 1 модель)\n"
            f"📡 Ollama: `{self.ollama_url}` — {ollama_status}\n"
            f"🏴 Бригады: Dmarket + OpenClaw ({total_roles} ролей)\n"
            f"🧠 Inference: {self.config['system']['hardware']['inference_engine']}"
        )
        await message.reply(status_msg, parse_mode="Markdown")

    async def cmd_models(self, message: Message):
        if message.from_user.id != self.admin_id:
            return

        models_msg = "🧠 *Модели по бригадам:*\n\n"
        for brigade_name, brigade_info in self.config['brigades'].items():
            models_msg += f"🏴 *{brigade_name}:*\n"
            for role, data in brigade_info['roles'].items():
                models_msg += f"  • `{role}` → `{data['model']}`\n"
            models_msg += "\n"

        # Count unique models
        all_models = set()
        for brigade_info in self.config['brigades'].values():
            for data in brigade_info['roles'].values():
                all_models.add(data['model'])
        models_msg += f"📊 *Уникальных моделей:* {len(all_models)}"

        await message.reply(models_msg, parse_mode="Markdown")

    async def cmd_test(self, message: Message):
        if message.from_user.id != self.admin_id:
            return

        await message.reply("🔬 Запускаю VRAM-тестирование всех моделей...\nЭто может занять 10-20 минут.", parse_mode="Markdown")

        # Launch pull_and_test.py as subprocess
        try:
            process = await asyncio.create_subprocess_exec(
                "python", "pull_and_test.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd="."
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                await message.reply("✅ VRAM-тест завершён! Результаты отправлены в чат.", parse_mode="Markdown")
            else:
                error = stderr.decode()[:500] if stderr else "Unknown error"
                await message.reply(f"❌ Ошибка тестирования:\n```\n{error}\n```", parse_mode="Markdown")
        except Exception as e:
            await message.reply(f"❌ Не удалось запустить тест: `{e}`", parse_mode="Markdown")

    async def cmd_test_all_models(self, message: Message):
        if message.from_user.id != self.admin_id:
            return

        status_msg = await message.reply("🚀 *Начинаю тестирование 20 моделей!*\n\nКаждая из ролей сейчас пройдет проверку отклика, чтобы подтвердить свои эмоции и характер. Ожидайте...", parse_mode="Markdown")
        
        import aiohttp
        final_report = "📊 *Отчет: Парад Планет (20 Ролей)*\n\n"
        
        async def fetch_hello(session, role_name, model_name, sys_prompt):
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": f"{sys_prompt}. Представься одним коротким предложением (максимум 5-7 слов), используя свои эмодзи."},
                    {"role": "user", "content": "Привет, проверка связи!"}
                ],
                "stream": False,
                "keep_alive": 0
            }
            try:
                # Set a moderate timeout in case a model isn't pulled or is failing
                timeout = aiohttp.ClientTimeout(total=45)
                async with session.post(f"{self.ollama_url}/api/chat", json=payload, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['message']['content'].strip().replace("\n", " ")
                    else:
                        return f"⚠️ Ошибка API ({resp.status})"
            except Exception as e:
                return f"❌ Timeout/Error: Модель не загружена"

        async with aiohttp.ClientSession() as session:
            for brigade_name, brigade_info in self.config['brigades'].items():
                final_report += f"🏴 *Бригада: {brigade_name}*\n"
                
                # Check models sequence (simulate Task Queue to avoid VRAM Thrashing)
                for role, data in brigade_info['roles'].items():
                    sys_prompt = data.get("system_prompt", "Обычный ассистент")
                    model_name = data.get("model")
                    
                    # Update status slightly
                    await self.archivist.send_status(role, model_name, "Пингую Ollama API...")
                    
                    response_text = await fetch_hello(session, role, model_name, sys_prompt)
                    final_report += f"• `{role}`: {response_text}\n"
                    
                final_report += "\n"
        
        # Send final long report using archivist to split correctly
        await self.archivist.send_summary("Результаты тестирования всех ролей", final_report)
        await status_msg.edit_text("✅ *Тестирование завершено!*\nВсе данные отправлены.", parse_mode="Markdown")

    async def handle_prompt(self, message: Message):
        if message.from_user.id != self.admin_id:
            return

        prompt = message.text
        logger.info(f"Received prompt: {prompt}")

        # 1. Planner Scope Resolution (Routing)
        brigade = "OpenClaw"
        dmarket_keywords = ["buy", "sell", "dmarket", "trade", "price", "hft", "arbitrage",
                           "купить", "продать", "торговля", "цена", "арбитраж", "дмаркет"]
        if any(kw in prompt.lower() for kw in dmarket_keywords):
            brigade = "Dmarket"

        status_msg = await message.reply(
            f"🤖 *Planner ({brigade})* анализирует задачу...\n"
            f"_Ожидайте ответа (загрузка модели)..._",
            parse_mode="Markdown"
        )

        await self.archivist.send_status(
            f"Planner ({brigade})", "Routing",
            f"Задача направлена в бригаду {brigade}..."
        )

        # 2. Call Ollama API for the Planner
        planner_config = self.config['brigades'][brigade]['roles']['Planner']
        planner_model = planner_config['model']
        planner_prompt = planner_config.get('system_prompt', 'Ты ИИ-ассистент.')
        planner_prompt += " Отвечай предельно четко, понятно, по делу и без лишней воды. Если тебе задают прямые вопросы - отвечай на них прямо. Не используй слишком сложное форматирование, которое может сломать Markdown."

        import aiohttp
        import re
        llm_response = ""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": planner_model,
                    "messages": [
                        {"role": "system", "content": planner_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "keep_alive": "5m"
                }
                timeout = aiohttp.ClientTimeout(total=120)
                async with session.post(f"{self.ollama_url}/api/chat", json=payload, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        llm_response = data['message']['content'].strip()
                        # Удаляем теги <think>...</think> если это модель deepseek-r1
                        llm_response = re.sub(r'<think>.*?</think>', '', llm_response, flags=re.DOTALL).strip()
                    else:
                        llm_response = f"⚠️ Ошибка API ({resp.status})"
        except Exception as e:
            llm_response = f"❌ Ошибка подключения: {e}"

        # 3. Send final response to User
        try:
            await status_msg.edit_text(
                f"🏴 *Бригада:* {brigade} | *Модель:* `{planner_model}`\n\n"
                f"{llm_response}",
                parse_mode="Markdown"
            )
        except Exception as e:
            # Если сломался Markdown
            await status_msg.edit_text(
                f"🏴 Бригада: {brigade} | Модель: {planner_model}\n\n"
                f"{llm_response}"
            )

        # 4. Memory GC Log Compression
        # gc = MemoryGarbageCollector(self.ollama_url)

        # 5. Final Report (для логов Архивариуса)
        roles = list(self.config['brigades'][brigade]['roles'].keys())
        await self.archivist.send_summary(
            f"Задача обработана ({brigade})",
            f"Промпт: {prompt}\n\n"
            f"*Ответ Planner:* {llm_response[:300]}...\n\n"
            f"*Бригада:* {brigade} (Ролей: {len(roles)})"
        )

    async def run(self):
        logger.info("Starting OpenClaw Gateway...")
        logger.info(f"Ollama URL: {self.ollama_url}")
        logger.info(f"Admin ID: {self.admin_id}")
        
        # Support ENV vars from start_wsl.sh
        use_webhook_env = os.environ.get("USE_WEBHOOK")
        if use_webhook_env == "1":
            use_webhook = True
            webhook_url = os.environ.get("WEBHOOK_URL", "")
        else:
            use_webhook = self.config["system"]["telegram"].get("use_webhook", False)
            webhook_url = self.config["system"]["telegram"].get("webhook_url", "")
        
        if use_webhook and webhook_url:
            from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
            from aiohttp import web
            
            await self.bot.set_webhook(webhook_url, drop_pending_updates=True)
            logger.info(f"🌐 Running in Webhook mode (URL: {webhook_url})")
            
            app = web.Application()
            webhook_requests_handler = SimpleRequestHandler(dispatcher=self.dp, bot=self.bot)
            webhook_requests_handler.register(app, path="/webhook")
            setup_application(app, self.dp, bot=self.bot)
            
            runner = web.AppRunner(app)
            await runner.setup()
            port = self.config["system"]["telegram"].get("webhook_port", 8080)
            site = web.TCPSite(runner, '0.0.0.0', port)
            await site.start()
            logger.info(f"✅ Webhook server listening on port {port}")
            
            # Keep process alive
            await asyncio.Event().wait()
        else:
            logger.info("🔄 Running in Long-Polling mode")
            await self.bot.delete_webhook(drop_pending_updates=True)
            await self.dp.start_polling(self.bot)


if __name__ == "__main__":
    acquire_lock()
    print("-" * 30)
    print("🚀 OpenClaw Gateway Starting...")
    print("💡 Tip: Use 'python main.py' (Python 3.11) to avoid ModuleNotFoundError.")
    print("-" * 30)
    try:
        gateway = OpenClawGateway()
        asyncio.run(gateway.run())
    except KeyboardInterrupt:
        print("\n🛑 OpenClaw Gateway stopped by user (Graceful Shutdown).")
    finally:
        release_lock()
