import os
from database import engine, Base
from models import User
# 导入 passlib 进行密码加密
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def reset_database():
    print("正在重置数据库...")
    
    # 1. 如果存在旧数据库文件，建议先手动删除 app.db，或者这里强制覆盖表结构
    # drop_all 会删除所有由 Base 定义的表
    Base.metadata.drop_all(bind=engine)
    
    # 2. 创建新表
    Base.metadata.create_all(bind=engine)
    print("数据库表结构创建完成")

    # 3. 创建管理员账号 (admin / 123456)
    from database import SessionLocal
    db = SessionLocal()
    
    # 检查 admin 是否存在
    if not db.query(User).filter(User.username == "admin").first():
        admin_user = User(
            username="admin",
            password_hash=pwd_context.hash("123456"), # 加密存储
            role="teacher"
        )
        db.add(admin_user)
        db.commit()
        print("管理员账号创建成功: admin / 123456")
    
    db.close()

if __name__ == "__main__":
    reset_database()