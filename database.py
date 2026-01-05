from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. 配置 SQLite 数据库地址
SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"

# 2. 创建数据库引擎
# check_same_thread=False 是 SQLite 在 FastAPI 多线程环境下的必要配置
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 创建模型基类
Base = declarative_base()

# 5. --- 关键修复：定义 get_db 依赖函数 ---
# 这个函数负责打开数据库连接，并在请求结束后自动关闭
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()