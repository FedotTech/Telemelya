"""Behave hooks: подключение к Telemelya-серверу, изоляция сценариев."""

import os

from telemelya.client import TelegramTestClient, ResponseCollector


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
