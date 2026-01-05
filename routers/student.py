from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import json

from database import get_db
from models import QuestionHistory, ExamRecord
from services.rag_service import rag_service
from services.llm_service import llm_service

router = APIRouter(prefix="/student", tags=["学生模块"])

# --- 请求模型 ---
class QuestionRequest(BaseModel):
    keyword: str
    student_id: int
    mode: str = "adaptive"
    manual_difficulty: str = "中等"
    question_type: str = "choice"

class GradeRequest(BaseModel):
    question: str
    standard_answer: str
    student_answer: str
    student_id: int
    difficulty: str
    question_type: str  # 新增：告诉后端这是选择题还是简答题
    direct_score: Optional[float] = None # 新增：如果是选择题，前端直接传分过来

# --- 核心：爬楼梯式自适应算法 (60/80分界) ---
def calculate_adaptive_difficulty(db: Session, student_id: int):
    # 1. 获取最近一次答题记录
    last_record = db.query(ExamRecord).filter(
        ExamRecord.student_id == student_id
    ).order_by(ExamRecord.created_at.desc()).first()

    # 2. 冷启动
    if not last_record:
        return "中等"

    # 3. 获取上一题数据
    last_diff = last_record.difficulty
    score = last_record.ai_score

    print(f"[自适应] 上一题: {last_diff}, 得分: {score}")

    # 4. 状态机逻辑 (爬楼梯)
    
    # === 当前在【简单】层 ===
    if last_diff == "简单":
        if score >= 80:
            return "中等"  # 晋级
        else:
            return "简单"  # 保持 (没考好继续练基础)

    # === 当前在【中等】层 ===
    elif last_diff == "中等":
        if score >= 80:
            return "困难"  # 晋级
        elif score < 60:
            return "简单"  # 降级 (太难了回退)
        else:
            return "中等"  # 保持 (60-80分之间，稳固当前层级)

    # === 当前在【困难】层 ===
    elif last_diff == "困难":
        if score < 60:
            return "中等"  # 降级 (太难了回退)
        else:
            return "困难"  # 保持 (高手继续挑战)
            
    return "中等"

# --- 接口实现 ---

@router.post("/generate_question")
async def generate_question(request: QuestionRequest, db: Session = Depends(get_db)):
    try:
        # 1. 确定难度
        if request.mode == "adaptive":
            difficulty = calculate_adaptive_difficulty(db, request.student_id)
        else:
            difficulty = request.manual_difficulty
            
        print(f"出题请求 - 模式: {request.mode}, 判定难度: {difficulty}, 题型: {request.question_type}")

        # 2. RAG 检索
        search_result = rag_service.search(request.keyword)
        context = "\n\n".join([doc.page_content for doc in search_result["final_docs"]])
        
        # 3. LLM 生成
        content = await llm_service.generate_quiz(
            request.keyword, 
            context, 
            difficulty, 
            request.question_type
        )
        
        # 4. 存入历史
        new_history = QuestionHistory(
            student_id=request.student_id,
            keyword=request.keyword,
            question_json=content,
            difficulty=difficulty
        )
        db.add(new_history)
        db.commit()
        
        return {
            "status": "success", 
            "data": content,
            "difficulty": difficulty,
            "context": context,
            "debug_info": {         
                "raw_docs": search_result["raw_docs"],
                "rerank_docs": search_result["rerank_docs"]
            }
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/grade_answer")
async def grade_answer(request: GradeRequest, db: Session = Depends(get_db)):
    try:
        final_score = 0
        comment = ""
        
        # 分支 1：如果是选择题，直接使用前端传来的分数 (0 或 100)
        if request.question_type == 'choice':
            final_score = request.direct_score
            comment = "选择题自动评分"
            print(f"选择题提交 - 得分: {final_score}")
            
        # 分支 2：如果是主观题，调用 LLM 评分
        else:
            print("主观题提交 - 调用 AI 评分...")
            content = await llm_service.grade_answer(
                request.question, 
                request.standard_answer, 
                request.student_answer
            )
            result_json = json.loads(content)
            final_score = result_json.get("score", 0)
            comment = result_json.get("suggestion", "")

        # 统一保存记录 (这是自适应的关键！)
        new_record = ExamRecord(
            student_id=request.student_id,
            question_content=request.question,
            student_answer=request.student_answer,
            ai_score=final_score,
            ai_comment=comment,
            difficulty=request.difficulty # 记录这道题的难度
        )
        db.add(new_record)
        db.commit()
        
        # 如果是主观题，返回详细评语；选择题则返回简单信息
        return {
            "status": "success",
            "data": {
                "score": final_score,
                "suggestion": comment,
                "reason": "系统自动判定" if request.question_type == 'choice' else result_json.get("reason", "")
            }
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))