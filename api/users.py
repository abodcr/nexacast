import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, List, Optional


class UserStore:
    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write({"users": []})

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"users": []}
            if "users" not in data or not isinstance(data["users"], list):
                data["users"] = []
            return data
        except Exception:
            return {"users": []}

    def _write(self, data: Dict[str, Any]) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def list_users(self) -> List[Dict[str, Any]]:
        return self._read()["users"]

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        wanted = username.strip().lower()
        for user in self.list_users():
            if str(user.get("username", "")).strip().lower() == wanted:
                return user
        return None

    def upsert_user(self, username: str, password: str, is_admin: bool = True, is_active: bool = True) -> Dict[str, Any]:
        username = username.strip()
        data = self._read()
        users = data["users"]
        now = int(time.time())

        existing = None
        for user in users:
            if str(user.get("username", "")).strip().lower() == username.lower():
                existing = user
                break

        record = {
            "username": username,
            "password_hash": hash_password(password),
            "is_admin": bool(is_admin),
            "is_active": bool(is_active),
            "created_at": existing.get("created_at", now) if existing else now,
            "updated_at": now,
            "last_login_at": existing.get("last_login_at") if existing else None,
        }

        if existing:
            existing.update(record)
            out = existing
        else:
            users.append(record)
            out = record

        self._write(data)
        return out

    def set_last_login(self, username: str) -> None:
        data = self._read()
        now = int(time.time())
        changed = False
        for user in data["users"]:
            if str(user.get("username", "")).strip().lower() == username.strip().lower():
                user["last_login_at"] = now
                user["updated_at"] = now
                changed = True
                break
        if changed:
            self._write(data)

    def ensure_default_admin(self, username: str, password: str) -> Dict[str, Any]:
        existing = self.get_user(username)
        if existing:
            return existing
        return self.upsert_user(username=username, password=password, is_admin=True, is_active=True)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200_000,
    )
    return f"pbkdf2_sha256$200000${salt}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds, salt, digest = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(rounds),
        ).hex()
        return hmac.compare_digest(calc, digest)
    except Exception:
        return False
