"""FTS search logic for CESG POI search."""
from __future__ import annotations
import math
import logging
from typing import Any
import duckdb

from .tokenizer import expand_query

logger = logging.getLogger(__name__)

# Field weights
WEIGHT_EXACT = 6.0
WEIGHT_CATEGORY = 3.0
WEIGHT_TRIGRAM = 2.5
WEIGHT_BIGRAM = 2.0
WEIGHT_MORPH = 1.5


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def search_bbox(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    limit: int = 20,
) -> list[dict[str, Any]]:
    expanded = expand_query(query)
    eq = expanded["exact_query"]
    cq = expanded["category_query"]
    bq = expanded["bigram_query"]
    tq = expanded["trigram_query"]
    mq = expanded["morph_query"]

    sql = """
    SELECT
        poi_id,
        name_primary,
        category_primary,
        lon,
        lat,
        source,
        source_feature_id,
        display_json,
        (
            COALESCE(fts_main_poi_documents.match_bm25(poi_id, $eq, fields := 'exact_tokens'), 0) * $w_exact
            + COALESCE(fts_main_poi_documents.match_bm25(poi_id, $cq, fields := 'category_tokens'), 0) * $w_cat
            + COALESCE(fts_main_poi_documents.match_bm25(poi_id, $bq, fields := 'name_bigram_tokens'), 0) * $w_bigram
            + COALESCE(fts_main_poi_documents.match_bm25(poi_id, $tq, fields := 'name_trigram_tokens'), 0) * $w_trigram
            + COALESCE(fts_main_poi_documents.match_bm25(poi_id, $mq, fields := 'morph_tokens'), 0) * $w_morph
        ) AS score
    FROM poi_documents
    WHERE
        lon BETWEEN $xmin AND $xmax
        AND lat BETWEEN $ymin AND $ymax
        AND score > 0
    ORDER BY score DESC
    LIMIT $limit
    """
    params = {
        "eq": eq, "cq": cq, "bq": bq, "tq": tq, "mq": mq,
        "w_exact": WEIGHT_EXACT, "w_cat": WEIGHT_CATEGORY,
        "w_bigram": WEIGHT_BIGRAM, "w_trigram": WEIGHT_TRIGRAM,
        "w_morph": WEIGHT_MORPH,
        "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
        "limit": limit,
    }
    rows = conn.execute(sql, params).fetchall()
    cols = ["poi_id", "name", "category", "lon", "lat", "source",
            "source_feature_id", "display_json", "score"]
    return [dict(zip(cols, row)) for row in rows]


def search_nearby(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    lat: float,
    lon: float,
    radius_m: float = 1000.0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    # Approximate degree offsets for bbox prefilter
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * math.cos(math.radians(lat)))
    xmin, xmax = lon - dlon, lon + dlon
    ymin, ymax = lat - dlat, lat + dlat

    candidates = search_bbox(conn, query, xmin, ymin, xmax, ymax, limit=limit * 5)
    results = []
    for row in candidates:
        dist = _haversine_m(lat, lon, row["lat"], row["lon"])
        if dist <= radius_m:
            row["distance_m"] = round(dist, 1)
            results.append(row)
    results.sort(key=lambda r: (-r["score"], r["distance_m"]))
    return results[:limit]
