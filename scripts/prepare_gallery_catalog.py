"""Prepare a local snapshot of factual fields from La Galería Online listings."""

import argparse
import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


RAW_COLUMNS = (
    "artist", "title", "technique", "support", "width_cm", "height_cm", "year",
    "price_cop", "url", "availability",
)
TRACE_COLUMNS = ("technique_raw", "dimensions_raw", "source_ref")
TECHNIQUES = {
    "oleo": r"\boleo\b",
    "grafito": r"\bgrafito\b",
    "lapiz": r"\blapiz\b",
    "acrilico": r"\bacrilic[oa]s?\b",
    "acuarela": r"\bacuarelas?\b",
    "carboncillo": r"\b(?:carbon|carboncillo)\b",
    "tinta": r"\btinta\b",
    "pastel": r"\bpastel(?:es)?\b",
    "tempera": r"\btempera\b",
}
SUPPORTS = ("lienzo", "papel", "madera", "carton", "tela", "metal")
DIMENSION_PAIR = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:cm)?\s*[x×]\s*(\d+(?:[.,]\d+)?)")
NON_PLANAR_OR_PRINT = re.compile(
    r"\b(?:escultura|instalacion|fotografi\w*|impresion|giclee|serigrafia|grabado|digital|ceramica|mobiliario)\b"
)
FRAMED = re.compile(r"\b(?:con marco|enmarcad[ao])\b")


def normalized(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).split())


def technique_and_support(raw: str, supplied_support: str) -> tuple[str, str]:
    label = normalized(raw)
    if NON_PLANAR_OR_PRINT.search(label):
        return "", ""

    medium, _, stated_support = label.partition(" sobre ")
    named = [name for name, pattern in TECHNIQUES.items() if re.search(pattern, medium)]
    colored_pencil = bool(re.search(r"\blapi(?:z|ces) (?:de )?color(?:es)?\b", medium))
    additional_media = r"\b(?:mixta|collage|marcador\w*|esmalte|hojilla|repujado)\b"
    mixed = len(named) > 1 or bool(re.search(additional_media, label))
    if colored_pencil and not mixed:
        technique = "lapiz_color"
    elif mixed:
        technique = "mixta"
    else:
        technique = named[0] if named else ""

    support_text = (stated_support or normalized(supplied_support)).split(" montado ")[0]
    matches = [support for support in SUPPORTS if re.search(rf"\b{support}\b", support_text)]
    return technique, matches[0] if len(matches) == 1 else ""


def canonical_product_url(value: str) -> str:
    try:
        url = urlsplit(value)
    except ValueError:
        return ""
    handle = re.search(r"/products/([\w-]+)/?$", url.path, flags=re.ASCII)
    if url.scheme != "https" or url.netloc not in {"lagaleriaonline.co", "www.lagaleriaonline.co"}:
        return ""
    return f"https://lagaleriaonline.co/products/{handle[1]}" if handle else ""


def dimensions_from_label(raw: str) -> tuple[float, float] | None:
    label = normalized(raw)
    if re.search(r"\b(?:diametro|bipartito|diptico|triptico|poliptico|cada|mm|pulgadas)\b|\d\s*m\b", label):
        return None
    pairs = list(DIMENSION_PAIR.finditer(label))
    if not pairs or len(pairs) > 2:
        return None
    if any(re.match(r"\s*(?:cm)?\s*[x×]\s*\d", label[pair.end():]) for pair in pairs):
        return None
    chosen = pairs[0]
    if len(pairs) == 1:
        if FRAMED.search(label):
            return None
    else:
        first_suffix = label[pairs[0].end():pairs[1].start()]
        last_suffix = label[pairs[1].end():]
        if "sin marco" in last_suffix and FRAMED.search(first_suffix):
            chosen = pairs[1]
        elif "sin marco" in first_suffix and FRAMED.search(last_suffix):
            chosen = pairs[0]
        elif not re.fullmatch(r"\s*(?:cm)?\s*\(\s*(?:enmarcad[ao]|con marco)\s*", first_suffix):
            return None
    return tuple(float(side.replace(",", ".")) for side in chosen.groups())


def positive_number(value: str) -> float | None:
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        return None
    return number if math.isfinite(number) and number > 0 else None


def prepare_row(raw: dict, date: str) -> tuple[dict | None, str]:
    row = {column: (raw.get(column) or "").strip() for column in RAW_COLUMNS + TRACE_COLUMNS}
    url = canonical_product_url(row["url"])
    if not url or not row["artist"]:
        return None, "fuente_o_artista_ausente"

    price = positive_number(row["price_cop"])
    if price is None or not price.is_integer():
        return None, "precio_invalido"

    raw_dimensions = row["dimensions_raw"]
    dimensions = dimensions_from_label(raw_dimensions) if raw_dimensions else (
        positive_number(row["width_cm"]), positive_number(row["height_cm"]),
    )
    if not dimensions or not all(side is not None and side > 0 for side in dimensions):
        return None, "medidas_no_comparables"
    width, height = dimensions

    technique_raw = row["technique_raw"] or row["technique"]
    technique, support = technique_and_support(technique_raw, row["support"])
    if not technique:
        return None, "tecnica_fuera_de_alcance"

    year = row["year"]
    row.update(
        artist=" ".join(row["artist"].split()),
        url=url,
        listing_url=raw["url"].strip(),
        technique_raw=technique_raw,
        technique=technique,
        support=support,
        width_cm=width,
        height_cm=height,
        year=int(year) if re.fullmatch(r"\d{4}", year) and 1000 <= int(year) <= int(date[:4]) else "",
        price_cop=int(price),
        consulted_at=date,
    )
    return row, ""


def prepare_catalog(inputs: list[Path], output: Path, date: str) -> dict:
    records = {}
    conflicted = set()
    source_files = []
    excluded = Counter()
    for source in inputs:
        source_files.append({"file": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
        with source.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if missing := set(RAW_COLUMNS) - set(reader.fieldnames or ()):
                raise ValueError(f"{source.name}: faltan columnas {', '.join(sorted(missing))}.")
            for raw in reader:
                row, reason = prepare_row(raw, date)
                if row is None:
                    excluded[reason] += 1
                    continue
                key = row["url"]
                if key in conflicted:
                    excluded["duplicado_conflictivo"] += 1
                    continue
                if key not in records:
                    records[key] = row
                    continue
                previous = records[key]
                same_artist = normalized(row["artist"]) == normalized(previous["artist"])
                salient = ("price_cop", "width_cm", "height_cm", "technique")
                if not same_artist or any(row[column] != previous[column] for column in salient):
                    conflicted.add(key)
                    records.pop(key)
                    excluded["duplicado_conflictivo"] += 2
                else:
                    excluded["duplicado_equivalente"] += 1

    if not records:
        raise ValueError("No hay fichas válidas para preparar el conjunto de datos.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        fields = RAW_COLUMNS + TRACE_COLUMNS + ("listing_url", "consulted_at")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records[key] for key in sorted(records))

    rows = list(records.values())
    manifest = {
        "source": "https://lagaleriaonline.co/collections/obras",
        "consulted_at": date,
        "target": "precio_publicado_cop",
        "inputs": source_files,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "rows": len(rows),
        "artists": len({normalized(row["artist"]) for row in rows}),
        "by_technique": dict(Counter(row["technique"] for row in rows)),
        "by_availability": dict(Counter(row["availability"] for row in rows)),
        "excluded": dict(excluded),
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    from datetime import date

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--consulted-at", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    manifest = prepare_catalog(args.input, args.output, args.consulted_at.isoformat())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
