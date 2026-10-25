"""Generic file importer: any platform's exported chat file + a mapping.

Some platforms will never get a dedicated importer. This one covers the
long tail: give it a chat export in JSON / JSONL / CSV plus a small
field-mapping config (see templates/mapping.example.json) and it
normalizes the file into the same unified JSONL as every other importer,
with the same three-count reconciliation and idempotent output.

Mapping config (JSON):
  {
    "platform": "some-platform",          # record platform tag
    "format": "auto",                     # auto | json | jsonl | csv
    "conversations": "conversations",     # optional dot path to the list
                                          # of conversations in a JSON doc
    "conversation": {"id": "id", "title": "title", "messages": "messages"},
    "message": {"id": "message_id", "role": "role",
                "text": "text", "time": "time"},
    "role_map": {"human": "user", "bot": "assistant"}   # optional
  }
Field names are dot paths ("meta.thread_id" works). Two input shapes:
- nested: a list of conversations, each holding a messages list;
- flat:   one message per row (CSV, or JSONL without a messages field) —
          rows are grouped by the conversation id field.
Messages without usable text are skipped and counted; a conversation
without an id has all of its messages skipped and counted — nothing is
silently dropped (reconciliation would fail the run otherwise).
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

from ..core import schema
from ..core.base import Importer, NormalizeResult, PullResult


def _get(obj, path):
    """Resolve a dot path ("meta.thread_id") against nested dicts."""
    if not path:
        return None
    current = obj
    for part in str(path).split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def load_mapping(path: Path) -> dict:
    mapping = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(mapping, dict):
        raise ValueError("mapping config must be a JSON object")
    conv = mapping.get("conversation") or {}
    msg = mapping.get("message") or {}
    if not conv.get("id"):
        raise ValueError("mapping.conversation.id is required")
    if not msg.get("text"):
        raise ValueError("mapping.message.text is required")
    return mapping


def _coerce_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _message_id(conv_id: str, message: dict, index: int, mapping: dict) -> str:
    raw = _get(message, (mapping.get("message") or {}).get("id"))
    if raw not in (None, ""):
        return str(raw)
    digest = hashlib.sha256(
        json.dumps([conv_id, index, _get(message, (mapping.get("message") or {}).get("text"))],
                   ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:24]
    return f"derived:{digest}"


def _units_from_conversations(conversations: list, mapping: dict) -> list[dict]:
    conv_map = mapping.get("conversation") or {}
    msg_key = conv_map.get("messages") or "messages"
    units = []
    for conv in conversations:
        if not isinstance(conv, dict):
            units.append({"id": None, "title": None, "messages": []})
            continue
        messages = _get(conv, msg_key)
        units.append({
            "id": _get(conv, conv_map.get("id")),
            "title": _get(conv, conv_map.get("title")),
            "messages": messages if isinstance(messages, list) else [],
        })
    return units


def _units_from_flat(rows: list, mapping: dict) -> list[dict]:
    conv_map = mapping.get("conversation") or {}
    groups: dict[str, dict] = {}
    order: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = _get(row, conv_map.get("id"))
        key = str(cid) if cid not in (None, "") else ""
        if key not in groups:
            groups[key] = {"id": cid, "title": _get(row, conv_map.get("title")),
                           "messages": []}
            order.append(groups[key])
        unit = groups[key]
        if not unit["title"]:
            unit["title"] = _get(row, conv_map.get("title"))
        unit["messages"].append(row)
    return order


def load_units(path: Path, mapping: dict) -> list[dict]:
    fmt = (mapping.get("format") or "auto").lower()
    if fmt == "auto":
        fmt = {".csv": "csv", ".jsonl": "jsonl", ".ndjson": "jsonl"}.get(
            path.suffix.lower(), "json")
    if fmt == "csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return _units_from_flat(list(csv.DictReader(fh)), mapping)
    if fmt == "jsonl":
        items = [json.loads(line) for line in
                 path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        conv_map = mapping.get("conversation") or {}
        msg_key = conv_map.get("messages") or "messages"
        if items and all(isinstance(it, dict) and isinstance(_get(it, msg_key), list)
                         for it in items):
            return _units_from_conversations(items, mapping)
        return _units_from_flat(items, mapping)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    container = mapping.get("conversations")
    if container:
        data = _get(data, container)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("unsupported generic file shape: expected a list of conversations")
    return _units_from_conversations(data, mapping)


class GenericFileImporter(Importer):
    name = "generic-file"
    platform = "generic"       # replaced by the mapping's platform in auth()
    display_name = "通用文件（任意平台导出 JSON/CSV + 字段映射）"
    entry_kind = "file"
    status = "ready"
    calibration = "synthetic fixtures (nested JSON, flat CSV); mapping-driven, no platform assumptions"

    def auth(self, *, source: str | None = None, mapping: str | None = None,
             **kwargs) -> dict:
        if not source:
            raise SystemExit("generic-file needs --source <export.json|export.jsonl|export.csv>")
        if not mapping:
            raise SystemExit("generic-file needs --mapping <mapping.json> "
                             "(see templates/mapping.example.json)")
        source_path = Path(source).expanduser()
        mapping_path = Path(mapping).expanduser()
        for label, path in (("source", source_path), ("mapping", mapping_path)):
            if not path.is_file():
                raise SystemExit(f"{label} not found: {path}")
        config = load_mapping(mapping_path)
        # The CLI runs one import per process; pointing the shared instance
        # at the mapped platform keeps shards/reports under that platform.
        self.platform = str(config.get("platform") or "generic")
        self._current_mapping = config
        return {"source_path": source_path, "mapping_path": mapping_path,
                "mapping": config}

    def pull(self, ctx: dict, raw_dir: Path, *, since: str | None = None) -> PullResult:
        raw_dir.mkdir(parents=True, exist_ok=True)
        source: Path = ctx["source_path"]
        target = raw_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
        mapping_copy = raw_dir / ctx["mapping_path"].name
        if ctx["mapping_path"].resolve() != mapping_copy.resolve():
            shutil.copyfile(ctx["mapping_path"], mapping_copy)
        return PullResult(raw_paths=[target], source_units=len(load_units(target, ctx["mapping"])))

    def normalize(self, pull: PullResult) -> NormalizeResult:
        # The mapping travels with the raw payload (copied by pull()).
        mapping = self._mapping_for(pull)
        units = load_units(pull.raw_paths[0], mapping)
        records: list[dict] = []
        items_seen = items_skipped = 0
        for unit in units:
            conv_id = unit["id"]
            title = unit["title"] if isinstance(unit["title"], str) else None
            if conv_id in (None, ""):
                items_seen += len(unit["messages"])
                items_skipped += len(unit["messages"])
                continue
            conv_id = str(conv_id)
            for index, message in enumerate(unit["messages"]):
                if not isinstance(message, dict):
                    continue
                items_seen += 1
                text = _coerce_text(_get(message, (mapping.get("message") or {}).get("text")))
                if text is None or not text.strip():
                    items_skipped += 1
                    continue
                role = _get(message, (mapping.get("message") or {}).get("role"))
                role = str(role) if role not in (None, "") else "unknown"
                role = (mapping.get("role_map") or {}).get(role, role)
                records.append(schema.make_record(
                    platform=self.platform,
                    source=self.name,
                    conversation_id=conv_id,
                    conversation_title=title,
                    message_id=_message_id(conv_id, message, index, mapping),
                    role=role,
                    text=text,
                    created_at=_get(message, (mapping.get("message") or {}).get("time")),
                ))
        return NormalizeResult(records=records, units_seen=len(units),
                               items_seen=items_seen, items_skipped=items_skipped)

    _current_mapping: dict | None = None

    def _mapping_for(self, pull: PullResult) -> dict:
        # pipeline calls auth() before pull()/normalize() in the same
        # process, so the mapping resolved there is authoritative; fall
        # back to the copy pull() landed next to the raw payload.
        if self._current_mapping is not None:
            return self._current_mapping
        raw_dir = pull.raw_paths[0].parent
        for candidate in sorted(raw_dir.glob("*.json")):
            if candidate != pull.raw_paths[0]:
                try:
                    return load_mapping(candidate)
                except (ValueError, json.JSONDecodeError):
                    continue
        raise ValueError("generic-file: mapping config not found")
