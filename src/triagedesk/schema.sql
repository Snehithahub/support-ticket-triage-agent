-- TriageDesk schema. Idempotent; applied on API startup and by the ingest CLI.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS kb_articles (
    id            text PRIMARY KEY,
    title         text NOT NULL,
    category      text NOT NULL,
    url           text NOT NULL,
    body          text NOT NULL,
    content_hash  text NOT NULL,
    updated       text,
    ingested_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id           bigserial PRIMARY KEY,
    article_id   text NOT NULL REFERENCES kb_articles(id) ON DELETE CASCADE,
    chunk_index  int NOT NULL,
    category     text NOT NULL,
    heading      text NOT NULL,
    content      text NOT NULL,
    tsv          tsvector GENERATED ALWAYS AS (
                     setweight(to_tsvector('english', heading), 'A') ||
                     setweight(to_tsvector('english', content), 'B')) STORED,
    embedding    vector({dim}) NOT NULL,
    UNIQUE (article_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS kb_chunks_tsv_idx ON kb_chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx ON kb_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS kb_chunks_category_idx ON kb_chunks (category);

CREATE TABLE IF NOT EXISTS kb_meta (
    key   text PRIMARY KEY,
    value text NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE,
    channel         text NOT NULL,
    customer_email  text,
    subject         text NOT NULL DEFAULT '',
    body            text NOT NULL,
    clean_body      text,
    masked_body     text,
    language        text,
    pii_types       jsonb NOT NULL DEFAULT '[]',
    status          text NOT NULL DEFAULT 'received',
    demo_mode       boolean NOT NULL DEFAULT false,
    error           text,
    triage_ms       integer,
    created_at      timestamptz NOT NULL DEFAULT now(),
    triaged_at      timestamptz,
    resolved_at     timestamptz
);
CREATE INDEX IF NOT EXISTS tickets_status_idx ON tickets (status, created_at DESC);

CREATE TABLE IF NOT EXISTS classifications (
    id                 bigserial PRIMARY KEY,
    ticket_id          uuid NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    intent             text NOT NULL,
    secondary_intents  jsonb NOT NULL DEFAULT '[]',
    urgency            text NOT NULL,
    sentiment          text NOT NULL,
    confidence         real NOT NULL,
    rationale          text,
    model              text NOT NULL,
    attempts           integer NOT NULL,
    repaired           boolean NOT NULL DEFAULT false,
    fallback           boolean NOT NULL DEFAULT false,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS classifications_ticket_idx ON classifications (ticket_id);

CREATE TABLE IF NOT EXISTS drafts (
    id                 bigserial PRIMARY KEY,
    ticket_id          uuid NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    body               text NOT NULL,
    needs_escalation   boolean NOT NULL DEFAULT false,
    escalation_reason  text,
    model              text NOT NULL,
    attempts           integer NOT NULL DEFAULT 1,
    retrieved          jsonb NOT NULL DEFAULT '[]',
    verified           boolean NOT NULL,
    grounding_score    real NOT NULL,
    issues             jsonb NOT NULL DEFAULT '[]',
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS drafts_ticket_idx ON drafts (ticket_id);

CREATE TABLE IF NOT EXISTS citations (
    id             bigserial PRIMARY KEY,
    draft_id       bigint NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
    article_id     text NOT NULL,
    url            text,
    in_retrieved   boolean NOT NULL,
    supported      boolean NOT NULL,
    support_score  real NOT NULL
);
CREATE INDEX IF NOT EXISTS citations_draft_idx ON citations (draft_id);

CREATE TABLE IF NOT EXISTS routing_decisions (
    id              bigserial PRIMARY KEY,
    ticket_id       uuid NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    decision        text NOT NULL CHECK (decision IN ('auto_send', 'human_review', 'escalate')),
    team            text NOT NULL,
    reasons         jsonb NOT NULL DEFAULT '[]',
    policy_version  text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS routing_ticket_idx ON routing_decisions (ticket_id);

CREATE TABLE IF NOT EXISTS review_actions (
    id                bigserial PRIMARY KEY,
    ticket_id         uuid NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    draft_id          bigint REFERENCES drafts(id) ON DELETE SET NULL,
    action            text NOT NULL CHECK (action IN ('approve', 'edit', 'reject')),
    reviewer          text NOT NULL,
    final_body        text,
    reason            text,
    edit_distance     integer,
    edit_ratio        real,
    handling_seconds  real,
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS review_actions_ticket_uidx ON review_actions (ticket_id);

CREATE TABLE IF NOT EXISTS ticket_events (
    id          bigserial PRIMARY KEY,
    ticket_id   uuid REFERENCES tickets(id) ON DELETE CASCADE,
    source      text NOT NULL,
    event       text NOT NULL,
    payload     jsonb NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now()
);
