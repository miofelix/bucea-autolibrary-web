from collections.abc import Generator
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

_engine = None
_engine_url = ""


def ensure_sqlite_parent_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return
    database_path = make_url(database_url).database
    if not database_path or database_path == ":memory:":
        return
    Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def get_engine():
    global _engine, _engine_url
    settings = get_settings()
    if _engine is None or _engine_url != settings.database_url:
        ensure_sqlite_parent_dir(settings.database_url)
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        _engine = create_engine(settings.database_url, connect_args=connect_args)
        _engine_url = settings.database_url
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
