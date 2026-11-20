import { scoreSpline } from "../predict.mjs?v=8d155b8";

export function buildGalleryFeatures({ technique, width, height, year }) {
  const validYear = Number.isInteger(year) && year >= 1 && year <= 9999;
  return {
    technique,
    log_area_cm2: Math.log1p(width * height),
    log_aspect: Math.abs(Math.log(width) - Math.log(height)),
    year: validYear ? year : NaN,
  };
}

function withinRange(value, range) {
  return Array.isArray(range) && range.length === 2 && range.every(Number.isFinite)
    && value >= range[0] && value <= range[1];
}

export function estimateGalleryOil(model, request) {
  const { width, height, year } = request ?? {};
  const coverage = model?.coverage?.oleo;
  if (model?.version !== 1 || model.model_id !== "spline_additive_log"
      || model.target !== "precio_publicado_cop" || !coverage
      || !Array.isArray(model.feature_columns)) return null;
  if (!Number.isFinite(width) || !Number.isFinite(height)) return null;

  const shortSide = Math.min(width, height);
  const longSide = Math.max(width, height);
  if (shortSide <= 0 || !withinRange(shortSide, coverage.short_side_cm)
      || !withinRange(longSide, coverage.long_side_cm)) return null;

  const features = buildGalleryFeatures({ technique: "oleo", width, height, year });
  if (!model.feature_columns.every((column) => Object.hasOwn(features, column))) return null;
  return scoreSpline(model, features);
}
