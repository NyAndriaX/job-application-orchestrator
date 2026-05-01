from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.mongo_service import get_users_collection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_keywords(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [item.strip().lower() for item in values if isinstance(item, str) and item.strip()]


def upsert_user_platform_config(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload.get("user_id", "")).strip()
    platform = str(payload.get("platform", "")).strip().lower()
    auth = payload.get("auth") or {}

    if not user_id:
        return {"success": False, "error": "user_id is required."}
    if not platform:
        return {"success": False, "error": "platform is required."}
    if not isinstance(auth, dict):
        return {"success": False, "error": "auth must be an object."}

    users = get_users_collection()
    updated = users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                f"platform_configs.{platform}.auth": auth,
                f"platform_configs.{platform}.updated_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }
        },
    )
    if updated.matched_count == 0:
        return {"success": False, "error": "User not found for this user_id."}
    return {"success": True, "message": "Platform configuration saved.", "user_id": user_id, "platform": platform}


def upsert_user_profile(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload.get("user_id", "")).strip()
    filters = payload.get("filters") or []
    skills = payload.get("skills")
    excluded_keywords = payload.get("excluded_keywords")
    min_relevance_score_raw = payload.get("min_relevance_score")
    max_jobs_raw = payload.get("max_jobs")

    if not user_id:
        return {"success": False, "error": "user_id is required."}
    if not isinstance(filters, list) or any(not isinstance(item, str) or not item.strip() for item in filters):
        return {"success": False, "error": "filters must be an array of non-empty strings."}
    if skills is not None and (
        not isinstance(skills, list) or any(not isinstance(item, str) or not item.strip() for item in skills)
    ):
        return {"success": False, "error": "skills must be an array of non-empty strings."}
    if excluded_keywords is not None and (
        not isinstance(excluded_keywords, list)
        or any(not isinstance(item, str) or not item.strip() for item in excluded_keywords)
    ):
        return {"success": False, "error": "excluded_keywords must be an array of non-empty strings."}
    if min_relevance_score_raw is not None:
        try:
            min_relevance_score = int(min_relevance_score_raw)
        except (TypeError, ValueError):
            return {"success": False, "error": "min_relevance_score must be an integer >= 0."}
        if min_relevance_score < 0:
            return {"success": False, "error": "min_relevance_score must be an integer >= 0."}
    if max_jobs_raw is not None:
        try:
            max_jobs = int(max_jobs_raw)
        except (TypeError, ValueError):
            return {"success": False, "error": "max_jobs must be an integer >= 1."}
        if max_jobs < 1:
            return {"success": False, "error": "max_jobs must be an integer >= 1."}

    profile_set = {"profile.filters": _normalize_keywords(filters)}
    if skills is not None:
        profile_set["profile.skills"] = _normalize_keywords(skills)
    if excluded_keywords is not None:
        profile_set["profile.excluded_keywords"] = _normalize_keywords(excluded_keywords)
    if min_relevance_score_raw is not None:
        profile_set["profile.min_relevance_score"] = int(min_relevance_score_raw)
    if max_jobs_raw is not None:
        profile_set["profile.max_jobs"] = int(max_jobs_raw)

    users = get_users_collection()
    updated = users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                **profile_set,
                "updated_at": _utc_now_iso(),
            }
        },
    )
    if updated.matched_count == 0:
        return {"success": False, "error": "User not found for this user_id."}
    return {"success": True, "message": "User profile updated.", "user_id": user_id}


def get_user_platform_config(user_id: str, platform: str) -> dict[str, Any] | None:
    users = get_users_collection()
    user_doc = users.find_one({"user_id": user_id})
    if not user_doc:
        return None
    platform_configs = user_doc.get("platform_configs") or {}
    config = platform_configs.get(platform)
    if not isinstance(config, dict):
        return None
    return config


def save_browser_state_if_missing(user_id: str, platform: str, browser_state: dict[str, Any]) -> None:
    if not isinstance(browser_state, dict) or not browser_state:
        return

    users = get_users_collection()
    user_doc = users.find_one({"user_id": user_id})
    if not user_doc:
        return

    platform_configs = user_doc.get("platform_configs") or {}
    config = platform_configs.get(platform) or {}
    existing_auth = config.get("auth") or {}
    if isinstance(existing_auth.get("browser_state"), dict) and existing_auth.get("browser_state"):
        return

    users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                f"platform_configs.{platform}.auth.browser_state": browser_state,
                f"platform_configs.{platform}.auth.session_storage": browser_state.get("session_storage", {}),
                f"platform_configs.{platform}.updated_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }
        },
    )
