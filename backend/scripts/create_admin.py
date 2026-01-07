import sys
import os

# 将项目根目录加入路径，防止报错 ModuleNotFoundError
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from backend.db.session import SessionLocal
from backend.models.tables import User
from backend.core.security import get_password_hash

def create_admin_user():
    db = SessionLocal()
    
    username = "root"
    password = "123456"
    
    # 1. 检查是否已存在
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        print(f"❌ 管理员账号 '{username}' 已存在，无需创建。")
        return

    # 2. 创建管理员
    print(f"⚙️ 正在创建管理员账号: {username} ...")
    admin_user = User(
        username=username,
        password_hash=get_password_hash(password),
        role="admin"  # <--- 关键：角色设为 admin
    )
    
    db.add(admin_user)
    db.commit()
    print(f"✅ 管理员创建成功！")
    print(f"👉 账号: {username}")
    print(f"👉 密码: {password}")
    
    db.close()

if __name__ == "__main__":
    create_admin_user()