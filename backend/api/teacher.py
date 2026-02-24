import os
import shutil
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends, Form
from sqlalchemy.orm import Session

# 引入配置 (让路径计算更简洁)
from backend.core.config import settings
# 引入数据库依赖
from backend.db.session import get_db
# 引入模型 (新增了 Document)
from backend.models.tables import ExamRecord, User, Document

# 引入 RAG 服务和初始化脚本
from backend.services.rag_service import rag_service
from backend.scripts.init_rag import init_local_rag

router = APIRouter(prefix="/teacher", tags=["教师模块"])

# --- 功能 1: 上传教材 (升级版：存硬盘 + 存数据库) ---
@router.post("/upload_doc")
async def upload_document(
    file: UploadFile = File(...), 
    user_id: int = Form(...) # 接收前端传来的老师ID
):
    """
    上传 PDF 或 TXT 到 data/docs 目录，并记录到数据库
    """
    try:
        # 1. 确保目录存在 (使用 settings 里的路径，代码更短更稳)
        if not os.path.exists(settings.DOCS_DIR):
            os.makedirs(settings.DOCS_DIR)
        
        file_path = os.path.join(settings.DOCS_DIR, file.filename)
        
        # 2. 保存文件到硬盘
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 3. --- 新增：写入数据库记录 (实现数据隔离的关键) ---
        db = next(get_db()) # 获取数据库会话
        new_doc = Document(
            filename=file.filename,
            filepath=file_path,
            teacher_id=user_id # 记录是谁传的
        )
        db.add(new_doc)
        db.commit()
            
        return {"status": "success", "message": f"文件 {file.filename} 上传成功并已归档"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

# --- 功能 2: 获取我的文档 (新增功能) ---
@router.get("/my_docs")
async def get_my_docs(teacher_id: int, db: Session = Depends(get_db)):
    """
    只获取当前老师上传的文档列表
    """
    docs = db.query(Document).filter(Document.teacher_id == teacher_id).order_by(Document.created_at.desc()).all()
    return {
        "status": "success", 
        "data": [{"id": d.id, "name": d.filename, "time": d.created_at.strftime("%Y-%m-%d %H:%M")} for d in docs]
    }

# --- 功能 3: 重建索引 (保持不变) ---
@router.post("/reindex_kb")
async def reindex_knowledge_base(background_tasks: BackgroundTasks):
    """
    触发后台任务：重新扫描文档并构建 FAISS 索引
    """
    try:
        # 在后台运行，防止前端卡死
        background_tasks.add_task(run_reindex_task)
        return {"status": "success", "message": "索引重建任务已启动，请稍后测试"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重建索引失败: {str(e)}")

def run_reindex_task():
    print("[Background] 开始重建索引...")
    # 1. 运行初始化脚本生成文件
    init_local_rag()
    # 2. 通知内存中的服务重新加载文件
    rag_service.reload_db()
    print("[Background] 索引重建完成并已热加载。")

# --- 功能 4: 获取看板数据 (保持不变) ---
@router.get("/dashboard_stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    获取最近的答题记录用于看板展示 (查看全班数据)
    """
    try:
        # 联表查询：ExamRecord + User
        records = db.query(ExamRecord, User.username)\
            .join(User, ExamRecord.student_id == User.id)\
            .order_by(ExamRecord.created_at.desc())\
            .limit(20)\
            .all()
        
        data = []
        for record, username in records:
            data.append({
                "id": record.id,
                "time": record.created_at.strftime("%Y-%m-%d %H:%M"),
                "student": username,
                # 截取题目防止太长
                "question": record.question_content[:30] + "..." if record.question_content else "未知题目",
                "score": record.ai_score
            })
        
        return {"status": "success", "data": data}
    except Exception as e:
        print(f"Dashboard Error: {e}")
        return {"status": "error", "data": []}

# --- 功能 5: 获取答题详情 (新增) ---
@router.get("/record_detail/{record_id}")
async def get_record_detail(record_id: int, db: Session = Depends(get_db)):
    """
    获取单条答题记录的详情 (教师端查看学生答题情况)
    """
    # 联表查询：获取记录和学生信息
    result = db.query(ExamRecord, User.username)\
        .join(User, ExamRecord.student_id == User.id)\
        .filter(ExamRecord.id == record_id)\
        .first()
    
    if not result:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    record, username = result
    
    return {
        "status": "success",
        "data": {
            "id": record.id,
            "time": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "student": username,
            "question": record.question_content,
            "student_answer": record.student_answer,
            "score": record.ai_score,
            "comment": record.ai_comment,
            "difficulty": record.difficulty
        }
    }