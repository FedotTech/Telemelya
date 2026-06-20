"""Redis state layer: webhook registry, response log, session management."""

from __future__ import annotations

import json
from typing import Optional

import redis.asyncio as redis

from telemelya.server.config import settings

RESPONSE_TTL = 3600  # 1 hour
MEDIA_META_TTL = 3600
MESSAGE_TTL = 3600
INLINE_TTL = 3600


class StateManager:
    """Async Redis state manager for the mock server."""

    def __init__(self) -> None:
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        self._redis = redis.from_url(
            settings.redis_url, decode_responses=True
        )

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()

    @property
    def redis(self) -> redis.Redis:
        assert self._redis is not None, "Redis not connected"
        return self._redis

    # --- Webhook registry ---

    async def set_webhook(self, token: str, url: str) -> None:
        await self.redis.set(f"webhook:{token}", url)

    async def get_webhook(self, token: str) -> Optional[str]:
        return await self.redis.get(f"webhook:{token}")

    async def delete_webhook(self, token: str) -> None:
        await self.redis.delete(f"webhook:{token}")

    # --- Response log ---

    async def push_response(self, session_id: str, response: dict) -> None:
        key = f"responses:{session_id}"
        await self.redis.rpush(key, json.dumps(response))
        await self.redis.expire(key, RESPONSE_TTL)

    async def get_responses(self, session_id: str) -> list[dict]:
        key = f"responses:{session_id}"
        items = await self.redis.lrange(key, 0, -1)
        return [json.loads(item) for item in items]

    async def wait_for_response(
        self, session_id: str, timeout: float = 5.0
    ) -> Optional[dict]:
        key = f"responses:{session_id}"
        try:
            result = await self.redis.blpop(key, timeout=timeout)
        except redis.TimeoutError:
            # blpop hit its timeout with nothing queued — treat as "no response"
            # rather than surfacing a 500 to the caller.
            return None
        if result:
            _, data = result
            return json.loads(data)
        return None

    # --- Media metadata ---

    async def push_media_meta(self, session_id: str, meta: dict) -> None:
        key = f"media_meta:{session_id}"
        await self.redis.rpush(key, json.dumps(meta))
        await self.redis.expire(key, MEDIA_META_TTL)

    async def get_media_meta(self, session_id: str) -> list[dict]:
        key = f"media_meta:{session_id}"
        items = await self.redis.lrange(key, 0, -1)
        return [json.loads(item) for item in items]

    async def set_file_meta(self, file_id: str, meta: dict) -> None:
        """Global file_id → {session_id, filename} map.

        Lets getFile resolve a file even when the calling bot provides no
        session header or chat_id.
        """
        key = f"file_meta:{file_id}"
        await self.redis.set(key, json.dumps(meta))
        await self.redis.expire(key, MEDIA_META_TTL)

    async def get_file_meta(self, file_id: str) -> Optional[dict]:
        raw = await self.redis.get(f"file_meta:{file_id}")
        return json.loads(raw) if raw else None

    # --- Stored messages (for edit-in-place) ---

    async def next_message_id(self, session_id: str) -> int:
        """Return a monotonic, deterministic message_id for the session."""
        key = f"msgseq:{session_id}"
        message_id = await self.redis.incr(key)
        await self.redis.expire(key, MESSAGE_TTL)
        return int(message_id)

    async def store_message(
        self, session_id: str, message_id: int, message: dict
    ) -> None:
        key = f"messages:{session_id}"
        await self.redis.hset(key, str(message_id), json.dumps(message))
        await self.redis.expire(key, MESSAGE_TTL)

    async def get_message(
        self, session_id: str, message_id: int
    ) -> Optional[dict]:
        key = f"messages:{session_id}"
        raw = await self.redis.hget(key, str(message_id))
        return json.loads(raw) if raw else None

    # store_message overwrites, so update is an alias for clarity at call sites
    update_message = store_message

    # --- Inline query results (for inline-mode emulation) ---

    async def store_inline_results(
        self, session_id: str, inline_query_id: str, results: list
    ) -> None:
        key = f"inline_results:{session_id}"
        await self.redis.hset(key, inline_query_id, json.dumps(results))
        await self.redis.expire(key, INLINE_TTL)

    async def get_inline_results(
        self, session_id: str, inline_query_id: str
    ) -> Optional[list]:
        key = f"inline_results:{session_id}"
        raw = await self.redis.hget(key, inline_query_id)
        return json.loads(raw) if raw else None

    async def map_inline_to_session(
        self, inline_query_id: str, session_id: str
    ) -> None:
        key = f"inline_session:{inline_query_id}"
        await self.redis.set(key, session_id)
        await self.redis.expire(key, INLINE_TTL)

    async def get_session_by_inline(
        self, inline_query_id: str
    ) -> Optional[str]:
        return await self.redis.get(f"inline_session:{inline_query_id}")

    async def get_latest_inline_results(
        self, session_id: str
    ) -> Optional[tuple[str, list]]:
        """Return (inline_query_id, results) for the most recent answerInlineQuery."""
        key = f"inline_results:{session_id}"
        entries = await self.redis.hgetall(key)
        if not entries:
            return None
        # Redis hashes don't preserve insertion order reliably; the caller
        # usually passes an explicit id, this is a best-effort convenience.
        last_id = list(entries.keys())[-1]
        return last_id, json.loads(entries[last_id])

    # --- Chat → Session mapping ---

    async def map_chat_to_session(
        self, chat_id: int, session_id: str
    ) -> None:
        key = f"chat_session:{chat_id}"
        await self.redis.set(key, session_id)
        await self.redis.expire(key, RESPONSE_TTL)

    async def get_session_by_chat(self, chat_id: int) -> Optional[str]:
        return await self.redis.get(f"chat_session:{chat_id}")

    # --- CallbackQuery → Session mapping ---
    # answerCallbackQuery carries no chat_id, so the session is resolved from
    # the callback_query_id that was generated when the update was delivered.

    async def map_callback_to_session(
        self, callback_query_id: str, session_id: str
    ) -> None:
        key = f"callback_session:{callback_query_id}"
        await self.redis.set(key, session_id)
        await self.redis.expire(key, RESPONSE_TTL)

    async def get_session_by_callback(
        self, callback_query_id: str
    ) -> Optional[str]:
        return await self.redis.get(f"callback_session:{callback_query_id}")

    # --- Session cleanup ---

    async def reset_session(self, session_id: str) -> None:
        keys = [
            f"responses:{session_id}",
            f"media_meta:{session_id}",
            f"messages:{session_id}",
            f"msgseq:{session_id}",
            f"inline_results:{session_id}",
        ]
        await self.redis.delete(*keys)

    # --- Health ---

    async def ping(self) -> bool:
        try:
            return await self.redis.ping()
        except Exception:
            return False


state_manager = StateManager()
