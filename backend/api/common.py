from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.db.session import get_db
from backend.models.tables import User
from backend.core.security import get_password_hash, verify_password

router = APIRouter(tags=["通用模块"])

class AuthRequest(BaseModel):
    username: str
    password: str
    role: str = "student"

@router.post("/register")
async def register(request: AuthRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == request.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    if request.role == "admin":
        raise HTTPException(status_code=403, detail="禁止注册管理员")
    
    new_user = User(
        username=request.username,
        password_hash=get_password_hash(request.password),
        role=request.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"status": "success", "user_id": new_user.id, "username": new_user.username, "role": new_user.role}

@router.post("/login")
async def login(request: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 角色校验：防止学生登教师端
    if user.role != "admin" and user.role != request.role:
        raise HTTPException(status_code=403, detail=f"身份不匹配！该账号是 {user.role}")
    
    return {"status": "success", "user_id": user.id, "username": user.username, "role": user.role}