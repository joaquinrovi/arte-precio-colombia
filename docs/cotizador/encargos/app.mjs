import { calculateCommission } from "./calculate.mjs";

const byId = (id) => document.getElementById(id);
const form = byId("commission-form");
const fields = byId("commission-fields");
const options = byId("commission-options");
const errorMessage = byId("commission-error");
const result = byId("commission-result");
const price = byId("commission-price");
const status = byId("commission-status");
const breakdown = byId("commission-breakdown");
const feeLine = byId("fee-line");
const netLine = byId("net-line");
const values = {
  directCost: byId("direct-cost-value"),
  labor: byId("labor-value"),
  base: byId("base-value"),
  reserve: byId("reserve-value"),
  fee: byId("fee-value"),
  net: byId("net-value"),
};

const oilExampleButton = byId("example-oil");
const oilExampleInputs = { materials: 80000, extras: 20000, hours: 12, hourlyRate: 25000, reservePercent: 10 };

const money = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  currencyDisplay: "narrowSymbol",
  maximumFractionDigits: 0,
});
const defaultStatus = status.textContent;

function showError(message = "") {
  errorMessage.textContent = message;
  errorMessage.hidden = !message;
}

function clearResult(message = defaultStatus) {
  price.hidden = true;
  status.textContent = message;
  breakdown.hidden = true;
}

function showQuote(quote, hasFee, isExample) {
  price.textContent = money.format(quote.quote);
  price.hidden = false;
  status.textContent = isExample
    ? "Ejemplo ilustrativo de óleo. Puedes cambiar los valores."
    : "Precio redondeado hacia arriba a múltiplos de $1.000.";

  for (const [key, value] of Object.entries(values)) {
    value.textContent = money.format(quote[key]);
  }
  breakdown.hidden = false;
  feeLine.hidden = !hasFee;
  netLine.hidden = !hasFee;
}

function calculateQuote(isExample = false) {
  const inputs = Object.fromEntries(new FormData(form));
  for (const [key, value] of Object.entries(inputs)) {
    inputs[key] = value === "" ? undefined : Number(value);
  }

  try {
    showQuote(calculateCommission(inputs), inputs.feePercent > 0, isExample);
    showError();
    return true;
  } catch (error) {
    clearResult();
    showError(error.message);
    return false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (calculateQuote()) {
    result.focus({ preventScroll: true });
    result.scrollIntoView({ block: "nearest" });
  }
});

form.addEventListener("input", () => {
  showError();
  if (!price.hidden) clearResult("Pulsa Calcular precio para actualizar el presupuesto.");
});

form.addEventListener("invalid", (event) => {
  if (options.contains(event.target)) options.open = true;
}, true);

byId("clear-commission").addEventListener("click", () => {
  form.reset();
  options.open = false;
  showError();
  clearResult();
  byId("materials").focus();
});

oilExampleButton.addEventListener("click", () => {
  form.reset();
  for (const [key, value] of Object.entries(oilExampleInputs)) form.elements.namedItem(key).value = value;
  options.open = true;
  calculateQuote(true);
});

oilExampleButton.disabled = false;
fields.disabled = false;
