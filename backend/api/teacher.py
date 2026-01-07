import os
import shutil
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session

# 引入数据库依赖
from backend.db.session import get_db
from backend.models.tables import ExamRecord, User

# 引入 RAG 服务和初始化脚本
from backend.services.rag_service import rag_service
from backend.scripts.init_rag import init_local_rag

router = APIRouter(prefix="/teacher", tags=["教师模块"])

# --- 功能 1: 上传教材 ---
@router.post("/upload_doc")
async def upload_document(file: UploadFile = File(...)):
    """
    上传 PDF 或 TXT 到 data/docs 目录
    """
    try:
        # 动态获取 data/docs 路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "../../"))
        save_dir = os.path.join(project_root, "data", "docs")
        
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        file_path = os.path.join(save_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"status": "success", "message": f"文件 {file.filename} 上传成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

# --- 功能 2: 重建索引 ---
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

# --- 功能 3: 获取看板数据 (你刚才发的那个) ---
@router.get("/dashboard_stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    获取最近的答题记录用于看板展示
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