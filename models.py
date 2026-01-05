from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime

# --- 关键修改：从 database.py 导入 Base，而不是重新定义 ---
from database import Base

# --- 1. 用户表 (User) ---
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(128))
    role = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)

# --- 2. 出题历史表 (QuestionHistory) ---
class QuestionHistory(Base):
    __tablename__ = "question_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    keyword = Column(String(100))
    question_json = Column(Text)
    difficulty = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)

# --- 3. 答题/评分记录表 (ExamRecord) ---
class ExamRecord(Base):
    __tablename__ = "exam_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    question_content = Column(Text)
    student_answer = Column(Text)
    ai_score = Column(Float)
    ai_comment = Column(Text)
    
    # --- 新增：记录这道题当时的难度 ---
    difficulty = Column(String(20)) 
    
    created_at = Column(DateTime, default=datetime.now)

# --- 4. 题库表 (Question) ---
class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    options = Column(Text)
    answer = Column(String(500))
    analysis = Column(Text)
    difficulty = Column(String(50))
    tag = Column(String(100))