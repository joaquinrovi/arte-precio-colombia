"""Entrena sobre precios publicados de una galería y valida con artistas nuevos."""

import argparse
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import pickle
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arte_precio.benchmark import MedianRegressor  # noqa: E402
from arte_precio.candidates import (  # noqa: E402
    GradientTreeBoostingRegressor,
    SplineAdditiveRegressor,
    WeightedNeighborRegressor,
)
from arte_precio.dataset import sha256_file, write_json  # noqa: E402
from arte_precio.evaluation import regression_metrics  # noqa: E402

SOURCE = "https://lagaleriaonline.co/collections/obras"
TARGET = "precio_publicado_cop"
COMMISSION_TECHNIQUES = ("oleo", "grafito")
SOURCE_COLUMNS = ("artist", "technique", "support", "width_cm", "height_cm", "year",
                  "price_cop", "url", "availability")
BASE_FEATURES = ("technique", "log_area_cm2", "log_aspect")
PROFILES = {
    "tecnica_dimensiones": BASE_FEATURES,
    "con_soporte": (*BASE_FEATURES, "support"),
    "con_anio": (*BASE_FEATURES, "year"),
    "con_soporte_y_anio": (*BASE_FEATURES, "support", "year"),
}
FEATURE_GROUPS = {
    "Dimensiones": ("log_area_cm2", "log_aspect"),
    "Técnica": ("technique",),
    "Soporte": ("support",),
    "Año de creación": ("year",),
}


class TechniqueMedianRegressor:
    def fit(self, features: pd.DataFrame, price: np.ndarray):
        self.price = float(np.median(price))
        series = pd.Series(price, index=features.index)
        self.by_technique = series.groupby(features["technique"]).median().to_dict()
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return features["technique"].map(self.by_technique).fillna(self.price).to_numpy(dtype=float)


MODELS = {
    "global_median": (
        "Mediana global", None, ({},),
    ),
    "technique_median": (
        "Mediana por técnica", TechniqueMedianRegressor, ({},),
    ),
    "spline_additive_log": (
        "Modelo aditivo con splines", SplineAdditiveRegressor,
        tuple({"penalty": penalty, "n_knots": knots}
              for penalty in (0.5, 3.0, 12.0) for knots in (0, 3)),
    ),
    "knn_weighted_log": (
        "Vecinos cercanos ponderados (KNN)", WeightedNeighborRegressor,
        tuple({"neighbors": neighbors} for neighbors in (5, 15, 35)),
    ),
    "boosting_numpy_log": (
        "Gradient Boosting", GradientTreeBoostingRegressor,
        tuple({"rounds": rounds, "learning_rate": rate, "min_leaf": leaf}
              for rounds, rate in ((35, 0.12), (70, 0.08)) for leaf in (6, 15)),
    ),
}
BASELINES = {"global_median", "technique_median"}


def normalized_artist(value: str) -> str:
    # Los cambios de orden, acentos y mayúsculas no separan observaciones del mismo artista.
    plain = unicodedata.normalize("NFKD", str(value)).casefold()
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return " ".join(sorted(re.findall(r"[^\W_]+", plain)))


def product_key(value: str) -> str:
    try:
        url = urlsplit(str(value).strip())
    except ValueError:
        return ""
    if url.scheme != "https" or url.hostname not in {"lagaleriaonline.co", "www.lagaleriaonline.co"}:
        return ""
    path = unquote(url.path).rstrip("/")
    return path.split("/products/", 1)[1].casefold() if "/products/" in path else ""


