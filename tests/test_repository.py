"""Unit tests for the repository layer (T-10)."""

from __future__ import annotations

from datetime import date

from tracker.models import Priority, Status, Task
from tracker.repository import Repository


def _task(title: str, **kwargs: object) -> Task:
    """Build a Task with sensible defaults for tests."""
    return Task(title=title, **kwargs)


def test_add_returns_task_with_id(repo: Repository) -> None:
    added = repo.add(_task("Read chapter 3"))
    assert added.id is not None
    assert added.title == "Read chapter 3"
    assert added.created_at is not None


def test_get_returns_none_for_missing_id(repo: Repository) -> None:
    assert repo.get(999999) is None


def test_list_returns_all_tasks(repo: Repository) -> None:
    repo.add(_task("One"))
    repo.add(_task("Two"))
    assert len(repo.list()) == 2


def test_list_filter_by_status(repo: Repository) -> None:
    repo.add(_task("Open one"))
    done = repo.add(_task("Done one"))
    done.status = Status.COMPLETE
    repo.update(done)

    assert len(repo.list(status=Status.OPEN)) == 1
    assert len(repo.list(status=Status.COMPLETE)) == 1


def test_list_filter_by_priority(repo: Repository) -> None:
    repo.add(_task("High", priority=Priority.HIGH))
    repo.add(_task("Low", priority=Priority.LOW))
    assert len(repo.list(priority=Priority.HIGH)) == 1


def test_list_sort_by_due_date(repo: Repository) -> None:
    repo.add(_task("Later", due_date=date(2026, 12, 31)))
    repo.add(_task("Sooner", due_date=date(2026, 1, 1)))
    repo.add(_task("Undated"))

    titles = [t.title for t in repo.list(sort_by="due")]
    assert titles == ["Sooner", "Later", "Undated"]


def test_list_sort_by_priority(repo: Repository) -> None:
    repo.add(_task("Low", priority=Priority.LOW))
    repo.add(_task("High", priority=Priority.HIGH))
    repo.add(_task("Medium", priority=Priority.MEDIUM))

    desc = repo.list(sort_by="priority", descending=True)
    assert [t.priority for t in desc] == [
        Priority.HIGH,
        Priority.MEDIUM,
        Priority.LOW,
    ]


def test_update_persists_changes(repo: Repository) -> None:
    task = repo.add(_task("Original", priority=Priority.LOW))
    task.title = "Changed"
    task.priority = Priority.HIGH
    repo.update(task)

    reloaded = repo.get(task.id)
    assert reloaded.title == "Changed"
    assert reloaded.priority == Priority.HIGH


def test_delete_removes_task(repo: Repository) -> None:
    task = repo.add(_task("Delete me"))
    assert repo.delete(task.id) is True
    assert repo.get(task.id) is None


def test_delete_returns_false_for_missing_id(repo: Repository) -> None:
    assert repo.delete(999999) is False
