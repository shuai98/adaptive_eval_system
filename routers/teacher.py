import os
import shutil
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from init_rag import init_local_rag
from services.rag_service import rag_service
from database import get_db
from models import ExamRecord, User
from sqlalchemy.orm import Session
from fastapi import Depends

router = APIRouter(prefix="/teacher", tags=["教师模块"])

@router.post("/upload_doc")
async def upload_document(file: UploadFile = File(...)):
    try:
        save_dir = "docs"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        file_path = os.path.join(save_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"status": "success", "message": f"文件 {file.filename} 上传成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

@router.post("/reindex_kb")
async def reindex_knowledge_base(background_tasks: BackgroundTasks):
    try:
        # 在后台运行索引重建
        background_tasks.add_task(run_reindex_task)
        return {"status": "success", "message": "索引重建任务已启动，请稍后测试"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重建索引失败: {str(e)}")

def run_reindex_task():
    # 执行初始化脚本
    init_local_rag()
    # 通知 RAG 服务重新加载新的向量库
    rag_service.reload_db()



@router.get("/dashboard_stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    # 获取最近的 20 条做题记录
    records = db.query(ExamRecord, User.username).join(User, ExamRecord.student_id == User.id).order_by(ExamRecord.created_at.desc()).limit(20).all()
    
    data = []
    for record, username in records:
        data.append({
            "id": record.id,
            "student": username,
            "score": record.ai_score,
            "question": record.question_content[:20] + "...", # 只显示前20字
            "time": record.created_at.strftime("%Y-%m-%d %H:%M")
        })
    
    return {"status": "success", "data": data}