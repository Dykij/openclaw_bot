# 🤖 OpenClaw Bot — Документация

## Быстрый старт

### Установка
```bash
git clone https://github.com/Dykij/openclaw_bot.git
cd openclaw_bot
pip install -r requirements.txt
```

### Настройка
1. Создайте файл `.env` на основе `.env.example`
2. Укажите ваш OpenRouter API ключ: `OPENROUTER_API_KEY=sk-...`
3. Настройте конфигурацию в `config/openclaw_config.json`

### Запуск
```bash
python -m src.main
```

## Архитектура

OpenClaw Bot — cloud-only AI ассистент на базе OpenRouter. Основные компоненты:

- **Pipeline Executor** (`src/pipeline/`) — Chain-of-Agents оркестрация
- **LLM Gateway** (`src/llm_gateway.py`) — маршрутизация к OpenRouter
- **Deep Research** (`src/research/`) — мультиисточниковый исследовательский движок
- **Memory System** (`src/memory/`, `src/supermemory.py`) — многоуровневая память
- **Safety** (`src/safety/`) — защита от галлюцинаций и инъекций

## Агенты и Бригады

Бот использует 20 ролей агентов, организованных в 3 бригады:
- **Dmarket-Dev** (3 роли) — разработка и торговля
- **OpenClaw-Core** (9 ролей) — ядро бота
- **Research-Ops** (3 роли) — исследования и аналитика

## Конфигурация

Основной файл конфигурации: `config/openclaw_config.json`

### Ключевые параметры:
- `inference_engine` — движок инференса (openrouter)
- `openrouter.api_key` — ваш API ключ
- `brigades` — настройка бригад и ролей
- `routing` — правила маршрутизации запросов

## MCP Инструменты

Бот поддерживает MCP (Model Context Protocol) инструменты:
- `web_search` — поиск в интернете
- `web_fetch` — загрузка веб-страниц
- `news_search` — поиск новостей
- `session-logs` — логирование сессий
- `github` — интеграция с GitHub
- `coding-agent` — помощник по коду

## Безопасность

- **Hallucination Detector** — обнаружение галлюцинаций через MARCH Protocol
- **Prompt Injection Defender** — защита от инъекций промптов
- **Constitutional AI** — проверка ответов на соответствие правилам
- **HITL Gate** — Human-in-the-Loop одобрение для рисковых операций

## Устранение неполадок

### Бот не отвечает
1. Проверьте `.env` файл — убедитесь что `OPENROUTER_API_KEY` установлен
2. Проверьте баланс на OpenRouter
3. Проверьте логи в терминале

### Ошибки памяти
- Перезапустите бот для очистки кэшей
- Проверьте доступ к `data/` директории

### Медленные ответы
- Проверьте задержку OpenRouter на status.openrouter.ai
- Уменьшите количество пропозеров MoA в конфиге
