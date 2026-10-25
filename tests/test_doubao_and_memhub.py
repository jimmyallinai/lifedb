import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lifedb_importers.core import pipeline, registry  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Fields Hy-Memory's parse_export_record requires / reads.
MEMHUB_REQUIRED = {"conversation_id", "message_id", "role", "written_by",
                   "verbatim", "record_type"}
WRITTEN_BY_ENUM = {"person", "agent", "tool", "unknown"}


class DoubaoFileTest(unittest.TestCase):
    def test_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            importer = registry.get("doubao-file")
            report = pipeline.run_import(
                importer, source=str(FIXTURES / "doubao" / "chats.jsonl"),
                out_root=Path(tmp))
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["source_units"], 2)
            self.assertEqual(report["items_seen"], 4)
            self.assertEqual(report["items_skipped"], 1)
            self.assertEqual(report["records_written"], 3)

    def test_derived_message_id_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            importer = registry.get("doubao-file")
            pipeline.run_import(importer, source=str(FIXTURES / "doubao" / "chats.jsonl"),
                                out_root=Path(tmp))
            lines = []
            for shard in (Path(tmp) / "data" / "doubao").glob("*.jsonl"):
                lines.extend(shard.read_text(encoding="utf-8").splitlines())
            records = [json.loads(line) for line in lines]
            derived = [r for r in records if r["message_id"].startswith("derived:")]
            self.assertEqual(len(derived), 1)


class MemHubLaneTest(unittest.TestCase):
    def _memhub_lines(self, importer_name: str, source: Path, tmp: str) -> list[dict]:
        importer = registry.get(importer_name)
        report = pipeline.run_import(importer, source=str(source),
                                     out_root=Path(tmp), to="memhub")
        self.assertTrue(report["ok"], report)
        path = Path(report["memhub_output"])
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_chatgpt_memhub_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self._memhub_lines("chatgpt-export",
                                      FIXTURES / "chatgpt" / "conversations.json", tmp)
            self.assertEqual(len(rows), 8)
            for row in rows:
                self.assertTrue(MEMHUB_REQUIRED <= set(row), row)
                self.assertIn(row["written_by"], WRITTEN_BY_ENUM)
                self.assertEqual(row["content_kind"], "raw_conversation")
            branched = [r for r in rows if ":branch:" in r["conversation_id"]]
            self.assertEqual(len(branched), 1)
            roles = {r["message_id"]: r["written_by"] for r in rows}
            self.assertEqual(roles["m-u1"], "person")
            self.assertEqual(roles["m-a1"], "agent")

    def test_doubao_memhub_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self._memhub_lines("doubao-file",
                                      FIXTURES / "doubao" / "chats.jsonl", tmp)
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertTrue(MEMHUB_REQUIRED <= set(row), row)


if __name__ == "__main__":
    unittest.main()
