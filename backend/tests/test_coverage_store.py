import unittest
from unittest.mock import patch

import coverage_store


class CoverageStoreTests(unittest.TestCase):
    @patch("coverage_store._using_postgres", return_value=False)
    def test_fallback_search_is_case_insensitive(self, _using_postgres):
        rows = coverage_store.list_covered_places(query="nIGeR")
        self.assertTrue(rows)
        self.assertTrue(all("niger" in row["country"].lower() for row in rows))

    @patch("coverage_store._using_postgres", return_value=False)
    def test_nearest_place_uses_catalogue(self, _using_postgres):
        place = coverage_store.nearest_covered_place(13.50, 2.10)
        self.assertEqual(place["name"], "Niamey")

    @patch("coverage_store._using_postgres", return_value=False)
    def test_worker_fallback_has_unique_cells(self, _using_postgres):
        cells = coverage_store.list_active_forecast_cells()
        keys = {cell["cell_key"] for cell in cells}
        self.assertEqual(len(cells), len(keys))


if __name__ == "__main__":
    unittest.main()
