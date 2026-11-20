import unittest

import numpy as np
import pandas as pd

from arte_precio.candidates import (
    GradientTreeBoostingRegressor,
    SplineAdditiveRegressor,
    WeightedNeighborRegressor,
    candidate_factories,
)


class CandidateTests(unittest.TestCase):
    def test_boosting_learns_interaction_between_size_and_material(self):
        cohorts = pd.DataFrame({"material": ["a", "b", "a", "b"], "size": [5, 5, 20, 20]})
        X = pd.concat([cohorts] * 20, ignore_index=True)
        prices = np.array([1, 2, 4, 20]) * 1_000_000
        model = GradientTreeBoostingRegressor().fit(X, np.tile(prices, 20))
        np.testing.assert_allclose(model.predict(cohorts), prices, rtol=0.03)

    def test_spline_learns_nonlinear_size_relationship(self):
        x = np.linspace(-2, 2, 100)
        prices = np.expm1(13 + 2 * np.abs(x))
        model = SplineAdditiveRegressor(penalty=0.05).fit(pd.DataFrame({"size": x}), prices)
        prediction = model.predict(pd.DataFrame({"size": [-1.8, 0.0, 1.8]}))
        self.assertGreater(prediction[0], 4 * prediction[1])
        self.assertGreater(prediction[2], 4 * prediction[1])

    def test_neighbor_prefers_same_artist_at_identical_sizes(self):
        X = pd.DataFrame({"artista": ["a", "b"], "size": [5, 5]})
        prices = [1_000_000, 10_000_000]
        model = WeightedNeighborRegressor(neighbors=1).fit(X, prices)
        np.testing.assert_allclose(model.predict(X.iloc[::-1]), prices[::-1])

    def test_all_candidates_handle_unseen_category_and_missing_values(self):
        train = pd.DataFrame({"artista": ["a", "a", "b"], "size": [1.0, np.nan, 3.0]})
        valid = pd.DataFrame({"artista": ["nuevo", None], "size": [100.0, np.nan]})
        for name, factory in candidate_factories().items():
            with self.subTest(name=name):
                model = factory().fit(train, [1_000_000, 2_000_000, 3_000_000])
                prediction = model.predict(valid)
                np.testing.assert_allclose(model.predict(valid.iloc[[0]]), prediction[:1])
                self.assertTrue(np.isfinite(prediction).all())
                self.assertTrue((prediction > 0).all())


if __name__ == "__main__":
    unittest.main()
