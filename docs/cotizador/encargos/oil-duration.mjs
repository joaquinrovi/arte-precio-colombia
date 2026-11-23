// Bandas de planificación a partir de formatos y plazos publicados por Kartidia Fine Art.
// Los límites de área están redondeados a partir de 11 × 14, 18 × 24 y 30 × 40 pulgadas.
const SIZE_BANDS = [
  { maxArea: 1000, label: "4 a 6 semanas" },
  { maxArea: 2800, label: "8 a 10 semanas" },
  { maxArea: 7750, label: "10 a 14 semanas o más" },
];

export function oilDurationRange(width, height) {
  if (!Number.isFinite(width) || !Number.isFinite(height)) return null;
  if (Math.min(width, height) < 20 || Math.max(width, height) > 102) return null;
  return SIZE_BANDS.find(({ maxArea }) => width * height <= maxArea)?.label ?? null;
}
