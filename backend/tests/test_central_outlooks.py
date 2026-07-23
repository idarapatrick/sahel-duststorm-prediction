"""Tests for the shared daily central-outlook contract."""

import unittest
from datetime import date

from central_outlooks import central_target_dates


class CentralOutlookTests(unittest.TestCase):
    def test_targets_cover_today_and_tomorrow_only(self):
        self.assertEqual(
            central_target_dates(date(2026, 7, 23)),
            [
                date(2026, 7, 23),
                date(2026, 7, 24),
            ],
        )


if __name__ == "__main__":
    unittest.main()
