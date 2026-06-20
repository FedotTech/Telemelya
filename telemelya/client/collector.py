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

    def assert_callback_answered(
        self,
        text: Optional[str] = None,
        show_alert: Optional[bool] = None,
    ) -> dict:
        """Assert an answerCallbackQuery is recorded (optionally text/show_alert)."""
        answers = [
            r
            for r in self.get_all_responses()
            if r.get("method") == "answerCallbackQuery"
        ]
        assert answers, "No answerCallbackQuery recorded"
        answer = answers[-1]
        if text is not None:
            assert answer.get("text") == text, (
                f"Expected callback text {text!r}, got {answer.get('text')!r}"
            )
        if show_alert is not None:
            assert bool(answer.get("show_alert")) == show_alert, (
                f"Expected show_alert={show_alert}, got {answer.get('show_alert')!r}"
            )
        return answer

    def assert_inline_answered(self, *, min_results: int = 1) -> dict:
        """Assert an answerInlineQuery is recorded with at least min_results."""
        answers = [
            r
            for r in self.get_all_responses()
            if r.get("method") == "answerInlineQuery"
        ]
        assert answers, "No answerInlineQuery recorded"
        answer = answers[-1]
        results = answer.get("results") or []
        assert len(results) >= min_results, (
            f"Expected >= {min_results} inline results, got {len(results)}"
        )
        return answer

    def find_response(
        self,
        *,
        method: Optional[str] = None,
        contains: Optional[str] = None,
        has_button: Optional[str] = None,
    ) -> Optional[dict]:
        """Find a recorded response by method/text substring/button text.

        Returns the matching record (with its message_id) or None. Prefer this
        over `last_message_id` when the bot emits several messages and you need
        to address a specific one.
        """
        for record in self.get_all_responses():
            if method is not None and record.get("method") != method:
                continue
            if contains is not None:
                haystack = (record.get("text") or "") + (record.get("caption") or "")
                if contains not in haystack:
                    continue
            if has_button is not None:
                markup = record.get("reply_markup") or {}
                texts = [
                    btn.get("text", "")
                    for row in markup.get("inline_keyboard", [])
                    for btn in row
                ]
                if has_button not in texts:
                    continue
            return record
        return None

    @property
    def last_message_id(self) -> Optional[int]:
        """message_id of the last collected response (convenience only).

        For assertions addressing a specific message prefer `find_response`,
        since a flow may emit several messages.
        """
        return self.last.get("message_id") if self._last_response else None

    def get_media(self, file_id: str) -> bytes:
        """Download media file by file_id."""
        return self.client.get_media(file_id)

    def get_all_responses(self) -> list[dict]:
        """Get all recorded responses for this session."""
        return self.client.get_responses()
