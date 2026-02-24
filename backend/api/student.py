from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import json
import time

from backend.db.session import get_db
from backend.models.tables import QuestionHistory, ExamRecord
from backend.services.rag_service import rag_service
from backend.services.llm_service import llm_service
from backend.models.tables import ExamRecord # 确保导入了 ExamRecord，以便保存历史记录

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
    question_type: str
    question_id: Optional[int] = None # 新增：关联出题历史 ID
    direct_score: Optional[float] = None
    analysis: Optional[str] = None

# --- 核心：多维度自适应算法 ---
class AdaptiveEngine:
    @staticmethod
    def calculate_next_difficulty(
        db: Session, 
        student_id: int, 
        keyword: str = None
    ) -> str:
        """
        多维度自适应算法（最终版）：
        1. 滑动窗口：看最近3题的平均分，而不是单题
        2. 稳定性检查：需要连续3题表现好才升级，避免频繁跳级
        3. 知识点维度：同一知识点的历史表现会影响难度判断
        4. 冷启动优化：新学生根据整体水平决定起始难度
        """
        # 1. 获取最近5题记录（用于滑动窗口分析）
        recent_records = db.query(ExamRecord).filter(
            ExamRecord.student_id == student_id
        ).order_by(ExamRecord.created_at.desc()).limit(5).all()

        if len(recent_records) < 3:
            return "中等"  # 冷启动：新学生从中等难度开始

        # 2. 计算最近3题平均分（滑动窗口）
        last_3_scores = [r.ai_score for r in recent_records[:3]]
        avg_score = sum(last_3_scores) / len(last_3_scores)

        # 3. 当前难度（以最近一次为准）
        current_diff = recent_records[0].difficulty

        # 4. 稳定性检查（最近3题难度是否一致，避免频繁跳级）
        last_3_diffs = [r.difficulty for r in recent_records[:3]]
        is_stable = len(set(last_3_diffs)) == 1

        # 5. 知识点掌握度（如果提供了关键词）
        keyword_bonus = 0
        if keyword:
            # 通过 join ExamRecord 和 QuestionHistory 来获取特定关键词的得分情况
            keyword_records = db.query(ExamRecord).join(
                QuestionHistory, ExamRecord.question_id == QuestionHistory.id
            ).filter(
                ExamRecord.student_id == student_id,
                QuestionHistory.keyword == keyword
            ).order_by(ExamRecord.created_at.desc()).limit(5).all()

            if keyword_records:
                keyword_avg = sum(r.ai_score for r in keyword_records) / len(keyword_records)
                if keyword_avg >= 85:
                    keyword_bonus = 1  # 该知识点很熟练，倾向于升级
                elif keyword_avg < 60:
                    keyword_bonus = -1  # 该知识点不熟，倾向于降级

        # 6. 决策逻辑（爬楼梯式，避免大幅跳跃）
        print(f"[自适应引擎] 当前难度: {current_diff}, 最近3题均分: {avg_score:.1f}, 稳定性: {is_stable}, 知识点加成: {keyword_bonus}")

        if current_diff == "简单":
            # 升级条件：连续3题稳定 + 平均分≥85 OR 该知识点掌握度高
            if (is_stable and avg_score >= 85) or keyword_bonus == 1:
                return "中等"
            else:
                return "简单"

        elif current_diff == "中等":
            # 升级条件：连续3题稳定 + 平均分≥85 OR 该知识点掌握度高
            if (is_stable and avg_score >= 85) or keyword_bonus == 1:
                return "困难"
            # 降级条件：平均分<60 OR 该知识点掌握度低
            elif avg_score < 60 or keyword_bonus == -1:
                return "简单"
            else:
                return "中等"

        elif current_diff == "困难":
            # 降级条件：平均分<60（给予更多容错空间）
            if avg_score < 60:
                return "中等"
            else:
                return "困难"

        return "中等"  # 默认返回中等

# --- 接口实现 ---

