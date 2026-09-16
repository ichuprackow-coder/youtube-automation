# YouTube Automation Pipeline

Готовый каркас для полностью автоматизированного YouTube-пайплайна на GitHub Actions для русскоязычного IT-канала с публикацией **3 видео в неделю**.

Выбранный стек:
- **LLM:** OpenAI Chat Completions (`LLM_PROVIDER=openai`) с опцией Gemini
- **Озвучка:** `edge-tts` по умолчанию, ElevenLabs опционально
- **Видео:** Python + FFmpeg
- **Превью:** Pillow-шаблон по умолчанию, OpenAI image generation опционально
- **Загрузка и аналитика:** YouTube Data API v3 + YouTube Analytics API

## Шаг 1. Репозиторий и структура

```bash
mkdir youtube-automation
cd youtube-automation
git init
git remote add origin git@github.com:ichuprackow-coder/youtube-automation.git
git add .
git commit -m "Initial YouTube automation pipeline"
git push -u origin main
```

Если репозиторий уже создан:

```bash
git clone git@github.com:ichuprackow-coder/youtube-automation.git
cd youtube-automation
```

Структура:

```text
.
├── .github/workflows/youtube-pipeline.yml
├── assets/
│   ├── backgrounds/
│   └── music/
├── config/
├── data/
│   ├── analytics/
│   ├── audio/
│   ├── scripts/
│   ├── thumbnails/
│   └── videos/
├── scripts/
│   ├── build_video.py
│   ├── check_publish_approval.py
│   ├── common.py
│   ├── fetch_analytics.py
│   ├── generate_script.py
│   ├── generate_thumbnail.py
│   ├── generate_tts.py
│   ├── publish_video.py
│   ├── topic_research.py
│   └── upload_youtube.py
├── .env.example
├── .gitignore
├── Dockerfile
└── requirements.txt
```

`.gitignore` уже настроен: секреты, OAuth-файлы, медиа-артефакты и runtime-логи не коммитятся.

## Шаг 2. API-ключи и GitHub Secrets

Нужные секреты:

| Secret | Где получить |
| --- | --- |
| `YOUTUBE_API_KEY` | Google Cloud Console → APIs & Services → Credentials |
| `YOUTUBE_CLIENT_SECRET_JSON` | Google Cloud Console → OAuth client JSON |
| `YOUTUBE_TOKEN_JSON` | Локально после OAuth-авторизации (`config/token.json`) |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `GEMINI_API_KEY` | Google AI Studio |
| `ELEVENLABS_API_KEY` | https://elevenlabs.io |
| `TELEGRAM_BOT_TOKEN` | @BotFather |
| `TELEGRAM_CHAT_ID` | ID чата/канала Telegram |
| `GITHUB_TOKEN` | встроенный токен Actions |

Как добавить:
1. GitHub → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**
3. Добавьте секреты из таблицы выше

Пример переменных окружения: см. [`.env.example`](./.env.example).

Чтобы сохранить OAuth JSON в GitHub Secrets:

```bash
# client_secret.json
cat config/client_secret.json

# token.json после первого локального запуска upload_youtube.py
cat config/token.json
```

Скопируйте содержимое целиком в `YOUTUBE_CLIENT_SECRET_JSON` и `YOUTUBE_TOKEN_JSON`.

## Шаг 3. Topic research

Готовый скрипт: [`scripts/topic_research.py`](./scripts/topic_research.py)

Что делает:
1. Ищет популярные видео по нише через YouTube Data API
2. Извлекает ключевые слова и оценивает конкуренцию
3. Просит LLM сгенерировать 5 идей
4. Сохраняет результат в `data/topics.json`

Локальный запуск:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# при необходимости поменяйте YOUTUBE_REGION_CODE на поддерживаемый рынок вашего канала
python scripts/topic_research.py --niche "образовательный контент про IT"
```

## Шаг 4. Генерация сценария

Готовый скрипт: [`scripts/generate_script.py`](./scripts/generate_script.py)

Возможности:
- читает тему из `data/topics.json`
- создает хук, структуру 3–5 пунктов и CTA
- генерирует SEO title/description
- подбирает теги из LLM и YouTube search suggestions
- сохраняет JSON в `data/scripts/[topic].json`

Запуск:

```bash
python scripts/generate_script.py --topic "Как войти в DevOps в 2026"
```

## Шаг 5. Озвучка

Готовый скрипт: [`scripts/generate_tts.py`](./scripts/generate_tts.py)

### Edge-TTS

Установка уже включена в `requirements.txt`.

Локальный запуск:

```bash
python scripts/generate_tts.py --topic "Как войти в DevOps в 2026"
```

CLI-аналог Edge-TTS:

```bash
edge-tts --voice ru-RU-SvetlanaNeural --text "Тестовая фраза" --write-media /tmp/test.mp3
```

### ElevenLabs

Переключение:

```bash
export TTS_PROVIDER=elevenlabs
export ELEVENLABS_API_KEY=...
export ELEVENLABS_VOICE_ID=...
python scripts/generate_tts.py --topic "Как войти в DevOps в 2026"
```

## Шаг 6. Сборка видео через FFmpeg

Готовый скрипт: [`scripts/build_video.py`](./scripts/build_video.py)

Что делает:
- берет `data/audio/[topic].mp3`
- берет изображения из `assets/backgrounds/`
- строит видео со `subtitles`, `xfade` и фоновой музыкой из `assets/music/`
- сохраняет `data/videos/[topic].mp4`

Пример ручной команды FFmpeg, которую генерирует тот же подход:

```bash
ffmpeg -loop 1 -t 12 -i assets/backgrounds/scene1.png \
  -i data/audio/topic.mp3 \
  -vf "scale=1920:1080,subtitles=/tmp/topic.srt" \
  -c:v libx264 -c:a aac -shortest data/videos/topic.mp4
