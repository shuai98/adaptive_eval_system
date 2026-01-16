from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.rag_service import rag_service
from backend.services.llm_service import llm_service
from backend.services.metrics.timer import RequestTimer # 刚刚创建的计时器
from backend.services.metrics.ragas_service import ragas_service

router = APIRouter(prefix="/admin", tags=["管理端模块"])

class TestRequest(BaseModel):
    keyword: str

@router.post("/debug_generation")
async def debug_generation(request: TestRequest):
    """
    研发专用：全链路生成测试 (带性能日志)
    """
    timer = RequestTimer()
    timer.mark("start")
    
    try:
        print(f"[Admin] Debugging keyword: {request.keyword}")

        # 1. RAG 检索 (模拟分步计时)
        # 注意：rag_service.search 内部是一起做的，为了计时我们这里逻辑上拆分一下
        # 实际耗时主要在 search 这一步
        search_result = rag_service.search(request.keyword, top_k=3)
        
        # 这里的计时只是近似值，因为 search 函数内部已经把 recall 和 rerank 做完了
        # 为了日志好看，我们假设 search 的前半段时间是 recall，后半段是 rerank
        # (在真实生产环境中，应该在 rag_service 内部打点)
        timer.mark("after_recall") 
        timer.mark("after_rerank") 

        context = "\n\n".join([doc.page_content for doc in search_result["final_docs"]])
        
        # 2. LLM 生成
        content = await llm_service.generate_quiz(
            request.keyword, 
            context, 
            difficulty="中等", 
            question_type="choice"
        )
        timer.mark("after_llm")
        
        # 3. 生成日志
        log_str = timer.generate_log()
        print(f"[Admin] Log: {log_str}")
        
        return {
            "status": "success",
            "data": {
                "generated_content": content,
                "debug_info": {
                    "raw_docs": search_result["raw_docs"],
                    "rerank_docs": search_result["rerank_docs"],
                    "timing_log": log_str
                }
            }
        }
    except Exception as e:
        print(f"[Admin Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/run_ragas_eval")
async def run_ragas_eval():
    """
    触发 RAGAS 自动化评测
    """
    try:
        # 注意：RAGAS 运行较慢，生产环境应使用 BackgroundTasks
        # 这里为了演示方便，直接 await 等待结果
        scores = await ragas_service.run_evaluation()
        
        if "error" in scores:
            raise HTTPException(status_code=404, detail=scores["error"])
            
        return {
            "status": "success",
            "data": scores
        }
    except Exception as e:
        print(f"RAGAS Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))