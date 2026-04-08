from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.core.config import settings

# 1. 使用 MySQL 连接字符串
SQLALCHEMY_DATABASE_URL = settings.SQLALCHEMY_DATABASE_URL

# 2. 创建引擎
# pool_pre_ping=True: 自动检测断开的连接并重连 (MySQL 必备)
# pool_recycle=3600: 每小时回收连接，防止 MySQL 8小时超时断开
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_pre_ping=True,
    pool_recycle=3600
)

# 3. 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 模型基类
Base = declarative_base()

# 5. 依赖注入函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
