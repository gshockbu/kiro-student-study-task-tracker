"""Command-line interface for the Study Task Tracker.

A Typer app exposing create, list, edit, done, reopen, and delete commands.
Output follows Boston University brand standards: active voice, plain English,
and BU Red reserved for errors and overdue markers. All task output goes to
stdout; errors go to stderr with exit code 1.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager

import structlog
import typer

from tracker.db import ConnectionSettings, get_connection, init_schema
from tracker.logging_config import configure_logging
from tracker.models import Priority, Status, Task
from tracker.repository import Repository
from tracker.service import NotFoundError, TaskService, ValidationError

app = typer.Typer(
    help="Track your study tasks from the command line.",
    add_completion=False,
    no_args_is_help=True,
)

_BU_RED = "\033[31m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

log = structlog.get_logger("tracker")


def _supports_color() -> bool:
    """Return whether stdout is an interactive terminal that can show ANSI."""
    return sys.stdout.isatty()


def _red(text: str) -> str:
    """Wrap text in BU Red when the terminal supports color."""
    return f"{_BU_RED}{text}{_RESET}" if _supports_color() else text


def _bold(text: str) -> str:
    """Wrap text in bold when the terminal supports color."""
    return f"{_BOLD}{text}{_RESET}" if _supports_color() else text


def _fail(message: str) -> None:
    """Print a BU-voice error to stderr in BU Red and exit with code 1.

    Args:
        message: The error text, already phrased in plain English.
    """
    print(_red(f"Error: {message}"), file=sys.stderr)
    raise typer.Exit(code=1)


@contextmanager
def _service_session() -> Iterator[TaskService]:
    """Yield a service with a live connection, closing it on exit.

    Configures logging, opens the database connection, and ensures the schema
    exists. On a connection failure, logs the error and exits with code 1
    (OBS-05). The connection is always closed when the ``with`` block ends,
    so no connection leaks across commands.

    Yields:
        A ready-to-use ``TaskService``.
    """
    configure_logging()
    settings = ConnectionSettings()
    try:
        conn = get_connection(settings)
    except RuntimeError as e:
        log.error(
            "db_connection_failed",
            host=settings.host,
            port=settings.port,
            dbname=settings.dbname,
        )
        _fail(str(e))
    try:
        init_schema(conn)
        log.info("startup", host=settings.host, dbname=settings.dbname)
        yield TaskService(Repository(conn))
    finally:
        conn.close()


def _format_task(task: Task) -> str:
    """Render a single task as one BU-branded line for the list view.

    Args:
        task: The task to render.

    Returns:
        A formatted line. Overdue tasks are prefixed with a BU Red marker.
    """
    due = task.due_date.isoformat() if task.due_date else "no due date"
    marker = _red("[OVERDUE] ") if task.is_overdue else ""
    return (
        f"{marker}{_bold(f'#{task.id} {task.title}')} "
        f"— {task.priority.value}, due {due}, {task.status.value}"
    )


@app.command()
def create(
    title: str = typer.Option("", "--title", help="Task title (required)."),
    description: str = typer.Option(
        None, "--description", help="Optional longer note."
    ),
    due: str = typer.Option(None, "--due", help="Due date as YYYY-MM-DD."),
    priority: str = typer.Option("medium", "--priority", help="low, medium, or high."),
) -> None:
    """Create a task."""
    with _service_session() as service:
        try:
            task = service.create(
                title=title,
                description=description,
                due_date=due,
                priority=priority,
            )
        except ValidationError as e:
            _fail(str(e))
        print(f"Created task #{task.id}: {task.title}.")


@app.command(name="list")
def list_tasks(
    status: str = typer.Option(None, "--status", help="Filter by open or complete."),
    priority: str = typer.Option(
        None, "--priority", help="Filter by low, medium, or high."
    ),
    sort: str = typer.Option(None, "--sort", help="Sort by due or priority."),
    desc: bool = typer.Option(False, "--desc", help="Sort in descending order."),
) -> None:
    """List tasks, with optional filters and sorting."""
    with _service_session() as service:
        try:
            status_val = Status(status) if status else None
            priority_val = Priority(priority) if priority else None
        except ValueError:
            _fail("Filter must use a valid status or priority value.")

        tasks = service.list(
            status=status_val,
            priority=priority_val,
            sort_by=sort,
            descending=desc,
        )
        if not tasks:
            print("No tasks found.")
            return
        for task in tasks:
            print(_format_task(task))


@app.command()
def edit(
    task_id: int = typer.Argument(..., help="The task's id."),
    title: str = typer.Option(None, "--title", help="New title."),
    description: str = typer.Option(None, "--description", help="New description."),
    due: str = typer.Option(None, "--due", help="New due date YYYY-MM-DD."),
    priority: str = typer.Option(None, "--priority", help="New priority."),
) -> None:
    """Edit an existing task."""
    with _service_session() as service:
        changes: dict[str, object] = {}
        if title is not None:
            changes["title"] = title
        if description is not None:
            changes["description"] = description
        if due is not None:
            changes["due_date"] = due
        if priority is not None:
            changes["priority"] = priority

        try:
            task = service.edit(task_id, **changes)
        except (NotFoundError, ValidationError) as e:
            _fail(str(e))
        print(f"Updated task #{task.id}.")


@app.command()
def done(
    task_id: int = typer.Argument(..., help="The task's id."),
) -> None:
    """Mark a task complete."""
    with _service_session() as service:
        try:
            task = service.complete(task_id)
        except NotFoundError as e:
            _fail(str(e))
        print(f"Completed task #{task.id}: {task.title}.")


@app.command()
def reopen(
    task_id: int = typer.Argument(..., help="The task's id."),
) -> None:
    """Reopen a completed task."""
    with _service_session() as service:
        try:
            task = service.reopen(task_id)
        except NotFoundError as e:
            _fail(str(e))
        print(f"Reopened task #{task.id}: {task.title}.")


@app.command()
def delete(
    task_id: int = typer.Argument(..., help="The task's id."),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Delete a task after confirmation."""
    with _service_session() as service:
        try:
            task = service.get(task_id)
        except NotFoundError as e:
            _fail(str(e))

        if not yes:
            confirmed = typer.confirm(
                f'Delete task {task.id} "{task.title}"?', default=False
            )
            if not confirmed:
                print("Cancelled. No task was deleted.")
                return

        try:
            service.delete(task_id)
        except NotFoundError as e:
            _fail(str(e))
        print(f"Deleted task #{task_id}.")


if __name__ == "__main__":
    app()
