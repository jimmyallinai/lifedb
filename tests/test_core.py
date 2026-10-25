import random
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lifedb_importers.core import reconcile, schema, vault  # noqa: E402
from lifedb_importers.core.ratelimit import PlatformBlocked, RateLimiter, raise_for_status  # noqa: E402


class SchemaTest(unittest.TestCase):
    def test_stable_id_deterministic_and_platform_scoped(self):
        self.assertEqual(schema.stable_id("chatgpt", "m-1"),
                         schema.stable_id("chatgpt", "m-1"))
        self.assertNotEqual(schema.stable_id("chatgpt", "m-1"),
                            schema.stable_id("doubao", "m-1"))

    def test_epoch_normalization(self):
        self.assertTrue(schema.normalize_time(1767225600).startswith("2026-01-01"))
        self.assertTrue(schema.normalize_time(1767225600000).startswith("2026-01-01"))
        self.assertIsNone(schema.normalize_time("not-a-date"))


class ReconcileTest(unittest.TestCase):
    def test_mismatch_detected(self):
        bad = reconcile.reconcile(source_units=3, units_seen=2, items_seen=10,
                                  items_skipped=3, records_written=8)
        self.assertFalse(bad["ok"])
        good = reconcile.reconcile(source_units=3, units_seen=3, items_seen=11,
                                   items_skipped=3, records_written=8)
        self.assertTrue(good["ok"])


class VaultTest(unittest.TestCase):
    def test_permissions_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = vault.save_credential("example", {"SESSDATA": "x"}, home=home)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(vault.load_credential("example", home=home),
                             {"SESSDATA": "x"})

    def test_redact(self):
        line = vault.redact("cookie SESSDATA=abc123; pt_key=zzz, token: t0ken")
        self.assertNotIn("abc123", line)
        self.assertNotIn("zzz", line)
        self.assertNotIn("t0ken", line)


class RateLimitTest(unittest.TestCase):
    def test_random_intervals(self):
        limiter = RateLimiter(1.0, 3.0, rng=random.Random(42))
        delays = [limiter.next_delay() for _ in range(50)]
        self.assertTrue(all(1.0 <= d <= 3.0 for d in delays))
        self.assertGreater(len(set(delays)), 20)  # not a fixed rhythm

    def test_403_stops(self):
        with self.assertRaises(PlatformBlocked):
            raise_for_status(403)
        raise_for_status(200)


if __name__ == "__main__":
    unittest.main()
