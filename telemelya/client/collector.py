"""ResponseCollector — assertion helpers for bot responses."""

from __future__ import annotations

from typing import Optional

from telemelya.client.client import TelegramTestClient


class ResponseCollector:
    """Collects and asserts on bot responses from the mock server."""

    def __init__(self, client: TelegramTestClient):
        self.client = client
        self._last_response: Optional[dict] = None

    def wait_for_response(self, timeout: float = 5.0) -> dict:
        """Wait for a single bot response and store it."""
        response = self.client.wait_for_response(timeout=timeout)
        if response is None:
            raise TimeoutError(
                f"No bot response received within {timeout}s"
            )
        self._last_response = response
        return response

    @property
    def last(self) -> dict:
        assert self._last_response is not None, "No response collected yet"
        return self._last_response

    def assert_text(self, expected: str) -> None:
        """Assert the last response text equals expected."""
        actual = self.last.get("text", "")
        assert actual == expected, (
            f"Expected text {expected!r}, got {actual!r}"
        )

    def assert_contains(self, substring: str) -> None:
        """Assert the last response text contains substring."""
        actual = self.last.get("text", "")
        assert substring in actual, (
            f"Expected {substring!r} in {actual!r}"
        )

    def assert_photo(self, caption: Optional[str] = None) -> None:
        """Assert the last response is a photo (optionally with caption)."""
        method = self.last.get("method", "")
        assert method == "sendPhoto", (
            f"Expected sendPhoto, got {method!r}"
        )
        if caption is not None:
            actual_caption = self.last.get("caption", "")
            assert actual_caption == caption, (
                f"Expected caption {caption!r}, got {actual_caption!r}"
            )

    def assert_reply_markup(self, buttons: list) -> None:
        """Assert the last response has reply_markup with given button texts."""
        markup = self.last.get("reply_markup")
        assert markup is not None, "No reply_markup in response"

        inline_kb = markup.get("inline_keyboard", [])
        actual_buttons = [
            btn.get("text", "") for row in inline_kb for btn in row
        ]
        assert actual_buttons == buttons, (
            f"Expected buttons {buttons!r}, got {actual_buttons!r}"
        )

    def get_media(self, file_id: str) -> bytes:
        """Download media file by file_id."""
        return self.client.get_media(file_id)

    def get_all_responses(self) -> list[dict]:
        """Get all recorded responses for this session."""
        return self.client.get_responses()
