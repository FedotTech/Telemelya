"""Tests for Bot API recording endpoints: sendMessage, sendPhoto, editMessageText, deleteMessage, answerCallbackQuery."""

import pytest


class TestSendMessage:
    """POST /bot{token}/sendMessage — records bot response."""

    def test_json_body(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 12345, "text": "Hello world"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["result"]["text"] == "Hello world"
        assert data["result"]["chat"]["id"] == 12345

    def test_form_data(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            data={"chat_id": "12345", "text": "Form message"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["text"] == "Form message"

    def test_empty_text(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 12345},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["text"] == ""

    def test_with_reply_markup(self, http, bot_token, headers, session_id):
        markup = {
            "inline_keyboard": [
                [{"text": "Click", "callback_data": "btn_1"}]
            ]
        }
        resp = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 12345, "text": "Choose:", "reply_markup": markup},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["reply_markup"] == markup

    def test_response_recorded(self, http, bot_token, headers, session_id):
        """sendMessage should be recorded in session responses."""
        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 12345, "text": "Recorded message"},
        )
        resp = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        )
        responses = resp.json()["responses"]
        assert len(responses) >= 1
        assert responses[-1]["method"] == "sendMessage"
        assert responses[-1]["text"] == "Recorded message"

    def test_chat_id_string_conversion(self, http, bot_token, headers):
        """chat_id passed as string should be converted to int."""
        resp = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": "99999", "text": "string id"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["chat"]["id"] == 99999

    def test_message_has_unique_id(self, http, bot_token, headers):
        """Each sendMessage should generate a message_id."""
        resp = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 1, "text": "a"},
        )
        assert "message_id" in resp.json()["result"]
        assert isinstance(resp.json()["result"]["message_id"], int)

    def test_record_includes_message_id(self, http, bot_token, headers, session_id):
        """Issue #3 / problem 5: sendMessage record must carry message_id."""
        result = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 12345, "text": "addressable"},
        ).json()["result"]
        record = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        ).json()["responses"][-1]
        assert record["method"] == "sendMessage"
        assert record["message_id"] == result["message_id"]

    def test_message_id_is_monotonic(self, http, bot_token, headers):
        """Deterministic, increasing ids within a session (no time-based collisions)."""
        ids = []
        for i in range(3):
            r = http.post(
                f"/bot{bot_token}/sendMessage",
                headers=headers,
                json={"chat_id": 1, "text": f"m{i}"},
            )
            ids.append(r.json()["result"]["message_id"])
        assert ids == sorted(ids)
        assert len(set(ids)) == 3


class TestSendPhoto:
    """POST /bot{token}/sendPhoto."""

    def test_photo_without_file(self, http, bot_token, headers, session_id):
        """sendPhoto without actual file — should record with file_size=0."""
        resp = http.post(
            f"/bot{bot_token}/sendPhoto",
            headers=headers,
            data={"chat_id": "12345", "caption": "No real file"},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert "photo" in result
        assert result["photo"][0]["file_size"] == 0
        assert result["caption"] == "No real file"

    def test_photo_generates_file_id(self, http, bot_token, headers):
        resp = http.post(
            f"/bot{bot_token}/sendPhoto",
            headers=headers,
            data={"chat_id": "12345"},
        )
        result = resp.json()["result"]
        assert result["photo"][0]["file_id"]
        assert result["photo"][0]["file_unique_id"]

    def test_photo_recorded_in_session(self, http, bot_token, headers, session_id):
        http.post(
            f"/bot{bot_token}/sendPhoto",
            headers=headers,
            data={"chat_id": "12345", "caption": "Test photo"},
        )
        resp = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        )
        responses = resp.json()["responses"]
        assert any(r["method"] == "sendPhoto" for r in responses)


def _send_with_keyboard(http, bot_token, headers, buttons):
    """Helper: send a message with an inline keyboard; return its message_id."""
    markup = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in buttons]]}
    resp = http.post(
        f"/bot{bot_token}/sendMessage",
        headers=headers,
        json={"chat_id": 12345, "text": "pick", "reply_markup": markup},
    )
    return resp.json()["result"]["message_id"]


