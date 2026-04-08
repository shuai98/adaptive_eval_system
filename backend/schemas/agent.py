from typing import List

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    top_k: int = 3


class Source(BaseModel):
    title: str
    content: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
