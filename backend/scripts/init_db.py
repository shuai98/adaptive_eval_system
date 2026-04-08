import os
import sys
from typing import Dict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from sqlalchemy import inspect, text

from backend.core.config import settings
from backend.core.security import get_password_hash
from backend.db.session import Base, SessionLocal, engine
from backend.models.tables import User


LEGACY_COLUMN_PATCHES: Dict[str, Dict[str, str]] = {
    "documents": {
        "stored_name": "VARCHAR(255) NOT NULL DEFAULT ''",
        "mime_type": "VARCHAR(100) NULL DEFAULT ''",
        "file_size": "INT NULL DEFAULT 0",
        "version": "INT NULL DEFAULT 1",
        "status": "VARCHAR(30) NULL DEFAULT 'uploaded'",
        "indexed_at": "DATETIME NULL",
    },
    "async_task_log": {
        "attempt_count": "INT NULL DEFAULT 0",
        "max_attempts": "INT NULL DEFAULT 2",
        "timeout_seconds": "INT NULL DEFAULT 300",
        "cancel_requested": "BOOLEAN NULL DEFAULT 0",
        "lease_expires_at": "DATETIME NULL",
        "heartbeat_at": "DATETIME NULL",
    },
}


def _fallback_schema_sync() -> None:
    print("[InitDB] Alembic unavailable, falling back to metadata sync + legacy column patching...")
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, columns in LEGACY_COLUMN_PATCHES.items():
            if table_name not in tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name in existing_columns:
                    continue
                print(f"[InitDB] Adding missing column: {table_name}.{column_name}")
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))


def upgrade_schema() -> None:
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError as exc:
        print(f"[InitDB] Alembic import failed: {exc}")
        _fallback_schema_sync()
        return

    config = Config(os.path.join(settings.BASE_DIR, "alembic.ini"))
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        print(f"[InitDB] Alembic upgrade failed: {exc}")
        _fallback_schema_sync()


def ensure_schema_ready() -> None:
    inspector = inspect(engine)
    if "users" not in set(inspector.get_table_names()):
        raise RuntimeError("Database schema is missing. Run migrations before bootstrapping data.")


def init_db() -> None:
    settings.validate_runtime()
    print("[InitDB] Applying Alembic migrations...")
    upgrade_schema()
    ensure_schema_ready()
    print("[InitDB] Schema is up to date.")

    admin_password = settings.require_admin_bootstrap_password()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.ADMIN_BOOTSTRAP_USERNAME).first()
        if admin is None:
            print(f"[InitDB] Creating admin account: {settings.ADMIN_BOOTSTRAP_USERNAME}")
            admin = User(
                username=settings.ADMIN_BOOTSTRAP_USERNAME,
                password_hash=get_password_hash(admin_password),
                role="admin",
            )
            db.add(admin)
            db.commit()
            print("[InitDB] Admin account created.")
        else:
            print("[InitDB] Admin account already exists, skip creation.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