class TestEditMessageText:
    """POST /bot{token}/editMessageText."""

    def test_edit_message(self, http, bot_token, headers, session_id):
        msg_id = _send_with_keyboard(http, bot_token, headers, [("A", "a")])
        resp = http.post(
            f"/bot{bot_token}/editMessageText",
            headers=headers,
            json={"chat_id": 12345, "message_id": msg_id, "text": "Edited text"},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["text"] == "Edited text"
        assert result["message_id"] == msg_id

    def test_edit_text_returns_new_reply_markup(self, http, bot_token, headers):
        """Acceptance #1: editMessageText with new keyboard returns it in result."""
        msg_id = _send_with_keyboard(http, bot_token, headers, [("Old", "old")])
        new_markup = {"inline_keyboard": [[{"text": "New", "callback_data": "new"}]]}
        resp = http.post(
            f"/bot{bot_token}/editMessageText",
            headers=headers,
            json={
                "chat_id": 12345,
                "message_id": msg_id,
                "text": "updated",
                "reply_markup": new_markup,
            },
        )
        result = resp.json()["result"]
        assert result["reply_markup"] == new_markup

    def test_edit_recorded(self, http, bot_token, headers, session_id):
        msg_id = _send_with_keyboard(http, bot_token, headers, [("A", "a")])
        http.post(
            f"/bot{bot_token}/editMessageText",
            headers=headers,
            json={"chat_id": 12345, "message_id": msg_id, "text": "New text"},
        )
        responses = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        ).json()["responses"]
        edits = [r for r in responses if r["method"] == "editMessageText"]
        assert edits and edits[-1]["message_id"] == msg_id


