import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import student, teacher, common # 引入 common

# 导入数据库 (确保表被创建)
from database import engine, Base
# 导入路由
from routers import student, teacher
# 导入服务
from services.rag_service import rag_service

# 1. 自动创建数据库表
Base.metadata.create_all(bind=engine)

# 2. 加载环境变量
load_dotenv()
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

app = FastAPI(title="自适应测评系统 V3")

# 3. 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. 启动事件：初始化 RAG 服务
@app.on_event("startup")
async def startup_event():
    # 这里会加载 1GB 的模型，只需加载一次
    rag_service.initialize()

# 5. 注册路由模块
app.include_router(student.router)
app.include_router(teacher.router)

# 注册 common 路由
app.include_router(common.router) 

@app.get("/")
def root():
    return {"message": "System is running", "version": "3.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)