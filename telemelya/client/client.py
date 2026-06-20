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

    def _raise_for_status(self, resp: httpx.Response) -> None:
        """Raise with a descriptive message on error responses."""
        if resp.is_success:
            return
        try:
            detail = resp.json().get("detail", {})
            msg = detail.get("error", resp.text) if isinstance(detail, dict) else str(detail)
        except Exception:
            msg = resp.text
        raise httpx.HTTPStatusError(
            f"{resp.status_code}: {msg}",
            request=resp.request,
            response=resp,
        )

    def send_message(self, chat_id: int, text: str) -> dict:
        """Send a text message update to the bot."""
        resp = self._client.post(
            "/api/v1/test/send_update",
            params={"bot_token": self.bot_token},
            json={"chat_id": chat_id, "text": text},
        )
        self._raise_for_status(resp)
        return resp.json()

    def send_command(self, chat_id: int, command: str) -> dict:
        """Send a command (e.g. /start) update to the bot."""
        resp = self._client.post(
            "/api/v1/test/send_update",
            params={"bot_token": self.bot_token},
            json={"chat_id": chat_id, "command": command},
        )
        self._raise_for_status(resp)
        return resp.json()

    def upload_media(self, file_path: str) -> str:
        """Upload media bytes to the mock server; returns the file_id."""
        import os

        with open(file_path, "rb") as fh:
            data = fh.read()
        filename = os.path.basename(file_path) or "upload.bin"
        resp = self._client.post(
            "/api/v1/test/upload_media",
            params={"session_id": self.session_id},
            files={"file": (filename, data, "image/jpeg")},
        )
        self._raise_for_status(resp)
        return resp.json()["file_id"]

    def send_photo(
        self, chat_id: int, photo_path: str, caption: Optional[str] = None
    ) -> dict:
        """Send a photo update to the bot, delivering real image bytes.

        The file is uploaded to the mock server first so the bot's
        getFile/download_file calls return the actual bytes.
        """
        photo_file_id = self.upload_media(photo_path)
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
        self._raise_for_status(resp)
        return resp.json()

    def send_inline_query(
        self,
        query: str,
        from_user: Optional[dict] = None,
        chat_id: Optional[int] = None,
        offset: str = "",
    ) -> dict:
        """Emulate an inline query update; returns the inline_query_id."""
        payload: dict = {"query": query, "offset": offset}
        if from_user:
            payload["from_user"] = from_user
        if chat_id is not None:
            payload["chat_id"] = chat_id
        resp = self._client.post(
            "/api/v1/test/send_inline_query",
            params={"bot_token": self.bot_token},
            json=payload,
        )
        self._raise_for_status(resp)
        return resp.json()

    def choose_inline_result(
        self,
        chat_id: int,
        *,
        inline_query_id: Optional[str] = None,
        result_id: Optional[str] = None,
        result_index: Optional[int] = None,
        from_user: Optional[dict] = None,
        deliver_update: bool = False,
    ) -> dict:
        """Emulate the user choosing an inline result."""
        payload: dict = {"chat_id": chat_id, "deliver_update": deliver_update}
        if inline_query_id is not None:
            payload["inline_query_id"] = inline_query_id
        if result_id is not None:
            payload["result_id"] = result_id
        if result_index is not None:
            payload["result_index"] = result_index
        if from_user:
            payload["from_user"] = from_user
        resp = self._client.post(
            "/api/v1/test/choose_inline_result",
            params={"bot_token": self.bot_token},
            json=payload,
        )
        self._raise_for_status(resp)
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
        self._raise_for_status(resp)
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
