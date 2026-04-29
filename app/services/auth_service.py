from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.services.mongo_service import get_users_collection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_user(payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    full_name = str(payload.get("full_name", "")).strip()
    filters = payload.get("filters") or []

    if not full_name:
        return {"success": False, "error": "full_name is required."}
    if not email:
        return {"success": False, "error": "email is required."}
    if len(password) < 8:
        return {"success": False, "error": "password must contain at least 8 characters."}
    if not isinstance(filters, list) or any(not isinstance(item, str) or not item.strip() for item in filters):
        return {"success": False, "error": "filters must be an array of non-empty strings."}

    users = get_users_collection()
    user_doc = {
        "user_id": str(uuid4()),
        "full_name": full_name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "profile": {"filters": [item.strip().lower() for item in filters]},
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }

    try:
        users.insert_one(user_doc)
    except DuplicateKeyError:
        return {"success": False, "error": "An account with this email already exists."}

    return {
        "success": True,
        "message": "User registered successfully.",
        "user": {
            "user_id": user_doc["user_id"],
            "full_name": user_doc["full_name"],
            "email": user_doc["email"],
        },
    }


def get_user_by_user_id(user_id: str) -> dict[str, Any] | None:
    users = get_users_collection()
    return users.find_one({"user_id": user_id})


def login_user(payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    if not email or not password:
        return {"success": False, "error": "email and password are required."}

    users = get_users_collection()
    user = users.find_one({"email": email})
    if not user:
        return {"success": False, "error": "Invalid email or password."}

    password_hash = user.get("password_hash")
    if not isinstance(password_hash, str) or not check_password_hash(password_hash, password):
        return {"success": False, "error": "Invalid email or password."}

    return {
        "success": True,
        "message": "Login successful.",
        "user": {
            "user_id": user.get("user_id"),
            "full_name": user.get("full_name"),
            "email": user.get("email"),
        },
    }
