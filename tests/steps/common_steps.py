"""Common step definitions."""

from behave import given


@given('chat_id "{chat_id}"')
def step_set_chat_id(context, chat_id):
    context.chat_id = int(chat_id)


@given('пользователь с ID "{user_id}"')
def step_set_user_id(context, user_id):
    context.user_id = int(user_id)
