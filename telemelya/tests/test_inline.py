"""Tests for inline-mode: answerInlineQuery recording + choose_inline_result.

These hit the Bot API / Control API directly (no live bot needed). The full
"button → inline → message from bot" round-trip lives in the echo_bot e2e tests.
"""

import pytest


def _article_results():
    return [
        {
            "type": "article",
            "id": "res-1",
            "title": "Поделиться консультацией",
            "input_message_content": {"message_text": "Вот моя консультация!"},
            "reply_markup": {
                "inline_keyboard": [[{"text": "Открыть", "url": "https://example.com"}]]
            },
        },
        {
            "type": "article",
            "id": "res-2",
            "title": "Второй вариант",
            "input_message_content": {"message_text": "Другой текст"},
        },
    ]


class TestAnswerInlineQuery:
    """POST /bot{token}/answerInlineQuery."""

    def test_records_results(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/answerInlineQuery",
            headers=headers,
            json={"inline_query_id": "iq-1", "results": _article_results()},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        responses = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        ).json()["responses"]
        rec = [r for r in responses if r["method"] == "answerInlineQuery"][-1]
        assert rec["inline_query_id"] == "iq-1"
        assert len(rec["results"]) == 2
        assert rec["results"][0]["title"] == "Поделиться консультацией"

    def test_empty_results(self, http, bot_token, headers):
        resp = http.post(
            f"/bot{bot_token}/answerInlineQuery",
            headers=headers,
            json={"inline_query_id": "iq-empty", "results": []},
        )
        assert resp.status_code == 200


class TestChooseInlineResult:
    """POST /api/v1/test/choose_inline_result — mechanism A (emulated post)."""

    def _record_answer(self, http, bot_token, headers, qid="iq-c"):
        http.post(
            f"/bot{bot_token}/answerInlineQuery",
            headers=headers,
            json={"inline_query_id": qid, "results": _article_results()},
        )
        return qid

    def test_choose_posts_message_from_bot(self, http, bot_token, headers, session_id):
        qid = self._record_answer(http, bot_token, headers)
        resp = http.post(
            "/api/v1/test/choose_inline_result",
            headers=headers,
            params={"bot_token": bot_token},
            json={"chat_id": 555, "inline_query_id": qid, "result_id": "res-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["message_id"]

        responses = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        ).json()["responses"]
        posted = [r for r in responses if r.get("via_inline")]
        assert posted, "Expected a message posted via inline choice"
        assert posted[-1]["text"] == "Вот моя консультация!"
        assert posted[-1]["chat_id"] == 555
        assert posted[-1]["message_id"] == data["message_id"]

    def test_choose_by_index(self, http, bot_token, headers, session_id):
        qid = self._record_answer(http, bot_token, headers, qid="iq-idx")
        resp = http.post(
            "/api/v1/test/choose_inline_result",
            headers=headers,
            params={"bot_token": bot_token},
            json={"chat_id": 1, "inline_query_id": qid, "result_index": 1},
        )
        assert resp.json()["chosen"]["id"] == "res-2"

    def test_choose_without_answer_conflicts(self, http, bot_token, headers, session_id):
        """No prior answerInlineQuery → 409 (masking-bug guard)."""
        resp = http.post(
            "/api/v1/test/choose_inline_result",
            headers=headers,
            params={"bot_token": bot_token},
            json={"chat_id": 1, "inline_query_id": "never-answered"},
        )
        assert resp.status_code == 409

    def test_choose_unknown_result_id(self, http, bot_token, headers):
        qid = self._record_answer(http, bot_token, headers, qid="iq-unknown")
        resp = http.post(
            "/api/v1/test/choose_inline_result",
            headers=headers,
            params={"bot_token": bot_token},
            json={"chat_id": 1, "inline_query_id": qid, "result_id": "nope"},
        )
        assert resp.status_code == 404
