import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.services.rag_service import rag_service
from backend.services.llm_service import llm_service

router = APIRouter()

class QueryRequest(BaseModel):
    question: str
    top_k: int = 3

class Source(BaseModel):
    title: str
    content: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]

@router.post("/query", response_model=QueryResponse, tags=["Agent"])
async def agent_query(request: QueryRequest):
    """
    为 EduReflex Agent 提供的标准查询接口
    
    接收问题，返回基于知识库的答案和来源文档
    """
    try:
        if not rag_service.is_initialized:
            raise HTTPException(status_code=503, detail="RAG 正在初始化，请稍后重试")

        # 1. 调用 RAG 服务进行检索（使用 Rerank 优化）
        search_result = await rag_service.search_async(request.question, top_k=request.top_k)
        
        # 提取 rerank 后的文档内容
        context_docs = search_result.get("rerank_docs", [])
        if not context_docs:
            return QueryResponse(
                answer="抱歉，我在知识库中没有找到相关信息来回答这个问题。", 
                sources=[]
            )

        # 2. 拼接上下文，调用 LLM 生成答案
        context_str = "\n\n---\n\n".join([f"片段 {i+1}:\n{doc}" for i, doc in enumerate(context_docs)])
        
        prompt = f"""你是一个教育领域的知识助手。请根据以下背景知识，简洁、准确地回答问题。

背景知识：
{context_str}

问题：{request.question}

要求：
1. 直接回答问题，不要重复问题本身
2. 答案要基于提供的背景知识
3. 保持简洁，突出重点
4. 如果背景知识不足以完整回答，请说明"""
        
        try:
            # 给 LLM 生成设置超时，避免接口长时间无响应
            llm_response = await asyncio.wait_for(
                llm_service.llm.ainvoke(prompt),
                timeout=8
            )
            answer = llm_response.content.strip()
        except Exception:
            # LLM 失败时降级，避免直接 500
            fallback_docs = "\n\n".join(context_docs[:3])
            answer = "LLM 生成失败，以下为检索片段的直接返回：\n" + fallback_docs[:1500]

        # 3. 格式化返回结果（构造 Source 对象列表）
        sources = [
            Source(title=f"知识片段 {i+1}", content=doc) 
            for i, doc in enumerate(context_docs)
        ]
        
        return QueryResponse(answer=answer, sources=sources)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
