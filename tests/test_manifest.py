"""Tests for manifest generation."""
import json
import os
import tempfile
from poc_cesg_poi_search.manifest import generate_manifest, write_manifest
from poc_cesg_poi_search.stac import manifest_to_stac_item


def test_generate_manifest_structure():
    m = generate_manifest(
        source="overture-places",
        source_release="2026-04-15.0",
        bbox=[139.55, 35.50, 139.95, 35.85],
        count=123,
        assets={"documents": "poi-documents.parquet", "duckdb": "poi-search.duckdb"},
    )
    assert m["profile"] == "cesg-poi-search/0.1"
    assert m["runtime"] == "duckdb+fts"
    assert m["count"] == 123
    assert m["tokenization"]["unigram"] is False
    assert 2 in m["tokenization"]["ngrams"]
    assert 3 in m["tokenization"]["ngrams"]


def test_write_manifest_roundtrip():
    m = generate_manifest(
        source="test",
        source_release="0.0.1",
        bbox=[0, 0, 1, 1],
        count=0,
        assets={},
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "manifest.json")
        write_manifest(m, path)
        with open(path) as f:
            loaded = json.load(f)
    assert loaded["source"] == "test"


def test_stac_item_structure():
    m = generate_manifest(
        source="overture-places",
        source_release="2026-04-15.0",
        bbox=[139.55, 35.50, 139.95, 35.85],
        count=100,
        assets={"documents": "poi-documents.parquet", "duckdb": "poi-search.duckdb"},
    )
    item = manifest_to_stac_item(m, base_url="https://example.com/cesg/tokyo/")
    assert item["type"] == "Feature"
    assert item["stac_version"] == "1.0.0"
    assert "poi_documents" in item["assets"]
    assert "poi_search_duckdb" in item["assets"]
    assert "manifest" in item["assets"]
    assert item["bbox"] == [139.55, 35.50, 139.95, 35.85]
