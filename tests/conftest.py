"""Shared pytest fixtures for the Study Task Tracker test suite.

All tests run against the ``tracker_test`` database. The ``TRACKER_DB_NAME``
environment variable is forced to ``tracker_test`` before settings load, so a
developer's ``.env`` pointing at the dev database can never be touched by the
suite. Each test starts with an empty ``tasks`` table.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

# Force the test database before any tracker module reads settings.
os.environ["TRACKER_DB_NAME"] = "tracker_test"

import psycopg  # noqa: E402
import pytest  # noqa: E402

from tracker.db import (  # noqa: E402
    ConnectionSettings,
    get_connection,
    init_schema,
)
from tracker.repository import Repository  # noqa: E402
from tracker.service import TaskService  # noqa: E402


@pytest.fixture(scope="session")
def db_settings() -> ConnectionSettings:
    """Connection settings pointed at the test database."""
    settings = ConnectionSettings()
    assert settings.dbname == "tracker_test", (
        "Tests must run against tracker_test, not "
        f"{settings.dbname!r}. Check TRACKER_DB_NAME."
    )
    return settings


@pytest.fixture
def conn(db_settings: ConnectionSettings) -> Iterator[psycopg.Connection]:
    """An open connection with an empty ``tasks`` table.

    The table is truncated before and after each test so repository writes
    (which commit internally) leave no residue between tests.
    """
    connection = get_connection(db_settings)
    init_schema(connection)
    _truncate(connection)
    yield connection
    _truncate(connection)
    connection.close()


@pytest.fixture
def repo(conn: psycopg.Connection) -> Repository:
    """A repository bound to the test connection."""
    return Repository(conn)


@pytest.fixture
def service(repo: Repository) -> TaskService:
    """A service bound to the test repository."""
    return TaskService(repo)


def _truncate(connection: psycopg.Connection) -> None:
    """Empty the ``tasks`` table and reset its id sequence."""
    with connection.cursor() as cur:
        cur.execute("TRUNCATE tasks RESTART IDENTITY")
    connection.commit()
