import { addFrameCost, findComparableOffers, frameTotal } from "./compare.mjs?v=4";

const form = document.querySelector("#references-form");
const fields = document.querySelector("#references-fields");
const results = document.querySelector("#reference-results");
const status = document.querySelector("#result-status");
const list = document.querySelector("#offer-list");
const errorMessage = document.querySelector("#references-error");
const galleryCard = document.querySelector("#gallery-reference");
const galleryPrice = document.querySelector("#gallery-price");
const galleryTotalLabel = document.querySelector("#gallery-total-label");
const galleryBreakdown = document.querySelector("#gallery-breakdown");
const galleryCaption = document.querySelector("#gallery-caption");
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

const examples = [
  ["#example-oil", { technique: "oleo", subject: "obra", width: 60, height: 80 }],
  ["#example-graphite", { technique: "grafito", subject: "retrato", width: 35, height: 50 }],
];

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
  const total = price === null ? null : addFrameCost(Math.round(price), frameCost);
  const hasTotal = total !== null;
  galleryTotalLabel.hidden = !hasTotal;
  galleryPrice.textContent = price === null ? "" : money.format(total ?? price);
  galleryPrice.hidden = price === null;
  galleryBreakdown.hidden = !hasTotal;
  galleryBreakdown.replaceChildren(...(hasTotal ? [
    detail("Precio base estimado", money.format(price)),
    detail("Marco cotizado", money.format(frameCost)),
  ] : []));
}

function showGalleryReference(gallery, query, frameCost) {
  let price = null;
  let caption = "La referencia de galería no está disponible en este momento.";
  if (query.technique === "grafito") {
    caption = "Para grafito, consulta las tarifas publicadas de encargo. El modelo de galería se usa para óleo.";
  } else if (gallery) {
    try {
      const year = new Date().getFullYear();
      price = gallery.estimate(gallery.model, { width: query.width, height: query.height, year });
      caption = price === null
        ? "Estas medidas quedan fuera de la cobertura del modelo de óleo."
        : "Estimación de un precio de catálogo de La Galería Online para un óleo de estas medidas. El modelo predictivo usa el año actual para una obra nueva.";
    } catch {
      caption = "No se pudo calcular la referencia experimental de galería.";
    }
  }

  showGalleryPrice(price, frameCost);
  galleryCard.hidden = false;
  galleryCaption.textContent = caption;
}

function enableSearch(offers, date, gallery) {
  let searched = false;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    showError();
    const { technique, subject, width, height, frameCost } = Object.fromEntries(new FormData(form));
    try {
      const query = {
        technique,
        subject,
        width: Number(width),
        height: Number(height),
      };
      const matches = findComparableOffers(offers, query);
      const enteredFrameCost = frameCost === "" ? null : Number(frameCost);
      list.replaceChildren(...matches.map((offer) => renderOffer(offer, enteredFrameCost)));
      list.hidden = matches.length === 0;
      const count = matches.length === 1 ? "1 oferta publicada" : `${matches.length} ofertas publicadas`;
      status.textContent = matches.length
        ? `${count}. Fuentes consultadas el ${date}.`
        : "No encontramos ofertas comparables para esta técnica, tipo de encargo y medidas.";
      showGalleryReference(gallery, query, enteredFrameCost);
      searched = true;
      results.focus({ preventScroll: true });
      results.scrollIntoView({ block: "nearest" });
    } catch (error) {
      list.hidden = true;
      galleryCard.hidden = true;
      status.textContent = "Revisa los datos del encargo.";
      showError(error instanceof RangeError ? error.message : "No se pudo completar la búsqueda.");
    }
  });

  form.addEventListener("input", () => {
    showError();
    if (!searched) return;
    list.hidden = true;
    galleryCard.hidden = true;
    status.textContent = "Pulsa Buscar precios para actualizar las ofertas según los datos ingresados.";
  });

  form.addEventListener("reset", () => {
    searched = false;
    list.replaceChildren();
    list.hidden = true;
    galleryCard.hidden = true;
    showGalleryPrice(null, null);
    galleryCaption.textContent = "";
    showError();
    status.textContent = initialStatus;
  });

  for (const [id, inputs] of examples) {
    document.querySelector(id).addEventListener("click", () => {
      form.reset();
      for (const [key, value] of Object.entries(inputs)) form.elements.namedItem(key).value = value;
      form.requestSubmit();
    });
  }

  fields.disabled = false;
  status.textContent = initialStatus;
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
    status.textContent = "Las ofertas no pudieron cargarse. Vuelve a intentarlo recargando la página.";
  }
}

await loadCatalog();
