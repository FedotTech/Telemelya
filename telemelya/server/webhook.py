"""Webhook delivery: POST Update to bot's webhook URL."""

from __future__ import annotations

import logging

import aiohttp

from telemelya.server.state import state_manager

logger = logging.getLogger(__name__)


async def deliver_update(token: str, update: dict) -> dict:
    """Send update to the bot's registered webhook URL.

    Returns a dict with delivery status and details.
    """
    webhook_url = await state_manager.get_webhook(token)
    if not webhook_url:
        return {
            "delivered": False,
            "error": f"No webhook registered for token {token!r}",
        }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=update,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                status = resp.status
                body = await resp.text()
                logger.info(
                    "Webhook delivery to %s: status=%d", webhook_url, status
                )
                return {
                    "delivered": True,
                    "status_code": status,
                    "response_body": body,
                }
    except Exception as exc:
        logger.error("Webhook delivery failed: %s", exc)
        return {"delivered": False, "error": str(exc)}
