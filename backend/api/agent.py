from fastapi import APIRouter, Depends, HTTPException

from backend.core.auth import AuthenticatedUser, get_current_user
from backend.schemas.agent import QueryRequest, QueryResponse
from backend.services.agent_service import answer_query

router = APIRouter()


@router.post("/query", response_model=QueryResponse, tags=["Agent"])
async def agent_query(
    request: QueryRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    _ = current_user
    try:
        return await answer_query(request)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(exc)}") from exc
