import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lifedb_importers.core import pipeline, registry  # noqa: E402
from lifedb_importers.importers.generic_file import load_mapping  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "generic"


def _run(source: Path, mapping: Path, tmp: str) -> dict:
    importer = registry.get("generic-file")
    return pipeline.run_import(importer, source=str(source),
                               out_root=Path(tmp), mapping=str(mapping))


def _records(tmp: str, platform: str) -> list[dict]:
    lines = []
    for shard in sorted((Path(tmp) / "data" / platform).glob("*.jsonl")):
        lines.extend(shard.read_text(encoding="utf-8").splitlines())
    return [json.loads(line) for line in lines]


class GenericFileJsonTest(unittest.TestCase):
    def test_mapping_parse_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(FIXTURES / "samplechat.json",
                          FIXTURES / "samplechat.mapping.json", tmp)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["source_units"], 2)
            self.assertEqual(report["items_seen"], 4)
            self.assertEqual(report["items_skipped"], 1)
            self.assertEqual(report["records_written"], 3)

    def test_roles_mapped_and_platform_from_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(FIXTURES / "samplechat.json",
                 FIXTURES / "samplechat.mapping.json", tmp)
            records = _records(tmp, "samplechat")
            self.assertEqual(len(records), 3)
            by_id = {r["message_id"]: r for r in records}
            self.assertEqual(by_id["s-1"]["role"], "user")
            self.assertEqual(by_id["s-2"]["role"], "assistant")
            self.assertTrue(all(r["platform"] == "samplechat" for r in records))
            self.assertEqual(by_id["s-1"]["conversation_title"], "示例会话一")

    def test_idempotent_rerun_byte_identical(self):
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                _run(FIXTURES / "samplechat.json",
                     FIXTURES / "samplechat.mapping.json", tmp)
                shard_bytes = b"".join(
                    shard.read_bytes()
                    for shard in sorted((Path(tmp) / "data" / "samplechat").glob("*.jsonl")))
                outputs.append(shard_bytes)
        self.assertEqual(outputs[0], outputs[1])


class GenericFileCsvTest(unittest.TestCase):
    def test_flat_csv_grouped_by_conversation(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = _run(FIXTURES / "flatchat.csv",
                          FIXTURES / "flatchat.mapping.json", tmp)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["source_units"], 3)
            self.assertEqual(report["items_seen"], 4)
            # The row without a conversation id is counted as skipped.
            self.assertEqual(report["items_skipped"], 1)
            self.assertEqual(report["records_written"], 3)
            records = _records(tmp, "flatchat")
            self.assertEqual({r["conversation_id"] for r in records}, {"c-1", "c-2"})


class MappingValidationTest(unittest.TestCase):
    def test_missing_text_field_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.mapping.json"
            bad.write_text(json.dumps({
                "platform": "x", "conversation": {"id": "id"},
                "message": {"role": "role"},
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_mapping(bad)


if __name__ == "__main__":
    unittest.main()
