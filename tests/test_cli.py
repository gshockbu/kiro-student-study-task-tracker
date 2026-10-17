"""Integration tests for the CLI (T-12).

These exercise the Typer app through ``CliRunner``, which passes arguments as
a list (so empty-string arguments reach the app, unlike an interactive shell).
Each test depends on the ``conn`` fixture for a clean ``tasks`` table.
"""

from __future__ import annotations

import psycopg
from typer.testing import CliRunner

from tracker.cli import app

runner = CliRunner()


def test_create_command_success(conn: psycopg.Connection) -> None:
    result = runner.invoke(app, ["create", "--title", "Read chapter 3"])
    assert result.exit_code == 0
    assert "Created task" in result.stdout


def test_create_command_missing_title(conn: psycopg.Connection) -> None:
    result = runner.invoke(app, ["create", "--title", ""])
    assert result.exit_code == 1
    assert "Title is required." in result.stderr


def test_list_command_empty(conn: psycopg.Connection) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No tasks found." in result.stdout


def test_list_command_shows_tasks(conn: psycopg.Connection) -> None:
    runner.invoke(app, ["create", "--title", "Visible task"])
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Visible task" in result.stdout


def test_list_command_filter_status(conn: psycopg.Connection) -> None:
    runner.invoke(app, ["create", "--title", "Open task"])
    runner.invoke(app, ["create", "--title", "Done task"])
    runner.invoke(app, ["done", "2"])

    result = runner.invoke(app, ["list", "--status", "open"])
    assert result.exit_code == 0
    assert "Open task" in result.stdout
    assert "Done task" not in result.stdout


def test_done_command(conn: psycopg.Connection) -> None:
    runner.invoke(app, ["create", "--title", "Finish me"])
    result = runner.invoke(app, ["done", "1"])
    assert result.exit_code == 0
    assert "Completed task" in result.stdout


def test_reopen_command(conn: psycopg.Connection) -> None:
    runner.invoke(app, ["create", "--title", "Reopen me"])
    runner.invoke(app, ["done", "1"])
    result = runner.invoke(app, ["reopen", "1"])
    assert result.exit_code == 0
    assert "Reopened task" in result.stdout


def test_delete_command_with_yes_flag(conn: psycopg.Connection) -> None:
    runner.invoke(app, ["create", "--title", "Delete me"])
    result = runner.invoke(app, ["delete", "1", "--yes"])
    assert result.exit_code == 0
    assert "Deleted task" in result.stdout


def test_delete_command_not_found(conn: psycopg.Connection) -> None:
    result = runner.invoke(app, ["delete", "999", "--yes"])
    assert result.exit_code == 1
    assert "not found" in result.stderr


def test_edit_command(conn: psycopg.Connection) -> None:
    runner.invoke(app, ["create", "--title", "Original"])
    result = runner.invoke(app, ["edit", "1", "--title", "Edited"])
    assert result.exit_code == 0
    assert "Updated task" in result.stdout

    listing = runner.invoke(app, ["list"])
    assert "Edited" in listing.stdout
