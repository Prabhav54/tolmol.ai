-- Ensure the pgvector extension is activated
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop table if you need a clean reset during development
-- DROP TABLE IF EXISTS product_reviews;

-- Core Schema for Hybrid RAG Operations
CREATE TABLE IF NOT EXISTS product_reviews (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384) -- Matches all-MiniLM-L6-v2 dimensions
);

-- Indexing for speed optimization on large datasets (Optional but recommended)
CREATE INDEX IF NOT EXISTS hf_vector_cosine_idx ON product_reviews 
USING hnsw (embedding vector_cosine_ops);