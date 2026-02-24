import sys
import os

# 路径修正
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from backend.db.session import engine, Base, SessionLocal
# 必须导入 tables，否则 Base 找不到表定义
from backend.models.tables import User, Document, ExamRecord, QuestionHistory
from backend.core.security import get_password_hash

def init_db():
    print("⚙️ 正在连接 MySQL 并初始化表结构...")
    
    # 1. 建表 (如果表不存在则创建)
    Base.metadata.create_all(bind=engine)
    print(" 数据库表结构同步完成。")

    # 2. 创建默认管理员 (root / 123456)
    db = SessionLocal()
    if not db.query(User).filter(User.username == "root").first():
        print("👤 正在创建管理员账号...")
        admin = User(
            username="root",
            password_hash=get_password_hash("123456"),
            role="admin"
        )
        db.add(admin)
        db.commit()
        print(" 管理员创建成功: root / 123456")
    else:
        print("ℹ 管理员账号已存在，跳过创建。")
    
    db.close()

if __name__ == "__main__":
    init_db()