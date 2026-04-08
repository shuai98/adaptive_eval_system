from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(128))
    role = Column(String(20))  # student / teacher / admin
    created_at = Column(DateTime, default=datetime.now)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False, default="")
    filepath = Column(String(512), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), index=True)
    mime_type = Column(String(100), default="")
    file_size = Column(Integer, default=0)
    version = Column(Integer, default=1)
    status = Column(String(30), default="uploaded")
    indexed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)


class ExamRecord(Base):
    __tablename__ = "exam_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), index=True)
    question_id = Column(Integer, ForeignKey("question_history.id"), nullable=True)
    question_content = Column(Text)
    student_answer = Column(Text)
    ai_score = Column(Float)
    ai_comment = Column(Text)
    difficulty = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)

    question_history = relationship("QuestionHistory")


class QuestionHistory(Base):
    __tablename__ = "question_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), index=True)
    keyword = Column(String(100), index=True)
    question_json = Column(Text)
    difficulty = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)


class StudentKeywordMastery(Base):
    __tablename__ = "student_keyword_mastery"
    __table_args__ = (
        UniqueConstraint("student_id", "keyword", name="uq_student_keyword_mastery"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    keyword = Column(String(100), index=True, nullable=False)
    mastery_score = Column(Float, default=60.0)
    confidence = Column(Float, default=0.2)
    avg_score = Column(Float, default=0.0)
    attempt_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    last_score = Column(Float, default=0.0)
    streak = Column(Integer, default=0)
    last_difficulty = Column(String(20), default="中等")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AsyncTaskLog(Base):
    __tablename__ = "async_task_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(50), index=True, nullable=False)
    task_scope = Column(String(20), index=True, nullable=False)
    owner_id = Column(Integer, index=True)
    status = Column(String(20), index=True, default="queued")
    progress = Column(Float, default=0.0)
    detail = Column(String(255), default="")
    payload_json = Column(Text)
    result_json = Column(Text)
    error_message = Column(Text)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=2)
    timeout_seconds = Column(Integer, default=300)
    cancel_requested = Column(Boolean, default=False)
    lease_expires_at = Column(DateTime)
    heartbeat_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class ExperimentVersion(Base):
    __tablename__ = "experiment_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene = Column(String(50), index=True, nullable=False)
    version_key = Column(String(80), index=True, nullable=False)
    dataset_name = Column(String(255))
    index_name = Column(String(255))
    parser_mode = Column(String(50))
    rerank_mode = Column(String(50))
    prompt_version = Column(String(80))
    summary_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
