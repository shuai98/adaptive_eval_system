from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser, get_current_teacher
from backend.core.observability import get_logger
from backend.db.session import get_db
from backend.services.async_task_service import async_task_service
from backend.services.teacher_service import (
    cancel_teacher_task as cancel_teacher_task_payload,
    create_reindex_task,
    get_class_insights as get_class_insights_payload,
    get_dashboard_stats as get_dashboard_stats_payload,
    get_my_docs as get_my_docs_payload,
    get_record_detail as get_record_detail_payload,
    get_student_profile as get_student_profile_payload,
    get_student_profiles as get_student_profiles_payload,
    list_teacher_tasks as list_teacher_tasks_payload,
    get_teacher_task as get_teacher_task_payload,
    index_document_runner,
    reindex_runner,
    upload_document as upload_document_payload,
)

router = APIRouter(prefix="/teacher", tags=["teacher"])
logger = get_logger("adaptive.api.teacher")


@router.post("/upload_doc")
async def upload_document(
    file: UploadFile = File(...),
    legacy_user_id: Optional[int] = Form(default=None, alias="user_id"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_teacher),
):
    _ = legacy_user_id
    return await upload_document_payload(file, db, current_user)


@router.get("/my_docs")
async def get_my_docs(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_teacher),
):
    return get_my_docs_payload(db, current_user)


@router.post("/reindex_kb")
async def reindex_knowledge_base(
    current_user: AuthenticatedUser = Depends(get_current_teacher),
):
    try:
        return create_reindex_task(current_user)
    except Exception as exc:
        logger.exception("reindex_task_failed teacher_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail=f"Failed to rebuild index: {exc}") from exc


@router.get("/tasks")
async def list_teacher_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    task_scope: Optional[str] = None,
    limit: int = 50,
    current_user: AuthenticatedUser = Depends(get_current_teacher),
):
    return list_teacher_tasks_payload(
        current_user,
        status=status,
        task_type=task_type,
        owner_id=owner_id,
        task_scope=task_scope,
        limit=limit,
    )


@router.get("/tasks/{task_id}")
async def get_teacher_task(
    task_id: int,
    current_user: AuthenticatedUser = Depends(get_current_teacher),
):
    return get_teacher_task_payload(task_id, current_user)


@router.delete("/tasks/{task_id}")
async def cancel_teacher_task(
    task_id: int,
    current_user: AuthenticatedUser = Depends(get_current_teacher),
):
    return cancel_teacher_task_payload(task_id, current_user)


@router.get("/dashboard_stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    teacher_user: AuthenticatedUser = Depends(get_current_teacher),
):
    _ = teacher_user
    try:
        return get_dashboard_stats_payload(db)
    except Exception:
        logger.exception("dashboard_stats_failed")
        return {"status": "error", "data": []}


@router.get("/class_insights")
async def get_class_insights(
    db: Session = Depends(get_db),
    teacher_user: AuthenticatedUser = Depends(get_current_teacher),
):
    _ = teacher_user
    return get_class_insights_payload(db)


@router.get("/student_profiles")
async def get_student_profiles(
    db: Session = Depends(get_db),
    teacher_user: AuthenticatedUser = Depends(get_current_teacher),
):
    _ = teacher_user
    return get_student_profiles_payload(db)


@router.get("/student_profile/{student_id}")
async def get_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
    teacher_user: AuthenticatedUser = Depends(get_current_teacher),
):
    _ = teacher_user
    return get_student_profile_payload(db, student_id)


@router.get("/record_detail/{record_id}")
async def get_record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    teacher_user: AuthenticatedUser = Depends(get_current_teacher),
):
    _ = teacher_user
    return get_record_detail_payload(db, record_id)


async_task_service.register_handler("index_document", index_document_runner)
async_task_service.register_handler("reindex_kb", reindex_runner)
