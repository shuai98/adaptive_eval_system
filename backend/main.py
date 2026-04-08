import os
import socket
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.core.config import settings
from backend.core.observability import configure_logging, get_logger, register_http_observability
from backend.services.async_task_service import async_task_service
from backend.services.rag_service import rag_service

os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"
os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT

configure_logging(
    settings.LOG_LEVEL,
    third_party_level=settings.THIRD_PARTY_LOG_LEVEL,
    verbose_llm_logs=settings.VERBOSE_LLM_LOGS,
)
logger = get_logger("adaptive.main")


def _runtime_rerank_enabled() -> bool:
    return os.getenv("RAG_FAST_MODE", "true").strip().lower() != "true"


def _print_startup_banner(port: int, local_ip: str) -> None:
    local_url = f"http://127.0.0.1:{port}/static/app/index.html?v=20260408u7#/login"
    lan_url = f"http://{local_ip}:{port}/static/app/index.html?v=20260408u7#/login"
    docs_url = f"http://127.0.0.1:{port}/docs"
    agent_url = f"http://127.0.0.1:{port}/api/query"
    parser_mode = os.getenv("RAG_PDF_PARSER", "docling").strip() or "docling"
    rerank_status = "ON" if _runtime_rerank_enabled() else "OFF (fast mode)"
    print("\n" + "=" * 78)
    print(" Adaptive Evaluation System | Runtime Ready ")
    print("-" * 78)
    print(f" Login Page : {local_url}")
    print(f" LAN URL    : {lan_url}")
    print(f" API Docs   : {docs_url}")
    print(f" Agent API  : {agent_url}")
    print(f" Parser     : {parser_mode}")
    print(f" Rerank     : {rerank_status}")
    print("=" * 78 + "\n")


def create_app() -> FastAPI:
    settings.validate_runtime()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        def _init_rag():
            try:
                rag_service.initialize()
            except Exception:
                logger.exception("rag_initialize_failed")

        threading.Thread(target=_init_rag, daemon=True).start()
        async_task_service.start_worker()

        port = 8088
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
            sock.close()
        except Exception:
            local_ip = "127.0.0.1"

        _print_startup_banner(port, local_ip)
        logger.info(
            "system_ready local_url=http://127.0.0.1:%s/static/app/index.html?v=20260408u7#/login lan_url=http://%s:%s/static/app/index.html?v=20260408u7#/login rerank_enabled=%s parser=%s",
            port,
            local_ip,
            port,
            _runtime_rerank_enabled(),
            os.getenv("RAG_PDF_PARSER", "docling").strip() or "docling",
        )
        yield
        async_task_service.stop_worker()
        logger.info("system_shutdown")

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )
    register_http_observability(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def disable_spa_cache(request, call_next):
        response = await call_next(request)
        path = request.url.path or ""
        if path.startswith("/static/app") or path.startswith("/static/common") or path.startswith("/static/student"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.include_router(api_router)

    frontend_dir = os.path.join(settings.BASE_DIR, "frontend")
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def root():
        return RedirectResponse(url="/static/app/index.html?v=20260408u7#/login")

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8088, reload=settings.RUN_RELOAD)
