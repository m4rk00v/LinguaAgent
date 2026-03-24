-- 002_enable_pgvector.sql
-- Vector store for RAG pipeline

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  content TEXT NOT NULL,
  embedding VECTOR(768),
  metadata JSONB DEFAULT '{}',
  source_type TEXT CHECK (source_type IN ('course', 'profile', 'policy')),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON documents
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
