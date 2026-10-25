"""Run one importer end to end: auth -> pull -> normalize -> dedupe ->
shard -> (optional MemHub lane) -> reconcile. Exit-code semantics live in
the CLI: reconciliation failure == run failure (exit 1).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import memhub, reconcile as rec
from .base import Importer


def run_import(importer: Importer, *, source: str | None, out_root: Path,
               to: str | None = None, since: str | None = None,
               mapping: str | None = None) -> dict:
    out_root = Path(out_root)
    ctx = importer.auth(source=source, mapping=mapping)
    pull = importer.pull(ctx, out_root / "raw" / importer.platform, since=since)
    norm = importer.normalize(pull)

    records = rec.dedupe(norm.records)
    if since:
        records = [r for r in records if (r["month"] or "") >= since]
    shards = rec.write_shards(records, out_root / "data", importer.platform)

    memhub_path = None
    if to == "memhub":
        memhub_path = _write_memhub(records, out_root, importer)

    report = rec.reconcile(
        source_units=pull.source_units,
        units_seen=norm.units_seen,
        items_seen=norm.items_seen,
        items_skipped=norm.items_skipped,
        records_written=len(records),
    )
    report.update({
        "importer": importer.name,
        "platform": importer.platform,
        "shards": shards,
        "memhub_output": str(memhub_path) if memhub_path else None,
    })
    rec.write_report(report, out_root / "reports" / f"{importer.name}.json")
    return report


def _write_memhub(records: list[dict], out_root: Path, importer: Importer) -> Path:
    path = out_root / "memhub" / f"{importer.platform}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        records,
        key=lambda r: (r["conversation_id"], r["created_at"] or "", r["message_id"]),
    )
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for record in ordered:
            fh.write(json.dumps(memhub.to_memhub_record(record),
                                ensure_ascii=False, sort_keys=True) + "\n")
    return path
