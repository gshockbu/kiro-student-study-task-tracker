"""Database connection settings and schema setup for the Study Task Tracker.

Connection parameters are loaded from ``TRACKER_DB_*`` environment variables
(or a local ``.env`` file) via pydantic-settings. The password is held as a
``SecretStr`` so it never appears in logs, tracebacks, or ``repr()`` output.
"""

from __future__ import annotations

import psycopg
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id          SERIAL      PRIMARY KEY,
    title       TEXT        NOT NULL,
    description TEXT,
    due_date    DATE,
    priority    TEXT        NOT NULL DEFAULT 'medium',
    status      TEXT        NOT NULL DEFAULT 'open',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class ConnectionSettings(BaseSettings):
    """PostgreSQL connection settings sourced from the environment.

    Reads ``TRACKER_DB_HOST``, ``TRACKER_DB_PORT``, ``TRACKER_DB_NAME``,
    ``TRACKER_DB_USER``, and ``TRACKER_DB_PASSWORD`` from the environment or a
    local ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_prefix="TRACKER_DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "localhost"
    port: int = 5432
    dbname: str = Field(default="tracker", alias="TRACKER_DB_NAME")
    user: str = ""
    password: SecretStr = SecretStr("")
    connect_timeout: int = 10

    def dsn(self) -> str:
        """Build a libpq connection string.

        A ``connect_timeout`` is included so an unreachable host fails with a
        clear error instead of hanging the CLI indefinitely.

        Returns:
            A keyword/value DSN string. The password is resolved from the
            ``SecretStr`` only at call time and must never be logged.
        """
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password.get_secret_value()} "
            f"connect_timeout={self.connect_timeout}"
        )


def get_connection(
    settings: ConnectionSettings | None = None,
) -> psycopg.Connection:
    """Open a connection to the configured PostgreSQL database.

    Args:
        settings: Connection settings. When ``None``, settings are loaded
            from the environment and ``.env``.

    Returns:
        An open psycopg connection.

    Raises:
        RuntimeError: If the database cannot be reached. The message includes
            host, port, and database name but never the password.
    """
    cfg = settings or ConnectionSettings()
    try:
        return psycopg.connect(cfg.dsn())
    except psycopg.OperationalError as e:
        raise RuntimeError(
            f"Cannot connect to PostgreSQL at {cfg.host}:{cfg.port}/{cfg.dbname}."
        ) from e


def init_schema(conn: psycopg.Connection) -> None:
    """Create the ``tasks`` table if it does not already exist.

    Args:
        conn: An open psycopg connection. The change is committed before
            returning.
    """
    with conn.cursor() as cur:
        cur.execute(_SCHEMA_SQL)
    conn.commit()
