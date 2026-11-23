"""Verify byte-for-byte SHA-256 parity of Lab 06 frozen contracts against canonical sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

LAB06_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = LAB06_DIR.parent

FROZEN_CONTRACT_SOURCES: List[Tuple[str, Path]] = [
    (
        "notification.openapi.yaml",
        REPO_ROOT / "05_Compose" / "contracts" / "notification.openapi.yaml",
    ),
    (
        "core-business.openapi.yaml",
        REPO_ROOT / "05_Compose" / "contracts" / "core-business.openapi.yaml",
    ),
    (
        "event-contract.md",
        REPO_ROOT / "03_Postman" / "queue-contract-tests" / "pair-04-core-notification" / "event-contract.md",
    ),
    (
        "producer-consumer-handshake.md",
        REPO_ROOT
        / "03_Postman"
        / "queue-contract-tests"
        / "pair-04-core-notification"
        / "producer-consumer-handshake.md",
    ),
    (
        "event-test-matrix.md",
        REPO_ROOT / "03_Postman" / "queue-contract-tests" / "pair-04-core-notification" / "event-test-matrix.md",
    ),
    (
        "schema/alert.created.schema.json",
        REPO_ROOT
        / "03_Postman"
        / "queue-contract-tests"
        / "pair-04-core-notification"
        / "schema"
        / "alert.created.schema.json",
    ),
    (
        "schema/alert.escalated.schema.json",
        REPO_ROOT
        / "03_Postman"
        / "queue-contract-tests"
        / "pair-04-core-notification"
        / "schema"
        / "alert.escalated.schema.json",
    ),
    (
        "schema/alert.resolved.schema.json",
        REPO_ROOT
        / "03_Postman"
        / "queue-contract-tests"
        / "pair-04-core-notification"
        / "schema"
        / "alert.resolved.schema.json",
    ),
    (
        "schema/campus.alerts.schema.json",
        REPO_ROOT
        / "03_Postman"
        / "queue-contract-tests"
        / "pair-04-core-notification"
        / "schema"
        / "campus.alerts.schema.json",
    ),
]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_openapi_version(text: str) -> str | None:
    match = re.search(r"(?m)^\s{2}version:\s*['\"]?([^'\"\r\n]+)['\"]?\s*$", text)
    return match.group(1).strip() if match else None


def verify_all() -> Tuple[bool, List[Dict[str, object]]]:
    contracts_dir = LAB06_DIR / "contracts"
    results: List[Dict[str, object]] = []
    all_ok = True

    for rel_path, canonical_path in FROZEN_CONTRACT_SOURCES:
        frozen_path = contracts_dir / rel_path
        entry: Dict[str, object] = {
            "contract": rel_path,
            "frozen_path": str(frozen_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "canonical_path": str(canonical_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "ok": False,
        }

        if not canonical_path.is_file():
            entry["error"] = "missing canonical source"
            all_ok = False
            results.append(entry)
            continue
        if not frozen_path.is_file():
            entry["error"] = "missing frozen copy"
            all_ok = False
            results.append(entry)
            continue

        canonical_bytes = canonical_path.read_bytes()
        frozen_bytes = frozen_path.read_bytes()
        canonical_sha = _sha256_bytes(canonical_bytes)
        frozen_sha = _sha256_bytes(frozen_bytes)

        entry["bytes"] = len(frozen_bytes)
        entry["sha256"] = frozen_sha

        if canonical_bytes != frozen_bytes or canonical_sha != frozen_sha:
            entry["error"] = f"hash mismatch (canonical={canonical_sha}, frozen={frozen_sha})"
            all_ok = False
            results.append(entry)
            continue

        if rel_path.endswith(".openapi.yaml"):
            version = _extract_openapi_version(frozen_bytes.decode("utf-8"))
            entry["openapi_version"] = version
            if version != "1.0.0":
                entry["error"] = f"expected info.version=1.0.0, got {version!r}"
                all_ok = False
                results.append(entry)
                continue

        if rel_path.endswith(".schema.json"):
            try:
                json.loads(frozen_bytes.decode("utf-8"))
            except json.JSONDecodeError as exc:
                entry["error"] = f"invalid JSON schema: {exc}"
                all_ok = False
                results.append(entry)
                continue

        entry["ok"] = True
        results.append(entry)

    return all_ok, results


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SHA-256 parity of Lab 06 frozen contracts")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    ok, results = verify_all()
    if args.json:
        print(json.dumps({"ok": ok, "contracts": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            tag = "PASS" if item["ok"] else "FAIL"
            if item["ok"]:
                extra = f" version={item['openapi_version']}" if "openapi_version" in item else ""
                print(
                    f"[{tag}] {item['contract']} ({item['bytes']} bytes, "
                    f"sha256={str(item['sha256'])[:16]}...){extra}"
                )
            else:
                print(f"[{tag}] {item['contract']}: {item.get('error')}")
        print(f"Summary: {sum(1 for r in results if r['ok'])}/{len(results)} frozen contracts verified")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
