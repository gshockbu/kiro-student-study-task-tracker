# Requirements — Student Study Task Tracker

Derived from: `AI_Student_Project_Specification_SMALL.docx`, sections 5–10.
Skills applied: `standard-libraries`, `pyproject-toml`, `python-project-structure`, `bu-brand`, `readme-changelog`.

---

## Functional Requirements

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-01 | Create a task with **title** (required), **description** (optional), **due date** (optional), **priority** (Low / Medium / High), and **status** (Open). | Task is persisted and appears in the task list immediately after creation. Title is required; creation is rejected if title is blank. |
| FR-02 | List all tasks in a readable view. | All persisted tasks are displayed with their title, due date, priority, and status. Output uses BU brand colours where the terminal supports ANSI (BU Red `#CC0000` for overdue/errors, Black `#2D2926` for body). |
| FR-03 | Edit an existing task. | Any field of an existing task (title, description, due date, priority) can be changed and the updated value is persisted. |
| FR-04 | Mark a task complete and reopen it. | Status transitions: Open → Complete, Complete → Open. Both directions work and are persisted. |
| FR-05 | Delete a task after explicit confirmation. | Deletion requires a second confirmation step (`--yes` flag or "y/n" prompt). A deleted task does not appear in any subsequent list. |
| FR-06 | Filter tasks by status and priority. | The list view can be narrowed to a single status value (Open / Complete) and/or a single priority value (Low / Medium / High). Combinations are supported. |
| FR-07 | Sort tasks by due date and priority. | The list view can be ordered ascending or descending by due date, and by priority (High → Medium → Low or reversed). |
| FR-08 | Validate required fields and reject malformed input. | Blank title → validation error with message. Invalid date format → validation error with expected format. Priority or status value not in allowed set → validation error. Errors are shown in plain English; no partial write occurs. |
| FR-09 | Persist data to a local PostgreSQL database so tasks survive application restart. | Tasks written in one session are present when the application is started again. The database connection is configured via environment variables (see Database Connection Configuration). |
| FR-10 | Show clear empty, validation-error, and not-found states. | Empty list → "No tasks found." message. Validation failure → specific field-level message in plain English. Edit/delete of a non-existent ID → "Task {id} not found." message. All messages follow BU voice: direct, plain English, active voice. |

---

## Nonfunctional Requirements

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| NFR-01 | **Single start command.** The application must start from one documented command. | `README.md` documents exactly one command; it works in a clean virtual environment with `uv sync`. |
| NFR-02 | **Documented dependencies only.** A clean install requires only the packages listed in `pyproject.toml`. A running local PostgreSQL instance is a documented prerequisite. | `uv sync --extra dev` in a fresh venv, with a local PostgreSQL instance configured per README, produces a working application with no additional steps. |
| NFR-03 | **Automated test coverage.** Core behavior must be covered by automated tests. | Unit tests exist for create, update, complete/reopen, delete, filtering, sorting, and validation. A persistence test proves tasks survive a repository teardown and reinitialisation against a test database. At least one overdue-task edge case and one invalid-input test are present. All tests pass from `pytest` (single command). |
| NFR-04 | **Understandable error messages.** The UI/CLI must provide clear, plain-English error messages in BU voice. | Every validation failure and not-found condition shows a human-readable message. Messages are direct and active ("Task 5 not found." not "Error: NotFoundError"). No raw Python tracebacks exposed to the user under normal operation. |
| NFR-05 | **No remote data collection.** No secrets, credentials, analytics beacons, or external API calls are permitted. | Static analysis and code review confirm no network calls, no API keys, no telemetry. |
| NFR-06 | **README completeness.** The repository must include a README following the `readme-changelog` skill standard. | README uses the mandatory header (h1 + emoji, h2 + description, badge rows). Sections in order: Architecture, Features, Environment Variables, Package Structure, Testing, Reset. Known limitations and design choices are stated. |
| NFR-07 | **BU brand compliance in all UI output.** The CLI output and any documentation must follow BU brand standards. | BU Red (`#CC0000`) used for overdue tasks, errors, and warnings (ANSI where supported). BentonSans or monospace fallback for terminal. Voice is vibrant, direct, plain English. No all-caps emphasis. Oxford comma in multi-item lists. |

---

## Architecture Constraints (Scope Ceiling)

| Constraint | Allowed | Prohibited |
|------------|---------|-----------|
| Process topology | One application process | Microservices, workers, daemons |
| Persistence | **Local PostgreSQL instance** | Cloud-hosted databases (RDS, Supabase, etc.), remote stores, caches |
| Interface | CLI (primary), simple local web app | Anything requiring a cloud account to run |
| Authentication | None for the application — single local user assumed | Auth providers, sessions, JWT |
| Database authentication | Local PostgreSQL credentials via environment variables | Hard-coded credentials, secrets committed to version control |
| External services | None | Queues, service meshes, serverless, LLMs, vector stores |
| Infrastructure | None beyond a local PostgreSQL installation | Kubernetes, Docker (for deployment), cloud accounts |

---

## Security and Privacy Requirements

