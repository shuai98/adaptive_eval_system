import asyncio

from fastapi import HTTPException

from backend.schemas.agent import QueryRequest, QueryResponse, Source
from backend.services.llm_service import llm_service
from backend.services.rag_service import rag_service


def _build_context(context_docs: list[str]) -> str:
    return "\n\n---\n\n".join(
        [f"Passage {index + 1}:\n{doc}" for index, doc in enumerate(context_docs)]
    )


def _fallback_answer(context_docs: list[str]) -> str:
    fallback_docs = "\n\n".join(context_docs[:3])
    return "LLM generation failed. Returning the retrieved passages directly:\n" + fallback_docs[:1500]


async def answer_query(request: QueryRequest) -> QueryResponse:
    if not rag_service.is_initialized:
        raise HTTPException(status_code=503, detail="RAG is still initializing. Please retry shortly.")

    search_result = await rag_service.search_async(request.question, top_k=request.top_k)
    context_docs = search_result.get("rerank_docs", [])
    if not context_docs:
        return QueryResponse(
            answer="Sorry, I could not find relevant knowledge base passages for this question.",
            sources=[],
        )

    prompt = (
        "You are an educational knowledge assistant. Answer the question using the provided context. "
        "Be concise, accurate, and say clearly if the context is insufficient.\n\n"
        f"Context:\n{_build_context(context_docs)}\n\nQuestion: {request.question}"
    )

    try:
        llm_response = await asyncio.wait_for(llm_service.llm.ainvoke(prompt), timeout=8)
        answer = llm_response.content.strip()
    except Exception:
        answer = _fallback_answer(context_docs)

    sources = [
        Source(title=f"Knowledge Passage {index + 1}", content=doc)
        for index, doc in enumerate(context_docs)
    ]
    return QueryResponse(answer=answer, sources=sources)
