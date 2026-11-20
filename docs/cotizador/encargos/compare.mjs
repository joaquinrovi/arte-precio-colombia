const TECHNIQUES = new Set(["oleo", "grafito"]);
const SUBJECTS = new Set(["retrato", "obra"]);
const PRICE_KINDS = new Set(["fijo", "desde"]);
const FRAME_STATES = new Set(["incluido", "no_incluido", "sin_indicar"]);
const SIDE_TOLERANCE = 0.25 + Number.EPSILON;

function validDimension(value) {
  return Number.isFinite(value) && value > 0;
}

function validPrice(value) {
  return Number.isSafeInteger(value) && value > 0;
}

function safeSource(url) {
  if (typeof url !== "string") return false;
  try {
    const source = new URL(url);
    return source.protocol === "https:" && !source.username && !source.password;
  } catch {
    return false;
  }
}

function validOffer(offer) {
  return typeof offer.seller === "string" && offer.seller.trim() !== ""
    && validDimension(offer.width) && validDimension(offer.height)
    && validPrice(offer.price) && PRICE_KINDS.has(offer.kind)
    && FRAME_STATES.has(offer.frame) && safeSource(offer.url)
    && (offer.leadTime == null || typeof offer.leadTime === "string")
    && (offer.note == null || typeof offer.note === "string");
}

export function findComparableOffers(offers, request) {
  const { technique, subject, width, height } = request ?? {};
  if (!TECHNIQUES.has(technique) || !SUBJECTS.has(subject)) {
    throw new RangeError("Selecciona una técnica y un tipo de obra.");
  }
  if (!validDimension(width) || !validDimension(height)) {
    throw new RangeError("Ingresa medidas mayores que cero en centímetros.");
  }

  const shortSide = Math.min(width, height);
  const longSide = Math.max(width, height);
  const closestBySeller = new Map();
  for (const offer of offers) {
    if (offer?.technique !== technique || offer.subject !== subject || !validOffer(offer)) continue;

    const shortDifference = Math.abs(Math.min(offer.width, offer.height) - shortSide) / shortSide;
    const longDifference = Math.abs(Math.max(offer.width, offer.height) - longSide) / longSide;
    if (Math.max(shortDifference, longDifference) > SIDE_TOLERANCE) continue;

    const distance = shortDifference + longDifference;
    const sellerKey = offer.seller.trim().normalize("NFC").toLocaleLowerCase("es-CO");
    const previous = closestBySeller.get(sellerKey);
    if (!previous || distance < previous.distance) {
      closestBySeller.set(sellerKey, { offer, distance });
    }
  }

  return [...closestBySeller.values()]
    .sort((a, b) => a.distance - b.distance || a.offer.seller.localeCompare(b.offer.seller, "es-CO"))
    .map(({ offer, distance }) => ({ ...offer, exact: distance === 0 }));
}

export function frameTotal(offer, frameCost) {
  if (offer?.frame !== "no_incluido" || !validPrice(offer.price)
      || !Number.isSafeInteger(frameCost) || frameCost < 0) return null;

  const total = offer.price + frameCost;
  return Number.isSafeInteger(total) ? total : null;
}
