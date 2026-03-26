import os
# 这告诉程序：访问本机地址时，不要走代理！
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,0.0.0.0'
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.db.session import engine, Base
from backend.services.rag_service import rag_service
from backend.api.router import api_router
from backend.core.config import settings

import socket
from contextlib import asynccontextmanager
import threading

# 初始化数据库
Base.metadata.create_all(bind=engine)

# 设置环境变量
os.environ['HF_ENDPOINT'] = settings.HF_ENDPOINT

def create_app() -> FastAPI:
    # 1. 定义生命周期逻辑
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- [Startup: 应用启动前执行] ---
        # 1. 初始化 RAG 服务（加载模型、读取 FAISS 索引）
        def _init_rag():
            try:
                rag_service.initialize()
            except Exception as e:
                print(f"[Warning] RAG initialize failed: {e}")

        threading.Thread(target=_init_rag, daemon=True).start()

        # 2. 打印访问链接
        port = 8088 
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"

        print("\n" + "="*60)
        print("   自适应测评系统后端已启动 | System Ready (V5 Refactored)")
        print("-" * 60)
        print(f"   登录页面: http://127.0.0.1:{port}/static/login.html")
        print(f"   局域网访问: http://{local_ip}:{port}/static/login.html")
        print(f"   API 文档: http://127.0.0.1:{port}/docs")
        print(f"   Agent 接口: http://127.0.0.1:{port}/api/query")
        print("="*60 + "\n")

        yield  # 运行分界点，应用在这里保持运行

        # --- [Shutdown: 应用关闭前执行] ---
        print("正在关闭系统，清理资源...")

    # 2. 初始化 FastAPI 并注入 lifespan
    app = FastAPI(
        title=settings.PROJECT_NAME, 
        version=settings.VERSION,
        lifespan=lifespan
    )

    # 3. 配置 CORS 中间件（允许 Agent 项目跨域访问）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8001",      # Agent 项目端口
            "http://127.0.0.1:8001",
            "http://localhost:8088",      # 本项目端口
            "http://127.0.0.1:8088",
            "*"                           # 开发环境允许所有来源
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. 注册路由
    app.include_router(api_router)

    # 5. 挂载静态文件
    frontend_dir = os.path.join(settings.BASE_DIR, "frontend")
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    # 6. 根路径重定向
    @app.get("/")
    async def root():
        return RedirectResponse(url="/static/login.html")

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8088, reload=True)