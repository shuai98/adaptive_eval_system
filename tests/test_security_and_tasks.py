import logging
import time
from datetime import datetime, timedelta

import backend.services.async_task_service as task_module
from backend.core.observability import configure_logging
from backend.core.config import settings
from backend.services.async_task_service import AsyncTaskService
from backend.models.tables import AsyncTaskLog
from backend.services.rag_service import RAGService


def _wait_for_task(service: AsyncTaskService, task_id: int, timeout: float = 4.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = service.get_task(task_id)
        if task and task["status"] in {"success", "failed", "cancelled", "timeout"}:
            return task
        time.sleep(0.1)
    return service.get_task(task_id)


def test_async_task_service_retries_and_succeeds(session_factory, monkeypatch):
    monkeypatch.setattr(task_module, "SessionLocal", session_factory)
    monkeypatch.setattr(AsyncTaskService, "_build_redis_client", lambda self: None)

    service = AsyncTaskService()
    attempts = {"count": 0}

    def handler(payload):
        def runner(task_context):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("first attempt fails")
            task_context.update(progress=0.6, detail="retry success")
            return {"value": payload["value"]}

        return runner

    service.register_handler("unit_retry", handler)
    task_id = service.create_task(
        task_type="unit_retry",
        task_scope="student",
        owner_id=1,
        payload={"value": 7},
        detail="queued",
        max_attempts=2,
        timeout_seconds=30,
    )
    task = _wait_for_task(service, task_id)
    service.stop_worker()

    assert task is not None
    assert task["status"] == "success"
    assert task["attempt_count"] == 2
    assert task["result"]["value"] == 7


def test_async_task_service_cancel_queued_task(session_factory, monkeypatch):
    monkeypatch.setattr(task_module, "SessionLocal", session_factory)
    monkeypatch.setattr(AsyncTaskService, "_build_redis_client", lambda self: None)

    service = AsyncTaskService()
    monkeypatch.setattr(service, "start_worker", lambda: None)
    service.register_handler("unit_cancel", lambda payload: (lambda task_context: payload))
    task_id = service.create_task(
        task_type="unit_cancel",
        task_scope="student",
        owner_id=1,
        payload={"value": 9},
        detail="queued",
    )
    task = service.cancel_task(task_id, owner_id=1)

    assert task["status"] == "cancelled"
    assert task["cancel_requested"] is True


def test_async_task_service_does_not_recover_queued_tasks_on_startup(session_factory, monkeypatch):
    monkeypatch.setattr(task_module, "SessionLocal", session_factory)
    monkeypatch.setattr(AsyncTaskService, "_build_redis_client", lambda self: None)
    monkeypatch.setattr(task_module.settings, "TASK_RECOVER_QUEUED_ON_START", False, raising=False)

    db = session_factory()
    try:
        task = AsyncTaskLog(
            task_type="startup_skip",
            task_scope="student",
            owner_id=7,
            status="queued",
            progress=0.05,
            detail="queued before restart",
            payload_json='{"keyword":"Python 递归","question_type":"choice"}',
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
    finally:
        db.close()

    service = AsyncTaskService()
    service.register_handler("startup_skip", lambda payload: (lambda task_context: {"unexpected": True}))
    service.start_worker()
    time.sleep(0.2)
    snapshot = service.get_task(task_id)
    service.stop_worker()

    assert snapshot is not None
    assert snapshot["status"] == "failed"
    assert snapshot["attempt_count"] == 0
    assert "manual retry" in snapshot["detail"].lower()


def test_async_task_service_recovers_stale_running_tasks_on_startup(session_factory, monkeypatch):
    monkeypatch.setattr(task_module, "SessionLocal", session_factory)
    monkeypatch.setattr(AsyncTaskService, "_build_redis_client", lambda self: None)
    monkeypatch.setattr(task_module.settings, "TASK_RECOVERY_LOOKBACK_SEC", 15, raising=False)

    db = session_factory()
    try:
        task = AsyncTaskLog(
            task_type="startup_recover",
            task_scope="student",
            owner_id=9,
            status="running",
            progress=0.4,
            detail="interrupted",
            payload_json='{"keyword":"Python 递归","question_type":"choice"}',
            timeout_seconds=30,
            heartbeat_at=datetime.now() - timedelta(seconds=60),
            lease_expires_at=datetime.now() - timedelta(seconds=5),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
    finally:
        db.close()

    service = AsyncTaskService()
    service.register_handler("startup_recover", lambda payload: (lambda task_context: {"recovered": payload["keyword"]}))
    service.start_worker()
    snapshot = _wait_for_task(service, task_id)
    service.stop_worker()

    assert snapshot is not None
    assert snapshot["status"] == "success"
    assert snapshot["result"]["recovered"] == "Python 递归"
    assert snapshot["attempt_count"] == 1


def test_configure_logging_mutes_third_party_loggers_by_default(monkeypatch):
    monkeypatch.setattr(configure_logging, "_configured", False, raising=False)

    configure_logging("INFO", third_party_level="WARNING", verbose_llm_logs=False)
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("openai._base_client").level == logging.WARNING

    configure_logging("INFO", third_party_level="WARNING", verbose_llm_logs=True)
    assert logging.getLogger("httpx").level == logging.INFO
    assert logging.getLogger("openai._base_client").level == logging.INFO


def test_rag_runtime_config_reports_effective_state(monkeypatch):
    monkeypatch.setattr(RAGService, "_build_redis_client", lambda self: None)
    service = RAGService()
    service.index_path = "D:/demo/faiss_index_eval_docling"
    service.index_build_meta = {
        "requested_parser": "docling",
        "parser_usage": {"pypdf": 12},
    }
    service.fast_mode = True
    service.reranker = None

    runtime = service._build_runtime_config(
        requested_use_rerank=True,
        rerank_applied=False,
        fallback_reason="fast_mode",
    )

    assert runtime["requested"]["parser"] == "docling"
    assert runtime["effective"]["parser"] == "pypdf"
    assert runtime["effective"]["use_rerank"] is False
    assert runtime["fallback_reason"] == "fast_mode"


def test_rag_runtime_index_defaults_to_production_index(monkeypatch):
    monkeypatch.setattr(RAGService, "_build_redis_client", lambda self: None)
    monkeypatch.delenv("RAG_RUNTIME_INDEX_PATH", raising=False)
    monkeypatch.setenv("RAG_RUNTIME_PARSER_MODE", "docling")

    service = RAGService()

    assert service._resolve_index_path() == settings.FAISS_INDEX_DIR


def test_rag_index_info_includes_docling_signal(monkeypatch):
    monkeypatch.setattr(RAGService, "_build_redis_client", lambda self: None)
    service = RAGService()
    service.index_path = "D:/demo/faiss_index"
    service.index_build_meta = {
        "requested_parser": "docling",
        "parser_usage": {"docling": 9, "text": 1},
        "source_usage": {"lesson.pdf": 8, "notes.txt": 1},
        "source_build_stats": {
            "lesson.pdf": {
                "requested_parser": "docling",
                "actual_parser": "docling",
                "docling_strategy": "backend_only",
                "docling_pages_total": 10,
                "docling_pages_success": 9,
                "docling_chars": 900,
                "baseline_chars": 1000,
            },
            "fallback.pdf": {
                "requested_parser": "docling",
                "actual_parser": "pypdf",
                "docling_strategy": "fallback_to_pypdf",
                "docling_pages_total": 5,
                "docling_pages_success": 0,
                "docling_chars": 0,
                "baseline_chars": 500,
            },
        },
    }

    info = service._build_index_info()

    assert info["index_scope"] == "production"
    assert info["is_evaluation_index"] is False
    assert info["docling_requested_sources"] == 2
    assert info["docling_actual_sources"] == 1
    assert info["docling_fallback_sources"] == 1
    assert info["docling_strategy_breakdown"]["backend_only"] == 1
    assert info["docling_strategy_breakdown"]["fallback_to_pypdf"] == 1
    assert info["docling_page_ratio"] == 0.6
    assert info["docling_char_ratio"] == 0.6
