## План: Подключение Telemelya к проекту бота

**TL;DR**: Telemelya — mock-сервер Telegram Bot API для BDD-тестирования aiogram-ботов. Для подключения нужно: (1) заменить стандартный запуск aiogram на `TemelyaRunner`, (2) развернуть Docker-инфраструктуру Telemelya, (3) написать тесты через `TelegramTestClient`. Переключение тест/прод — только через переменные окружения, код бота идентичен.

---

### Фаза 1: Настройка бота с Telemelya-адаптером

**Шаг 1. Установить зависимость** 
- Добавить `telemelya` как git-зависимость: `pip install git+https://github.com/FedotTech/Telemelya.git`
- Это даёт и `telemelya.aiogram` (для бота), и `telemelya.client` (для тестов)

**Шаг 2. Заменить точку входа бота**
- Вместо `dp.run_polling()` / `dp.start_webhook()` использовать `TemelyaRunner` из `telemelya/aiogram.py`
- Образец — `examples/echo_bot/bot.py`:
  - Создать `Dispatcher`, зарегистрировать хэндлеры
  - `runner = TemelyaRunner(dp)` → `runner.run()`
- `TemelyaRunner` автоматически выбирает режим:
  - `TELEMELYA_URL` задан → **webhook к mock-серверу** (тестирование)
  - `WEBHOOK_URL` задан → **webhook к реальному Telegram** (продакшен)
  - Ничего → **polling** (локальная разработка)

**Шаг 3. Настроить переменные окружения**

| Режим | Переменные |
|-------|-----------|
| Разработка (polling) | `BOT_TOKEN=<реальный>` |
| Тестирование (mock) | `BOT_TOKEN=123456:FAKE`, `TELEMELYA_URL=http://localhost:8080`, `WEBHOOK_PORT=8081` |
| Продакшен (webhook) | `BOT_TOKEN=<реальный>`, `WEBHOOK_URL=https://bot.example.com` |

**Шаг 4. Структура проекта**
```
my_bot/
├── bot.py                  # Точка входа с TemelyaRunner
├── handlers/               # Хэндлеры aiogram (без изменений)
├── requirements.txt        # aiogram + telemelya
├── Dockerfile
├── docker-compose.yml      # Бот + Telemelya-стек
└── tests/
    ├── environment.py      # Behave setup
    ├── features/*.feature  # BDD-сценарии
    └── steps/*.py          # Step-определения
```

---

### Фаза 2: Docker-инфраструктура (*параллельно с Фазой 1*)

**Шаг 5. Создать docker-compose** на основе `docker-compose.local.yml`
- 4 сервиса: `mock-server` (Telemelya, порт 8080), `redis`, `minio`, `my-bot` (порт 8081)
- Для бота в Docker: `WEBHOOK_EXTERNAL_HOST=my-bot` (чтобы mock-сервер мог достучаться по имени контейнера)


### Дополнительные соображения
1. **Минимальность изменений в боте**: замена на `TemelyaRunner` — это 3-5 строк. Все хэндлеры, фильтры, middleware остаются без изменений
2. **Windows**: использовать `127.0.0.1` вместо `localhost`, `NO_PROXY=localhost,127.0.0.1` при корпоративном прокси
3. **Если бот уже существует**: достаточно заменить только точку входа (`main`/`__main__`), остальной код не трогается
