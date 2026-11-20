"""Selecciona hiperparámetros de splines dentro del período de entrenamiento."""

from itertools import product

import pandas as pd

from .candidates import SplineAdditiveRegressor
from .evaluation import regression_metrics
from .features import build_features

PENALTIES = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)
KNOT_COUNTS = (0, 1, 3, 5)


def search_spline(train: pd.DataFrame, profile: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ordena la rejilla por MAE por lote en años de validación crecientes."""
    dates = pd.to_datetime(train["fecha_subasta"], errors="coerce")
    if dates.isna().any() or dates.dt.year.nunique() < 2:
        raise ValueError("La búsqueda requiere fechas válidas y al menos dos años de entrenamiento.")

    years = dates.dt.year
    features = build_features(train, profile)
    prices = train["precio_venta_cop"].to_numpy(dtype=float)
    rows = []
    for year in sorted(years.unique())[1:]:
        before = (years < year).to_numpy()
        current = (years == year).to_numpy()
        x_fit, y_fit = features.loc[before], prices[before]
        x_score, y_score = features.loc[current], prices[current]
        for penalty, n_knots in product(PENALTIES, KNOT_COUNTS):
            model = SplineAdditiveRegressor(penalty=penalty, n_knots=n_knots).fit(x_fit, y_fit)
            rows.append({
                "validation_year": int(year),
                "train_rows": int(before.sum()),
                "validation_auctions": dates[current].dt.normalize().nunique(),
                "penalty": penalty,
                "n_knots": n_knots,
                **regression_metrics(y_score, model.predict(x_score)),
            })

    by_year = pd.DataFrame(rows)
    totals = (
        by_year.assign(absolute_error_cop=by_year["mae_cop"] * by_year["n"])
        .groupby(["penalty", "n_knots"], as_index=False)
        .agg(n=("n", "sum"), absolute_error_cop=("absolute_error_cop", "sum"))
    )
    totals["mae_cop"] = totals.pop("absolute_error_cop") / totals["n"]
    ranking = totals.sort_values(
        ["mae_cop", "n_knots", "penalty"], ascending=[True, True, False], ignore_index=True,
    )
    return ranking, by_year
