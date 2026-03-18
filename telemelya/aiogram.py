"""
Telemelya aiogram adapter — run the same bot code in production and test modes.

Usage:

    from aiogram import Dispatcher, types
    from aiogram.filters import CommandStart
    from telemelya.aiogram import TemelyaRunner

    dp = Dispatcher()

    @dp.message(CommandStart())
    async def handle_start(message: types.Message):
        await message.answer("Hello!")

    @dp.message()
    async def handle_echo(message: types.Message):
        await message.answer(message.text or "")

    if __name__ == "__main__":
        runner = TemelyaRunner(dp)
        runner.run()

Mode selection (BOT_RUN_MODE=auto, default):

    +---------------------+------------------+---------------------------+
    | TELEMELYA_URL       | WEBHOOK_URL      | Result                    |
    +---------------------+------------------+---------------------------+
    | set                 | (any)            | webhook -> mock server    |
    | empty               | set              | webhook -> real Telegram  |
    | empty               | empty            | polling <- real Telegram  |
    +---------------------+------------------+---------------------------+

    Override with BOT_RUN_MODE=polling or BOT_RUN_MODE=webhook.

Typical usage scenarios:

    # Test (Telemelya mock server):
    TELEMELYA_URL=http://mock-server:8080 python bot.py

    # Production (webhook on server):
    BOT_TOKEN=real:token WEBHOOK_URL=https://bot.example.com python bot.py

    # Local dev / debug (polling):
    BOT_TOKEN=real:token python bot.py
    BOT_TOKEN=real:token PROXY_URL=http://127.0.0.1:12334 python bot.py

Environment variables:

    BOT_TOKEN          — Telegram bot token (required in production).
    TELEMELYA_URL      — Mock server URL. If set -> test mode (webhook to mock).
    PROXY_URL          — HTTP/SOCKS proxy for outgoing requests (production).
    WEBHOOK_URL        — Public URL for webhook (production webhook mode).
    WEBHOOK_HOST       — Host to bind webhook server (default: 0.0.0.0).
    WEBHOOK_PORT       — Port to bind webhook server (default: 8081).
    BOT_RUN_MODE       — Force mode: "polling", "webhook", or "auto" (default).
"""

from __future__ import annotations

import asyncio
import logging
import os
from enum import Enum
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

logger = logging.getLogger("telemelya.aiogram")


class RunMode(str, Enum):
    """Bot run mode."""

    AUTO = "auto"
    POLLING = "polling"
    WEBHOOK = "webhook"


def create_bot(
    token: Optional[str] = None,
    *,
    mock_url: Optional[str] = None,
    proxy: Optional[str] = None,
) -> Bot:
    """Create an aiogram Bot configured for production or test mode.

    Args:
        token: Bot token. Falls back to BOT_TOKEN env var.
        mock_url: Telemelya server URL. Falls back to TELEMELYA_URL env var.
                  If set, bot will target the mock server instead of Telegram.
        proxy: HTTP/SOCKS proxy URL. Falls back to PROXY_URL env var.
               Only used in production mode.

    Returns:
        Configured aiogram Bot instance.
    """
    token = token or os.environ.get("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("Bot token is required (pass token= or set BOT_TOKEN)")

    mock_url = mock_url or os.environ.get("TELEMELYA_URL", "")

    if mock_url:
        logger.info("Test mode: targeting mock server at %s", mock_url)
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(mock_url),
        )
        return Bot(token=token, session=session)

    proxy = proxy or os.environ.get("PROXY_URL", "")
    if proxy:
        logger.info("Production mode with proxy: %s", proxy)
        session = AiohttpSession(proxy=proxy)
        return Bot(token=token, session=session)

    logger.info("Production mode (direct connection)")
    return Bot(token=token)


