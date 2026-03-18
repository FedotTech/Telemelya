"""Redis state layer: webhook registry, response log, session management."""

from __future__ import annotations

import json
from typing import Optional

import redis.asyncio as redis

from telemelya.server.config import settings

RESPONSE_TTL = 3600  # 1 hour
MEDIA_META_TTL = 3600


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
        result = await self.redis.blpop(key, timeout=timeout)
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

    # --- Chat → Session mapping ---

    async def map_chat_to_session(
        self, chat_id: int, session_id: str
    ) -> None:
        key = f"chat_session:{chat_id}"
        await self.redis.set(key, session_id)
        await self.redis.expire(key, RESPONSE_TTL)

    async def get_session_by_chat(self, chat_id: int) -> Optional[str]:
        return await self.redis.get(f"chat_session:{chat_id}")

    # --- Session cleanup ---

    async def reset_session(self, session_id: str) -> None:
        keys = [f"responses:{session_id}", f"media_meta:{session_id}"]
        await self.redis.delete(*keys)

    # --- Health ---

    async def ping(self) -> bool:
        try:
            return await self.redis.ping()
        except Exception:
            return False


state_manager = StateManager()
