# Adapted from Tencent Hy-Memory (Apache License 2.0):
#   memhub/apps/core/src/one_memory/imports/chat_exports.py
#   Copyright 2026 Tencent. Original license: third_party/tencent-hy-memory/LICENSE
# Modifications (lifedb-importers, MIT): the conversation-tree walk below
# re-implements the same decoding semantics (parent-chain depths, active
# branch via current_node, branch separation, skip rules) but emits lifedb
# unified records (core.schema) instead of Hy-Memory ParsedMessage objects,
# and adds full kept/skipped accounting for three-count reconciliation.
# No Tencent code is imported at runtime; this module is stdlib-only.
"""ChatGPT official export importer (file entry, no login).

Input : the official export .zip (Settings -> Data controls -> Export) or a
        bare conversations.json.
Output: unified records, one per kept message.

Decoding semantics (aligned with the Hy-Memory reference implementation):
- conversations are trees (`mapping`); message order = parent-chain depth.
- the ACTIVE branch is the chain ending at `current_node`; messages off
  that branch belong to an edit/regeneration offshoot and are tagged with
  a branch id (sha256 of the offshoot root, first 16 hex chars) so they
  never masquerade as the main line of the dialogue.
- skipped (counted, never silent): non user/assistant roles, analysis
  channel (model thinking), reasoning content types without a text parts
  list (`thoughts` / `reasoning_recap` — on a real export these were
  1,376 of 1,391 skips), recipients other than "all", empty text.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from ..core import schema
from ..core.base import Importer, NormalizeResult, PullResult


def _load_conversations(path: Path) -> list[dict]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist()
                     if Path(n).name == "conversations.json"]
            if len(names) != 1:
                raise ValueError("export zip must contain exactly one conversations.json")
            payload = archive.read(names[0])
        data = json.loads(payload.decode("utf-8-sig"))
    else:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):  # a single exported conversation
        data = [data]
    if not isinstance(data, list) or not all(isinstance(c, dict) for c in data):
        raise ValueError("unsupported conversations.json shape")
    return data


def _depths(mapping: dict) -> dict[str, int]:
    depths: dict[str, int] = {}
    for key in mapping:
        chain, seen = [], set()
        cursor = key
        while cursor is not None and cursor not in depths:
            if cursor in seen or cursor not in mapping:
                raise ValueError("invalid conversation tree (cycle or dangling parent)")
            chain.append(cursor)
            seen.add(cursor)
            cursor = mapping[cursor].get("parent")
        depth = depths.get(cursor, -1) if cursor is not None else -1
        for entry in reversed(chain):
            depth += 1
            depths[entry] = depth
    return depths


def _active_nodes(conversation: dict, mapping: dict) -> set[str]:
    active: set[str] = set()
    current = conversation.get("current_node")
    while current is not None and current in mapping and current not in active:
        active.add(current)
        current = mapping[current].get("parent")
    return active


def _branch_id(node_key: str, mapping: dict, active: set[str]) -> str:
    """First 16 hex of sha256 of the offshoot root (the node whose parent
    chain first touches the active branch)."""
    ancestor, visited = node_key, set()
    while mapping[ancestor].get("parent") not in active:
        if ancestor in visited:
            raise ValueError("invalid conversation tree (branch cycle)")
        visited.add(ancestor)
        parent = mapping[ancestor].get("parent")
        if parent is None or parent not in mapping:
            break
        ancestor = parent
    return hashlib.sha256(ancestor.encode("utf-8")).hexdigest()[:16]


def parse_conversation(conversation: dict) -> tuple[list[dict], int, int]:
    """Returns (records, items_seen, items_skipped) for one conversation."""
    conversation_id = str(conversation.get("id") or conversation.get("conversation_id") or "")
    mapping = conversation.get("mapping")
    if not conversation_id:
        if not mapping:
            # Real exports contain empty {} placeholder entries; they are
            # units with zero messages, not corruption. Count and move on.
            return [], 0, 0
        raise ValueError("conversation with mapping but without id")
    if not isinstance(mapping, dict) or not mapping:
        return [], 0, 0
    title = conversation.get("title") if isinstance(conversation.get("title"), str) else None
    depths = _depths(mapping)
    active = _active_nodes(conversation, mapping)
    records: list[dict] = []
    seen = skipped = 0
    for key in sorted(mapping, key=lambda k: depths[k]):
        node = mapping[key]
        message = node.get("message")
        if message is None:
            continue  # structural node, not an item
        seen += 1
        if not isinstance(message, dict) or not isinstance(message.get("author"), dict):
            skipped += 1
            continue
        role = message["author"].get("role")
        content = message.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if (
            role not in ("user", "assistant")
            or message.get("channel") == "analysis"
            or message.get("recipient") not in (None, "all")
            or not isinstance(parts, list)
        ):
            skipped += 1
            continue
        text = "\n".join(part for part in parts if isinstance(part, str))
        if not text.strip():
            skipped += 1
            continue
        branch = None
        if key not in active and active:
            branch = _branch_id(key, mapping, active)
        records.append(schema.make_record(
            platform="chatgpt",
            source="chatgpt-export",
            conversation_id=conversation_id,
            conversation_title=title,
            message_id=str(message.get("id") or key),
            role=role,
            text=text,
            created_at=message.get("create_time"),
            branch=branch,
        ))
    return records, seen, skipped


class ChatGPTExportImporter(Importer):
    name = "chatgpt-export"
    platform = "chatgpt"
    display_name = "ChatGPT 官方导出包"
    entry_kind = "file"
    status = "ready"
    calibration = "parser semantics aligned with Tencent Hy-Memory chat_exports.py; verified on a real export (counts in repo report)"

    def auth(self, *, source: str | None = None, **kwargs) -> dict:
        if not source:
            raise SystemExit("chatgpt-export needs --source <export.zip|conversations.json>")
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
        conversations = _load_conversations(target)
        return PullResult(raw_paths=[target], source_units=len(conversations))

    def normalize(self, pull: PullResult) -> NormalizeResult:
        conversations = _load_conversations(pull.raw_paths[0])
        records: list[dict] = []
        items_seen = items_skipped = 0
        for conversation in conversations:
            kept, seen, skipped = parse_conversation(conversation)
            records.extend(kept)
            items_seen += seen
            items_skipped += skipped
        return NormalizeResult(records=records, units_seen=len(conversations),
                               items_seen=items_seen, items_skipped=items_skipped)
