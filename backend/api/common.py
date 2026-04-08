from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.common import AuthRequest
from backend.services.auth_service import login_user, register_user

router = APIRouter(tags=["common"])


@router.post("/register")
async def register(request: AuthRequest, db: Session = Depends(get_db)):
    try:
        return register_user(request, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/login")
async def login(request: AuthRequest, db: Session = Depends(get_db)):
    try:
        return login_user(request, db)
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
