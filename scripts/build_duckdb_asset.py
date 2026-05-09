#!/usr/bin/env python3
"""Build poi-search.duckdb from poi-documents.parquet with DuckDB FTS index."""
from __future__ import annotations
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import duckdb

from poc_cesg_poi_search.manifest import generate_manifest, write_manifest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
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
);
"""


def build_duckdb(documents_path: str, out_path: str, manifest_path: str | None) -> None:
    if os.path.exists(out_path):
        logger.info("Removing existing %s", out_path)
        os.remove(out_path)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    logger.info("Creating DuckDB at %s ...", out_path)
    conn = duckdb.connect(out_path)

    conn.execute(CREATE_TABLE_SQL)

    logger.info("Importing from %s ...", documents_path)
    conn.execute(
        f"INSERT INTO poi_documents SELECT * FROM read_parquet('{documents_path}')"
    )

    count = conn.execute("SELECT COUNT(*) FROM poi_documents").fetchone()[0]
    logger.info("Imported %d rows", count)

    # Reorder for spatial locality
    logger.info("Reordering by quadkey_z12 ...")
    conn.execute("""
        CREATE TABLE poi_documents_sorted AS
        SELECT * FROM poi_documents
        ORDER BY quadkey_z12, category_primary, name_normalized;
    """)
    conn.execute("DROP TABLE poi_documents;")
    conn.execute("ALTER TABLE poi_documents_sorted RENAME TO poi_documents;")

    logger.info("Building FTS index ...")
    conn.execute("INSTALL fts")
    conn.execute("LOAD fts")
    conn.execute("""
        PRAGMA create_fts_index(
            'poi_documents',
            'poi_id',
            'exact_tokens',
            'category_tokens',
            'morph_tokens',
            'name_bigram_tokens',
            'name_trigram_tokens',
            stemmer = 'none',
            stopwords = 'none',
            ignore = '[\\s]+',
            strip_accents = 1,
            lower = 1,
            overwrite = 1
        );
    """)
    logger.info("FTS index created")

    if manifest_path:
        row = conn.execute(
            "SELECT source, source_release, MIN(lon), MIN(lat), MAX(lon), MAX(lat) FROM poi_documents"
        ).fetchone()
        source, source_release, xmin, ymin, xmax, ymax = row
        manifest = generate_manifest(
            source=source,
            source_release=source_release,
            bbox=[xmin, ymin, xmax, ymax],
            count=count,
            assets={
                "documents": os.path.basename(documents_path),
                "duckdb": os.path.basename(out_path),
            },
        )
        write_manifest(manifest, manifest_path)
        logger.info("Manifest written to %s", manifest_path)

    conn.close()
    logger.info("Done: %s", out_path)


def main():
    parser = argparse.ArgumentParser(description="Build poi-search.duckdb from poi-documents.parquet")
    parser.add_argument("--documents", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args()

    build_duckdb(
        documents_path=args.documents,
        out_path=args.out,
        manifest_path=args.manifest,
    )


if __name__ == "__main__":
    main()
