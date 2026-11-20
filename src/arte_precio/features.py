"""Lista explícita de predictores; ningún precio de referencia entra por defecto."""
import numpy as np
import pandas as pd

PROFILES = ("intrinseco", "sin_artista", "documentado", "con_avaluo")
FORBIDDEN = {
    "precio_venta_cop", "registro_id", "subasta_id", "lote", "estado_fuente",
    "usar_modelo_base", "motivo_revision", "fecha_consulta", "tipo_precio",
    "texto_identificacion_original", "fuente_resultado_url", "fuente_ficha_url",
    "fuente_catalogo_url", "pagina_catalogo",
}


def numeric(frame: pd.DataFrame, key: str) -> pd.Series:
    values = frame[key] if key in frame else pd.Series(np.nan, index=frame.index)
    return pd.to_numeric(values, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)


def category(frame: pd.DataFrame, key: str) -> pd.Series:
    values = frame[key] if key in frame else pd.Series(None, index=frame.index)
    return values.map(lambda x: str(x).strip() if pd.notna(x) and str(x).strip() else np.nan).astype(object)


def build_features(frame: pd.DataFrame, profile: str = "intrinseco") -> pd.DataFrame:
    if profile not in PROFILES:
        raise ValueError(f"Perfil inválido: {profile}. Opciones: {PROFILES}")
    features = pd.DataFrame(index=frame.index)
    if profile != "sin_artista":
        features["artista"] = category(frame, "artista_id")
    for name in ["tecnica_grupo", "soporte", "tipo_objeto", "precision_anio_obra", "base_dimensiones"]:
        features[name] = category(frame, name)
    date = pd.to_datetime(frame["fecha_subasta"], errors="coerce")
    features["anio_venta"] = date.dt.year.astype(float)
    work_year = numeric(frame, "anio_obra")
    precision = category(frame, "precision_anio_obra")
    allowed_year = precision.isin(["exacto_publicado", "aproximado", "atribuido_catalogo"])
    work_year = work_year.where(allowed_year & (work_year <= features["anio_venta"]))
    features["anio_obra"] = work_year
    features["edad_obra_venta"] = (features["anio_venta"] - work_year).where(work_year.notna())
    for name in ["dim1_cm", "dim2_cm", "dim3_cm", "diametro_cm", "edicion_total"]:
        value = numeric(frame, name).where(lambda x: x > 0)
        features[f"log_{name}"] = np.log1p(value)
    # Recalcular geometría desde medidas evita aprender errores de fórmulas del Excel.
    d1, d2 = numeric(frame, "dim1_cm"), numeric(frame, "dim2_cm")
    valid = (d1 > 0) & (d2 > 0)
    features["log_area_rectangular_cm2"] = np.log1p((d1 * d2).where(valid))
    features["relacion_lados"] = (pd.concat([d1, d2], axis=1).max(axis=1) /
                                  pd.concat([d1, d2], axis=1).min(axis=1)).where(valid)
    if profile == "documentado":
        for name in ["firma_mencionada", "certificado_mencionado", "procedencia_mencionada",
                     "literatura_mencionada", "exposiciones_mencionadas"]:
            # Ausencia de información documental no equivale a un NO explícito.
            value = numeric(frame, name)
            features[name] = value.map({1.0: "mencionado", 0.0: "cero_explicito"}).fillna("sin_informacion").astype(object)
    if profile == "con_avaluo":
        for name in ["precio_salida_cop", "estimado_min_cop", "estimado_max_cop"]:
            features[f"log_{name}"] = np.log1p(numeric(frame, name).where(lambda x: x > 0))
    assert not FORBIDDEN.intersection(features.columns)
    return features
