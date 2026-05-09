-- Example weighted BM25 search across FTS fields
-- Replace $eq, $cq, $bq, $tq, $mq, $xmin/$xmax/$ymin/$ymax, $limit at runtime
SELECT
    poi_id,
    name_primary,
    category_primary,
    lon,
    lat,
    (
        COALESCE(fts_main_poi_documents.match_bm25(poi_id, $eq, fields := 'exact_tokens'), 0) * 6.0
        + COALESCE(fts_main_poi_documents.match_bm25(poi_id, $cq, fields := 'category_tokens'), 0) * 3.0
        + COALESCE(fts_main_poi_documents.match_bm25(poi_id, $bq, fields := 'name_bigram_tokens'), 0) * 2.0
        + COALESCE(fts_main_poi_documents.match_bm25(poi_id, $tq, fields := 'name_trigram_tokens'), 0) * 2.5
        + COALESCE(fts_main_poi_documents.match_bm25(poi_id, $mq, fields := 'morph_tokens'), 0) * 1.5
    ) AS score
FROM poi_documents
WHERE
    lon BETWEEN $xmin AND $xmax
    AND lat BETWEEN $ymin AND $ymax
    AND score > 0
ORDER BY score DESC
LIMIT $limit;
