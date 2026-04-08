import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict

from passlib.context import CryptContext

from backend.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> None:
    normalized = (password or "").strip()
    if len(normalized) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    if normalized.lower() in {"123456", "password", "admin123", "root123456"}:
        raise ValueError("Password is too weak. Please choose a stronger password.")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _sign(message: bytes) -> str:
    digest = hmac.new(settings.APP_SECRET_KEY.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(digest)


def create_access_token(*, user_id: int, username: str, role: str, expires_in_hours: int | None = None) -> str:
    now = int(time.time())
    ttl_hours = expires_in_hours or settings.ACCESS_TOKEN_EXPIRE_HOURS
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + (ttl_hours * 3600),
        "iss": "adaptive-eval-system",
    }
    header = {"alg": "HS256", "typ": "AET"}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = _sign(signing_input)
    return f"{header_segment}.{payload_segment}.{signature}"


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        header_segment, payload_segment, signature = token.split(".")
    except ValueError as exc:
        raise ValueError("Malformed access token.") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Token signature verification failed.")

    try:
        payload = json.loads(_b64url_decode(payload_segment))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid token payload.") from exc

    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        raise ValueError("Access token has expired.")
    return payload
