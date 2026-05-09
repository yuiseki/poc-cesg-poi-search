#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${1:?Usage: $0 <data-dir> <area-name>}"
AREA="${2:?Usage: $0 <data-dir> <area-name>}"
DEST="/data/www/html/static/cesg/${AREA}"

echo "Deploying ${DATA_DIR} -> ${DEST}"
mkdir -p "${DEST}"
cp -v "${DATA_DIR}/"*.parquet "${DEST}/" 2>/dev/null || true
cp -v "${DATA_DIR}/"*.duckdb  "${DEST}/" 2>/dev/null || true
cp -v "${DATA_DIR}/"*.json    "${DEST}/" 2>/dev/null || true
echo "Done. Assets available at https://z.yuiseki.net/static/cesg/${AREA}/"
