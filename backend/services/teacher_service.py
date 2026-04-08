import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from langchain_community.vectorstores import FAISS
from sqlalchemy.orm import Session

from backend.core.auth import AuthenticatedUser
from backend.core.config import settings
from backend.db.session import SessionLocal
from backend.models.tables import Document, ExamRecord, User
from backend.schemas.student import DEFAULT_DIFFICULTY
from backend.services.async_task_service import async_task_service
from backend.services.learning_analytics_service import learning_analytics_service
from backend.services.rag_service import rag_service
from backend.scripts.init_rag import (
    faiss_index_exists,
    get_embedding_model,
    init_local_rag,
    list_supported_source_files,
    load_source_documents,
    read_build_meta,
    resolve_rag_build_config,
    split_documents_for_rag,
    summarize_documents,
    write_build_meta,
)


def sanitize_filename(filename: str) -> tuple[str, str]:
    file_path = Path(filename or "")
    ext = file_path.suffix.lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or 'unknown'}")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", file_path.stem).strip("._")
    return stem or "document", ext


async def persist_upload(file: UploadFile) -> tuple[bytes, int]:
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return content, len(content)


async def upload_document(
    file: UploadFile,
    db: Session,
    current_user: AuthenticatedUser,
) -> dict[str, Any]:
    config = _resolve_production_rag_config()
    safe_stem, ext = sanitize_filename(file.filename or "")
    content, file_size = await persist_upload(file)

    os.makedirs(settings.DOCS_DIR, exist_ok=True)
    latest_version = (
        db.query(Document)
        .filter(Document.teacher_id == current_user.id, Document.filename == (file.filename or ""))
        .order_by(Document.version.desc())
        .first()
    )
    version = int(latest_version.version or 0) + 1 if latest_version else 1
    stored_name = f"{safe_stem}_v{version}_{uuid4().hex[:8]}{ext}"
    file_path = os.path.join(settings.DOCS_DIR, stored_name)
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    new_doc = Document(
        filename=file.filename or stored_name,
        stored_name=stored_name,
        filepath=file_path,
        teacher_id=current_user.id,
        mime_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        version=version,
        status="indexing",
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    try:
        task_id = create_document_index_task(new_doc)
    except Exception:
        new_doc.status = "failed"
        db.commit()
        raise
    return {
        "status": "success",
        "message": f"File {new_doc.filename} uploaded successfully. Indexing started.",
        "task_id": task_id,
        "data": {
            "id": new_doc.id,
            "name": new_doc.filename,
            "stored_name": new_doc.stored_name,
            "time": new_doc.created_at.strftime("%Y-%m-%d %H:%M"),
            "version": new_doc.version,
            "status": new_doc.status,
            "size": new_doc.file_size,
            "task_id": task_id,
            "indexing_mode": "async_incremental",
            "index_scope": "production",
            "target_index": os.path.basename(config["index_path"]),
            "requested_parser": config["parser"],
        },
    }


def _serialize_document(doc: Document) -> dict[str, Any]:
    return {
        "id": doc.id,
        "name": doc.filename,
        "stored_name": doc.stored_name,
        "time": doc.created_at.strftime("%Y-%m-%d %H:%M"),
        "version": int(doc.version or 1),
        "status": doc.status,
        "size": int(doc.file_size or 0),
        "indexed_at": doc.indexed_at.strftime("%Y-%m-%d %H:%M") if doc.indexed_at else None,
    }


def _merge_counter(existing: dict[str, Any] | None, delta: dict[str, int]) -> dict[str, int]:
    merged = {str(key): int(value) for key, value in (existing or {}).items()}
    for key, value in delta.items():
        merged[key] = merged.get(key, 0) + int(value)
    return merged


def _set_document_status(
    document_id: int,
    *,
    status: str,
    indexed_at: datetime | None = None,
) -> Document | None:
    db = SessionLocal()
    try:
        row = db.query(Document).filter(Document.id == document_id).first()
        if row is None:
            return None
        row.status = status
        row.indexed_at = indexed_at
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def _mark_all_documents_indexed() -> None:
    db = SessionLocal()
    try:
        now = datetime.now()
        for row in db.query(Document).all():
            row.status = "indexed"
            row.indexed_at = now
        db.commit()
    finally:
        db.close()


def _build_vector_db_from_chunks(chunks, embeddings):
    if not chunks:
        raise RuntimeError("No document chunks were produced for indexing.")
    try:
        batch_size = max(1, int(os.getenv("RAG_FAISS_BATCH_SIZE", "64")))
    except ValueError:
        batch_size = 64
    first_batch = chunks[:batch_size]
    vector_db = FAISS.from_documents(first_batch, embeddings)
    for start in range(batch_size, len(chunks), batch_size):
        vector_db.add_documents(chunks[start : start + batch_size])
    return vector_db


def _resolve_production_index_path() -> str:
    return os.path.abspath(settings.FAISS_INDEX_DIR)


def _resolve_production_rag_config() -> dict[str, Any]:
    return resolve_rag_build_config(faiss_index_path=_resolve_production_index_path())


def _build_parser_result(file_stats: dict[str, Any] | None) -> dict[str, Any]:
    file_stats = file_stats or {}
    requested_parser = file_stats.get("requested_parser") or "unknown"
    actual_parser = file_stats.get("actual_parser") or requested_parser
    fallback_reason = file_stats.get("fallback_reason") or ""
    docling_strategy = file_stats.get("docling_strategy")
    mode = "incremental_append"
    if requested_parser == "docling" and actual_parser == "pypdf":
        mode = "docling_fallback_to_pypdf"
    return {
        "mode": mode,
        "requested_parser": requested_parser,
        "actual_parser": actual_parser,
        "fallback_reason": fallback_reason,
        "docling_strategy": docling_strategy,
    }


def _should_fallback_to_full_rebuild(
    *,
    index_path: str,
    current_filepath: str,
    parser: str,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[bool, str]:
    supported_files = [
        os.path.abspath(path)
        for path in list_supported_source_files(settings.DOCS_DIR)
    ]
    has_other_files = any(path != current_filepath for path in supported_files)
    if not faiss_index_exists(index_path):
        if has_other_files:
            return True, "Existing documents detected without a usable FAISS index."
        return False, ""

    build_meta = read_build_meta(index_path)
    if not build_meta:
        return False, ""

    mismatches = []
    if build_meta.get("requested_parser") not in {None, parser}:
        mismatches.append("parser")
    if int(build_meta.get("chunk_size") or chunk_size) != int(chunk_size):
        mismatches.append("chunk_size")
    if int(build_meta.get("chunk_overlap") or chunk_overlap) != int(chunk_overlap):
        mismatches.append("chunk_overlap")
    if mismatches:
        return True, f"Index build configuration mismatch: {', '.join(mismatches)}."
    return False, ""


def _run_full_rebuild(task_context, *, config: dict[str, Any], reason: str = "") -> dict[str, Any]:
    task_context.update(progress=0.36, detail="Falling back to a full knowledge base rebuild.")
    index_path = init_local_rag(
        parser_mode=config["parser"],
        faiss_index_path=config["index_path"],
        embeddings=rag_service.embeddings if rag_service.is_initialized else None,
    )
    task_context.update(progress=0.82, detail="Reloading the runtime vector index.")
    rag_service.reload_db()
    _mark_all_documents_indexed()
    return {
        "mode": "full_rebuild",
        "full_rebuild": True,
        "full_rebuild_reason": reason or "",
        "requested_parser": config["parser"],
        "actual_parser": config["parser"],
        "fallback_reason": "",
        "docling_strategy": None,
        "index_path": index_path,
        "active_index": index_path,
        "index_scope": "production",
        "message": "Full index rebuild completed and the runtime index has been refreshed.",
    }


def _index_document_incrementally(payload: dict[str, Any], task_context) -> dict[str, Any]:
    current_filepath = os.path.abspath(str(payload["filepath"]))
    config = _resolve_production_rag_config()
    should_fallback, reason = _should_fallback_to_full_rebuild(
        index_path=config["index_path"],
        current_filepath=current_filepath,
        parser=config["parser"],
        chunk_size=int(config["chunk_size"]),
        chunk_overlap=int(config["chunk_overlap"]),
    )
    if should_fallback:
        task_context.update(progress=0.24, detail=reason or "Full rebuild required.")
        return _run_full_rebuild(task_context, config=config, reason=reason)

    task_context.update(progress=0.24, detail="Parsing the uploaded document.")
    loaded_docs, file_stats = load_source_documents(current_filepath, config["parser"])
    if not loaded_docs:
        raise RuntimeError("The uploaded document produced no readable content.")
    parser_result = _build_parser_result(file_stats)

    task_context.update(progress=0.48, detail="Chunking the uploaded document.")
    chunks = split_documents_for_rag(
        loaded_docs,
        chunk_size=int(config["chunk_size"]),
        chunk_overlap=int(config["chunk_overlap"]),
    )
    if not chunks:
        raise RuntimeError("The uploaded document produced no indexable chunks.")

    used_embeddings = get_embedding_model(rag_service.embeddings if rag_service.is_initialized else None)
    task_context.update(progress=0.68, detail="Appending the document to the FAISS index.")
    try:
        if faiss_index_exists(config["index_path"]):
            vector_db = FAISS.load_local(
                folder_path=config["index_path"],
                embeddings=used_embeddings,
                allow_dangerous_deserialization=True,
            )
            vector_db.add_documents(chunks)
        else:
            vector_db = _build_vector_db_from_chunks(chunks, used_embeddings)
    except Exception:
        supported_files = [
            os.path.abspath(path)
            for path in list_supported_source_files(settings.DOCS_DIR)
        ]
        if any(path != current_filepath for path in supported_files):
            task_context.update(progress=0.32, detail="Incremental append failed. Switching to full rebuild.")
            return _run_full_rebuild(
                task_context,
                config=config,
                reason="Incremental append failed while other documents were present.",
            )
        raise

    os.makedirs(config["index_path"], exist_ok=True)
    vector_db.save_local(config["index_path"])

    parser_usage, source_usage = summarize_documents(loaded_docs)
    build_meta = read_build_meta(config["index_path"])
    build_meta = {
        **build_meta,
        "requested_parser": config["parser"],
        "parser_usage": _merge_counter(build_meta.get("parser_usage"), parser_usage),
        "source_usage": _merge_counter(build_meta.get("source_usage"), source_usage),
        "source_build_stats": {
            **(build_meta.get("source_build_stats") or {}),
            os.path.basename(current_filepath): file_stats,
        },
        "chunk_size": int(config["chunk_size"]),
        "chunk_overlap": int(config["chunk_overlap"]),
        "total_documents": int(build_meta.get("total_documents") or 0) + len(loaded_docs),
        "total_chunks": int(build_meta.get("total_chunks") or 0) + len(chunks),
    }
    write_build_meta(config["index_path"], build_meta)

    task_context.update(progress=0.88, detail="Reloading the runtime vector index.")
    rag_service.reload_db()
    return {
        **parser_result,
        "index_update_mode": "incremental_append",
        "full_rebuild": False,
        "document_id": int(payload["document_id"]),
        "index_path": config["index_path"],
        "active_index": config["index_path"],
        "index_scope": "production",
        "chunks_added": len(chunks),
        "message": "Document indexed and the runtime index has been refreshed.",
    }


def get_my_docs(db: Session, current_user: AuthenticatedUser) -> dict[str, Any]:
    docs = (
        db.query(Document)
        .filter(Document.teacher_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return {
        "status": "success",
        "meta": {
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
            "allowed_extensions": sorted(settings.ALLOWED_UPLOAD_EXTENSIONS),
        },
        "data": [
            {
                **_serialize_document(doc),
                "path": doc.filepath,
            }
            for doc in docs
        ],
    }


def create_document_index_task(document: Document) -> int:
    return async_task_service.create_task(
        task_type="index_document",
        task_scope="teacher",
        owner_id=document.teacher_id,
        payload={
            "document_id": document.id,
            "stored_name": document.stored_name,
            "filepath": document.filepath,
            "teacher_id": document.teacher_id,
        },
        detail="Document indexing task queued.",
        timeout_seconds=max(settings.TASK_DEFAULT_TIMEOUT_SEC, 900),
    )


def index_document_runner(payload: dict[str, Any]):
    def runner(task_context):
        document_id = int(payload["document_id"])
        db = SessionLocal()
        try:
            row = db.query(Document).filter(Document.id == document_id).first()
            if row is None:
                raise RuntimeError("Document not found.")
            if row.status not in {"indexing", "failed", "uploaded"}:
                raise RuntimeError(f"Document status '{row.status}' cannot be indexed.")
        finally:
            db.close()

        try:
            result = _index_document_incrementally(payload, task_context)
            if result.get("mode") == "full_rebuild":
                indexed_doc = _set_document_status(document_id, status="indexed", indexed_at=datetime.now())
            else:
                indexed_doc = _set_document_status(document_id, status="indexed", indexed_at=datetime.now())
            result["document"] = _serialize_document(indexed_doc) if indexed_doc else None
            return result
        except Exception:
            _set_document_status(document_id, status="failed", indexed_at=None)
            raise

    return runner


def reindex_runner(payload: dict[str, Any]):
    def runner(task_context):
        config = _resolve_production_rag_config()
        task_context.update(progress=0.18, detail="Parsing documents and building the vector index.")
        index_path = init_local_rag(
            parser_mode=config["parser"],
            faiss_index_path=config["index_path"],
            embeddings=rag_service.embeddings if rag_service.is_initialized else None,
        )
        task_context.update(progress=0.82, detail="Reloading the runtime vector index.")
        rag_service.reload_db()
        _mark_all_documents_indexed()
        return {
            "mode": "full_rebuild",
            "full_rebuild": True,
            "requested_parser": config["parser"],
            "actual_parser": config["parser"],
            "fallback_reason": "",
            "docling_strategy": None,
            "index_path": index_path,
            "active_index": index_path,
            "index_scope": "production",
            "message": "Index rebuild completed and the runtime index has been refreshed.",
        }

    return runner


def create_reindex_task(current_user: AuthenticatedUser) -> dict[str, Any]:
    task_id = async_task_service.create_task(
        task_type="reindex_kb",
        task_scope="teacher",
        owner_id=current_user.id,
        payload={"triggered_by": current_user.id},
        detail="Index rebuild task queued.",
        timeout_seconds=max(settings.TASK_DEFAULT_TIMEOUT_SEC, 900),
    )
    return {
        "status": "success",
        "message": "Index rebuild task queued successfully.",
        "task_id": task_id,
    }


def get_teacher_task(task_id: int, current_user: AuthenticatedUser) -> dict[str, Any]:
    task = async_task_service.get_task(task_id)
    if task is None or task.get("task_scope") != "teacher":
        raise HTTPException(status_code=404, detail="Task not found.")
    if current_user.role != "admin" and task.get("owner_id") not in {None, current_user.id}:
        raise HTTPException(status_code=403, detail="Permission denied.")
    return {"status": "success", "data": task}


def list_teacher_tasks(
    current_user: AuthenticatedUser,
    *,
    status: str | None = None,
    task_type: str | None = None,
    owner_id: int | None = None,
    task_scope: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    _ = current_user
    tasks = async_task_service.list_tasks(
        status=status,
        task_type=task_type,
        owner_id=owner_id,
        task_scope=task_scope,
        limit=limit,
    )
    return {
        "status": "success",
        "meta": {
            "count": len(tasks),
            "filters": {
                "status": status,
                "task_type": task_type,
                "owner_id": owner_id,
                "task_scope": task_scope,
                "limit": max(1, min(int(limit), 200)),
            },
        },
        "data": tasks,
    }


def cancel_teacher_task(task_id: int, current_user: AuthenticatedUser) -> dict[str, Any]:
    try:
        task = async_task_service.cancel_task(
            task_id,
            owner_id=None if current_user.role == "admin" else current_user.id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found.") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Permission denied.") from exc
    return {"status": "success", "data": task}


def get_dashboard_stats(db: Session) -> dict[str, Any]:
    records = (
        db.query(ExamRecord, User.username)
        .join(User, ExamRecord.student_id == User.id)
        .order_by(ExamRecord.created_at.desc())
        .limit(30)
        .all()
    )
    data = []
    for record, username in records:
        keyword = learning_analytics_service.get_question_keyword(db, record.question_id)
        question = record.question_content or "Unknown question"
        data.append(
            {
                "id": record.id,
                "student_id": record.student_id,
                "time": record.created_at.strftime("%Y-%m-%d %H:%M"),
                "student": username,
                "keyword": keyword,
                "difficulty": record.difficulty or DEFAULT_DIFFICULTY,
                "question": question[:42] + "..." if len(question) > 42 else question,
                "score": round(float(record.ai_score or 0.0), 1),
            }
        )
    return {"status": "success", "data": data}


def get_class_insights(db: Session) -> dict[str, Any]:
    return {"status": "success", "data": learning_analytics_service.build_class_insights(db)}


def get_student_profiles(db: Session) -> dict[str, Any]:
    insights = learning_analytics_service.build_class_insights(db)
    return {"status": "success", "data": insights["student_snapshots"]}


def get_student_profile(db: Session, student_id: int) -> dict[str, Any]:
    student = db.query(User).filter(User.id == student_id, User.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    return {
        "status": "success",
        "data": learning_analytics_service.build_teacher_student_profile(db, student_id),
    }


def get_record_detail(db: Session, record_id: int) -> dict[str, Any]:
    result = (
        db.query(ExamRecord, User.username)
        .join(User, ExamRecord.student_id == User.id)
        .filter(ExamRecord.id == record_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Record not found.")
    record, username = result
    keyword = learning_analytics_service.get_question_keyword(db, record.question_id)
    return {
        "status": "success",
        "data": {
            "id": record.id,
            "time": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "student": username,
            "student_id": record.student_id,
            "keyword": keyword,
            "question": record.question_content,
            "student_answer": record.student_answer,
            "score": round(float(record.ai_score or 0.0), 1),
            "comment": record.ai_comment,
            "difficulty": record.difficulty or DEFAULT_DIFFICULTY,
        },
    }
