"""Шаги behave для тестирования echo-бота."""

import os
import tempfile
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


# --- Интерактивные сценарии (issue #3) ---


def _wait_for(context, predicate, timeout=5.0):
    """Поллит ленту ответов, пока predicate(responses) не вернёт значение."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        responses = context.collector.get_all_responses()
        result = predicate(responses)
        if result:
            return result
        time.sleep(0.2)
    return predicate(context.collector.get_all_responses())


@when('пользователь нажимает кнопку "{button_text}"')
def step_tap_button(context, button_text):
    # Находим сообщение с нужной callback-кнопкой и шлём callback на его message_id.
    record = _wait_for(
        context,
        lambda rs: context.collector.find_response(
            method="sendMessage", has_button=button_text
        ),
    )
    assert record, f"Не найдено сообщение с кнопкой {button_text!r}"
    markup = record["reply_markup"]
    data = next(
        btn["callback_data"]
        for row in markup["inline_keyboard"]
        for btn in row
        if btn.get("text") == button_text
    )
    context.tapped_message_id = record["message_id"]
    context.client.send_callback_query(
        chat_id=context.chat_id, data=data, message_id=record["message_id"]
    )
    time.sleep(1)


@then('клавиатура сообщения меняется на "{button_text}"')
def step_keyboard_changed(context, button_text):
    record = _wait_for(
        context,
        lambda rs: next(
            (
                r
                for r in rs
                if r.get("method") == "editMessageReplyMarkup"
                and r.get("message_id") == context.tapped_message_id
            ),
            None,
        ),
    )
    assert record, "Правка клавиатуры не зафиксирована"
    texts = [
        btn.get("text")
        for row in record["reply_markup"]["inline_keyboard"]
        for btn in row
    ]
    assert button_text in texts, f"Ожидали кнопку {button_text!r}, получили {texts!r}"


@then('бот показывает алерт "{text}"')
def step_alert_shown(context, text):
    _wait_for(
        context,
        lambda rs: any(r.get("method") == "answerCallbackQuery" for r in rs),
    )
    context.collector.assert_callback_answered(text=text, show_alert=True)


@when('пользователь запускает inline через кнопку "{button_text}"')
def step_launch_inline(context, button_text):
    record = _wait_for(
        context,
        lambda rs: context.collector.find_response(
            method="sendMessage", has_button=button_text
        ),
    )
    assert record, f"Не найдено сообщение с кнопкой {button_text!r}"
    query = next(
        btn["switch_inline_query"]
        for row in record["reply_markup"]["inline_keyboard"]
        for btn in row
        if btn.get("text") == button_text
    )
    result = context.client.send_inline_query(query=query, chat_id=context.chat_id)
    context.inline_query_id = result["inline_query_id"]
    time.sleep(1)


@when("пользователь выбирает первый inline-результат")
def step_choose_inline(context):
    _wait_for(
        context,
        lambda rs: any(r.get("method") == "answerInlineQuery" for r in rs),
    )
    context.client.choose_inline_result(
        chat_id=context.chat_id,
        inline_query_id=context.inline_query_id,
        result_index=0,
    )
    time.sleep(1)


@then('бот публикует сообщение содержащее "{substring}"')
def step_inline_message_posted(context, substring):
    record = _wait_for(
        context,
        lambda rs: next(
            (r for r in rs if r.get("via_inline") and substring in (r.get("text") or "")),
            None,
        ),
    )
    assert record, f"Не найдено inline-сообщение с {substring!r}"


@when("пользователь отправляет фото размером {size:d} байт")
def step_send_photo_bytes(context, size):
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * (size - 8)
    fd, path = tempfile.mkstemp(suffix=".png")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        context.client.send_photo(context.chat_id, path)
    finally:
        os.unlink(path)
    time.sleep(1)
