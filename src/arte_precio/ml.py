"""Modelos opcionales con preprocesamiento ajustado solo al entrenamiento."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .evaluation import regression_metrics
from .features import build_features


_DEPENDENCY_MESSAGE = (
    "Las dependencias opcionales de aprendizaje automático no están disponibles. "
    'Instálalas con: python -m pip install -e ".[ml]"'
)


def _target(frame: pd.DataFrame) -> np.ndarray:
    values = pd.to_numeric(frame["precio_venta_cop"], errors="raise").to_numpy(
        dtype=float
    )
    if not len(values) or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("El target debe contener precios positivos y finitos.")
    return values


def train_models(
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    profile: str,
    seed: int = 42,
    quick: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Entrena dos candidatos y los evalúa sin reajustarlos con validación.

    Los modelos retornados reciben ``build_features(frame, profile)`` al predecir.
    Las predicciones y las métricas están expresadas en COP nominales.
    """
    try:
        from sklearn.base import clone
        from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except ImportError as exc:
        raise RuntimeError(_DEPENDENCY_MESSAGE) from exc

    x_train = build_features(train_df, profile=profile)
    x_valid = build_features(valid_df, profile=profile)
    if x_train.empty or list(x_train.columns) != list(x_valid.columns):
        raise ValueError("Entrenamiento y validación requieren las mismas features.")
    y_train, y_valid = _target(train_df), _target(valid_df)
    numeric = x_train.select_dtypes(include="number").columns.tolist()
    categorical = [name for name in x_train.columns if name not in numeric]
    preprocessing = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        (
                            "imputer",
                            SimpleImputer(
                                strategy="median",
                                add_indicator=True,
                                keep_empty_features=True,
                            ),
                        ),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            (
                "categorical",
                Pipeline(
                    [
                        (
                            "imputer",
                            SimpleImputer(
                                strategy="constant",
                                fill_value="__sin_informacion__",
                                keep_empty_features=True,
                            ),
                        ),
                        (
                            "encoder",
                            OneHotEncoder(
                                handle_unknown="ignore", sparse_output=False
                            ),
                        ),
                    ]
                ),
                categorical,
            ),
        ],
        remainder="drop",
        sparse_threshold=0,
    )
    estimators = {
        "ridge_log": Ridge(alpha=10.0, solver="lsqr"),
        "random_forest_log": RandomForestRegressor(
            n_estimators=32 if quick else 300,
            min_samples_leaf=3,
            max_features=0.8,
            random_state=seed,
            n_jobs=1,
        ),
    }
    fitted: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for name, estimator in estimators.items():
        model = TransformedTargetRegressor(
            regressor=Pipeline(
                [
                    ("preprocessor", clone(preprocessing)),
                    ("regressor", estimator),
                ]
            ),
            func=np.log1p,
            inverse_func=np.expm1,
            check_inverse=True,
        )
        model.fit(x_train, y_train)
        prediction = np.asarray(model.predict(x_valid), dtype=float)
        fitted[name] = model
        rows.append({"model": name, **regression_metrics(y_valid, prediction)})
    return fitted, rows


def rank_features(
    model: Any,
    valid_frame: pd.DataFrame,
    profile: str,
    seed: int = 42,
    repeats: int = 5,
) -> pd.DataFrame:
    """Permuta las features originales y mide el aumento de MAE en validación.

    Un valor negativo puede deberse a ruido o redundancia. Esta operación no
    reajusta el modelo ni convierte una importancia predictiva en causalidad.
    """
    try:
        from sklearn.inspection import permutation_importance
    except ImportError as exc:
        raise RuntimeError(_DEPENDENCY_MESSAGE) from exc
    if repeats < 1:
        raise ValueError("repeats debe ser al menos 1.")
    matrix = build_features(valid_frame, profile=profile)
    result = permutation_importance(
        model,
        matrix,
        _target(valid_frame),
        scoring=_negative_mae,
        n_repeats=repeats,
        random_state=seed,
        n_jobs=1,
    )
    return (
        pd.DataFrame(
            {
                "feature": matrix.columns,
                "mae_increase_cop_mean": result.importances_mean,
                "mae_increase_cop_std": result.importances_std,
            }
        )
        .sort_values("mae_increase_cop_mean", ascending=False, kind="stable")
        .reset_index(drop=True)
    )


def _negative_mae(estimator, matrix, target) -> float:
    """La misma regla de predicción no negativa que la selección por MAE."""
    return -regression_metrics(target, estimator.predict(matrix))["mae_cop"]


def dump_model(model: Any, path: str | Path) -> Path:
    """Guarda el estimador y su preprocesamiento ya ajustados."""
    try:
        import joblib
    except ImportError as exc:
        raise RuntimeError(_DEPENDENCY_MESSAGE) from exc
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, destination)
    return destination


def load_model(path: str | Path) -> Any:
    """Carga un modelo local de procedencia confiable."""
    try:
        import joblib
    except ImportError as exc:
        raise RuntimeError(_DEPENDENCY_MESSAGE) from exc
    return joblib.load(Path(path))
