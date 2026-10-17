"""Persistence tests (T-13).

These prove data survives a connection teardown and that the schema is
created on first connection. They use committed data and clean up afterwards
so the test database is left in its original (empty) state.
"""

from __future__ import annotations

import psycopg

from tracker.db import ConnectionSettings, get_connection, init_schema
from tracker.models import Task
from tracker.repository import Repository


def test_tasks_survive_connection_teardown(
    db_settings: ConnectionSettings,
) -> None:
    """A task written on one connection is readable on a fresh one."""
    first = get_connection(db_settings)
    init_schema(first)
    try:
        repo = Repository(first)
        created = repo.add(Task(title="Survives restart"))
        task_id = created.id
    finally:
        first.close()

    second = get_connection(db_settings)
    try:
        reloaded = Repository(second).get(task_id)
        assert reloaded is not None
        assert reloaded.title == "Survives restart"
    finally:
        with second.cursor() as cur:
            cur.execute("TRUNCATE tasks RESTART IDENTITY")
        second.commit()
        second.close()


def test_schema_initialises_on_first_connection(
    db_settings: ConnectionSettings,
) -> None:
    """Dropping and re-initialising the schema yields an empty table."""
    conn = get_connection(db_settings)
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS tasks")
        conn.commit()

        # Table is gone; init_schema recreates it.
        init_schema(conn)
        assert Repository(conn).list() == []
    finally:
        _ensure_empty(conn)
        conn.close()


def _ensure_empty(conn: psycopg.Connection) -> None:
    """Guarantee an empty ``tasks`` table exists after a test."""
    init_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE tasks RESTART IDENTITY")
    conn.commit()
