CREATE TABLE IF NOT EXISTS poi_documents (
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
