# ClawHub Skills → Роли агентов: Максимальный маппинг v2

> 38 из 53 ClawHub-скилов назначены. 342 назначения на 20 ролей.
> Дата: 2026-03-30

## Обзор

| Бригада | Ролей | Скилов назначено | Δ от v1 |
|---------|-------|------------------|---------|
| Dmarket-Dev | 3 | 55 | +39 |
| OpenClaw-Core | 9 | 151 | +102 |
| Research-Ops | 3 | 61 | +46 |
| Автономные агенты | 5 | 75 | +51 |
| **Итого** | **20** | **342** | **+238** |

---

## 🏭 Бригада: Dmarket-Dev

### Planner (Оркестратор) — 24 скила
**Модель:** `nvidia/nemotron-3-super-120b-a12b:free`
**Домен:** HFT-трейдинг, Dmarket API, арбитраж CS2 скинов

| Категория | Скилы |
|-----------|-------|
| Ядро | `clawhub`, `session-logs`, `github`, `summarize`, `gemini`, `oracle` |
| PM/Задачи | `gh-issues`, `trello`, `notion`, `things-mac`, `obsidian` |
| Коммуникации | `discord`, `slack`, `himalaya`, `wacli`, `voice-call` |
| Аналитика | `weather`, `xurl`, `blogwatcher`, `model-usage` |
| Инструменты | `coding-agent`, `canvas`, `nano-pdf`, `gog` |

### Coder (Разработчик) — 17 скилов
**Модель:** `nvidia/nemotron-3-super-120b-a12b:free`
**Домен:** Python/asyncio, Dmarket API, WebSocket, HMAC

| Категория | Скилы |
|-----------|-------|
| Ядро | `clawhub`, `session-logs`, `github`, `summarize`, `gemini`, `oracle` |
| Разработка | `coding-agent`, `tmux`, `skill-creator`, `template-skill`, `mcporter` |
| Медиа | `canvas`, `nano-pdf`, `video-frames`, `openai-whisper-api` |
| Трекинг | `gh-issues`, `model-usage` |

### Auditor (Безопасность) — 14 скилов
**Модель:** `nvidia/nemotron-3-super-120b-a12b:free`
**Домен:** Security audit, injection, credentials, risk

| Категория | Скилы |
|-----------|-------|
| Ядро | `clawhub`, `session-logs`, `github`, `summarize`, `gemini`, `oracle` |
| Безопасность | `healthcheck`, `1password`, `mcporter` |
| Разработка | `coding-agent`, `tmux` |
| Трекинг | `gh-issues`, `model-usage`, `nano-pdf` |

---

## ⚙️ Бригада: OpenClaw-Core

### Planner — 25 скилов
`apple-notes`, `blogwatcher`, `canvas`, `clawhub`, `coding-agent`, `discord`, `gemini`, `gh-issues`, `github`, `gog`, `himalaya`, `model-usage`, `nano-pdf`, `notion`, `obsidian`, `oracle`, `session-logs`, `slack`, `summarize`, `things-mac`, `tmux` *(отсутствует — планировщик)*, `trello`, `voice-call`, `wacli`, `weather`, `xurl`

### Foreman — 17 скилов
`clawhub`, `coding-agent`, `discord`, `gemini`, `gh-issues`, `github`, `healthcheck`, `mcporter`, `model-usage`, `notion`, `oracle`, `session-logs`, `skill-creator`, `slack`, `summarize`, `tmux`, `trello`

### Executor_Architect — 15 скилов
`canvas`, `clawhub`, `coding-agent`, `gemini`, `gh-issues`, `github`, `mcporter`, `model-usage`, `nano-pdf`, `oracle`, `session-logs`, `skill-creator`, `summarize`, `template-skill`, `tmux`

### Executor_Tools — 19 скилов
`canvas`, `clawhub`, `coding-agent`, `gemini`, `gh-issues`, `github`, `mcporter`, `model-usage`, `nano-banana-pro`, `nano-pdf`, `openai-whisper-api`, `oracle`, `peekaboo`, `session-logs`, `skill-creator`, `summarize`, `template-skill`, `tmux`, `video-frames`

### Executor_Integration — 18 скилов
`canvas`, `clawhub`, `coding-agent`, `discord`, `gemini`, `gh-issues`, `github`, `healthcheck`, `mcporter`, `model-usage`, `notion`, `oracle`, `session-logs`, `skill-creator`, `slack`, `summarize`, `tmux`, `voice-call`

### Auditor — 14 скилов
`1password`, `clawhub`, `coding-agent`, `gemini`, `gh-issues`, `github`, `healthcheck`, `mcporter`, `model-usage`, `nano-pdf`, `oracle`, `session-logs`, `summarize`, `tmux`

### Archivist — 19 скилов
`apple-notes`, `bear-notes`, `canvas`, `clawhub`, `discord`, `gemini`, `github`, `gog`, `himalaya`, `nano-pdf`, `notion`, `obsidian`, `oracle`, `session-logs`, `slack`, `summarize`, `things-mac`, `trello`, `wacli`

### State_Manager — 12 скилов
`canvas`, `clawhub`, `coding-agent`, `gemini`, `github`, `model-usage`, `nano-pdf`, `notion`, `obsidian`, `oracle`, `session-logs`, `summarize`

### Test_Writer — 12 скилов
`clawhub`, `coding-agent`, `gemini`, `gh-issues`, `github`, `mcporter`, `model-usage`, `oracle`, `session-logs`, `summarize`, `template-skill`, `tmux`

---

## 🔬 Бригада: Research-Ops

