import unittest
from unittest.mock import patch

import pandas as pd

from arte_precio.tuning import search_spline


class SplineTuningTests(unittest.TestCase):
    def test_uses_only_past_auctions_in_each_year(self):
        lots = pd.DataFrame({
            "fecha_subasta": ["2020-01-01"] * 2 + ["2021-02-01"] * 2 + ["2022-03-01"] * 2,
            "precio_venta_cop": [100, 200, 300, 400, 500, 600],
            "dim1_cm": [1, 2, 3, 4, 5, 6],
            "artista_id": ["a", "a", "a", "b", "a", "c"],
        })
        changed = lots.copy()
        changed.loc[4:, ["dim1_cm", "precio_venta_cop"]] *= 100_000
        with patch("arte_precio.tuning.PENALTIES", (1.0, 8.0)), patch(
            "arte_precio.tuning.KNOT_COUNTS", (1, 3),
        ):
            ranking, by_year = search_spline(lots, "intrinseco")
            _, changed_by_year = search_spline(changed, "intrinseco")

        first_year = by_year["validation_year"].eq(2021)
        pd.testing.assert_frame_equal(by_year[first_year], changed_by_year[first_year])
        self.assertEqual(set(by_year["validation_year"]), {2021, 2022})
        self.assertEqual(set(by_year[first_year]["train_rows"]), {2})
        self.assertEqual(set(by_year[~first_year]["train_rows"]), {4})
        self.assertEqual(set(by_year["validation_auctions"]), {1})
        self.assertEqual(ranking["n"].tolist(), [4, 4, 4, 4])
        self.assertTrue(ranking["mae_cop"].is_monotonic_increasing)


if __name__ == "__main__":
    unittest.main()
