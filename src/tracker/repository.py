"""Repository layer for the Study Task Tracker.

Translates between ``Task`` models and the ``tasks`` table using psycopg v3.
Every query uses ``%s`` placeholders — no value is ever interpolated into SQL
text. This layer holds no business logic; validation and state rules live in
the service layer.
"""

from __future__ import annotations

import psycopg

from tracker.models import Priority, Status, Task

# Columns selected for every read, in a fixed order matching ``_row_to_task``.
_COLUMNS = "id, title, description, due_date, priority, status, created_at, updated_at"

# Allowlist mapping caller-facing sort keys to trusted SQL fragments. Column
# names cannot be parameterised, so sorting is restricted to these fragments
# to keep the query injection-safe (SEC-02).
_SORT_FRAGMENTS: dict[str, str] = {
    "due": "due_date",
    "priority": (
        "CASE priority WHEN 'high' THEN 3 WHEN 'medium' THEN 2 "
        "WHEN 'low' THEN 1 ELSE 0 END"
    ),
}


def _row_to_task(row: tuple) -> Task:
    """Build a ``Task`` from a result row in ``_COLUMNS`` order."""
    return Task(
        id=row[0],
        title=row[1],
        description=row[2],
        due_date=row[3],
        priority=Priority(row[4]),
        status=Status(row[5]),
        created_at=row[6],
        updated_at=row[7],
    )


class Repository:
    """Data-access layer for ``Task`` rows backed by a psycopg connection."""

    def __init__(self, conn: psycopg.Connection) -> None:
        """Store the connection used for all queries.

        Args:
            conn: An open psycopg connection. The repository does not open or
                close it.
        """
        self._conn = conn

    def add(self, task: Task) -> Task:
        """Insert a task and return it with its generated id.

        Args:
            task: The task to persist. Its ``id`` is ignored on insert.

        Returns:
            The task with ``id``, ``created_at``, and ``updated_at`` set from
            the database.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks "
                "(title, description, due_date, priority, status) "
                "VALUES (%s, %s, %s, %s, %s) "
                f"RETURNING {_COLUMNS}",
                (
                    task.title,
                    task.description,
                    task.due_date,
                    task.priority.value,
                    task.status.value,
                ),
            )
            row = cur.fetchone()
        self._conn.commit()
        return _row_to_task(row)

    def get(self, task_id: int) -> Task | None:
        """Fetch a task by id.

        Args:
            task_id: The task's primary key.

        Returns:
            The matching task, or ``None`` if no row has that id.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUMNS} FROM tasks WHERE id = %s",
                (task_id,),
            )
            row = cur.fetchone()
        return _row_to_task(row) if row is not None else None

    def list(
        self,
        status: Status | None = None,
        priority: Priority | None = None,
        sort_by: str | None = None,
        descending: bool = False,
    ) -> list[Task]:
        """List tasks with optional filtering and sorting.

        Args:
            status: If given, return only tasks with this status.
            priority: If given, return only tasks with this priority.
            sort_by: ``"due"`` or ``"priority"``. Any other value sorts by id.
            descending: Sort descending when ``True``.

        Returns:
            Matching tasks, possibly empty.
        """
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value)
        if priority is not None:
            clauses.append("priority = %s")
            params.append(priority.value)

        sql = f"SELECT {_COLUMNS} FROM tasks"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        order_expr = _SORT_FRAGMENTS.get(sort_by or "", "id")
        direction = "DESC" if descending else "ASC"
        # NULLS LAST keeps undated tasks at the end of a due-date sort (asc).
        nulls = " NULLS LAST" if sort_by == "due" and not descending else ""
        sql += f" ORDER BY {order_expr} {direction}{nulls}, id ASC"

        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_task(row) for row in rows]

    def update(self, task: Task) -> Task:
        """Persist changes to an existing task.

        Args:
            task: The task to update. Must have a non-``None`` ``id``.

        Returns:
            The updated task as stored, including a refreshed ``updated_at``.

        Raises:
            ValueError: If ``task.id`` is ``None``.
        """
        if task.id is None:
            raise ValueError("Cannot update a task without an id.")
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE tasks SET "
                "title = %s, description = %s, due_date = %s, "
                "priority = %s, status = %s, updated_at = now() "
                "WHERE id = %s "
                f"RETURNING {_COLUMNS}",
                (
                    task.title,
                    task.description,
                    task.due_date,
                    task.priority.value,
                    task.status.value,
                    task.id,
                ),
            )
            row = cur.fetchone()
        self._conn.commit()
        return _row_to_task(row)

    def delete(self, task_id: int) -> bool:
        """Delete a task by id.

        Args:
            task_id: The task's primary key.

        Returns:
            ``True`` if a row was deleted, ``False`` if no row had that id.
        """
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            deleted = cur.rowcount
        self._conn.commit()
        return deleted > 0
