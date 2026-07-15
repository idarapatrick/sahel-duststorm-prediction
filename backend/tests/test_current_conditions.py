import unittest
from unittest.mock import Mock, patch

import data_pipeline


class CurrentConditionsTests(unittest.TestCase):
    @patch("data_pipeline.requests.get")
    def test_current_conditions_are_normalized_for_dashboard(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {
            "current": {
                "time": "2026-07-15T14:00",
                "interval": 900,
                "temperature_2m": 34.2,
                "relative_humidity_2m": 23,
                "apparent_temperature": 32.8,
                "dew_point_2m": 10.1,
                "precipitation": 0.0,
                "surface_pressure": 987.4,
                "wind_speed_10m": 6.5,
                "wind_direction_10m": 72,
                "wind_gusts_10m": 9.2,
                "visibility": 18000,
                "cloud_cover": 12,
                "soil_moisture_0_to_7cm": 0.084,
            }
        }
        get.return_value = response

        result = data_pipeline._fetch_openmeteo_current(13.51, 2.11)

        self.assertEqual(result["temperature_c"], 34.2)
        self.assertEqual(result["wind_speed_ms"], 6.5)
        self.assertEqual(result["wind_speed_kmh"], 23.4)
        self.assertEqual(result["soil_moisture"], 0.084)
        self.assertEqual(result["dewpoint_c"], 10.1)
        self.assertEqual(result["visibility_m"], 18000)
        params = get.call_args.kwargs["params"]
        self.assertIn("temperature_2m", params["current"])
        self.assertIn("wind_speed_10m", params["current"])

    @patch("data_pipeline.requests.get")
    def test_upstream_error_is_explicit(self, get):
        response = Mock(status_code=503, text="temporarily unavailable")
        get.return_value = response
        with self.assertRaisesRegex(RuntimeError, "Open-Meteo current conditions error"):
            data_pipeline._fetch_openmeteo_current(13.51, 2.11)


if __name__ == "__main__":
    unittest.main()
