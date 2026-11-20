"""Compara regresores en una validación temporal común."""

import importlib.util

import numpy as np
import pandas as pd

from .baseline import MedianBaseline
from .candidates import candidate_factories
from .evaluation import regression_metrics
from .features import build_features

MODEL_LABELS = {
    "global_median": "Mediana global",
    "artist_median_shrunk": "Mediana por artista suavizada",
    "spline_additive_log": "Modelo aditivo con splines",
    "knn_weighted_log": "Vecinos cercanos ponderados (KNN)",
    "boosting_numpy_log": "Gradient Boosting de árboles poco profundos",
    "ridge_log": "Ridge",
    "random_forest_log": "Random Forest",
    "extra_trees_log": "Extra Trees",
    "gradient_boosting_log": "Gradient Boosting",
    "svr_rbf_log": "SVR con kernel RBF",
}
SKLEARN_MODELS = (
    "ridge_log", "random_forest_log", "extra_trees_log", "gradient_boosting_log", "svr_rbf_log",
)


class MedianRegressor:
    """Adapta la referencia existente a la misma interfaz de los demás modelos."""

    def __init__(self, by_artist: bool, prior_weight: float):
        self.baseline = MedianBaseline(by_artist, prior_weight)

    def fit(self, features: pd.DataFrame, price: np.ndarray):
        self.baseline.fit(pd.DataFrame({
            "artista_id": features.get("artista"), "precio_venta_cop": price,
        }, index=features.index))
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return self.baseline.predict(pd.DataFrame({"artista_id": features.get("artista")},
                                                  index=features.index))


def fit_comparison(
    train: pd.DataFrame, validation: pd.DataFrame, profile: str, prior_weight: float,
    seed: int = 42, quick: bool = False,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, list[str]]:
    x_train = build_features(train, profile)
    x_validation = build_features(validation, profile)
    y_train = train["precio_venta_cop"].to_numpy(dtype=float)
    y_validation = validation["precio_venta_cop"].to_numpy(dtype=float)
    factories = {"global_median": lambda: MedianRegressor(False, prior_weight)}
    if "artista" in x_train:
        factories["artist_median_shrunk"] = lambda: MedianRegressor(True, prior_weight)
    factories.update(candidate_factories(seed=seed, quick=quick))
    unavailable = []
    if importlib.util.find_spec("sklearn") is not None:
        from .ml import sklearn_factories

        factories.update(sklearn_factories(x_train, seed, quick, extended=True))
    else:
        unavailable = list(SKLEARN_MODELS)

    fitted = {}
    predictions = pd.DataFrame(index=validation.index)
    rows = []
    for name, factory in factories.items():
        model = factory().fit(x_train, y_train)
        prediction = model.predict(x_validation)
        rows.append({"model": name, "modelo": MODEL_LABELS[name],
                     **regression_metrics(y_validation, prediction)})
        fitted[name] = model
        predictions[name] = np.maximum(0, prediction)
    comparison = pd.DataFrame(rows).sort_values("mae_cop", kind="stable", ignore_index=True)
    reference_mae = comparison.loc[comparison["model"].eq("global_median"), "mae_cop"].item()
    comparison.insert(0, "rank", comparison.index + 1)
    comparison["mae_reduction_vs_global_pct"] = (
        100 * (1 - comparison["mae_cop"] / reference_mae) if reference_mae else np.nan
    )
    return fitted, comparison, predictions, unavailable


def grouped_importance(
    model, matrix: pd.DataFrame, actual: np.ndarray, *, seed: int, repeats: int,
) -> pd.DataFrame:
    """Mide el cambio de MAE al permutar juntas las columnas de un grupo."""
    if repeats < 1:
        raise ValueError("La importancia por permutación requiere al menos una repetición.")
    groups = {
        "Artista": ["artista"],
        "Técnica, soporte y tipo de obra": ["tecnica_grupo", "soporte", "tipo_objeto"],
        "Dimensiones": ["base_dimensiones", "log_dim1_cm", "log_dim2_cm", "log_dim3_cm",
                        "log_diametro_cm", "log_area_rectangular_cm2", "relacion_lados"],
        "Fechas": ["anio_venta", "anio_obra", "edad_obra_venta", "precision_anio_obra"],
        "Tiraje": ["log_edicion_total"],
        "Documentación": ["firma_mencionada", "certificado_mencionado", "procedencia_mencionada",
                          "literatura_mencionada", "exposiciones_mencionadas"],
        "Avalúo previo": ["log_precio_salida_cop", "log_estimado_min_cop", "log_estimado_max_cop"],
    }
    if isinstance(model, MedianRegressor):
        groups = {"Artista": ["artista"]} if model.baseline.by_artist else {}
    rng = np.random.default_rng(seed)
    permutations = [rng.permutation(len(matrix)) for _ in range(repeats)]
    reference = regression_metrics(actual, model.predict(matrix))["mae_cop"]
    columns = ["grupo", "columnas", "aumento_mae_cop", "desviacion_aumento_cop"]
    rows = []
    for name, group_columns in groups.items():
        included = [column for column in group_columns if column in matrix]
        if not included:
            continue
        deltas = []
        for order in permutations:
            permuted = matrix.copy()
            for column in included:
                permuted[column] = matrix[column].to_numpy()[order]
            deltas.append(regression_metrics(actual, model.predict(permuted))["mae_cop"] - reference)
        rows.append([name, ", ".join(included), float(np.mean(deltas)), float(np.std(deltas))])
    return pd.DataFrame(rows, columns=columns).sort_values("aumento_mae_cop", ascending=False)
