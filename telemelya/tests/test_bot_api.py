"""Tests for Bot API recording endpoints: sendMessage, sendPhoto, editMessageText, answerCallbackQuery."""

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


class TestEditMessageText:
    """POST /bot{token}/editMessageText."""

    def test_edit_message(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/editMessageText",
            headers=headers,
            json={
                "chat_id": 12345,
                "message_id": 1,
                "text": "Edited text",
            },
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["text"] == "Edited text"
        assert result["message_id"] == 1

    def test_edit_recorded(self, http, bot_token, headers, session_id):
        http.post(
            f"/bot{bot_token}/editMessageText",
            headers=headers,
            json={"chat_id": 12345, "message_id": 1, "text": "New text"},
        )
        resp = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        )
        responses = resp.json()["responses"]
        assert any(r["method"] == "editMessageText" for r in responses)


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

    def test_empty_body(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/answerCallbackQuery",
            headers=headers,
            json={},
        )
        assert resp.status_code == 200
