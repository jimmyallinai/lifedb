import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lifedb_importers.core import pipeline, registry  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "chatgpt" / "conversations.json"


def shard_bytes(out: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted((out / "data" / "chatgpt").glob("*.jsonl"))}


class ChatGPTExportTest(unittest.TestCase):
    def run_importer(self, source: Path, tmp: str) -> dict:
        importer = registry.get("chatgpt-export")
        return pipeline.run_import(importer, source=str(source), out_root=Path(tmp))

    def test_counts_and_reconcile(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.run_importer(FIXTURE, tmp)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["source_units"], 3)
            self.assertEqual(report["units_seen"], 3)
            self.assertEqual(report["items_seen"], 11)
            self.assertEqual(report["items_skipped"], 3)
            self.assertEqual(report["records_written"], 8)

    def test_branch_tagged_and_months_sharded(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_importer(FIXTURE, tmp)
            shards = shard_bytes(Path(tmp))
            self.assertEqual(sorted(shards), ["2025-12.jsonl", "2026-01.jsonl"])
            records = [json.loads(line) for name in shards
                       for line in shards[name].decode("utf-8").splitlines()]
            branched = [r for r in records if r["branch"]]
            self.assertEqual(len(branched), 1)
            self.assertEqual(branched[0]["message_id"], "m-a2alt")
            self.assertEqual(len(branched[0]["branch"]), 16)
            self.assertTrue(all(r["id"].startswith("sha256:") for r in records))

    def test_zip_input_same_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "export.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.write(FIXTURE, arcname="conversations.json")
                zf.writestr("user.json", "{}")  # extra files are ignored
            report = self.run_importer(zip_path, str(Path(tmp) / "out"))
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["records_written"], 8)

    def test_empty_placeholder_conversation_tolerated(self):
        # Real ChatGPT exports include empty {} placeholder entries.
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data.append({})
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "conversations.json"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            report = self.run_importer(source, str(Path(tmp) / "out"))
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["source_units"], 4)
            self.assertEqual(report["records_written"], 8)

    def test_idempotent_byte_identical(self):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            self.run_importer(FIXTURE, t1)
            self.run_importer(FIXTURE, t2)
            self.assertEqual(shard_bytes(Path(t1)), shard_bytes(Path(t2)))


if __name__ == "__main__":
    unittest.main()
