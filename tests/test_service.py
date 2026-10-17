"""Unit tests for the service layer (T-11)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tracker.models import Priority, Status
from tracker.service import NotFoundError, TaskService, ValidationError


def test_create_persists_task(service: TaskService) -> None:
    task = service.create(title="Read chapter 3")
    assert task.id is not None
    assert task.status == Status.OPEN


def test_create_raises_on_blank_title(service: TaskService) -> None:
    with pytest.raises(ValidationError, match="Title is required."):
        service.create(title="   ")


def test_create_raises_on_invalid_date(service: TaskService) -> None:
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        service.create(title="x", due_date="31-12-2026")


def test_create_raises_on_invalid_priority(service: TaskService) -> None:
    with pytest.raises(ValidationError, match="low, medium, or high"):
        service.create(title="x", priority="urgent")


def test_edit_updates_fields(service: TaskService) -> None:
    task = service.create(title="Original", priority="low")
    edited = service.edit(task.id, title="Edited", priority="high")
    assert edited.title == "Edited"
    assert edited.priority == Priority.HIGH


def test_edit_raises_not_found(service: TaskService) -> None:
    with pytest.raises(NotFoundError, match="Task 999999 not found."):
        service.edit(999999, title="x")


def test_complete_changes_status(service: TaskService) -> None:
    task = service.create(title="Finish me")
    assert service.complete(task.id).status == Status.COMPLETE


def test_reopen_changes_status(service: TaskService) -> None:
    task = service.create(title="Reopen me")
    service.complete(task.id)
    assert service.reopen(task.id).status == Status.OPEN


def test_delete_removes_task(service: TaskService) -> None:
    task = service.create(title="Delete me")
    service.delete(task.id)
    assert service.list() == []


def test_delete_raises_not_found(service: TaskService) -> None:
    with pytest.raises(NotFoundError, match="Task 999999 not found."):
        service.delete(999999)


def test_list_returns_empty_list_when_no_tasks(
    service: TaskService,
) -> None:
    assert service.list() == []


def test_list_filters_by_status(service: TaskService) -> None:
    service.create(title="Open one")
    done = service.create(title="Done one")
    service.complete(done.id)
    assert len(service.list(status=Status.OPEN)) == 1


def test_list_filters_by_priority(service: TaskService) -> None:
    service.create(title="High", priority="high")
    service.create(title="Low", priority="low")
    assert len(service.list(priority=Priority.HIGH)) == 1


def test_list_sorts_by_due_date(service: TaskService) -> None:
    service.create(title="Later", due_date="2026-12-31")
    service.create(title="Sooner", due_date="2026-01-01")
    titles = [t.title for t in service.list(sort_by="due")]
    assert titles.index("Sooner") < titles.index("Later")


def test_list_sorts_by_priority_order(service: TaskService) -> None:
    service.create(title="Low", priority="low")
    service.create(title="High", priority="high")
    desc = service.list(sort_by="priority", descending=True)
    assert desc[0].priority == Priority.HIGH


def test_overdue_task_flagged_correctly(service: TaskService) -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    overdue = service.create(title="Past due", due_date=yesterday)
    future = service.create(title="Future", due_date=tomorrow)
    undated = service.create(title="Undated")

    done = service.create(title="Past done", due_date=yesterday)
    service.complete(done.id)

    by_title = {t.title: t for t in service.list()}
    assert by_title["Past due"].is_overdue is True
    assert by_title["Future"].is_overdue is False
    assert by_title["Undated"].is_overdue is False
    assert by_title["Past done"].is_overdue is False

    assert overdue.is_overdue is True
    assert future.is_overdue is False
    assert undated.is_overdue is False


def test_invalid_input_rejected(service: TaskService) -> None:
    with pytest.raises(ValidationError):
        service.create(title="")
    with pytest.raises(ValidationError):
        service.edit(service.create(title="valid").id, due_date="not-a-date")
