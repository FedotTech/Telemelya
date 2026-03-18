FROM python:3.12-slim

WORKDIR /app

# Установка telemelya из исходников проекта
COPY pyproject.toml .
COPY telemelya/ telemelya/
RUN pip install --no-cache-dir ".[aiogram]"

# Копирование примера бота
COPY examples/echo_bot/bot.py .

CMD ["python", "bot.py"]
