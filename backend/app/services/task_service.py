from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import LibraryUser, Task, TaskMode, TaskType


class TaskService:
    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    def list_tasks(self) -> list[Task]:
        statement = select(Task).order_by(Task.id)
        return list(self._db.exec(statement).all())

    def get_task(self, task_id: int) -> Task:
        task = self._db.get(Task, task_id)
        if task is None:
            raise NotFoundError(f"task {task_id} not found")
        return task

    def create_task(
        self,
        *,
        name: str,
        task_type: TaskType,
        mode: TaskMode,
        library_user_id: int,
        enabled: bool = True,
        cron: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Task:
        if self._db.get(LibraryUser, library_user_id) is None:
            raise NotFoundError(f"library user {library_user_id} not found")
        if mode == TaskMode.SCHEDULED and not cron:
            raise ValidationAppError("scheduled tasks require a cron expression")
        task = Task(
            name=name,
            task_type=task_type,
            mode=mode,
            library_user_id=library_user_id,
            enabled=enabled,
            cron=cron,
            payload_json=json.dumps(payload) if payload else None,
        )
        self._db.add(task)
        self._db.commit()
        self._db.refresh(task)
        return task

    def update_task(self, task_id: int, **fields: Any) -> Task:
        task = self.get_task(task_id)
        for key, value in fields.items():
            if key == "payload":
                task.payload_json = json.dumps(value) if value else None
            elif hasattr(task, key) and value is not None:
                setattr(task, key, value)
        task.updated_at = datetime.now(timezone.utc)
        self._db.add(task)
        self._db.commit()
        self._db.refresh(task)
        return task

    def delete_task(self, task_id: int) -> None:
        task = self.get_task(task_id)
        self._db.delete(task)
        self._db.commit()

    @staticmethod
    def payload(task: Task) -> dict[str, Any]:
        if not task.payload_json:
            return {}
        try:
            value = json.loads(task.payload_json)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}
