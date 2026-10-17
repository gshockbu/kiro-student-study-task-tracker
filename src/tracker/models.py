"""Domain models for the Study Task Tracker.

Defines the ``Task`` entity and its ``Priority`` and ``Status`` enumerations
using Pydantic v2. Validation (such as the title length constraint) runs at
construction time, before a task reaches the service or repository layers.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class Priority(str, Enum):
    """Task priority levels, ordered low to high."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Status(str, Enum):
    """Lifecycle status of a task."""

    OPEN = "open"
    COMPLETE = "complete"


class Task(BaseModel):
    """A single study task.

    Attributes:
        id: Database primary key. ``None`` until the task is persisted.
        title: Short task name. Required, 1 to 200 characters.
        description: Optional longer note about the task.
        due_date: Optional ISO 8601 date the task is due.
        priority: Task priority. Defaults to ``Priority.MEDIUM``.
        status: Lifecycle status. Defaults to ``Status.OPEN``.
        created_at: Timestamp set by the database on insert.
        updated_at: Timestamp updated by the database on every write.
    """

    id: int | None = None
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    due_date: date | None = None
    priority: Priority = Priority.MEDIUM
    status: Status = Status.OPEN
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"populate_by_name": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_overdue(self) -> bool:
        """Whether the task is past due and still open.

        Computed at read time from ``due_date`` and ``status``: a task is
        overdue when it has a due date earlier than today and is still open.
        """
        return (
            self.due_date is not None
            and self.status == Status.OPEN
            and self.due_date < date.today()
        )
