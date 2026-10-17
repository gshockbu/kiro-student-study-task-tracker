# Tasks — Student Study Task Tracker

Derived from: `AI_Student_Project_Specification_SMALL.docx` §13, `requirements.md`, `design.md`.
Skills applied: `standard-libraries`, `pyproject-toml`, `python-project-structure`, `bu-brand`, `readme-changelog`.

Complete tasks in order — each phase depends on the previous.

---

## Phase 1 — Foundation

### T-01 Initialise project structure and tooling
**Requirements:** NFR-01, NFR-02, NFR-06, SEC-06  
**Skills:** `pyproject-toml`, `python-project-structure`  
**Effort:** ~1 hour

- [ ] Create `pyproject.toml` per `design.md §12` — `setuptools` backend, `requires-python = ">=3.11"`, lower-bound version pins, `dev` extras, `[tool.ruff]` with `G` rule set, `[tool.pytest.ini_options]` with `--cov`
- [ ] Create directory tree per `design.md §5`: `src/tracker/`, `tests/`
- [ ] Add `__init__.py` to `src/tracker/`
- [ ] Add `.gitignore` — must include: `.env`, `.venv`, `__pycache__/`, `*.pyc`, `.ruff_cache/`, `*.egg-info/`, `dist/`, `.coverage`, `htmlcov/`
- [ ] Confirm `.env.example` exists at project root (already created)
- [ ] Run `uv sync --extra dev` in a fresh venv — must succeed

**Done when:** `uv sync --extra dev` exits 0 and `python -m pytest --collect-only` finds no errors.

---

### T-02 Define data models (Pydantic v2)
**Requirements:** FR-01, FR-04, FR-08  
**Skills:** `standard-libraries` (pydantic v2)  
**Effort:** ~30 minutes

- [ ] Create `src/tracker/models.py`
- [ ] Implement `Priority(str, Enum)`: `LOW="low"`, `MEDIUM="medium"`, `HIGH="high"`
- [ ] Implement `Status(str, Enum)`: `OPEN="open"`, `COMPLETE="complete"`
- [ ] Implement `Task(BaseModel)` with all fields from `design.md §3` — use `Field(..., min_length=1, max_length=200)` for title
- [ ] Set `model_config = {"populate_by_name": True}`
- [ ] Use `str | None` syntax (never `Optional[str]`)

**Done when:** `from tracker.models import Task, Priority, Status` imports without error; `Task(title="")` raises `ValidationError`.

---

### T-03 Implement database connection and schema
**Requirements:** FR-09, SEC-05, SEC-06, OBS-01, OBS-05  
**Skills:** `standard-libraries` (pydantic-settings, psycopg v3)  
**Effort:** ~1.5 hours

- [ ] Create `src/tracker/db.py`
- [ ] Implement `ConnectionSettings(BaseSettings)` per `design.md §4`:
  - `model_config = SettingsConfigDict(env_prefix="TRACKER_DB_", env_file=".env")`
  - `password: SecretStr` — never a plain `str`
  - `dsn()` method calls `self.password.get_secret_value()` — never logs the result
- [ ] Implement `get_connection(settings=None) -> psycopg.Connection`
  - Catch `psycopg.OperationalError`, raise `RuntimeError` with host/port/dbname — **no password**
- [ ] Implement `init_schema(conn) -> None` — `CREATE TABLE IF NOT EXISTS tasks (...)` per `design.md §3`

**Done when:** `ConnectionSettings()` reads from `.env`; connecting with valid credentials succeeds; connecting with wrong host raises `RuntimeError` with a readable message that does not contain the password.

---

### T-04 Implement repository layer (PostgreSQL / psycopg v3)
**Requirements:** FR-09, SEC-02  
**Skills:** `standard-libraries` (psycopg v3)  
**Effort:** ~2 hours

- [ ] Create `src/tracker/repository.py`
- [ ] `Repository.__init__(conn: psycopg.Connection)` — stores connection only
- [ ] `Repository.add(task: Task) -> Task` — `INSERT ... RETURNING id`; return task with id set
- [ ] `Repository.get(task_id: int) -> Task | None`
- [ ] `Repository.list(status=None, priority=None, sort_by=None, descending=False) -> list[Task]` — optional `WHERE`, `ORDER BY`
- [ ] `Repository.update(task: Task) -> Task` — `UPDATE ... SET ... WHERE id = %s`
- [ ] `Repository.delete(task_id: int) -> bool` — `DELETE WHERE id = %s`; return False if 0 rows
- [ ] **All queries use psycopg `%s` placeholders — zero string interpolation** (SEC-02)
- [ ] `conn.commit()` after every write

