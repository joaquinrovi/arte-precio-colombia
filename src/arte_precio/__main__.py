import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import pickle
import subprocess
import sys

import numpy as np
import pandas as pd

from .baseline import MedianBaseline
from .config import PROJECT_ROOT, load_config, project_path
from .dataset import prepare_dataset, sha256_file, validate_source, write_json
from .evaluation import regression_metrics
from .features import PROFILES, build_features
from .splits import split_summary, temporal_split


def _environment() -> dict:
    versions = {}
    for name in ["numpy", "pandas", "openpyxl", "scikit-learn", "joblib"]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True
    )
    changes = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    return {"python": sys.version.split()[0], "packages": versions,
            "git_commit": git.stdout.strip() if git.returncode == 0 else None,
            "git_has_local_changes": bool(changes.stdout.strip()) if changes.returncode == 0 else None}


def _load_parts(config: dict):
    path = project_path(config["data"]["output"])
    if not path.exists():
        raise ValueError("Falta el CSV preparado. Ejecuta primero: python run.py prepare")
    frame = pd.read_csv(path)
    validate_source(frame)
    return path, temporal_split(frame, **config["split"])


def _run_paths(name: str | None) -> tuple[Path, Path, str]:
    name = name or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
        raise ValueError("run-name solo admite letras, números, guiones y guiones bajos.")
    report = PROJECT_ROOT / "reports/runs" / name
    artifact = PROJECT_ROOT / "artifacts" / name
    if report.exists() or artifact.exists():
        raise ValueError(f"La ejecución {name} ya existe; elige otro run-name.")
    report.mkdir(parents=True)
    artifact.mkdir(parents=True)
    return report, artifact, name


def _segments(train: pd.DataFrame, valid: pd.DataFrame, predictions) -> dict:
    seen = valid["artista_id"].isin(set(train["artista_id"].dropna())).to_numpy()
    result = {}
    for name, mask in [("known_artist", seen), ("new_artist", ~seen)]:
        if mask.any():
            result[name] = regression_metrics(valid["precio_venta_cop"].to_numpy()[mask], np.asarray(predictions)[mask])
    return result


def _baseline_run(config: dict, name: str | None) -> dict:
    dataset_path, (train, valid, test) = _load_parts(config)
    results, predictions, models = [], {}, {}
    for label, by_artist in [("global_median", False), ("artist_median_shrunk", True)]:
        model = MedianBaseline(by_artist, config["baseline"]["artist_prior_weight"]).fit(train)
        pred = model.predict(valid)
        models[label] = model.to_dict()
        results.append({"model": label, **regression_metrics(valid["precio_venta_cop"], pred),
                        "segments": _segments(train, valid, pred)})
        predictions[label] = pred
    report_dir, artifact_dir, run = _run_paths(name)
    table = valid[["registro_id", "precio_venta_cop"]].copy()
    for model_name, pred in predictions.items():
        table[model_name] = pred
    table.to_csv(report_dir / "validation_predictions.csv", index=False)
    write_json(artifact_dir / "baselines.json", models)
    report = {"run": run, "kind": "baseline", "environment": _environment(),
              "dataset_sha256": sha256_file(dataset_path), "split": split_summary(train, valid, test),
              "validation_metrics": results, "test_metrics_computed": False,
              "selection_metric": "mae_cop", "config": config}
    write_json(report_dir / "metrics.json", report)
    return report


def _train_run(config: dict, name: str | None, profile: str | None, quick: bool) -> dict:
    from .ml import dump_model, rank_features, train_models

    dataset_path, (train, valid, test) = _load_parts(config)
    profile = profile or config["model"]["profile"]
    models, metrics = train_models(train, valid, profile, config["model"]["seed"], quick)
    winner = min(metrics, key=lambda row: row["mae_cop"])["model"]
    importance = rank_features(models[winner], valid, profile, config["model"]["seed"],
                               2 if quick else config["model"]["permutation_repeats"])
    report_dir, artifact_dir, run = _run_paths(name)
    prediction = np.maximum(0, models[winner].predict(build_features(valid, profile)))
    valid[["registro_id", "precio_venta_cop"]].assign(prediction_cop=prediction).to_csv(
        report_dir / "validation_predictions.csv", index=False
    )
    importance.to_csv(report_dir / "feature_importance_validation.csv", index=False)
    dump_model(models[winner], artifact_dir / "model.joblib")
    report = {"run": run, "kind": "ml", "profile": profile, "winner": winner,
              "environment": _environment(), "dataset_sha256": sha256_file(dataset_path),
              "split": split_summary(train, valid, test), "validation_metrics": metrics,
              "winner_segments": _segments(train, valid, prediction),
              "features": list(build_features(train, profile)), "config": config,
              "selection_metric": "mae_cop", "test_metrics_computed": False,
              "importance_scope": "Exploratoria sobre validación; no usa la prueba final."}
    write_json(report_dir / "metrics.json", report)
    return report


