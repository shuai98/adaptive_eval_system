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

# 初始化数据库
Base.metadata.create_all(bind=engine)

# 设置环境变量
os.environ['HF_ENDPOINT'] = settings.HF_ENDPOINT

def create_app() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

    # 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 启动事件
    # 1. 定义生命周期逻辑
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- [Startup: 应用启动前执行] ---
        # 1. 初始化 RAG 服务（加载模型、读取 FAISS 索引）
        rag_service.initialize()

        # 2. 打印访问链接（你的原有逻辑）
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
        print("="*60 + "\n")

        yield  # 运行分界点，应用在这里保持运行

        # --- [Shutdown: 应用关闭前执行] ---
        print("正在关闭系统，清理资源...")
        # 如果以后有数据库连接或临时文件，可以在这里清理

    # 2. 初始化 FastAPI 并注入 lifespan
    app = FastAPI(lifespan=lifespan)

    # 注册路由
    app.include_router(api_router)

    # 静态文件
    # 使用 settings 里的路径，更稳健
    frontend_dir = os.path.join(settings.BASE_DIR, "frontend")

    # ... 在 create_app 函数里 ...

    # 4. 挂载静态文件
    frontend_dir = os.path.join(settings.BASE_DIR, "frontend")
    

    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def root():
        return RedirectResponse(url="/static/login.html")

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8088, reload=True)