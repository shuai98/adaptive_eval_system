import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.core.auth import get_current_admin
from backend.core.observability import get_logger
from backend.schemas.admin import StressConfig, TestRequest
from backend.services.experiment_version_service import experiment_version_service
from backend.services.llm_service import llm_service
from backend.services.metrics.ragas_service import ragas_service
from backend.services.metrics.stress_service import stress_service
from backend.services.rag_service import rag_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])
logger = get_logger("adaptive.api.admin")


@router.post("/debug_generation")
async def debug_generation(request: TestRequest):
    started_at = time.time()
    try:
        logger.info("debug_generation keyword=%s", request.keyword)
        search_result = rag_service.search(request.keyword, top_k=6, recall_k=15)
        rag_timings = search_result.get("timings", {"recall": "0ms", "rerank": "0ms"})
        generation_docs, generation_doc_indices = rag_service.build_generation_context(
            search_result.get("final_docs", []),
            pool_size=6,
            sample_size=3,
        )
        context = "\n\n".join(generation_docs)

        llm_started_at = time.time()
        content = await llm_service.generate_quiz(
            request.keyword,
            context,
            difficulty="中等",
            question_type="choice",
        )
        llm_duration = time.time() - llm_started_at
        total_duration = time.time() - started_at
        log_str = (
            f"[Timing] embedding recall: {rag_timings.get('recall', '0ms')} "
            f"[Timing] rerank: {rag_timings.get('rerank', '0ms')} "
            f"[Timing] llm generation: {llm_duration:.2f}s "
            f"[Timing] total: {total_duration:.2f}s"
        )

        return {
            "status": "success",
            "data": {
                "generated_content": content,
                "debug_info": {
                    "raw_docs": search_result["raw_docs"],
                    "rerank_docs": search_result["rerank_docs"],
                    "generation_docs": generation_docs,
                    "generation_doc_indices": generation_doc_indices,
                    "raw_doc_details": search_result.get("raw_doc_details", []),
                    "rerank_doc_details": search_result.get("rerank_doc_details", []),
                    "index_info": search_result.get("index_info", {}),
                    "runtime_config": search_result.get("runtime_config", {}),
                    "rerank_applied": search_result.get("rerank_applied", False),
                    "rerank_reason": search_result.get("rerank_reason", ""),
                    "timing_log": log_str,
                },
            },
        }
    except Exception as exc:
        logger.exception("debug_generation_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/debug_generation_stream")
async def debug_generation_stream(request: TestRequest):
    try:
        logger.info("debug_generation_stream keyword=%s", request.keyword)
        rag_started_at = time.time()
        search_result = rag_service.search(request.keyword, top_k=6, recall_k=15)
        rag_duration = time.time() - rag_started_at
        rag_timings = search_result.get("timings", {"recall": "0ms", "rerank": "0ms"})
        generation_docs, generation_doc_indices = rag_service.build_generation_context(
            search_result.get("final_docs", []),
            pool_size=6,
            sample_size=3,
        )
        context = "\n\n".join(generation_docs)

        async def event_stream():
            metadata = {
                "type": "metadata",
                "rag_time": f"{rag_duration * 1000:.0f}ms",
                "timings": rag_timings,
                "raw_docs": search_result["raw_docs"],
                "rerank_docs": search_result["rerank_docs"],
                "generation_docs": generation_docs,
                "generation_doc_indices": generation_doc_indices,
                "raw_doc_details": search_result.get("raw_doc_details", []),
                "rerank_doc_details": search_result.get("rerank_doc_details", []),
                "index_info": search_result.get("index_info", {}),
                "runtime_config": search_result.get("runtime_config", {}),
                "rerank_applied": search_result.get("rerank_applied", False),
                "rerank_reason": search_result.get("rerank_reason", ""),
            }
            yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'llm_start'}, ensure_ascii=False)}\n\n"

            llm_started_at = time.time()
            full_content = ""
            async for chunk in llm_service.stream_generate_quiz(
                request.keyword,
                context,
                difficulty="中等",
                question_type="choice",
            ):
                full_content += chunk
                yield f"data: {json.dumps({'type': 'content', 'content': chunk}, ensure_ascii=False)}\n\n"

            llm_duration = time.time() - llm_started_at
            total_duration = time.time() - rag_started_at
            log_str = (
                f"[Timing] embedding recall: {rag_timings.get('recall', '0ms')} "
                f"[Timing] rerank: {rag_timings.get('rerank', '0ms')} "
                f"[Timing] llm generation: {llm_duration:.2f}s "
                f"[Timing] total: {total_duration:.2f}s"
            )
            yield f"data: {json.dumps({'type': 'done', 'full_content': full_content, 'timing_log': log_str}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as exc:
        logger.exception("debug_generation_stream_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/run_ragas_eval")
async def run_ragas_eval():
    try:
        scores = await ragas_service.run_evaluation()
        if "error" in scores:
            raise HTTPException(status_code=404, detail=scores["error"])
        return {"status": "success", "data": scores}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("run_ragas_eval_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stress/start")
def start_stress_test(config: StressConfig):
    logger.info("stress_test_start users=%s rate=%s", config.user_count, config.spawn_rate)
    result = stress_service.start_test(config.user_count, config.spawn_rate)
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("message") or "压测启动失败")
    return {"status": "success", "data": result.get("data") or {}}


@router.post("/stress/stop")
def stop_stress_test():
    logger.info("stress_test_stop")
    return {"status": "success", "data": stress_service.stop_test()}


@router.get("/stress/stats")
def get_stress_stats():
    stats = stress_service.get_stats()
    return {"status": "success", "data": stats}


@router.get("/experiment_versions")
def get_experiment_versions(scene: str | None = None, limit: int = 10):
    return {
        "status": "success",
        "data": experiment_version_service.list_versions(scene=scene, limit=limit),
    }