@router.post("/generate_question")
async def generate_question(request: QuestionRequest, db: Session = Depends(get_db)):
    try:
        # 1. 确定难度
        if request.mode == "adaptive":
            difficulty = AdaptiveEngine.calculate_next_difficulty(db, request.student_id, request.keyword)
        else:
            difficulty = request.manual_difficulty
            
        print(f"出题请求 - 模式: {request.mode}, 判定难度: {difficulty}, 题型: {request.question_type}")

        # 2. RAG 检索 (异步调用)
        search_result = await rag_service.search_async(request.keyword)
        context = "\n\n".join(search_result["final_docs"])
        
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
            question_json=json.dumps(content, ensure_ascii=False), # 转字符串存库
            difficulty=difficulty
        )
        db.add(new_history)
        db.commit()
        db.refresh(new_history) # 获取生成的 ID
        
        # 修改返回值，包含 question_id
        return {
            "status": "success", 
            "data": content,
            "question_id": new_history.id, # 返回题目 ID
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
    

@router.post("/generate_question_stream")
async def generate_question_stream(request: QuestionRequest, db: Session = Depends(get_db)):
    """
    流式生成题目接口 - 使用 SSE (Server-Sent Events)
    """
    try:
        # 1. 确定难度
        if request.mode == "adaptive":
            difficulty = AdaptiveEngine.calculate_next_difficulty(db, request.student_id, request.keyword)
        else:
            difficulty = request.manual_difficulty
            
        print(f"[流式] 出题请求 - 模式: {request.mode}, 判定难度: {difficulty}, 题型: {request.question_type}")

        # 2. RAG 检索
        t0 = time.time()
        search_result = await rag_service.search_async(request.keyword)
        context = "\n\n".join(search_result["final_docs"])
        t1 = time.time()
        rag_time_ms = (t1 - t0) * 1000
        
        print(f"[流式] RAG 检索完成，耗时: {rag_time_ms:.0f}ms")
        
        # 3. 定义流式生成器
        async def event_stream():
            try:
                # 预先创建一个 QuestionHistory 记录，为了获取 ID
                # 此时内容还是空的，等生成完再更新
                new_history = QuestionHistory(
                    student_id=request.student_id,
                    keyword=request.keyword,
                    question_json="", # 占位
                    difficulty=difficulty
                )
                db.add(new_history)
                db.commit()
                db.refresh(new_history)
                question_id = new_history.id

                # 首先发送元数据（难度、检索信息、题目ID等）
                metadata = {
                    "type": "metadata",
                    "difficulty": difficulty,
                    "question_id": question_id, # 返回题目 ID
                    "rag_time": f"{rag_time_ms:.0f}ms",
                    "timings": search_result.get("timings", {})
                }
                yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
                
                # 发送开始标记
                yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"
                
                # 逐字流式返回题目内容
                full_content = ""
                async for chunk in llm_service.stream_generate_quiz(
                    request.keyword,
                    context,
                    difficulty,
                    request.question_type
                ):
                    full_content += chunk
                    # 发送每个文本块
                    data = {
                        "type": "content",
                        "content": chunk
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                # 更新历史记录
                try:
                    # 解析生成的内容（简单版）
                    question_data = {
                        "raw_text": full_content,
                        "difficulty": difficulty,
                        "question_type": request.question_type
                    }
                    
                    new_history.question_json = json.dumps(question_data, ensure_ascii=False)
                    db.commit()
                except Exception as e:
                    print(f"[Stream History Error]: {e}")
                
                # 发送结束标记
                end_data = {
                    "type": "done",
                    "full_content": full_content
                }
                yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"
            except Exception as e:
                print(f"[Stream Error]: {e}")
                error_data = {"type": "error", "message": str(e)}
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        
        # 返回 SSE 流
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
            }
        )
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/grade_answer")
async def grade_answer(request: GradeRequest, db: Session = Depends(get_db)):
    try:
        final_score = 0
        comment = ""
        # 保存完整的题目信息（包括选项和解析）
        question_full = request.question
        
        # 分支 1：如果是选择题，直接使用前端传来的分数 (0 或 100)
        if request.question_type == 'choice':
            final_score = request.direct_score
            # 保存标准答案和解析作为评语
            comment = f"正确答案：{request.standard_answer}"
            if request.analysis:
                comment += f"\n\n解析：{request.analysis}"
            print(f"选择题提交 - 得分: {final_score}")
            
        # 分支 2：如果是主观题，调用 LLM 评分
        else:
            print("主观题提交 - 调用 AI 评分...")
            content = await llm_service.grade_answer(
                request.question, 
                request.standard_answer, 
                request.student_answer
            )
            result_json = content  # 已经是字典格式
            final_score = result_json.get("score", 0)
            comment = result_json.get("suggestion", "")

        # 统一保存记录 (这是自适应的关键！)
        new_record = ExamRecord(
            student_id=request.student_id,
            question_id=request.question_id, # 新增：保存题目 ID
            question_content=question_full,  # 保存完整题目
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
    
#历史记录接口
@router.get("/history")
async def get_history(student_id: int, db: Session = Depends(get_db)):
    """
    获取学生的做题历史
    """
    records = db.query(ExamRecord).filter(
        ExamRecord.student_id == student_id
    ).order_by(ExamRecord.created_at.desc()).limit(50).all()
    
    data = []
    for r in records:
        data.append({
            "id": r.id,
            "time": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "question": r.question_content[:30] + "..." if r.question_content else "未知题目",
            "score": r.ai_score,
            "difficulty": r.difficulty
        })
    
    return {"status": "success", "data": data}

@router.get("/history/{record_id}")
async def get_history_detail(record_id: int, db: Session = Depends(get_db)):
    """
    获取单条历史记录的详情
    """
    record = db.query(ExamRecord).filter(ExamRecord.id == record_id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    return {
        "status": "success",
        "data": {
            "id": record.id,
            "time": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "question": record.question_content,
            "student_answer": record.student_answer,
            "score": record.ai_score,
            "comment": record.ai_comment,
            "difficulty": record.difficulty
        }
    }

@router.get("/adaptive_stats")
async def get_adaptive_stats(student_id: int, keyword: str = None, db: Session = Depends(get_db)):
    """
    获取自适应算法的可视化数据
    返回：
    1. 最近10题的分数和难度趋势
    2. 知识点掌握度分析
    3. 当前自适应状态
    """
    # 1. 获取最近10题记录
    recent_records = db.query(ExamRecord).filter(
        ExamRecord.student_id == student_id
    ).order_by(ExamRecord.created_at.desc()).limit(10).all()
    
    if not recent_records:
        return {
            "status": "success",
            "data": {
                "recent_trend": [],
                "keyword_stats": {},
                "adaptive_state": {
                    "current_difficulty": "中等",
                    "avg_score_last_3": 0,
                    "is_stable": False,
                    "next_difficulty": "中等",
                    "reason": "暂无答题记录"
                }
            }
        }
    
    # 2. 构建趋势数据（倒序，最早的在前）
    trend_data = []
    for r in reversed(recent_records):
        # 获取关联的知识点
        keyword_name = "未知"
        if r.question_id:
            q_history = db.query(QuestionHistory).filter(
                QuestionHistory.id == r.question_id
            ).first()
            if q_history:
                keyword_name = q_history.keyword
        
        trend_data.append({
            "time": r.created_at.strftime("%m-%d %H:%M"),
            "score": r.ai_score,
            "difficulty": r.difficulty,
            "keyword": keyword_name
        })
    
    # 3. 知识点掌握度统计
    keyword_stats = {}
    
    # 获取所有做过的知识点
    all_records_with_keyword = db.query(ExamRecord, QuestionHistory).join(
        QuestionHistory, ExamRecord.question_id == QuestionHistory.id
    ).filter(
        ExamRecord.student_id == student_id
    ).all()
    
    for record, question in all_records_with_keyword:
        kw = question.keyword
        if kw not in keyword_stats:
            keyword_stats[kw] = {
                "count": 0,
                "total_score": 0,
                "avg_score": 0,
                "level": "未掌握"
            }
        keyword_stats[kw]["count"] += 1
        keyword_stats[kw]["total_score"] += record.ai_score
    
    # 计算平均分和掌握等级
    for kw in keyword_stats:
        avg = keyword_stats[kw]["total_score"] / keyword_stats[kw]["count"]
        keyword_stats[kw]["avg_score"] = round(avg, 1)
        
        if avg >= 85:
            keyword_stats[kw]["level"] = "熟练掌握"
        elif avg >= 70:
            keyword_stats[kw]["level"] = "基本掌握"
        elif avg >= 60:
            keyword_stats[kw]["level"] = "需要练习"
        else:
            keyword_stats[kw]["level"] = "未掌握"
    
    # 4. 当前自适应状态
    if len(recent_records) >= 3:
        last_3_scores = [r.ai_score for r in recent_records[:3]]
        avg_score = sum(last_3_scores) / len(last_3_scores)
        
        current_diff = recent_records[0].difficulty
        last_3_diffs = [r.difficulty for r in recent_records[:3]]
        is_stable = len(set(last_3_diffs)) == 1
        
        # 计算下一题难度
        next_diff = AdaptiveEngine.calculate_next_difficulty(db, student_id, keyword)
        
        # 生成决策理由
        reason_parts = []
        reason_parts.append(f"最近3题平均分: {avg_score:.1f}")
        reason_parts.append(f"难度稳定性: {'稳定' if is_stable else '不稳定'}")
        
        if keyword and keyword in keyword_stats:
            reason_parts.append(f"'{keyword}'掌握度: {keyword_stats[keyword]['avg_score']}")
        
        if next_diff != current_diff:
            reason_parts.append(f"建议调整: {current_diff} → {next_diff}")
        else:
            reason_parts.append(f"维持当前难度")
        
        adaptive_state = {
            "current_difficulty": current_diff,
            "avg_score_last_3": round(avg_score, 1),
            "is_stable": is_stable,
            "next_difficulty": next_diff,
            "reason": " | ".join(reason_parts)
        }
    else:
        adaptive_state = {
            "current_difficulty": recent_records[0].difficulty if recent_records else "中等",
            "avg_score_last_3": 0,
            "is_stable": False,
            "next_difficulty": "中等",
            "reason": "答题数量不足3题，暂无自适应建议"
        }
    
    return {
        "status": "success",
        "data": {
            "recent_trend": trend_data,
            "keyword_stats": keyword_stats,
            "adaptive_state": adaptive_state
        }
    }