**Done when:** Repository unit tests pass (T-09).

---

### T-05 Implement logging (structlog)
**Requirements:** OBS-01 – OBS-05, SEC-03  
**Skills:** `standard-libraries` (structlog)  
**Effort:** ~30 minutes

- [ ] Create `src/tracker/logging_config.py`
- [ ] Implement `configure_logging(level="WARNING")` per `design.md §11`
  - `sys.stdout.isatty()` → `ConsoleRenderer`; else → `JSONRenderer`
- [ ] **No f-strings in any log call** (ruff `G004` will catch violations)
- [ ] Log startup: `logger.info("startup", host=..., dbname=...)` — never `password`
- [ ] Log DB errors: `logger.error("db_connection_failed", host=..., port=..., dbname=...)`

**Done when:** `configure_logging("INFO")` produces a startup line with host/dbname; password is absent from all log output.

---

## Phase 2 — Service Layer

### T-06 Implement service — create and list
**Requirements:** FR-01, FR-02, FR-08, FR-10  
**Effort:** ~1.5 hours

- [ ] Create `src/tracker/service.py`
- [ ] Define `ValidationError(Exception)` and `NotFoundError(Exception)` with clear messages
- [ ] `TaskService.__init__(repo: Repository)`
- [ ] `TaskService.create(title, description, due_date, priority) -> Task`
  - Validate title non-empty (raise `ValidationError: "Title is required."`)
  - Validate due_date format if provided (raise `ValidationError: "Due date must be YYYY-MM-DD."`)
  - Validate priority value (raise `ValidationError: "Priority must be low, medium, or high."`)
  - Set `status=open`; delegate to `repo.add()`
- [ ] `TaskService.list(status=None, priority=None, sort_by=None, descending=False) -> list[Task]`
  - Returns `[]` — never raises — when no tasks exist (FR-10)

**Done when:** Service unit tests for create and list pass.

---

### T-07 Implement service — edit, complete, reopen, delete
**Requirements:** FR-03, FR-04, FR-05, FR-10  
**Effort:** ~1.5 hours

- [ ] `TaskService.edit(task_id, **fields) -> Task`
  - `repo.get()` → raise `NotFoundError: "Task {id} not found."` if absent
  - Validate changed fields with same rules as create
- [ ] `TaskService.complete(task_id) -> Task` — raise `NotFoundError` if absent; set `status=complete`
- [ ] `TaskService.reopen(task_id) -> Task` — raise `NotFoundError` if absent; set `status=open`
- [ ] `TaskService.delete(task_id) -> None` — raise `NotFoundError` if absent; delegate to `repo.delete()`

**Done when:** Service unit tests for edit, complete, reopen, and delete pass.

---

### T-08 Implement service — filter, sort, overdue
**Requirements:** FR-06, FR-07  
**Effort:** ~45 minutes

- [ ] Pass `status`, `priority`, `sort_by`, `descending` through to `repo.list()`
- [ ] Priority sort order: `high > medium > low`
- [ ] Tasks with `due_date = None` sort last on due-date sort
- [ ] Annotate `is_overdue` at read time: `due_date < date.today()` and `status == open`
  - Add `is_overdue: bool = False` computed field to `Task` or annotate in service

**Done when:** Filter and sort unit tests pass.

---

## Phase 3 — CLI (BU Brand)

### T-09 Implement CLI — all commands
**Requirements:** FR-01 – FR-10, NFR-01, NFR-04, NFR-07  
**Skills:** `bu-brand`  
**Effort:** ~2.5 hours

- [ ] Create `src/tracker/cli.py` with `app = typer.Typer()`
- [ ] Register entry point in `pyproject.toml`: `tracker = "tracker.cli:app"`
- [ ] `tracker create` — all fields as options (FR-01)
- [ ] `tracker list` — with `--status`, `--priority`, `--sort`, `--desc` (FR-02, FR-06, FR-07)
  - Show `[OVERDUE]` in BU Red (`\033[31m`) when terminal is a TTY, plain `[OVERDUE]` otherwise
  - Show `No tasks found.` when list is empty (FR-10)
