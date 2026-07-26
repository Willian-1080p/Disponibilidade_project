import os
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://disponibilidade:troque_esta_senha@db:5432/disponibilidade",
)

pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10, open=False)


def open_pool() -> None:
    pool.open()
    pool.wait()


def close_pool() -> None:
    pool.close()


def ensure_schema() -> None:
    """Aplica estruturas novas sem exigir a exclusão do volume existente."""
    statements = [
        """
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
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_agents_last_seen
        ON agents (last_seen_at DESC)
        """,
        """
        CREATE OR REPLACE VIEW latest_agent_status AS
        SELECT
            id, name, location, client_external_id, hostname, local_ip,
            operating_system, last_seen_at, created_at,
            CASE
                WHEN enabled = FALSE THEN 'disabled'
                WHEN last_seen_at IS NULL THEN 'unknown'
                WHEN last_seen_at >= NOW() - INTERVAL '2 minutes' THEN 'online'
                WHEN last_seen_at >= NOW() - INTERVAL '5 minutes' THEN 'warning'
                ELSE 'offline'
            END AS status
        FROM agents
        """,
    ]
    with pool.connection() as conn:
        for statement in statements:
            conn.execute(statement)
