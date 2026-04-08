from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser, get_current_student
from backend.core.observability import get_logger
from backend.db.session import get_db
from backend.schemas.student import GradeRequest, QuestionRequest
from backend.services.async_task_service import async_task_service
from backend.services.student_service import (
    cancel_student_task as cancel_student_task_payload,
    create_generate_question_task,
    create_grade_answer_task,
    ensure_student_access,
    generate_question as generate_question_payload,
    generate_question_task_runner,
    get_adaptive_stats as get_adaptive_stats_payload,
    get_history as get_history_payload,
    get_history_detail as get_history_detail_payload,
    get_learning_dashboard as get_learning_dashboard_payload,
    get_student_task as get_student_task_payload,
    get_wrong_questions as get_wrong_questions_payload,
    grade_answer as grade_answer_payload,
    grade_answer_task_runner,
    stream_generate_question,
)

router = APIRouter(prefix="/student", tags=["student"])
logger = get_logger("adaptive.api.student")


@router.post("/generate_question")
async def generate_question(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    try:
        student_id = ensure_student_access(request.student_id, current_user)
        request.student_id = student_id
        return await generate_question_payload(db, student_id, request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate_question_failed student_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generate_question_task")
async def generate_question_task(
    request: QuestionRequest,
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    try:
        student_id = ensure_student_access(request.student_id, current_user)
        return create_generate_question_task(request, student_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate_question_task_failed student_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generate_question_stream")
async def generate_question_stream(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    try:
        student_id = ensure_student_access(request.student_id, current_user)
        request.student_id = student_id
        return await stream_generate_question(db, student_id, request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate_question_stream_failed student_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/grade_answer")
async def grade_answer(
    request: GradeRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    try:
        student_id = ensure_student_access(request.student_id, current_user)
        request.student_id = student_id
        return await grade_answer_payload(db, student_id, request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("grade_answer_failed student_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/grade_answer_task")
async def grade_answer_task(
    request: GradeRequest,
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    try:
        student_id = ensure_student_access(request.student_id, current_user)
        return create_grade_answer_task(request, student_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("grade_answer_task_failed student_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/tasks/{task_id}")
async def get_student_task(
    task_id: int,
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    return get_student_task_payload(task_id, current_user)


@router.delete("/tasks/{task_id}")
async def cancel_student_task(
    task_id: int,
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    return cancel_student_task_payload(task_id, current_user)


@router.get("/history")
async def get_history(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    return get_history_payload(db, current_user.id)


@router.get("/history/{record_id}")
async def get_history_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    return get_history_detail_payload(db, current_user.id, record_id)


@router.get("/learning_dashboard")
async def get_learning_dashboard(
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    return get_learning_dashboard_payload(db, current_user.id, keyword)


@router.get("/wrong_questions")
async def get_wrong_questions(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    return get_wrong_questions_payload(db, current_user.id)


@router.get("/adaptive_stats")
async def get_adaptive_stats(
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_student),
):
    return get_adaptive_stats_payload(db, current_user.id, keyword)


async_task_service.register_handler("generate_question", generate_question_task_runner)
async_task_service.register_handler("grade_answer", grade_answer_task_runner)
