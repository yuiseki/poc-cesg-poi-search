"""Tests for FastAPI endpoints using a minimal fixture DuckDB."""
from __future__ import annotations
import json
import os
import tempfile
from unittest.mock import patch

import pytest
import duckdb
from fastapi.testclient import TestClient


def _make_fixture_db(path: str) -> None:
    """Create a minimal DuckDB with FTS for testing."""
    conn = duckdb.connect(path)
    conn.execute("""
        CREATE TABLE poi_documents (
            poi_id VARCHAR PRIMARY KEY,
            source VARCHAR NOT NULL,
            source_release VARCHAR NOT NULL,
            source_feature_id VARCHAR NOT NULL,
            lon DOUBLE NOT NULL,
            lat DOUBLE NOT NULL,
            quadkey_z12 VARCHAR NOT NULL,
            name_primary VARCHAR,
            name_normalized VARCHAR,
            names_all VARCHAR,
            category_primary VARCHAR,
            category_path VARCHAR,
            address_text VARCHAR,
            exact_tokens VARCHAR,
            category_tokens VARCHAR,
            morph_tokens VARCHAR,
            name_bigram_tokens VARCHAR,
            name_trigram_tokens VARCHAR,
            display_json JSON
        )
    """)
    rows = [
        ("test:001", "test", "0.0.1", "001", 139.767, 35.681, "133313112300",
         "テストカフェ", "テストカフェ", "テストカフェ", "cafe", "food > cafe",
         "東京都千代田区", "テストカフェ", "cafe food",
         "テストカフェ", "テスト テストカ スとカ とカフ カフェ", "テストカフ ストカフェ",
         json.dumps({"name": "テストカフェ", "category": "cafe"}, ensure_ascii=False)),
    ]
    conn.executemany("""
        INSERT INTO poi_documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.execute("INSTALL fts")
    conn.execute("LOAD fts")
    conn.execute("""
        PRAGMA create_fts_index(
            'poi_documents', 'poi_id',
            'exact_tokens', 'category_tokens', 'morph_tokens',
            'name_bigram_tokens', 'name_trigram_tokens',
            stemmer='none', stopwords='none', ignore='[\\s]+',
            strip_accents=1, lower=1, overwrite=1
        )
    """)
    conn.close()


@pytest.fixture
def client():
    import poc_cesg_poi_search.db as db_module

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.duckdb")
        _make_fixture_db(db_path)

        conn = duckdb.connect(db_path, read_only=True)
        conn.execute("LOAD fts")
        original = db_module._conn
        db_module._conn = conn

        import poc_cesg_poi_search.app as app_module
        from poc_cesg_poi_search.app import app

        original_manifest = app_module._manifest_cache
        original_status = app_module._db_init_status
        original_error = app_module._db_init_error
        app_module._manifest_cache = {"asset": "ready"}
        app_module._db_init_status = "ready"
        app_module._db_init_error = None

        # Patch background init to a no-op so the lifespan does not overwrite _conn
        with patch("poc_cesg_poi_search.app._start_background_initialization", return_value=None), \
             patch("poc_cesg_poi_search.app.close_db", return_value=None), \
             TestClient(app, raise_server_exceptions=False) as c:
            yield c

        conn.close()
        db_module._conn = original
        app_module._manifest_cache = original_manifest
        app_module._db_init_status = original_status
        app_module._db_init_error = original_error


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "poc-cesg-poi-search"
    assert r.json()["db_ready"] is True
    assert r.json()["db_init_status"] == "ready"


def test_health_alias(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "poc-cesg-poi-search"


def test_root_returns_service_info(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "poc-cesg-poi-search"
    assert "endpoints" in data
    assert data["endpoints"]["health"] == "/health"
    assert data["endpoints"]["healthz"] == "/healthz"


def test_healthz_returns_ng_when_db_unavailable():
    import poc_cesg_poi_search.db as db_module
    import poc_cesg_poi_search.app as app_module
    from poc_cesg_poi_search.app import app

    original_conn = db_module._conn
    original_manifest = app_module._manifest_cache
    original_status = app_module._db_init_status
    original_error = app_module._db_init_error
    db_module._conn = None
    app_module._manifest_cache = {}
    app_module._db_init_status = "error"
    app_module._db_init_error = "boom"
    try:
        with patch("poc_cesg_poi_search.app._start_background_initialization", return_value=None), \
             patch("poc_cesg_poi_search.app.close_db", return_value=None), \
             TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/healthz")
        assert r.status_code == 503
        data = r.json()
        assert data["ok"] is False
        assert data["status"] == "ng"
        assert data["service"] == "poc-cesg-poi-search"
        assert data["db_ready"] is False
        assert data["db_init_status"] == "error"
        assert data["db_init_error"] == "boom"
    finally:
        db_module._conn = original_conn
        app_module._manifest_cache = original_manifest
        app_module._db_init_status = original_status
        app_module._db_init_error = original_error


def test_healthz_returns_ng_while_initializing():
    import poc_cesg_poi_search.db as db_module
    import poc_cesg_poi_search.app as app_module
    from poc_cesg_poi_search.app import app

    original_conn = db_module._conn
    original_manifest = app_module._manifest_cache
    original_status = app_module._db_init_status
    original_error = app_module._db_init_error
    db_module._conn = None
    app_module._manifest_cache = {}
    app_module._db_init_status = "initializing"
    app_module._db_init_error = None
    try:
        with patch("poc_cesg_poi_search.app._start_background_initialization", return_value=None), \
             patch("poc_cesg_poi_search.app.close_db", return_value=None), \
             TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/healthz")
        assert r.status_code == 503
        data = r.json()
        assert data["ok"] is False
        assert data["status"] == "ng"
        assert data["db_ready"] is False
        assert data["db_init_status"] == "initializing"
        assert data["db_init_error"] is None
    finally:
        db_module._conn = original_conn
        app_module._manifest_cache = original_manifest
        app_module._db_init_status = original_status
        app_module._db_init_error = original_error


def test_search_returns_json(client):
    r = client.get("/search", params={"q": "カフェ", "bbox": "139.55,35.50,139.95,35.85"})
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "count" in data


def test_search_missing_bbox(client):
    r = client.get("/search", params={"q": "カフェ"})
    assert r.status_code == 422


def test_search_invalid_bbox(client):
    r = client.get("/search", params={"q": "カフェ", "bbox": "bad,bbox"})
    assert r.status_code == 400


def test_nearby_returns_json(client):
    r = client.get("/nearby", params={
        "q": "カフェ", "lat": 35.681, "lon": 139.767, "radius_m": 2000
    })
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
