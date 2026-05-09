"""DuckDB connection lifecycle for CESG POI search."""
from __future__ import annotations
import logging
import os
import httpx
import duckdb

logger = logging.getLogger(__name__)
_conn: duckdb.DuckDBPyConnection | None = None


def _download_db(url: str, dest: str) -> None:
    logger.info("Downloading DuckDB asset from %s ...", url)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=1 << 20):
                f.write(chunk)
    logger.info("Downloaded %s bytes to %s", os.path.getsize(dest), dest)


def get_connection() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        raise RuntimeError("DuckDB connection not initialized. Call init_db() first.")
    return _conn


def init_db(
    db_path: str,
    asset_url: str,
    local_cache: str,
) -> None:
    global _conn
    path = db_path
    if path and os.path.exists(path):
        logger.info("Using local DuckDB at %s", path)
    else:
        if os.path.exists(local_cache):
            logger.info("Using cached DuckDB at %s", local_cache)
            path = local_cache
        else:
            _download_db(asset_url, local_cache)
            path = local_cache

    _conn = duckdb.connect(path, read_only=True)
    _conn.execute("INSTALL fts")
    _conn.execute("LOAD fts")
    logger.info("DuckDB ready: %s", path)


def close_db() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
