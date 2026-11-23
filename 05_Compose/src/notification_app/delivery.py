"""Channel delivery adapters (safe stdout mock by default + optional webhooks).

By default, every channel writes a structured log line to stdout (visible via
`docker logs`) so the stack stays secretless and deterministic. When optional
webhook environment variables (`DISCORD_WEBHOOK_URL` or `TELEGRAM_BOT_TOKEN` +
`TELEGRAM_CHAT_ID`) are configured, stdlib `urllib.request` dispatches real
messages with a <= 5s timeout. `FAIL_CHANNELS` is always evaluated first so
fault-injection and unit tests stay deterministic.
"""

from __future__ import annotations

from collections import deque
import json
import logging
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Deque, FrozenSet, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from .config import settings
from .models import iso_utc

logger = logging.getLogger("notification.delivery")

DELIVERY_FEED_MAX = 80
_lock = threading.RLock()
fail_channels_override: Optional[FrozenSet[str]] = None
_delivery_feed: Deque[dict] = deque(maxlen=DELIVERY_FEED_MAX)


def get_fail_channels_override() -> Optional[FrozenSet[str]]:
    with _lock:
        return fail_channels_override


def set_fail_channels_override(channels: Optional[Iterable[str]]) -> Optional[FrozenSet[str]]:
    global fail_channels_override
    with _lock:
        if channels is None:
            fail_channels_override = None
        else:
            fail_channels_override = frozenset(
                item.strip().lower() for item in channels if item and item.strip()
            )
        return fail_channels_override


def effective_fail_channels() -> FrozenSet[str]:
    with _lock:
        if fail_channels_override is not None:
            return fail_channels_override
    return settings.fail_channels


def channel_mode(channel: str) -> str:
    if channel == "discord" and settings.discord_webhook_url:
        return "webhook"
    if channel == "telegram" and settings.telegram_bot_token and settings.telegram_chat_id:
        return "webhook"
    return "stdout_mock"


def get_delivery_feed() -> List[dict]:
    with _lock:
        return [dict(item) for item in _delivery_feed]


def delivery_feed_count() -> int:
    with _lock:
        return len(_delivery_feed)


def clear_delivery_feed() -> None:
    with _lock:
        _delivery_feed.clear()


def _record_delivery_feed(entry: dict) -> None:
    with _lock:
        _delivery_feed.appendleft(entry)


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
    started = time.perf_counter()
    mode = channel_mode(channel)
    ok = False
    error_msg: Optional[str] = None
    msg_text = message or ""
    try:
        if channel in effective_fail_channels():
            raise ChannelDeliveryError(f"{channel} gateway unavailable (simulated by FAIL_CHANNELS)")

        timeout = settings.webhook_timeout_seconds
        if channel == "discord" and settings.discord_webhook_url:
            _post_json(
                settings.discord_webhook_url,
                {"content": f"[{alert_id}] ({correlation_id}) {msg_text}"},
                timeout,
                "discord",
            )
            logger.info("channel=discord alert_id=%s correlationId=%s delivered via webhook", alert_id, correlation_id)
        elif channel == "telegram" and settings.telegram_bot_token and settings.telegram_chat_id:
            telegram_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            _post_json(
                telegram_url,
                {"chat_id": settings.telegram_chat_id, "text": f"[{alert_id}] ({correlation_id}) {msg_text}"},
                timeout,
                "telegram",
            )
            logger.info("channel=telegram alert_id=%s correlationId=%s delivered via webhook", alert_id, correlation_id)
        else:
            logger.info(
                "channel=%s alert_id=%s correlationId=%s delivered message=%r",
                channel,
                alert_id,
                correlation_id,
                msg_text,
            )
        ok = True
    except Exception as exc:
        error_msg = str(exc)[:500]
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        _record_delivery_feed(
            {
                "id": str(uuid.uuid4()),
                "timestamp": iso_utc(),
                "channel": channel,
                "alert_id": alert_id,
                "correlationId": correlation_id,
                "message": msg_text[:500],
                "mode": mode,
                "ok": ok,
                "error": error_msg,
                "duration_ms": duration_ms,
            }
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

