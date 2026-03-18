"""TelegramTestClient — sync httpx-based client for Telemelya Control API."""

from __future__ import annotations

import uuid
from typing import Optional

import httpx


class TelegramTestClient:
    """Client for interacting with the Telemelya mock server."""

    def __init__(
        self,
        server_url: str,
        api_key: str,
        bot_token: str,
        session_id: Optional[str] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.bot_token = bot_token
        self.session_id = session_id or str(uuid.uuid4())
        self._client = httpx.Client(
            base_url=self.server_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-Test-Session": self.session_id,
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def send_message(self, chat_id: int, text: str) -> dict:
        """Send a text message update to the bot."""
        resp = self._client.post(
            "/api/v1/test/send_update",
            params={"bot_token": self.bot_token},
            json={"chat_id": chat_id, "text": text},
        )
        resp.raise_for_status()
        return resp.json()

    def send_command(self, chat_id: int, command: str) -> dict:
        """Send a command (e.g. /start) update to the bot."""
        resp = self._client.post(
            "/api/v1/test/send_update",
            params={"bot_token": self.bot_token},
            json={"chat_id": chat_id, "command": command},
        )
        resp.raise_for_status()
        return resp.json()

    def send_photo(
        self, chat_id: int, photo_path: str, caption: Optional[str] = None
    ) -> dict:
        """Send a photo update to the bot (simulated via file_id)."""
        photo_file_id = str(uuid.uuid4())
        payload: dict = {
            "chat_id": chat_id,
            "photo_file_id": photo_file_id,
        }
        if caption:
            payload["photo_caption"] = caption

        resp = self._client.post(
            "/api/v1/test/send_update",
            params={"bot_token": self.bot_token},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def send_callback_query(
        self, chat_id: int, data: str, message_id: int
    ) -> dict:
        """Send a callback query update to the bot."""
        resp = self._client.post(
            "/api/v1/test/send_update",
            params={"bot_token": self.bot_token},
            json={
                "chat_id": chat_id,
                "callback_data": data,
                "callback_message_id": message_id,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def get_responses(self) -> list[dict]:
        """Get all recorded bot responses for this session."""
        resp = self._client.get(
            "/api/v1/test/responses",
            params={"session_id": self.session_id},
        )
        resp.raise_for_status()
        return resp.json().get("responses", [])

    def wait_for_response(self, timeout: float = 5.0) -> Optional[dict]:
        """Wait for a bot response (long-poll from Redis)."""
        resp = self._client.get(
            "/api/v1/test/responses/wait",
            params={"session_id": self.session_id, "timeout": timeout},
            timeout=timeout + 5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response")

    def get_media(self, file_id: str) -> bytes:
        """Download a media file by file_id."""
        resp = self._client.get(
            f"/api/v1/test/media/{file_id}",
            params={"session_id": self.session_id},
        )
        resp.raise_for_status()
        return resp.content

    def reset(self) -> None:
        """Reset session state (clear responses and media)."""
        resp = self._client.post(
            "/api/v1/test/reset",
            params={"session_id": self.session_id},
        )
        resp.raise_for_status()
