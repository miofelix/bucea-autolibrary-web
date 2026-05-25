from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.serializers import serialize_utc
from app.db.models import JobLogLevel, JobStatus, TaskMode, TaskType


class TaskRead(BaseModel):
    id: int
    name: str
    task_type: TaskType
    mode: TaskMode
    enabled: bool
    cron: str | None
    library_user_id: int
    payload: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, value: datetime | None) -> str | None:
        return serialize_utc(value)


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    task_type: TaskType
    mode: TaskMode = TaskMode.MANUAL
    enabled: bool = True
    cron: str | None = Field(default=None, max_length=128)
    library_user_id: int = Field(gt=0)
    payload: dict[str, Any] | None = None


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    task_type: TaskType | None = None
    mode: TaskMode | None = None
    enabled: bool | None = None
    cron: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] | None = None


class JobRead(BaseModel):
    id: int
    task_id: int | None
    task_type: TaskType
    library_user_id: int
    status: JobStatus
    summary: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("started_at", "finished_at", "created_at")
    def _ser_dt(self, value: datetime | None) -> str | None:
        return serialize_utc(value)


class JobRunRequest(BaseModel):
    task_id: int | None = Field(default=None, gt=0)
    task_type: TaskType | None = None
    library_user_id: int | None = Field(default=None, gt=0)
    payload: dict[str, Any] | None = None


class JobLogRead(BaseModel):
    id: int
    job_id: int
    level: JobLogLevel
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def _ser_dt(self, value: datetime | None) -> str | None:
        return serialize_utc(value)
