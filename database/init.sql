CREATE TABLE IF NOT EXISTS targets (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    target VARCHAR(500) NOT NULL,
    check_type VARCHAR(20) NOT NULL CHECK (check_type IN ('http', 'tcp', 'ping', 'ssl')),
    port INTEGER,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT target_type_unique UNIQUE (target, check_type, port)
);

CREATE TABLE IF NOT EXISTS check_results (
    id BIGSERIAL PRIMARY KEY,
    target_id BIGINT NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('online', 'offline', 'warning')),
    latency_ms NUMERIC(12,2),
    status_code INTEGER,
    message TEXT,
    certificate_expires_at TIMESTAMPTZ,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_results_target_checked
    ON check_results (target_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS agents (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    location VARCHAR(120),
    client_external_id VARCHAR(120),
    token_hash CHAR(64) NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    hostname VARCHAR(255),
    local_ip VARCHAR(64),
    operating_system VARCHAR(255),
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_last_seen
    ON agents (last_seen_at DESC);

CREATE OR REPLACE VIEW latest_target_status AS
SELECT DISTINCT ON (t.id)
    t.id,
    t.name,
    t.target,
    t.check_type,
    t.port,
    r.status,
    r.latency_ms,
    r.status_code,
    r.message,
    r.certificate_expires_at,
    r.checked_at
FROM targets t
LEFT JOIN check_results r ON r.target_id = t.id
WHERE t.enabled = TRUE
ORDER BY t.id, r.checked_at DESC NULLS LAST;

CREATE OR REPLACE VIEW latest_agent_status AS
SELECT
    id,
    name,
    location,
    client_external_id,
    hostname,
    local_ip,
    operating_system,
    last_seen_at,
    created_at,
    CASE
        WHEN enabled = FALSE THEN 'disabled'
        WHEN last_seen_at IS NULL THEN 'unknown'
        WHEN last_seen_at >= NOW() - INTERVAL '2 minutes' THEN 'online'
        WHEN last_seen_at >= NOW() - INTERVAL '5 minutes' THEN 'warning'
        ELSE 'offline'
    END AS status
FROM agents;

INSERT INTO targets (name, target, check_type, port)
VALUES
    ('API do projeto', 'http://api:8000/health', 'http', NULL),
    ('PostgreSQL', 'db', 'tcp', 5432)
ON CONFLICT DO NOTHING;