- [ ] `tracker edit ID` (FR-03)
- [ ] `tracker done ID` (FR-04)
- [ ] `tracker reopen ID` (FR-04)
- [ ] `tracker delete ID [--yes]` — prompt `Delete task {id} "{title}"? [y/N]` without `--yes` (FR-05)
- [ ] All commands: catch `ValidationError` → print `Error: {message}` to stderr in BU Red (TTY) → exit 1
- [ ] All commands: catch `NotFoundError` → print `Error: {message}` to stderr in BU Red (TTY) → exit 1
- [ ] All commands: call `configure_logging()` + `load_dotenv()` + `init_schema()` once at startup

**BU brand checklist for all output:**
- [ ] Active voice, plain English — "Task created." not "Task has been successfully created."
- [ ] Oxford comma in any multi-item enumerations
- [ ] No all-caps for emphasis
- [ ] BU Red for errors and overdue only — body text uses terminal default
- [ ] Error messages are specific: "Task 5 not found." not "An error occurred."

**Done when:** `tracker --help` and all sub-command `--help` outputs are correct; smoke test of all six commands passes.

---

## Phase 4 — Automated Tests

### T-10 Write unit tests — repository
**Requirements:** NFR-03  
**Effort:** ~1.5 hours

- [ ] Create `tests/conftest.py` per `design.md §10` — `conn` fixture with rollback; `repo` fixture; `service` fixture
- [ ] Set `TRACKER_DB_NAME=tracker_test` in test environment (`.env` or `pytest.ini` `env` section)
- [ ] `tests/test_repository.py`:
  - `test_add_returns_task_with_id`
  - `test_get_returns_none_for_missing_id`
  - `test_list_returns_all_tasks`
  - `test_list_filter_by_status`
  - `test_list_filter_by_priority`
  - `test_list_sort_by_due_date`
  - `test_list_sort_by_priority`
  - `test_update_persists_changes`
  - `test_delete_removes_task`
  - `test_delete_returns_false_for_missing_id`

**Done when:** All repository tests pass; rollback leaves test DB empty after each test.

---

### T-11 Write unit tests — service
**Requirements:** NFR-03  
**Effort:** ~1.5 hours

- [ ] `tests/test_service.py`:
  - `test_create_persists_task`
  - `test_create_raises_on_blank_title`
  - `test_create_raises_on_invalid_date`
  - `test_create_raises_on_invalid_priority`
  - `test_edit_updates_fields`
  - `test_edit_raises_not_found`
  - `test_complete_changes_status`
  - `test_reopen_changes_status`
  - `test_delete_removes_task`
  - `test_delete_raises_not_found`
  - `test_list_returns_empty_list_when_no_tasks`
  - `test_list_filters_by_status`
  - `test_list_filters_by_priority`
  - `test_list_sorts_by_due_date`
  - `test_list_sorts_by_priority_order`
  - `test_overdue_task_flagged_correctly` (edge case)
  - `test_invalid_input_rejected` (edge case)

**Done when:** All service tests pass.

---

### T-12 Write integration tests — CLI
**Requirements:** NFR-03, NFR-07  
**Effort:** ~1 hour

- [ ] `tests/test_cli.py` using `typer.testing.CliRunner`:
  - `test_create_command_success`
  - `test_create_command_missing_title` — stderr contains "Title is required."
  - `test_list_command_empty` — stdout contains "No tasks found."
  - `test_list_command_shows_tasks`
  - `test_list_command_filter_status`
  - `test_done_command`
  - `test_reopen_command`
  - `test_delete_command_with_yes_flag`
  - `test_delete_command_not_found` — stderr contains "not found"
  - `test_edit_command`
- [ ] Verify error messages use BU voice (active, plain English, specific)

**Done when:** All CLI tests pass.

---

### T-13 Write persistence test
**Requirements:** FR-09, NFR-03  
**Effort:** ~30 minutes

