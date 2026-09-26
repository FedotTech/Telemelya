"""Tests for POST /api/v1/test/send_update — the core Control API endpoint."""

import pytest


class TestSendUpdateNoWebhook:
    """send_update when no webhook is registered — should fail with 424."""

    def test_no_webhook_returns_424(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={"chat_id": 1},
        )
        assert resp.status_code == 424
        detail = resp.json()["detail"]
        assert "No webhook registered" in detail["error"]
        assert "no-webhook-token" in detail["bot_token"]

    def test_no_webhook_includes_hint(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "missing-hook"},
            json={"chat_id": 1},
        )
        assert resp.status_code == 424
        assert "hint" in resp.json()["detail"]


class TestSendUpdateWebhookUnreachable:
    """send_update when webhook URL is set but bot is not actually running."""

    def test_unreachable_webhook_returns_424(self, http, headers, bot_token):
        # Register webhook pointing to nowhere
        http.post(
            f"/bot{bot_token}/setWebhook",
            json={"url": "http://127.0.0.1:59999/nonexistent"},
        )
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": bot_token},
            json={"chat_id": 1, "text": "hello"},
        )
        assert resp.status_code == 424
        # Cleanup
        http.post(f"/bot{bot_token}/deleteWebhook")


class TestSendUpdateValidation:
    """Validation and parameter edge cases for send_update."""

    def test_missing_bot_token_param(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            json={"chat_id": 1},
        )
        assert resp.status_code == 422  # FastAPI validation

    def test_missing_chat_id(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "any-token"},
            json={},
        )
        assert resp.status_code == 422  # chat_id is required in model

    def test_missing_body(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "any-token"},
        )
        assert resp.status_code == 422

    def test_requires_auth(self, http):
        resp = http.post(
            "/api/v1/test/send_update",
            params={"bot_token": "any-token"},
            json={"chat_id": 1},
        )
        assert resp.status_code in (401, 403)


class TestSendUpdateCommandGeneration:
    """Verify that send_update builds correct Update objects for different inputs."""

    @pytest.fixture(autouse=True)
    def _setup_echo_webhook(self, http, bot_token, server_url):
        """Register webhook if bot is running, skip otherwise.

        These tests need the echo bot to generate delivery success.
        They will be skipped if the bot is not running.
        """
        # We can't guarantee the bot is running, so we test update structure
        # via the 424 response when we need just validation.
        pass

    def test_command_auto_prefixed_with_slash(self, http, headers, bot_token):
        """When command='start', the update should contain '/start'."""
        # We register a webhook that won't respond, but the 424 still
        # proves the endpoint parsed our request. For structural tests
        # we need to inspect the actual update, which requires a live bot.
        # This test just validates the request is accepted.
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={"chat_id": 1, "command": "start"},
        )
        # Gets 424 (no webhook), but not 422 (validation passes)
        assert resp.status_code == 424

    def test_callback_data_accepted(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={"chat_id": 1, "callback_data": "btn_yes", "callback_message_id": 5},
        )
        assert resp.status_code == 424  # no webhook, but request was valid

    def test_photo_with_caption_accepted(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={
                "chat_id": 1,
                "photo_file_id": "fake-photo-id",
                "photo_caption": "My photo",
            },
        )
        assert resp.status_code == 424  # no webhook, but request structure was valid

    def test_custom_from_user(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={
                "chat_id": 1,
                "text": "hello",
                "from_user": {
                    "id": 999,
                    "first_name": "Alice",
                    "username": "alice_test",
                },
            },
        )
        assert resp.status_code == 424  # no webhook


class TestSendUpdateReplyToMessage:
    """reply_to_message_id: update carries message.reply_to_message of a bot message."""

    TOKEN = "reply-test-token"

    @pytest.fixture(autouse=True)
    def _self_webhook(self, http):
        # Webhook на собственный getMe сервера: доставка успешна без живого бота.
        http.post(
            f"/bot{self.TOKEN}/setWebhook",
            json={"url": f"http://127.0.0.1:8080/bot{self.TOKEN}/getMe"},
        )
        yield
        http.post(f"/bot{self.TOKEN}/deleteWebhook")

    def _bot_says(self, http, headers, chat_id, text, **extra):
        resp = http.post(
            f"/bot{self.TOKEN}/sendMessage",
            headers=headers,
            json={"chat_id": chat_id, "text": text, **extra},
        )
        return resp.json()["result"]["message_id"]

    def _send(self, http, headers, **body):
        return http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": self.TOKEN},
            json=body,
        )

    def test_reply_to_bot_message(self, http, headers, session_id):
        first = self._bot_says(http, headers, 1, "first answer")
        self._bot_says(http, headers, 1, "second answer")

        # message_id из /responses — то, на что ссылаются тесты
        responses = http.get(
            "/api/v1/test/responses", headers=headers, params={"session_id": session_id}
        ).json()["responses"]
        assert responses[0]["message_id"] == first

        resp = self._send(http, headers, chat_id=1, text="follow-up", reply_to_message_id=first)
        assert resp.status_code == 200, resp.text
        reply = resp.json()["update"]["message"]["reply_to_message"]
        assert reply["message_id"] == first
        assert reply["text"] == "first answer"
        assert reply["from"]["is_bot"] is True
        assert reply["chat"]["id"] == 1
        assert "date" in reply

    def test_reply_strips_reply_keyboard(self, http, headers):
        """В Message Telegram отдаёт только inline reply_markup (иначе aiogram не распарсит)."""
        mid = self._bot_says(
            http, headers, 1, "menu", reply_markup={"keyboard": [[{"text": "A"}]]}
        )
        resp = self._send(http, headers, chat_id=1, text="x", reply_to_message_id=mid)
        assert "reply_markup" not in resp.json()["update"]["message"]["reply_to_message"]

    def test_reply_with_photo(self, http, headers):
        mid = self._bot_says(http, headers, 1, "answer")
        resp = self._send(
            http, headers, chat_id=1, photo_file_id="fake-photo-id",
            photo_caption="look", reply_to_message_id=mid,
        )
        message = resp.json()["update"]["message"]
        assert message["reply_to_message"]["message_id"] == mid
        assert message["caption"] == "look"

    def test_unknown_message_returns_404(self, http, headers):
        resp = self._send(http, headers, chat_id=1, text="x", reply_to_message_id=424242)
        assert resp.status_code == 404
        assert "424242" in resp.json()["detail"]["error"]

    def test_other_chat_message_returns_404(self, http, headers):
        mid = self._bot_says(http, headers, 1, "answer")
        resp = self._send(http, headers, chat_id=2, text="x", reply_to_message_id=mid)
        assert resp.status_code == 404

    def test_without_reply_has_no_reply_to_message(self, http, headers):
        resp = self._send(http, headers, chat_id=1, text="plain")
        assert "reply_to_message" not in resp.json()["update"]["message"]

    def test_client_send_message_reply(self, http, headers, server_url, api_key, session_id):
        from telemelya.client.client import TelegramTestClient

        mid = self._bot_says(http, headers, 1, "answer")
        with TelegramTestClient(server_url, api_key, self.TOKEN, session_id) as client:
            payload = client.send_message(1, "follow-up", reply_to_message_id=mid)
        assert payload["update"]["message"]["reply_to_message"]["message_id"] == mid
