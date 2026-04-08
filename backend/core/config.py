import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _as_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_csv(raw: str, fallback: List[str]) -> List[str]:
    items = [item.strip() for item in (raw or "").split(",") if item.strip()]
    return items or list(fallback)


class Settings:
    def __init__(self) -> None:
        self.APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
        self.PROJECT_NAME = "Adaptive Evaluation System"
        self.VERSION = "6.0"

        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.DATA_DIR = os.path.join(self.BASE_DIR, "data")
        self.DOCS_DIR = os.path.join(self.DATA_DIR, "docs")
        self.FAISS_INDEX_DIR = os.path.join(self.DATA_DIR, "faiss_index")

        self.MYSQL_USER = os.getenv("MYSQL_USER", "root").strip()
        self.MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "").strip()
        self.MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1").strip()
        self.MYSQL_PORT = os.getenv("MYSQL_PORT", "3306").strip()
        self.MYSQL_DB = os.getenv("MYSQL_DB", "adaptive_eval").strip()
        explicit_db_url = os.getenv("SQLALCHEMY_DATABASE_URL", "").strip()
        self.SQLALCHEMY_DATABASE_URL = explicit_db_url or (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        )

        self.is_test = self.APP_ENV in {"test", "pytest", "ci"} or "PYTEST_CURRENT_TEST" in os.environ
        self.ALLOW_INSECURE_DEFAULTS = _as_bool("ALLOW_INSECURE_DEFAULTS", self.is_test)
        self.APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "").strip() or (
            "adaptive-eval-test-secret-key"
            if self.ALLOW_INSECURE_DEFAULTS
            else ""
        )
        self.ACCESS_TOKEN_EXPIRE_HOURS = _as_int("ACCESS_TOKEN_EXPIRE_HOURS", 12)

        self.REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1").strip()
        self.REDIS_PORT = _as_int("REDIS_PORT", 6379)
        self.REDIS_DB = _as_int("REDIS_DB", 0)
        self.TASK_QUEUE_NAME = os.getenv("TASK_QUEUE_NAME", "adaptive_eval:task_queue").strip()
        self.TASK_POLL_INTERVAL_SEC = max(1, _as_int("TASK_POLL_INTERVAL_SEC", 2))
        self.TASK_DEFAULT_TIMEOUT_SEC = max(30, _as_int("TASK_DEFAULT_TIMEOUT_SEC", 300))
        self.TASK_DEFAULT_MAX_ATTEMPTS = max(1, _as_int("TASK_DEFAULT_MAX_ATTEMPTS", 2))
        self.TASK_RECOVERY_LOOKBACK_SEC = max(5, _as_int("TASK_RECOVERY_LOOKBACK_SEC", 15))
        self.TASK_STALE_SEC = max(0, _as_int("TASK_STALE_SEC", 3600))
        self.TASK_GENERATE_QUESTION_TIMEOUT_SEC = max(
            30, _as_int("TASK_GENERATE_QUESTION_TIMEOUT_SEC", self.TASK_DEFAULT_TIMEOUT_SEC)
        )
        self.TASK_GENERATE_QUESTION_MAX_ATTEMPTS = max(
            1, _as_int("TASK_GENERATE_QUESTION_MAX_ATTEMPTS", 1)
        )
        self.TASK_GRADE_ANSWER_TIMEOUT_SEC = max(
            30, _as_int("TASK_GRADE_ANSWER_TIMEOUT_SEC", self.TASK_DEFAULT_TIMEOUT_SEC)
        )
        self.TASK_GRADE_ANSWER_MAX_ATTEMPTS = max(
            1, _as_int("TASK_GRADE_ANSWER_MAX_ATTEMPTS", 1)
        )
        self.LOAD_TEST_ACTIVE = _as_bool("LOAD_TEST_ACTIVE", False)
        self.LOAD_TEST_DROP_ON_IDLE = _as_bool("LOAD_TEST_DROP_ON_IDLE", True)
        self.LOAD_TEST_TRIGGER_VALUE = os.getenv("LOAD_TEST_TRIGGER_VALUE", "load_test").strip()

        self.HF_ENDPOINT = os.getenv("HF_ENDPOINT", "https://hf-mirror.com").strip()
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        self.THIRD_PARTY_LOG_LEVEL = os.getenv("THIRD_PARTY_LOG_LEVEL", "WARNING").strip().upper()
        self.VERBOSE_LLM_LOGS = _as_bool("VERBOSE_LLM_LOGS", False)
        self.RUN_RELOAD = _as_bool("RUN_RELOAD", self.APP_ENV == "development")
        self.TASK_RECOVER_QUEUED_ON_START = _as_bool("TASK_RECOVER_QUEUED_ON_START", False)
        self.TASK_RECOVER_RETRYING_ON_START = _as_bool("TASK_RECOVER_RETRYING_ON_START", False)
        self.LLM_REQUEST_TIMEOUT_SEC = max(5, _as_int("LLM_REQUEST_TIMEOUT_SEC", 60))

        self.MAX_UPLOAD_SIZE_MB = max(1, _as_int("MAX_UPLOAD_SIZE_MB", 200))
        self.ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".txt"}

        default_origins = [
            "http://localhost:8001",
            "http://127.0.0.1:8001",
            "http://localhost:8088",
            "http://127.0.0.1:8088",
        ]
        self.CORS_ORIGINS = _parse_csv(os.getenv("CORS_ORIGINS", ",".join(default_origins)), default_origins)

        self.ADMIN_BOOTSTRAP_USERNAME = os.getenv("ADMIN_BOOTSTRAP_USERNAME", "root").strip()
        self.ADMIN_BOOTSTRAP_PASSWORD = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "").strip()

    def validate_runtime(self) -> None:
        errors: List[str] = []
        if not self.APP_SECRET_KEY:
            errors.append("APP_SECRET_KEY is required.")
        if not self.ALLOW_INSECURE_DEFAULTS and self.MYSQL_PASSWORD in {"", "123456"}:
            errors.append("MYSQL_PASSWORD must be configured and cannot use the default weak password.")
        if errors:
            raise RuntimeError("Runtime configuration is invalid:\n- " + "\n- ".join(errors))

    def require_admin_bootstrap_password(self) -> str:
        if self.ADMIN_BOOTSTRAP_PASSWORD and self.ADMIN_BOOTSTRAP_PASSWORD != "123456":
            return self.ADMIN_BOOTSTRAP_PASSWORD
        if self.ALLOW_INSECURE_DEFAULTS:
            return self.ADMIN_BOOTSTRAP_PASSWORD or "adaptive-eval-admin-test"
        raise RuntimeError(
            "ADMIN_BOOTSTRAP_PASSWORD must be set and cannot use a weak default."
        )


settings = Settings()
