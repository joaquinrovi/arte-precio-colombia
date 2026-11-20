"""Comprueba los modelos opcionales cuando están instaladas sus dependencias."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from arte_precio.ml import dump_model, load_model, rank_features, train_models


HAS_SKLEARN = importlib.util.find_spec("sklearn") is not None


def feature_matrix(frame, profile="intrinseco"):
    """Aísla el contrato de features de las pruebas del preprocesamiento."""
    return frame[["dim1_cm", "missing_numeric", "artista_id"]].copy()


@unittest.skipUnless(HAS_SKLEARN, "Requiere las dependencias opcionales [ml].")
class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = pd.DataFrame(
            {
                "dim1_cm": [1.0, np.nan, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0],
                "missing_numeric": [np.nan] * 8,
                "artista_id": ["ana", "ana", "ana", "ana", "bea", "bea", "bea", "bea"],
                "precio_venta_cop": [1e6, 1.1e6, 1.2e6, 1.3e6, 1.4e6, 1.5e6, 1.6e6, 1.7e6],
            }
        )
        cls.valid = pd.DataFrame(
            {
                "dim1_cm": [15.0, 17.0, np.nan, 19.0],
                "missing_numeric": [np.nan] * 4,
                "artista_id": ["nueva", "ana", "nueva", np.nan],
                "precio_venta_cop": [1.8e6, 1.9e6, 1.4e6, 2e6],
            }
        )
        with patch("arte_precio.ml.build_features", side_effect=feature_matrix):
            cls.models, cls.metrics = train_models(
                cls.train, cls.valid, profile="intrinseco", seed=7, quick=True
            )

    def test_imputation_and_categories_learn_only_from_training(self):
        pipeline = self.models["ridge_log"].regressor_
        prep = pipeline.named_steps["preprocessor"]
        imputer = prep.named_transformers_["numeric"].named_steps["imputer"]
        self.assertAlmostEqual(imputer.statistics_[0], 7.0)
        self.assertEqual(imputer.statistics_[1], 0.0)
        self.assertTrue(imputer.keep_empty_features)
        self.assertTrue(imputer.add_indicator)
        encoder = prep.named_transformers_["categorical"].named_steps["encoder"]
        self.assertNotIn("nueva", encoder.categories_[0])
        self.assertEqual(set(encoder.categories_[0]), {"ana", "bea"})

    def test_unseen_categories_and_missing_values_predict_in_cop(self):
        matrix = feature_matrix(self.valid)
        for name, model in self.models.items():
            with self.subTest(model=name):
                prediction = model.predict(matrix)
                self.assertEqual(prediction.shape, (4,))
                self.assertTrue(np.isfinite(prediction).all())
                self.assertTrue((prediction > 0).all())
        self.assertEqual(
            {row["model"] for row in self.metrics},
            {"ridge_log", "random_forest_log"},
        )

    def test_permutation_reports_original_features(self):
        with patch("arte_precio.ml.build_features", side_effect=feature_matrix):
            result = rank_features(
                self.models["ridge_log"], self.valid, "intrinseco", seed=7, repeats=2
            )
        self.assertEqual(set(result["feature"]), set(feature_matrix(self.valid)))
        self.assertEqual(
            list(result.columns),
            ["feature", "mae_increase_cop_mean", "mae_increase_cop_std"],
        )
        self.assertTrue(np.isfinite(result.iloc[:, 1:].to_numpy()).all())

    def test_model_roundtrip_preserves_predictions(self):
        matrix = feature_matrix(self.valid)
        original = self.models["ridge_log"]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "nested" / "model.joblib"
            self.assertEqual(dump_model(original, destination), destination)
            restored = load_model(destination)
            np.testing.assert_allclose(original.predict(matrix), restored.predict(matrix))


if __name__ == "__main__":
    unittest.main()
