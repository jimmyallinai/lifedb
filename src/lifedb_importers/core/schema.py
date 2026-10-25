"""Unified record schema (lifedb canonical JSONL, one record per message).

Fields
------
id              stable id: "sha256:" + sha256(platform + US + source message id)
platform        e.g. "chatgpt", "doubao"
source          importer name, e.g. "chatgpt-export"
conversation_id platform-native conversation id (string)
conversation_title  conversation title if the platform provides one, else None
message_id      platform-native message id (string)
role            "user" | "assistant" | "system" | "tool" | "unknown" | ...
text            visible text of the message (verbatim)
created_at      ISO 8601 with timezone, or None
month           "YYYY-MM" derived from created_at, or "unknown" (shard key)
branch          branch suffix (16 hex chars) if the message sits on a
                non-active branch of the conversation tree, else None
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

RECORD_FIELDS = (
    "id", "platform", "source", "conversation_id", "conversation_title",
    "message_id", "role", "text", "created_at", "month", "branch",
)


def stable_id(platform: str, source_message_id: str) -> str:
    """Stable record id = hash of platform + source-internal id (v3 spec)."""
    digest = hashlib.sha256(f"{platform}\x1f{source_message_id}".encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def iso_from_epoch(value) -> str | None:
    """Normalize epoch seconds/ms/us/ns (number or numeric string) to ISO 8601 UTC."""
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1e17:
        number /= 1e9
    elif number > 1e14:
        number /= 1e6
    elif number > 1e11:
        number /= 1e3
    if not (946684800 <= number <= 4102444800):  # 2000-01-01 .. 2100-01-01
        return None
    return datetime.fromtimestamp(number, tz=timezone.utc).isoformat()


def normalize_time(value) -> str | None:
    """Accept epoch values or ISO strings; return ISO 8601 or None."""
    if isinstance(value, str) and value and not value.replace(".", "").isdigit():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return iso_from_epoch(value)


def month_of(created_at: str | None) -> str:
    return created_at[:7] if created_at else "unknown"


def make_record(*, platform: str, source: str, conversation_id: str,
                conversation_title, message_id: str, role: str, text: str,
                created_at, branch=None) -> dict:
    created = normalize_time(created_at)
    return {
        "id": stable_id(platform, message_id),
        "platform": platform,
        "source": source,
        "conversation_id": str(conversation_id),
        "conversation_title": conversation_title,
        "message_id": str(message_id),
        "role": role or "unknown",
        "text": text,
        "created_at": created,
        "month": month_of(created),
        "branch": branch,
    }


def validate_record(record: dict) -> None:
    missing = [f for f in RECORD_FIELDS if f not in record]
    if missing:
        raise ValueError(f"record missing fields: {missing}")
    if not record["id"].startswith("sha256:"):
        raise ValueError("record id must be a sha256 stable id")


def dump_record(record: dict) -> str:
    """Canonical serialization: sorted keys -> byte-identical reruns."""
    return json.dumps(record, ensure_ascii=False, sort_keys=True)
