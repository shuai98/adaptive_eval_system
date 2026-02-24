import time
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 引入服务
from backend.services.rag_service import rag_service
from backend.services.llm_service import llm_service
# 引入评测服务
from backend.services.metrics.ragas_service import ragas_service
# 引入压测服务 (如果你还没创建这个文件，请看下面的说明，暂时注释掉也可以)
from backend.services.metrics.stress_service import stress_service

router = APIRouter(prefix="/admin", tags=["管理端模块"])

# --- 请求模型 ---
class TestRequest(BaseModel):
    keyword: str

class StressConfig(BaseModel):
    user_count: int
    spawn_rate: int

# ==========================================
# 1. 调试接口 (修复了计时逻辑)
# ==========================================
@router.post("/debug_generation")
async def debug_generation(request: TestRequest):
    """
    研发专用：全链路生成测试 (使用内部精准计时)
    """
    # 总计时开始
    t_start = time.time()
    
    try:
        print(f"[Admin] Debugging keyword: {request.keyword}")

        # 1. RAG 检索
        # 注意：rag_service.search 内部已经计算了精准的 recall 和 rerank 时间
        search_result = rag_service.search(request.keyword, top_k=3)
        
        # 获取内部计时数据 (例如: {'recall': '120ms', 'rerank': '450ms'})
        # 使用 .get 防止旧代码没返回 timings 导致报错
        rag_timings = search_result.get("timings", {"recall": "0ms", "rerank": "0ms"})

        # 准备上下文
        # 兼容处理：如果是字符串列表直接 join
        docs = search_result["final_docs"]
        if docs and isinstance(docs[0], str):
            context = "\n\n".join(docs)
        else:
            # 万一还是 Document 对象
            context = "\n\n".join([d.page_content for d in docs])
        
        # 2. LLM 生成 (单独计时)
        t_llm_start = time.time()
        content = await llm_service.generate_quiz(
            request.keyword, 
            context, 
            difficulty="中等", 
            question_type="choice"
        )
        t_llm_end = time.time()
        llm_duration = t_llm_end - t_llm_start
        
        # 3. 总耗时
        total_duration = time.time() - t_start
        
        # 4. 组装日志字符串
        # 直接使用 rag_service 返回的精准时间
        log_str = (
            f"[Timing] embedding recall: {rag_timings.get('recall', '0ms')} "
            f"[Timing] rerank: {rag_timings.get('rerank', '0ms')} "
            f"[Timing] llm generation: {llm_duration:.2f}s "
            f"[Timing] total: {total_duration:.2f}s"
        )
        
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

# ==========================================
# 1.5. 流式调试接口 (新增)
# ==========================================
@router.post("/debug_generation_stream")
async def debug_generation_stream(request: TestRequest):
    """
    研发专用：流式全链路生成测试
    """
    try:
        print(f"[Admin Stream] Debugging keyword: {request.keyword}")
        
        # 1. RAG 检索
        t_rag_start = time.time()
        search_result = rag_service.search(request.keyword, top_k=3)
        t_rag_end = time.time()
        rag_duration = t_rag_end - t_rag_start
        
        rag_timings = search_result.get("timings", {"recall": "0ms", "rerank": "0ms"})
        
        # 准备上下文
        docs = search_result["final_docs"]
        if docs and isinstance(docs[0], str):
            context = "\n\n".join(docs)
        else:
            context = "\n\n".join([d.page_content for d in docs])
        
        # 2. 流式生成器
        async def event_stream():
            # 发送 RAG 元数据
            metadata = {
                "type": "metadata",
                "rag_time": f"{rag_duration*1000:.0f}ms",
                "timings": rag_timings,
                "raw_docs": search_result["raw_docs"],
                "rerank_docs": search_result["rerank_docs"]
            }
            yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
            
            # 发送 LLM 生成开始标记
            yield f"data: {json.dumps({'type': 'llm_start'}, ensure_ascii=False)}\n\n"
            
            # 流式生成题目
            t_llm_start = time.time()
            full_content = ""
            async for chunk in llm_service.stream_generate_quiz(
                request.keyword,
                context,
                difficulty="中等",
                question_type="choice"
            ):
                full_content += chunk
                data = {
                    "type": "content",
                    "content": chunk
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
            t_llm_end = time.time()
            llm_duration = t_llm_end - t_llm_start
            
            # 发送完成信息
            total_duration = time.time() - t_rag_start
            log_str = (
                f"[Timing] embedding recall: {rag_timings.get('recall', '0ms')} "
                f"[Timing] rerank: {rag_timings.get('rerank', '0ms')} "
                f"[Timing] llm generation: {llm_duration:.2f}s "
                f"[Timing] total: {total_duration:.2f}s"
            )
            
            end_data = {
                "type": "done",
                "full_content": full_content,
                "timing_log": log_str
            }
            yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        print(f"[Admin Stream Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. RAGAS 评测接口 (保留原样)
# ==========================================
@router.post("/run_ragas_eval")
async def run_ragas_eval():
    """
    触发 RAGAS 自动化评测
    """
    try:
        # 调用 RAGAS 服务
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

# ==========================================
# 3. 压力测试接口 (补全功能)
# ==========================================
@router.post("/stress/start")
def start_stress_test(config: StressConfig):
    print(f"[Admin] ==> Received Stress Test Request: users={config.user_count}, rate={config.spawn_rate}")
    return stress_service.start_test(config.user_count, config.spawn_rate)

@router.post("/stress/stop")
def stop_stress_test():
    print("[Admin] ==> Received Stop Stress Request")
    return stress_service.stop_test()

@router.get("/stress/stats")
def get_stress_stats():
    stats = stress_service.get_stats()
    if not stats:
        return {"status": "offline"}
    return {"status": "success", "data": stats}