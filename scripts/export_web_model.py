"""Exporta los parámetros de una corrida local de confianza al cotizador estático."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import pickle
import re
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arte_precio.candidates import FeatureEncoder, SplineAdditiveRegressor  # noqa: E402
from arte_precio.dataset import sha256_file, write_json  # noqa: E402
from arte_precio.features import build_features  # noqa: E402

WEB_DIR = ROOT / "docs/cotizador"
MODEL_ID = "spline_additive_log"
MISSING = "__sin_informacion__"
LABELS = {
    "precision_anio_obra": {
        "aproximado": "Aproximado",
        "atribuido_catalogo": "Atribuido en el catálogo",
        "decada_o_periodo": "Década o período",
        "exacto_publicado": "Exacto",
        "intervalo": "Intervalo de años",
        "no_publicado": "No publicado",
        "sin_fecha": "Sin fecha",
    },
    "base_dimensiones": {
        "imagen": "Imagen",
        "obra_sin_ejes": "Obra, sin ejes indicados",
        "orden_fuente_sin_ejes": "Orden de la fuente, sin ejes indicados",
        "papel": "Papel",
        "sin_etiqueta": "Medidas sin etiqueta",
    },
}
RAW_FIELDS = (
    "artista_id", "tecnica_grupo", "soporte", "tipo_objeto", "precision_anio_obra",
    "base_dimensiones", "fecha_subasta", "anio_obra", "dim1_cm", "dim2_cm",
    "dim3_cm", "diametro_cm", "edicion_total",
)


def load_run(run: str) -> tuple[dict, SplineAdditiveRegressor, pd.DataFrame]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run):
        raise ValueError("Usa el nombre de una corrida local de benchmark.")
    report_path = ROOT / "reports/runs" / run / "metrics.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (report["run"], report["kind"], report["profile"], report["winner"], report["quick"]) != (
        run, "benchmark", "intrinseco", MODEL_ID, False,
    ):
        raise ValueError("La corrida debe ser un benchmark completo intrínseco ganado por splines.")
    dataset = ROOT / report["config"]["data"]["output"]
    if sha256_file(dataset) != report["dataset_sha256"]:
        raise ValueError("La huella de los datos no coincide con la registrada en la corrida.")

    # El reporte y el modelo deben proceder de una ejecución propia y de confianza.
    artifact = (ROOT / "artifacts" / run / "model.pkl").read_bytes()
    model = pickle.loads(artifact)
    if not isinstance(model, SplineAdditiveRegressor):
        raise ValueError("El artefacto local no es el modelo de splines registrado.")

    # Solo se leen características públicas de catálogo. El CSV no entra al artefacto web.
    frame = pd.read_csv(dataset, usecols=[*RAW_FIELDS, "artista"])
    dates = pd.to_datetime(frame["fecha_subasta"], errors="raise").dt.normalize()
    train = frame.loc[dates <= pd.Timestamp(report["config"]["split"]["train_end"])].copy()
    train_dates = dates.loc[train.index]
    summary = report["split"]["train"]
    if (len(train), train_dates.min().date().isoformat(), train_dates.max().date().isoformat()) != (
        summary["rows"], summary["start"], summary["end"],
    ):
        raise ValueError("La partición de entrenamiento no coincide con el informe guardado.")
    return {**report, "artifact_sha256": sha256(artifact).hexdigest()}, model, train


def artist_options(train: pd.DataFrame, features: pd.DataFrame) -> list[dict]:
    names = train["artista"].map(lambda name: str(name).strip() if pd.notna(name) else "")
    catalog = pd.DataFrame({"id": features["artista"], "name": names})
    options = []
    for artist_id, rows in catalog.groupby("id", sort=True):
        names = rows.loc[rows["name"] != "", "name"].value_counts()
        labels = sorted(names.index, key=lambda name: (-names[name], name.casefold(), name))
        option = {
            "id": artist_id,
            "label": labels[0] if labels else artist_id.replace("_", " "),
            "count": len(rows),
        }
        if len(labels) > 1:
            option["aliases"] = labels[1:]
        options.append(option)
    return options


def export_model(report: dict, model: SplineAdditiveRegressor, train: pd.DataFrame) -> dict:
    features = build_features(train, report["profile"])
    encoder = model.encoder_
    if encoder.columns != report["features"] or encoder.columns != features.columns.tolist():
        raise ValueError("Las características del modelo, el informe y el código no coinciden.")
    options = {"artista_id": artist_options(train, features)}
    fitted_categories = FeatureEncoder(features, min_category_count=2).categories
    if fitted_categories != encoder.categories:
        raise ValueError("Las categorías aprendidas no corresponden a esta partición de entrenamiento.")
    for field, levels in encoder.categories.items():
        if field != "artista":
            options[field] = [
                {"id": level, "label": LABELS.get(field, {}).get(level, level)}
                for level in levels if level != MISSING
            ]

    numeric = [{**asdict(column), "knots": column.knots.tolist()} for column in encoder.numeric]
    width = 1 + sum(1 + len(col["knots"]) + col["has_missing"] for col in numeric)
    width += sum(map(len, encoder.categories.values()))
    if model.coefficients_.shape != (width,):
        raise ValueError("Los coeficientes no coinciden con la matriz de variables aprendida.")
    low, high = model.bounds_
    safe_max = np.nextafter(np.log(np.finfo(float).max), 0)
    summary = report["split"]["train"]
    validation = next(row for row in report["validation_metrics"] if row["model"] == MODEL_ID)
    return {
        "version": 1,
        "metadata": {
            "run": report["run"],
            "model_name": validation["modelo"],
            "artifact_sha256": report["artifact_sha256"],
            "dataset_sha256": report["dataset_sha256"],
            "training_commit": report["environment"]["git_commit"],
            "training_rows": summary["rows"],
            "training_years": [int(summary[key][:4]) for key in ("start", "end")],
            "validation": {key: validation[key] for key in (
                "n", "mae_cop", "median_absolute_error_cop", "rmse_cop", "r2",
                "median_absolute_percentage_error_pct",
            )},
        },
        "options": options,
        "numeric": numeric,
        "categories": encoder.categories,
        "coefficients": model.coefficients_.tolist(),
        "log_target_bounds": [float(low), float(min(high, safe_max))],
    }


def check_parity(payload: dict, model: SplineAdditiveRegressor, train: pd.DataFrame) -> None:
    # Se comprueba portabilidad con características de entrenamiento y escenarios nuevos,
    # sin consultar precios de venta observados ni particiones reservadas.
    invented = [
        {"fecha_subasta": "2026-01-01"},
        {"fecha_subasta": "2026-01-01", "artista_id": "autor_de_prueba_sin_historial",
         "dim1_cm": 5, "dim2_cm": 400, "dim3_cm": 0, "diametro_cm": 50, "edicion_total": 99},
        {"fecha_subasta": "2024-02-29", "anio_obra": 2025, "precision_anio_obra": "exacto_publicado",
         "dim1_cm": -100, "dim2_cm": 1.5, "tecnica_grupo": "Técnica sin historial"},
        {"fecha_subasta": "2023-08-15", "anio_obra": 1789, "precision_anio_obra": "aproximado",
         "dim1_cm": 5000, "dim2_cm": 1, "soporte": "Papel", "tecnica_grupo": "Óleo"},
    ]
    frame = pd.concat([train[list(RAW_FIELDS)], pd.DataFrame(invented)], ignore_index=True)
    expected = model.predict(build_features(frame, "intrinseco"))
    rows = frame.astype(object).where(frame.notna(), None).to_dict("records")
    module = (WEB_DIR / "predict.mjs").as_uri()
    program = f"""
        import {{ readFileSync }} from 'node:fs';
        import {{ predictPrice }} from {json.dumps(module)};
        const {{ model, rows }} = JSON.parse(readFileSync(0, 'utf8'));
        console.log(JSON.stringify(rows.map(row => predictPrice(model, row))));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        input=json.dumps({"model": payload, "rows": rows}, ensure_ascii=False, allow_nan=False),
        capture_output=True, check=True, encoding="utf-8",
    )
    actual = np.array(json.loads(result.stdout))
    np.testing.assert_allclose(actual, expected, rtol=3e-12, atol=1e-7)
    max_difference = np.max(np.abs(actual - expected))
    print(f"Paridad Python/JavaScript: {len(actual)} casos, diferencia máxima {max_difference:.8f} COP.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="Nombre de la corrida de benchmark local")
    parser.add_argument("--check-parity", action="store_true", help="Comparar con Node.js antes de exportar")
    args = parser.parse_args()
    report, model, train = load_run(args.run)
    payload = export_model(report, model, train)
    if args.check_parity:
        check_parity(payload, model, train)
    path = WEB_DIR / "model.json"
    write_json(path, payload)
    print(f"Exportado {path.relative_to(ROOT).as_posix()}.")


if __name__ == "__main__":
    main()
