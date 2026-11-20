from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED = {
    "registro_id", "precio_venta_cop", "moneda_original", "fecha_subasta",
    "artista_id", "tecnica_grupo", "dim1_cm", "dim2_cm", "diametro_cm",
    "lote_multiple", "usar_modelo_base", "motivo_revision", "fuente_resultado_url",
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: str | Path, payload: dict | list) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_source(path: str | Path, sheet: str = "Ventas") -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"No se encontró {path}. Copia el Excel original en data/raw/.")
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    elif path.suffix.lower() == ".xlsx":
        frame = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    else:
        raise ValueError("La fuente debe ser .xlsx o .csv.")
    return frame


def validate_source(frame: pd.DataFrame) -> dict:
    missing = sorted(REQUIRED - set(frame.columns))
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {missing}")
    if frame.empty:
        raise ValueError("El conjunto está vacío.")
    if frame["registro_id"].isna().any() or frame["registro_id"].duplicated().any():
        raise ValueError("registro_id debe ser completo y único.")
    price = pd.to_numeric(frame["precio_venta_cop"], errors="coerce")
    if price.isna().any() or not np.isfinite(price).all() or (price <= 0).any():
        raise ValueError("El target debe ser numérico, finito y mayor que cero.")
    if not frame["moneda_original"].eq("COP").all():
        raise ValueError("El modelo inicial solo acepta precios de venta en COP.")
    dates = pd.to_datetime(frame["fecha_subasta"], errors="coerce")
    if dates.isna().any():
        raise ValueError("Hay fechas de subasta ausentes o inválidas.")
    if not frame["fuente_resultado_url"].fillna("").str.startswith("https://").all():
        raise ValueError("Cada venta debe conservar su fuente HTTPS.")
    for name in ["dim1_cm", "dim2_cm", "dim3_cm", "diametro_cm"]:
        if name not in frame:
            continue
        values = pd.to_numeric(frame[name], errors="coerce")
        if (frame[name].notna() & values.isna()).any():
            raise ValueError(f"{name} contiene medidas no numéricas.")
        if ((values <= 0) | ~np.isfinite(values)).where(values.notna(), False).any():
            raise ValueError(f"{name} contiene medidas no positivas o no finitas.")
    warnings = []
    if "firma_mencionada" in frame and frame["firma_mencionada"].eq(0).any():
        warnings.append("Hay firma_mencionada=0; se conserva separado de información ausente.")
    return {
        "rows": len(frame), "columns": len(frame.columns),
        "first_auction": dates.min().date().isoformat(),
        "last_auction": dates.max().date().isoformat(),
        "warnings": warnings,
    }


def select_model_rows(
    frame: pd.DataFrame, require_base_flag: bool = True, exclude_open_post_sale: bool = True
) -> tuple[pd.DataFrame, dict]:
    validate_source(frame)
    mask = pd.Series(True, index=frame.index)
    counts = {}
    if require_base_flag:
        eligible = pd.to_numeric(frame["usar_modelo_base"], errors="coerce").eq(1)
        counts["base_flag"] = int((mask & ~eligible).sum())
        mask &= eligible
    # No se permite entrenar accidentalmente con un precio del conjunto como precio individual.
    multiple = pd.to_numeric(frame["lote_multiple"], errors="coerce").eq(1)
    counts["explicit_multiple_after_base"] = int((mask & multiple).sum())
    mask &= ~multiple
    open_sale = frame["motivo_revision"].fillna("").str.contains("posventa abierta", case=False)
    if exclude_open_post_sale:
        counts["open_post_sale_after_previous_filters"] = int((mask & open_sale).sum())
        mask &= ~open_sale
    result = frame.loc[mask].copy()
    if result.empty:
        raise ValueError("Ninguna fila cumple los filtros de modelado.")
    result["fecha_subasta"] = pd.to_datetime(result["fecha_subasta"]).dt.normalize()
    result = result.sort_values(["fecha_subasta", "registro_id"]).reset_index(drop=True)
    return result, {
        "input_rows": len(frame), "selected_rows": len(result),
        "excluded_rows": int((~mask).sum()),
        "open_post_sale_rows": int(open_sale.sum()),
        "require_base_flag": require_base_flag,
        "exclude_open_post_sale": exclude_open_post_sale,
        "multiple_lots_always_excluded": True,
        "sequential_exclusions": counts,
    }


def prepare_dataset(source: Path, output: Path, data_config: dict) -> dict:
    original = load_source(source, data_config.get("sheet", "Ventas"))
    source_report = validate_source(original)
    selected, selection = select_model_rows(
        original,
        require_base_flag=data_config.get("require_base_flag", True),
        exclude_open_post_sale=data_config.get("exclude_open_post_sale", True),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(output, index=False, encoding="utf-8", date_format="%Y-%m-%d")
    rejected = original.loc[~original["registro_id"].isin(selected["registro_id"])].copy()
    def rejection_reason(row):
        reasons = []
        if data_config.get("require_base_flag", True) and row["usar_modelo_base"] != 1:
            reasons.append("No cumple usar_modelo_base=1")
        if row["lote_multiple"] == 1:
            reasons.append("Lote con varias piezas")
        if data_config.get("exclude_open_post_sale", True) and "posventa abierta" in str(row["motivo_revision"]).lower():
            reasons.append("Posventa abierta en la fecha de consulta")
        return " | ".join(reasons)
    rejected["motivo_exclusion_modelado"] = rejected.apply(rejection_reason, axis=1)
    rejected[["registro_id", "motivo_exclusion_modelado", "motivo_revision"]].to_csv(
        output.with_suffix(".exclusions.csv"), index=False, encoding="utf-8"
    )
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_name": source.name, "source_sha256": sha256_file(source),
        "output_sha256": sha256_file(output),
        "source": source_report, "selection": selection,
        "target": "precio_venta_cop", "unit": "COP nominales por lote; sin comisión",
    }
    write_json(output.with_suffix(".manifest.json"), report)
    return report
