from __future__ import annotations

import os
from typing import Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ALLOW_INSECURE_DEFAULTS", "1")
os.environ.setdefault("APP_SECRET_KEY", "adaptive-eval-pytest-secret")

from backend.api import student, teacher
from backend.core.security import create_access_token
from backend.db.session import Base, get_db
from backend.models.tables import ExamRecord, QuestionHistory, User
from backend.services.learning_analytics_service import learning_analytics_service


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def seeded_data(session_factory) -> Dict[str, int]:
    db = session_factory()
    try:
        teacher_user = User(username="teacher_demo", password_hash="x", role="teacher")
        student_user = User(username="student_demo", password_hash="y", role="student")
        admin_user = User(username="admin_demo", password_hash="z", role="admin")
        db.add_all([teacher_user, student_user, admin_user])
        db.commit()
        db.refresh(teacher_user)
        db.refresh(student_user)
        db.refresh(admin_user)

        q1 = QuestionHistory(
            student_id=student_user.id,
            keyword="递归",
            question_json='{"question":"什么是递归？"}',
            difficulty="简单",
        )
        q2 = QuestionHistory(
            student_id=student_user.id,
            keyword="装饰器",
            question_json='{"question":"什么是装饰器？"}',
            difficulty="中等",
        )
        q3 = QuestionHistory(
            student_id=student_user.id,
            keyword="列表推导式",
            question_json='{"question":"什么是列表推导式？"}',
            difficulty="困难",
        )
        db.add_all([q1, q2, q3])
        db.commit()
        db.refresh(q1)
        db.refresh(q2)
        db.refresh(q3)

        records = [
            ExamRecord(
                student_id=student_user.id,
                question_id=q1.id,
                question_content="递归基础题",
                student_answer="答错",
                ai_score=45,
                ai_comment="需要补强递归终止条件。",
                difficulty="简单",
            ),
            ExamRecord(
                student_id=student_user.id,
                question_id=q2.id,
                question_content="装饰器理解题",
                student_answer="基本正确",
                ai_score=78,
                ai_comment="掌握基本概念。",
                difficulty="中等",
            ),
            ExamRecord(
                student_id=student_user.id,
                question_id=q3.id,
                question_content="列表推导式综合题",
                student_answer="优秀",
                ai_score=92,
                ai_comment="综合表现较好。",
                difficulty="困难",
            ),
        ]
        db.add_all(records)
        db.commit()
        for record in records:
            db.refresh(record)
            learning_analytics_service.update_mastery_from_record(db, record)

        return {
            "teacher_id": teacher_user.id,
            "student_id": student_user.id,
            "admin_id": admin_user.id,
            "question_id": q1.id,
        }
    finally:
        db.close()


@pytest.fixture()
def client(session_factory):
    app = FastAPI()
    app.include_router(student.router)
    app.include_router(teacher.router)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(seeded_data):
    return {
        "student": {
            "Authorization": "Bearer " + create_access_token(
                user_id=seeded_data["student_id"],
                username="student_demo",
                role="student",
                expires_in_hours=12,
            )
        },
        "teacher": {
            "Authorization": "Bearer " + create_access_token(
                user_id=seeded_data["teacher_id"],
                username="teacher_demo",
                role="teacher",
                expires_in_hours=12,
            )
        },
        "admin": {
            "Authorization": "Bearer " + create_access_token(
                user_id=seeded_data["admin_id"],
                username="admin_demo",
                role="admin",
                expires_in_hours=12,
            )
        },
    }
