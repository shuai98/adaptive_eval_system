from typing import Optional

from pydantic import BaseModel


DEFAULT_DIFFICULTY = "\u4e2d\u7b49"


class QuestionRequest(BaseModel):
    keyword: str
    student_id: Optional[int] = None
    mode: str = "adaptive"
    manual_difficulty: str = DEFAULT_DIFFICULTY
    question_type: str = "choice"


class GradeRequest(BaseModel):
    question: str
    standard_answer: str
    student_answer: str
    student_id: Optional[int] = None
    difficulty: str
    question_type: str
    question_id: Optional[int] = None
    direct_score: Optional[float] = None
    analysis: Optional[str] = None
