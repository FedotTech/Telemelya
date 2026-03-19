"""Integration test script for Telemelya + echo bot."""

import sys
import time

from telemelya.client.client import TelegramTestClient
from telemelya.client.collector import ResponseCollector


SERVER_URL = "http://127.0.0.1:8080"
API_KEY = "test-api-key-12345"
BOT_TOKEN = "123456789:ABCDefGhIjKlMnOpQrStUvWxYz"

passed = 0
failed = 0


def run_test(name, func):
    global passed, failed
    try:
        func()
        print(f"  PASS: {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {name} — {e}")
        failed += 1


def test_health():
    client = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
    resp = client._client.get("/api/v1/test/health")
    data = resp.json()
    assert data["ok"], f"Health check failed: {data}"
    assert data["redis"] == "ok"
    assert data["minio"] == "ok"
    client.close()


def test_start_command():
    client = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
    collector = ResponseCollector(client)
    try:
        client.send_command(chat_id=12345, command="/start")
        time.sleep(1)
        collector.wait_for_response(timeout=5.0)
        collector.assert_text("Добро пожаловать!")
    finally:
        client.reset()
        client.close()


def test_echo_message():
    client = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
    collector = ResponseCollector(client)
    try:
        client.send_message(chat_id=12345, text="Привет, бот!")
        time.sleep(1)
        collector.wait_for_response(timeout=5.0)
        collector.assert_text("Привет, бот!")
    finally:
        client.reset()
        client.close()


def test_echo_english():
    client = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
    collector = ResponseCollector(client)
    try:
        client.send_message(chat_id=99999, text="Hello world")
        time.sleep(1)
        collector.wait_for_response(timeout=5.0)
        collector.assert_text("Hello world")
    finally:
        client.reset()
        client.close()


def test_session_isolation():
    client1 = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
    client2 = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
    try:
        client1.send_message(chat_id=11111, text="msg1")
        time.sleep(1)
        client2.send_message(chat_id=22222, text="msg2")
        time.sleep(1)

        responses1 = client1.get_responses()
        responses2 = client2.get_responses()

        assert len(responses1) >= 1, f"Expected >=1 response for client1, got {len(responses1)}"
        assert len(responses2) >= 1, f"Expected >=1 response for client2, got {len(responses2)}"
        assert responses1[0]["text"] == "msg1", f"Client1 got wrong text: {responses1[0]['text']}"
        assert responses2[0]["text"] == "msg2", f"Client2 got wrong text: {responses2[0]['text']}"
    finally:
        client1.reset()
        client2.reset()
        client1.close()
        client2.close()


def test_auth_required():
    """Verify that requests without auth are rejected."""
    import httpx
    resp = httpx.get(f"{SERVER_URL}/api/v1/test/health")
    assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


def test_reset():
    client = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
    try:
        client.send_message(chat_id=12345, text="before reset")
        time.sleep(1)
        responses_before = client.get_responses()
        assert len(responses_before) >= 1

        client.reset()
        responses_after = client.get_responses()
        assert len(responses_after) == 0, f"Expected 0 after reset, got {len(responses_after)}"
    finally:
        client.close()


def test_multiple_responses():
    client = TelegramTestClient(SERVER_URL, API_KEY, BOT_TOKEN)
    try:
        client.send_message(chat_id=33333, text="one")
        time.sleep(1)
        client.send_message(chat_id=33333, text="two")
        time.sleep(1)

        responses = client.get_responses()
        assert len(responses) >= 2, f"Expected >=2 responses, got {len(responses)}"
        texts = [r["text"] for r in responses]
        assert "one" in texts, f"'one' not found in {texts}"
        assert "two" in texts, f"'two' not found in {texts}"
    finally:
        client.reset()
        client.close()


if __name__ == "__main__":
    print("\n=== Telemelya Integration Tests ===\n")

    run_test("Health check", test_health)
    run_test("Auth required", test_auth_required)
    run_test("/start command", test_start_command)
    run_test("Echo message (Russian)", test_echo_message)
    run_test("Echo message (English)", test_echo_english)
    run_test("Session isolation", test_session_isolation)
    run_test("Reset session", test_reset)
    run_test("Multiple responses", test_multiple_responses)

    print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
    sys.exit(1 if failed else 0)