| ID | Requirement |
|----|-------------|
| SEC-01 | Use only synthetic or user-entered study-task data. No real student data. |
| SEC-02 | Validate all input before persistence. Use parameterised queries exclusively — no string interpolation in SQL. Prevent command injection and unsafe dynamic execution. |
| SEC-03 | Do not log unnecessary task content. Log only startup, errors, and persistence failures. Never log connection strings or passwords. |
| SEC-04 | Pin all dependencies with lower-bound versions in `pyproject.toml` (e.g. `psycopg>=3.1.0`). Use `uv.lock` for reproducibility. |
| SEC-05 | Database credentials are supplied via environment variables (`TRACKER_DB_HOST`, `TRACKER_DB_PORT`, `TRACKER_DB_NAME`, `TRACKER_DB_USER`, `TRACKER_DB_PASSWORD`). No credentials are committed to version control. A `.env.example` file documents required variables without values. |
| SEC-06 | The `.env` file containing real credentials must be listed in `.gitignore` and never committed. |

---

## Observability Requirements

| ID | Requirement |
|----|-------------|
| OBS-01 | Log application startup with DB host and database name (never password). Use `structlog` with JSON in production, ConsoleRenderer in dev (TTY detection). |
| OBS-02 | Log persistence/connection errors (connection refused, authentication failure, query error) at ERROR level with host/port/dbname context. |
| OBS-03 | Log unhandled exceptions before exiting. |
| OBS-04 | No external telemetry, metrics, or tracing stack. Logs go to stderr only. |
| OBS-05 | Log a clear error and exit with code 1 when the database connection cannot be established at startup. |

---

## Library Standards (from `standard-libraries` skill)

| Concern | Library | Version |
|---|---|---|
| Data validation | `pydantic` | `>=2.5.0` |
| Settings / env vars | `pydantic-settings` | `>=2.1.0` |
| PostgreSQL driver | `psycopg[binary]` | `>=3.1.0` |
| CLI framework | `typer` | `>=0.12.0` |
| Structured logging | `structlog` | `>=25.0.0` |
| Testing | `pytest` | `>=8.0.0` |
| Test mocking | `pytest-mock` | `>=3.12.0` |
| Test coverage | `pytest-cov` | `>=4.1.0` |
| Linting + formatting | `ruff` | `>=0.1.0` |

Libraries explicitly avoided: `psycopg2` (legacy), `black` (use `ruff format`), `flake8` (use `ruff check`), `isort` (use `ruff check`), stdlib `logging` as primary (use `structlog`).

---

## Database Connection Configuration

The application resolves the PostgreSQL connection from environment variables loaded via `pydantic-settings`. All variables must be set before running the application or its tests.

| Variable | Default | Description |
|---|---|---|
| `TRACKER_DB_HOST` | `localhost` | PostgreSQL server hostname |
| `TRACKER_DB_PORT` | `5432` | PostgreSQL server port |
| `TRACKER_DB_NAME` | `tracker` | Database name |
| `TRACKER_DB_USER` | _(required)_ | PostgreSQL username |
| `TRACKER_DB_PASSWORD` | _(required)_ | PostgreSQL password (SecretStr) |

A `.env.example` file must be present in the repository root. Developers copy it to `.env` and supply their local credentials. The `.env` file is listed in `.gitignore`.

---

## BU Brand Requirements (from `bu-brand` skill)

All user-facing output must follow BU brand standards:

| Element | Standard |
|---|---|
| Primary colour (errors, overdue, warnings) | BU Red `#CC0000` via ANSI escape (with TTY check) |
| Body text colour | Black `#2D2926` or default terminal |
| Font (terminal) | Monospace default; BentonSans in any HTML output |
| Voice | Vibrant, direct, plain English, active voice |
| Error messages | Direct and specific ("Task 5 not found." not "An error occurred.") |
| Lists | Oxford comma for 3+ items |
| Capitalisation | Title case for headings only; sentence case for body |
| All-caps | Never used for emphasis |

---

## Stretch Goals (optional, post-acceptance)

| ID | Goal |
|----|------|
| STR-01 | Import/export tasks using a documented local format (e.g., CSV). |
| STR-02 | Show a "due soon" summary (tasks due within the next 3 days), styled with BU brand colours. |
| STR-03 | Lightweight accessibility improvements to any UI elements. |

---

## Traceability

| Source | Requirements |
|---|---|
| Spec §5 Functional Requirements | FR-01 – FR-10 |
| Spec §6 Nonfunctional Requirements | NFR-01 – NFR-07 |
| Spec §7 Architecture Constraints | Scope Ceiling table |
| Spec §8 Security and Privacy | SEC-01 – SEC-06 |
| Spec §9 Observability | OBS-01 – OBS-05 |
| Spec §10 Testing Requirements | NFR-03 (expanded in tasks.md) |
| Spec §15 Stretch Goals | STR-01 – STR-03 |
| `standard-libraries` skill | Library Standards table |
| `bu-brand` skill | NFR-07, FR-02, FR-10, BU Brand Requirements table |
| `pyproject-toml` skill | SEC-04, NFR-02 (version pinning, dev extras) |
| `python-project-structure` skill | NFR-06 (structure, .gitignore) |
| `readme-changelog` skill | NFR-06 (README format) |
