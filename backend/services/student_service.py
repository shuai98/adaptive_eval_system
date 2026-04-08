import asyncio
import json
import time
from typing import Any, Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser
from backend.core.config import settings
from backend.db.session import SessionLocal
from backend.models.tables import ExamRecord, QuestionHistory
from backend.schemas.student import DEFAULT_DIFFICULTY, GradeRequest, QuestionRequest
from backend.services.async_task_service import async_task_service
from backend.services.learning_analytics_service import learning_analytics_service
from backend.services.llm_service import llm_service
from backend.services.rag_service import rag_service


def normalize_question_payload(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "question": content,
                "options": None,
                "answer": "",
                "analysis": "",
            }
    return {"question": "", "options": None, "answer": "", "analysis": ""}


def ensure_student_access(request_student_id: Optional[int], current_user: AuthenticatedUser) -> int:
    if request_student_id is not None and request_student_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only access your own records.")
    return current_user.id


def resolve_difficulty(db: Session, student_id: int, request: QuestionRequest) -> str:
    if request.mode == "adaptive":
        return learning_analytics_service.calculate_next_difficulty(db, student_id, request.keyword)
    return request.manual_difficulty or DEFAULT_DIFFICULTY


def create_question_history(
    db: Session,
    student_id: int,
    keyword: str,
    difficulty: str,
    content: dict[str, Any],
) -> QuestionHistory:
    row = QuestionHistory(
        student_id=student_id,
        keyword=keyword,
        question_json=json.dumps(content, ensure_ascii=False),
        difficulty=difficulty,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def build_feedback_dimensions(
    score: float,
    suggestion: str,
    keyword: Optional[str] = None,
) -> dict[str, Any]:
    accuracy = round(score, 1)
    completeness = round(max(0.0, min(100.0, score - 5 if score >= 60 else score - 2)), 1)
    expression = round(max(0.0, min(100.0, score - 8 if score >= 60 else score + 5)), 1)
    return {
        "accuracy": accuracy,
        "completeness": completeness,
        "expression": expression,
        "next_focus": keyword or "Continue practicing the current topic.",
        "improvement": suggestion,
    }


def _debug_info(search_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_docs": search_result["raw_docs"],
        "rerank_docs": search_result["rerank_docs"],
        "raw_doc_details": search_result.get("raw_doc_details", []),
        "rerank_doc_details": search_result.get("rerank_doc_details", []),
        "index_info": search_result.get("index_info", {}),
        "runtime_config": search_result.get("runtime_config", {}),
        "rerank_applied": search_result.get("rerank_applied", False),
        "rerank_reason": search_result.get("rerank_reason", ""),
    }


async def generate_question(
    db: Session,
    student_id: int,
    request: QuestionRequest,
) -> dict[str, Any]:
    difficulty = resolve_difficulty(db, student_id, request)
    search_result = await rag_service.search_async(request.keyword)
    context = "\n\n".join(search_result["final_docs"])
    content = await llm_service.generate_quiz(
        request.keyword,
        context,
        difficulty,
        request.question_type,
    )
    normalized = normalize_question_payload(content)
    history = create_question_history(db, student_id, request.keyword, difficulty, normalized)
    return {
        "status": "success",
        "data": normalized,
        "question_id": history.id,
        "difficulty": difficulty,
        "context": context,
        "debug_info": _debug_info(search_result),
        "adaptive_state": learning_analytics_service.build_adaptive_snapshot(
            db,
            student_id,
            request.keyword,
        ).to_dict(),
    }


def generate_question_task_runner(payload: dict[str, Any]):
    request = QuestionRequest(**payload)

    def runner(task_context):
        db = SessionLocal()
        try:
            difficulty = resolve_difficulty(db, int(request.student_id), request)
            task_context.update(progress=0.2, detail="Retrieving study context.")
            search_result = rag_service.search(request.keyword)
            context = "\n\n".join(search_result["final_docs"])
            if task_context.is_cancel_requested():
                raise RuntimeError("Task cancelled by user.")
            task_context.update(progress=0.55, detail="Generating question.")
            content = asyncio.run(
                llm_service.generate_quiz(
                    request.keyword,
                    context,
                    difficulty,
                    request.question_type,
                )
            )
            normalized = normalize_question_payload(content)
            history = create_question_history(
                db,
                int(request.student_id),
                request.keyword,
                difficulty,
                normalized,
            )
            task_context.update(progress=0.88, detail="Saving question history.")
            return {
                "status": "success",
                "data": normalized,
                "question_id": history.id,
                "difficulty": difficulty,
                "debug_info": _debug_info(search_result),
                "adaptive_state": learning_analytics_service.build_adaptive_snapshot(
                    db,
                    int(request.student_id),
                    request.keyword,
                ).to_dict(),
            }
        finally:
            db.close()

    return runner


def create_generate_question_task(request: QuestionRequest, student_id: int) -> dict[str, Any]:
    request.student_id = student_id
    task_id = async_task_service.create_task(
        task_type="generate_question",
        task_scope="student",
        owner_id=student_id,
        payload=request.model_dump(),
        detail="Question generation task queued.",
        max_attempts=settings.TASK_GENERATE_QUESTION_MAX_ATTEMPTS,
        timeout_seconds=settings.TASK_GENERATE_QUESTION_TIMEOUT_SEC,
    )
    return {"status": "success", "task_id": task_id}


def _grade_values(request: GradeRequest) -> tuple[float, str, str]:
    score = float(request.direct_score or 0.0)
    reason = "Auto-graded against the reference answer."
    suggestion = f"Correct answer: {request.standard_answer}"
    if request.analysis:
        suggestion += f"\n\nAnalysis: {request.analysis}"
    return score, reason, suggestion


async def _grade_with_fallback(request: GradeRequest) -> tuple[float, str, str]:
    if request.question_type == "choice":
        return _grade_values(request)

    llm_result = await llm_service.grade_answer(
        request.question,
        request.standard_answer,
        request.student_answer,
    )
    return (
        float(llm_result.get("score", 0.0)),
        llm_result.get("reason", ""),
        llm_result.get("suggestion", ""),
    )


async def grade_answer(
    db: Session,
    student_id: int,
    request: GradeRequest,
) -> dict[str, Any]:
    keyword = learning_analytics_service.get_question_keyword(db, request.question_id)
    score, reason, suggestion = await _grade_with_fallback(request)
    record = ExamRecord(
        student_id=student_id,
        question_id=request.question_id,
        question_content=request.question,
        student_answer=request.student_answer,
        ai_score=score,
        ai_comment=suggestion,
        difficulty=request.difficulty,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    mastery = learning_analytics_service.update_mastery_from_record(db, record)
    return {
        "status": "success",
        "data": {
            "score": score,
            "reason": reason,
            "suggestion": suggestion,
            "feedback_dimensions": build_feedback_dimensions(score, suggestion, keyword),
            "mastery_update": learning_analytics_service.mastery_payload(mastery) if mastery else None,
        },
    }


def grade_answer_task_runner(payload: dict[str, Any]):
    request = GradeRequest(**payload)

    def runner(task_context):
        db = SessionLocal()
        try:
            task_context.update(progress=0.18, detail="Preparing grading payload.")
            keyword = learning_analytics_service.get_question_keyword(db, request.question_id)
            if request.question_type == "choice":
                score, reason, suggestion = _grade_values(request)
            else:
                task_context.update(progress=0.52, detail="Calling the grading model.")
                if task_context.is_cancel_requested():
                    raise RuntimeError("Task cancelled by user.")
                llm_result = asyncio.run(
                    llm_service.grade_answer(
                        request.question,
                        request.standard_answer,
                        request.student_answer,
                    )
                )
                score = float(llm_result.get("score", 0.0))
                reason = llm_result.get("reason", "")
                suggestion = llm_result.get("suggestion", "")

            record = ExamRecord(
                student_id=int(request.student_id),
                question_id=request.question_id,
                question_content=request.question,
                student_answer=request.student_answer,
                ai_score=score,
                ai_comment=suggestion,
                difficulty=request.difficulty,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            task_context.update(progress=0.8, detail="Updating mastery profile.")
            mastery = learning_analytics_service.update_mastery_from_record(db, record)
            return {
                "status": "success",
                "data": {
                    "score": score,
                    "reason": reason,
                    "suggestion": suggestion,
                    "feedback_dimensions": build_feedback_dimensions(score, suggestion, keyword),
                    "mastery_update": learning_analytics_service.mastery_payload(mastery) if mastery else None,
                },
            }
        finally:
            db.close()

    return runner


def create_grade_answer_task(request: GradeRequest, student_id: int) -> dict[str, Any]:
    request.student_id = student_id
    task_id = async_task_service.create_task(
        task_type="grade_answer",
        task_scope="student",
        owner_id=student_id,
        payload=request.model_dump(),
        detail="Answer grading task queued.",
        max_attempts=settings.TASK_GRADE_ANSWER_MAX_ATTEMPTS,
        timeout_seconds=settings.TASK_GRADE_ANSWER_TIMEOUT_SEC,
    )
    return {"status": "success", "task_id": task_id}


async def stream_generate_question(
    db: Session,
    student_id: int,
    request: QuestionRequest,
) -> StreamingResponse:
    difficulty = resolve_difficulty(db, student_id, request)
    started_at = time.time()
    search_result = await rag_service.search_async(request.keyword)
    context = "\n\n".join(search_result["final_docs"])
    rag_time_ms = (time.time() - started_at) * 1000

    async def event_stream():
        history = QuestionHistory(
            student_id=student_id,
            keyword=request.keyword,
            question_json="",
            difficulty=difficulty,
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        metadata = {
            "type": "metadata",
            "difficulty": difficulty,
            "question_id": history.id,
            "rag_time": f"{rag_time_ms:.0f}ms",
            "timings": search_result.get("timings", {}),
            "index_info": search_result.get("index_info", {}),
            "runtime_config": search_result.get("runtime_config", {}),
        }
        yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"

        full_content = ""
        async for chunk in llm_service.stream_generate_quiz(
            request.keyword,
            context,
            difficulty,
            request.question_type,
        ):
            full_content += chunk
            yield f"data: {json.dumps({'type': 'content', 'content': chunk}, ensure_ascii=False)}\n\n"

        parsed = normalize_question_payload(full_content)
        history.question_json = json.dumps(parsed, ensure_ascii=False)
        db.commit()
        done_event = {
            "type": "done",
            "full_content": full_content,
            "parsed_content": parsed,
        }
        yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def get_student_task(task_id: int, current_user: AuthenticatedUser) -> dict[str, Any]:
    task = async_task_service.get_task(task_id)
    if task is None or task.get("task_scope") != "student":
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.get("owner_id") not in {None, current_user.id}:
        raise HTTPException(status_code=403, detail="Permission denied.")
    return {"status": "success", "data": task}


def cancel_student_task(task_id: int, current_user: AuthenticatedUser) -> dict[str, Any]:
    try:
        task = async_task_service.cancel_task(task_id, owner_id=current_user.id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found.") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Permission denied.") from exc
    return {"status": "success", "data": task}


def get_history(db: Session, student_id: int) -> dict[str, Any]:
    records = (
        db.query(ExamRecord)
        .filter(ExamRecord.student_id == student_id)
        .order_by(ExamRecord.created_at.desc())
        .limit(50)
        .all()
    )
    data = []
    for record in records:
        keyword = learning_analytics_service.get_question_keyword(db, record.question_id)
        question = record.question_content or "Unknown question"
        data.append(
            {
                "id": record.id,
                "time": record.created_at.strftime("%Y-%m-%d %H:%M"),
                "question": (question[:30] + "...") if len(question) > 30 else question,
                "score": round(float(record.ai_score or 0.0), 1),
                "difficulty": record.difficulty or DEFAULT_DIFFICULTY,
                "keyword": keyword,
            }
        )
    return {"status": "success", "data": data}


def get_history_detail(db: Session, student_id: int, record_id: int) -> dict[str, Any]:
    record = (
        db.query(ExamRecord)
        .filter(ExamRecord.id == record_id, ExamRecord.student_id == student_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    keyword = learning_analytics_service.get_question_keyword(db, record.question_id)
    return {
        "status": "success",
        "data": {
            "id": record.id,
            "time": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "question": record.question_content,
            "student_answer": record.student_answer,
            "score": round(float(record.ai_score or 0.0), 1),
            "comment": record.ai_comment,
            "difficulty": record.difficulty or DEFAULT_DIFFICULTY,
            "keyword": keyword,
        },
    }


def get_learning_dashboard(
    db: Session,
    student_id: int,
    keyword: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "status": "success",
        "data": learning_analytics_service.build_student_dashboard(db, student_id, keyword),
    }


def get_wrong_questions(db: Session, student_id: int) -> dict[str, Any]:
    dashboard = learning_analytics_service.build_student_dashboard(db, student_id)
    return {"status": "success", "data": dashboard["wrong_questions"]}


def get_adaptive_stats(
    db: Session,
    student_id: int,
    keyword: Optional[str] = None,
) -> dict[str, Any]:
    dashboard = learning_analytics_service.build_student_dashboard(db, student_id, keyword)
    return {
        "status": "success",
        "data": {
            "recent_trend": dashboard["recent_trend"],
            "keyword_stats": dashboard["keyword_stats"],
            "adaptive_state": dashboard["adaptive_state"],
            "mastery_by_keyword": dashboard["mastery_by_keyword"],
            "wrong_questions": dashboard["wrong_questions"],
            "recommended_practice": dashboard["recommended_practice"],
            "learning_path": dashboard["learning_path"],
            "student_overview": dashboard["student_overview"],
        },
    }