def _benchmark_run(config: dict, name: str | None, profile: str | None, quick: bool) -> dict:
    from .benchmark import fit_comparison, grouped_importance

    dataset_path, (train, valid, test) = _load_parts(config)
    profile = profile or config["model"]["profile"]
    seed = config["model"]["seed"]
    models, comparison, predictions, omitted = fit_comparison(
        train, valid, profile, config["baseline"]["artist_prior_weight"], seed, quick,
    )
    winner = comparison.iloc[0]["model"]
    x_valid = build_features(valid, profile)
    importance = grouped_importance(
        models[winner], x_valid, valid["precio_venta_cop"].to_numpy(),
        seed=seed, repeats=2 if quick else config["model"]["permutation_repeats"],
    )
    by_auction = []
    for date, indices in valid.groupby("fecha_subasta", sort=True).groups.items():
        for model in comparison["model"]:
            by_auction.append({"fecha_subasta": str(date)[:10], "model": model,
                **regression_metrics(valid.loc[indices, "precio_venta_cop"], predictions.loc[indices, model])})
    report_dir, artifact_dir, run = _run_paths(name)
    comparison.to_csv(report_dir / "model_comparison.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(by_auction).to_csv(report_dir / "validation_by_auction.csv", index=False)
    importance.to_csv(report_dir / "group_importance_validation.csv", index=False, encoding="utf-8-sig")
    valid[["registro_id", "precio_venta_cop"]].join(predictions).to_csv(
        report_dir / "validation_predictions.csv", index=False,
    )
    with (artifact_dir / "model.pkl").open("wb") as file:
        pickle.dump(models[winner], file)
    report = {"run": run, "kind": "benchmark", "profile": profile, "winner": winner,
              "quick": quick, "environment": _environment(), "dataset_sha256": sha256_file(dataset_path),
              "split": split_summary(train, valid, test), "validation_metrics": json.loads(comparison.to_json(orient="records")),
              "winner_segments": _segments(train, valid, predictions[winner]), "config": config,
              "features": list(x_valid), "omitted_models_missing_sklearn": omitted,
              "selection_metric": "mae_cop", "test_metrics_computed": False}
    write_json(report_dir / "metrics.json", report)
    return report


def _evaluate_test(config: dict, run: str) -> dict:

    # La elección del experimento es explícita; train/baseline nunca llaman este paso.
    if Path(run).name != run or not run:
        raise ValueError("run debe ser el nombre simple de un experimento local.")
    report_path = PROJECT_ROOT / "reports/runs" / run / "metrics.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("kind") not in {"ml", "benchmark"}:
        raise ValueError("evaluate-test requiere un experimento creado con train o benchmark.")
    source, (train, _valid, test) = _load_parts(report["config"])
    if sha256_file(source) != report["dataset_sha256"]:
        raise ValueError("Los datos cambiaron desde el entrenamiento. Genera otro experimento.")
    target = report_path.parent / "test_metrics.json"
    if target.exists():
        raise ValueError("Esta ejecución ya abrió la prueba final. Usa sus métricas guardadas.")
    artifact_dir = PROJECT_ROOT / "artifacts" / run
    if report["kind"] == "benchmark":
        # Solo se cargan artefactos de ejecuciones locales de confianza.
        with (artifact_dir / "model.pkl").open("rb") as file:
            model = pickle.load(file)
    else:
        from .ml import load_model

        model = load_model(artifact_dir / "model.joblib")
    pred = np.maximum(0, model.predict(build_features(test, report["profile"])))
    result = {"run": run, "model": report["winner"],
              "test_metrics": regression_metrics(test["precio_venta_cop"], pred),
              "segments": _segments(train, test, pred),
              "warning": "Si ajustas el modelo tras leer este resultado, deja de ser una prueba final independiente."}
    write_json(target, result)
    test[["registro_id", "precio_venta_cop"]].assign(prediction_cop=pred).to_csv(
        report_path.parent / "test_predictions.csv", index=False
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Desarrollo reproducible de precios de arte en COP")
    parser.add_argument("--config", default=None, help="Ruta del TOML; predeterminado configs/default.toml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="Validar el Excel y generar CSV + huellas")
    commands.add_parser("validate", help="Validar el CSV preparado y los cortes temporales")
    baseline = commands.add_parser("baseline", help="Comparar referencias sin usar la prueba final")
    baseline.add_argument("--run-name")
    train = commands.add_parser("train", help="Comparar Ridge y Random Forest en validación")
    train.add_argument("--run-name")
    train.add_argument("--profile", choices=PROFILES)
    train.add_argument("--quick", action="store_true", help="Comprobación rápida, no búsqueda exhaustiva")
    benchmark = commands.add_parser("benchmark", help="Comparar algoritmos y referencias en validación")
    benchmark.add_argument("--run-name")
    benchmark.add_argument("--profile", choices=PROFILES)
    benchmark.add_argument("--quick", action="store_true", help="Reducir iteraciones para comprobar el flujo")
    test = commands.add_parser("evaluate-test", help="Abrir la prueba final de un experimento elegido")
    test.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    try:
        if args.command == "prepare":
            result = prepare_dataset(project_path(config["data"]["source"]),
                                     project_path(config["data"]["output"]), config["data"])
        elif args.command == "validate":
            path, (tr, va, te) = _load_parts(config)
            result = {"dataset_sha256": sha256_file(path), "split": split_summary(tr, va, te)}
        elif args.command == "baseline":
            result = _baseline_run(config, args.run_name)
        elif args.command == "train":
            result = _train_run(config, args.run_name, args.profile, args.quick)
        elif args.command == "benchmark":
            result = _benchmark_run(config, args.run_name, args.profile, args.quick)
        else:
            result = _evaluate_test(config, args.run)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
