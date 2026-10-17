# Design — Student Study Task Tracker

Derived from: `AI_Student_Project_Specification_SMALL.docx` §7–9, `requirements.md`.
Skills applied: `standard-libraries`, `pyproject-toml`, `python-project-structure`, `bu-brand`, `readme-changelog`.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────┐
│              CLI Entry Point                    │
│         src/tracker/cli.py  (Typer)             │
│                                                 │
│  create  list  edit  done  reopen  delete       │
└───────────────────┬─────────────────────────────┘
                    │ calls
┌───────────────────▼─────────────────────────────┐
│              Service Layer                      │
│         src/tracker/service.py                  │
│                                                 │
│  Business rules, validation, state transitions  │
└───────────────────┬─────────────────────────────┘
                    │ reads/writes
┌───────────────────▼─────────────────────────────┐
│           Repository Layer                      │
│      src/tracker/repository.py                  │
│                                                 │
│  psycopg (v3) — parameterised queries only      │
│  ConnectionSettings loaded via pydantic-settings│
└───────────────────┬─────────────────────────────┘
                    │ TCP (localhost)
┌───────────────────▼─────────────────────────────┐
│         Local PostgreSQL 18 Instance            │
│  Database: tracker  (dev)                       │
│  Database: tracker_test  (test)                 │
│  Host: localhost:5432  (default)                │
└─────────────────────────────────────────────────┘
```

**One process. One local PostgreSQL database. Credentials via pydantic-settings + environment variables only.**

### Layer responsibilities

| Layer | File | Responsibility |
|---|---|---|
| CLI | `cli.py` | Parse args, format BU-branded output, call service, handle errors |
| Service | `service.py` | Business rules, validation, state transitions |
| Repository | `repository.py` | Parameterised SQL queries only — no business logic |
| DB | `db.py` | `ConnectionSettings` (pydantic-settings), `get_connection()`, `init_schema()` |
| Models | `models.py` | `Task`, `Priority`, `Status` — Pydantic v2 models |
| Logging | `logging_config.py` | structlog setup — JSON in prod, ConsoleRenderer in dev |

---

## 2. Technology Decisions

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Specified by steering |
| CLI framework | `typer>=0.12.0` | Type-hint-driven; clean `--help`; active community |
| PostgreSQL driver | `psycopg[binary]>=3.1.0` | psycopg v3 is the org standard; replaces legacy psycopg2 |
| Settings / env vars | `pydantic-settings>=2.1.0` | Org standard for env-based config; reads `.env` automatically; `SecretStr` for password |
| Data validation | `pydantic>=2.5.0` | Org standard v2; 5–50x faster than v1 |
| Structured logging | `structlog>=25.0.0` | Org standard; JSON in cluster/prod, ConsoleRenderer on TTY |
| Packaging | `pyproject.toml` + `uv` | Org standard; reproducible via `uv.lock` |
| Testing | `pytest>=8.0.0` + `pytest-mock>=3.12.0` + `pytest-cov>=4.1.0` | Org standard test stack |
| Linting + formatting | `ruff>=0.1.0` | Replaces black, flake8, isort, pylint in one tool |
| UI branding | BU brand (bu-brand skill) | BU Red for errors/overdue, plain English, active voice |

---

## 3. Data Model

### Task entity

| Field | PostgreSQL Type | Python Type | Constraints |
|---|---|---|---|
| `id` | `SERIAL` | `int \| None` | Primary key, auto-increment |
| `title` | `TEXT NOT NULL` | `str` | Required, non-empty, max 200 chars |
| `description` | `TEXT` | `str \| None` | Optional, nullable |
| `due_date` | `DATE` | `date \| None` | ISO 8601, nullable |
| `priority` | `TEXT NOT NULL` | `Priority` enum | `low`, `medium`, `high`. Default: `medium` |
| `status` | `TEXT NOT NULL` | `Status` enum | `open`, `complete`. Default: `open` |
| `created_at` | `TIMESTAMPTZ NOT NULL` | `datetime` | Set on insert via `DEFAULT now()` |
| `updated_at` | `TIMESTAMPTZ NOT NULL` | `datetime` | Updated on every write |

### SQL schema (PostgreSQL 18)

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id          SERIAL      PRIMARY KEY,
    title       TEXT        NOT NULL,
    description TEXT,
    due_date    DATE,
    priority    TEXT        NOT NULL DEFAULT 'medium',
    status      TEXT        NOT NULL DEFAULT 'open',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Schema is created automatically on first connection via `init_schema()`.

### Python models (Pydantic v2)

```python
# src/tracker/models.py
from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field

