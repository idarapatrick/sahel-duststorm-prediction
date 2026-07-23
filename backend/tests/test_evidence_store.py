"""Tests for evidence timing, identity, and source-composition rules."""

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from evidence_store import (
    EvidenceRecord,
    evidence_fingerprint,
    evidence_summary,
    replay_eligible,
)


class EvidenceStoreTests(unittest.TestCase):
    """Verify that provenance rules prevent future-data leakage."""

    def test_late_satellite_reading_is_excluded_from_replay(self):
        issued = datetime(2026, 7, 23, 10, tzinfo=timezone.utc)
        record = EvidenceRecord(
            variable_name="soil_moisture",
            value=0.08,
            unit="m3/m3",
            provider="smap",
            evidence_kind="delayed_observation",
            measured_at="2026-07-23T06:00:00Z",
            available_at="2026-07-25T06:00:00Z",
        )
        self.assertEqual(replay_eligible([record], issued), [])

    def test_value_available_before_issue_is_eligible(self):
        record = EvidenceRecord(
            variable_name="previous_day_aod",
            value=0.4,
            unit="unitless",
            provider="cams-global",
            evidence_kind="analysis",
            measured_at="2026-07-23T06:00:00Z",
            available_at="2026-07-23T08:00:00Z",
        )
        self.assertEqual(
            replay_eligible([record], "2026-07-23T10:00:00Z"), [record]
        )

    def test_retrieval_time_does_not_change_evidence_fingerprint(self):
        common = {
            "variable_name": "temperature_2m",
            "value": 32.0,
            "unit": "degrees_celsius",
            "provider": "open-meteo-forecast",
            "evidence_kind": "forecast",
            "available_at": "2026-07-23T08:00:00Z",
            "forecast_target_at": "2026-07-24T00:00:00Z",
        }
        first = EvidenceRecord(**common, retrieved_at="2026-07-23T08:01:00Z")
        second = EvidenceRecord(**common, retrieved_at="2026-07-23T08:05:00Z")
        self.assertEqual(
            evidence_fingerprint([first]), evidence_fingerprint([second])
        )

    def test_missing_values_reduce_completeness_without_becoming_zero(self):
        available = EvidenceRecord(
            variable_name="soil_moisture",
            value=0.0,
            unit="m3/m3",
            provider="smap",
            evidence_kind="observation",
            available_at="2026-07-23T08:00:00Z",
        )
        missing = EvidenceRecord(
            variable_name="previous_day_aod",
            value=None,
            unit="unitless",
            provider="unavailable",
            evidence_kind="missing",
            available_at="2026-07-23T08:00:00Z",
            quality_status="missing",
        )
        summary = evidence_summary([available, missing])
        self.assertEqual(summary["input_completeness"], 0.5)
        self.assertEqual(missing.value, None)


if __name__ == "__main__":
    unittest.main()
