from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.documents import Document as LangChainDocument

import backend.services.teacher_service as teacher_service
from backend.models.tables import Document


class _FakeTaskContext:
    def __init__(self):
        self.updates = []

    def update(self, **kwargs):
        self.updates.append(kwargs)


class _FakeVectorDB:
    def add_documents(self, docs):
        self.docs = list(docs)

    def save_local(self, index_path):
        path = Path(index_path)
        path.mkdir(parents=True, exist_ok=True)
        (path / "index.faiss").write_text("fake-faiss", encoding="utf-8")
        (path / "index.pkl").write_text("fake-pkl", encoding="utf-8")


@pytest.fixture()
def local_tmp_dir():
    base_dir = Path.cwd() / ".tmp_test_artifacts"
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"teacher-upload-index-{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_teacher_upload_returns_task_and_indexing_status(
    client,
    session_factory,
    auth_headers,
    monkeypatch,
    local_tmp_dir,
):
    docs_dir = local_tmp_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(teacher_service.settings, "DOCS_DIR", str(docs_dir))
    monkeypatch.setattr(teacher_service.settings, "FAISS_INDEX_DIR", str(local_tmp_dir / "faiss_index"))
    monkeypatch.setattr(teacher_service, "create_document_index_task", lambda document: 321)

    response = client.post(
        "/teacher/upload_doc",
        headers=auth_headers["teacher"],
        files={"file": ("lesson.txt", b"teachers can upload and index this text", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["task_id"] == 321
    assert payload["data"]["status"] == "indexing"
    assert payload["data"]["indexing_mode"] == "async_incremental"
    assert payload["data"]["index_scope"] == "production"
    assert payload["data"]["target_index"] == "faiss_index"
    assert payload["data"]["requested_parser"] == "docling"
    assert (docs_dir / payload["data"]["stored_name"]).exists()

    verify_response = client.get("/teacher/my_docs", headers=auth_headers["teacher"])
    verify_payload = verify_response.json()
    assert verify_payload["data"][0]["status"] == "indexing"


def test_index_document_runner_marks_document_indexed(
    session_factory,
    monkeypatch,
    local_tmp_dir,
):
    docs_dir = local_tmp_dir / "docs"
    production_index_dir = local_tmp_dir / "faiss_index"
    docs_dir.mkdir(parents=True, exist_ok=True)
    source_path = docs_dir / "lesson.txt"
    source_path.write_text("dynamic indexing content", encoding="utf-8")
    monkeypatch.setattr(teacher_service.settings, "DOCS_DIR", str(docs_dir))
    monkeypatch.setattr(teacher_service.settings, "FAISS_INDEX_DIR", str(production_index_dir))
    monkeypatch.setattr(teacher_service, "SessionLocal", session_factory)
    monkeypatch.setattr(teacher_service.rag_service, "is_initialized", False)
    monkeypatch.setattr(teacher_service.rag_service, "_resolve_index_path", lambda: str(local_tmp_dir / "faiss_index_eval_docling"))
    monkeypatch.setattr(teacher_service.rag_service, "reload_db", lambda: True)
    monkeypatch.setattr(
        teacher_service,
        "load_source_documents",
        lambda file_path, parser: (
            [
                LangChainDocument(
                    page_content="dynamic indexing content",
                    metadata={"source": file_path, "parser": "text"},
                )
            ],
            {"requested_parser": "text", "actual_parser": "text", "docling_strategy": None},
        ),
    )
    monkeypatch.setattr(teacher_service, "split_documents_for_rag", lambda documents, chunk_size, chunk_overlap: list(documents))
    monkeypatch.setattr(teacher_service, "get_embedding_model", lambda embeddings=None: object())
    monkeypatch.setattr(teacher_service, "_build_vector_db_from_chunks", lambda chunks, embeddings: _FakeVectorDB())

    db = session_factory()
    try:
        row = Document(
            filename="lesson.txt",
            stored_name="lesson_v1.txt",
            filepath=str(source_path),
            teacher_id=1,
            mime_type="text/plain",
            file_size=24,
            version=1,
            status="indexing",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        document_id = row.id
    finally:
        db.close()

    runner = teacher_service.index_document_runner(
        {
            "document_id": document_id,
            "stored_name": "lesson_v1.txt",
            "filepath": str(source_path),
            "teacher_id": 1,
        }
    )
    result = runner(_FakeTaskContext())

    assert result["mode"] == "incremental_append"
    assert result["index_update_mode"] == "incremental_append"
    assert result["index_scope"] == "production"
    assert result["requested_parser"] == "text"
    assert result["actual_parser"] == "text"
    assert result["chunks_added"] == 1
    assert result["index_path"] == str(production_index_dir)
    assert (production_index_dir / "build_meta.json").exists()

    db = session_factory()
    try:
        refreshed = db.query(Document).filter(Document.id == document_id).first()
        assert refreshed is not None
        assert refreshed.status == "indexed"
        assert refreshed.indexed_at is not None
    finally:
        db.close()


def test_index_document_runner_uses_docling_for_pdf_and_updates_build_meta(
    session_factory,
    monkeypatch,
    local_tmp_dir,
):
    docs_dir = local_tmp_dir / "docs"
    production_index_dir = local_tmp_dir / "faiss_index"
    docs_dir.mkdir(parents=True, exist_ok=True)
    source_path = docs_dir / "lesson.pdf"
    source_path.write_text("fake pdf payload", encoding="utf-8")
    monkeypatch.setattr(teacher_service.settings, "DOCS_DIR", str(docs_dir))
    monkeypatch.setattr(teacher_service.settings, "FAISS_INDEX_DIR", str(production_index_dir))
    monkeypatch.setattr(teacher_service, "SessionLocal", session_factory)
    monkeypatch.setattr(teacher_service.rag_service, "is_initialized", False)
    monkeypatch.setattr(teacher_service.rag_service, "_resolve_index_path", lambda: str(local_tmp_dir / "faiss_index_eval_docling"))
    monkeypatch.setattr(teacher_service.rag_service, "reload_db", lambda: True)
    monkeypatch.setattr(
        teacher_service,
        "load_source_documents",
        lambda file_path, parser: (
            [
                LangChainDocument(
                    page_content="docling extracted content",
                    metadata={"source": file_path, "parser": "docling", "docling_strategy": "backend_only"},
                )
            ],
            {
                "requested_parser": "docling",
                "actual_parser": "docling",
                "docling_strategy": "backend_only",
                "docling_page_ratio": 1.0,
                "docling_char_ratio": 1.0,
            },
        ),
    )
    monkeypatch.setattr(teacher_service, "split_documents_for_rag", lambda documents, chunk_size, chunk_overlap: list(documents))
    monkeypatch.setattr(teacher_service, "get_embedding_model", lambda embeddings=None: object())
    monkeypatch.setattr(teacher_service, "_build_vector_db_from_chunks", lambda chunks, embeddings: _FakeVectorDB())

    db = session_factory()
    try:
        row = Document(
            filename="lesson.pdf",
            stored_name="lesson_v1.pdf",
            filepath=str(source_path),
            teacher_id=1,
            mime_type="application/pdf",
            file_size=64,
            version=1,
            status="indexing",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        document_id = row.id
    finally:
        db.close()

    result = teacher_service.index_document_runner(
        {
            "document_id": document_id,
            "stored_name": "lesson_v1.pdf",
            "filepath": str(source_path),
            "teacher_id": 1,
        }
    )(_FakeTaskContext())

    assert result["mode"] == "incremental_append"
    assert result["requested_parser"] == "docling"
    assert result["actual_parser"] == "docling"
    assert result["docling_strategy"] == "backend_only"
    assert result["index_scope"] == "production"
    assert result["index_path"] == str(production_index_dir)

    build_meta = json.loads((production_index_dir / "build_meta.json").read_text(encoding="utf-8"))
    assert build_meta["requested_parser"] == "docling"
    assert build_meta["parser_usage"]["docling"] == 1
    assert build_meta["source_build_stats"]["lesson.pdf"]["actual_parser"] == "docling"


def test_index_document_runner_reports_docling_fallback_to_pypdf(
    session_factory,
    monkeypatch,
    local_tmp_dir,
):
    docs_dir = local_tmp_dir / "docs"
    production_index_dir = local_tmp_dir / "faiss_index"
    docs_dir.mkdir(parents=True, exist_ok=True)
    source_path = docs_dir / "fallback.pdf"
    source_path.write_text("fake pdf payload", encoding="utf-8")
    monkeypatch.setattr(teacher_service.settings, "DOCS_DIR", str(docs_dir))
    monkeypatch.setattr(teacher_service.settings, "FAISS_INDEX_DIR", str(production_index_dir))
    monkeypatch.setattr(teacher_service, "SessionLocal", session_factory)
    monkeypatch.setattr(teacher_service.rag_service, "is_initialized", False)
    monkeypatch.setattr(teacher_service.rag_service, "reload_db", lambda: True)
    monkeypatch.setattr(
        teacher_service,
        "load_source_documents",
        lambda file_path, parser: (
            [
                LangChainDocument(
                    page_content="fallback content",
                    metadata={"source": file_path, "parser": "pypdf", "page": 1},
                )
            ],
            {
                "requested_parser": "docling",
                "actual_parser": "pypdf",
                "docling_strategy": "fallback_to_pypdf",
                "fallback_reason": "ValueError: docling quality too low",
                "docling_page_ratio": 0.0,
                "docling_char_ratio": 0.0,
            },
        ),
    )
    monkeypatch.setattr(teacher_service, "split_documents_for_rag", lambda documents, chunk_size, chunk_overlap: list(documents))
    monkeypatch.setattr(teacher_service, "get_embedding_model", lambda embeddings=None: object())
    monkeypatch.setattr(teacher_service, "_build_vector_db_from_chunks", lambda chunks, embeddings: _FakeVectorDB())

    db = session_factory()
    try:
        row = Document(
            filename="fallback.pdf",
            stored_name="fallback_v1.pdf",
            filepath=str(source_path),
            teacher_id=1,
            mime_type="application/pdf",
            file_size=64,
            version=1,
            status="indexing",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        document_id = row.id
    finally:
        db.close()

    result = teacher_service.index_document_runner(
        {
            "document_id": document_id,
            "stored_name": "fallback_v1.pdf",
            "filepath": str(source_path),
            "teacher_id": 1,
        }
    )(_FakeTaskContext())

    assert result["mode"] == "docling_fallback_to_pypdf"
    assert result["index_update_mode"] == "incremental_append"
    assert result["requested_parser"] == "docling"
    assert result["actual_parser"] == "pypdf"
    assert "docling quality too low" in result["fallback_reason"]

    build_meta = json.loads((production_index_dir / "build_meta.json").read_text(encoding="utf-8"))
    assert build_meta["requested_parser"] == "docling"
    assert build_meta["parser_usage"]["pypdf"] == 1
    assert build_meta["source_build_stats"]["fallback.pdf"]["actual_parser"] == "pypdf"


def test_index_document_runner_falls_back_to_full_rebuild_on_config_mismatch(
    session_factory,
    monkeypatch,
    local_tmp_dir,
):
    docs_dir = local_tmp_dir / "docs"
    production_index_dir = local_tmp_dir / "faiss_index"
    docs_dir.mkdir(parents=True, exist_ok=True)
    production_index_dir.mkdir(parents=True, exist_ok=True)
    source_path = docs_dir / "lesson.pdf"
    source_path.write_text("fake pdf payload", encoding="utf-8")
    (production_index_dir / "index.faiss").write_text("fake-faiss", encoding="utf-8")
    (production_index_dir / "index.pkl").write_text("fake-pkl", encoding="utf-8")
    (production_index_dir / "build_meta.json").write_text(
        json.dumps(
            {
                "requested_parser": "pypdf",
                "chunk_size": 500,
                "chunk_overlap": 50,
                "total_documents": 3,
                "total_chunks": 6,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(teacher_service.settings, "DOCS_DIR", str(docs_dir))
    monkeypatch.setattr(teacher_service.settings, "FAISS_INDEX_DIR", str(production_index_dir))
    monkeypatch.setattr(teacher_service, "SessionLocal", session_factory)
    monkeypatch.setattr(teacher_service.rag_service, "is_initialized", False)
    monkeypatch.setattr(teacher_service.rag_service, "reload_db", lambda: True)
    monkeypatch.setattr(
        teacher_service,
        "init_local_rag",
        lambda parser_mode=None, faiss_index_path=None, embeddings=None: str(faiss_index_path),
    )

    db = session_factory()
    try:
        row = Document(
            filename="lesson.pdf",
            stored_name="lesson_v1.pdf",
            filepath=str(source_path),
            teacher_id=1,
            mime_type="application/pdf",
            file_size=64,
            version=1,
            status="indexing",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        document_id = row.id
    finally:
        db.close()

    result = teacher_service.index_document_runner(
        {
            "document_id": document_id,
            "stored_name": "lesson_v1.pdf",
            "filepath": str(source_path),
            "teacher_id": 1,
        }
    )(_FakeTaskContext())

    assert result["mode"] == "full_rebuild"
    assert result["full_rebuild"] is True
    assert result["requested_parser"] == "docling"
    assert result["index_scope"] == "production"
    assert "parser" in result["full_rebuild_reason"]
