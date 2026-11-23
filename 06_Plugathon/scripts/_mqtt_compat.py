"""Shared MQTT helper for Lab 06 Plug-a-thon scripts.

Reuses the canonical stdlib/paho-mqtt helper in `../05_Compose/scripts/_mqtt_compat.py`
without duplicating wire-protocol code, and disables bytecode emission during import
so running host scripts never pollutes `05_Compose/scripts/__pycache__/`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL_COMPAT = (
    Path(__file__).resolve().parents[2] / "05_Compose" / "scripts" / "_mqtt_compat.py"
)

if not _CANONICAL_COMPAT.is_file():  # pragma: no cover
    raise ImportError(f"Canonical MQTT compat helper not found: {_CANONICAL_COMPAT}")

_prev_dont_write = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    _spec = importlib.util.spec_from_file_location("_lab05_mqtt_compat", _CANONICAL_COMPAT)
    if _spec is None or _spec.loader is None:  # pragma: no cover
        raise ImportError(f"Could not load spec for {_CANONICAL_COMPAT}")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
finally:
    sys.dont_write_bytecode = _prev_dont_write

parse_broker_url = _mod.parse_broker_url
publish_once = _mod.publish_once
subscribe_loop = _mod.subscribe_loop

__all__ = ["parse_broker_url", "publish_once", "subscribe_loop"]
