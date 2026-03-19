"""Control API endpoints for test orchestration."""

from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from telemelya.models import SendUpdateRequest, TelegramApiResponse
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
