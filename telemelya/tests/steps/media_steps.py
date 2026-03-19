"""Media step definitions."""

import time
from typing import Optional

from behave import when, then, use_step_matcher

use_step_matcher("re")


@when('пользователь отправляет фото "(?P<path>[^"]+)" с подписью "(?P<caption>[^"]+)"')
def step_send_photo_with_caption(context, path, caption):
    context.client.send_photo(context.chat_id, path, caption=caption)
    time.sleep(1)


@when('пользователь отправляет фото "(?P<path>[^"]+)"')
def step_send_photo(context, path):
    context.client.send_photo(context.chat_id, path)
    time.sleep(1)


use_step_matcher("parse")


@then("бот отправляет фото")
def step_bot_sends_photo(context):
    context.collector.wait_for_response(timeout=5.0)
    context.collector.assert_photo()


@then('бот отправляет фото с подписью "{caption}"')
def step_bot_sends_photo_with_caption(context, caption):
    context.collector.wait_for_response(timeout=5.0)
    context.collector.assert_photo(caption=caption)
