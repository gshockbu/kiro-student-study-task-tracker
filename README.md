<h1 align="center">📚 Study Task Tracker</h1>

<h2 align="center"><strong>A local CLI task tracker for BU students</strong></h2>

<div align="center">

[![Version](https://img.shields.io/badge/version-0.1.0-black)]()
[![Status](https://img.shields.io/badge/status-Alpha-orange)]()
[![Changelog](https://img.shields.io/badge/changelog-blue)](./CHANGELOG.md)

[![Python](https://img.shields.io/badge/Python-3.x-blue)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-blue)]()
[![Typer](https://img.shields.io/badge/Typer-CLI-green)]()

</div>

## Architecture

Study Task Tracker is a single-process command-line app backed by a local
PostgreSQL database. It uses a three-layer design so each layer stays
independently testable: the CLI parses input and formats output, the service
holds the business rules, and the repository runs parameterized SQL. Nothing
reaches the database except through the repository, and the service never sees
psycopg.

```
tracker <command>
      │
      ▼
┌─────────────┐   parse args, format BU-branded output
│   cli.py    │   (Typer)
└──────┬──────┘
       │ calls
┌──────▼──────┐   validation, state transitions, overdue logic
│ service.py  │
└──────┬──────┘
       │ reads / writes
┌──────▼──────┐   parameterized queries only (psycopg v3)
│repository.py│
└──────┬──────┘
       │ TCP localhost:5432
┌──────▼──────┐
│ PostgreSQL  │   database: tracker (dev), tracker_test (tests)
│     18      │
└─────────────┘
```

Connection settings load from `TRACKER_DB_*` environment variables through
pydantic-settings. The password is held as a `SecretStr`, so it never appears
in logs or error messages. Structured logs (structlog) go to stderr — JSON in
CI, human-readable on an interactive terminal.

## Features

- **Create** a task with a title, optional description, optional due date, and
  a priority of low, medium, or high.
- **List** tasks in a readable view, with overdue tasks flagged in BU Red.
- **Edit** any field of an existing task.
- **Complete** and **reopen** tasks (Open ↔ Complete).
- **Delete** a task, with a confirmation prompt you can skip using `--yes`.
- **Filter** by status and priority, and combine the two.
- **Sort** by due date or priority, ascending or descending.
- **Validation** rejects a blank title, a malformed date, or an unknown
  priority with a clear, plain-English message.

## Environment Variables

Copy `.env.example` to `.env` and fill in your local values. The `.env` file is
gitignored and must never be committed.

```env
# ======= PostgreSQL Configuration =======
TRACKER_DB_HOST=<str>       # server hostname (default: localhost)
TRACKER_DB_PORT=<int>       # server port (default: 5432)
TRACKER_DB_NAME=<str>       # database name (default: tracker)
TRACKER_DB_USER=<str>       # PostgreSQL username (required)
TRACKER_DB_PASSWORD=<str>   # PostgreSQL password (required, held as SecretStr)
```

To run the test suite against a separate database, set
`TRACKER_DB_NAME=tracker_test`.

## Prerequisites

- Python 3.11 or newer.
- A locally running PostgreSQL 18 instance.
- Two databases — `tracker` and `tracker_test` — and a role that can use them.
  Since PostgreSQL 15, a new role needs an explicit grant to create tables in
  the `public` schema. Run this once per database as a superuser:

  ```sql
  GRANT CREATE, USAGE ON SCHEMA public TO <your_user>;
  ```

## Package Structure

```
study-task-tracker/
├── src/
│   └── tracker/
│       ├── __init__.py
│       ├── cli.py              # Typer app — BU-branded output
│       ├── service.py          # business rules, validation, transitions
│       ├── repository.py       # parameterized SQL (psycopg v3)
│       ├── db.py               # settings, connection, schema init
│       ├── models.py           # Task, Priority, Status (Pydantic v2)
│       └── logging_config.py   # structlog setup
├── tests/
│   ├── conftest.py             # fixtures, forces tracker_test
│   ├── test_repository.py
│   ├── test_service.py
│   ├── test_cli.py
│   └── test_persistence.py
├── .env.example
├── pyproject.toml
└── README.md
```

## Installation and Running

Install dependencies into a virtual environment with uv, then run the CLI:

```bash
uv sync --extra dev
uv run tracker --help
```

Create and list a task:

```bash
uv run tracker create --title "Read chapter 3" --due 2026-12-31 --priority high
uv run tracker list
```

## Testing

Tests run against the `tracker_test` database. The suite forces
`TRACKER_DB_NAME=tracker_test` on its own, so your `.env` can keep pointing at
the dev database. Run the full suite with:

```bash
uv run pytest
```

This runs every test and reports coverage. The suite covers the repository,
service, CLI, and data persistence.

## Reset

To clear all tasks but keep the table:

```sql
TRUNCATE tasks RESTART IDENTITY;
```

To drop the table entirely (it is recreated on the next run):

```sql
DROP TABLE tasks;
```

Run either in `psql` against the `tracker` database.

## Known Limitations

- Requires a locally running PostgreSQL instance.
- Single local user — no application-level authentication.
- No undo — deletion is permanent once confirmed.
- Due dates are dates, not datetimes.
- Colored output needs a color-capable terminal; plain text is used otherwise.
- No migration tooling — schema changes are manual.
- Typing `--title ""` directly in PowerShell is intercepted by the shell before
  the app runs; use a non-empty title, or omit `--title` to see the validation
  message.