### Researcher — 24 скила
`blogwatcher`, `camsnap`, `canvas`, `clawhub`, `coding-agent`, `gemini`, `gh-issues`, `github`, `gog`, `goplaces`, `himalaya`, `model-usage`, `nano-banana-pro`, `nano-pdf`, `notion`, `obsidian`, `openai-whisper-api`, `oracle`, `session-logs`, `summarize`, `tmux`, `video-frames`, `weather`, `xurl`

### Analyst — 20 скилов
`blogwatcher`, `canvas`, `clawhub`, `coding-agent`, `gemini`, `gh-issues`, `github`, `goplaces`, `model-usage`, `nano-pdf`, `notion`, `obsidian`, `openai-whisper-api`, `oracle`, `session-logs`, `summarize`, `tmux`, `video-frames`, `weather`, `xurl`

### Summarizer — 17 скилов
`apple-notes`, `bear-notes`, `canvas`, `clawhub`, `discord`, `gemini`, `github`, `gog`, `himalaya`, `nano-pdf`, `notion`, `obsidian`, `oracle`, `session-logs`, `slack`, `summarize`, `wacli`

---

## 🤖 Автономные агенты

### Risk Manager — 16 скилов
`1password`, `clawhub`, `coding-agent`, `discord`, `gemini`, `gh-issues`, `github`, `healthcheck`, `mcporter`, `model-usage`, `nano-pdf`, `oracle`, `session-logs`, `slack`, `summarize`, `tmux`

### Latency Monitor — 14 скилов
`canvas`, `clawhub`, `coding-agent`, `gemini`, `gh-issues`, `github`, `healthcheck`, `mcporter`, `model-usage`, `nano-pdf`, `oracle`, `session-logs`, `summarize`, `tmux`

### Security Auditor — 14 скилов
`1password`, `clawhub`, `coding-agent`, `gemini`, `gh-issues`, `github`, `healthcheck`, `mcporter`, `model-usage`, `nano-pdf`, `oracle`, `session-logs`, `summarize`, `tmux`

### Tool Smith — 19 скилов
`canvas`, `clawhub`, `coding-agent`, `gemini`, `gh-issues`, `github`, `mcporter`, `model-usage`, `nano-banana-pro`, `nano-pdf`, `openai-whisper-api`, `oracle`, `peekaboo`, `session-logs`, `skill-creator`, `summarize`, `template-skill`, `tmux`, `video-frames`

### Memory Garbage Collector — 12 скилов
`canvas`, `clawhub`, `coding-agent`, `gemini`, `github`, `model-usage`, `nano-pdf`, `notion`, `obsidian`, `oracle`, `session-logs`, `summarize`

---

## 📊 Статистика использования скилов

| Скил | Ролей | Категория |
|------|-------|-----------|
| `clawhub` | 20 | Маркетплейс |
| `session-logs` | 20 | Логирование |
| `github` | 20 | DevOps |
| `summarize` | 20 | Обработка текста |
| `gemini` | 20 | AI ассистент |
| `oracle` | 20 | AI ассистент |
| `model-usage` | 18 | Мониторинг |
| `coding-agent` | 16 | Разработка |
| `gh-issues` | 15 | GitHub Issues |
| `tmux` | 13 | Терминал |
| `nano-pdf` | 15 | Документы |
| `canvas` | 13 | Визуализация |
| `mcporter` | 10 | MCP инструменты |
| `notion` | 9 | PM |
| `healthcheck` | 7 | Безопасность |
| `discord` | 7 | Коммуникации |
| `slack` | 7 | Коммуникации |
| `obsidian` | 7 | Заметки |
| `skill-creator` | 5 | Создание скилов |
| `1password` | 4 | Секреты |
| `himalaya` | 4 | Email |
| `wacli` | 4 | WhatsApp |
| `trello` | 4 | Kanban |
| `gog` | 4 | Google Workspace |
| `weather` | 4 | Погода/корреляции |
| `xurl` | 4 | Twitter/X |
| `blogwatcher` | 4 | RSS мониторинг |
| `template-skill` | 4 | Шаблоны |
| `things-mac` | 3 | Задачи macOS |
| `video-frames` | 4 | Видеоанализ |
| `openai-whisper-api` | 4 | Транскрипция |
| `voice-call` | 3 | Голосовые звонки |
| `apple-notes` | 3 | Заметки Apple |
| `bear-notes` | 2 | Заметки Bear |
| `goplaces` | 2 | Геолокация |
| `nano-banana-pro` | 3 | Генерация изображений |
| `peekaboo` | 2 | macOS автоматизация |
| `camsnap` | 1 | Камеры |

## Неиспользуемые скилы (15 из 53)

Следующие скилы **не назначены** ни одной роли — они слишком нишевые:

| Скил | Причина |
|------|---------|
| `apple-reminders` | macOS-only, дублирует things-mac |
| `blucli` | BluOS аудио — нишевое |
| `bluebubbles` | iMessage — дублирует imsg |
| `eightctl` | Eight Sleep pod — IoT |
| `gifgrep` | GIF поиск — развлекательное |
| `imsg` | iMessage — macOS-only |
| `openai-image-gen` | Дублирует nano-banana-pro |
| `openai-whisper` | Локальный — дублирует API версию |
| `openhue` | Philips Hue — IoT |
| `ordercli` | Foodora заказы — нишевое |
| `sag` | ElevenLabs TTS — нишевое |
| `sherpa-onnx-tts` | Локальный TTS — нишевое |
| `songsee` | Аудио визуализация — нишевое |
| `sonoscli` | Sonos колонки — IoT |
| `spotify-player` | Spotify — развлекательное |
