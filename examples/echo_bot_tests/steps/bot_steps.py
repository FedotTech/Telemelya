"""Шаги behave для тестирования echo-бота."""

import time

from behave import given, when, then


@given('chat_id "{chat_id}"')
def step_set_chat_id(context, chat_id):
    context.chat_id = int(chat_id)


@when('пользователь отправляет команду "{command}"')
def step_send_command(context, command):
    context.client.send_command(chat_id=context.chat_id, command=command)
    time.sleep(1)


@when('пользователь отправляет сообщение "{text}"')
def step_send_message(context, text):
    context.client.send_message(chat_id=context.chat_id, text=text)
    time.sleep(1)


@then('бот отвечает "{text}"')
def step_assert_text(context, text):
    context.collector.wait_for_response(timeout=5.0)
    context.collector.assert_text(text)


@then('ответ содержит "{substring}"')
def step_assert_contains(context, substring):
    context.collector.wait_for_response(timeout=5.0)
    context.collector.assert_contains(substring)
