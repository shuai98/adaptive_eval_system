from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.db.session import Base

# 1. 用户表 (核心)
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(128))
    role = Column(String(20))  # student / teacher / admin
    created_at = Column(DateTime, default=datetime.now)

# 2. 教师文档表 (实现教师数据隔离)
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(512), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), index=True) # 谁传的
    created_at = Column(DateTime, default=datetime.now)

# 3. 答题记录表 (实现学生数据隔离)
class ExamRecord(Base):
    __tablename__ = "exam_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), index=True) # 谁做的
    question_id = Column(Integer, ForeignKey("question_history.id"), nullable=True) # 关联出题历史
    question_content = Column(Text)
    student_answer = Column(Text)
    ai_score = Column(Float)
    ai_comment = Column(Text)
    difficulty = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)

    # 建立关联关系，方便查询
    question_history = relationship("QuestionHistory")

# 4. 出题历史表
class QuestionHistory(Base):
    __tablename__ = "question_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), index=True)
    keyword = Column(String(100))
    question_json = Column(Text)
    difficulty = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)