```

## Шаг 7. Генерация thumbnail

Готовый скрипт: [`scripts/generate_thumbnail.py`](./scripts/generate_thumbnail.py)

По умолчанию:
- генерирует короткий промт через LLM
- если включен AI image provider, запрашивает изображение
- в любом случае накладывает текст через Pillow
- сохраняет `data/thumbnails/[topic].png`

Без AI-картинки:

```bash
export THUMBNAIL_PROVIDER=template
python scripts/generate_thumbnail.py --topic "Как войти в DevOps в 2026"
```

## Шаг 8. Автозагрузка на YouTube

Готовый скрипт: [`scripts/upload_youtube.py`](./scripts/upload_youtube.py)

Возможности:
- OAuth 2.0 авторизация
- загрузка видео, title, description, tags, privacy status
- установка thumbnail
- добавление в playlist
- логирование в `data/upload_log.json`

Первый локальный запуск для получения `token.json`:

```bash
python scripts/upload_youtube.py --topic "Как войти в DevOps в 2026"
```

Если `config/token.json` отсутствует, откроется OAuth-flow. После авторизации загрузите `token.json` в GitHub Secret `YOUTUBE_TOKEN_JSON`.

## Шаг 9. GitHub Actions workflow

Готовый workflow: [`.github/workflows/youtube-pipeline.yml`](./.github/workflows/youtube-pipeline.yml)

Что уже настроено:
1. `schedule` каждые 2 дня
2. `workflow_dispatch`
3. Последовательность `topic research → script → TTS → video → thumbnail → upload`
4. Все ключи идут через `secrets`
5. Готовое видео и логи сохраняются через `actions/upload-artifact`
6. В Telegram отправляется статус

## Шаг 10. Уведомления и мониторинг

В workflow добавлены:
- уведомление в Telegram через Bot API
- ежедневный отчет по завершенному дню в `data/analytics/`
- чтение CTR превью через `impressionsClickThroughRate`

Локальный запуск аналитики:

```bash
python scripts/fetch_analytics.py --latest
```

Для первого полноценного 24-часового отчета повторно запустите `fetch_analytics.py --latest` через сутки после публикации или вынесите этот шаг в отдельный scheduled workflow.

## Дополнительно

### Ручная проверка перед публикацией

Рекомендуемый сценарий:
1. В `.env`/Secrets держите `YOUTUBE_PRIVACY_STATUS=unlisted`
2. Создаете GitHub Issue, например `Publish video 123`
3. Добавляете label `publish-approved`
4. Запускаете:

```bash
python scripts/check_publish_approval.py --issue-number 12
python scripts/publish_video.py --latest --privacy-status public
```

Эти же шаги уже заложены в workflow как опциональный ручной job через `workflow_dispatch`.

### A/B-тест заголовков и превью

Практичный вариант:
- запускать `generate_script.py` дважды с разными промтами
- хранить варианты `title_options` и `thumbnail_text_options` в JSON
- публиковать видео как `unlisted`
- менять title/thumbnail через `publish_video.py` после первых метрик CTR

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Docker

```bash
docker build -t youtube-automation .
docker run --rm --env-file .env \
  -v "$(pwd)/config:/app/config" \
  -v "$(pwd)/assets:/app/assets" \
  -v "$(pwd)/data:/app/data" \
  youtube-automation \
  python scripts/topic_research.py
```

## Быстрый end-to-end запуск

```bash
python scripts/topic_research.py
python scripts/generate_script.py
python scripts/generate_tts.py
python scripts/build_video.py
python scripts/generate_thumbnail.py
python scripts/upload_youtube.py
python scripts/fetch_analytics.py --latest
```
