import unittest

from mt5bot.smc.snapshot import SnapshotError, validate_snapshot


def sample():
    return {
        "schema_version": 1,
        "library_version": "test",
        "symbol": "EURUSD",
        "timeframe": "M15",
        "time_basis": "broker",
        "as_of": "2026-01-01 10:00:00",
        "status": "READY",
        "config": {},
        "modules": {},
        "records": [
            {
                "id": "ob-1",
                "concept": "ORDER_BLOCK",
                "direction": "BULLISH",
                "lower": 1.1,
                "upper": 1.101,
                "state": "ACTIVE",
                "active": True,
            }
        ],
    }


class SnapshotReaderTests(unittest.TestCase):
    def test_accepts_ready_snapshot(self):
        result = validate_snapshot(sample())
        self.assertEqual(result.symbol, "EURUSD")
        self.assertEqual(len(result.records), 1)

    def test_rejects_non_ready_snapshot_by_default(self):
        data = sample()
        data["status"] = "PARTIAL"
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)

    def test_can_inspect_non_ready_snapshot_explicitly(self):
        data = sample()
        data["status"] = "PARTIAL"
        self.assertEqual(validate_snapshot(data, require_ready=False).status, "PARTIAL")

    def test_rejects_duplicate_ids(self):
        data = sample()
        data["records"].append(dict(data["records"][0]))
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)

    def test_rejects_inverted_zone(self):
        data = sample()
        data["records"][0]["lower"] = 2
        data["records"][0]["upper"] = 1
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)


if __name__ == "__main__":
    unittest.main()
