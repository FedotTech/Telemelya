"""Bot API endpoints emulating api.telegram.org/bot{token}/."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile

from telemelya.models import TelegramApiResponse, PhotoSize, WebhookInfo
from telemelya.server.config import settings
from telemelya.server.state import state_manager
from telemelya.server.media import media_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Default bot info stub
DEFAULT_BOT_INFO = {
    "id": 123456789,
    "is_bot": True,
    "first_name": "TestBot",
    "username": "telemelya_bot",
    "can_join_groups": True,
    "can_read_all_group_messages": False,
    "supports_inline_queries": True,
}


async def _parse_body(request: Request) -> dict:
    """Parse request body from JSON or form data."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return await request.json()
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        result = {}
        for key in form:
            value = form[key]
            if isinstance(value, UploadFile):
                result[key] = value
            else:
                # Try to parse JSON values (e.g. reply_markup)
                try:
                    result[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[key] = value
        return result
    # Fallback: try JSON
    try:
        return await request.json()
    except Exception:
        return {}


async def _extract_session_id(request: Request, chat_id: int | None = None) -> str:
    sid = (
        request.headers.get("X-Test-Session")
        or request.query_params.get("session_id")
    )
    if sid:
        return sid
    # Look up session by chat_id (set when send_update was called)
    if chat_id is not None:
        mapped = await state_manager.get_session_by_chat(chat_id)
        if mapped:
            return mapped
    return "default"


def _as_int(value, default=None):
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    if isinstance(value, int):
        return value
    return default


@router.post("/bot{token}/getMe")
async def get_me(token: str):
    return TelegramApiResponse(ok=True, result=DEFAULT_BOT_INFO)


@router.post("/bot{token}/setWebhook")
async def set_webhook(token: str, request: Request):
    body = await _parse_body(request)
    url = body.get("url", "")
    if url:
        await state_manager.set_webhook(token, url)
        return TelegramApiResponse(ok=True, result=True, description="Webhook was set")
    return TelegramApiResponse(
        ok=False, error_code=400, description="Bad Request: no url specified"
    )


@router.post("/bot{token}/deleteWebhook")
async def delete_webhook(token: str):
    await state_manager.delete_webhook(token)
    return TelegramApiResponse(
        ok=True, result=True, description="Webhook was deleted"
    )


@router.post("/bot{token}/getWebhookInfo")
async def get_webhook_info(token: str):
    url = await state_manager.get_webhook(token) or ""
    info = WebhookInfo(url=url)
    return TelegramApiResponse(ok=True, result=info.model_dump())


@router.post("/bot{token}/sendMessage")
async def send_message(token: str, request: Request):
    body = await _parse_body(request)
    chat_id = _as_int(body.get("chat_id"))
    session_id = await _extract_session_id(request, chat_id)
    text = body.get("text", "")

    message_id = await state_manager.next_message_id(session_id)

    result = {
        "message_id": message_id,
        "from": DEFAULT_BOT_INFO,
        "chat": {"id": chat_id, "type": "private"},
        "date": int(time.time()),
        "text": text,
    }

    if "reply_markup" in body:
        result["reply_markup"] = body["reply_markup"]

    await state_manager.store_message(session_id, message_id, result)

    response_record = {
        "method": "sendMessage",
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "reply_markup": body.get("reply_markup"),
        "raw": body,
    }
    await state_manager.push_response(session_id, response_record)

    return TelegramApiResponse(ok=True, result=result)


@router.post("/bot{token}/sendPhoto")
async def send_photo(token: str, request: Request):
    body = await _parse_body(request)
    chat_id = _as_int(body.get("chat_id"), 0)
    caption = body.get("caption")
    photo = body.get("photo")

    session_id = await _extract_session_id(request, chat_id)

    # Resolve file_id and persist bytes if an actual file was uploaded.
    if isinstance(photo, UploadFile):
        file_id = str(uuid.uuid4())
        file_unique_id = file_id[:16]
        filename = photo.filename or "photo.jpg"
        photo_data = await photo.read()
        await media_manager.upload(
            session_id, file_id, filename, photo_data, "image/jpeg"
        )
        file_size = len(photo_data)
        await state_manager.push_media_meta(
            session_id,
            {
                "file_id": file_id,
                "file_unique_id": file_unique_id,
                "filename": filename,
                "session_id": session_id,
            },
        )
        await state_manager.set_file_meta(
            file_id, {"session_id": session_id, "filename": filename}
        )
    elif isinstance(photo, str) and photo:
        # photo passed as an existing file_id (e.g. re-sending uploaded media)
        file_id = photo
        file_unique_id = file_id[:16]
        filename = "photo.jpg"
        file_size = 0
    else:
        file_id = str(uuid.uuid4())
        file_unique_id = file_id[:16]
        filename = "photo.jpg"
        file_size = 0

    photo_sizes = [
        PhotoSize(
            file_id=file_id,
            file_unique_id=file_unique_id,
            width=800,
            height=600,
            file_size=file_size,
        ).model_dump()
    ]

    message_id = await state_manager.next_message_id(session_id)
    result = {
        "message_id": message_id,
        "from": DEFAULT_BOT_INFO,
        "chat": {"id": chat_id, "type": "private"},
        "date": int(time.time()),
        "photo": photo_sizes,
        "caption": caption,
    }
    if "reply_markup" in body:
        result["reply_markup"] = body["reply_markup"]

    await state_manager.store_message(session_id, message_id, result)

    response_record = {
        "method": "sendPhoto",
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": caption,
        "photo": photo_sizes,
        "file_id": file_id,
        "reply_markup": body.get("reply_markup"),
        "raw": {"chat_id": chat_id, "caption": caption},
    }
    await state_manager.push_response(session_id, response_record)

    return TelegramApiResponse(ok=True, result=result)


@router.post("/bot{token}/getFile")
async def get_file(token: str, request: Request):
    body = await _parse_body(request)
    file_id = body.get("file_id", "")
    session_id = await _extract_session_id(request)

    media_metas = await state_manager.get_media_meta(session_id)
    for meta in media_metas:
        if meta.get("file_id") == file_id:
            filename = meta.get("filename", "file")
            file_path = f"{session_id}/{file_id}/{filename}"
            return TelegramApiResponse(
                ok=True,
                result={
                    "file_id": file_id,
                    "file_unique_id": file_id[:16],
                    "file_path": file_path,
                },
            )

    # Fallback: resolve via the global file map (bot calls carry no session).
    if file_id:
        global_meta = await state_manager.get_file_meta(file_id)
        if global_meta:
            owner = global_meta.get("session_id", session_id)
            filename = global_meta.get("filename", "file")
            file_path = f"{owner}/{file_id}/{filename}"
            return TelegramApiResponse(
                ok=True,
                result={
                    "file_id": file_id,
                    "file_unique_id": file_id[:16],
                    "file_path": file_path,
                },
            )

    return TelegramApiResponse(
        ok=False, error_code=400, description="Bad Request: file not found"
    )


async def _serve_file(file_path: str):
    from fastapi.responses import Response

    data = await media_manager.download_by_key(file_path)
    if data is None:
        return TelegramApiResponse(
            ok=False, error_code=404, description="File not found"
        )
    return Response(content=data, media_type="application/octet-stream")


@router.get("/file/bot{token}/{file_path:path}")
async def download_file_telegram(token: str, file_path: str):
    """Real Telegram file URL layout: /file/bot{token}/{file_path}.

    This is what aiogram's bot.download_file() requests.
    """
    return await _serve_file(file_path)


@router.get("/bot{token}/file/{file_path:path}")
async def download_file(token: str, file_path: str):
    """Legacy/mock layout kept for backwards compatibility."""
    return await _serve_file(file_path)


@router.post("/bot{token}/answerCallbackQuery")
async def answer_callback_query(token: str, request: Request):
    body = await _parse_body(request)

    # Resolve session from the callback_query_id (no chat_id is present).
    callback_query_id = body.get("callback_query_id")
    session_id = None
    if callback_query_id:
        session_id = await state_manager.get_session_by_callback(callback_query_id)
    if not session_id:
        session_id = await _extract_session_id(request)

    show_alert = body.get("show_alert")
    if isinstance(show_alert, str):
        show_alert = show_alert.lower() in ("1", "true", "yes")

    response_record = {
        "method": "answerCallbackQuery",
        "callback_query_id": body.get("callback_query_id"),
        "text": body.get("text"),
        "show_alert": bool(show_alert) if show_alert is not None else False,
        "raw": body,
    }
    await state_manager.push_response(session_id, response_record)

    return TelegramApiResponse(ok=True, result=True)


# --- Edit-in-place (editMessageText / ReplyMarkup / Caption) ---

# Fields each edit method is allowed to mutate on the stored message.
_EDIT_FIELDS = ("text", "caption", "reply_markup")


async def _apply_edit(request: Request, method: str) -> TelegramApiResponse:
    body = await _parse_body(request)
    chat_id = _as_int(body.get("chat_id"))
    message_id = _as_int(body.get("message_id"))
    session_id = await _extract_session_id(request, chat_id)

    stored = None
    if message_id is not None:
        stored = await state_manager.get_message(session_id, message_id)

    if stored is None:
        if settings.strict_edit:
            return TelegramApiResponse(
                ok=False,
                error_code=400,
                description="Bad Request: message to edit not found",
            )
        logger.warning(
            "%s: message_id=%r not found in session %r; returning synthetic "
            "Message (enable strict_edit to fail instead)",
            method,
            message_id,
            session_id,
        )
        stored = {
            "message_id": message_id if message_id is not None else 1,
            "from": DEFAULT_BOT_INFO,
            "chat": {"id": chat_id, "type": "private"},
            "date": int(time.time()),
        }

    # Apply whichever editable fields are present in the request body.
    for field in _EDIT_FIELDS:
        if field in body:
            stored[field] = body[field]
    stored["edit_date"] = int(time.time())

    if message_id is not None:
        await state_manager.update_message(session_id, message_id, stored)

    response_record = {
        "method": method,
        "chat_id": chat_id,
        "message_id": message_id,
        "text": stored.get("text"),
        "caption": stored.get("caption"),
        "reply_markup": stored.get("reply_markup"),
        "raw": body,
    }
    await state_manager.push_response(session_id, response_record)

    return TelegramApiResponse(ok=True, result=stored)


@router.post("/bot{token}/editMessageText")
async def edit_message_text(token: str, request: Request):
    return await _apply_edit(request, "editMessageText")


@router.post("/bot{token}/editMessageReplyMarkup")
async def edit_message_reply_markup(token: str, request: Request):
    return await _apply_edit(request, "editMessageReplyMarkup")


@router.post("/bot{token}/editMessageCaption")
async def edit_message_caption(token: str, request: Request):
    return await _apply_edit(request, "editMessageCaption")


@router.post("/bot{token}/deleteMessage")
async def delete_message(token: str, request: Request):
    body = await _parse_body(request)
    chat_id = _as_int(body.get("chat_id"))
    message_id = _as_int(body.get("message_id"))

    session_id = await _extract_session_id(request, chat_id)

    response_record = {
        "method": "deleteMessage",
        "chat_id": chat_id,
        "message_id": message_id,
        "raw": body,
    }
    await state_manager.push_response(session_id, response_record)

    return TelegramApiResponse(ok=True, result=True)


@router.post("/bot{token}/answerInlineQuery")
async def answer_inline_query(token: str, request: Request):
    body = await _parse_body(request)
    inline_query_id = body.get("inline_query_id")

    # Session is mapped from the inline_query_id at delivery time, since
    # inline queries carry no chat_id to resolve the session from.
    session_id = None
    if inline_query_id:
        session_id = await state_manager.get_session_by_inline(inline_query_id)
    if not session_id:
        session_id = await _extract_session_id(request)

    results = body.get("results") or []
    if isinstance(results, str):
        try:
            results = json.loads(results)
        except (json.JSONDecodeError, TypeError):
            results = []

    if inline_query_id:
        await state_manager.store_inline_results(
            session_id, inline_query_id, results
        )

    response_record = {
        "method": "answerInlineQuery",
        "inline_query_id": inline_query_id,
        "results": results,
        "raw": body,
    }
    await state_manager.push_response(session_id, response_record)

    return TelegramApiResponse(ok=True, result=True)
