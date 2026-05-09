INSTALL fts;
LOAD fts;

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
    ignore = '[\s]+',
    strip_accents = 1,
    lower = 1,
    overwrite = 1
);
