const MISSING_CATEGORY = "__sin_informacion__";
const YEAR_PRECISIONS = new Set(["exacto_publicado", "aproximado", "atribuido_catalogo"]);
const MEASUREMENTS = ["dim1_cm", "dim2_cm", "dim3_cm", "diametro_cm", "edicion_total"];

function category(value) {
  return String(value ?? "").trim() || MISSING_CATEGORY;
}

function number(value) {
  if (typeof value === "string") {
    value = value.trim();
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value)) return NaN;
    value = Number(value);
  }
  return Number.isFinite(value) ? value : NaN;
}

function saleYear(raw) {
  const date = String(raw.fecha_subasta ?? "").trim();
  if (!date) {
    const year = number(raw.anio_venta);
    return Number.isInteger(year) && year >= 1 && year <= 9999 ? year : NaN;
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date.startsWith("0000")) return NaN;
  const parsed = new Date(`${date}T00:00:00Z`);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date) return NaN;
  return parsed.getUTCFullYear();
}

export function buildFeatures(raw) {
  const precision = category(raw.precision_anio_obra);
  const year = saleYear(raw);
  const suppliedWorkYear = number(raw.anio_obra);
  const workYear = YEAR_PRECISIONS.has(precision) && suppliedWorkYear <= year
    ? suppliedWorkYear
    : NaN;
  const features = {
    artista: category(raw.artista_id),
    tecnica_grupo: category(raw.tecnica_grupo),
    soporte: category(raw.soporte),
    tipo_objeto: category(raw.tipo_objeto),
    precision_anio_obra: precision,
    base_dimensiones: category(raw.base_dimensiones),
    anio_venta: year,
    anio_obra: workYear,
    edad_obra_venta: year - workYear,
  };
  for (const field of MEASUREMENTS) {
    const value = number(raw[field]);
    features[`log_${field}`] = value > 0 ? Math.log1p(value) : NaN;
  }
  const dim1 = number(raw.dim1_cm);
  const dim2 = number(raw.dim2_cm);
  const validArea = dim1 > 0 && dim2 > 0;
  features.log_area_rectangular_cm2 = validArea ? Math.log1p(dim1 * dim2) : NaN;
  features.relacion_lados = validArea ? Math.max(dim1, dim2) / Math.min(dim1, dim2) : NaN;
  return features;
}

function normalizeArtist(value) {
  return value.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

export function resolveArtist(model, text) {
  const label = String(text ?? "").trim();
  if (!label) return { id: null, label: "", status: "unspecified", count: 0 };

  const artists = model.options.artista_id;
  let artist = artists.find(({ id }) => id === label);
  const normalized = normalizeArtist(label);
  if (!artist && normalized) {
    const matches = artists.filter(({ id, label, aliases = [] }) =>
      [id, label, ...aliases].some((name) => normalizeArtist(name) === normalized));
    if (matches.length === 1) [artist] = matches;
  }
  if (!artist) return { id: null, label, status: "unknown", count: 0 };

  const status = model.categories.artista.includes(artist.id) ? "modeled" : "rare";
  return { id: artist.id, label: artist.label, status, count: artist.count };
}

export function predictPrice(model, raw) {
  if (model.version !== 1) {
    throw new Error("La versión del modelo no es compatible con el cotizador.");
  }
  const artist = resolveArtist(model, raw.artista_id);
  const features = buildFeatures({ ...raw, artista_id: artist.id });
  // A new name has zero training indicators. A blank may have a fitted missing level.
  if (artist.status === "unknown") features.artista = null;

  let index = 0;
  let logPrediction = model.coefficients[index++];
  for (const column of model.numeric) {
    const observed = features[column.name];
    const missing = !Number.isFinite(observed);
    const filled = missing ? column.center : observed;
    const clipped = Math.min(column.upper, Math.max(column.lower, filled));
    const value = (clipped - column.center) / column.scale;
    logPrediction += value * model.coefficients[index++];
    for (const knot of column.knots) {
      logPrediction += Math.max(0, value - knot) * model.coefficients[index++];
    }
    if (column.has_missing) logPrediction += Number(missing) * model.coefficients[index++];
  }
  for (const [name, levels] of Object.entries(model.categories)) {
    const level = levels.indexOf(features[name]);
    if (level !== -1) logPrediction += model.coefficients[index + level];
    index += levels.length;
  }
  if (index !== model.coefficients.length || !Number.isFinite(logPrediction)) {
    throw new Error("Los parámetros del modelo no son válidos.");
  }
  const [lower, upper] = model.log_target_bounds;
  return Math.expm1(Math.min(upper, Math.max(lower, logPrediction)));
}
