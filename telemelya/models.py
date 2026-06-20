"""Pydantic models for Telegram Bot API objects."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class Chat(BaseModel):
    id: int
    type: str = "private"
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class PhotoSize(BaseModel):
    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: Optional[int] = None


class MessageEntity(BaseModel):
    type: str
    offset: int
    length: int
    url: Optional[str] = None
    user: Optional[User] = None
    language: Optional[str] = None


class InlineKeyboardButton(BaseModel):
    text: str
    url: Optional[str] = None
    callback_data: Optional[str] = None


class InlineKeyboardMarkup(BaseModel):
    inline_keyboard: list[list[InlineKeyboardButton]]


class ReplyKeyboardButton(BaseModel):
    text: str
    request_contact: Optional[bool] = None
    request_location: Optional[bool] = None


class ReplyKeyboardMarkup(BaseModel):
    keyboard: list[list[ReplyKeyboardButton]]
    resize_keyboard: Optional[bool] = None
    one_time_keyboard: Optional[bool] = None


class Message(BaseModel):
    message_id: int
    from_: Optional[User] = Field(default=None, alias="from")
    chat: Chat
    date: int
    text: Optional[str] = None
    entities: Optional[list[MessageEntity]] = None
    photo: Optional[list[PhotoSize]] = None
    caption: Optional[str] = None
    reply_markup: Optional[InlineKeyboardMarkup] = None

    model_config = {"populate_by_name": True}


class CallbackQuery(BaseModel):
    id: str
    from_: User = Field(alias="from")
    message: Optional[Message] = None
    chat_instance: str = ""
    data: Optional[str] = None

    model_config = {"populate_by_name": True}


class InlineQuery(BaseModel):
    id: str
    from_: User = Field(alias="from")
    query: str = ""
    offset: str = ""

    model_config = {"populate_by_name": True}


class InputTextMessageContent(BaseModel):
    message_text: str
    parse_mode: Optional[str] = None


class InlineQueryResultArticle(BaseModel):
    type: str = "article"
    id: str
    title: str
    input_message_content: InputTextMessageContent
    reply_markup: Optional[InlineKeyboardMarkup] = None
    description: Optional[str] = None


class ChosenInlineResult(BaseModel):
    result_id: str
    from_: User = Field(alias="from")
    query: str = ""
    inline_message_id: Optional[str] = None

    model_config = {"populate_by_name": True}


class Update(BaseModel):
    update_id: int
    message: Optional[Message] = None
    callback_query: Optional[CallbackQuery] = None
    inline_query: Optional[InlineQuery] = None
    chosen_inline_result: Optional[ChosenInlineResult] = None


class WebhookInfo(BaseModel):
    url: str
    has_custom_certificate: bool = False
    pending_update_count: int = 0


class File(BaseModel):
    file_id: str
    file_unique_id: str
    file_size: Optional[int] = None
    file_path: Optional[str] = None


class BotResponse(BaseModel):
    """A recorded bot response from the mock server."""
    method: str
    chat_id: Optional[int] = None
    message_id: Optional[int] = None
    text: Optional[str] = None
    caption: Optional[str] = None
    photo: Optional[list[PhotoSize]] = None
    file_id: Optional[str] = None
    reply_markup: Optional[dict] = None
    # answerCallbackQuery
    callback_query_id: Optional[str] = None
    show_alert: Optional[bool] = None
    # answerInlineQuery
    inline_query_id: Optional[str] = None
    results: Optional[list] = None
    raw: dict = Field(default_factory=dict)


class SendUpdateRequest(BaseModel):
    """Request body for POST /api/v1/test/send_update."""
    chat_id: int
    text: Optional[str] = None
    command: Optional[str] = None
    photo_file_id: Optional[str] = None
    photo_caption: Optional[str] = None
    callback_data: Optional[str] = None
    callback_message_id: Optional[int] = None
    from_user: Optional[User] = None


class InlineQueryRequest(BaseModel):
    """Request body for POST /api/v1/test/send_inline_query."""
    query: str = ""
    from_user: Optional[User] = None
    chat_id: Optional[int] = None
    offset: str = ""


class ChooseInlineResultRequest(BaseModel):
    """Request body for POST /api/v1/test/choose_inline_result."""
    chat_id: int
    inline_query_id: Optional[str] = None
    result_id: Optional[str] = None
    result_index: Optional[int] = None
    from_user: Optional[User] = None
    deliver_update: bool = False


class TelegramApiResponse(BaseModel):
    """Standard Telegram Bot API response wrapper."""
    ok: bool = True
    result: Optional[dict | list | bool] = None
    description: Optional[str] = None
    error_code: Optional[int] = None
