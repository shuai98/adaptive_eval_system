from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
# 引入核心配置
from backend.core.config import settings

# 1. 使用配置中的路径
SQLALCHEMY_DATABASE_URL = f"sqlite:///{settings.DB_PATH}"

# 2. 创建数据库引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 创建模型基类
Base = declarative_base()

# 5. 依赖函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()