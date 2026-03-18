# Telemelya — Mock Telegram Bot API

Фреймворк для BDD-тестирования Telegram-ботов. Предоставляет mock-сервер Telegram Bot API (FastAPI + Redis + MinIO) и Python-клиент для тестирования с интеграцией behave/Gherkin.

## Содержание

- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация mock-сервера](#конфигурация-mock-сервера)
- [API mock-сервера](#api-mock-сервера)
- [Тестовый клиент](#тестовый-клиент)
- [BDD-тестирование](#bdd-тестирование)
- [Изоляция сессий](#изоляция-сессий)
- [Поддержка нескольких ботов](#поддержка-нескольких-ботов)
- [Адаптер для aiogram](#создание-бот-сервисов-с-адаптером-telemelya-aiogram)
- [Примеры типовых архитектур](#примеры-типовых-архитектур)
- [CI/CD](#cicd-github-actions)
- [Рекомендации](#рекомендации)
- [Лицензия](#лицензия)

---

## Архитектура

```
Тестовый клиент (behave)  →  Mock Telegram Bot API  →  Бот (webhook)
                                   ├── Redis (состояние)
                                   └── MinIO (медиа)
```

1. Бот регистрирует webhook на mock-сервере
2. Тестовый клиент отправляет обновления через Control API → mock-сервер доставляет их на webhook бота
3. Бот обрабатывает обновление и вызывает эндпоинты Bot API mock-сервера (`sendMessage`, `sendPhoto` и т.д.)
4. Mock-сервер записывает ответы в Redis, медиа — в MinIO
5. Тестовый клиент получает ответы и проверяет их

---

## Быстрый старт

### Локальная разработка

1. Скопируйте `.env.example` в `.env` и при необходимости измените настройки
2. Запустите инфраструктуру:
   ```bash
   make local-up
   ```
3. Запустите вашего бота, указав mock-сервер:
   ```bash
   TELEMELYA_URL=http://localhost:8080 BOT_TOKEN=123456:ABC python your_bot.py
   ```
4. Запустите тесты:
   ```bash
   pip install -r requirements-client.txt
   make test
   ```
5. Остановка:
   ```bash
   make local-down
   ```

### Развёртывание на сервере (VPS)

1. Настройте `.env` — укажите домен, учётные данные MinIO и API-ключи
2. Обновите `Caddyfile`, указав ваш домен
3. Развёрните:
   ```bash
   docker compose up -d
   ```
4. Укажите вашему боту `TELEMELYA_URL=https://mock.ваш-домен.com`

---

## Конфигурация mock-сервера

Все настройки задаются через переменные окружения (см. `.env.example`):

| Переменная | По умолчанию | Описание |
|---|---|---|
| `MOCK_SERVER_HOST` | `0.0.0.0` | Хост для привязки сервера |
| `MOCK_SERVER_PORT` | `8080` | Порт сервера |
| `MOCK_SERVER_URL` | `http://localhost:8080` | Публичный URL mock-сервера |
| `REDIS_URL` | `redis://localhost:6379/0` | URL подключения к Redis |
| `MINIO_ENDPOINT` | `localhost:9000` | Эндпоинт MinIO |
| `MINIO_ACCESS_KEY` | `minioadmin` | Ключ доступа MinIO |
| `MINIO_SECRET_KEY` | `minioadmin` | Секретный ключ MinIO |
| `MINIO_BUCKET` | `test-media` | Имя бакета MinIO |
| `MINIO_USE_SSL` | `false` | Использовать SSL для MinIO |
| `AUTH_KEYS` | `` | API-ключи через запятую |

---

## API mock-сервера

### Bot API (`/bot{token}/...`)

Эмулирует `api.telegram.org`:

| Метод | Эндпоинт | Описание |
|---|---|---|
| POST | `/bot{token}/getMe` | Информация о боте |
| POST | `/bot{token}/setWebhook` | Регистрация webhook |
| POST | `/bot{token}/deleteWebhook` | Удаление webhook |
| POST | `/bot{token}/sendMessage` | Отправка текстового сообщения |
| POST | `/bot{token}/sendPhoto` | Отправка фото |
| POST | `/bot{token}/getFile` | Получение информации о файле |
| GET | `/bot{token}/file/{file_path}` | Скачивание файла |
| POST | `/bot{token}/answerCallbackQuery` | Ответ на callback-запрос |
| POST | `/bot{token}/editMessageText` | Редактирование сообщения |

### Control API (`/api/v1/test/...`)

Требует заголовок `Authorization: Bearer <api_key>`:

| Метод | Эндпоинт | Описание |
|---|---|---|
| POST | `/api/v1/test/send_update?bot_token=...` | Отправить обновление боту |
| GET | `/api/v1/test/responses?session_id=...` | Получить ответы бота |
| GET | `/api/v1/test/responses/wait?session_id=...&timeout=5` | Ожидание ответа (long-poll) |
| POST | `/api/v1/test/reset?session_id=...` | Сброс состояния сессии |
| GET | `/api/v1/test/media/{file_id}?session_id=...` | Скачать медиафайл |
| GET | `/api/v1/test/health` | Проверка работоспособности |

---

## Тестовый клиент

```python
from telemelya.client import TelegramTestClient, ResponseCollector

client = TelegramTestClient(
    server_url="http://localhost:8080",
    api_key="ваш-api-ключ",
    bot_token="токен-бота",
)
collector = ResponseCollector(client)

# Отправить команду
client.send_command(chat_id=12345, command="/start")

# Дождаться ответа и проверить
collector.wait_for_response(timeout=5.0)
collector.assert_text("Добро пожаловать!")

# Очистка
client.reset()
client.close()
```

### Методы `TelegramTestClient`

| Метод | Описание |
|---|---|
| `send_message(chat_id, text)` | Отправить текстовое сообщение |
| `send_command(chat_id, command)` | Отправить команду (например, `/start`) |
| `send_photo(chat_id, photo_path, caption=)` | Отправить фото |
| `send_callback_query(chat_id, data, message_id)` | Отправить callback-запрос |
| `get_responses()` | Получить все ответы бота |
| `wait_for_response(timeout=5.0)` | Дождаться ответа (long-poll) |
| `get_media(file_id)` | Скачать медиафайл |
| `reset()` | Сбросить состояние сессии |
| `close()` | Закрыть соединение |

### Методы `ResponseCollector`

| Метод | Описание |
|---|---|
| `wait_for_response(timeout=5.0)` | Дождаться ответа и сохранить |
| `assert_text(expected)` | Проверить точное совпадение текста |
| `assert_contains(substring)` | Проверить наличие подстроки |
| `assert_photo()` | Проверить, что ответ содержит фото |
| `assert_reply_markup()` | Проверить наличие клавиатуры |
| `last` | Последний полученный ответ |

---

## BDD-тестирование

Сценарии на Gherkin с поддержкой русского языка:

```gherkin
# language: ru
Функционал: Обработка команды /start

  Сценарий: Пользователь запускает бота
    Допустим chat_id "12345"
    Когда пользователь отправляет команду "/start"
    Тогда бот отвечает "Добро пожаловать!"
```

### Встроенные шаги

| Шаг | Описание |
|---|---|
| `Допустим chat_id "{id}"` | Задать ID чата |
| `Когда пользователь отправляет сообщение "{text}"` | Отправить текстовое сообщение |
| `Когда пользователь отправляет команду "{command}"` | Отправить команду |
| `Когда пользователь отправляет фото "{path}"` | Отправить фото |
| `Тогда бот отвечает "{text}"` | Проверить точный текст ответа |
| `Тогда ответ содержит "{substring}"` | Проверить наличие подстроки |
| `Тогда бот отправляет фото` | Проверить, что ответ — фото |
| `Тогда бот отправляет фото с подписью "{caption}"` | Проверить фото с подписью |

### Запуск тестов

```bash
# Все тесты
python -m behave tests/features/

# Конкретный feature-файл
python -m behave tests/features/start_command.feature

# С генерацией отчёта Allure
python -m behave tests/features/ -f allure_behave.formatter:AllureFormatter -o allure-results
allure serve allure-results
```

---

## Изоляция сессий

Каждый тестовый сценарий получает уникальный `session_id` (UUID). Клиент передаёт его через заголовок `X-Test-Session`. Это позволяет запускать тесты параллельно без конфликтов.

## Поддержка нескольких ботов

Mock-сервер различает ботов по `{token}` в URL-путях. Один сервер может обслуживать несколько ботов одновременно.

## Пример echo-бота

См. `examples/echo_bot/` — минимальный aiogram echo-бот, настроенный для работы с Telemelya.

---

## Создание бот-сервисов с адаптером `telemelya.aiogram`

Адаптер `telemelya.aiogram` позволяет писать код бота **один раз** и запускать его как в продакшне (с реальным Telegram API), так и в тестовом режиме (с mock-сервером Telemelya). Переключение — только через переменные окружения, без изменения кода.

### Принцип работы

```
                 ┌──────────────────────┐
  Ваш код бота  │    Dispatcher +      │
  (хендлеры)    │    TemelyaRunner     │
                 └──────────┬───────────┘
                            │
              ┌─────────────┴─────────────┐
              │ TELEMELYA_URL задан?        │
              ├─── Да ────────────────┐   │
              │   Bot → Mock Server   │   │
              │   Режим: webhook      │   │
              ├─── Нет ───────────────┤   │
              │   Bot → api.telegram  │   │
              │   Режим: polling      │   │
              └───────────────────────────┘
```

### Быстрый старт адаптера

#### 1. Установите зависимости

```bash
pip install telemelya[aiogram]
# или
pip install aiogram aiohttp-socks
```

#### 2. Создайте бота

```python
# my_bot.py
from aiogram import Dispatcher, types
from aiogram.filters import CommandStart
from telemelya.aiogram import TemelyaRunner

dp = Dispatcher()

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    await message.answer("Привет! Я ваш бот.")

@dp.message()
async def handle_echo(message: types.Message):
    await message.answer(message.text or "")

if __name__ == "__main__":
    runner = TemelyaRunner(dp)
    runner.run()
```

Это **весь код**. Дальше — только переменные окружения.

#### 3. Локальный запуск для отладки (polling)

По умолчанию, без `TELEMELYA_URL` и `WEBHOOK_URL`, бот запускается в polling-режиме — удобно для локальной разработки и отладки:

```bash
BOT_TOKEN=123456789:REAL_TOKEN python my_bot.py
```

Бот подключится к `api.telegram.org`, удалит старый webhook и начнёт polling.

С прокси:
```bash
BOT_TOKEN=123456789:REAL_TOKEN \
PROXY_URL=http://127.0.0.1:12334 \
python my_bot.py
```

#### 4. Продакшн (webhook)

На сервере боты обычно работают через webhook — Telegram сам отправляет обновления на ваш публичный URL. Задайте `WEBHOOK_URL`:

```bash
BOT_TOKEN=123456789:REAL_TOKEN \
WEBHOOK_URL=https://bot.example.com \
python my_bot.py
```

Адаптер автоматически выберет webhook-режим при наличии `WEBHOOK_URL`.

#### 5. Запуск в тестовом режиме (Telemelya)

```bash
# Сначала поднимите mock-сервер
docker compose -f docker-compose.local.yml up -d

# Запустите бота, указав TELEMELYA_URL
TELEMELYA_URL=http://127.0.0.1:8080 python my_bot.py
```

Бот автоматически:
- Подключится к mock-серверу вместо Telegram
- Зарегистрирует webhook (с `host.docker.internal` для Docker)
- Начнёт принимать тестовые обновления

#### 6. Напишите тесты

```python
# test_my_bot.py
from telemelya.client import TelegramTestClient, ResponseCollector

client = TelegramTestClient(
    server_url="http://127.0.0.1:8080",
    api_key="test-api-key-12345",
    bot_token="123456789:ABCDefGhIjKlMnOpQrStUvWxYz",
)
collector = ResponseCollector(client)

# Отправить /start → проверить ответ
client.send_command(chat_id=12345, command="/start")
collector.wait_for_response(timeout=5.0)
collector.assert_text("Привет! Я ваш бот.")

client.reset()
client.close()
```

Или через BDD (Gherkin):

```gherkin
# language: ru
Функционал: Основные команды бота

  Сценарий: Пользователь запускает бота
    Допустим chat_id "12345"
    Когда пользователь отправляет команду "/start"
    Тогда бот отвечает "Привет! Я ваш бот."

  Сценарий: Эхо-ответ
    Допустим chat_id "12345"
    Когда пользователь отправляет сообщение "Тест"
    Тогда бот отвечает "Тест"
```

---

### API адаптера

#### `create_bot(token, *, mock_url, proxy) → Bot`

Фабрика для создания `aiogram.Bot` с нужной конфигурацией.

| Параметр | Env-переменная | Описание |
|----------|---------------|----------|
| `token` | `BOT_TOKEN` | Токен бота (обязательный) |
| `mock_url` | `TELEMELYA_URL` | URL mock-сервера. Если задан → тестовый режим |
| `proxy` | `PROXY_URL` | HTTP/SOCKS прокси (только продакшн) |

Приоритет: параметр функции → переменная окружения.

```python
from telemelya.aiogram import create_bot

# Тест
bot = create_bot(token="fake:token", mock_url="http://localhost:8080")

# Продакшн
bot = create_bot()  # читает BOT_TOKEN из env
```

#### `TemelyaRunner(dp, **kwargs)`

Запускает `Dispatcher` в нужном режиме.

| Параметр | Env-переменная | По умолчанию | Описание |
|----------|---------------|-------------|----------|
| `dp` | — | — | aiogram `Dispatcher` (обязательный) |
| `bot` | — | `None` | Готовый `Bot` (если `None`, создаётся через `create_bot`) |
| `token` | `BOT_TOKEN` | — | Токен (если `bot` не передан) |
| `mock_url` | `TELEMELYA_URL` | `""` | URL mock-сервера |
| `proxy` | `PROXY_URL` | `""` | HTTP/SOCKS прокси |
| `mode` | `BOT_RUN_MODE` | `"auto"` | Режим: `auto`, `polling`, `webhook` |
| `webhook_url` | `WEBHOOK_URL` | `""` | Публичный URL для webhook |
| `webhook_host` | `WEBHOOK_HOST` | `0.0.0.0` | Хост для webhook-сервера |
| `webhook_port` | `WEBHOOK_PORT` | `8081` | Порт для webhook-сервера |
| `webhook_path` | — | `/webhook` | Путь для webhook-эндпоинта |

**Автоматическое определение режима** (при `BOT_RUN_MODE=auto`):

| `TELEMELYA_URL` | `WEBHOOK_URL` | Режим | Сценарий |
|:-:|:-:|---|---|
| ✅ | — | webhook → mock | Тесты (Telemelya) |
| — | ✅ | webhook → Telegram | Продакшн (сервер) |
| — | — | polling ← Telegram | Локальная отладка |

Можно переопределить через `BOT_RUN_MODE=polling` или `BOT_RUN_MODE=webhook`.

```python
runner = TemelyaRunner(dp)
runner.run()          # Блокирующий запуск
await runner.start()  # Асинхронный запуск
```

Свойства:
- `runner.is_test_mode` — `True` если работает через mock
- `runner.effective_mode` — текущий режим (`RunMode.POLLING` / `RunMode.WEBHOOK`)

---

### Переменные окружения адаптера

| Переменная | Обязательная | Описание |
|-----------|-------------|----------|
| `BOT_TOKEN` | Да (продакшн) | Токен бота от @BotFather |
| `TELEMELYA_URL` | Нет | URL Telemelya. Если задан — тестовый режим |
| `PROXY_URL` | Нет | HTTP/SOCKS5 прокси (продакшн) |
| `WEBHOOK_URL` | Нет | Публичный URL для webhook (продакшн) |
| `BOT_RUN_MODE` | Нет | `auto` (по умолчанию), `polling`, `webhook` |
| `WEBHOOK_HOST` | Нет | Хост для webhook-сервера (`0.0.0.0`) |
| `WEBHOOK_PORT` | Нет | Порт для webhook-сервера (`8081`) |
| `WEBHOOK_EXTERNAL_HOST` | Нет | Хост для webhook URL в тесте (`host.docker.internal`) |

---

## Примеры типовых архитектур

### Простой бот (один файл)

```python
# bot.py
from aiogram import Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from telemelya.aiogram import TemelyaRunner

dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Добро пожаловать!", reply_markup=...)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Список команд: /start, /help, /settings")

@dp.message(F.photo)
async def on_photo(message: types.Message):
    await message.answer("Фото получено!")

@dp.message()
async def on_text(message: types.Message):
    # Бизнес-логика обработки текста
    result = process_text(message.text)
    await message.answer(result)

if __name__ == "__main__":
    TemelyaRunner(dp).run()
```

### Бот с роутерами (многофайловый)

```
my_bot/
├── main.py              # Точка входа
├── handlers/
│   ├── __init__.py
│   ├── start.py         # /start, /help
│   ├── photos.py        # Обработка фото
│   └── payments.py      # Платежи
├── services/
│   └── ai_service.py    # Бизнес-логика
└── docker-compose.test.yml
```

```python
# my_bot/handlers/start.py
from aiogram import Router, types
from aiogram.filters import CommandStart

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет!")
```

```python
# my_bot/main.py
from aiogram import Dispatcher
from telemelya.aiogram import TemelyaRunner
from handlers.start import router as start_router
from handlers.photos import router as photo_router

dp = Dispatcher()
dp.include_router(start_router)
dp.include_router(photo_router)

if __name__ == "__main__":
    TemelyaRunner(dp).run()
```

### Docker Compose для тестирования

```yaml
# docker-compose.test.yml
services:
  mock-server:
    image: ghcr.io/fedottech/telemelya:latest
    ports: ["8080:8080"]
    depends_on: [redis, minio]
    environment:
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      AUTH_KEYS: test-key-123

  my-bot:
    build: .
    depends_on: [mock-server]
    environment:
      BOT_TOKEN: "123456789:ABCDefGhIjKlMnOpQrStUvWxYz"
      TELEMELYA_URL: "http://mock-server:8080"
      WEBHOOK_HOST: "0.0.0.0"
      WEBHOOK_PORT: "8081"

  redis:
    image: redis:7-alpine

  minio:
    image: minio/minio
    command: server /data
```

### CI/CD (GitHub Actions)

```yaml
# .github/workflows/bot-tests.yml
name: Bot Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports: [6379:6379]
      minio:
        image: minio/minio
        ports: [9000:9000]
        env:
          MINIO_ROOT_USER: minioadmin
          MINIO_ROOT_PASSWORD: minioadmin

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Установка зависимостей
        run: pip install telemelya[client,aiogram] behave

      - name: Запуск mock-сервера
        run: |
          pip install telemelya
          telemelya-server &
          sleep 3
        env:
          REDIS_URL: redis://localhost:6379/0
          AUTH_KEYS: test-key

      - name: Запуск тестируемого бота
        run: |
          python my_bot/main.py &
          sleep 2
        env:
          TELEMELYA_URL: http://localhost:8080
          BOT_TOKEN: "123456789:FakeTestToken"

      - name: Запуск BDD-тестов
        run: behave tests/features/
        env:
          MOCK_SERVER_URL: http://localhost:8080
          API_KEY: test-key
```

---

## Рекомендации

1. **Не храните токен в коде** — всегда через `BOT_TOKEN` env-переменную
2. **Один entry-point** — используйте `TemelyaRunner(dp).run()` как единственную точку запуска
3. **Фейковый токен для тестов** — формат `123456789:ABCDefGhIjKlMnOpQrStUvWxYz` (aiogram валидирует формат)
4. **Изоляция тестов** — каждый тест-сценарий получает уникальный `session_id`, тесты не мешают друг другу
5. **Прокси только для продакшна** — `PROXY_URL` игнорируется в тестовом режиме
6. **Windows + Docker Desktop** — в тестовом клиенте используйте `127.0.0.1` вместо `localhost` (проблема с IPv6)
7. **Системный прокси Windows** — если в системе настроен HTTP-прокси (корпоративный VPN, антивирус и т.д.), Python-библиотека httpx будет направлять запросы к `localhost` через прокси, что вызовет ошибку `ReadError: [WinError 10054]`. Решение — задайте `NO_PROXY=localhost,127.0.0.1` перед запуском тестов, либо используйте `127.0.0.1` вместо `localhost`:
   ```bash
   NO_PROXY=localhost,127.0.0.1 make test
   ```

---

## Установка

### Только mock-сервер

```bash
pip install telemelya
```

### Тестовый клиент + BDD

```bash
pip install telemelya[client]
```

### Адаптер для aiogram

```bash
pip install telemelya[aiogram]
```

### Всё для разработки

```bash
pip install telemelya[dev]
```

---

## Структура проекта

```
Telemelya/
├── telemelya/
│   ├── server/
│   │   ├── app.py           # FastAPI-приложение, точка входа сервера
│   │   ├── config.py        # Конфигурация (Pydantic Settings)
│   │   ├── state.py         # Redis: webhook-реестр, логи ответов, сессии
│   │   ├── media.py         # MinIO: загрузка/скачивание медиафайлов
│   │   ├── bot_api.py       # Эмуляция Bot API (/bot{token}/...)
│   │   ├── control_api.py   # Control API (/api/v1/test/...)
│   │   ├── webhook.py       # Доставка обновлений на webhook бота
│   │   └── auth.py          # Аутентификация по API-ключу
│   ├── client/
│   │   ├── client.py        # TelegramTestClient (httpx)
│   │   └── collector.py     # ResponseCollector (assertions)
│   ├── aiogram.py           # Адаптер TemelyaRunner для aiogram
│   └── models.py            # Pydantic-модели Telegram API
├── tests/
│   ├── features/            # Gherkin-сценарии (.feature)
│   ├── steps/               # Шаги behave (Python)
│   ├── environment.py       # Хуки behave (setup/teardown)
│   └── test_integration.py  # Интеграционные тесты
├── examples/
│   └── echo_bot/            # Пример echo-бота
├── docker-compose.local.yml # Docker Compose для разработки
├── docker-compose.yml       # Docker Compose для продакшна
├── Dockerfile               # Multi-stage Dockerfile
├── Makefile                 # Удобные команды
└── pyproject.toml           # Конфигурация Python-пакета
```

---

## Лицензия

MIT
