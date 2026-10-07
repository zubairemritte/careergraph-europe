PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('demo', 'live')),
    country TEXT NOT NULL,
    scope TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    catalog_hash TEXT NOT NULL,
    report TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS offers (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    offer_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    country TEXT NOT NULL,
    role TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    description TEXT NOT NULL,
    published_at TEXT NOT NULL,
    expires_at TEXT,
    source_url TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    PRIMARY KEY (run_id, offer_id),
    UNIQUE (run_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS skill_mentions (
    run_id TEXT NOT NULL,
    offer_id TEXT NOT NULL,
    skill TEXT NOT NULL,
    start_offset INTEGER NOT NULL CHECK (start_offset >= 0),
    end_offset INTEGER NOT NULL,
    matched_text TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    PRIMARY KEY (run_id, offer_id, skill),
    FOREIGN KEY (run_id, offer_id) REFERENCES offers(run_id, offer_id)
);

CREATE TABLE IF NOT EXISTS benchmark_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    retrieved_at TEXT NOT NULL,
    source_updated_at TEXT,
    request_url TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    metadata TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmarks (
    snapshot_id TEXT NOT NULL REFERENCES benchmark_snapshots(snapshot_id),
    country TEXT NOT NULL,
    quarter TEXT NOT NULL,
    vacancy_rate REAL CHECK (vacancy_rate >= 0 AND vacancy_rate <= 100),
    status_flag TEXT,
    PRIMARY KEY (snapshot_id, country, quarter)
);

CREATE INDEX IF NOT EXISTS offers_cohort ON offers(run_id, country, role, published_at);
CREATE INDEX IF NOT EXISTS runs_latest ON runs(kind, status, completed_at);