class TestEditMessageReplyMarkup:
    """POST /bot{token}/editMessageReplyMarkup — the core SMP-169 edit-in-place case."""

    def test_endpoint_exists_and_returns_new_markup(self, http, bot_token, headers):
        """Acceptance #1: must not 404 (caused Failed to deserialize) and
        result must contain the NEW reply_markup."""
        msg_id = _send_with_keyboard(http, bot_token, headers, [("Share", "share")])
        new_markup = {"inline_keyboard": [[{"text": "Shared ✓", "callback_data": "done"}]]}
        resp = http.post(
            f"/bot{bot_token}/editMessageReplyMarkup",
            headers=headers,
            json={"chat_id": 12345, "message_id": msg_id, "reply_markup": new_markup},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["reply_markup"] == new_markup
        assert result["message_id"] == msg_id

    def test_edit_applies_to_stored_message(self, http, bot_token, headers):
        """A subsequent edit sees the previously applied markup (state persisted)."""
        msg_id = _send_with_keyboard(http, bot_token, headers, [("1", "1")])
        m1 = {"inline_keyboard": [[{"text": "2", "callback_data": "2"}]]}
        http.post(
            f"/bot{bot_token}/editMessageReplyMarkup",
            headers=headers,
            json={"chat_id": 12345, "message_id": msg_id, "reply_markup": m1},
        )
        # Edit text only — keyboard from the previous edit must remain.
        resp = http.post(
            f"/bot{bot_token}/editMessageText",
            headers=headers,
            json={"chat_id": 12345, "message_id": msg_id, "text": "kept"},
        )
        result = resp.json()["result"]
        assert result["text"] == "kept"
        assert result["reply_markup"] == m1

    def test_recorded_with_message_id(self, http, bot_token, headers, session_id):
        msg_id = _send_with_keyboard(http, bot_token, headers, [("A", "a")])
        new_markup = {"inline_keyboard": [[{"text": "B", "callback_data": "b"}]]}
        http.post(
            f"/bot{bot_token}/editMessageReplyMarkup",
            headers=headers,
            json={"chat_id": 12345, "message_id": msg_id, "reply_markup": new_markup},
        )
        responses = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        ).json()["responses"]
        rec = [r for r in responses if r["method"] == "editMessageReplyMarkup"][-1]
        assert rec["message_id"] == msg_id
        assert rec["reply_markup"] == new_markup

    def test_unknown_message_id_soft_fallback(self, http, bot_token, headers):
        """Unknown id → schema-valid synthetic Message (default, non-strict)."""
        resp = http.post(
            f"/bot{bot_token}/editMessageReplyMarkup",
            headers=headers,
            json={
                "chat_id": 12345,
                "message_id": 999999,
                "reply_markup": {"inline_keyboard": [[{"text": "x", "callback_data": "x"}]]},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["result"]["message_id"] == 999999


class TestEditMessageCaption:
    """POST /bot{token}/editMessageCaption."""

    def test_edit_caption_returns_new_caption(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/sendPhoto",
            headers=headers,
            data={"chat_id": "12345", "caption": "before"},
        )
        msg_id = resp.json()["result"]["message_id"]
        resp = http.post(
            f"/bot{bot_token}/editMessageCaption",
            headers=headers,
            json={"chat_id": 12345, "message_id": msg_id, "caption": "after"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["caption"] == "after"
        responses = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        ).json()["responses"]
        assert any(r["method"] == "editMessageCaption" for r in responses)


class TestDeleteMessage:
    """POST /bot{token}/deleteMessage."""

    def test_delete_message(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/deleteMessage",
            headers=headers,
            json={"chat_id": 12345, "message_id": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["result"] is True

    def test_delete_recorded(self, http, bot_token, headers, session_id):
        http.post(
            f"/bot{bot_token}/deleteMessage",
            headers=headers,
            json={"chat_id": 12345, "message_id": 42},
        )
        resp = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        )
        responses = resp.json()["responses"]
        assert any(
            r["method"] == "deleteMessage"
            and r["message_id"] == 42
            and r["chat_id"] == 12345
            for r in responses
        )

    def test_delete_message_string_ids(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/deleteMessage",
            headers=headers,
            json={"chat_id": "12345", "message_id": "7"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] is True

        responses = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        ).json()["responses"]
        assert any(
            r["method"] == "deleteMessage"
            and r["chat_id"] == 12345
            and r["message_id"] == 7
            for r in responses
        )


class TestAnswerCallbackQuery:
    """POST /bot{token}/answerCallbackQuery."""

    def test_answer_callback(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/answerCallbackQuery",
            headers=headers,
            json={"callback_query_id": "12345", "text": "Done!"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_answer_callback_recorded(self, http, bot_token, headers, session_id):
        http.post(
            f"/bot{bot_token}/answerCallbackQuery",
            headers=headers,
            json={"callback_query_id": "12345"},
        )
        resp = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        )
        responses = resp.json()["responses"]
        assert any(r["method"] == "answerCallbackQuery" for r in responses)

    def test_records_text_and_show_alert(self, http, bot_token, headers, session_id):
        """Acceptance #2: text and show_alert surfaced as top-level fields."""
        http.post(
            f"/bot{bot_token}/answerCallbackQuery",
            headers=headers,
            json={
                "callback_query_id": "cq1",
                "text": "Готово!",
                "show_alert": True,
            },
        )
        responses = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        ).json()["responses"]
        rec = [r for r in responses if r["method"] == "answerCallbackQuery"][-1]
        assert rec["callback_query_id"] == "cq1"
        assert rec["text"] == "Готово!"
        assert rec["show_alert"] is True

    def test_show_alert_defaults_false(self, http, bot_token, headers, session_id):
        http.post(
            f"/bot{bot_token}/answerCallbackQuery",
            headers=headers,
            json={"callback_query_id": "cq2", "text": "toast"},
        )
        responses = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        ).json()["responses"]
        rec = [r for r in responses if r["method"] == "answerCallbackQuery"][-1]
        assert rec["show_alert"] is False

    def test_empty_body(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/answerCallbackQuery",
            headers=headers,
            json={},
        )
        assert resp.status_code == 200
