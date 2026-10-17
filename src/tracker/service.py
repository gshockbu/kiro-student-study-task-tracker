"""Service layer for the Study Task Tracker.

Holds business rules, input validation, and state transitions. The service
raises ``ValidationError`` and ``NotFoundError`` with plain-English, BU-voice
messages; the CLI translates these into user-facing output. This layer never
touches psycopg directly — all persistence goes through the repository.
"""

from __future__ import annotations

from datetime import date

from tracker.models import Priority, Status, Task
from tracker.repository import Repository


class ValidationError(Exception):
    """Raised when user input fails a business rule."""


class NotFoundError(Exception):
    """Raised when an operation targets a task id that does not exist."""


class _Unset:
    """Sentinel for an edit field that was not supplied.

    Distinguishes "leave unchanged" from an explicit ``None`` (which clears a
    nullable field such as ``description`` or ``due_date``).
    """


_UNSET = _Unset()


def _parse_due_date(value: str | date | None) -> date | None:
    """Normalise a due date to a ``date`` or ``None``.

    Args:
        value: A ``date``, an ISO ``YYYY-MM-DD`` string, or ``None``.

    Returns:
        The parsed date, or ``None`` when no due date is given.

    Raises:
        ValidationError: If a string is not a valid ISO date.
    """
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise ValidationError("Due date must be YYYY-MM-DD (e.g., 2026-12-31).") from e


def _parse_priority(value: str | Priority | None) -> Priority:
    """Normalise a priority to a ``Priority``, defaulting to medium.

    Args:
        value: A ``Priority``, one of ``"low"``, ``"medium"``, ``"high"``,
            or ``None``.

    Returns:
        The resolved priority.

    Raises:
        ValidationError: If a string is not a valid priority.
    """
    if value is None:
        return Priority.MEDIUM
    if isinstance(value, Priority):
        return value
    try:
        return Priority(value.lower())
    except ValueError as e:
        raise ValidationError("Priority must be low, medium, or high.") from e


class TaskService:
    """Business-rule layer sitting between the CLI and the repository."""

    def __init__(self, repo: Repository) -> None:
        """Store the repository used for persistence.

        Args:
            repo: The repository the service delegates reads and writes to.
        """
        self._repo = repo

    def create(
        self,
        title: str,
        description: str | None = None,
        due_date: str | date | None = None,
        priority: str | Priority | None = None,
    ) -> Task:
        """Validate inputs and create a new open task.

        Args:
            title: Task title. Required and non-empty after trimming.
            description: Optional longer note.
            due_date: Optional ISO ``YYYY-MM-DD`` string or ``date``.
            priority: ``"low"``, ``"medium"``, or ``"high"``. Defaults to
                medium.

        Returns:
            The persisted task, with its generated id.

        Raises:
            ValidationError: If the title is blank, the date is malformed, or
                the priority is not an allowed value.
        """
        clean_title = (title or "").strip()
        if not clean_title:
            raise ValidationError("Title is required.")

        parsed_due = _parse_due_date(due_date)
        parsed_priority = _parse_priority(priority)

        task = Task(
            title=clean_title,
            description=description,
            due_date=parsed_due,
            priority=parsed_priority,
            status=Status.OPEN,
        )
        return self._repo.add(task)

    def list(
        self,
        status: Status | None = None,
        priority: Priority | None = None,
        sort_by: str | None = None,
        descending: bool = False,
    ) -> list[Task]:
        """List tasks, optionally filtered and sorted.

        Returns an empty list — never raises — when no tasks match.

        Args:
            status: Restrict to this status when given.
            priority: Restrict to this priority when given.
            sort_by: ``"due"`` or ``"priority"``.
            descending: Sort descending when ``True``.

        Returns:
            Matching tasks, possibly empty.
        """
        return self._repo.list(
            status=status,
            priority=priority,
            sort_by=sort_by,
            descending=descending,
        )

    def get(self, task_id: int) -> Task:
        """Fetch a task or raise ``NotFoundError``.

        Args:
            task_id: The task's primary key.

        Returns:
            The task.

        Raises:
            NotFoundError: If no task has that id.
        """
        task = self._repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found.")
        return task

    def edit(
        self,
        task_id: int,
        title: str | _Unset = _UNSET,
        description: str | None | _Unset = _UNSET,
        due_date: str | date | None | _Unset = _UNSET,
        priority: str | Priority | _Unset = _UNSET,
    ) -> Task:
        """Update selected fields of an existing task.

        Only supplied fields change; omitted fields keep their current value.
        Passing ``None`` for ``description`` or ``due_date`` clears it.

        Args:
            task_id: The task to edit.
            title: New title. Must be non-empty when supplied.
            description: New description, or ``None`` to clear it.
            due_date: New ISO ``YYYY-MM-DD`` date or ``date``, or ``None`` to
                clear it.
            priority: New priority value.

        Returns:
            The updated task.

        Raises:
            NotFoundError: If no task has that id.
            ValidationError: If a supplied field fails its rule.
        """
        task = self.get(task_id)

        if not isinstance(title, _Unset):
            clean_title = (title or "").strip()
            if not clean_title:
                raise ValidationError("Title is required.")
            task.title = clean_title

        if not isinstance(description, _Unset):
            task.description = description

        if not isinstance(due_date, _Unset):
            task.due_date = _parse_due_date(due_date)

        if not isinstance(priority, _Unset):
            task.priority = _parse_priority(priority)

        return self._repo.update(task)

    def complete(self, task_id: int) -> Task:
        """Mark a task complete.

        Args:
            task_id: The task to complete.

        Returns:
            The updated task.

        Raises:
            NotFoundError: If no task has that id.
        """
        task = self.get(task_id)
        task.status = Status.COMPLETE
        return self._repo.update(task)

    def reopen(self, task_id: int) -> Task:
        """Reopen a completed task.

        Args:
            task_id: The task to reopen.

        Returns:
            The updated task.

        Raises:
            NotFoundError: If no task has that id.
        """
        task = self.get(task_id)
        task.status = Status.OPEN
        return self._repo.update(task)

    def delete(self, task_id: int) -> None:
        """Delete a task.

        Args:
            task_id: The task to delete.

        Raises:
            NotFoundError: If no task has that id.
        """
        self.get(task_id)
        self._repo.delete(task_id)
