from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.db.session import get_db
from backend.models.tables import User
from backend.core.security import get_password_hash, verify_password

router = APIRouter(tags=["通用模块"])

# 定义注册请求模型，增加 role 字段
class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "student"  # 默认为学生

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # 1. 检查用户名
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 2. 安全校验：防止有人恶意注册成 admin
    if request.role == "admin":
        raise HTTPException(status_code=403, detail="管理员账号禁止注册")
    
    # 3. 创建用户
    hashed_password = get_password_hash(request.password)
    
    new_user = User(
        username=request.username,
        password_hash=hashed_password,
        role=request.role # 使用前端传来的角色
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "status": "success",
        "user_id": new_user.id,
        "username": new_user.username,
        "role": new_user.role
    }

@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    return {
        "status": "success",
        "user_id": user.id,
        "username": user.username,
        "role": user.role
    }