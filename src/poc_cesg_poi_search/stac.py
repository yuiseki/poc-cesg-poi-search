"""STAC item generation for CESG POI search asset."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any


def manifest_to_stac_item(
    manifest: dict[str, Any],
    base_url: str,
    item_id: str | None = None,
) -> dict[str, Any]:
    bbox = manifest["bbox"]
    xmin, ymin, xmax, ymax = bbox
    now = datetime.now(timezone.utc).isoformat()
    _id = item_id or f"cesg-poi-search-{manifest['source']}-{manifest['source_release']}"

    base_url = base_url.rstrip("/")
    assets_manifest = manifest.get("assets", {})

    return {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": _id,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [xmin, ymin], [xmax, ymin],
                [xmax, ymax], [xmin, ymax],
                [xmin, ymin],
            ]],
        },
        "bbox": bbox,
        "properties": {
            "datetime": now,
            "profile": manifest.get("profile"),
            "source": manifest.get("source"),
            "source_release": manifest.get("source_release"),
            "count": manifest.get("count"),
            "runtime": manifest.get("runtime"),
            "tokenization": manifest.get("tokenization"),
        },
        "assets": {
            "poi_documents": {
                "href": f"{base_url}/{assets_manifest.get('documents', 'poi-documents.parquet')}",
                "type": "application/parquet",
                "roles": ["search", "poi", "runtime-index"],
                "title": "POI documents (canonical Parquet)",
            },
            "poi_search_duckdb": {
                "href": f"{base_url}/{assets_manifest.get('duckdb', 'poi-search.duckdb')}",
                "type": "application/x-duckdb",
                "roles": ["search", "poi", "runtime-index"],
                "title": "POI search index (DuckDB FTS runtime asset)",
            },
            "manifest": {
                "href": f"{base_url}/poi-search-manifest.json",
                "type": "application/json",
                "roles": ["metadata"],
                "title": "CESG POI search manifest",
            },
        },
        "links": [],
    }
