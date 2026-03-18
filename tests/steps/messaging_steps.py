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
