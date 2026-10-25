"""lifedb-import CLI.

Usage:
  lifedb-import list
  lifedb-import import chatgpt-export --source export.zip --out ./out [--to memhub] [--since 2026-01]
  lifedb-import import doubao-file   --source chats.jsonl  --out ./out [--to memhub]
  lifedb-import import generic-file  --source export.csv  --mapping mapping.json --out ./out

Output discipline: one summary line per run + the reconciliation report
path. Details live in <out>/reports/<importer>.json. Exit code 1 when
reconciliation fails (counts disagree) — never succeed silently.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import pipeline, registry


def _cmd_list(_args) -> int:
    rows = []
    for importer in registry.IMPORTERS.values():
        rows.append({
            "name": importer.name, "platform": importer.platform,
            "entry": importer.entry_kind, "status": importer.status,
        })
    for planned in registry.PLANNED:
        rows.append({"name": planned["name"], "platform": planned["platform"],
                     "entry": planned["entry_kind"], "status": planned["status"]})
    for row in rows:
        print(f"{row['name']:<16} platform={row['platform']:<10} "
              f"entry={row['entry']:<8} status={row['status']}")
    return 0


def _cmd_import(args) -> int:
    importer = registry.get(args.platform)
    report = pipeline.run_import(
        importer,
        source=args.source,
        out_root=Path(args.out),
        to=args.to,
        since=args.since,
        mapping=args.mapping,
    )
    status = "OK" if report["ok"] else "FAIL(reconcile)"
    print(f"{importer.name}: units={report['units_seen']} "
          f"records={report['records_written']} skipped={report['items_skipped']} "
          f"-> {status}; report={Path(args.out) / 'reports' / (importer.name + '.json')}")
    if args.to == "memhub" and report.get("memhub_output"):
        print(f"memhub: {report['memhub_output']}")
    return 0 if report["ok"] else 1


def _cmd_wizard(_args) -> int:
    print("wizard is planned for slice 3 (one-command QR marathon across "
          "login-based importers). This slice ships file-entry importers only.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lifedb-import")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list importers and their status")

    p_import = sub.add_parser("import", help="run one importer")
    p_import.add_argument("platform", help="importer name, e.g. chatgpt-export")
    p_import.add_argument("--source", required=True, help="input file (export zip / json / jsonl)")
    p_import.add_argument("--out", default="./lifedb-out", help="output root directory")
    p_import.add_argument("--to", choices=["memhub"], default=None,
                          help="extra output target: MemHub generic-export JSONL")
    p_import.add_argument("--since", default=None, help="watermark month, YYYY-MM")
    p_import.add_argument("--mapping", default=None,
                          help="field-mapping config (generic-file; see templates/mapping.example.json)")

    sub.add_parser("wizard", help="(planned, slice 3)")

    args = parser.parse_args(argv)
    if args.command == "list":
        return _cmd_list(args)
    if args.command == "import":
        return _cmd_import(args)
    if args.command == "wizard":
        return _cmd_wizard(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
