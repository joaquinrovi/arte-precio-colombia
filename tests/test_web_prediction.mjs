import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { estimateGalleryOil } from "../docs/cotizador/encargos/gallery-predict.mjs";
import { buildFeatures, predictPrice, resolveArtist } from "../docs/cotizador/predict.mjs";

const published = JSON.parse(readFileSync(new URL("../docs/cotizador/model.json", import.meta.url)));
const gallery = JSON.parse(readFileSync(new URL("../docs/cotizador/encargos/gallery-model.json", import.meta.url)));
const sample = {
  version: 1,
  options: {
    artista_id: [
      { id: "violeta_bosque", label: "Violeta del Bosque", count: 4, aliases: ["Violeta Bosqué"] },
      { id: "iris_rio", label: "Iris Río", count: 1 },
    ],
  },
  numeric: [
    { name: "log_dim1_cm", center: 2, scale: 2, lower: 0, upper: 6, knots: [0, 0.5], has_missing: true },
  ],
  categories: {
    artista: ["violeta_bosque", "__sin_informacion__"],
    tecnica_grupo: ["Témpera", "Otra"],
  },
  // Intercepto, componente lineal, dos nudos, faltante y niveles de cada categoría.
  coefficients: [1, 0.5, 0.25, -0.25, 0.125, 0.5, 0.25, 0.125, 0.25],
  log_target_bounds: [0, 8],
};

test("calcula los descriptores de dimensiones, edad y edición en el orden de la fuente", () => {
  const features = buildFeatures({
    artista_id: " violeta_bosque ", fecha_subasta: "2024-02-29", anio_venta: 1980,
    anio_obra: "2001", precision_anio_obra: "aproximado", dim1_cm: "18", dim2_cm: 30,
    dim3_cm: 5, diametro_cm: " 3e1 ", edicion_total: "25",
  });
  assert.equal(features.artista, "violeta_bosque");
  assert.equal(features.anio_venta, 2024);
  assert.equal(features.edad_obra_venta, 23);
  assert.equal(features.log_dim1_cm, Math.log1p(18));
  assert.equal(features.log_dim2_cm, Math.log1p(30));
  assert.equal(features.log_dim3_cm, Math.log1p(5));
  assert.equal(features.log_diametro_cm, Math.log1p(30));
  assert.equal(features.log_edicion_total, Math.log1p(25));
  assert.equal(features.log_area_rectangular_cm2, Math.log1p(540));
  assert.equal(features.relacion_lados, 30 / 18);
  assert.equal(buildFeatures({ anio_venta: "2026", anio_obra: 2024, precision_anio_obra: "exacto_publicado" }).edad_obra_venta, 2);
});

test("toma como ausentes las fechas ambiguas, inválidas o posteriores al remate y las medidas no positivas", () => {
  const ambiguous = buildFeatures({
    fecha_subasta: "2025-11-20", anio_obra: 2000, precision_anio_obra: "decada_o_periodo",
    dim1_cm: 0, dim2_cm: -1, dim3_cm: "0x10", edicion_total: "",
  });
  assert.equal(ambiguous.precision_anio_obra, "decada_o_periodo");
  for (const key of ["anio_obra", "edad_obra_venta", "log_dim1_cm", "log_dim2_cm", "log_dim3_cm",
    "log_edicion_total", "log_area_rectangular_cm2", "relacion_lados"]) {
    assert.ok(Number.isNaN(ambiguous[key]), key);
  }
  assert.ok(Number.isNaN(buildFeatures({ fecha_subasta: "2025-02-29" }).anio_venta));
  assert.ok(Number.isNaN(buildFeatures({ anio_venta: 2024, anio_obra: 2025, precision_anio_obra: "atribuido_catalogo" }).anio_obra));
});