- [ ] `tests/test_persistence.py` — committed transactions against `tracker_test`:
  - `test_tasks_survive_connection_teardown` — insert, close connection, open new connection, verify tasks present
  - `test_schema_initialises_on_first_connection` — drop table, call `init_schema()`, verify `list()` returns `[]`
- [ ] `finally` block cleans up all committed rows

**Done when:** Persistence tests pass; test DB left in its original state.

---

## Phase 5 — Documentation and Pull Request

### T-14 Write README.md and CHANGELOG.md
**Requirements:** NFR-06  
**Skills:** `readme-changelog`, `bu-brand`  
**Effort:** ~1 hour

- [ ] README follows the mandatory header from `design.md §13`:
  - `<h1 align="center">📚 Study Task Tracker</h1>`
  - `<h2 align="center"><strong>A local CLI task tracker for BU students</strong></h2>`
  - Badge row 1: Version, Status (Alpha), Changelog
  - Badge row 2: Python 3.x, PostgreSQL 18, Typer
- [ ] Sections in order: Architecture (ASCII diagram), Features, Environment Variables, Package Structure, Testing, Reset
- [ ] Environment Variables section documents all five `TRACKER_DB_*` vars with types and defaults
- [ ] Testing section explains `TRACKER_DB_NAME=tracker_test` setup
- [ ] Reset section: `TRUNCATE tasks;` in psql, or `DROP TABLE tasks;`
- [ ] Known limitations from `design.md §14`
- [ ] Voice is BU brand: vibrant, direct, plain English, "you" over third person
- [ ] `CHANGELOG.md` with `### v0.1.0 - YYYY-MM-DD` entry

**Done when:** A person unfamiliar with the project can install, run, test, and reset using only the README.

---

### T-15 Final quality checks
**Requirements:** All  
**Effort:** ~30 minutes

- [ ] `ruff check src/ tests/` — zero errors (including `G004` for f-string logs)
- [ ] `ruff format --check src/ tests/` — zero diffs
- [ ] `pytest --cov=tracker --cov-report=term-missing` — all tests pass, coverage ≥80%
- [ ] `grep -r "password" src/` — confirm no hard-coded credentials
- [ ] `grep -r "get_secret_value" src/` — confirm password only accessed in `dsn()` method
- [ ] `.env` in `.gitignore` ✓; `.env.example` committed with no values ✓
- [ ] All five `TRACKER_DB_*` variables documented in README ✓
- [ ] All FR-01 – FR-10 traceable to at least one test

**Done when:** Zero linting errors, all tests pass, coverage ≥80%.

---

### T-16 Create pull request
**Requirements:** Spec §11–12  
**Effort:** ~30 minutes

PR must include:
- [ ] **Summary** — what the tracker does and what changed (BU voice)
- [ ] **Skills applied** — list all skills referenced during build
- [ ] **Requirements coverage** — FR-01 – FR-10, each marked satisfied
- [ ] **Test evidence** — paste `pytest` output with coverage summary
- [ ] **Screenshots or sample output** — `tracker list` with an overdue task, one error message
- [ ] **BU brand compliance note** — confirm colours and voice reviewed
- [ ] **Known limitations** — reference `design.md §14`

**Done when:** PR submitted; reviewer can verify all spec §11 acceptance criteria from the PR alone.

---

## Acceptance Criteria Checklist (spec §11)

- [ ] FR-01 – FR-10 all demonstrably implemented
- [ ] Application runs from one documented command in a clean environment
- [ ] Visible automated tests pass
- [ ] No prohibited architecture or cloud dependency introduced
- [ ] Data persists and can be reset using documented steps
- [ ] README states known limitations and design choices
- [ ] PR includes summary, test evidence, and sample output

---

## Task Summary

| Phase | Tasks | Key output |
|---|---|---|
| 1 — Foundation | T-01 – T-05 | pyproject.toml, Pydantic models, DB module (pydantic-settings + psycopg v3), repository, structlog |
| 2 — Service | T-06 – T-08 | Validation, state transitions, filter/sort, overdue |
| 3 — CLI | T-09 | Typer CLI with BU brand colours and voice |
| 4 — Tests | T-10 – T-13 | Repository + service unit tests, CLI integration, persistence |
| 5 — Docs & PR | T-14 – T-16 | README (readme-changelog format), CHANGELOG, quality checks, PR |

**Estimated effort: 14–18 hours.**
