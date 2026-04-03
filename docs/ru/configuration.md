# ⚙️ Конфигурация OpenClaw Bot

## Основной конфиг

Файл: `config/openclaw_config.json`

### Секция OpenRouter
```json
{
  "inference_engine": "openrouter",
  "openrouter": {
    "api_key": "sk-or-...",
    "base_url": "https://openrouter.ai/api/v1",
    "default_model": "nvidia/nemotron-3-super-120b-a12b:free"
  }
}
```

### Используемые модели
| Модель | Роли | Назначение |
|--------|------|------------|
| nvidia/nemotron-3-super-120b-a12b:free | 12 ролей | Основная модель |
| arcee-ai/trinity-large-preview:free | 2 роли | Исследования |
| arcee-ai/trinity-mini:free | 3 роли | Лёгкие задачи |

### Секция бригад
```json
{
  "brigades": {
    "Dmarket-Dev": {
      "lead": "dmarket-lead",
      "roles": ["trader", "analyst", "dev"]
    }
  }
}
```

## Переменные окружения

| Переменная | Описание | Обязательная |
|-----------|----------|-------------|
| OPENROUTER_API_KEY | Ключ API OpenRouter | ✅ |
| TELEGRAM_BOT_TOKEN | Токен Telegram бота | ✅ |
| FIRECRAWL_API_KEY | Ключ Firecrawl (опционально) | ❌ |
| OTEL_ENABLED | Включить OpenTelemetry трейсинг | ❌ |

## Навыки (Skills)

Каждой роли назначаются навыки из ClawHub:
- Универсальные (все 20 ролей): clawhub, session-logs, github, summarize, gemini, oracle
- Кодинг: coding-agent, tmux, gh-issues, mcporter
- Поиск: blogwatcher, xurl
