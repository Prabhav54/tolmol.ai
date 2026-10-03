-- tolmol.ai catalog schema.
-- The API creates these objects automatically on startup (db/session.py::init_db).
-- This file is for running manually in the Supabase SQL editor if you prefer.
-- vector(768) must match EMBEDDING_DIM (768 = gemini-embedding-001 with reduced output size).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS products (
    id            SERIAL PRIMARY KEY,
    url_hash      CHAR(64)      NOT NULL UNIQUE,   -- SHA-256 of the normalized product URL
    url           TEXT          NOT NULL,
    platform      VARCHAR(50)   NOT NULL,
    title         TEXT          NOT NULL,
    brand         TEXT,
    category      TEXT,
    description   TEXT,
    price         NUMERIC(12, 2),
    currency      VARCHAR(8)    NOT NULL DEFAULT 'INR',
    rating        NUMERIC(3, 2),
    rating_count  INTEGER,
    image_url     TEXT,
    in_stock      BOOLEAN,
    content_hash  CHAR(64),                        -- SHA-256 of the embedded text
    embedding     vector(768),
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_products_embedding_hnsw ON products
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS ix_products_price    ON products (price);
CREATE INDEX IF NOT EXISTS ix_products_rating   ON products (rating);
CREATE INDEX IF NOT EXISTS ix_products_platform ON products (platform);
CREATE INDEX IF NOT EXISTS ix_products_category ON products (category);

CREATE TABLE IF NOT EXISTS price_history (
    id           SERIAL PRIMARY KEY,
    product_id   INTEGER        NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    price        NUMERIC(12, 2) NOT NULL,
    recorded_at  TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_price_history_product ON price_history (product_id, recorded_at);