class Priority(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"

class Status(str, Enum):
    OPEN     = "open"
    COMPLETE = "complete"

class Task(BaseModel):
    id:          int | None  = None
    title:       str         = Field(..., min_length=1, max_length=200)
    description: str | None  = None
    due_date:    date | None = None
    priority:    Priority    = Priority.MEDIUM
    status:      Status      = Status.OPEN
    created_at:  datetime | None = None
    updated_at:  datetime | None = None

    model_config = {"populate_by_name": True}
```

---

## 4. Settings and Connection (pydantic-settings)

```python
# src/tracker/db.py
from __future__ import annotations
import psycopg
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class ConnectionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRACKER_DB_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
    host:     str       = "localhost"
    port:     int       = 5432
    dbname:   str       = "tracker"        # maps to TRACKER_DB_NAME
    user:     str       = ""
    password: SecretStr = SecretStr("")

    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password.get_secret_value()}"
        )

def get_connection(settings: ConnectionSettings | None = None) -> psycopg.Connection:
    cfg = settings or ConnectionSettings()
    try:
        return psycopg.connect(cfg.dsn())
    except psycopg.OperationalError as e:
        raise RuntimeError(
            f"Cannot connect to PostgreSQL at {cfg.host}:{cfg.port}/{cfg.dbname} — {e}"
        ) from e

def init_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("""
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
        """)
    conn.commit()
