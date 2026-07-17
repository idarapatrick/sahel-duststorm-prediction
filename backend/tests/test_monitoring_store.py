import os
import sys
import unittest
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from monitoring_store import monitoring_window, tracking_key
from prediction_cache import build_cache_key
from alert_store import should_deliver


class MonitoringLifecycleTests(unittest.TestCase):
    def test_tracking_key_coalesces_same_location_and_target(self):
        target = date(2026, 7, 17)
        self.assertEqual(
            tracking_key(14.69001, -17.44001, target),
            tracking_key(14.69002, -17.44002, target),
        )

    def test_window_runs_from_minus_60_to_plus_12_hours(self):
        start, end = monitoring_window(date(2026, 7, 17))
        self.assertEqual(start, datetime(2026, 7, 14, 12, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 7, 17, 12, tzinfo=timezone.utc))
        self.assertEqual((end - start).total_seconds() / 3600, 72)

    def test_cache_key_coalesces_nearby_requests_in_same_time_bucket(self):
        instant = datetime(2026, 7, 16, 12, 3, tzinfo=timezone.utc)
        first = build_cache_key(14.69001, -17.44001, date(2026, 7, 16), now=instant)
        second = build_cache_key(14.69002, -17.44002, date(2026, 7, 16), now=instant)
        self.assertEqual(first, second)

    def test_cache_key_changes_for_new_input_window(self):
        first = build_cache_key(
            14.69, -17.44, date(2026, 7, 16),
            now=datetime(2026, 7, 16, 12, 4, tzinfo=timezone.utc),
        )
        second = build_cache_key(
            14.69, -17.44, date(2026, 7, 16),
            now=datetime(2026, 7, 16, 12, 5, tzinfo=timezone.utc),
        )
        self.assertNotEqual(first, second)

    def test_alert_thresholds_and_downgrades_are_respected(self):
        self.assertTrue(should_deliver("warning", "alert", "upgraded"))
        self.assertFalse(should_deliver("alert", "warning", "upgraded"))
        self.assertFalse(should_deliver("alert", "clear", "downgraded"))


if __name__ == "__main__":
    unittest.main()
