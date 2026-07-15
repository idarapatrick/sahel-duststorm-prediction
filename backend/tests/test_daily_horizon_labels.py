import unittest

import numpy as np

from ml.daily_horizon_labels import build_daily_horizon_targets


class DailyHorizonLabelTests(unittest.TestCase):
    def test_labels_follow_same_cell_and_calendar_date(self):
        dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-01"]
        cells = [101, 101, 101, 202]
        labels = [0, 1, 0, 1]
        targets, valid = build_daily_horizon_targets(dates, cells, labels)
        np.testing.assert_array_equal(targets[0], [0, 1, 0])
        np.testing.assert_array_equal(valid[0], [True, True, True])
        self.assertTrue(np.isnan(targets[3, 1]))
        self.assertFalse(valid[3, 1])

    def test_missing_day_is_masked_not_interpolated(self):
        targets, valid = build_daily_horizon_targets(
            ["2024-01-01", "2024-01-03"], [7, 7], [0, 1]
        )
        self.assertTrue(np.isnan(targets[0, 1]))
        self.assertFalse(valid[0, 1])


if __name__ == "__main__":
    unittest.main()
