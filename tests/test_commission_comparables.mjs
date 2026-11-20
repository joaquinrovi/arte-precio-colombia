import assert from "node:assert/strict";
import { test } from "node:test";
import { findComparableOffers, frameTotal } from "../docs/cotizador/encargos/compare.mjs";

const request = { technique: "oleo", subject: "retrato", width: 40, height: 60 };
const offer = {
  seller: "Taller A",
  url: "https://example.com/retrato",
  ...request,
  price: 600_000,
  kind: "fijo",
  frame: "no_incluido",
  leadTime: "15 días hábiles",
};

test("filtra por técnica y tipo y reconoce las dimensiones independientemente de la orientación", () => {
  const rotated = { ...offer, width: 60, height: 40 };
  const catalog = [rotated, { ...offer, technique: "grafito" }, { ...offer, subject: "obra" }];
  assert.deepEqual(findComparableOffers(catalog, request), [{ ...rotated, exact: true }]);
  assert.equal(rotated.exact, undefined);
});

test("selecciona una oferta por vendedor y ordena por cercanía y luego por nombre", () => {
  const similar = { ...offer, width: 38, height: 62, price: 730_000 };
  const exact = { ...offer, seller: " Taller A ", price: 660_000 };
  const sameDistanceB = { ...similar, seller: "Taller B" };
  const sameDistanceC = { ...similar, seller: "Taller C" };
  const matches = findComparableOffers([similar, sameDistanceC, exact, sameDistanceB], request);
  assert.deepEqual(matches, [
    { ...exact, exact: true },
    { ...sameDistanceB, exact: false },
    { ...sameDistanceC, exact: false },
  ]);
});

test("acepta el 25 % por lado y se abstiene fuera de cobertura", () => {
  const boundary = { ...offer, width: 30, height: 75, kind: "desde" };
  const tooLong = { ...offer, height: 75.01 };
  const tooNarrow = { ...offer, width: 29.99 };
  assert.deepEqual(findComparableOffers([tooLong, tooNarrow, boundary], request), [
    { ...boundary, exact: false },
  ]);
  assert.deepEqual(findComparableOffers([tooLong, tooNarrow], request), []);
});

test("rechaza consultas inválidas y omite entradas de catálogo defectuosas", () => {
  for (const invalid of [{ width: 0 }, { height: NaN }, { width: "40" }, { subject: "paisaje" }]) {
    assert.throws(() => findComparableOffers([offer], { ...request, ...invalid }), RangeError);
  }
  assert.deepEqual(findComparableOffers([
    null,
    { ...offer, url: "javascript:void(0)" },
    { ...offer, url: "https://name:pass@example.com/" },
    { ...offer, price: 600_000.5 },
    { ...offer, frame: "desconocido" },
    { ...offer, seller: " " },
    { ...offer, width: Infinity },
  ], request), []);
});

test("solo suma un costo de marco válido si la oferta lo excluye expresamente", () => {
  assert.equal(frameTotal(offer, 75_000), 675_000);
  assert.equal(frameTotal(offer, 0), 600_000);
  assert.equal(frameTotal({ ...offer, frame: "incluido" }, 75_000), null);
  assert.equal(frameTotal({ ...offer, frame: "sin_indicar" }, 75_000), null);
  for (const value of [null, "75000", 1.1, -1, Infinity, Number.MAX_SAFE_INTEGER]) {
    assert.equal(frameTotal(offer, value), null);
  }
});
