import { findComparableOffers, frameTotal, galleryQuote } from "./compare.mjs?v=6";
import { oilDurationRange } from "./oil-duration.mjs";

const form = document.querySelector("#references-form");
const fields = document.querySelector("#references-fields");
const results = document.querySelector("#reference-results");
const status = document.querySelector("#result-status");
const offerDisclosure = document.querySelector("#offer-disclosure");
const offerSummary = document.querySelector("#offer-summary");
const offerSources = document.querySelector("#offer-sources");
const list = document.querySelector("#offer-list");
const errorMessage = document.querySelector("#references-error");
const galleryCard = document.querySelector("#gallery-reference");
const galleryPrice = document.querySelector("#gallery-price");
const galleryTotalLabel = document.querySelector("#gallery-total-label");
const galleryBreakdown = document.querySelector("#gallery-breakdown");
const galleryCaption = document.querySelector("#gallery-caption");
const durationCard = document.querySelector("#oil-duration");
const durationRange = document.querySelector("#oil-duration-range");
const durationNote = document.querySelector("#oil-duration-note");
const initialStatus = "Completa los datos del encargo o prueba un ejemplo para ver las ofertas disponibles.";

const money = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});
const measures = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2 });
const dateFormat = new Intl.DateTimeFormat("es-CO", { dateStyle: "long", timeZone: "UTC" });
const frameLabels = {
  incluido: "Incluido",
  no_incluido: "Sin enmarcar",
  sin_indicar: "Sin especificar",
};

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function detail(label, value) {
  const row = element("div");
  row.append(element("dt", label), element("dd", value));
  return row;
}

function publishedAmount(kind, price) {
  return `${kind === "desde" ? "Desde " : ""}${money.format(price)}`;
}

function renderOffer(offer, frameCost) {
  const card = element("li", "", "offer-card");
  const heading = element("div", "", "offer-heading");
  const source = element("a", offer.seller, "offer-source");
  source.href = offer.url;
  source.target = "_blank";
  source.rel = "noopener noreferrer";
  heading.append(element("h3", publishedAmount(offer.kind, offer.price), "offer-price"), source);

  const dimensions = `${measures.format(offer.width)} × ${measures.format(offer.height)} cm`;
  const details = element("dl", "", "offer-details");
  details.append(
    detail(offer.exact ? "Medida exacta" : "Medida cercana", dimensions),
    detail("Marco", frameLabels[offer.frame]),
    detail("Plazo publicado", offer.leadTime || "Sin especificar"),
  );

  card.append(heading, details);
  if (offer.note) card.append(element("p", offer.note, "offer-note"));

  const total = offer.exact ? frameTotal(offer, frameCost) : null;
  if (total !== null) {
    const addition = element("p", "Precio publicado + tu marco ", "offer-frame-total");
    addition.append(element("strong", publishedAmount(offer.kind, total)));
    card.append(addition);
  }
  return card;
}

function showError(message = "") {
  errorMessage.textContent = message;
  errorMessage.hidden = !message;
}

function showStatus(message = "") {
  status.textContent = message;
  status.hidden = !message;
}

function hideOffers() {
  offerDisclosure.open = false;
  offerDisclosure.hidden = true;
}

async function loadGalleryReference() {
  try {
    const [response, calculator] = await Promise.all([
      fetch(new URL("./gallery-model.json", import.meta.url)),
      import("./gallery-predict.mjs?v=2"),
    ]);
    if (!response.ok) return null;
    const model = await response.json();
    return { model, estimate: calculator.estimateGalleryOil };
  } catch {
    return null;
  }
}

function showGalleryPrice(price, frameCost) {
  const quote = galleryQuote(price, frameCost);
  galleryTotalLabel.hidden = quote === null;
  galleryPrice.textContent = quote === null ? "" : money.format(quote.total);
  galleryPrice.hidden = quote === null;
  galleryBreakdown.hidden = quote === null;
  galleryBreakdown.replaceChildren();
  if (quote === null) return;

  galleryBreakdown.append(detail("Precio base estimado", money.format(quote.base)));
  if (quote.frameCost !== null) {
    galleryBreakdown.append(
      detail("Marco cotizado", money.format(quote.frameCost)),
      detail("Subtotal", money.format(quote.subtotal)),
    );
  }
  galleryBreakdown.append(detail("IVA (19 %)", money.format(quote.vat)));
}

