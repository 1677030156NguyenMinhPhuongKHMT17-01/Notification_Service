"""Channel delivery adapters (safe stdout mock by default + optional webhooks).

By default, every channel writes a structured log line to stdout (visible via
`docker logs`) so the stack stays secretless and deterministic. When optional
webhook environment variables (`DISCORD_WEBHOOK_URL` or `TELEGRAM_BOT_TOKEN` +
`TELEGRAM_CHAT_ID`) are configured, stdlib `urllib.request` dispatches real
messages with a <= 5s timeout. `FAIL_CHANNELS` is always evaluated first so
fault-injection and unit tests stay deterministic.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Iterable, List, Tuple
from urllib.parse import urlparse

from .config import settings

logger = logging.getLogger("notification.delivery")


class ChannelDeliveryError(RuntimeError):
    pass


def _post_json(url: str, payload: dict, timeout: float, label: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ChannelDeliveryError(f"{label} webhook URL must use http/https")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"{settings.service_name}/{settings.service_version}",
        },
        method="POST",
    )
    effective_timeout = max(0.1, min(timeout, 5.0))
    try:
        with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
            status_code = getattr(resp, "status", 200)
            if status_code >= 400:
                raise ChannelDeliveryError(f"{label} webhook returned HTTP {status_code}")
    except urllib.error.HTTPError as exc:
        raise ChannelDeliveryError(f"{label} webhook returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", type(exc).__name__)
        raise ChannelDeliveryError(f"{label} webhook failed: {reason}") from exc


def send_to_channel(channel: str, alert_id: str, message: str, correlation_id: str) -> None:
    if channel in settings.fail_channels:
        raise ChannelDeliveryError(f"{channel} gateway unavailable (simulated by FAIL_CHANNELS)")

    timeout = settings.webhook_timeout_seconds
    if channel == "discord" and settings.discord_webhook_url:
        _post_json(
            settings.discord_webhook_url,
            {"content": f"[{alert_id}] ({correlation_id}) {message}"},
            timeout,
            "discord",
        )
        logger.info("channel=discord alert_id=%s correlationId=%s delivered via webhook", alert_id, correlation_id)
        return

    if channel == "telegram" and settings.telegram_bot_token and settings.telegram_chat_id:
        telegram_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        _post_json(
            telegram_url,
            {"chat_id": settings.telegram_chat_id, "text": f"[{alert_id}] ({correlation_id}) {message}"},
            timeout,
            "telegram",
        )
        logger.info("channel=telegram alert_id=%s correlationId=%s delivered via webhook", alert_id, correlation_id)
        return

    logger.info(
        "channel=%s alert_id=%s correlationId=%s delivered message=%r",
        channel,
        alert_id,
        correlation_id,
        message,
    )


def deliver_all(channels: Iterable[str], alert_id: str, message: str, correlation_id: str) -> Tuple[bool, List[str]]:
    """Send to every channel. Returns (all_ok, list_of_error_messages)."""
    errors: List[str] = []
    for channel in channels:
        try:
            send_to_channel(channel, alert_id, message, correlation_id)
        except ChannelDeliveryError as exc:
            logger.warning("channel=%s alert_id=%s correlationId=%s failed: %s", channel, alert_id, correlation_id, exc)
            errors.append(str(exc))
    return (not errors, errors)

