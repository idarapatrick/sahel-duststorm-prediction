"""Tests for leakage-safe probability evaluation and operational slices."""

import os
import sys
import unittest
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from validation_service import (
    ValidationCase,
    ValidationEvaluator,
    probability_metrics,
    sahel_season,
)


class ValidationServiceTests(unittest.TestCase):
    """Verify metrics and failure slices without requiring a database."""

    def test_perfect_probabilities_have_zero_brier_score(self):
        result = probability_metrics([0.0, 1.0], [False, True])
        self.assertEqual(result["brier_score"], 0.0)
        self.assertEqual(result["roc_auc"], 1.0)
        self.assertEqual(result["precision"], 1.0)
        self.assertEqual(result["recall"], 1.0)

    def test_evaluator_reports_location_season_source_and_lead_slices(self):
        cases = [
            ValidationCase(
                snapshot_id="one",
                location_id="location",
                location_name="Niamey",
                target_date=date(2026, 7, 24),
                issued_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
                probability=0.8,
                outcome=True,
                lead_hours=24,
                season=sahel_season(date(2026, 7, 24)),
                fallback_used=True,
                completeness=0.9,
                evidence={
                    "wind_speed_10m": 9.0,
                    "soil_moisture": 0.06,
                    "previous_day_aod": 0.5,
                },
            )
        ]
        result = ValidationEvaluator().evaluate(cases)
        self.assertIn("location:Niamey", result["slices"])
        self.assertIn("season:wet", result["slices"])
        self.assertIn("source:fallback", result["slices"])
        self.assertIn("lead:18_to_36h", result["slices"])
        self.assertIn("physical_threshold", result["baselines"])


if __name__ == "__main__":
    unittest.main()
