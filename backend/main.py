import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.db.session import engine, Base
from backend.services.rag_service import rag_service
from backend.api.router import api_router
from backend.core.config import settings

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
    @app.on_event("startup")
    async def startup_event():
        rag_service.initialize()

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