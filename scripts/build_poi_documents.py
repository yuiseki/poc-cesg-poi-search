#!/usr/bin/env python3
"""Build poi-documents.parquet from input Parquet/GeoParquet."""
from __future__ import annotations
import argparse
import json
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from poc_cesg_poi_search.tokenizer import (
    normalize_text,
    build_exact_tokens,
    build_category_tokens,
    build_morph_tokens,
    build_name_bigram_tokens,
    build_name_trigram_tokens,
)
from poc_cesg_poi_search.quadkey import lonlat_to_quadkey

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _extract_name(names_val) -> tuple[str, str, str]:
    """Return (name_primary, name_normalized, names_all) from names column."""
    if names_val is None:
        return "", "", ""
    if isinstance(names_val, str):
        try:
            names_val = json.loads(names_val)
        except Exception:
            return names_val, normalize_text(names_val), names_val

    primary = ""
    all_names: list[str] = []

    if isinstance(names_val, dict):
        primary = names_val.get("primary", "") or ""
        common = names_val.get("common", []) or []
        if isinstance(common, list):
            for entry in common:
                if isinstance(entry, dict):
                    v = entry.get("value", "")
                    if v:
                        all_names.append(str(v))
                elif isinstance(entry, str):
                    all_names.append(entry)
        if not primary and all_names:
            primary = all_names[0]
    elif isinstance(names_val, str):
        primary = names_val

    if primary and primary not in all_names:
        all_names.insert(0, primary)

    return primary, normalize_text(primary), " ".join(all_names)


def _extract_category(row: pd.Series) -> tuple[str, str]:
    """Return (category_primary, category_path)."""
    cat = ""
    path = ""
    if "categories" in row.index and row.get("categories") is not None:
        cats = row["categories"]
        if isinstance(cats, str):
            try:
                cats = json.loads(cats)
            except Exception:
                return str(cats), str(cats)
        if isinstance(cats, dict):
            cat = cats.get("primary", "") or ""
            alts = cats.get("alternate", None)
            try:
                alts = list(alts) if alts is not None else []
            except Exception:
                alts = []
            path = " > ".join([cat] + [str(a) for a in alts if a])
        elif isinstance(cats, list) and cats:
            cat = str(cats[0])
            path = " > ".join(str(c) for c in cats)
    if not cat and "basic_category" in row.index:
        bc = row.get("basic_category")
        if bc:
            cat = str(bc)
            path = str(bc)
    return cat, path


def _extract_address(row: pd.Series) -> str:
    for col in ("addresses", "address"):
        if col in row.index and row.get(col) is not None:
            val = row[col]
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except Exception:
                    return str(val)
            # numpy array or list
            try:
                val = list(val)
            except Exception:
                pass
            if isinstance(val, list) and val:
                addr = val[0]
                if isinstance(addr, dict):
                    parts = [
                        addr.get("freeform", ""),
                        addr.get("locality", ""),
                        addr.get("region", ""),
                        addr.get("country", ""),
                    ]
                    return ", ".join(p for p in parts if p)
    return ""


def _extract_lonlat(row: pd.Series) -> tuple[float | None, float | None]:
    # Overture GeoParquet: bbox column is a struct {xmin,ymin,xmax,ymax}
    if "bbox" in row.index and row.get("bbox") is not None:
        b = row["bbox"]
        if isinstance(b, dict):
            try:
                lon = (b["xmin"] + b["xmax"]) / 2.0
                lat = (b["ymin"] + b["ymax"]) / 2.0
                return float(lon), float(lat)
            except Exception:
                pass

    if "geometry" in row.index and row.get("geometry") is not None:
        geom = row["geometry"]
        # WKB bytes (Overture GeoParquet)
        if isinstance(geom, (bytes, bytearray)):
            try:
                from shapely import wkb
                g = wkb.loads(bytes(geom))
                return g.x, g.y
            except Exception:
                pass
        if isinstance(geom, str):
            try:
                geom = json.loads(geom)
            except Exception:
                return None, None
        if isinstance(geom, dict) and geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                return float(coords[0]), float(coords[1])
    for lon_col in ("lon", "longitude", "lng"):
        for lat_col in ("lat", "latitude"):
            if lon_col in row.index and lat_col in row.index:
                lon_v = row.get(lon_col)
                lat_v = row.get(lat_col)
                if lon_v is not None and lat_v is not None:
                    try:
                        return float(lon_v), float(lat_v)
                    except Exception:
                        pass
    return None, None


def build_documents(
    input_path: str,
    source: str,
    source_release: str,
    bbox: list[float] | None,
    out_path: str,
) -> int:
    logger.info("Reading %s ...", input_path)
    df = pd.read_parquet(input_path)
    logger.info("Rows: %d, columns: %s", len(df), list(df.columns))

    records: list[dict] = []
    skipped = 0

    for idx, row in df.iterrows():
        lon, lat = _extract_lonlat(row)
        if lon is None or lat is None:
            skipped += 1
            continue

        if bbox:
            xmin, ymin, xmax, ymax = bbox
            if not (xmin <= lon <= xmax and ymin <= lat <= ymax):
                skipped += 1
                continue

        source_fid = str(row.get("id", idx))
        poi_id = f"{source}:{source_fid}"

        name_primary, name_normalized, names_all = _extract_name(row.get("names"))
        if not name_primary:
            skipped += 1
            continue

        category_primary, category_path = _extract_category(row)
        address_text = _extract_address(row)
        quadkey_z12 = lonlat_to_quadkey(lon, lat, 12)

        record: dict = {
            "poi_id": poi_id,
            "source": source,
            "source_release": source_release,
            "source_feature_id": source_fid,
            "lon": lon,
            "lat": lat,
            "quadkey_z12": quadkey_z12,
            "name_primary": name_primary,
            "name_normalized": name_normalized,
            "names_all": names_all,
            "category_primary": category_primary,
            "category_path": category_path,
            "address_text": address_text,
        }
        record["exact_tokens"] = build_exact_tokens(record)
        record["category_tokens"] = build_category_tokens(record)
        record["morph_tokens"] = build_morph_tokens(record)
        record["name_bigram_tokens"] = build_name_bigram_tokens(record)
        record["name_trigram_tokens"] = build_name_trigram_tokens(record)

        display = {
            "name": name_primary,
            "category": category_primary,
            "address": address_text,
        }
        record["display_json"] = json.dumps(display, ensure_ascii=False)
        records.append(record)

    logger.info("Built %d records (skipped %d)", len(records), skipped)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    out_df = pd.DataFrame(records)
    out_df.to_parquet(out_path, index=False)
    logger.info("Written to %s", out_path)
    return len(records)


def main():
    parser = argparse.ArgumentParser(description="Build poi-documents.parquet")
    parser.add_argument("--input", required=True)
    parser.add_argument("--source", default="overture-places")
    parser.add_argument("--source-release", default="2026-04-15.0")
    parser.add_argument("--bbox", default=None, help="xmin,ymin,xmax,ymax")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    bbox = None
    if args.bbox:
        bbox = [float(v) for v in args.bbox.split(",")]

    count = build_documents(
        input_path=args.input,
        source=args.source,
        source_release=args.source_release,
        bbox=bbox,
        out_path=args.out,
    )
    logger.info("Done: %d documents", count)


if __name__ == "__main__":
    main()
