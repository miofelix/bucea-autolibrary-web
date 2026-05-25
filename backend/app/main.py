import os
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.api import health, jobs, library, logs, settings as settings_api, tasks, users
from app.core.errors import AppError, app_error_handler
from app.db.session import get_engine, init_db
from app.services.job_runner import JobScheduler


@contextmanager
def _session_factory():
    with Session(get_engine()) as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = JobScheduler(session_factory=_session_factory)
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AutoLibrary API",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(health.router)
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(library.router, prefix="/api/library", tags=["library"])
    app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
    app.include_router(logs.router, prefix="/api/jobs", tags=["logs"])
    app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
    _register_static_frontend(app)
    return app


def _register_static_frontend(app: FastAPI) -> None:
    static_dir = Path(os.getenv("AUTO_LIBRARY_STATIC_DIR", "/app/static")).resolve()
    index_file = static_dir / "index.html"
    if not index_file.is_file():
        return

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404)

        requested_path = (static_dir / full_path).resolve()
        try:
            requested_path.relative_to(static_dir)
        except ValueError as exc:
            raise HTTPException(status_code=404) from exc

        if requested_path.is_file():
            return FileResponse(requested_path)
        return FileResponse(index_file)


app = create_app()