class TemelyaRunner:
    """Runs an aiogram Dispatcher in the appropriate mode.

    Automatically detects whether to use Telemelya (test) or real Telegram (production)
    based on the TELEMELYA_URL environment variable.

    Args:
        dp: aiogram Dispatcher with registered handlers.
        bot: Pre-configured Bot instance. If None, created via create_bot().
        token: Bot token (used only if bot is None).
        mock_url: Override TELEMELYA_URL for test mode.
        proxy: Override PROXY_URL for production mode.
        mode: Force a specific run mode (auto/polling/webhook).
        webhook_url: Public webhook URL (production webhook mode).
        webhook_host: Host to bind the webhook server (default: 0.0.0.0).
        webhook_port: Port to bind the webhook server (default: 8081).
        webhook_path: URL path for webhook endpoint (default: /webhook).
    """

    def __init__(
        self,
        dp: Dispatcher,
        *,
        bot: Optional[Bot] = None,
        token: Optional[str] = None,
        mock_url: Optional[str] = None,
        proxy: Optional[str] = None,
        mode: Optional[RunMode] = None,
        webhook_url: Optional[str] = None,
        webhook_host: Optional[str] = None,
        webhook_port: Optional[int] = None,
        webhook_path: str = "/webhook",
    ):
        self.dp = dp
        self.bot = bot or create_bot(token, mock_url=mock_url, proxy=proxy)
        self._mock_url = mock_url or os.environ.get("TELEMELYA_URL", "")
        self._mode = mode or RunMode(
            os.environ.get("BOT_RUN_MODE", "auto").lower()
        )
        self._webhook_url = webhook_url or os.environ.get("WEBHOOK_URL", "")
        self._webhook_host = webhook_host or os.environ.get(
            "WEBHOOK_HOST", "0.0.0.0"
        )
        self._webhook_port = webhook_port or int(
            os.environ.get("WEBHOOK_PORT", "8081")
        )
        self._webhook_path = webhook_path

    @property
    def is_test_mode(self) -> bool:
        """True if running against Telemelya mock server."""
        return bool(self._mock_url)

    @property
    def effective_mode(self) -> RunMode:
        """Determine which mode will actually be used.

        AUTO logic (default):
          - TELEMELYA_URL set   → webhook (to mock server, test mode)
          - WEBHOOK_URL set    → webhook (to real Telegram, production)
          - neither set        → polling (local development / debug)

        Explicit BOT_RUN_MODE=polling or webhook overrides auto-detection.
        """
        if self._mode == RunMode.POLLING:
            return RunMode.POLLING
        if self._mode == RunMode.WEBHOOK:
            return RunMode.WEBHOOK
        # AUTO: test → webhook to mock, WEBHOOK_URL → webhook to Telegram,
        #       otherwise → polling (local dev / debug)
        if self.is_test_mode:
            return RunMode.WEBHOOK
        if self._webhook_url:
            return RunMode.WEBHOOK
        return RunMode.POLLING

    def run(self) -> None:
        """Start the bot (blocking). Entry point for scripts."""
        asyncio.run(self.start())

    async def start(self) -> None:
        """Start the bot (async)."""
        mode = self.effective_mode
        logger.info(
            "Starting bot: mode=%s, test=%s", mode.value, self.is_test_mode
        )
        if mode == RunMode.POLLING:
            await self._run_polling()
        else:
            await self._run_webhook()

    async def _run_polling(self) -> None:
        """Run in long-polling mode (production)."""
        await self.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot started in polling mode")
        await self.dp.start_polling(self.bot)

    async def _run_webhook(self) -> None:
        """Run as webhook server (test mode or production with webhook)."""
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import (
            SimpleRequestHandler,
            setup_application,
        )

        # Determine the full webhook URL to register
        if self.is_test_mode:
            # In test mode, figure out the right hostname for the mock server
            # to reach this webhook. If mock is in Docker, use host.docker.internal.
            wh_host = self._webhook_host
            if wh_host == "0.0.0.0":
                # Mock server in Docker can't reach 0.0.0.0;
                # try host.docker.internal for Docker Desktop, else localhost.
                wh_host = os.environ.get(
                    "WEBHOOK_EXTERNAL_HOST", "host.docker.internal"
                )
            webhook_full = (
                f"http://{wh_host}:{self._webhook_port}"
                f"{self._webhook_path}"
            )
        else:
            webhook_full = f"{self._webhook_url}{self._webhook_path}"

        # Register startup hook to set webhook
        async def _on_startup(bot: Bot, **kwargs):
            logger.info("Setting webhook: %s", webhook_full)
            await bot.set_webhook(webhook_full)
            info = await bot.get_webhook_info()
            logger.info(
                "Webhook active: url=%s, pending=%d",
                info.url,
                info.pending_update_count,
            )

        self.dp.startup.register(_on_startup)

        # Build aiohttp app
        app = web.Application()
        handler = SimpleRequestHandler(dispatcher=self.dp, bot=self.bot)
        handler.register(app, path=self._webhook_path)
        setup_application(app, self.dp, bot=self.bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self._webhook_host, self._webhook_port)
        logger.info(
            "Webhook server listening on %s:%d",
            self._webhook_host,
            self._webhook_port,
        )
        await site.start()
        await asyncio.Event().wait()


# Backward-compatibility alias
TeremockRunner = TemelyaRunner
