from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskType(str, Enum):
    RESERVE = "reserve"
    CHECKIN = "checkin"
    RENEW = "renew"
    CANCEL = "cancel"
    SEARCH = "search"
    STOP_USING = "stop_using"
    LEAVE = "leave"
    RESUME = "resume"


class TaskMode(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED_NEED_USER_CONFIRMATION = "blocked_need_user_confirmation"


class JobLogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


class LibraryUser(SQLModel, table=True):
    __tablename__ = "library_users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    password_encrypted: str = Field(min_length=1)
    enabled: bool = Field(default=True)
    notes: str | None = Field(default=None, max_length=512)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=128)
    task_type: TaskType = Field(index=True)
    mode: TaskMode = Field(default=TaskMode.MANUAL)
    enabled: bool = Field(default=True)
    cron: str | None = Field(default=None, max_length=128)
    library_user_id: int = Field(foreign_key="library_users.id", index=True)
    payload_json: str | None = Field(default=None, max_length=2048)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int | None = Field(default=None, foreign_key="tasks.id", index=True)
    task_type: TaskType
    library_user_id: int = Field(foreign_key="library_users.id", index=True)
    status: JobStatus = Field(default=JobStatus.PENDING, index=True)
    summary: str | None = Field(default=None, max_length=512)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)


class JobLog(SQLModel, table=True):
    __tablename__ = "job_logs"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    level: JobLogLevel = Field(default=JobLogLevel.INFO)
    message: str = Field(max_length=2048)
    created_at: datetime = Field(default_factory=utc_now)
