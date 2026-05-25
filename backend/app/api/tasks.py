from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter()


def get_task_service(session: Session = Depends(get_session)) -> TaskService:
    return TaskService(session)


def _to_read(task) -> TaskRead:  # type: ignore[no-untyped-def]
    return TaskRead(
        id=task.id,
        name=task.name,
        task_type=task.task_type,
        mode=task.mode,
        enabled=task.enabled,
        cron=task.cron,
        library_user_id=task.library_user_id,
        payload=TaskService.payload(task) or None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("", response_model=list[TaskRead])
def list_tasks(service: TaskService = Depends(get_task_service)) -> list[TaskRead]:
    return [_to_read(task) for task in service.list_tasks()]


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    task = service.create_task(
        name=payload.name,
        task_type=payload.task_type,
        mode=payload.mode,
        library_user_id=payload.library_user_id,
        enabled=payload.enabled,
        cron=payload.cron,
        payload=payload.payload,
    )
    return _to_read(task)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskRead:
    return _to_read(service.get_task(task_id))


@router.put("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    data = payload.model_dump(exclude_unset=True)
    return _to_read(service.update_task(task_id, **data))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, service: TaskService = Depends(get_task_service)) -> Response:
    service.delete_task(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
