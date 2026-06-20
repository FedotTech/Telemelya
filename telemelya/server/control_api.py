"""Control API endpoints for test orchestration."""

from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from telemelya.models import (
    ChooseInlineResultRequest,
    InlineQueryRequest,
    SendUpdateRequest,
    TelegramApiResponse,
)
from telemelya.server.auth import require_api_key
from telemelya.server.state import state_manager
from telemelya.server.media import media_manager
from telemelya.server.webhook import deliver_update

router = APIRouter(
    prefix="/api/v1/test",
    dependencies=[Depends(require_api_key)],
)


def _make_update(req: SendUpdateRequest, session_id: str) -> dict:
    """Build a Telegram Update object from the request."""
    update_id = int(time.time() * 1000) % 10_000_000

    from_user = {
        "id": req.from_user.id if req.from_user else req.chat_id,
        "is_bot": False,
        "first_name": req.from_user.first_name if req.from_user else "TestUser",
    }
    if req.from_user and req.from_user.username:
        from_user["username"] = req.from_user.username

    chat = {"id": req.chat_id, "type": "private"}

    if req.callback_data:
        message_id = req.callback_message_id or 1
        update = {
            "update_id": update_id,
            "callback_query": {
                "id": str(uuid.uuid4()),
                "from": from_user,
                "chat_instance": str(req.chat_id),
                "data": req.callback_data,
                "message": {
                    "message_id": message_id,
                    "from": from_user,
                    "chat": chat,
                    "date": int(time.time()),
                    "text": "",
                },
            },
        }
    else:
        text = req.text or ""
        if req.command:
            text = req.command if req.command.startswith("/") else f"/{req.command}"

        entities = None
        if text.startswith("/"):
            entities = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]

        message: dict = {
            "message_id": int(time.time() * 1000) % 1_000_000,
            "from": from_user,
            "chat": chat,
            "date": int(time.time()),
            "text": text,
        }
        if entities:
            message["entities"] = entities

        if req.photo_file_id:
            message["photo"] = [
                {
                    "file_id": req.photo_file_id,
                    "file_unique_id": req.photo_file_id[:16],
                    "width": 800,
                    "height": 600,
                }
            ]
            if req.photo_caption:
                message["caption"] = req.photo_caption

        update = {"update_id": update_id, "message": message}

    return update


@router.post("/send_update")
async def send_update(
    req: SendUpdateRequest,
    request: Request,
    bot_token: str = Query(..., alias="bot_token"),
):
    session_id = (
        request.headers.get("X-Test-Session")
        or request.query_params.get("session_id")
        or "default"
    )

    update = _make_update(req, session_id)

    # Map chat_id → session_id so bot's API calls are tracked
    await state_manager.map_chat_to_session(req.chat_id, session_id)

    # answerCallbackQuery carries no chat_id, so map the callback_query_id too.
    cb = update.get("callback_query")
    if cb and cb.get("id"):
        await state_manager.map_callback_to_session(cb["id"], session_id)

    delivery = await deliver_update(bot_token, update)

    if not delivery.get("delivered"):
        raise HTTPException(
            status_code=424,
            detail={
                "error": delivery.get("error", "Webhook delivery failed"),
                "hint": "Make sure the bot is running and has called setWebhook on the mock server.",
                "bot_token": bot_token,
            },
        )

    return {
        "ok": True,
        "update": update,
        "delivery": delivery,
        "session_id": session_id,
    }


def _from_user_dict(req_user, fallback_id: int) -> dict:
    user = {
        "id": req_user.id if req_user else fallback_id,
        "is_bot": False,
        "first_name": req_user.first_name if req_user else "TestUser",
    }
    if req_user and req_user.username:
        user["username"] = req_user.username
    return user


@router.post("/send_inline_query")
async def send_inline_query(
    req: InlineQueryRequest,
    request: Request,
    bot_token: str = Query(..., alias="bot_token"),
):
    """Emulate an inline query: deliver an inline_query update to the bot.

    The bot is expected to answer with answerInlineQuery; the mock maps the
    generated inline_query_id to this session so the answer is recorded here.
    """
    session_id = (
        request.headers.get("X-Test-Session")
        or request.query_params.get("session_id")
        or "default"
    )

    inline_query_id = str(uuid.uuid4())
    await state_manager.map_inline_to_session(inline_query_id, session_id)
    if req.chat_id is not None:
        await state_manager.map_chat_to_session(req.chat_id, session_id)

    fallback_id = req.from_user.id if req.from_user else (req.chat_id or 0)
    update = {
        "update_id": int(time.time() * 1000) % 10_000_000,
        "inline_query": {
            "id": inline_query_id,
            "from": _from_user_dict(req.from_user, fallback_id),
            "query": req.query,
            "offset": req.offset,
        },
    }

    delivery = await deliver_update(bot_token, update)
    if not delivery.get("delivered"):
        raise HTTPException(
            status_code=424,
            detail={
                "error": delivery.get("error", "Webhook delivery failed"),
                "hint": "Make sure the bot is running and handles inline_query.",
                "bot_token": bot_token,
            },
        )

    return {
        "ok": True,
        "inline_query_id": inline_query_id,
        "update": update,
        "delivery": delivery,
        "session_id": session_id,
    }


