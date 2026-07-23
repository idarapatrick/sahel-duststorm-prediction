import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import data_pipeline


class ImmediateExecutor:
    async def run_in_executor(self, _executor, function, *args):
        return function(*args)


class SatelliteFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_eight_day_smap_miss_uses_open_meteo_and_marks_degraded(self):
        target = datetime(2026, 7, 21, tzinfo=timezone.utc)
        raw = {"hourly": {}}
        atmospheric = [[0.0] * 7 for _ in range(72)]

        with (
            patch.object(data_pipeline, "GEE_AVAILABLE", True),
            patch.object(data_pipeline, "_fetch_openmeteo_forecast", return_value=raw),
            patch.object(data_pipeline, "_extract_72h_window", return_value=atmospheric),
            patch.object(data_pipeline, "_extract_soil_moisture", return_value=0.17),
            patch.object(data_pipeline, "_fetch_smap_gee", return_value=(None, None)) as smap,
            patch.object(data_pipeline, "_fetch_modis_aod_gee", return_value=0.0) as modis,
            patch.object(data_pipeline, "_fetch_cams_aod", return_value=(0.0, None)),
        ):
            _, surface, provenance, _ = await data_pipeline.build_prediction_inputs(
                13.51, 2.11, target, ImmediateExecutor()
            )

        self.assertEqual(smap.call_count, 8)
        self.assertEqual(modis.call_count, 7)
        self.assertEqual(surface[:3], [0.17, 0.0, 0.0])
        self.assertEqual(provenance["soil_moisture"]["source"], "open-meteo-forecast")
        self.assertFalse(provenance["vegetation_water_content"]["available"])
        self.assertFalse(provenance["previous_day_aod"]["available"])
        self.assertTrue(provenance["degraded"])

    async def test_backfilled_satellite_dates_are_preserved(self):
        target = datetime(2026, 7, 21, tzinfo=timezone.utc)
        raw = {"hourly": {}}
        atmospheric = [[0.0] * 7 for _ in range(72)]
        smap_values = [(None, None), (None, None), (0.11, 0.42)]
        aod_values = [0.0, 0.0, 0.36]

        with (
            patch.object(data_pipeline, "GEE_AVAILABLE", True),
            patch.object(data_pipeline, "_fetch_openmeteo_forecast", return_value=raw),
            patch.object(data_pipeline, "_extract_72h_window", return_value=atmospheric),
            patch.object(data_pipeline, "_extract_soil_moisture", return_value=0.17),
            patch.object(data_pipeline, "_fetch_smap_gee", side_effect=smap_values),
            patch.object(data_pipeline, "_fetch_modis_aod_gee", side_effect=aod_values),
            patch.object(data_pipeline, "_fetch_cams_aod", return_value=(0.0, None)),
        ):
            _, surface, provenance, _ = await data_pipeline.build_prediction_inputs(
                13.51, 2.11, target, ImmediateExecutor()
            )

        self.assertEqual(surface[:3], [0.11, 0.42, 0.36])
        self.assertEqual(provenance["soil_moisture"]["observed_at"], "2026-07-19")
        self.assertEqual(provenance["previous_day_aod"]["observed_at"], "2026-07-18")
        self.assertFalse(provenance["degraded"])

    async def test_current_cams_aod_fills_recent_modis_ingestion_gap(self):
        target = datetime(2026, 7, 24, tzinfo=timezone.utc)
        atmospheric = [[0.0] * 7 for _ in range(72)]
        with (
            patch.object(data_pipeline, "GEE_AVAILABLE", True),
            patch.object(data_pipeline, "_fetch_openmeteo_forecast", return_value={"hourly": {}}),
            patch.object(data_pipeline, "_extract_72h_window", return_value=atmospheric),
            patch.object(data_pipeline, "_fetch_smap_gee", return_value=(0.12, 0.3)),
            patch.object(data_pipeline, "_fetch_modis_aod_gee", return_value=0.0),
            patch.object(data_pipeline, "_fetch_cams_aod", return_value=(0.23, "2026-07-23T00:00:00Z")),
        ):
            _, surface, provenance, _ = await data_pipeline.build_prediction_inputs(
                13.51, 2.11, target, ImmediateExecutor()
            )

        self.assertEqual(surface[2], 0.23)
        self.assertEqual(provenance["previous_day_aod"]["source"], "cams-global")
        self.assertEqual(provenance["previous_day_aod"]["kind"], "atmospheric-analysis")
        self.assertTrue(provenance["previous_day_aod"]["available"])
        self.assertFalse(provenance["degraded"])


if __name__ == "__main__":
    unittest.main()
