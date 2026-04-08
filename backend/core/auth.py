from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.core.security import decode_access_token
from backend.db.session import get_db
from backend.models.tables import User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    id: int
    username: str
    role: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if user.role != payload.get("role"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token role mismatch.")
    return AuthenticatedUser(id=user.id, username=user.username, role=user.role)


def _require_roles(current_user: AuthenticatedUser, allowed_roles: set[str]) -> AuthenticatedUser:
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    return current_user


def get_current_student(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    return _require_roles(current_user, {"student"})


def get_current_teacher(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    return _require_roles(current_user, {"teacher", "admin"})


def get_current_admin(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    current_user = _require_roles(current_user, {"admin"})
    if current_user.username != "root":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only root can access the admin lab.",
        )
    return current_user