function showGalleryReference(gallery, query, frameCost) {
  let price = null;
  let caption = "La referencia de galería no está disponible en este momento.";
  if (gallery) {
    try {
      const year = new Date().getFullYear();
      price = gallery.estimate(gallery.model, { width: query.width, height: query.height, year });
      caption = price === null
        ? "Estas medidas quedan fuera de la cobertura del modelo de óleo."
        : "El modelo predictivo estima un precio de catálogo de La Galería Online para un óleo nuevo de estas medidas. El cálculo del total toma esa referencia como valor antes de IVA.";
    } catch {
      caption = "No se pudo calcular la referencia experimental de galería.";
    }
  }

  showGalleryPrice(price, frameCost);
  galleryCard.hidden = false;
  galleryCaption.textContent = caption;
}

function showOilDuration(query) {
  durationCard.hidden = false;
  const range = oilDurationRange(query.width, query.height);
  durationRange.textContent = range ?? "";
  durationRange.hidden = range === null;
  durationNote.textContent = range
    ? "Óleo sobre lienzo. Guía por área basada en plazos publicados que incluyen la pintura y el secado. El grosor de las capas y los pigmentos pueden cambiar el plazo."
    : "Estas medidas quedan fuera de los formatos de referencia. Acuerda con el artista un plazo que incluya el secado.";
}

function enableSearch(offers, date, gallery) {
  offerSources.textContent = `Fuentes consultadas el ${date}.`;
  let searched = false;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    showError();
    const { subject, width, height, frameCost } = Object.fromEntries(new FormData(form));
    try {
      const query = {
        technique: "oleo",
        subject,
        width: Number(width),
        height: Number(height),
      };
      const matches = findComparableOffers(offers, query);
      const enteredFrameCost = frameCost === "" ? null : Number(frameCost);
      list.replaceChildren(...matches.map((offer) => renderOffer(offer, enteredFrameCost)));
      offerDisclosure.open = false;
      offerDisclosure.hidden = matches.length === 0;
      offerSummary.textContent = `Ver ofertas de encargo (${matches.length})`;
      showGalleryReference(gallery, query, enteredFrameCost);
      showOilDuration(query);
      showStatus(matches.length || !galleryPrice.hidden
        ? ""
        : "No encontramos ofertas comparables de óleo para este tipo de encargo y medidas.");
      searched = true;
      results.focus({ preventScroll: true });
      results.scrollIntoView({ block: "nearest" });
    } catch (error) {
      hideOffers();
      galleryCard.hidden = true;
      durationCard.hidden = true;
      showStatus("Revisa los datos del encargo.");
      showError(error instanceof RangeError ? error.message : "No se pudo completar la búsqueda.");
    }
  });

  form.addEventListener("input", () => {
    showError();
    if (!searched) return;
    hideOffers();
    galleryCard.hidden = true;
    durationCard.hidden = true;
    showStatus("Pulsa Buscar precios para actualizar las ofertas según los datos ingresados.");
  });

  form.addEventListener("reset", () => {
    searched = false;
    list.replaceChildren();
    hideOffers();
    galleryCard.hidden = true;
    durationCard.hidden = true;
    showGalleryPrice(null, null);
    galleryCaption.textContent = "";
    showError();
    showStatus(initialStatus);
  });

  document.querySelector("#example-oil").addEventListener("click", () => {
    form.reset();
    form.elements.namedItem("width").value = 60;
    form.elements.namedItem("height").value = 80;
    form.requestSubmit();
  });

  fields.disabled = false;
  showStatus(initialStatus);
}

async function loadCatalog() {
  try {
    const [response, gallery] = await Promise.all([
      fetch(new URL("./offers.json", import.meta.url)),
      loadGalleryReference(),
    ]);
    if (!response.ok) throw new Error("Catálogo sin acceso");
    const catalog = await response.json();
    if (!Array.isArray(catalog.offers)) throw new Error("Catálogo inválido");
    const date = dateFormat.format(new Date(`${catalog.checkedAt}T00:00:00Z`));
    enableSearch(catalog.offers, date, gallery);
  } catch {
    showStatus("Las ofertas no pudieron cargarse. Vuelve a intentarlo recargando la página.");
  }
}

await loadCatalog();
