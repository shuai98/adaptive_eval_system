import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from backend.core.config import settings
from backend.core.security import get_password_hash
from backend.db.session import SessionLocal
from backend.models.tables import User


def create_admin_user() -> None:
    settings.validate_runtime()
    username = settings.ADMIN_BOOTSTRAP_USERNAME
    password = settings.require_admin_bootstrap_password()

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"[CreateAdmin] Admin '{username}' already exists.")
            return

        print(f"[CreateAdmin] Creating admin '{username}' ...")
        admin_user = User(
            username=username,
            password_hash=get_password_hash(password),
            role="admin",
        )
        db.add(admin_user)
        db.commit()
        print(f"[CreateAdmin] Admin '{username}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    create_admin_user()
