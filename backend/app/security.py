# -*- coding: utf-8 -*-
"""密码哈希与 JWT（标准库实现，避免额外依赖）。"""
import base64
import hashlib
import hmac
import json
import os
import time

from .config import settings

_SALT_BYTES = 16
_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_b64, dk_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        dk = base64.b64decode(dk_b64)
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iters))
        return hmac.compare_digest(calc, dk)
    except Exception:
        return False


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(user_id: int, role: str) -> str:
    header = {"alg": settings.JWT_ALG, "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.TOKEN_EXPIRE_MINUTES * 60,
    }
    head = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signing = f"{head}.{body}".encode()
    sig = _b64encode(hmac.new(settings.JWT_SECRET.encode(), signing, hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def decode_token(token: str) -> dict | None:
    try:
        head, body, sig = token.split(".")
        signing = f"{head}.{body}".encode()
        expected = _b64encode(hmac.new(settings.JWT_SECRET.encode(), signing, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64decode(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None