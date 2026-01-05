from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import User
from passlib.context import CryptContext

router = APIRouter(tags=["通用模块"])

# 配置密码加密上下文
# 使用 pbkdf2_sha256 算法，避免 bcrypt 的 72 字节长度限制
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# 定义请求体模型
class AuthRequest(BaseModel):
    username: str
    password: str

@router.post("/register")
async def register(request: AuthRequest, db: Session = Depends(get_db)):
    """
    用户注册接口
    """
    # 1. 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 2. 确定角色 (仅供演示：用户名为 admin 时自动设为教师)
    role = "teacher" if request.username == "admin" else "student"
    
    # 3. 创建新用户 (密码加密存储)
    hashed_password = pwd_context.hash(request.password)
    
    new_user = User(
        username=request.username,
        password_hash=hashed_password,
        role=role
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "status": "success",
        "message": "注册成功",
        "user_id": new_user.id,
        "username": new_user.username,
        "role": new_user.role
    }

@router.post("/login")
async def login(request: AuthRequest, db: Session = Depends(get_db)):
    """
    用户登录接口
    """
    # 1. 查询用户
    user = db.query(User).filter(User.username == request.username).first()
    
    # 2. 验证用户是否存在以及密码是否正确
    if not user or not pwd_context.verify(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    return {
        "status": "success",
        "message": "登录成功",
        "user_id": user.id,
        "username": user.username,
        "role": user.role
    }