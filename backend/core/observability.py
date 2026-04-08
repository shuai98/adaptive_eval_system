import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        return True


def _coerce_log_level(level: str, default: int = logging.INFO) -> int:
    return getattr(logging, str(level or "").upper(), default)


def _configure_library_loggers(level: str, verbose_llm_logs: bool = False) -> None:
    effective_level = logging.INFO if verbose_llm_logs else _coerce_log_level(level, logging.WARNING)
    for logger_name in ("httpx", "httpcore", "openai", "openai._base_client"):
        logging.getLogger(logger_name).setLevel(effective_level)


def configure_logging(
    level: str = "INFO",
    *,
    third_party_level: str = "WARNING",
    verbose_llm_logs: bool = False,
) -> None:
    root = logging.getLogger()
    if not getattr(configure_logging, "_configured", False):
        logging.basicConfig(
            level=_coerce_log_level(level, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
        )
        request_filter = RequestIdFilter()
        for handler in root.handlers:
            handler.addFilter(request_filter)
        configure_logging._configured = True
    else:
        root.setLevel(_coerce_log_level(level, logging.INFO))

    _configure_library_loggers(third_party_level, verbose_llm_logs=verbose_llm_logs)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def register_http_observability(app: FastAPI) -> None:
    logger = get_logger("adaptive.http")

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.exception(
                "request_failed method=%s path=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                duration_ms,
            )
            request_id_ctx.reset(token)
            raise

        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        request_id_ctx.reset(token)
        return response
