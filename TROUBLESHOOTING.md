# Troubleshooting

## OpenRouter API Connection

OpenRouter — основной провайдер LLM инференса (cloud-only).

**Конфигурация:**

- API URL: `https://openrouter.ai/api/v1`
- Модели: тированные (fast/balanced/premium/reasoning)
- Ключ: OPENROUTER_API_KEY в environment variables

**Возможные проблемы:**

1. Rate-limit → SmartModelRouter автоматически переключает модель
2. 401 Unauthorized → проверить OPENROUTER_API_KEY
3. Таймаут → проверить https://openrouter.ai/status
4. Модель недоступна → проверить доступность на https://openrouter.ai/models

## Legacy: Ollama Windows to WSL Connection (deprecated)

Данная секция сохранена для справки. Локальные модели удалены — миграция на OpenRouter завершена 2026-04.
