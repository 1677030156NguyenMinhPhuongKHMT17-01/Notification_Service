"""Mock delivery channels.

Lab 04 only requires channel mocks (no real Telegram/e-mail token may be
committed). Each sender writes a structured log line to stdout, which is
visible with `docker logs`. A channel listed in FAIL_CHANNELS raises an
error so the retry -> DLQ path can be demonstrated on demand.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Tuple

from .config import settings

logger = logging.getLogger("notification.delivery")


class ChannelDeliveryError(RuntimeError):
    pass


def send_to_channel(channel: str, alert_id: str, message: str, correlation_id: str) -> None:
    if channel in settings.fail_channels:
        raise ChannelDeliveryError(f"{channel} gateway unavailable (simulated by FAIL_CHANNELS)")
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

