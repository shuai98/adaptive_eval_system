from sqlalchemy.orm import Session

from backend.core.security import (
    create_access_token,
    get_password_hash,
    validate_password_strength,
    verify_password,
)
from backend.models.tables import User
from backend.schemas.common import AuthRequest


def _user_payload(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }


def register_user(request: AuthRequest, db: Session) -> dict[str, object]:
    if db.query(User).filter(User.username == request.username).first():
        raise ValueError("Username already exists.")

    if request.role == "admin":
        raise PermissionError("Admin registration is not allowed from the public endpoint.")

    validate_password_strength(request.password)

    new_user = User(
        username=request.username,
        password_hash=get_password_hash(request.password),
        role=request.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    user_payload = _user_payload(new_user)
    return {
        "status": "success",
        "user": user_payload,
        "user_id": new_user.id,
        "username": new_user.username,
        "role": new_user.role,
    }


def login_user(request: AuthRequest, db: Session) -> dict[str, object]:
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise LookupError("Invalid username or password.")

    if user.role != "admin" and user.role != request.role:
        raise PermissionError(f"Role mismatch. This account belongs to {user.role}.")

    access_token = create_access_token(user_id=user.id, username=user.username, role=user.role)
    user_payload = _user_payload(user)
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_payload,
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
    }
