"""CESG POI search asset manifest generation."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Any


def generate_manifest(
    source: str,
    source_release: str,
    bbox: list[float],
    count: int,
    assets: dict[str, str],
) -> dict[str, Any]:
    return {
        "profile": "cesg-poi-search/0.1",
        "runtime": "duckdb+fts",
        "source": source,
        "source_release": source_release,
        "bbox": bbox,
        "count": count,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tokenization": {
            "normalization": ["unicode_nfkc", "lowercase"],
            "morph": "lindera",
            "ngrams": [2, 3],
            "unigram": False,
        },
        "assets": assets,
    }


def write_manifest(manifest: dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
