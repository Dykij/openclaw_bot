---
tags:
  - brigade
  - openclaw
  - framework
category: domain-knowledge
difficulty: intermediate
training: true
created: 2026-06-30
---

# OpenClaw-Core Brigade

Бригада ядра фреймворка — отвечает за самосовершенствование OpenClaw.

## Состав цепочки

```
Planner → Foreman → Executor_Tools → Executor_Architect → Auditor → State_Manager → Archivist
```

## Правила

1. **Full access**: может модифицировать фреймворк и любой код
2. **System commands**: разрешены (`can_execute_system_commands: true`)
3. **No restricted namespaces**: полный доступ к системным библиотекам
4. **Security Auditor**: Monitors for unauthorized sandbox escapes
5. **Auto-rollback**: `AutoRollback` откатывает git-изменения при сломанном коде

## Компоненты доступа

- **MCP клиент**: `OpenClawMCPClient` с полным доступом к filesystem фреймворка
- **DynamicSandbox**: генерация → валидация → выполнение → сохранение как skill
- **CodeValidator**: статический анализ перед коммитом
- **SuperMemory**: полный доступ (store, recall, episodes, GC)

## Типичные задачи

- Рефакторинг пайплайна (AFlow, LATS, Reflexion)
- Добавление новых агентских ролей
- Улучшение SuperMemory и auto-learning
- Обновление скиллов и Knowledge Base
- Инфраструктурные изменения (Docker, fly.toml, CI)

## Self-Evolution

SAGE Engine анализирует feedback Auditor-а и генерирует:

- Коррекции system-промптов ролей
- Новые паттерны для `special_skills.json`
- Предложения по изменению цепочки

## Модели

- **Planner/Foreman**: `qwen/qwen3.6-plus:free`
- **Executor_Tools**: `qwen/qwen3.6-plus:free`
- **Executor_Architect**: `qwen/qwen3.6-plus:free`
- **Auditor**: `qwen/qwen3.6-plus:free`
- **State_Manager/Archivist**: `qwen/qwen3.6-plus:free`