test("resuelve nombres, variantes e identificadores de catálogo y admite artistas libres", () => {
  const modeled = { id: "violeta_bosque", label: "Violeta del Bosque", status: "modeled", count: 4 };
  for (const name of ["violeta_bosque", "VIOLETA DEL BOSQUE", "Violeta dEl  Bosqué", "violeta bosque"]) {
    assert.deepEqual(resolveArtist(sample, name), modeled);
  }
  assert.deepEqual(resolveArtist(sample, "Iris Rio"), {
    id: "iris_rio", label: "Iris Río", status: "rare", count: 1,
  });
  assert.deepEqual(resolveArtist(sample, "Mi propio nombre artístico"), {
    id: null, label: "Mi propio nombre artístico", status: "unknown", count: 0,
  });
  assert.deepEqual(resolveArtist(sample, "   "), { id: null, label: "", status: "unspecified", count: 0 });
});

test("no asigna un efecto de identidad cuando el nombre normalizado es ambiguo", () => {
  const ambiguous = { ...sample, options: { artista_id: [...sample.options.artista_id,
    { id: "otra_violeta", label: "Violeta del Bosqué", count: 1 }] } };
  assert.equal(resolveArtist(ambiguous, "Violeta del Bosque").status, "unknown");
  assert.equal(resolveArtist(ambiguous, "violeta_bosque").id, "violeta_bosque");
});

test("combina splines, faltantes y categorías y usa los límites logarítmicos aprendidos", () => {
  const inputs = { dim1_cm: Math.expm1(10), tecnica_grupo: "Témpera" };
  const generic = predictPrice(sample, { ...inputs, artista_id: "Artista nuevo" });
  assert.equal(generic, Math.expm1(2.25));
  assert.equal(predictPrice(sample, { ...inputs, artista_id: "Iris Río" }), generic);
  assert.equal(predictPrice(sample, { ...inputs, artista_id: "Violeta Bosqué" }), Math.expm1(2.75));
  assert.equal(predictPrice(sample, inputs), Math.expm1(2.5));
  assert.equal(predictPrice(sample, {}), Math.expm1(1.375));
  assert.equal(predictPrice({ ...sample, log_target_bounds: [2.4, 2.6] }, {
    ...inputs, artista_id: "Violeta Bosqué",
  }), Math.expm1(2.6));
  assert.equal(predictPrice({ ...sample, log_target_bounds: [2.4, 2.6] }, {}), Math.expm1(2.4));
});

test("el modelo publicado contiene un catálogo coherente y devuelve COP para artistas nuevos", () => {
  const artists = published.options.artista_id;
  assert.equal(new Set(artists.map(({ id }) => id)).size, artists.length);
  const modeled = artists.filter((artist) => resolveArtist(published, artist.id).status === "modeled");
  const rare = artists.filter((artist) => resolveArtist(published, artist.id).status === "rare");
  assert.ok(modeled.length > 0 && rare.length > 0);
  assert.ok(modeled.every((artist) => artist.count >= 2));
  assert.ok(rare.every((artist) => artist.count === 1));
  assert.ok(artists.reduce((sum, { count }) => sum + count, 0) <= published.metadata.training_rows);

  const raw = { anio_venta: 2026, dim1_cm: 50, dim2_cm: 70, tecnica_grupo: "Óleo" };
  const newArtist = predictPrice(published, { ...raw, artista_id: "Artista ficticio de verificación" });
  assert.ok(Number.isFinite(newArtist) && newArtist > 0);
  assert.equal(newArtist, predictPrice(published, { ...raw, artista_id: rare[0].id }));
});

test("el modelo de galería publicado reproduce el ejemplo de óleo en ambas orientaciones", () => {
  const price = estimateGalleryOil(gallery, { width: 60, height: 80, year: 2026 });
  assert.equal(Math.round(price), 2962641);
  assert.equal(estimateGalleryOil(gallery, { width: 80, height: 60, year: 2026 }), price);
});

test("la referencia de galería omite las medidas fuera de cobertura", () => {
  assert.equal(estimateGalleryOil(gallery, { width: 200, height: 300, year: 2026 }), null);
  assert.equal(estimateGalleryOil(gallery, { width: 0, height: 80, year: 2026 }), null);
});
