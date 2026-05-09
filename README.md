# poc-cesg-poi-search

poc-cesg-poi-search is a proof-of-concept for a portable POI search asset: a STAC-described, DuckDB-backed, pre-indexed POI search data product that can run on Knative/FaaS in the cloud or on edge nodes without a dedicated search server.

## Purpose

This PoC demonstrates that a full-text geospatial POI search index can be:

- Built offline from Overture Places Parquet data using standard Python tooling
- Packaged as a single portable DuckDB file with a pre-built FTS index
- Described with a STAC item and a CESG manifest for discovery and interoperability
- Served via a minimal FastAPI process (no Elasticsearch, no Solr, no external search server)
- Deployed to Knative or any container platform with cold-start download from static hosting

## CESG POI Search Asset

The CESG (Cloud-Edge Symmetric Geospatial) POI search asset is a self-contained data product consisting of:

- `poi-documents.parquet`: canonical POI records with pre-computed token columns
- `poi-search.duckdb`: DuckDB database with FTS index over the token columns
- `poi-search-manifest.json`: CESG manifest describing the asset profile, source, bbox, and tokenization
- `stac-item.json` (optional): STAC Feature item linking all assets with spatial metadata

### Tokenization strategy

The asset uses multi-field BM25 search with the following token types (no unigrams):

| Column | Content | Weight |
|---|---|---|
| `exact_tokens` | NFKC-normalized names | 6.0 |
| `category_tokens` | category path segments | 3.0 |
| `name_trigram_tokens` | character tri-grams | 2.5 |
| `name_bigram_tokens` | character bi-grams | 2.0 |
| `morph_tokens` | Lindera morphological tokens | 1.5 |

## Architecture

```
Overture Places (Parquet)
        |
        v
build_poi_documents.py   (tokenize, bi/tri-gram, normalize)
        |
        v
poi-documents.parquet    (canonical document store)
        |
        v
build_duckdb_asset.py    (DuckDB FTS index, quadkey sort)
        |
        v
poi-search.duckdb  +  poi-search-manifest.json  +  stac-item.json
        |
        v
Static hosting (z.yuiseki.net/static/cesg/<area>/)
        |
        v
FastAPI server (app.py)        <-- downloads on cold start
   /search  (bbox)
   /nearby  (radius)
   /metadata
   /healthz
        |
        v
Knative Service  /  Docker  /  uvicorn local
        |
        v
docs/index.html (MapLibre GL JS frontend)
```

## Build steps

### 1. Install dependencies

```bash
pip install -e .
# Optional: Lindera morphological tokenizer
pip install -e ".[lindera]"
```

### 2. Build POI documents from Overture Places Parquet

```bash
python scripts/build_poi_documents.py \
  --input /path/to/overture-places.parquet \
  --source overture-places \
  --source-release 2026-04-15.0 \
  --bbox 139.55,35.50,139.95,35.85 \
  --out data/tokyo/poi-documents.parquet
```

### 3. Build the DuckDB asset and manifest

```bash
python scripts/build_duckdb_asset.py \
  --documents data/tokyo/poi-documents.parquet \
  --out data/tokyo/poi-search.duckdb \
  --manifest data/tokyo/poi-search-manifest.json
```

### 4. (Optional) Export STAC item

```bash
python scripts/export_stac_item.py \
  --manifest data/tokyo/poi-search-manifest.json \
  --base-url https://z.yuiseki.net/static/cesg/tokyo \
  --out data/tokyo/stac-item.json
```

## Local API startup

```bash
# Point at a local DuckDB file
POI_SEARCH_DB=data/tokyo/poi-search.duckdb uvicorn poc_cesg_poi_search.app:app --port 8080

# Or let the server download on first start
POI_SEARCH_ASSET_URL=https://z.yuiseki.net/static/cesg/tokyo/poi-search.duckdb \
  uvicorn poc_cesg_poi_search.app:app --port 8080
```

### Example queries

```bash
# BBox search
curl "http://localhost:8080/search?q=カフェ&bbox=139.55,35.50,139.95,35.85"

# Nearby search
curl "http://localhost:8080/nearby?q=コンビニ&lat=35.681&lon=139.767&radius_m=500"

# Health check
curl http://localhost:8080/healthz
```

## Docker build and run

```bash
docker build -f docker/Dockerfile -t poc-cesg-poi-search .

docker run -p 8080:8080 \
  -e POI_SEARCH_ASSET_URL=https://z.yuiseki.net/static/cesg/tokyo/poi-search.duckdb \
  poc-cesg-poi-search
```

## Knative deploy

```bash
kubectl apply -f k8s/ksvc.yaml

# Check status
kubectl get ksvc poc-cesg-poi-search
```

The Knative service will download the DuckDB asset from `POI_SEARCH_ASSET_URL` on cold start and cache it at `POI_SEARCH_LOCAL_CACHE`.

## GitHub Pages frontend

The `docs/index.html` file is a self-contained MapLibre GL JS UI that connects to any running API instance.

To enable GitHub Pages: go to repository Settings, then Pages, and set the source to the `docs/` folder on the `main` branch.

Set the API base URL in the input field to point at your deployed instance.

## Static asset deploy

```bash
bash scripts/deploy_static_assets.sh data/tokyo tokyo
# Copies .parquet, .duckdb, .json to /data/www/html/static/cesg/tokyo/
```

## Running tests

```bash
pip install -e .
python -m pytest tests/ -v
```

## Known limitations

- The DuckDB FTS extension does not support incremental index updates. Rebuilding the index requires recreating the full DuckDB file.
- Cold-start download time depends on the DuckDB file size (typically 50-500 MB for a city-scale dataset). Use `POI_SEARCH_DB` to point at a pre-mounted volume for production use.
- DuckDB FTS `match_bm25` requires the FTS index to exist in the connected database. The index is created at build time and is embedded in the `.duckdb` file.
- Lindera morphological tokenizer is optional. Without it, the fallback tokenizer splits on whitespace and punctuation, which reduces recall for Japanese queries.
- The `/nearby` endpoint uses a rectangular bbox prefilter followed by Haversine distance filtering in Python, not a native spatial index. For very large datasets, query latency may increase.
- No authentication or rate limiting is implemented. This is a proof-of-concept only.
