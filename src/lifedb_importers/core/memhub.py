"""MemHub export lane: convert lifedb records to the MemHub "generic export"
JSONL shape consumed by Tencent Hy-Memory's parse_export_record
(memhub/apps/core/src/one_memory/imports/sources/exported.py, Apache-2.0).

One JSON object per MESSAGE with fields:
  conversation_id (str, required)   message_id (str, required)
  role (str, required)               written_by ("person"|"agent"|"tool"|"unknown")
  verbatim (str, required)           record_type (str, required)
  created_at (ISO 8601, optional)    project (str, optional)
  content_kind ("raw_conversation" | "memory_content", default raw_conversation)

So a downstream MemHub install can ingest lifedb-importers output as a
generic-export source: we borrow its distribution/recall layer without
depending on its login model (it has none for server-side platforms).
"""

from __future__ import annotations

WRITTEN_BY = {
    "user": "person",
    "human": "person",
    "assistant": "agent",
    "tool": "tool",
}

RECORD_TYPE = {
    "chatgpt-export": "chatgpt_export",
    "doubao-file": "doubao_export",
}


def to_memhub_record(record: dict) -> dict:
    conversation_id = record["conversation_id"]
    if record.get("branch"):
        # Mirror Hy-Memory's own branch handling: offshoots are separate
        # conversations suffixed with the branch id.
        conversation_id = f"{conversation_id}:branch:{record['branch']}"
    out = {
        "conversation_id": conversation_id,
        "message_id": record["message_id"],
        "role": record["role"],
        "written_by": WRITTEN_BY.get(record["role"], "unknown"),
        "verbatim": record["text"],
        "record_type": RECORD_TYPE.get(record["source"], f"{record['platform']}_export"),
        "content_kind": "raw_conversation",
    }
    if record.get("created_at"):
        out["created_at"] = record["created_at"]
    if record.get("conversation_title"):
        out["project"] = record["conversation_title"]
    return out