```

`pydantic-settings` reads `TRACKER_DB_*` variables from the environment or `.env` automatically. The password is stored as `SecretStr` — it is never exposed in logs or `repr()`.

---

## 5. Project Structure

```
study-task-tracker/
├── src/
│   └── tracker/
│       ├── __init__.py
│       ├── cli.py              # Typer app — BU-branded output
│       ├── service.py          # Business logic, validation
│       ├── repository.py       # PostgreSQL queries (psycopg v3)
│       ├── db.py               # ConnectionSettings, get_connection, init_schema
│       ├── models.py           # Task, Priority, Status (Pydantic v2)
│       └── logging_config.py   # structlog setup
├── tests/
│   ├── conftest.py             # DB fixtures: conn (rollback), repo, service
│   ├── test_repository.py      # Unit: CRUD, filter, sort
│   ├── test_service.py         # Unit: validation, state transitions
│   ├── test_cli.py             # Integration: CLI via typer.testing.CliRunner
│   └── test_persistence.py     # Persistence: survive connection teardown
├── .env                        # Real credentials (gitignored)
├── .env.example                # Template with no values (committed)
├── .gitignore                  # Includes .env, .venv, __pycache__, .ruff_cache
├── pyproject.toml
├── uv.lock
├── README.md                   # readme-changelog skill format
├── CHANGELOG.md
├── requirements.md
├── design.md
└── tasks.md
```

---

## 6. Key Design Decisions

### 6.1 pydantic-settings for connection config

`pydantic-settings` is the org standard for environment-based configuration. It reads `.env` automatically, validates types, and stores the password as `SecretStr` — preventing accidental logging. This replaces the raw `os.getenv()` approach.

### 6.2 Pydantic v2 models (not dataclasses)

Org standard is Pydantic v2. Models get free validation (`min_length=1`), serialisation, and `model_config`. The `Task` model validates title length at construction time — before it reaches the service layer.

### 6.3 structlog for logging

Org standard is `structlog`. In dev (TTY detected): `ConsoleRenderer` for human-readable output. In prod/CI (non-TTY): `JSONRenderer`. Never f-strings in log calls (ruff `G004`). Password never appears in any log event.

### 6.4 BU brand in CLI output

- **BU Red** (`\033[31m` ANSI approximation, checked with `sys.stdout.isatty()`) for overdue tasks, errors, warnings
- **Bold** for task titles in list view
- **Plain English, active voice** for all messages — "Task 5 not found." not "NotFoundError(5)"
- **Oxford comma** in multi-item enumerations
- No all-caps emphasis anywhere

### 6.5 Three-layer architecture

CLI → Service → Repository keeps each layer independently testable. The service layer never sees psycopg; the repository never knows about Typer. Validation lives in the service layer (not the CLI) so it's covered by unit tests without CLI overhead.

### 6.6 Confirmation for delete (FR-05)

```bash
tracker delete 3           # prompts: Delete task 3 "Buy textbooks"? [y/N]
tracker delete 3 --yes     # skips prompt (used in tests and scripts)
```

### 6.7 Overdue detection

Computed at read time: `due_date < date.today()` and `status == open`. No stored flag, no background job. Marked in the list view with BU Red `[OVERDUE]` prefix.

---

## 7. CLI Command Reference

```
tracker create  --title TEXT [--description TEXT] [--due YYYY-MM-DD] [--priority low|medium|high]
tracker list    [--status open|complete] [--priority low|medium|high] [--sort due|priority] [--desc]
tracker edit    ID [--title TEXT] [--description TEXT] [--due YYYY-MM-DD] [--priority low|medium|high]
tracker done    ID
tracker reopen  ID
tracker delete  ID [--yes]
```

All commands exit 0 on success, 1 on error. Errors print to stderr in BU voice.

---

## 8. State Transition Diagram

```
         create
           │
           ▼
        ┌──────┐
        │ OPEN │◄──── reopen ────┐
        └──┬───┘                 │
           │ done                │
           ▼                     │
      ┌──────────┐               │
      │ COMPLETE ├───────────────┘
      └──────────┘
           │ delete (either state)
           ▼
        (gone)
```

---

## 9. Error Handling

| Scenario | Message (BU voice) | Exit |
|---|---|---|
| Blank title | `Error: Title is required.` | 1 |
| Invalid date | `Error: Due date must be YYYY-MM-DD (e.g., 2026-12-31).` | 1 |
| Invalid priority | `Error: Priority must be low, medium, or high.` | 1 |
| Task not found | `Error: Task {id} not found.` | 1 |
| DB connection refused | `Error: Cannot connect to PostgreSQL at localhost:5432/tracker.` | 1 |
| DB auth failure | Same as above — password never in message | 1 |
| Unexpected exception | `Error: Something went wrong. Check the logs for details.` | 1 |

Messages are printed to stderr. Tracebacks go to the structlog ERROR level, never to stdout.

---

## 10. Testing Strategy

| Test type | File | Isolation | Tool |
|---|---|---|---|
| Unit — repository | `test_repository.py` | Transaction rollback per test | pytest + psycopg |
| Unit — service | `test_service.py` | Transaction rollback per test (via repo fixture) | pytest + pytest-mock |
| Integration — CLI | `test_cli.py` | Transaction rollback per test (via env override) | pytest + typer.testing.CliRunner |
| Persistence | `test_persistence.py` | Committed rows, cleaned in `finally` | pytest + psycopg |

### conftest.py fixtures

```python
# tests/conftest.py
import pytest
import psycopg
from tracker.db import ConnectionSettings, get_connection, init_schema
from tracker.repository import Repository
from tracker.service import TaskService

@pytest.fixture(scope="session")
def db_settings():
    # Override DB name for tests via TRACKER_DB_NAME=tracker_test in environment
    return ConnectionSettings()

@pytest.fixture
def conn(db_settings):
    connection = get_connection(db_settings)
    init_schema(connection)
    connection.autocommit = False
    yield connection
    connection.rollback()
    connection.close()

@pytest.fixture
def repo(conn):
    return Repository(conn)

@pytest.fixture
def service(repo):
    return TaskService(repo)
```

Single test command: `pytest` (with `TRACKER_DB_NAME=tracker_test` set in `.env` or environment).

---

## 11. Logging Design (structlog)

```python
# src/tracker/logging_config.py
import sys
import structlog

def configure_logging(level: str = "WARNING") -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer()
            if sys.stdout.isatty()
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), level.upper(), 30)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

- Dev (TTY): human-readable ConsoleRenderer
- Prod/CI: JSONRenderer for log aggregation
- Startup logs: `host` and `dbname` only — **never** `password`
- All log calls use key=value style (ruff `G004` enforced): `logger.info("startup", host=cfg.host, dbname=cfg.dbname)`

---

## 12. pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "study-task-tracker"
version = "0.1.0"
description = "A local CLI task tracker for BU students"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12.0",
    "psycopg[binary]>=3.1.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "structlog>=25.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
]

[project.scripts]
tracker = "tracker.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "--strict-markers --cov=tracker --cov-report=term-missing"

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "G"]
```

---

## 13. README Structure (readme-changelog skill)

The README must follow this exact structure:

```markdown
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
## Features
## Environment Variables
## Package Structure
## Testing
## Reset
```

---

## 14. Known Limitations

- Requires a locally running PostgreSQL instance.
- Single local user — no application-level authentication.
- No undo/redo — deletion is permanent after confirmation.
- Due dates are dates, not datetimes.
- ANSI colour output requires a colour-capable terminal; plain text fallback is used otherwise.
- No database migration tooling — schema changes require manual SQL.