def load_catalog(path: Path) -> tuple[pd.DataFrame, dict]:
    original = pd.read_csv(path, usecols=list(SOURCE_COLUMNS), keep_default_na=False)
    rows = original.copy()
    rows["product"] = rows["url"].map(product_key)
    rows["artist_group"] = rows["artist"].map(normalized_artist)
    for column in ("technique", "support", "availability"):
        rows[column] = rows[column].astype("string").str.strip().str.lower().replace("", pd.NA)
    for column in ("width_cm", "height_cm", "price_cop", "year"):
        values = pd.to_numeric(rows[column], errors="coerce").astype(float)
        rows[column] = values.where(np.isfinite(values) & values.gt(0))
    valid_year = rows["year"].between(1, 9999) & (rows["year"] % 1 == 0)
    rows["year"] = rows["year"].where(valid_year)

    required = rows[["technique", "width_cm", "height_cm", "price_cop"]].notna().all(axis=1)
    rows = rows.loc[required & rows["product"].ne("") & rows["artist_group"].ne("")].copy()
    invalid = len(original) - len(rows)
    identity = ["artist_group", "technique", "width_cm", "height_cm", "price_cop"]
    versions = rows.groupby("product")[identity].nunique()
    conflicting = versions.index[versions.gt(1).any(axis=1)]
    conflicted_rows = rows["product"].isin(conflicting)
    excluded_conflicts = int(conflicted_rows.sum())
    rows = rows.loc[~conflicted_rows]
    unique = rows.drop_duplicates(subset="product").sort_values("product").reset_index(drop=True)
    summary = {
        "input_rows": len(original),
        "excluded_invalid_rows": invalid,
        "excluded_conflicting_rows": excluded_conflicts,
        "excluded_duplicate_rows": len(rows) - len(unique),
        "availability": {str(key): int(count) for key, count in unique["availability"]
                         .fillna("sin_indicar").value_counts().items()},
    }
    return unique, summary


def create_features(rows: pd.DataFrame) -> pd.DataFrame:
    width = np.log(rows["width_cm"])
    height = np.log(rows["height_cm"])
    return pd.DataFrame({
        "technique": rows["technique"],
        "log_area_cm2": np.logaddexp(0, width + height),
        "log_aspect": (width - height).abs(),
        "support": rows["support"],
        "year": rows["year"],
    }, index=rows.index)


def split_artists(rows: pd.DataFrame, seed: int) -> tuple[np.ndarray, np.ndarray]:
    artists = np.array(sorted(rows["artist_group"].unique()))
    if len(artists) < 5:
        raise ValueError("Se requieren cinco artistas: al menos tres para CV y dos para prueba.")
    shuffled = np.random.default_rng(seed).permutation(artists)
    test_artists = shuffled[:max(2, round(len(artists) * 0.2))]
    test_mask = rows["artist_group"].isin(test_artists).to_numpy()
    return np.flatnonzero(~test_mask), np.flatnonzero(test_mask)