@router.post("/choose_inline_result")
async def choose_inline_result(
    req: ChooseInlineResultRequest,
    request: Request,
    bot_token: str = Query(..., alias="bot_token"),
):
    """Emulate the user picking an inline result.

    Mechanism A (default): take input_message_content of the chosen result
    (recorded by answerInlineQuery) and post it into the chat as a bot message.
    Mechanism B (deliver_update=True): deliver a chosen_inline_result update so
    the bot itself decides what to post.
    """
    session_id = (
        request.headers.get("X-Test-Session")
        or request.query_params.get("session_id")
        or "default"
    )
    await state_manager.map_chat_to_session(req.chat_id, session_id)

    inline_query_id = req.inline_query_id
    results = None
    if inline_query_id:
        results = await state_manager.get_inline_results(
            session_id, inline_query_id
        )
    else:
        latest = await state_manager.get_latest_inline_results(session_id)
        if latest:
            inline_query_id, results = latest

    if not results:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "No inline results recorded for this session.",
                "hint": "Call send_inline_query first and ensure the bot "
                "answered with answerInlineQuery before choosing a result.",
            },
        )

    # Resolve the chosen result by id or index (default: first result).
    chosen = None
    if req.result_id is not None:
        chosen = next(
            (r for r in results if str(r.get("id")) == str(req.result_id)), None
        )
    elif req.result_index is not None:
        if 0 <= req.result_index < len(results):
            chosen = results[req.result_index]
    else:
        chosen = results[0]

    if chosen is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Chosen inline result not found in recorded set."},
        )

    delivery = None
    if req.deliver_update:
        fallback_id = req.from_user.id if req.from_user else req.chat_id
        update = {
            "update_id": int(time.time() * 1000) % 10_000_000,
            "chosen_inline_result": {
                "result_id": str(chosen.get("id")),
                "from": _from_user_dict(req.from_user, fallback_id),
                "query": "",
            },
        }
        delivery = await deliver_update(bot_token, update)

    # Mechanism A: post the result's message content as a bot message.
    content = chosen.get("input_message_content") or {}
    text = content.get("message_text", "")
    message_id = await state_manager.next_message_id(session_id)
    message = {
        "message_id": message_id,
        "from": {"id": 123456789, "is_bot": True, "first_name": "TestBot"},
        "chat": {"id": req.chat_id, "type": "private"},
        "date": int(time.time()),
        "text": text,
    }
    if chosen.get("reply_markup"):
        message["reply_markup"] = chosen["reply_markup"]
    await state_manager.store_message(session_id, message_id, message)

    response_record = {
        "method": "sendMessage",
        "chat_id": req.chat_id,
        "message_id": message_id,
        "text": text,
        "reply_markup": chosen.get("reply_markup"),
        "via_inline": True,
        "raw": {"chosen_inline_result_id": chosen.get("id")},
    }
    await state_manager.push_response(session_id, response_record)

    return {
        "ok": True,
        "chosen": chosen,
        "message_id": message_id,
        "delivery": delivery,
        "session_id": session_id,
    }


@router.post("/upload_media")
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    session_id: Optional[str] = Query(None),
):
    """Upload media bytes so a later update can reference them by file_id.

    Returns the generated file_id; the bot's getFile/download will then serve
    the real bytes from MinIO.
    """
    sid = (
        session_id
        or request.headers.get("X-Test-Session")
        or "default"
    )
    file_id = str(uuid.uuid4())
    filename = file.filename or "upload.bin"
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"

    await media_manager.upload(sid, file_id, filename, data, content_type)
    await state_manager.push_media_meta(
        sid,
        {
            "file_id": file_id,
            "file_unique_id": file_id[:16],
            "filename": filename,
            "session_id": sid,
        },
    )
    await state_manager.set_file_meta(
        file_id, {"session_id": sid, "filename": filename}
    )

    return {
        "ok": True,
        "file_id": file_id,
        "file_unique_id": file_id[:16],
        "size": len(data),
        "session_id": sid,
    }


@router.get("/responses")
async def get_responses(
    request: Request,
    session_id: Optional[str] = Query(None),
):
    sid = (
        session_id
        or request.headers.get("X-Test-Session")
        or "default"
    )
    responses = await state_manager.get_responses(sid)
    return {"ok": True, "responses": responses, "session_id": sid}


@router.get("/responses/wait")
async def wait_for_response(
    request: Request,
    session_id: Optional[str] = Query(None),
    timeout: float = Query(5.0),
):
    sid = (
        session_id
        or request.headers.get("X-Test-Session")
        or "default"
    )
    response = await state_manager.wait_for_response(sid, timeout=timeout)
    if response:
        return {"ok": True, "response": response, "session_id": sid}
    return {"ok": True, "response": None, "session_id": sid, "timeout": True}


@router.post("/reset")
async def reset_session(
    request: Request,
    session_id: Optional[str] = Query(None),
):
    sid = (
        session_id
        or request.headers.get("X-Test-Session")
        or "default"
    )
    await state_manager.reset_session(sid)
    await media_manager.cleanup_session(sid)
    return {"ok": True, "session_id": sid}


@router.get("/media/{file_id}")
async def get_media(
    file_id: str,
    request: Request,
    session_id: Optional[str] = Query(None),
):
    sid = (
        session_id
        or request.headers.get("X-Test-Session")
        or "default"
    )
    media_metas = await state_manager.get_media_meta(sid)
    for meta in media_metas:
        if meta.get("file_id") == file_id:
            filename = meta.get("filename", "file")
            data = await media_manager.download(sid, file_id, filename)
            if data:
                return Response(
                    content=data, media_type="application/octet-stream"
                )

    return TelegramApiResponse(
        ok=False, error_code=404, description="Media not found"
    )


@router.get("/health")
async def health():
    redis_ok = await state_manager.ping()
    minio_ok = await media_manager.ping()
    healthy = redis_ok and minio_ok
    return {
        "ok": healthy,
        "redis": "ok" if redis_ok else "error",
        "minio": "ok" if minio_ok else "error",
    }
