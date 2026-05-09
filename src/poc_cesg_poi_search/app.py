"""FastAPI application for CESG POI search."""
from __future__ import annotations
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

import orjson
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db import init_db, get_connection, close_db
from .search import search_bbox, search_nearby

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_manifest_cache: dict[str, Any] = {}


class ORJSONResponse(JSONResponse):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(
        db_path=settings.poi_search_db,
        asset_url=settings.poi_search_asset_url,
        local_cache=settings.poi_search_local_cache,
    )
    # Load manifest if accessible
    global _manifest_cache
    try:
        import httpx
        r = httpx.get(settings.poi_search_manifest_url, timeout=10)
        if r.status_code == 200:
            _manifest_cache = r.json()
    except Exception as e:
        logger.warning("Could not load manifest: %s", e)

    yield
    close_db()


app = FastAPI(
    title="poc-cesg-poi-search",
    description="CESG portable POI search asset served via FastAPI",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/metadata")
def metadata():
    return _manifest_cache or {"status": "manifest not loaded"}


@app.get("/search")
def search(
    q: str = Query(..., description="Search query"),
    bbox: str = Query(..., description="xmin,ymin,xmax,ymax in WGS84"),
    limit: int = Query(20, ge=1, le=100),
):
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox must be xmin,ymin,xmax,ymax")
    try:
        xmin, ymin, xmax, ymax = (float(p) for p in parts)
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox values must be numeric")
    if xmin >= xmax or ymin >= ymax:
        raise HTTPException(status_code=400, detail="invalid bbox: min must be less than max")

    conn = get_connection()
    results = search_bbox(conn, q, xmin, ymin, xmax, ymax, limit=limit)
    _serialize_display(results)
    return {"query": q, "count": len(results), "results": results}


@app.get("/nearby")
def nearby(
    q: str = Query(..., description="Search query"),
    lat: float = Query(..., description="Center latitude"),
    lon: float = Query(..., description="Center longitude"),
    radius_m: float = Query(1000.0, ge=1, le=50_000, description="Radius in meters"),
    limit: int = Query(20, ge=1, le=100),
):
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=400, detail="lat must be between -90 and 90")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="lon must be between -180 and 180")

    conn = get_connection()
    results = search_nearby(conn, q, lat, lon, radius_m=radius_m, limit=limit)
    _serialize_display(results)
    return {"query": q, "count": len(results), "results": results}


def _serialize_display(results: list[dict]) -> None:
    for r in results:
        dj = r.get("display_json")
        if isinstance(dj, str):
            try:
                r["display"] = json.loads(dj)
            except Exception:
                r["display"] = {}
        elif dj is None:
            r["display"] = {}
        else:
            r["display"] = dj
        r.pop("display_json", None)
