"""Three-count reconciliation + sharded, idempotent writing.

Counts that must agree before a run is allowed to succeed:
  1. source units in the raw payload (e.g. conversations)
  2. units seen by the parser
  3. raw items seen by the parser == records written + items skipped
Any disagreement marks the run failed (CLI exit code 1) and the report says
exactly which count drifted. Nothing is silently swallowed.

Idempotency: records are deduplicated by stable id and serialized with
sorted keys, so re-running the same input produces byte-identical shards.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import schema


def dedupe(records: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for record in records:
        schema.validate_record(record)
        seen[record["id"]] = record
    return list(seen.values())


def write_shards(records: list[dict], out_dir: Path, platform: str) -> dict[str, int]:
    """Write <out_dir>/<platform>/<YYYY-MM>.jsonl shards. Returns month->count."""
    target_dir = out_dir / platform
    target_dir.mkdir(parents=True, exist_ok=True)
    by_month: dict[str, list[dict]] = {}
    for record in records:
        by_month.setdefault(record["month"], []).append(record)
    counts: dict[str, int] = {}
    for month, month_records in sorted(by_month.items()):
        ordered = sorted(
            month_records,
            key=lambda r: (r["created_at"] or "", r["conversation_id"], r["message_id"]),
        )
        path = target_dir / f"{month}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            for record in ordered:
                fh.write(schema.dump_record(record) + "\n")
        counts[month] = len(ordered)
    return counts


def reconcile(*, source_units: int, units_seen: int, items_seen: int,
              items_skipped: int, records_written: int) -> dict:
    checks = {
        "units_match": source_units == units_seen,
        "items_accounted": items_seen == records_written + items_skipped,
    }
    return {
        "source_units": source_units,
        "units_seen": units_seen,
        "items_seen": items_seen,
        "items_skipped": items_skipped,
        "records_written": records_written,
        "checks": checks,
        "ok": all(checks.values()),
    }


def write_report(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path
