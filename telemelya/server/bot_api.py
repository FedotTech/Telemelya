"""Bot API endpoints emulating api.telegram.org/bot{token}/."""

from __future__ import annotations

import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile

from telemelya.models import TelegramApiResponse, PhotoSize, WebhookInfo
from telemelya.server.state import state_manager
from telemelya.server.media import media_manager

router = APIRouter()

# Default bot info stub
DEFAULT_BOT_INFO = {
    "id": 123456789,
    "is_bot": True,
    "first_name": "TestBot",
    "username": "telemelya_bot",
    "can_join_groups": True,
    "can_read_all_group_messages": False,
    "supports_inline_queries": False,
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
    chat_id = body.get("chat_id")
    if isinstance(chat_id, str):
        chat_id = int(chat_id)
    session_id = await _extract_session_id(request, chat_id)
    text = body.get("text", "")

    message_id = int(time.time() * 1000) % 1_000_000

    result = {
        "message_id": message_id,
        "from": DEFAULT_BOT_INFO,
        "chat": {"id": chat_id, "type": "private"},
        "date": int(time.time()),
        "text": text,
    }

    if "reply_markup" in body:
        result["reply_markup"] = body["reply_markup"]

    response_record = {
        "method": "sendMessage",
        "chat_id": chat_id,
        "text": text,
        "reply_markup": body.get("reply_markup"),
        "raw": body,
    }
    await state_manager.push_response(session_id, response_record)

    return TelegramApiResponse(ok=True, result=result)


@router.post("/bot{token}/sendPhoto")
async def send_photo(token: str, request: Request):
    body = await _parse_body(request)
    chat_id = body.get("chat_id", 0)
    if isinstance(chat_id, str):
        chat_id = int(chat_id)
    caption = body.get("caption")
    photo = body.get("photo")

    file_id = str(uuid.uuid4())
    file_unique_id = file_id[:16]

    if isinstance(photo, UploadFile):
        filename = photo.filename or "photo.jpg"
        photo_data = await photo.read()
        session_id_temp = await _extract_session_id(request, chat_id)
        await media_manager.upload(
            session_id_temp, file_id, filename, photo_data, "image/jpeg"
        )
        file_size = len(photo_data)
    else:
        filename = "photo.jpg"
        file_size = 0

    session_id = await _extract_session_id(request, chat_id)

    photo_sizes = [
        PhotoSize(
            file_id=file_id,
            file_unique_id=file_unique_id,
            width=800,
            height=600,
            file_size=file_size,
        ).model_dump()
    ]

    message_id = int(time.time() * 1000) % 1_000_000
    result = {
        "message_id": message_id,
        "from": DEFAULT_BOT_INFO,
        "chat": {"id": chat_id, "type": "private"},
        "date": int(time.time()),
        "photo": photo_sizes,
        "caption": caption,
    }

    response_record = {
        "method": "sendPhoto",
        "chat_id": chat_id,
        "caption": caption,
        "photo": photo_sizes,
        "file_id": file_id,
        "raw": {"chat_id": chat_id, "caption": caption},
    }
    await state_manager.push_response(session_id, response_record)

    await state_manager.push_media_meta(
        session_id,
        {
            "file_id": file_id,
            "file_unique_id": file_unique_id,
            "filename": filename,
            "session_id": session_id,
        },
    )

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

    return TelegramApiResponse(
        ok=False, error_code=400, description="Bad Request: file not found"
    )


@router.get("/bot{token}/file/{file_path:path}")
async def download_file(token: str, file_path: str):
    from fastapi.responses import Response

    data = await media_manager.download_by_key(file_path)
    if data is None:
        return TelegramApiResponse(
            ok=False, error_code=404, description="File not found"
        )
    return Response(content=data, media_type="application/octet-stream")


@router.post("/bot{token}/answerCallbackQuery")
async def answer_callback_query(token: str, request: Request):
    body = await _parse_body(request)
    session_id = await _extract_session_id(request)

    response_record = {
        "method": "answerCallbackQuery",
        "raw": body,
    }
    await state_manager.push_response(session_id, response_record)

    return TelegramApiResponse(ok=True, result=True)


@router.post("/bot{token}/editMessageText")
async def edit_message_text(token: str, request: Request):
    body = await _parse_body(request)
    chat_id = body.get("chat_id")
    session_id = await _extract_session_id(request, chat_id)

    response_record = {
        "method": "editMessageText",
        "chat_id": chat_id,
        "text": body.get("text"),
        "reply_markup": body.get("reply_markup"),
        "raw": body,
    }
    await state_manager.push_response(session_id, response_record)

    message_id = body.get("message_id", 1)
    result = {
        "message_id": message_id,
        "from": DEFAULT_BOT_INFO,
        "chat": {"id": body.get("chat_id"), "type": "private"},
        "date": int(time.time()),
        "text": body.get("text", ""),
    }
    return TelegramApiResponse(ok=True, result=result)
