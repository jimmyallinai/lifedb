"""Doubao (豆包) file-entry importer.

Doubao conversations can be landed locally (in-app export / downloaded
data / an offline HAR capture). This importer parses the local file; it
never logs in and never calls the platform.

Primary format (VERIFIED): the offline HAR extractor's `chats.jsonl`
observed in the owner's 2026-10-20 capture pipeline — one JSON object per
line:
  {"id": "...", "title": "...", "created": <epoch|iso>,
   "messages": [{"role": "user"|"assistant"|"unknown", "text": "...",
                 "time": <epoch|iso>, "message_id": "...", ...}, ...],
   "coverage": "...", ...extra fields are ignored...}

Fallback format (GENERIC, not yet calibrated against a real Doubao
in-app export): a .json array of conversation objects, or
{"conversations": [...]}, whose messages use `text` or `content` and a
`time`/`create_time`/`created_at` timestamp.

Calibration status: BETA. The primary shape is verified against a real
12-conversation capture sample; full-history exports (larger message
volumes, user-role coverage) still need a real sample to calibrate.
Kimi is NOT handled here — see registry (planned, format undecided).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from ..core import schema
from ..core.base import Importer, NormalizeResult, PullResult


def _message_id(conv_id: str, message: dict, index: int) -> str:
    raw = message.get("message_id") or message.get("id")
    if raw:
        return str(raw)
    digest = hashlib.sha256(
        json.dumps([conv_id, index, message.get("text") or message.get("content") or ""],
                   ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:24]
    return f"derived:{digest}"


def _parse_conversations(data) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("conversations"), list):
        return data["conversations"]
    if isinstance(data, list):
        return data
    raise ValueError("unsupported doubao file shape")


def _load(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        conversations = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line:
                conversations.append(json.loads(line))
        return conversations
    return _parse_conversations(json.loads(path.read_text(encoding="utf-8-sig")))


def parse_conversation(conversation: dict) -> tuple[list[dict], int, int]:
    conv_id = str(conversation.get("id") or conversation.get("conversation_id") or "")
    if not conv_id:
        return [], 0, 0
    title = conversation.get("title") or conversation.get("name")
    title = title if isinstance(title, str) else None
    records: list[dict] = []
    seen = skipped = 0
    for index, message in enumerate(conversation.get("messages") or []):
        if not isinstance(message, dict):
            continue
        seen += 1
        text = message.get("text")
        if not isinstance(text, str):
            text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            skipped += 1
            continue
        records.append(schema.make_record(
            platform="doubao",
            source="doubao-file",
            conversation_id=conv_id,
            conversation_title=title,
            message_id=_message_id(conv_id, message, index),
            role=str(message.get("role") or "unknown"),
            text=text,
            created_at=(message.get("time") or message.get("create_time")
                        or message.get("created_at") or conversation.get("created")),
        ))
    return records, seen, skipped


class DoubaoFileImporter(Importer):
    name = "doubao-file"
    platform = "doubao"
    display_name = "豆包本地文件（HAR 提取 chats.jsonl / 通用 JSON）"
    entry_kind = "file"
    status = "beta"
    calibration = "primary chats.jsonl shape verified on a real capture sample; generic JSON fallback uncalibrated"

    def auth(self, *, source: str | None = None, **kwargs) -> dict:
        if not source:
            raise SystemExit("doubao-file needs --source <chats.jsonl|export.json>")
        path = Path(source).expanduser()
        if not path.is_file():
            raise SystemExit(f"source not found: {path}")
        return {"source_path": path}

    def pull(self, ctx: dict, raw_dir: Path, *, since: str | None = None) -> PullResult:
        raw_dir.mkdir(parents=True, exist_ok=True)
        source: Path = ctx["source_path"]
        target = raw_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
        return PullResult(raw_paths=[target], source_units=len(_load(target)))

    def normalize(self, pull: PullResult) -> NormalizeResult:
        conversations = _load(pull.raw_paths[0])
        records: list[dict] = []
        items_seen = items_skipped = 0
        for conversation in conversations:
            kept, seen, skipped = parse_conversation(conversation)
            records.extend(kept)
            items_seen += seen
            items_skipped += skipped
        return NormalizeResult(records=records, units_seen=len(conversations),
                               items_seen=items_seen, items_skipped=items_skipped)