def grouped_folds(groups: pd.Series, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    counts = groups.value_counts().sort_index()
    rng = np.random.default_rng(seed)
    artists = sorted(rng.permutation(counts.index), key=counts.get, reverse=True)
    fold_loads = np.zeros(min(5, len(artists)), dtype=int)
    artist_to_fold = {}
    for artist in artists:
        fold = int(fold_loads.argmin())
        artist_to_fold[artist] = fold
        fold_loads[fold] += counts[artist]
    assignments = groups.map(artist_to_fold).to_numpy()
    return [(np.flatnonzero(assignments != fold), np.flatnonzero(assignments == fold))
            for fold in range(len(fold_loads))]


def make_model(model_id: str, params: dict):
    factory = MODELS[model_id][1]
    if factory is None:
        return MedianRegressor(by_artist=False, prior_weight=0)
    return factory(**params)


def cross_validate(model_id: str, params: dict, features: pd.DataFrame, target: np.ndarray,
                   folds: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
    predictions = np.empty(len(features))
    for train, heldout in folds:
        model = make_model(model_id, params).fit(features.iloc[train], target[train])
        predictions[heldout] = model.predict(features.iloc[heldout])
    return predictions


def select_settings(features: pd.DataFrame, target: np.ndarray, folds) -> tuple[list, list]:
    focus = features["technique"].isin(COMMISSION_TECHNIQUES).to_numpy(dtype=bool)
    grid = []
    tuned = []
    for model_id, (label, _, grid_params) in MODELS.items():
        profiles = tuple(PROFILES) if model_id not in BASELINES else (next(iter(PROFILES)),)
        best = None
        for profile in profiles:
            matrix = features[list(PROFILES[profile])]
            for params in grid_params:
                predictions = cross_validate(model_id, params, matrix, target, folds)
                scores = regression_metrics(target, predictions)
                result = {"model_id": model_id, "model": label, "feature_profile": profile,
                          "params": params, "cv": scores,
                          "cv_focus": regression_metrics(target[focus], predictions[focus])}
                grid.append(result)
                if best is None or result["cv_focus"]["mae_cop"] < best["cv_focus"]["mae_cop"]:
                    best = result
        tuned.append(best)
    return sorted(tuned, key=lambda setting: setting["cv_focus"]["mae_cop"]), grid


def permutation_importance(setting: dict, features: pd.DataFrame, target: np.ndarray, folds,
                           *, seed: int, repeats: int = 5) -> pd.DataFrame:
    columns = ["grupo", "columnas", "aumento_mae_cop", "desviacion_aumento_cop"]
    if setting["model_id"] in BASELINES:
        return pd.DataFrame(columns=columns)
    matrix = features[list(PROFILES[setting["feature_profile"]])]
    focus = features["technique"].isin(COMMISSION_TECHNIQUES).to_numpy(dtype=bool)
    groups = {name: [col for col in group_columns if col in matrix]
              for name, group_columns in FEATURE_GROUPS.items()}
    groups = {name: group_columns for name, group_columns in groups.items() if group_columns}
    errors = {name: np.zeros(repeats) for name in groups}
    rng = np.random.default_rng(seed)
    for train, heldout in folds:
        relevant = heldout[focus[heldout]]
        if not len(relevant):
            continue
        model = make_model(setting["model_id"], setting["params"]).fit(
            matrix.iloc[train], target[train],
        )
        observed = matrix.iloc[relevant]
        orders = [rng.permutation(len(relevant)) for _ in range(repeats)]
        for name, feature_names in groups.items():
            for repeat, order in enumerate(orders):
                permuted = observed.copy()
                for col in feature_names:
                    permuted[col] = observed[col].array[order]
                errors[name][repeat] += np.abs(target[relevant] - model.predict(permuted)).sum()
    baseline_mae = setting["cv_focus"]["mae_cop"]
    count = int(focus.sum())
    values = [(name, ", ".join(groups[name]), values.mean() / count - baseline_mae,
               values.std() / count) for name, values in errors.items()]
    return pd.DataFrame(values, columns=columns).sort_values("aumento_mae_cop", ascending=False)


def by_technique(rows: pd.DataFrame, target: np.ndarray, predictions: np.ndarray) -> dict:
    result = {}
    for technique, slots in rows.groupby("technique").indices.items():
        result[technique] = {
            "artists": int(rows.iloc[slots]["artist_group"].nunique()),
            **regression_metrics(target[slots], predictions[slots]),
        }
    return result


def model_coverage(rows: pd.DataFrame) -> dict:
    coverage = {}
    for technique, group in rows.groupby("technique"):
        sizes = group[["width_cm", "height_cm"]].to_numpy()
        short = sizes.min(axis=1)
        long = sizes.max(axis=1)
        coverage[technique] = {
            "rows": len(group), "artists": int(group["artist_group"].nunique()),
            "short_side_cm": [float(short.min()), float(short.max())],
            "long_side_cm": [float(long.min()), float(long.max())],
            "support": sorted(str(value) for value in group["support"].dropna().unique()),
        }
    return coverage


def export_parameters(model, setting: dict, rows: pd.DataFrame, metadata: dict) -> dict | None:
    # KNN necesita los precios observados y los rasgos de cada vecino en la inferencia.
    if setting["model_id"] == "knn_weighted_log":
        return None
    payload = {
        "version": 1, "target": TARGET, "source": SOURCE,
        "model_id": setting["model_id"], "feature_profile": setting["feature_profile"],
        "feature_columns": list(PROFILES[setting["feature_profile"]]),
        "coverage": model_coverage(rows), "metadata": metadata,
    }
    if isinstance(model, MedianRegressor):
        return {**payload, "price": model.baseline.global_}
    if isinstance(model, TechniqueMedianRegressor):
        return {**payload, "price": model.price, "by_technique": model.by_technique}
    numeric = [{**asdict(col), "knots": col.knots.tolist()}
               for col in model.encoder_.numeric]
    payload.update({
        "log_target_bounds": list(model.bounds_), "numeric": numeric,
        "categories": model.encoder_.categories,
    })
    if isinstance(model, SplineAdditiveRegressor):
        return {**payload, "coefficients": model.coefficients_.tolist()}
    return {**payload, "initial": model.initial_, "learning_rate": model.learning_rate,
            "rules": [asdict(rule) for rule in model.rules_],
            "trees": [asdict(tree) for tree in model.trees_]}


def flatten_metrics(result: dict) -> dict:
    return {
        "model_id": result["model_id"], "model": result["model"],
        "feature_profile": result["feature_profile"],
        "params": json.dumps(result["params"], sort_keys=True),
        **{f"cv_{name}": value for name, value in result["cv"].items()},
        **{f"cv_focus_{name}": value for name, value in result["cv_focus"].items()},
        **{f"test_{name}": value for name, value in result.get("test", {}).items()},
        **{f"test_focus_{name}": value for name, value in result.get("test_focus", {}).items()},
    }


def train(input_path: Path, run: str, seed: int, checked_at: str | None) -> dict:
    data_fingerprint = sha256_file(input_path)
    rows, ingest = load_catalog(input_path)
    if sha256_file(input_path) != data_fingerprint:
        raise ValueError("El catálogo cambió mientras se estaba leyendo.")
    train_slots, test_slots = split_artists(rows, seed)
    features = create_features(rows)
    train_rows, test_rows = rows.iloc[train_slots], rows.iloc[test_slots]
    train_x, test_x = features.iloc[train_slots], features.iloc[test_slots]
    train_y = train_rows["price_cop"].to_numpy()
    test_y = test_rows["price_cop"].to_numpy()
    focus = test_rows["technique"].isin(COMMISSION_TECHNIQUES).to_numpy(dtype=bool)
    if not focus.any() or not train_rows["technique"].isin(COMMISSION_TECHNIQUES).any():
        raise ValueError("La muestra necesita fichas de óleo o grafito en desarrollo y prueba.")
    folds = grouped_folds(train_rows["artist_group"], seed)
    comparison, grid = select_settings(train_x, train_y, folds)
    selected = comparison[0]
    importance_setting = next(row for row in comparison if row["model_id"] not in BASELINES)
    importance = permutation_importance(importance_setting, train_x, train_y, folds, seed=seed)

    trained_models = {}
    test_predictions = {}
    for setting in comparison:
        key = setting["model_id"]
        cols = list(PROFILES[setting["feature_profile"]])
        model = make_model(key, setting["params"]).fit(train_x[cols], train_y)
        prediction = model.predict(test_x[cols])
        setting["test"] = regression_metrics(test_y, prediction)
        setting["test_focus"] = regression_metrics(test_y[focus], prediction[focus])
        trained_models[key] = model
        test_predictions[key] = prediction

    winner_id = selected["model_id"]
    winner_x = train_x[list(PROFILES[selected["feature_profile"]])]
    winner_cv = cross_validate(winner_id, selected["params"], winner_x, train_y, folds)
    baseline_cv = cross_validate("global_median", {}, train_x, train_y, folds)
    groups = {
        "train_rows": len(train_rows), "train_artists": int(train_rows["artist_group"].nunique()),
        "test_rows": len(test_rows), "test_artists": int(test_rows["artist_group"].nunique()),
        "cv_folds": len(folds),
    }
    report = {
        "run": run, "source": SOURCE, "target": TARGET, "checked_at": checked_at,
        "selection_techniques": list(COMMISSION_TECHNIQUES),
        "dataset_sha256": data_fingerprint, "seed": seed, "data": ingest,
        "split": groups, "selected": selected, "models": comparison,
        "tuning_configurations": len(grid),
        "importance_model_id": importance_setting["model_id"],
        "importance_validation": importance.to_dict(orient="records"),
        "coverage_by_technique": model_coverage(train_rows),
        "cv_by_technique": by_technique(train_rows, train_y, winner_cv),
        "test_by_technique": by_technique(test_rows, test_y, test_predictions[winner_id]),
        "baseline_cv_by_technique": by_technique(train_rows, train_y, baseline_cv),
        "baseline_test_by_technique": by_technique(
            test_rows, test_y, test_predictions["global_median"],
        ),
        "technique_median_test_by_technique": by_technique(
            test_rows, test_y, test_predictions["technique_median"],
        ),
    }
    model = trained_models[winner_id]
    metadata = {"checked_at": checked_at, **groups, "test": selected["test"],
                "test_by_technique": report["test_by_technique"]}
    browser_model = export_parameters(model, selected, train_rows, metadata)
    report["browser_parameters"] = browser_model is not None

    report_dir = ROOT / "reports/runs" / run
    artifact_dir = ROOT / "artifacts" / run
    report_dir.mkdir(parents=True, exist_ok=False)
    artifact_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(map(flatten_metrics, comparison)).to_csv(report_dir / "model_comparison.csv", index=False)
    pd.DataFrame(map(flatten_metrics, grid)).to_csv(report_dir / "tuning_grid.csv", index=False)
    importance.to_csv(report_dir / "feature_importance.csv", index=False)
    test_rows.assign(**test_predictions).to_csv(report_dir / "predictions_test.csv", index=False)
    if not isinstance(model, TechniqueMedianRegressor):
        artifact = {"model": model, "feature_columns": list(PROFILES[selected["feature_profile"]]),
                    "model_id": winner_id, "target": TARGET}
        with (artifact_dir / "model.pkl").open("wb") as handle:
            pickle.dump(artifact, handle)
    if browser_model is not None:
        write_json(artifact_dir / "model.json", browser_model)
    write_json(report_dir / "metrics.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="CSV local del catálogo de galería")
    parser.add_argument("--run", required=True, help="Nombre nuevo para guardar la corrida")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checked-at", type=date.fromisoformat,
                        help="Fecha de consulta del catálogo (AAAA-MM-DD)")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run):
        parser.error("--run solo admite letras, números, guiones y guiones bajos")
    if any((ROOT / folder / args.run).exists() for folder in ("reports/runs", "artifacts")):
        parser.error("La corrida ya existe. Usa otro nombre para conservar los resultados anteriores.")
    if args.seed < 0:
        parser.error("--seed debe ser no negativa")
    checked_at = args.checked_at.isoformat() if args.checked_at else None
    report = train(args.input, args.run, args.seed, checked_at)
    selected = report["selected"]
    print(f'{selected["model"]} | {selected["feature_profile"]}')
    print(f'MAE CV (óleo y grafito): {selected["cv_focus"]["mae_cop"]:,.0f} COP')
    print(f'MAE prueba (óleo y grafito): {selected["test_focus"]["mae_cop"]:,.0f} COP')
    print(ROOT / "reports/runs" / args.run / "metrics.json")


if __name__ == "__main__":
    main()
