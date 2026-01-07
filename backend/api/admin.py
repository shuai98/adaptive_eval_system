from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.rag_service import rag_service

router = APIRouter(prefix="/admin", tags=["管理端"])

class TestRetrievalRequest(BaseModel):
    keyword: str

@router.post("/test_retrieval")
async def test_retrieval(request: TestRetrievalRequest):
    try:
        # 调用 RAG 服务，只检索不生成
        search_result = rag_service.search(request.keyword, top_k=3)
        
        return {
            "status": "success",
            "data": {
                "raw_docs": search_result["raw_docs"],
                "rerank_docs": search_result["rerank_docs"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))