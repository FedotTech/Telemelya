"""
Тесты echo-бота на pytest — без Gherkin, чистый Python.

Запуск:
    python test_echo_bot.py

Переменные окружения:
    MOCK_SERVER_URL  — адрес Telemelya (по умолчанию http://127.0.0.1:8080)
    API_KEY          — API-ключ (по умолчанию test-api-key-12345)
    BOT_TOKEN        — токен бота (по умолчанию 123456789:ABCDefGhIjKlMnOpQrStUvWxYz)
"""

import os
import time

from telemelya.client import TelegramTestClient, ResponseCollector


SERVER_URL = os.environ.get("MOCK_SERVER_URL", "http://127.0.0.1:8080")
API_KEY = os.environ.get("API_KEY", "test-api-key-12345")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "123456789:ABCDefGhIjKlMnOpQrStUvWxYz")


def create_client():
    return TelegramTestClient(
        server_url=SERVER_URL,
        api_key=API_KEY,
        bot_token=BOT_TOKEN,
    )


def test_start_command():
    """Команда /start возвращает приветствие."""
    client = create_client()
    collector = ResponseCollector(client)
    try:
        client.send_command(chat_id=12345, command="/start")
        time.sleep(1)
        collector.wait_for_response(timeout=5.0)
        collector.assert_text("Добро пожаловать!")
        print("✓ /start — OK")
    finally:
        client.reset()
        client.close()


def test_echo_message():
    """Бот повторяет текстовое сообщение."""
    client = create_client()
    collector = ResponseCollector(client)
    try:
        client.send_message(chat_id=12345, text="Привет, бот!")
        time.sleep(1)
        collector.wait_for_response(timeout=5.0)
        collector.assert_text("Привет, бот!")
        print("✓ Эхо — OK")
    finally:
        client.reset()
        client.close()


def test_session_isolation():
    """Два пользователя не видят ответы друг друга."""
    client1 = create_client()
    client2 = create_client()
    collector1 = ResponseCollector(client1)
    collector2 = ResponseCollector(client2)
    try:
        client1.send_message(chat_id=11111, text="Сообщение от первого")
        client2.send_message(chat_id=22222, text="Сообщение от второго")
        time.sleep(1)

        collector1.wait_for_response(timeout=5.0)
        collector1.assert_text("Сообщение от первого")

        collector2.wait_for_response(timeout=5.0)
        collector2.assert_text("Сообщение от второго")
        print("✓ Изоляция сессий — OK")
    finally:
        client1.reset()
        client1.close()
        client2.reset()
        client2.close()


if __name__ == "__main__":
    print(f"Сервер: {SERVER_URL}")
    print(f"Токен: {BOT_TOKEN[:10]}...")
    print()
    test_start_command()
    test_echo_message()
    test_session_isolation()
    print()
    print("Все тесты пройдены!")
