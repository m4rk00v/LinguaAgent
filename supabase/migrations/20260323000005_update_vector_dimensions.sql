-- 005_update_vector_dimensions.sql
-- Change vector dimensions from 1536 (OpenAI) to 768 (Ollama nomic-embed-text)

-- 1. Drop existing index
DROP INDEX IF EXISTS documents_embedding_idx;

-- 2. Change column dimension
ALTER TABLE documents
  ALTER COLUMN embedding TYPE VECTOR(768);

-- 3. Recreate index
CREATE INDEX ON documents
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- 4. Recreate search function with new dimension
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding VECTOR(768),
  match_count INT DEFAULT 5,
  filter_source TEXT DEFAULT NULL,
  filter_level TEXT DEFAULT NULL
)
RETURNS TABLE (
  id INT,
  content TEXT,
  metadata JSONB,
  source_type TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.content,
    d.metadata,
    d.source_type,
    1 - (d.embedding <=> query_embedding) AS similarity
  FROM documents d
  WHERE
    (filter_source IS NULL OR d.source_type = filter_source)
    AND (filter_level IS NULL OR d.metadata->>'level' = filter_level)
  ORDER BY d.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
