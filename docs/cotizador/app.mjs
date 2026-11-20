import { predictPrice, resolveArtist } from "./predict.mjs";

const byId = (id) => document.getElementById(id);
const form = byId("quote-form");
const fields = byId("form-fields");
const artistInput = byId("artist");
const saveArtistButton = byId("save-artist");
const artistOptions = byId("artist-options");
const artistStatus = byId("artist-status");
const dimensionsHelp = byId("dimensions-help");
const dimensionOne = byId("dimension-one");
const dimensionTwo = byId("dimension-two");
const diameter = byId("diameter");
const thirdDimension = byId("third-dimension");
const dimensionBasis = byId("dimension-basis");
const workYear = byId("work-year");
const yearPrecision = byId("year-precision");
const appMessage = byId("app-message");
const exampleButton = byId("load-example");
const moreDetails = byId("more-details");
const studyArt = byId("study-art");
const studySize = byId("study-size");
const result = byId("result");
const quoteStatus = byId("quote-status");
const quotePrice = byId("quote-price");
const quoteCaption = byId("quote-caption");
const quoteArtist = byId("quote-artist");
const quote = quotePrice.parentElement;

const storageKey = "arte-precio-colombia:artistas-guardados";
const saleYear = Number(new Intl.DateTimeFormat("en", {
  timeZone: "America/Bogota",
  year: "numeric",
}).format(new Date()));
const money = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  currencyDisplay: "narrowSymbol",
  maximumFractionDigits: 0,
});
const measurement = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2 });

let model;
let savedArtists = loadSavedArtists();
let storageAvailable = true;

function loadSavedArtists() {
  try {
    const names = JSON.parse(localStorage.getItem(storageKey) ?? "[]");
    return Array.isArray(names)
      ? names.filter((name) => typeof name === "string" && name.trim() && name.length <= 120)
      : [];
  } catch {
    return [];
  }
}

function artistKey(name) {
  return name.normalize("NFKD").replace(/\p{M}/gu, "").toLocaleLowerCase("es-CO").replace(/\s+/gu, " ").trim();
}

function populateSelect(id, options) {
  const select = byId(id);
  for (const { id: value, label } of options) select.add(new Option(label, value));
}

function populateArtistOptions() {
  const options = document.createDocumentFragment();
  const labels = [...savedArtists, ...model.options.artista_id.map(({ label }) => label)];
  const used = new Set();
  for (const label of labels) {
    const key = artistKey(label);
    if (used.has(key)) continue;
    used.add(key);
    options.append(new Option(label, label));
  }
  artistOptions.replaceChildren(options);
}

function getArtist() {
  return resolveArtist(model, artistInput.value);
}

function updateArtistStatus() {
  const { label, status } = getArtist();
  const saved = savedArtists.some((name) => artistKey(name) === artistKey(label));
  const descriptions = {
    modeled: "El modelo usa el historial de este artista.",
    rare: "El artista tiene pocos registros. La estimación se basa en las características de la obra.",
    unknown: "El modelo usará las características de la obra como referencia.",
    unspecified: "",
  };

  saveArtistButton.hidden = status === "unspecified" || !storageAvailable;
  saveArtistButton.textContent = saved ? "Quitar" : "Guardar";
  saveArtistButton.setAttribute("aria-label", saved ? "Quitar nombre guardado" : "Guardar nombre en este navegador");
  saveArtistButton.title = saved ? "Quitar de las sugerencias guardadas" : "Guardar en este navegador";

  const message = saved ? `${descriptions[status]} Nombre guardado en este navegador.` : descriptions[status];
  artistStatus.hidden = !message;
  if (artistStatus.textContent !== message) artistStatus.textContent = message;
}

function toggleSavedArtist() {
  const { label } = getArtist();
  if (!label) return;
  const key = artistKey(label);
  const others = savedArtists.filter((name) => artistKey(name) !== key);
  const next = others.length === savedArtists.length ? [label, ...others] : others;
  try {
    localStorage.setItem(storageKey, JSON.stringify(next));
    savedArtists = next;
    populateArtistOptions();
  } catch {
    storageAvailable = false;
    showAppMessage("El navegador impidió guardar el nombre. Puedes usarlo para calcular la estimación.");
    artistInput.focus();
  }
  updateArtistStatus();
}

function isRound() {
  return form.elements.shape.value === "round";
}

function hasMeasurements() {
  return [dimensionOne, dimensionTwo, diameter, thirdDimension].some((field) => !field.disabled && field.value);
}

function syncConditionalFields() {
  const round = isRound();
  byId("sides-fields").hidden = round;
  byId("round-fields").hidden = !round;
  dimensionsHelp.hidden = round;
  dimensionOne.disabled = round;
  dimensionTwo.disabled = round;
  diameter.disabled = !round;
  dimensionBasis.disabled = !hasMeasurements();
  yearPrecision.disabled = !workYear.value;
}

function drawStudy() {
  const round = isRound();
  const first = round ? diameter.valueAsNumber : dimensionOne.valueAsNumber;
  const second = round ? first : dimensionTwo.valueAsNumber;
  const hasPair = first > 0 && second > 0;
  studyArt.style.setProperty("--art-radius", round ? "50%" : "2px");

  if (!hasPair) {
    studyArt.style.setProperty("--art-width", round ? "128px" : "115px");
    studyArt.style.setProperty("--art-height", "128px");
    studySize.textContent = "";
    return;
  }

  const ratio = Math.min(2.8, Math.max(.35, second / first));
  studyArt.style.setProperty("--art-width", `${Math.min(198, 132 * ratio)}px`);
  studyArt.style.setProperty("--art-height", `${Math.min(132, 198 / ratio)}px`);
  studySize.textContent = round
    ? `Ø ${measurement.format(first)} cm`
    : `${measurement.format(first)} × ${measurement.format(second)} cm`;
}

