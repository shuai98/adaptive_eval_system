from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any, Callable, Dict, Optional

import redis

from backend.core.config import settings
from backend.core.observability import get_logger
from backend.db.session import SessionLocal
from backend.models.tables import AsyncTaskLog

TaskHandler = Callable[[Dict[str, Any]], Callable[["TaskContext"], Any]]

logger = get_logger("adaptive.tasks")
_PAYLOAD_SUMMARY_KEYS = (
    "keyword",
    "question_type",
    "difficulty",
    "student_id",
    "question_id",
    "record_id",
    "triggered_by",
)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: Optional[str]) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _trim_for_summary(value: Any, max_length: int = 80) -> Any:
    if isinstance(value, str) and len(value) > max_length:
        return f"{value[: max_length - 3]}..."
    return value


def _summarize_payload(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    summary: Dict[str, Any] = {}
    for key in _PAYLOAD_SUMMARY_KEYS:
        if key in payload and payload[key] not in (None, "", [], {}):
            summary[key] = _trim_for_summary(payload[key])
    return summary


def _is_load_test_active() -> bool:
    raw = os.getenv("LOAD_TEST_ACTIVE")
    if raw is None:
        return settings.LOAD_TEST_ACTIVE
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _should_drop_load_test_task(payload: Dict[str, Any]) -> bool:
    if not settings.LOAD_TEST_DROP_ON_IDLE:
        return False
    if not payload or not isinstance(payload, dict):
        return False
    if payload.get("triggered_by") != settings.LOAD_TEST_TRIGGER_VALUE:
        return False
    return not _is_load_test_active()


class TaskContext:
    def __init__(self, service: "AsyncTaskService", task_id: int):
        self.service = service
        self.task_id = task_id

    def update(
        self,
        progress: Optional[float] = None,
        detail: Optional[str] = None,
        result: Any = None,
    ) -> None:
        self.service.update_task(self.task_id, progress=progress, detail=detail, result=result, heartbeat=True)

    def is_cancel_requested(self) -> bool:
        task = self.service.get_task(self.task_id)
        return bool(task and task.get("cancel_requested"))


class AsyncTaskService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._stop_event = Event()
        self._worker_thread: Thread | None = None
        self._local_queue: Queue[int] = Queue()
        self._handlers: Dict[str, TaskHandler] = {}
        self.redis_client = self._build_redis_client()

    def _build_redis_client(self):
        try:
            client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
            client.ping()
            logger.info("task_queue_backend=redis connected=1 queue=%s", settings.TASK_QUEUE_NAME)
            return client
        except Exception as exc:
            logger.warning("task_queue_backend=memory connected=0 reason=%s", exc)
            return None

    def register_handler(self, task_type: str, handler: TaskHandler) -> None:
        self._handlers[task_type] = handler

    def start_worker(self) -> None:
        with self._lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._recover_pending_tasks()
            self._worker_thread = Thread(target=self._worker_loop, name="adaptive-task-worker", daemon=True)
            self._worker_thread.start()
            logger.info("task_worker_started")

    def stop_worker(self) -> None:
        self._stop_event.set()
        if self.redis_client is None:
            self._local_queue.put(-1)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3)
        logger.info("task_worker_stopped")

    def create_task(
        self,
        task_type: str,
        task_scope: str,
        owner_id: Optional[int],
        payload: Optional[Dict[str, Any]],
        detail: str = "Task queued.",
        *,
        max_attempts: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> int:
        self.start_worker()
        db = SessionLocal()
        try:
            task = AsyncTaskLog(
                task_type=task_type,
                task_scope=task_scope,
                owner_id=owner_id,
                status="queued",
                progress=0.05,
                detail=detail,
                payload_json=_json_dumps(payload or {}),
                max_attempts=max_attempts or settings.TASK_DEFAULT_MAX_ATTEMPTS,
                timeout_seconds=timeout_seconds or settings.TASK_DEFAULT_TIMEOUT_SEC,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            task_id = task.id
        finally:
            db.close()

        self._enqueue_task(task_id)
        logger.info(
            "task_created task_id=%s task_type=%s task_scope=%s owner_id=%s payload_summary=%s",
            task_id,
            task_type,
            task_scope,
            owner_id,
            _json_dumps(_summarize_payload(payload or {})),
        )
        return task_id

    def cancel_task(self, task_id: int, owner_id: Optional[int] = None) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            task = db.query(AsyncTaskLog).filter(AsyncTaskLog.id == task_id).first()
            if task is None:
                raise KeyError(task_id)
            if owner_id is not None and task.owner_id not in {None, owner_id}:
                raise PermissionError(task_id)
            task.cancel_requested = True
            if task.status in {"queued", "retrying"}:
                task.status = "cancelled"
                task.detail = "Task cancelled before execution."
                task.finished_at = datetime.now()
                task.progress = 1.0
            db.commit()
        finally:
            db.close()
        return self.get_task(task_id) or {}

    def _enqueue_task(self, task_id: int) -> None:
        if self.redis_client is not None:
            self.redis_client.rpush(settings.TASK_QUEUE_NAME, str(task_id))
            return
        self._local_queue.put(task_id)

    def _dequeue_task(self) -> Optional[int]:
        if self.redis_client is not None:
            result = self.redis_client.blpop(settings.TASK_QUEUE_NAME, timeout=settings.TASK_POLL_INTERVAL_SEC)
            if result is None:
                return None
            _, raw_task_id = result
            return int(raw_task_id)
        try:
            task_id = self._local_queue.get(timeout=settings.TASK_POLL_INTERVAL_SEC)
            return None if task_id == -1 else int(task_id)
        except Empty:
            return None

    def _recover_pending_tasks(self) -> None:
        db = SessionLocal()
        try:
            now = datetime.now()
            recover_before = now - timedelta(seconds=settings.TASK_RECOVERY_LOOKBACK_SEC)
            rows = (
                db.query(AsyncTaskLog)
                .filter(AsyncTaskLog.status.in_(("queued", "running", "retrying")))
                .all()
            )
            for row in rows:
                previous_status = row.status
                payload = _json_loads(row.payload_json)
                payload_summary = _json_dumps(_summarize_payload(payload))
                expired = row.lease_expires_at is not None and row.lease_expires_at <= now
                stale_running = previous_status == "running" and (row.heartbeat_at or row.started_at or row.created_at) <= recover_before
                should_recover_running = previous_status == "running" and (expired or stale_running)
                if previous_status == "queued" and not settings.TASK_RECOVER_QUEUED_ON_START:
                    row.status = "failed"
                    row.detail = "Task remained queued during startup and now requires manual retry."
                    row.error_message = "Startup skipped automatic recovery for a queued task."
                    row.finished_at = now
                    row.lease_expires_at = None
                    row.progress = 1.0
                    db.commit()
                    logger.warning(
                        "task_startup_skip task_id=%s task_type=%s task_scope=%s owner_id=%s previous_status=%s payload_summary=%s",
                        row.id,
                        row.task_type,
                        row.task_scope,
                        row.owner_id,
                        "queued",
                        payload_summary,
                    )
                    continue
                if previous_status == "retrying" and not settings.TASK_RECOVER_RETRYING_ON_START:
                    row.status = "failed"
                    row.detail = "Task was waiting to retry during startup and now requires manual retry."
                    row.error_message = row.error_message or "Startup skipped automatic recovery for a retrying task."
                    row.finished_at = now
                    row.lease_expires_at = None
                    row.progress = 1.0
                    db.commit()
                    logger.warning(
                        "task_startup_skip task_id=%s task_type=%s task_scope=%s owner_id=%s previous_status=%s payload_summary=%s",
                        row.id,
                        row.task_type,
                        row.task_scope,
                        row.owner_id,
                        "retrying",
                        payload_summary,
                    )
                    continue
                if previous_status in {"queued", "retrying"} or should_recover_running:
                    row.status = "queued"
                    row.detail = "Task recovered on startup and re-queued."
                    row.progress = min(float(row.progress or 0.0), 0.1)
                    row.lease_expires_at = None
                    row.finished_at = None
                    db.commit()
                    self._enqueue_task(row.id)
                    logger.info(
                        "task_recovered task_id=%s task_type=%s task_scope=%s owner_id=%s previous_status=%s payload_summary=%s",
                        row.id,
                        row.task_type,
                        row.task_scope,
                        row.owner_id,
                        previous_status,
                        payload_summary,
                    )
        finally:
            db.close()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            task_id = self._dequeue_task()
            if task_id is None:
                continue
            try:
                self._execute_task(task_id)
            except Exception:
                logger.exception("task_worker_error task_id=%s", task_id)

    def _execute_task(self, task_id: int) -> None:
        db = SessionLocal()
        try:
            task = db.query(AsyncTaskLog).filter(AsyncTaskLog.id == task_id).first()
            if task is None:
                return
            if settings.TASK_STALE_SEC and task.created_at:
                stale_before = datetime.now() - timedelta(seconds=int(settings.TASK_STALE_SEC))
                if task.status in {"queued", "retrying"} and task.created_at <= stale_before:
                    task.status = "failed"
                    task.detail = "Task expired before execution."
                    task.error_message = "Task dropped as stale."
                    task.finished_at = datetime.now()
                    task.progress = 1.0
                    db.commit()
                    logger.warning("task_stale_drop task_id=%s task_type=%s", task_id, task.task_type)
                    return
            if task.cancel_requested:
                task.status = "cancelled"
                task.detail = "Task cancelled."
                task.progress = 1.0
                task.finished_at = datetime.now()
                db.commit()
                return

            handler_factory = self._handlers.get(task.task_type)
            if handler_factory is None:
                task.status = "failed"
                task.detail = "No task handler registered."
                task.error_message = f"Missing handler for task_type={task.task_type}"
                task.finished_at = datetime.now()
                task.progress = 1.0
                db.commit()
                return

            payload = {}
            if task.payload_json:
                payload = json.loads(task.payload_json)
            if _should_drop_load_test_task(payload):
                task.status = "failed"
                task.detail = "Load test ended; task dropped."
                task.error_message = "Dropped queued load-test task because LOAD_TEST_ACTIVE is false."
                task.finished_at = datetime.now()
                task.progress = 1.0
                db.commit()
                logger.warning("task_load_test_drop task_id=%s task_type=%s", task_id, task.task_type)
                return
            payload_summary = _json_dumps(_summarize_payload(payload))

            task.attempt_count = int(task.attempt_count or 0) + 1
            task.status = "running"
            task.detail = "Task is running."
            task.started_at = task.started_at or datetime.now()
            task.heartbeat_at = datetime.now()
            task.lease_expires_at = datetime.now() + timedelta(seconds=int(task.timeout_seconds or settings.TASK_DEFAULT_TIMEOUT_SEC))
            task.progress = max(float(task.progress or 0.0), 0.12)
            db.commit()
            task_type = task.task_type
            task_scope = task.task_scope
            owner_id = task.owner_id
            attempt_count = task.attempt_count
            timeout_seconds = int(task.timeout_seconds or settings.TASK_DEFAULT_TIMEOUT_SEC)
        finally:
            db.close()

        logger.info(
            "task_started task_id=%s task_type=%s task_scope=%s owner_id=%s attempt=%s payload_summary=%s",
            task_id,
            task_type,
            task_scope,
            owner_id,
            attempt_count,
            payload_summary,
        )
        runner = handler_factory(payload)
        context = TaskContext(self, task_id)
        started_at = time.perf_counter()

        try:
            result = runner(context)
            duration_ms = (time.perf_counter() - started_at) * 1000
            if duration_ms > timeout_seconds * 1000:
                self.update_task(
                    task_id,
                    status="timeout",
                    progress=1.0,
                    detail="Task exceeded the configured timeout.",
                    error_message=f"Timed out after {duration_ms:.0f}ms",
                    finished=True,
                    heartbeat=True,
                )
                logger.warning("task_timeout task_id=%s task_type=%s duration_ms=%.1f", task_id, task_type, duration_ms)
                return

            self.update_task(
                task_id,
                status="success",
                progress=1.0,
                detail="Task completed successfully.",
                result=result,
                finished=True,
                heartbeat=True,
            )
            logger.info("task_completed task_id=%s task_type=%s duration_ms=%.1f", task_id, task_type, duration_ms)
        except Exception as exc:
            db = SessionLocal()
            try:
                task = db.query(AsyncTaskLog).filter(AsyncTaskLog.id == task_id).first()
                if task is None:
                    return
                task.error_message = f"{type(exc).__name__}: {exc}"
                task.heartbeat_at = datetime.now()
                if task.cancel_requested:
                    task.status = "cancelled"
                    task.detail = "Task cancelled."
                    task.finished_at = datetime.now()
                    task.progress = 1.0
                elif int(task.attempt_count or 0) < int(task.max_attempts or settings.TASK_DEFAULT_MAX_ATTEMPTS):
                    task.status = "retrying"
                    task.detail = "Task failed and is queued for retry."
                    task.progress = min(float(task.progress or 0.0), 0.3)
                    task.lease_expires_at = None
                else:
                    task.status = "failed"
                    task.detail = "Task failed."
                    task.finished_at = datetime.now()
                    task.progress = 1.0
                db.commit()
                should_retry = task.status == "retrying"
            finally:
                db.close()

            if should_retry:
                self._enqueue_task(task_id)
                logger.warning("task_retry task_id=%s task_type=%s error=%s", task_id, task_type, exc)
            else:
                logger.exception("task_failed task_id=%s task_type=%s", task_id, task_type)

    def update_task(
        self,
        task_id: int,
        *,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        detail: Optional[str] = None,
        result: Any = None,
        error_message: Optional[str] = None,
        started: bool = False,
        finished: bool = False,
        heartbeat: bool = False,
    ) -> None:
        with self._lock:
            db = SessionLocal()
            try:
                task = db.query(AsyncTaskLog).filter(AsyncTaskLog.id == task_id).first()
                if task is None:
                    return
                if status is not None:
                    task.status = status
                if progress is not None:
                    task.progress = float(progress)
                if detail is not None:
                    task.detail = detail
                if result is not None:
                    task.result_json = _json_dumps(result)
                if error_message is not None:
                    task.error_message = error_message
                if started and task.started_at is None:
                    task.started_at = datetime.now()
                if heartbeat:
                    task.heartbeat_at = datetime.now()
                    if status == "running":
                        task.lease_expires_at = datetime.now() + timedelta(seconds=int(task.timeout_seconds or settings.TASK_DEFAULT_TIMEOUT_SEC))
                if finished:
                    task.finished_at = datetime.now()
                    task.lease_expires_at = None
                db.commit()
            finally:
                db.close()

    def _serialize_task(
        self,
        task: AsyncTaskLog,
        *,
        include_payload: bool = True,
        include_result: bool = True,
    ) -> Dict[str, Any]:
        payload = _json_loads(task.payload_json)
        result = _json_loads(task.result_json)
        payload_summary = _summarize_payload(payload)
        return {
            "task_id": task.id,
            "task_type": task.task_type,
            "task_scope": task.task_scope,
            "owner_id": task.owner_id,
            "status": task.status,
            "progress": round(float(task.progress or 0.0), 2),
            "detail": task.detail,
            "payload": payload if include_payload else None,
            "payload_summary": payload_summary,
            "result": result if include_result else None,
            "error_message": task.error_message,
            "attempt_count": int(task.attempt_count or 0),
            "max_attempts": int(task.max_attempts or 0),
            "timeout_seconds": int(task.timeout_seconds or 0),
            "cancel_requested": bool(task.cancel_requested),
            "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
            "started_at": task.started_at.strftime("%Y-%m-%d %H:%M:%S") if task.started_at else None,
            "heartbeat_at": task.heartbeat_at.strftime("%Y-%m-%d %H:%M:%S") if task.heartbeat_at else None,
            "lease_expires_at": task.lease_expires_at.strftime("%Y-%m-%d %H:%M:%S") if task.lease_expires_at else None,
            "finished_at": task.finished_at.strftime("%Y-%m-%d %H:%M:%S") if task.finished_at else None,
        }

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            task = db.query(AsyncTaskLog).filter(AsyncTaskLog.id == task_id).first()
            if task is None:
                return None
            return self._serialize_task(task, include_payload=True, include_result=True)
        finally:
            db.close()

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        owner_id: Optional[int] = None,
        task_scope: Optional[str] = None,
        limit: int = 50,
    ) -> list[Dict[str, Any]]:
        db = SessionLocal()
        try:
            query = db.query(AsyncTaskLog)
            if status:
                query = query.filter(AsyncTaskLog.status == status)
            if task_type:
                query = query.filter(AsyncTaskLog.task_type == task_type)
            if owner_id is not None:
                query = query.filter(AsyncTaskLog.owner_id == owner_id)
            if task_scope:
                query = query.filter(AsyncTaskLog.task_scope == task_scope)
            rows = (
                query.order_by(AsyncTaskLog.created_at.desc(), AsyncTaskLog.id.desc())
                .limit(max(1, min(int(limit), 200)))
                .all()
            )
            return [self._serialize_task(row, include_payload=False, include_result=False) for row in rows]
        finally:
            db.close()


async_task_service = AsyncTaskService()
