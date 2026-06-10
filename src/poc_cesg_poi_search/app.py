"""FastAPI application for CESG POI search."""
from __future__ import annotations
import json
import logging
import threading
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
_db_init_status = "starting"
_db_init_error: str | None = None
_init_thread: threading.Thread | None = None


class ORJSONResponse(JSONResponse):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _start_background_initialization()

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


def _health_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "status": "ok",
        "service": "poc-cesg-poi-search",
    }


def _db_ready() -> bool:
    try:
        get_connection()
    except RuntimeError:
        return False
    return True


def _healthz_payload() -> tuple[dict[str, Any], int]:
    db_ready = _db_ready()
    if db_ready:
        return (
            {
                **_health_payload(),
                "db_ready": True,
                "db_init_status": _db_init_status,
                "manifest_loaded": bool(_manifest_cache),
            },
            200,
        )
    return (
        {
            "ok": False,
            "status": "ng",
            "service": "poc-cesg-poi-search",
            "db_ready": False,
            "db_init_status": _db_init_status,
            "db_init_error": _db_init_error,
            "manifest_loaded": bool(_manifest_cache),
        },
        503,
    )


def _load_manifest() -> None:
    global _manifest_cache
    try:
        import httpx
        r = httpx.get(settings.poi_search_manifest_url, timeout=10)
        if r.status_code == 200:
            _manifest_cache = r.json()
    except Exception as e:
        logger.warning("Could not load manifest: %s", e)


def _initialize_assets() -> None:
    global _db_init_status, _db_init_error
    _db_init_status = "initializing"
    _db_init_error = None
    try:
        init_db(
            db_path=settings.poi_search_db,
            asset_url=settings.poi_search_asset_url,
            local_cache=settings.poi_search_local_cache,
        )
        _db_init_status = "ready"
    except Exception as e:
        _db_init_status = "error"
        _db_init_error = str(e)
        logger.warning("DuckDB not available at startup: %s — /search and /nearby will return 503", e)
    finally:
        _load_manifest()


def _start_background_initialization() -> None:
    global _init_thread
    if _init_thread is not None and _init_thread.is_alive():
        return
    _init_thread = threading.Thread(
        target=_initialize_assets,
        name="poi-search-init",
        daemon=True,
    )
    _init_thread.start()


@app.get("/")
def root():
    return {
        **_health_payload(),
        "manifest_loaded": bool(_manifest_cache),
        "endpoints": {
            "health": "/health",
            "healthz": "/healthz",
            "metadata": "/metadata",
            "search": "/search",
            "nearby": "/nearby",
        },
    }


@app.get("/health")
def health():
    return _health_payload()


@app.get("/healthz")
def healthz():
    payload, status_code = _healthz_payload()
    return ORJSONResponse(payload, status_code=status_code)


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

    try:
        conn = get_connection()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Search index not available")
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

    try:
        conn = get_connection()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Search index not available")
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
