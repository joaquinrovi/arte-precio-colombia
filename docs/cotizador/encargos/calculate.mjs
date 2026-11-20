const QUOTE_STEP = 1_000n;
const MAX_SAFE_PESOS = BigInt(Number.MAX_SAFE_INTEGER);

function costInPesos(value, label) {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new RangeError(`${label} debe ser un monto entero en pesos colombianos, igual o mayor que cero.`);
  }
  return BigInt(value);
}

// Conservar los decimales ingresados evita sumar $1.000 de más en un límite exacto.
function decimalRatio(value) {
  const [mantissa, exponent = "0"] = String(value).split("e");
  const [integer, fraction = ""] = mantissa.split(".");
  const places = fraction.length - Number(exponent);
  const digits = BigInt(integer + fraction);
  const numerator = places < 0 ? digits * 10n ** BigInt(-places) : digits;
  return [numerator, 10n ** BigInt(Math.max(places, 0))];
}

function percentRatio(value, label, canEqualHundred) {
  if (!Number.isFinite(value) || value < 0 || value > 100 || (!canEqualHundred && value === 100)) {
    const range = canEqualHundred ? "entre 0 % y 100 %" : "igual o mayor que 0 % y menor que 100 %";
    throw new RangeError(`${label} debe ser ${range}.`);
  }
  const [numerator, denominator] = decimalRatio(value);
  return [numerator, denominator * 100n];
}

function nearestPeso(numerator, denominator) {
  return (numerator + denominator / 2n) / denominator;
}

export function calculateCommission({ materials, extras, hours, hourlyRate, reservePercent, feePercent }) {
  if (!Number.isFinite(hours) || hours <= 0) {
    throw new RangeError("Ingresa una cantidad positiva de horas de trabajo.");
  }
  if (!Number.isFinite(hourlyRate) || hourlyRate <= 0) {
    throw new RangeError("Ingresa una tarifa por hora mayor que cero.");
  }
  const directCost = costInPesos(materials ?? 0, "El costo de materiales")
    + costInPesos(extras ?? 0, "El costo de los gastos adicionales");
  const [time, timeScale] = decimalRatio(hours);
  const [rate, rateScale] = decimalRatio(hourlyRate);
  const labor = nearestPeso(time * rate, timeScale * rateScale);
  if (labor < 1n) {
    throw new RangeError("El pago por el tiempo de trabajo debe sumar al menos $1 COP.");
  }

  const base = directCost + labor;
  const [reserveRate, reserveScale] = percentRatio(reservePercent ?? 0, "La reserva", true);
  const reserve = nearestPeso(base * reserveRate, reserveScale);
  const subtotal = base + reserve;

  const [feeRate, feeScale] = percentRatio(feePercent ?? 0, "La comisión", false);
  const netPerStep = (feeScale - feeRate) * QUOTE_STEP;
  const steps = (subtotal * feeScale + netPerStep - 1n) / netPerStep;
  const quote = steps * QUOTE_STEP;
  if (quote > MAX_SAFE_PESOS) {
    throw new RangeError("El total es demasiado alto para calcularlo con precisión. Revisa los montos y la comisión.");
  }
  const fee = nearestPeso(quote * feeRate, feeScale);
  const net = quote - fee;

  return {
    directCost: Number(directCost),
    labor: Number(labor),
    base: Number(base),
    reserve: Number(reserve),
    subtotal: Number(subtotal),
    fee: Number(fee),
    quote: Number(quote),
    net: Number(net),
  };
}
