"""initial schema

Revision ID: 20260329_0001
Revises:
Create Date: 2026-03-29 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260329_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("password_hash", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("filepath", sa.String(length=512), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_teacher_id"), "documents", ["teacher_id"], unique=False)

    op.create_table(
        "question_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("keyword", sa.String(length=100), nullable=True),
        sa.Column("question_json", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_question_history_keyword"), "question_history", ["keyword"], unique=False)
    op.create_index(op.f("ix_question_history_student_id"), "question_history", ["student_id"], unique=False)

    op.create_table(
        "exam_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("question_id", sa.Integer(), nullable=True),
        sa.Column("question_content", sa.Text(), nullable=True),
        sa.Column("student_answer", sa.Text(), nullable=True),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("ai_comment", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["question_id"], ["question_history.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exam_records_student_id"), "exam_records", ["student_id"], unique=False)

    op.create_table(
        "student_keyword_mastery",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("keyword", sa.String(length=100), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("avg_score", sa.Float(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=True),
        sa.Column("success_count", sa.Integer(), nullable=True),
        sa.Column("wrong_count", sa.Integer(), nullable=True),
        sa.Column("last_score", sa.Float(), nullable=True),
        sa.Column("streak", sa.Integer(), nullable=True),
        sa.Column("last_difficulty", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "keyword", name="uq_student_keyword_mastery"),
    )
    op.create_index(op.f("ix_student_keyword_mastery_keyword"), "student_keyword_mastery", ["keyword"], unique=False)
    op.create_index(op.f("ix_student_keyword_mastery_student_id"), "student_keyword_mastery", ["student_id"], unique=False)

    op.create_table(
        "async_task_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("task_scope", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("detail", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_async_task_log_owner_id"), "async_task_log", ["owner_id"], unique=False)
    op.create_index(op.f("ix_async_task_log_status"), "async_task_log", ["status"], unique=False)
    op.create_index(op.f("ix_async_task_log_task_scope"), "async_task_log", ["task_scope"], unique=False)
    op.create_index(op.f("ix_async_task_log_task_type"), "async_task_log", ["task_type"], unique=False)

    op.create_table(
        "experiment_version",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scene", sa.String(length=50), nullable=False),
        sa.Column("version_key", sa.String(length=80), nullable=False),
        sa.Column("dataset_name", sa.String(length=255), nullable=True),
        sa.Column("index_name", sa.String(length=255), nullable=True),
        sa.Column("parser_mode", sa.String(length=50), nullable=True),
        sa.Column("rerank_mode", sa.String(length=50), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_experiment_version_scene"), "experiment_version", ["scene"], unique=False)
    op.create_index(op.f("ix_experiment_version_version_key"), "experiment_version", ["version_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_experiment_version_version_key"), table_name="experiment_version")
    op.drop_index(op.f("ix_experiment_version_scene"), table_name="experiment_version")
    op.drop_table("experiment_version")
    op.drop_index(op.f("ix_async_task_log_task_type"), table_name="async_task_log")
    op.drop_index(op.f("ix_async_task_log_task_scope"), table_name="async_task_log")
    op.drop_index(op.f("ix_async_task_log_status"), table_name="async_task_log")
    op.drop_index(op.f("ix_async_task_log_owner_id"), table_name="async_task_log")
    op.drop_table("async_task_log")
    op.drop_index(op.f("ix_student_keyword_mastery_student_id"), table_name="student_keyword_mastery")
    op.drop_index(op.f("ix_student_keyword_mastery_keyword"), table_name="student_keyword_mastery")
    op.drop_table("student_keyword_mastery")
    op.drop_index(op.f("ix_exam_records_student_id"), table_name="exam_records")
    op.drop_table("exam_records")
    op.drop_index(op.f("ix_question_history_student_id"), table_name="question_history")
    op.drop_index(op.f("ix_question_history_keyword"), table_name="question_history")
    op.drop_table("question_history")
    op.drop_index(op.f("ix_documents_teacher_id"), table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
