import assert from "node:assert/strict";
import { test } from "node:test";
import { calculateCommission } from "../docs/cotizador/encargos/calculate.mjs";

const oil = {
  materials: 80_000, extras: 20_000, hours: 12, hourlyRate: 25_000, reservePercent: 10,
};

test("desglosa los materiales, el trabajo y la reserva de un encargo al óleo", () => {
  assert.deepEqual(calculateCommission(oil), {
    directCost: 100_000, labor: 300_000, base: 400_000, reserve: 40_000,
    subtotal: 440_000, fee: 0, quote: 440_000, net: 440_000,
  });
});

test("cotiza un dibujo a grafito e incluye la comisión sobre el total", () => {
  const graphite = {
    materials: 28_000, extras: 12_000, hours: 6, hourlyRate: 20_000, reservePercent: 10,
  };
  assert.equal(calculateCommission(graphite).quote, 176_000);
  assert.deepEqual(calculateCommission({ ...graphite, feePercent: 3.5 }), {
    directCost: 40_000, labor: 120_000, base: 160_000, reserve: 16_000,
    subtotal: 176_000, fee: 6_405, quote: 183_000, net: 176_595,
  });
});

test("permite costos directos omitidos, opcionales vacíos y horas fraccionarias", () => {
  assert.deepEqual(calculateCommission({ materials: null, hours: 1.5, hourlyRate: 21_500 }), {
    directCost: 0, labor: 32_250, base: 32_250, reserve: 0,
    subtotal: 32_250, fee: 0, quote: 33_000, net: 33_000,
  });
});

test("redondea los decimales de cada concepto al peso sin añadir miles en un límite exacto", () => {
  const fractional = calculateCommission({ hours: 0.29, hourlyRate: 50, reservePercent: 10 });
  assert.equal(fractional.labor, 15);
  assert.equal(fractional.reserve, 2);
  const exact = calculateCommission({ hours: 1, hourlyRate: 96_800, feePercent: 3.2 });
  assert.equal(exact.quote, 100_000);
  assert.equal(exact.net, exact.subtotal);
});

test("mantiene el subtotal después de descontar la comisión, incluso cerca del 100 %", () => {
  for (const feePercent of [0, 0.05, 10.99, 93, 99.99, 99.9999999999999]) {
    const result = calculateCommission({ hours: 1, hourlyRate: 1, feePercent });
    assert.equal(result.quote % 1_000, 0);
    assert.equal(result.net, result.quote - result.fee);
    assert.ok(result.net >= result.subtotal);
  }
});

test("rechaza datos fuera de rango, tipos inválidos y resultados que pierden precisión", () => {
  const invalidInputs = [
    { materials: -1 }, { extras: 1.1 }, { materials: "25000" },
    { hours: 0 }, { hours: NaN }, { hours: undefined }, { hourlyRate: Infinity },
    { reservePercent: -1 }, { reservePercent: 101 }, { feePercent: 100 },
    { feePercent: -0.1 }, { hours: 1e10, hourlyRate: 1e10 },
    { feePercent: 99.99999999999999 },
  ];
  for (const values of invalidInputs) {
    assert.throws(() => calculateCommission({ ...oil, ...values }), RangeError);
  }
  assert.throws(() => calculateCommission({ hours: 0.01, hourlyRate: 1 }), RangeError);
});