function showAppMessage(message) {
  appMessage.textContent = message;
  appMessage.hidden = !message;
}

function showInstructions(changed = false) {
  quote.dataset.state = changed ? "changed" : "empty";
  quoteStatus.textContent = changed ? "Cambios por calcular" : "Tu estimación aparecerá aquí";
  quoteCaption.textContent = changed
    ? "Pulsa Calcular estimación para actualizar el valor."
    : "Completa la ficha y pulsa Calcular estimación.";
  quotePrice.hidden = true;
  quoteArtist.hidden = true;
}

function showEstimate(price, artist) {
  const priceStep = 10000;
  const rounded = Math.round(price / priceStep) * priceStep;
  const descriptions = {
    modeled: `${artist.label} · ${artist.count} lotes en el entrenamiento.`,
    rare: `${artist.label} · ${artist.count} ${artist.count === 1 ? "lote" : "lotes"} en el entrenamiento. La estimación se basa en las características de la obra, dada la escasez de registros del artista.`,
    unknown: `${artist.label} · Artista nuevo para el modelo. La referencia se basa en las características de la obra. En 2026, el error porcentual absoluto mediano para artistas nuevos fue del 85 %.`,
    unspecified: "Estimación basada en las características ingresadas, sin identificar al artista.",
  };

  quote.dataset.state = "result";
  quoteStatus.textContent = "Referencia orientativa";
  quotePrice.textContent = rounded ? money.format(rounded) : `Menos de ${money.format(priceStep)}`;
  quotePrice.hidden = false;
  quoteCaption.textContent = `Pesos colombianos · Redondeo en múltiplos de ${money.format(priceStep)}`;
  quoteArtist.textContent = descriptions[artist.status];
  quoteArtist.hidden = false;
  result.focus({ preventScroll: true });
  result.scrollIntoView({ block: "nearest" });
}

function calculateEstimate(event) {
  event.preventDefault();
  const raw = Object.fromEntries(new FormData(form));
  raw.anio_venta = saleYear;
  if (hasMeasurements() && !raw.base_dimensiones) raw.base_dimensiones = "sin_etiqueta";

  try {
    const price = predictPrice(model, raw);
    if (!Number.isFinite(price) || price <= 0) throw new Error("Precio inválido");
    showAppMessage("");
    showEstimate(price, getArtist());
  } catch {
    showInstructions(true);
    showAppMessage("Hubo un problema al calcular la estimación. Revisa los datos e inténtalo de nuevo.");
  }
}

function onFormInput(event) {
  if (event.target === artistInput) updateArtistStatus();
  syncConditionalFields();
  drawStudy();
  if (quote.dataset.state === "result") showInstructions(true);
}

function clearForm() {
  form.reset();
  moreDetails.open = false;
  updateArtistStatus();
  syncConditionalFields();
  drawStudy();
  showAppMessage("");
  showInstructions();
}

function loadExample() {
  clearForm();
  byId("work-type").value = "Obra bidimensional";
  byId("technique").value = "Óleo";
  byId("support").value = "Lienzo";
  dimensionOne.value = "50";
  dimensionTwo.value = "70";
  syncConditionalFields();
  drawStudy();
  form.requestSubmit();
}

async function initialize() {
  try {
    const response = await fetch("./model.json");
    if (!response.ok) throw new Error("Modelo inaccesible");
    model = await response.json();

    const { options, metadata } = model;
    populateSelect("work-type", options.tipo_objeto);
    populateSelect("technique", options.tecnica_grupo);
    populateSelect("support", options.soporte);
    populateSelect("dimension-basis", options.base_dimensiones);
    const supportedYearPrecisions = ["exacto_publicado", "aproximado", "atribuido_catalogo"];
    const yearOptions = supportedYearPrecisions.map((id) => options.precision_anio_obra.find((option) => option.id === id)).filter(Boolean);
    populateSelect("year-precision", yearOptions);
    populateArtistOptions();
    workYear.max = String(saleYear);
    const [fromYear, toYear] = metadata.training_years;
    byId("training-info").textContent = `El modelo usa ${measurement.format(metadata.training_rows)} remates históricos de Bogotá entre ${fromYear} y ${toYear}, en pesos nominales. Usa el año de consulta para calcular la edad de la obra.`;

    saveArtistButton.addEventListener("click", toggleSavedArtist);
    exampleButton.addEventListener("click", loadExample);
    form.addEventListener("input", onFormInput);
    form.addEventListener("submit", calculateEstimate);
    byId("clear-form").addEventListener("click", clearForm);
    form.addEventListener("invalid", (event) => {
      if (moreDetails.contains(event.target)) moreDetails.open = true;
    }, true);
    syncConditionalFields();
    updateArtistStatus();
    drawStudy();
    fields.disabled = false;
    exampleButton.disabled = false;
    showAppMessage("");
  } catch {
    showAppMessage("Hubo un problema al cargar el modelo. Recarga la página para reintentar.");
  }
}

initialize();
