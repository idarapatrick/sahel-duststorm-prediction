import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import history_store


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_path = history_store.SQLITE_PATH
        history_store.SQLITE_PATH = Path(self.temp_dir.name) / "history.db"

    def tearDown(self):
        history_store.SQLITE_PATH = self.previous_path
        self.temp_dir.cleanup()

    def snapshot(self, recorded_at=None):
        return {
            "lat": 13.51,
            "lon": 2.11,
            "location_name": "Niamey, Niger",
            "target_date": datetime.now(timezone.utc).date().isoformat(),
            "recorded_at": recorded_at,
            "probability": 0.41,
            "alert_level": "watch",
            "dust_event": False,
            "data_source": "test",
        }

    def test_round_trip_snapshot(self):
        saved = history_store.save_snapshot(self.snapshot())
        rows = history_store.query_snapshots(13.51, 2.11, datetime.now(timezone.utc).date())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], saved["id"])
        self.assertEqual(rows[0]["alert_level"], "watch")

    def test_query_uses_small_coordinate_tolerance(self):
        history_store.save_snapshot(self.snapshot())
        rows = history_store.query_snapshots(14.0, 2.11, datetime.now(timezone.utc).date())
        self.assertEqual(rows, [])

    def test_retention_purges_records_older_than_90_days(self):
        old = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
        history_store.save_snapshot(self.snapshot(old))
        history_store.purge_expired()
        rows = history_store.query_snapshots(13.51, 2.11, datetime.now(timezone.utc).date())
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
