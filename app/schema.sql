CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY,
    filename        TEXT NOT NULL,
    title           TEXT,
    file_type       TEXT NOT NULL,
    stored_name     TEXT NOT NULL,
    sha256          TEXT NOT NULL UNIQUE,
    size_bytes      BIGINT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    error           TEXT,
    num_pages       INT,
    num_chunks      INT NOT NULL DEFAULT 0,
    content         TEXT,
    embedding_model TEXT,
    processing_ms   INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INT NOT NULL,
    page         INT,
    heading      TEXT,
    content      TEXT NOT NULL,
    start_char   INT NOT NULL,
    end_char     INT NOT NULL,
    embedding    vector({dim}) NOT NULL,
    -- Section headings get a higher weight than body text in keyword ranking.
    tsv          tsvector GENERATED ALWAYS AS (
                     setweight(to_tsvector('english', coalesce(heading, '')), 'A') ||
                     setweight(to_tsvector('english', content), 'B')
                 ) STORED
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_document_idx ON chunks (document_id);
