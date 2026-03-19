# Пример тестов для echo-бота

Готовый набор тестов, который QA-инженер может запустить **с локальной машины** к боту, развёрнутому на сервере (или локально в Docker).

## Структура

```
echo_bot_tests/
├── README.md              # Этот файл
├── requirements.txt       # Зависимости для тестов
├── .env.example           # Шаблон переменных окружения
├── test_echo_bot.py       # Тесты на pytest (без Gherkin)
├── environment.py         # Behave hooks
├── features/
│   └── echo_bot.feature   # BDD-сценарии на русском
└── steps/
    └── bot_steps.py       # Шаги behave
```

## Быстрый старт

### 1. Установите зависимости

```bash
pip install telemelya[client]
# или
pip install httpx behave Pillow
```

### 2. Настройте подключение

Скопируйте `.env.example` в `.env` и укажите адрес сервера:

```bash
cp .env.example .env
```

Отредактируйте `.env`:
- `MOCK_SERVER_URL` — адрес Telemelya-сервера (например, `https://mock.example.com` или `http://127.0.0.1:8080`)
- `API_KEY` — API-ключ для аутентификации
- `BOT_TOKEN` — токен бота, зарегистрированного на сервере

### 3. Запустите тесты

**BDD (Gherkin):**
```bash
behave features/
```

**Pytest:**
```bash
python test_echo_bot.py
```

## Варианты подключения

### Бот и Telemelya в Docker (локально)
```
MOCK_SERVER_URL=http://127.0.0.1:8080
```

### Бот и Telemelya на удалённом сервере
```
MOCK_SERVER_URL=https://mock.example.com
```

### Windows-специфика

Если запросы к localhost не проходят (ошибка `WinError 10054`):
```bash
set NO_PROXY=localhost,127.0.0.1
```
Или используйте `127.0.0.1` вместо `localhost`.
