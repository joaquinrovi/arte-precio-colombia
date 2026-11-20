import tempfile
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from arte_precio.baseline import MedianBaseline
from arte_precio.dataset import load_source, prepare_dataset, select_model_rows, validate_source
from arte_precio.evaluation import regression_metrics
from arte_precio.features import FORBIDDEN, build_features
from arte_precio.splits import temporal_split


def sample():
    dates = ["2024-05-01", "2024-05-01", "2025-05-01", "2025-05-01", "2026-05-01", "2026-05-01"]
    return pd.DataFrame({
        "registro_id": [f"S-{i}" for i in range(6)],
        "precio_venta_cop": [100, 300, 10000, 20000, 900000, 800000],
        "moneda_original": "COP", "fecha_subasta": dates,
        "artista_id": ["ana", "ana", "bea", "ana", "bea", "nueva"],
        "tecnica_grupo": "Óleo", "dim1_cm": 20.0, "dim2_cm": 30.0,
        "diametro_cm": np.nan, "lote_multiple": np.nan, "usar_modelo_base": 1,
        "motivo_revision": None, "fuente_resultado_url": "https://example.org/lot",
        "firma_mencionada": [1, 0, np.nan, 1, np.nan, 1],
        "anio_obra": 2000, "precision_anio_obra": "exacto_publicado",
    })


class DatasetTests(unittest.TestCase):
    def test_validation_rejects_duplicate_ids(self):
        frame = sample()
        frame.loc[1, "registro_id"] = frame.loc[0, "registro_id"]
        with self.assertRaisesRegex(ValueError, "único"):
            validate_source(frame)

    def test_validation_rejects_nonpositive_target_and_wrong_currency(self):
        for column, value in [("precio_venta_cop", 0), ("moneda_original", "USD"), ("dim1_cm", -3)]:
            frame = sample()
            frame.loc[0, column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                validate_source(frame)

    def test_selection_excludes_multiple_and_open_post_sale(self):
        frame = sample()
        frame.loc[0, "lote_multiple"] = 1
        frame.loc[1, "motivo_revision"] = "Adjudicación reciente: posventa abierta"
        selected, _ = select_model_rows(frame)
        self.assertEqual(selected["registro_id"].tolist(), ["S-2", "S-3", "S-4", "S-5"])
        selected, _ = select_model_rows(frame, exclude_open_post_sale=False)
        self.assertIn("S-1", selected["registro_id"].tolist())

    def test_invalid_dimension_text_is_not_silently_missing(self):
        frame = sample()
        frame["dim1_cm"] = frame["dim1_cm"].astype(object)
        frame.loc[0, "dim1_cm"] = "abc"
        with self.assertRaisesRegex(ValueError, "no numéricas"):
            validate_source(frame)

    def test_xlsx_roundtrip_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.xlsx"
            sample().to_excel(source, sheet_name="Ventas", index=False)
            output = Path(directory) / "clean.csv"
            report = prepare_dataset(source, output, {})
            self.assertEqual(report["selection"]["selected_rows"], 6)
            self.assertEqual(len(report["source_sha256"]), 64)
            self.assertTrue(output.with_suffix(".manifest.json").exists())
            self.assertEqual(len(load_source(output)), 6)


class SplitTests(unittest.TestCase):
    def test_no_date_or_id_crosses_a_split(self):
        train, valid, test = temporal_split(sample())
        self.assertEqual([len(x) for x in [train, valid, test]], [2, 2, 2])
        for left, right in [(train, valid), (valid, test), (train, test)]:
            self.assertFalse(set(left["fecha_subasta"]) & set(right["fecha_subasta"]))
            self.assertFalse(set(left["registro_id"]) & set(right["registro_id"]))

    def test_bad_cutoffs_and_empty_period_fail(self):
        with self.assertRaises(ValueError):
            temporal_split(sample(), "2026-12-31", "2025-12-31")
        with self.assertRaises(ValueError):
            temporal_split(sample(), "2023-12-31", "2025-12-31")


class FeatureTests(unittest.TestCase):
    def test_whitelist_excludes_target_and_reference_prices(self):
        frame = sample().assign(precio_salida_cop=999999, estimado_min_cop=1)
        features = build_features(frame)
        self.assertFalse(FORBIDDEN.intersection(features.columns))
        self.assertFalse(any("precio" in x or "estimado" in x for x in features.columns))
        with_prices = build_features(frame, "con_avaluo")
        self.assertIn("log_precio_salida_cop", with_prices)

    def test_unknown_documentation_is_different_from_explicit_zero(self):
        features = build_features(sample(), "documentado")
        self.assertEqual(features["firma_mencionada"].iloc[:3].tolist(),
                         ["mencionado", "cero_explicito", "sin_informacion"])

    def test_without_artist_and_invalid_year(self):
        frame = sample()
        frame.loc[0, "anio_obra"] = 2035
        frame.loc[1, "precision_anio_obra"] = "decada_o_periodo"
        features = build_features(frame, "sin_artista")
        self.assertNotIn("artista", features)
        self.assertTrue(features.loc[:1, "anio_obra"].isna().all())

    def test_features_do_not_depend_on_target_values(self):
        original = sample()
        modified = original.assign(precio_venta_cop=1e12)
        pd.testing.assert_frame_equal(build_features(original), build_features(modified))


class BaselineTests(unittest.TestCase):
    def test_no_validation_target_leakage_and_new_artist_fallback(self):
        train, valid, _ = temporal_split(sample())
        model = MedianBaseline(by_artist=True).fit(train)
        np.testing.assert_allclose(model.predict(valid), [200, 200])
        valid["precio_venta_cop"] = 10**12
        np.testing.assert_allclose(model.predict(valid), [200, 200])

    def test_metrics_are_in_cop(self):
        result = regression_metrics([100, 200], [80, 230])
        self.assertEqual(result["mae_cop"], 25)
        self.assertEqual(result["median_absolute_error_cop"], 25)
        self.assertAlmostEqual(result["rmse_cop"], np.sqrt(650))

    def test_predictive_quality_metrics_with_equal_price_and_relative_tolerance(self):
        result = regression_metrics([100, 100], [75, 126])
        self.assertIsNone(result["r2"])
        self.assertEqual(result["within_25_pct"], 50)
        self.assertEqual(result["median_absolute_percentage_error_pct"], 25.5)
        self.assertAlmostEqual(regression_metrics([100, 200], [80, 230])["r2"], 0.74)

    def test_nonfinite_prediction_rejected(self):
        with self.assertRaises(ValueError):
            regression_metrics([100], [np.nan])


if __name__ == "__main__":
    unittest.main()
