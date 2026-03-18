# Руководство по тестированию Telegram-ботов с Telemelya

Это руководство поможет вам настроить тестовое окружение и писать BDD-тесты для Telegram-ботов. Руководство рассчитано на тестировщиков разного уровня — от начинающих до продвинутых.

---

## Содержание

1. [Как это работает (для начинающих)](#1-как-это-работает)
2. [Подготовка окружения](#2-подготовка-окружения)
3. [Первый тест за 5 минут](#3-первый-тест-за-5-минут)
4. [Написание BDD-тестов (Gherkin)](#4-написание-bdd-тестов)
5. [Справочник встроенных шагов](#5-справочник-встроенных-шагов)
6. [Примеры тестов](#6-примеры-тестов)
7. [Написание собственных шагов (продвинутый уровень)](#7-написание-собственных-шагов)
8. [Тестирование через Python API (без Gherkin)](#8-тестирование-через-python-api)
9. [Интеграция с Jira / Xray](#9-интеграция-с-jira--xray)
10. [Отладка проблем](#10-отладка-проблем)
11. [Лучшие практики](#11-лучшие-практики)

---

## 1. Как это работает

### Идея

Telemelya — это «поддельный» Telegram. Вместо того чтобы тестировать бота через настоящий Telegram (что медленно и неудобно), мы запускаем **mock-сервер**, который притворяется Telegram API.

```
┌─────────────┐     ┌───────────────────┐     ┌───────────┐
│  Ваш тест   │────▶│  Telemelya (mock)  │────▶│  Ваш бот  │
│  (behave)   │◀────│  "поддельный TG"   │◀────│ (aiogram)  │
└─────────────┘     └───────────────────┘     └───────────┘
```

**Что происходит:**

1. Вы пишете: *«Когда пользователь отправляет /start»*
2. Telemelya создаёт объект сообщения и передаёт его боту через webhook
3. Бот обрабатывает сообщение и отвечает через mock-сервер (вместо api.telegram.org)
4. Вы проверяете: *«Тогда бот отвечает "Добро пожаловать!"»*

**Преимущества:**
- Тесты работают **без интернета**
- Тесты выполняются **за секунды**, а не минуты
- Не нужен **реальный Telegram-бот** и аккаунт
- Тесты **повторяемы** — нет зависимости от сети и серверов Telegram

---

## 2. Подготовка окружения

### 2.1. Требования

- Python 3.11+
- Тестируемый бот (на aiogram)
- Docker и Docker Compose (если запускаете Telemelya локально)

### 2.2. Установка тестовых зависимостей

Пакет `telemelya` пока не опубликован на PyPI — зависимости устанавливаются из клонированного репозитория:

```bash
# Из корня репозитория Telemelya
pip install -r requirements-client.txt
```

Файл `requirements-client.txt` содержит: `httpx`, `behave`, `Pillow`.

### 2.3. Варианты окружения

Выберите вариант, подходящий под вашу ситуацию:

| Вариант | Telemelya | Бот | Docker на вашей машине | Для кого |
|---|---|---|---|---|
| [А. Всё локально](#вариант-а-всё-локально-с-нуля) | Поднимаете сами | В контейнере | Нужен | Первое знакомство, локальная разработка |
| [Б. Готовый стенд](#вариант-б-сервер-telemelya-и-бот-уже-развёрнуты) | Уже на сервере | Уже на сервере | Не нужен | QA-команда, тестирование на staging |
| [В. Бот локально](#вариант-в-telemelya-в-docker-бот-запускается-локально) | Поднимаете сами | Запускаете вручную | Нужен | Разработчик бота, отладка |
| [Г. Бот на сервере](#вариант-г-бот-на-удалённом-сервере-telemelya-рядом) | Уже на сервере | Уже на сервере | Не нужен | Удалённое тестирование |

---

#### Вариант А. Всё локально (с нуля)

> Telemelya и бот запускаются на вашей машине через Docker Compose.
> Самый простой способ начать — подходит для первого знакомства.

**Требования:** Docker, Docker Compose, Python 3.11+

**Шаг 1. Разверните окружение:**

```bash
# Клонируйте репозиторий Telemelya
git clone https://github.com/FedotTech/Telemelya.git
cd Telemelya

# Скопируйте файл с настройками
cp .env.example .env

# Установите тестовые зависимости
pip install -r requirements-client.txt

# Поднимите всё одной командой (mock-сервер + Redis + MinIO + echo-bot)
make local-up
#   или напрямую: docker compose -f docker-compose.local.yml up -d

# Проверьте, что контейнеры работают
docker compose -f docker-compose.local.yml ps
```

**Шаг 2. Параметры подключения** (значения по умолчанию, менять не нужно):

| Параметр | Env-переменная | Значение по умолчанию | Откуда |
|---|---|---|---|
| Адрес сервера | `MOCK_SERVER_URL` | `http://127.0.0.1:8080` | Порт mock-сервера из `docker-compose.local.yml` |
| API-ключ | `API_KEY` | `test-api-key-12345` | Переменная `AUTH_KEYS` в `.env` |
| Токен бота | `BOT_TOKEN` | `123456789:ABCDefGhIjKlMnOpQrStUvWxYz` | Контейнер `echo-bot` в `docker-compose.local.yml` |

> **Важно (Windows):** Используйте `127.0.0.1` вместо `localhost`. На Windows с Docker Desktop `localhost` может резолвиться в IPv6-адрес, что вызывает ошибки подключения.
>
> **Важно (Windows + системный прокси):** Если в системе настроен HTTP-прокси (корпоративный VPN, антивирус), httpx будет направлять запросы к localhost через прокси. Задайте `NO_PROXY=localhost,127.0.0.1` перед запуском тестов. Подробнее — в [разделе «Отладка проблем»](#10-отладка-проблем).

**Шаг 3. Проверьте, что сервер отвечает:**

```bash
curl http://127.0.0.1:8080/
# → {"service": "Telemelya", "version": "0.1.0", ...}

curl -H "Authorization: Bearer test-api-key-12345" http://127.0.0.1:8080/api/v1/test/health
# → {"ok": true, "redis": "ok", "minio": "ok"}
```

**Шаг 4. Запустите тесты:**

```bash
make test
#   или: python -m behave tests/features/
```

**Остановка:**

```bash
make local-down
#   или: docker compose -f docker-compose.local.yml down -v
```

---

#### Вариант Б. Сервер Telemelya и бот уже развёрнуты

> Telemelya и бот уже работают на удалённом сервере (тестовый стенд, staging).
> Вам нужен только тестовый клиент на вашей машине. Docker не нужен.

**Требования:** Python 3.11+

**Шаг 1. Клонируйте репозиторий и установите зависимости:**

```bash
git clone https://github.com/FedotTech/Telemelya.git
cd Telemelya
pip install -r requirements-client.txt
```

**Шаг 2. Получите параметры подключения** у DevOps / тимлида:

| Параметр | Env-переменная | Пример значения | Откуда |
|---|---|---|---|
| Адрес сервера | `MOCK_SERVER_URL` | `https://telemelya.staging.example.com` | URL, по которому доступна Telemelya |
| API-ключ | `API_KEY` | `staging-api-key-xxx` | Ключ из `AUTH_KEYS` на сервере |
| Токен бота | `BOT_TOKEN` | `123456789:ABCDefGhIjKl...` | Токен, с которым запущен бот на сервере |

**Шаг 3. Задайте переменные окружения:**

```bash
export MOCK_SERVER_URL=https://telemelya.staging.example.com
export API_KEY=ваш-api-ключ
export BOT_TOKEN=123456789:токен-бота
```

**Шаг 4. Проверьте доступность сервера:**

```bash
curl -H "Authorization: Bearer $API_KEY" $MOCK_SERVER_URL/api/v1/test/health
# → {"ok": true, "redis": "ok", "minio": "ok"}
```

**Шаг 5. Запустите тесты:**

```bash
python -m behave tests/features/
```

---

#### Вариант В. Telemelya в Docker, бот запускается локально

> Бот пока в разработке — вы запускаете его через `python bot.py` на своей машине,
> а Telemelya работает в Docker рядом. Подходит для отладки нового функционала бота.

**Требования:** Docker, Docker Compose, Python 3.11+

**Шаг 1. Поднимите инфраструктуру (без бота):**

```bash
git clone https://github.com/FedotTech/Telemelya.git
cd Telemelya
cp .env.example .env
pip install -r requirements-client.txt

# Запускаем только mock-сервер + Redis + MinIO (без echo-bot)
docker compose -f docker-compose.local.yml up -d mock-server redis minio
```

**Шаг 2. Запустите вашего бота**, указав ему mock-сервер вместо api.telegram.org:

```bash
TELEMELYA_URL=http://127.0.0.1:8080 \
BOT_TOKEN=123456789:ABCDefGhIjKlMnOpQrStUvWxYz \
python your_bot.py
```

> `host.docker.internal` — специальный адрес, по которому Docker-контейнер (mock-сервер) может обратиться к хост-машине. Так mock-сервер доставит webhook-обновления вашему боту, который работает вне Docker.

**Шаг 3. Параметры для тестов** (значения по умолчанию, менять не нужно):

| Параметр | Env-переменная | Значение по умолчанию | Откуда |
|---|---|---|---|
| Адрес сервера | `MOCK_SERVER_URL` | `http://127.0.0.1:8080` | Порт mock-сервера из `docker-compose.local.yml` |
| API-ключ | `API_KEY` | `test-api-key-12345` | Переменная `AUTH_KEYS` в `.env` |
| Токен бота | `BOT_TOKEN` | `123456789:ABCDefGhIjKlMnOpQrStUvWxYz` | Тот же токен, с которым вы запустили бота |

**Шаг 4. Проверьте и запустите тесты:**

```bash
curl -H "Authorization: Bearer test-api-key-12345" http://127.0.0.1:8080/api/v1/test/health
# → {"ok": true, "redis": "ok", "minio": "ok"}

python -m behave tests/features/
```

**Остановка инфраструктуры:**

```bash
docker compose -f docker-compose.local.yml down -v
```

---

#### Вариант Г. Бот на удалённом сервере, Telemelya рядом

> Бот и Telemelya уже развёрнуты на VPS/staging.
> Вы подключаетесь со своей машины для запуска тестов. Docker не нужен.

**Требования:** Python 3.11+

**Шаг 1. Клонируйте репозиторий и установите зависимости:**

```bash
git clone https://github.com/FedotTech/Telemelya.git
cd Telemelya
pip install -r requirements-client.txt
```

**Шаг 2. Убедитесь, что бот настроен на mock-сервер** (спросите DevOps):
- Переменная `TELEMELYA_URL` бота указывает на Telemelya (например, `http://telemelya:8080` внутри Docker-сети сервера)
- Бот должен быть доступен для mock-сервера по сети (чтобы доставлять webhook-обновления)

**Шаг 3. Получите параметры подключения:**

| Параметр | Env-переменная | Пример значения | Откуда |
|---|---|---|---|
| Адрес сервера | `MOCK_SERVER_URL` | `https://telemelya.your-server.com` | Публичный URL Telemelya на сервере |
| API-ключ | `API_KEY` | `prod-api-key-xxx` | `AUTH_KEYS` на сервере |
| Токен бота | `BOT_TOKEN` | `123456789:ABCDefGhIjKl...` | Токен, с которым бот запущен на сервере |

**Шаг 4. Задайте переменные и запустите тесты:**

```bash
export MOCK_SERVER_URL=https://telemelya.your-server.com
export API_KEY=ваш-api-ключ
export BOT_TOKEN=токен-бота-на-сервере

curl -H "Authorization: Bearer $API_KEY" $MOCK_SERVER_URL/api/v1/test/health
# → {"ok": true, "redis": "ok", "minio": "ok"}

python -m behave tests/features/
```

---

## 3. Первый тест за 5 минут

В проекте Telemelya уже есть **готовые тесты**, которые можно запустить как есть и использовать как шаблон. В этом разделе мы разберём, как они устроены.

### Шаг 1. Используйте готовую структуру

В репозитории Telemelya папка `tests/` содержит полный рабочий пример:

```
tests/
├── environment.py                  ← Подключение к mock-серверу
├── features/
│   ├── start_command.feature       ← Сценарии: /start и эхо
│   └── photo_handling.feature      ← Сценарии: фото
├── steps/
│   ├── common_steps.py             ← Предусловия (chat_id и др.)
│   ├── messaging_steps.py          ← Отправка сообщений и проверка ответов
│   └── media_steps.py              ← Отправка и проверка фото
├── fixtures/
│   └── photos/                     ← Тестовые изображения
└── test_integration.py             ← Standalone-тесты (pytest)
```

Для вашего проекта — **скопируйте эту папку** и адаптируйте сценарии под вашего бота.

### Шаг 2. Разберём настройку клиента — `tests/environment.py`

Откройте файл `tests/environment.py` — он настраивает подключение к mock-серверу:

```python
"""Behave hooks: initialize client, reset per scenario."""

import os

from telemelya.client.client import TelegramTestClient
from telemelya.client.collector import ResponseCollector


def before_all(context):
    context.server_url = os.environ.get("MOCK_SERVER_URL", "http://127.0.0.1:8080")
    context.api_key = os.environ.get("API_KEY", "test-api-key-12345")
    context.bot_token = os.environ.get("BOT_TOKEN", "123456789:ABCDefGhIjKlMnOpQrStUvWxYz")


def before_scenario(context, scenario):
    context.client = TelegramTestClient(
        server_url=context.server_url,
        api_key=context.api_key,
        bot_token=context.bot_token,
    )
    context.collector = ResponseCollector(context.client)
    context.chat_id = 12345


def after_scenario(context, scenario):
    if hasattr(context, "client"):
        context.client.reset()
        context.client.close()
```

**Три параметра подключения** (см. [раздел 2.3](#23-варианты-окружения) — откуда берутся значения):

| Параметр | Env-переменная | По умолчанию | Назначение |
|---|---|---|---|
| Адрес сервера | `MOCK_SERVER_URL` | `http://127.0.0.1:8080` | URL mock-сервера Telemelya |
| API-ключ | `API_KEY` | `test-api-key-12345` | Авторизация в Control API (задаётся в `AUTH_KEYS` на сервере) |
| Токен бота | `BOT_TOKEN` | `123456789:ABCDef...` | Должен совпадать с токеном, с которым запущен бот |

Значения по умолчанию подходят для **Варианта А** (всё локально). Для других вариантов — задайте переменные окружения перед запуском тестов.

**Хуки фреймворка behave:**
- `before_all` — выполняется **один раз** перед всеми тестами; читает параметры подключения
- `before_scenario` — выполняется **перед каждым сценарием**; создаёт свежий клиент с уникальной сессией
- `after_scenario` — выполняется **после каждого сценария**; очищает данные сессии, чтобы тесты не влияли друг на друга

### Шаг 3. Разберём предусловия — `tests/steps/common_steps.py`

```python
"""Common step definitions."""

from behave import given


@given('chat_id "{chat_id}"')
def step_set_chat_id(context, chat_id):
    context.chat_id = int(chat_id)
```

**Зачем нужен `chat_id`?** В настоящем Telegram каждое сообщение автоматически привязано к чату. В тестировании мы **сами выбираем**, от имени какого чата (пользователя) отправлять сообщение. Это позволяет:
- Имитировать разных пользователей в одном тесте
- Проверять изоляцию — ответы одного пользователя не попадают к другому
- Тестировать групповые чаты (отрицательные chat_id)

По умолчанию `chat_id = 12345` (задан в `environment.py`). Этот шаг нужен только когда вы хотите **переопределить** его в конкретном сценарии.

### Шаг 4. Разберём шаги для сообщений — `tests/steps/messaging_steps.py`

```python
"""Messaging step definitions."""

import time
from behave import when, then


@when('пользователь отправляет сообщение "{text}"')
def step_send_message(context, text):
    context.client.send_message(context.chat_id, text)
    time.sleep(1)


@when('пользователь отправляет команду "{command}"')
def step_send_command(context, command):
    context.client.send_command(context.chat_id, command)
    time.sleep(1)


@then('бот отвечает "{text}"')
def step_bot_responds_with(context, text):
    context.collector.wait_for_response(timeout=5.0)
    context.collector.assert_text(text)


@then('ответ содержит "{substring}"')
def step_response_contains(context, substring):
    context.collector.wait_for_response(timeout=5.0)
    context.collector.assert_contains(substring)
```

**Принцип создания шагов:** каждый шаг — это Python-функция с декоратором, соответствующим ключевому слову Gherkin:
- `@given(...)` → `Допустим` — подготовка (задать предусловия)
- `@when(...)` → `Когда` — действие (отправить сообщение / команду)
- `@then(...)` → `Тогда` — проверка (что бот ответил правильно)

Текст в декораторе — это **шаблон**, который behave сопоставляет со строкой в `.feature`-файле. Параметры в `"{фигурных_скобках}"` извлекаются и передаются в функцию.

**Ключевые объекты в `context`:**

| Объект | Тип | Назначение |
|---|---|---|
| `context.client` | `TelegramTestClient` | Отправляет сообщения и команды в mock-сервер (имитирует действия пользователя) |
| `context.collector` | `ResponseCollector` | Получает ответы бота и проверяет их (assert-методы) |
| `context.chat_id` | `int` | Числовой ID чата, от имени которого идёт взаимодействие |

**Зачем `time.sleep(1)`?** После отправки сообщения нужно дать боту время на обработку. Цепочка: тест → mock-сервер → webhook бота → бот обрабатывает → бот отвечает через Bot API → mock-сервер сохраняет ответ. Пауза в 1 секунду гарантирует, что ответ будет готов к моменту проверки.

### Шаг 5. Разберём сценарий — `tests/features/start_command.feature`

```gherkin
# language: ru
Функционал: Обработка команды /start

  Сценарий: Пользователь запускает бота
    Допустим chat_id "12345"
    Когда пользователь отправляет команду "/start"
    Тогда бот отвечает "Добро пожаловать!"

  Сценарий: Пользователь отправляет текстовое сообщение
    Допустим chat_id "12345"
    Когда пользователь отправляет сообщение "Привет"
    Тогда ответ содержит "Привет"
```

**Как составляется сценарий:**
1. Каждая строка `.feature`-файла — это вызов одного из шагов, описанных в Python-файлах (шаги 3–4)
2. Behave находит подходящий шаг по **точному совпадению** текста с шаблоном в декораторе
3. Например, строка `Когда пользователь отправляет команду "/start"` → вызывает функцию `step_send_command` с параметром `command="/start"`

Вы можете комбинировать любые доступные шаги в произвольном порядке (полный список — [раздел 5](#5-справочник-встроенных-шагов)).

### Шаг 6. Запустите тесты

```bash
# Запуск готовых тестов из проекта Telemelya
python -m behave tests/features/
```

Ожидаемый результат:
```
Функционал: Обработка команды /start
  Сценарий: Пользователь запускает бота ...                    passed
  Сценарий: Пользователь отправляет текстовое сообщение ...    passed

Функционал: Обработка фото
  Сценарий: Пользователь отправляет фото ...                   passed
  Сценарий: Пользователь отправляет фото с подписью ...        passed

2 features passed, 0 failed
4 scenarios passed, 0 failed
```

Все тесты прошли — окружение работает. Теперь вы можете добавлять свои `.feature`-файлы и шаги.

---

## 4. Написание BDD-тестов

### 4.1. Что такое BDD и Gherkin

**BDD (Behavior-Driven Development)** — подход, при котором тесты описываются на **человеческом языке**. Формат описания — **Gherkin**.

Файлы Gherkin имеют расширение `.feature` и состоят из:

| Ключевое слово | Назначение | Пример |
|---|---|---|
| `Функционал:` | Заголовок — что тестируем | `Функционал: Обработка команд` |
| `Сценарий:` | Один тест-кейс | `Сценарий: Пользователь нажимает /start` |
| `Допустим` | Предусловие (Given) | `Допустим chat_id "12345"` |
| `Когда` | Действие (When) | `Когда пользователь отправляет "/start"` |
| `Тогда` | Проверка (Then) | `Тогда бот отвечает "Привет!"` |
| `И` / `Но` | Дополнительные шаги | `И ответ содержит "Добро"` |

> **Важно:** Первая строка файла должна быть `# language: ru` — это включает поддержку русского языка.

### 4.2. Структура feature-файла

```gherkin
# language: ru
Функционал: Название функционала
  Краткое описание того, что тестируем.
  Можно написать несколько строк.

  Предыстория:
    Допустим chat_id "12345"

  Сценарий: Название первого тест-кейса
    Когда пользователь отправляет команду "/start"
    Тогда бот отвечает "Добро пожаловать!"

  Сценарий: Название второго тест-кейса
    Когда пользователь отправляет сообщение "Привет"
    Тогда ответ содержит "Привет"
```

**Предыстория** — блок шагов, который выполняется **перед каждым сценарием** в файле. Удобно, чтобы не повторять одинаковые строки.

### 4.3. Связь с Jira / Xray

BDD-сценарии можно связать с тест-кейсами в Jira Xray. Подробности — в [разделе 9. Интеграция с Jira / Xray](#9-интеграция-с-jira--xray).

### 4.4. Структура папок для тестов

```
tests/
├── features/                # Сценарии (.feature)
│   ├── commands.feature     # Тесты команд (/start, /help)
│   ├── messages.feature     # Тесты текстовых сообщений
│   ├── media.feature        # Тесты фото/документов
│   └── edge_cases.feature   # Граничные случаи
├── steps/                   # Python-реализации шагов
│   ├── common_steps.py      # Общие шаги (chat_id и т.д.)
│   ├── messaging_steps.py   # Шаги для текста
│   └── media_steps.py       # Шаги для медиа
├── fixtures/                # Тестовые данные
│   └── photos/
│       └── test.jpg
└── environment.py           # Настройка окружения
```

### 4.5. Запуск тестов

```bash
# Все тесты
python -m behave tests/features/

# Один feature-файл
python -m behave tests/features/commands.feature

# Конкретный сценарий (по имени)
python -m behave tests/features/ --name "Бот приветствует"

# С подробным выводом
python -m behave tests/features/ -v

# Только сценарии с определённым тегом
python -m behave tests/features/ --tags=@smoke
```

---

## 5. Справочник встроенных шагов

### Предусловия (Допустим / Given)

| Шаг | Описание |
|---|---|
| `Допустим chat_id "{id}"` | Переопределить ID чата для сценария. В Telegram каждый чат имеет числовой ID — именно он идентифицирует пользователя/группу. По умолчанию `12345` (задан в `environment.py`). Используйте этот шаг для тестирования нескольких пользователей или изоляции сессий |

### Действия (Когда / When)

| Шаг | Описание |
|---|---|
| `Когда пользователь отправляет команду "{command}"` | Отправить команду (например, `/start`) |
| `Когда пользователь отправляет сообщение "{text}"` | Отправить текстовое сообщение |
| `Когда пользователь отправляет фото "{path}"` | Отправить фото |
| `Когда пользователь отправляет фото "{path}" с подписью "{caption}"` | Отправить фото с подписью |

### Проверки (Тогда / Then)

| Шаг | Описание |
|---|---|
| `Тогда бот отвечает "{text}"` | Проверить точное совпадение текста ответа |
| `Тогда ответ содержит "{substring}"` | Проверить, что ответ содержит подстроку |
| `Тогда бот отправляет фото` | Проверить, что бот ответил фотографией |
| `Тогда бот отправляет фото с подписью "{caption}"` | Проверить фото с конкретной подписью |

---

## 6. Примеры тестов

### Пример 1. Команды бота (начальный уровень)

```gherkin
# language: ru
Функционал: Основные команды

  Предыстория:
    Допустим chat_id "12345"

  Сценарий: Команда /start
    Когда пользователь отправляет команду "/start"
    Тогда бот отвечает "Добро пожаловать!"

  Сценарий: Команда /help
    Когда пользователь отправляет команду "/help"
    Тогда ответ содержит "Список команд"
    И ответ содержит "/start"
    И ответ содержит "/help"

  Сценарий: Неизвестная команда
    Когда пользователь отправляет команду "/xyz"
    Тогда бот отвечает "Неизвестная команда. Попробуйте /help"
```

### Пример 2. Эхо-бот (начальный уровень)

```gherkin
# language: ru
Функционал: Эхо-ответы

  Предыстория:
    Допустим chat_id "12345"

  Сценарий: Бот повторяет текст на русском
    Когда пользователь отправляет сообщение "Привет, бот!"
    Тогда бот отвечает "Привет, бот!"

  Сценарий: Бот повторяет текст на английском
    Когда пользователь отправляет сообщение "Hello world"
    Тогда бот отвечает "Hello world"

  Сценарий: Бот повторяет эмодзи
    Когда пользователь отправляет сообщение "🎉🎊"
    Тогда бот отвечает "🎉🎊"
```

### Пример 3. Обработка фотографий (средний уровень)

```gherkin
# language: ru
Функционал: Обработка фотографий

  Предыстория:
    Допустим chat_id "12345"

  Сценарий: Пользователь отправляет простое фото
    Когда пользователь отправляет фото "fixtures/photos/test.jpg"
    Тогда бот отправляет фото

  Сценарий: Пользователь отправляет фото с подписью
    Когда пользователь отправляет фото "fixtures/photos/test.jpg" с подписью "Моё фото"
    Тогда бот отправляет фото с подписью "Фото получено"
```

### Пример 4. Диалог из нескольких шагов (средний уровень)

```gherkin
# language: ru
Функционал: Многошаговый диалог

  Предыстория:
    Допустим chat_id "12345"

  Сценарий: Пользователь проходит регистрацию
    Когда пользователь отправляет команду "/register"
    Тогда бот отвечает "Как вас зовут?"
    Когда пользователь отправляет сообщение "Иван"
    Тогда бот отвечает "Приятно познакомиться, Иван! Укажите ваш email:"
    Когда пользователь отправляет сообщение "ivan@example.com"
    Тогда ответ содержит "Регистрация завершена"
```

### Пример 5. Разные пользователи (средний уровень)

```gherkin
# language: ru
Функционал: Изоляция пользователей

  Сценарий: Два пользователя работают независимо
    Допустим chat_id "11111"
    Когда пользователь отправляет команду "/start"
    Тогда бот отвечает "Добро пожаловать!"

    Допустим chat_id "22222"
    Когда пользователь отправляет сообщение "Тест"
    Тогда бот отвечает "Тест"
```

### Пример 6. Теги и фильтрация (продвинутый уровень)

```gherkin
# language: ru
Функционал: Команды с тегами

  @smoke
  Сценарий: Smoke-тест: бот живой
    Допустим chat_id "12345"
    Когда пользователь отправляет команду "/start"
    Тогда бот отвечает "Добро пожаловать!"

  @regression
  Сценарий: Длинное сообщение
    Допустим chat_id "12345"
    Когда пользователь отправляет сообщение "А"
    Тогда бот отвечает "А"

  @regression @slow
  Сценарий: Множественные сообщения подряд
    Допустим chat_id "12345"
    Когда пользователь отправляет сообщение "Первое"
    Тогда бот отвечает "Первое"
    Когда пользователь отправляет сообщение "Второе"
    Тогда бот отвечает "Второе"
    Когда пользователь отправляет сообщение "Третье"
    Тогда бот отвечает "Третье"
```

Запуск только smoke-тестов:
```bash
python -m behave tests/features/ --tags=@smoke
```

Запуск regression, кроме медленных:
```bash
python -m behave tests/features/ --tags=@regression --tags=~@slow
```

### Пример 7. Шаблоны сценариев (продвинутый уровень)

Когда нужно проверить одну и ту же логику с разными данными — используйте **Структуру сценария**:

```gherkin
# language: ru
Функционал: Обработка различных команд

  Структура сценария: Бот отвечает на команды
    Допустим chat_id "12345"
    Когда пользователь отправляет команду "<команда>"
    Тогда ответ содержит "<ожидаемый_фрагмент>"

    Примеры:
      | команда    | ожидаемый_фрагмент      |
      | /start     | Добро пожаловать        |
      | /help      | Список команд           |
      | /settings  | Настройки               |
      | /about     | Версия                  |
```

Behave автоматически создаст **4 сценария** — по одному для каждой строки таблицы `Примеры`.

---

## 7. Написание собственных шагов

> Этот раздел для тех, кому нужно добавить новые проверки или действия.

### 7.1. Как устроены шаги

Каждый шаг — это Python-функция с декоратором `@given`, `@when` или `@then`:

```python
from behave import when, then
import time


@when('пользователь отправляет команду "{command}"')
def step_send_command(context, command):
    # context.client — тестовый клиент (создаётся в environment.py)
    # context.chat_id — ID чата (задаётся шагом Допустим)
    context.client.send_command(context.chat_id, command)
    time.sleep(1)  # ← даём боту время на обработку


@then('бот отвечает "{text}"')
def step_bot_responds_with(context, text):
    # collector ждёт ответ от бота и проверяет его
    context.collector.wait_for_response(timeout=5.0)
    context.collector.assert_text(text)
```

**Ключевые объекты:**
- `context.client` — `TelegramTestClient` для отправки сообщений
- `context.collector` — `ResponseCollector` для получения и проверки ответов
- `context.chat_id` — текущий ID чата (число)

### 7.2. Пример: шаг для проверки inline-кнопок

```python
# tests/steps/keyboard_steps.py

from behave import then


@then('бот отправляет кнопки')
def step_bot_sends_buttons(context):
    context.collector.wait_for_response(timeout=5.0)
    markup = context.collector.last.get("reply_markup")
    assert markup is not None, "Ответ не содержит клавиатуру"


@then('в ответе есть кнопка "{button_text}"')
def step_response_has_button(context, button_text):
    markup = context.collector.last.get("reply_markup", {})
    buttons = [
        btn.get("text", "")
        for row in markup.get("inline_keyboard", [])
        for btn in row
    ]
    assert button_text in buttons, (
        f"Кнопка '{button_text}' не найдена. Доступные: {buttons}"
    )
```

Использование в feature-файле:
```gherkin
  Сценарий: Бот показывает меню
    Когда пользователь отправляет команду "/menu"
    Тогда бот отправляет кнопки
    И в ответе есть кнопка "📋 Каталог"
    И в ответе есть кнопка "⚙️ Настройки"
```

### 7.3. Пример: шаг для callback-кнопок

```python
# tests/steps/callback_steps.py

import time
from behave import when


@when('пользователь нажимает кнопку с данными "{callback_data}" на сообщении "{message_id}"')
def step_press_button(context, callback_data, message_id):
    context.client.send_callback_query(
        chat_id=context.chat_id,
        data=callback_data,
        message_id=int(message_id),
    )
    time.sleep(1)
```

Использование:
```gherkin
  Сценарий: Пользователь нажимает кнопку в меню
    Когда пользователь отправляет команду "/menu"
    Тогда бот отвечает "Выберите раздел:"
    Когда пользователь нажимает кнопку с данными "catalog" на сообщении "1"
    Тогда бот отвечает "Каталог товаров:"
```

### 7.4. Пример: шаг для проверки нескольких ответов

```python
# tests/steps/multi_response_steps.py

from behave import then


@then('бот отвечает "{count}" сообщениями')
def step_bot_sends_multiple(context, count):
    expected = int(count)
    responses = context.client.get_responses()
    assert len(responses) >= expected, (
        f"Ожидалось {expected} ответов, получено {len(responses)}"
    )
```

### 7.5. Пример: шаг с таблицей данных

```python
# tests/steps/table_steps.py

from behave import then


@then('бот отвечает сообщениями')
def step_bot_responds_with_messages(context):
    """Проверяет несколько ответов по таблице из feature-файла."""
    responses = context.client.get_responses()
    for row in context.table:
        expected_text = row["текст"]
        found = any(r.get("text") == expected_text for r in responses)
        assert found, f"Ответ '{expected_text}' не найден среди {[r.get('text') for r in responses]}"
```

Использование:
```gherkin
  Сценарий: Бот отвечает несколькими сообщениями
    Когда пользователь отправляет команду "/info"
    Тогда бот отвечает сообщениями
      | текст                    |
      | Информация о боте        |
      | Версия: 1.0              |
```

---

## 8. Тестирование через Python API

> Для тестировщиков, предпочитающих pytest или standalone-скрипты вместо Gherkin.

### 8.1. Простой тест

```python
import time
from telemelya.client import TelegramTestClient, ResponseCollector

# Подключение
client = TelegramTestClient(
    server_url="http://127.0.0.1:8080",
    api_key="test-api-key-12345",
    bot_token="123456789:ABCDefGhIjKlMnOpQrStUvWxYz",
)
collector = ResponseCollector(client)

# Тест
client.send_command(chat_id=12345, command="/start")
time.sleep(1)
collector.wait_for_response(timeout=5.0)
collector.assert_text("Добро пожаловать!")

# Очистка
client.reset()
client.close()

print("Тест пройден!")
```

### 8.2. С использованием pytest

```python
# test_bot.py
import time
import pytest
from telemelya.client import TelegramTestClient, ResponseCollector

SERVER_URL = "http://127.0.0.1:8080"
API_KEY = "test-api-key-12345"
BOT_TOKEN = "123456789:ABCDefGhIjKlMnOpQrStUvWxYz"


@pytest.fixture
def bot_client():
    """Фикстура: создать клиент, после теста — очистить."""
    client = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
    yield client
    client.reset()
    client.close()


@pytest.fixture
def collector(bot_client):
    return ResponseCollector(bot_client)


class TestStartCommand:
    def test_start_returns_welcome(self, bot_client, collector):
        bot_client.send_command(chat_id=12345, command="/start")
        time.sleep(1)
        collector.wait_for_response(timeout=5.0)
        collector.assert_text("Добро пожаловать!")

    def test_start_contains_greeting(self, bot_client, collector):
        bot_client.send_command(chat_id=12345, command="/start")
        time.sleep(1)
        collector.wait_for_response(timeout=5.0)
        collector.assert_contains("Добро")


class TestEcho:
    def test_echo_russian(self, bot_client, collector):
        bot_client.send_message(chat_id=12345, text="Привет!")
        time.sleep(1)
        collector.wait_for_response(timeout=5.0)
        collector.assert_text("Привет!")

    def test_echo_english(self, bot_client, collector):
        bot_client.send_message(chat_id=12345, text="Hello")
        time.sleep(1)
        collector.wait_for_response(timeout=5.0)
        collector.assert_text("Hello")


class TestSessionIsolation:
    def test_different_chats_are_isolated(self):
        client1 = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
        client2 = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
        try:
            client1.send_message(chat_id=11111, text="msg1")
            time.sleep(1)
            client2.send_message(chat_id=22222, text="msg2")
            time.sleep(1)

            resp1 = client1.get_responses()
            resp2 = client2.get_responses()

            assert resp1[0]["text"] == "msg1"
            assert resp2[0]["text"] == "msg2"
        finally:
            client1.reset()
            client2.reset()
            client1.close()
            client2.close()
```

Запуск:
```bash
pytest test_bot.py -v
```

### 8.3. Справочник тестового клиента

| Метод | Параметры | Описание |
|---|---|---|
| `send_message(chat_id, text)` | `chat_id: int`, `text: str` | Отправить текст |
| `send_command(chat_id, command)` | `chat_id: int`, `command: str` | Отправить команду (`/start`) |
| `send_photo(chat_id, path, caption=)` | `chat_id: int`, `path: str` | Отправить фото |
| `send_callback_query(chat_id, data, message_id)` | `chat_id: int`, `data: str`, `message_id: int` | Нажать inline-кнопку |
| `get_responses()` | — | Все ответы бота (список dict) |
| `wait_for_response(timeout=5.0)` | `timeout: float` | Ждать один ответ |
| `get_media(file_id)` | `file_id: str` | Скачать медиафайл (bytes) |
| `reset()` | — | Очистить сессию |
| `close()` | — | Закрыть соединение |

### 8.4. Справочник ResponseCollector

| Метод | Описание |
|---|---|
| `wait_for_response(timeout=5.0)` | Дождаться ответа из очереди |
| `assert_text(expected)` | Текст ответа == `expected` |
| `assert_contains(substring)` | Текст ответа содержит `substring` |
| `assert_photo(caption=None)` | Ответ — фото (опционально с подписью) |
| `assert_reply_markup(buttons)` | Ответ содержит inline-кнопки |
| `last` | Последний полученный ответ (dict) |
| `get_all_responses()` | Все ответы бота в сессии |
| `get_media(file_id)` | Скачать медиафайл |

### 8.5. Формат ответа бота

Ответ — это словарь с полями, зависящими от типа:

```python
# Текстовое сообщение (sendMessage)
{
    "method": "sendMessage",
    "chat_id": 12345,
    "text": "Привет!",
    "reply_markup": {...}   # если есть клавиатура
}

# Фото (sendPhoto)
{
    "method": "sendPhoto",
    "chat_id": 12345,
    "photo": "file_id_xxx",
    "caption": "Подпись к фото"
}
```

---

## 9. Интеграция с Jira / Xray

BDD-сценарии из `.feature`-файлов можно связать с тест-кейсами в **Jira Xray** — плагине для управления тестированием. Это позволяет:

- Видеть результаты автотестов прямо в Jira
- Связывать сценарии с пользовательскими историями и дефектами
- Генерировать отчёты по покрытию

### 9.1. Связь через теги

Добавьте тег с ID задачи Jira перед сценарием:

```gherkin
# language: ru
Функционал: Обработка команды /start

  @PROJ-123
  Сценарий: Бот приветствует нового пользователя
    Допустим chat_id "12345"
    Когда пользователь отправляет команду "/start"
    Тогда бот отвечает "Добро пожаловать!"

  @PROJ-124
  Сценарий: Бот повторяет текстовое сообщение
    Допустим chat_id "12345"
    Когда пользователь отправляет сообщение "Привет"
    Тогда ответ содержит "Привет"
```

Тег `@PROJ-123` привязывает сценарий к Xray Test с ключом `PROJ-123` в Jira.

### 9.2. Импорт .feature-файлов в Xray

Xray поддерживает **импорт Gherkin-файлов**:

1. В Jira → **Xray** → **Test Repository** → **Import Feature Files**
2. Загрузите ваши `.feature`-файлы
3. Xray автоматически создаст Test-задачи для каждого сценария

Или через REST API:
```bash
curl -H "Content-Type: multipart/form-data" \
     -u user:token \
     -F "file=@tests/features/start_command.feature" \
     "https://jira.example.com/rest/raven/1.0/import/feature?projectKey=PROJ"
```

### 9.3. Экспорт результатов в Xray

Используйте формат **Xray JSON** или **Cucumber JSON** для импорта результатов:

```bash
# Запуск тестов с выводом в формате JSON для Cucumber
python -m behave tests/features/ \
  -f json -o results/cucumber-report.json \
  -f pretty

# Импорт результатов в Xray через REST API
curl -H "Content-Type: application/json" \
     -u user:token \
     -d @results/cucumber-report.json \
     "https://jira.example.com/rest/raven/1.0/import/execution/cucumber"
```

### 9.4. Двусторонняя синхронизация

Xray позволяет работать в обе стороны:

| Направление | Описание |
|---|---|
| **Jira → код** | Xray экспортирует `.feature`-файлы из Test-задач. Тестировщик пишет сценарий в Jira, разработчик скачивает его в проект |
| **Код → Jira** | `.feature`-файлы импортируются в Xray. Тестировщик пишет сценарий в IDE, загружает в Jira |
| **Результаты → Jira** | JSON-отчёт behave загружается в Xray как Test Execution |

> **Совет:** Для CI/CD добавьте импорт результатов в pipeline (см. `.github/workflows/bot-tests.yml` как основу).

---

## 10. Отладка проблем

### Тест зависает / тайм-аут

**Симптом:** `TimeoutError: No bot response received within 5s`

**Причины и решения:**

| Причина | Решение |
|---|---|
| Бот не запущен | `docker compose -f docker-compose.local.yml ps` — проверьте, что контейнер echo-bot в состоянии `Up` |
| Бот упал при старте | `docker compose -f docker-compose.local.yml logs echo-bot` — проверьте логи |
| Неправильный `bot_token` | Токен в тесте должен совпадать с токеном бота в docker-compose |
| Webhook не зарегистрирован | Логи mock-server: `docker compose logs mock-server \| grep webhook` |
| Увеличьте тайм-аут | `collector.wait_for_response(timeout=10.0)` |

### Mock-сервер не отвечает

```bash
# Проверьте состояние контейнеров
docker compose -f docker-compose.local.yml ps

# Проверьте логи
docker compose -f docker-compose.local.yml logs mock-server

# Перезапустите
docker compose -f docker-compose.local.yml restart mock-server
```

### Ошибка подключения к серверу

**Симптом:** `ConnectionRefusedError` или `ConnectError`

| Причина | Решение |
|---|---|
| Неправильный адрес | Используйте `http://127.0.0.1:8080` (не `localhost`) |
| Порт занят | `netstat -an \| findstr 8080` (Windows) или `lsof -i :8080` (Linux/Mac) |
| Docker не запущен | Запустите Docker Desktop |

### Системный прокси Windows (ReadError / WinError 10054)

**Симптом:** `httpx.ReadError: [WinError 10054] Удалённый хост принудительно разорвал существующее подключение`

**Причина:** Windows имеет системные настройки прокси (Параметры → Сеть → Прокси-сервер). Они могут быть включены корпоративным VPN, антивирусом или вручную. Python-библиотека httpx по умолчанию подхватывает эти настройки (`trust_env=True`) и направляет даже запросы к `localhost` через прокси, который их отклоняет.

**Решения (любое из трёх):**

1. **Переменная `NO_PROXY`** — самый простой способ, исключает localhost из проксирования:
   ```bash
   # Linux / Git Bash / WSL
   NO_PROXY=localhost,127.0.0.1 make test

   # PowerShell
   $env:NO_PROXY="localhost,127.0.0.1"; make test

   # CMD
   set NO_PROXY=localhost,127.0.0.1 && make test
   ```

2. **Отключите системный прокси** в Windows:
   Параметры → Сеть и Интернет → Прокси-сервер → отключите «Использовать прокси-сервер».

3. **Используйте `127.0.0.1` вместо `localhost`** в переменной `MOCK_SERVER_URL` — некоторые прокси пропускают IP-адреса, но перехватывают DNS-имена.

> **Подсказка:** Быстро проверить, есть ли проблема с прокси:
> ```bash
> curl http://127.0.0.1:8080/
> # Если отвечает — сервер работает, проблема в прокси Python
> ```

### IPv6 на Windows (localhost → ::1)

**Симптом:** `ConnectionRefusedError: [Errno 111] Connect call failed ('::1', 8080)`

**Причина:** На Windows `localhost` может резолвиться в IPv6-адрес `::1`, а Docker Desktop слушает только на IPv4 `127.0.0.1`.

**Решение:** Везде используйте `127.0.0.1` вместо `localhost`:
```bash
MOCK_SERVER_URL=http://127.0.0.1:8080 make test
```

### Тесты влияют друг на друга

**Симптом:** Тест проходит по отдельности, но падает при запуске всех вместе.

**Решение:** Убедитесь, что `after_scenario` вызывает `client.reset()`. Также каждый `TelegramTestClient` получает уникальный `session_id` — не создавайте клиент один раз на все тесты.

### Шаг «не найден»

**Симптом:** `behave.runner.UndefinedStepError`

**Решение:** Проверьте, что:
1. Файл с шагами лежит в `tests/steps/`
2. Текст шага в `.feature` **точно** совпадает с шаблоном в Python-файле
3. Нет лишних пробелов или разной кодировки кавычек

---

## 11. Лучшие практики

### Для начинающих

1. **Один сценарий = один тест-кейс.** Не пытайтесь проверить всё в одном сценарии.

2. **Используйте `Предысторию`** для общих шагов:
   ```gherkin
   Предыстория:
     Допустим chat_id "12345"
   ```

3. **Называйте сценарии понятно.** «Бот приветствует нового пользователя» лучше, чем «Тест 1».

4. **Группируйте feature-файлы по функционалу:** `commands.feature`, `messages.feature`, `payments.feature`.

### Для среднего уровня

5. **Используйте теги** для категоризации:
   - `@smoke` — базовые проверки (запускать после каждого деплоя)
   - `@regression` — полный набор тестов
   - `@slow` — медленные тесты (исключать из быстрых прогонов)
   - `@wip` — незавершённые тесты
   - `@PROJ-NNN` — привязка к задаче в Jira (см. [раздел 9](#9-интеграция-с-jira--xray))

6. **Используйте `Структуру сценария`** когда проверяете одну логику с разными входными данными.

7. **Не хардкодьте адреса и ключи** — используйте переменные окружения (настроены в `environment.py`).

8. **Добавляйте `time.sleep(1)`** после отправки сообщения — боту нужно время на обработку (подробнее в [шаге 4 раздела 3](#шаг-4-разберём-шаги-для-сообщений--testsstepsmessaging_stepspy)).

### Для продвинутых

9. **Создавайте свои шаги** для бизнес-логики вашего бота. Чем выше уровень абстракции шагов, тем читабельнее тесты:
   ```gherkin
   # Плохо
   Когда пользователь отправляет сообщение "Заказ #123"
   Тогда ответ содержит "Статус: В обработке"

   # Хорошо (собственный шаг)
   Когда пользователь проверяет статус заказа "123"
   Тогда бот показывает статус "В обработке"
   ```

10. **Используйте `context`** для передачи данных между шагами:
    ```python
    @when('пользователь создаёт заказ')
    def step_create_order(context):
        # ... отправка команды ...
        context.order_id = extract_order_id(response)

    @then('заказ отображается в списке')
    def step_order_in_list(context):
        # ... используем context.order_id ...
    ```

11. **Параллельный запуск:** Каждый тест получает уникальную сессию — тесты можно запускать параллельно через `behave-parallel` или разбиением feature-файлов.

12. **Интеграция с Allure** для красивых отчётов:
    ```bash
    pip install allure-behave
    python -m behave tests/features/ -f allure_behave.formatter:AllureFormatter -o allure-results
    allure serve allure-results
    ```

---

## Приложение: шпаргалка

### Быстрые команды

```bash
# Поднять окружение
make local-up

# Запустить все BDD-тесты
make test

# Запустить smoke-тесты
python -m behave tests/features/ --tags=@smoke

# Запустить интеграционные тесты (Python)
python tests/test_integration.py

# Посмотреть логи бота
docker compose -f docker-compose.local.yml logs -f echo-bot

# Остановить окружение
make local-down
```

### Минимальный feature-файл

```gherkin
# language: ru
Функционал: <Название>

  Предыстория:
    Допустим chat_id "12345"

  Сценарий: <Что проверяем>
    Когда пользователь отправляет команду "/start"
    Тогда бот отвечает "Ожидаемый текст"
```

### Минимальный Python-тест

```python
from telemelya.client import TelegramTestClient, ResponseCollector
import time

client = TelegramTestClient("http://127.0.0.1:8080", "test-api-key-12345", "123456789:ABCDefGhIjKlMnOpQrStUvWxYz")
collector = ResponseCollector(client)

client.send_command(chat_id=12345, command="/start")
time.sleep(1)
collector.wait_for_response(timeout=5.0)
collector.assert_text("Добро пожаловать!")

client.reset()
client.close()
```
