# Changelog

### v0.1.0 - 2026-10-16
- Initial release.
- Create, list, edit, complete, reopen, and delete study tasks from the
  command line.
- Filter tasks by status and priority, and sort by due date or priority.
- Flag overdue tasks (past due and still open) in the list view.
- Validate title, due date, and priority with plain-English error messages.
- Persist tasks to a local PostgreSQL database via psycopg v3, with connection
  settings loaded from environment variables and the password held as a
  `SecretStr`.
- Structured logging through structlog, written to stderr.
