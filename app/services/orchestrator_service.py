from __future__ import annotations

from typing import Any

from app.platforms.registry import get_platform_adapter
from app.services.auth_service import get_user_by_user_id
from app.services.user_platform_config_service import (
    get_user_platform_config,
    save_browser_state_if_missing,
)

SUPPORTED_MODE = "auto_apply"


def _build_platform_filters(user_doc: dict[str, Any]) -> dict[str, Any]:
    profile = user_doc.get("profile") or {}
    filters_list = profile.get("filters") or []
    skills_list = profile.get("skills") or []
    excluded_keywords_list = profile.get("excluded_keywords") or []
    min_relevance_score_raw = profile.get("min_relevance_score", 1)
    max_jobs_raw = profile.get("max_jobs", 20)
    try:
        min_relevance_score = max(int(min_relevance_score_raw), 0)
    except (TypeError, ValueError):
        min_relevance_score = 1
    try:
        max_jobs = max(int(max_jobs_raw), 1)
    except (TypeError, ValueError):
        max_jobs = 20
    if not isinstance(filters_list, list):
        return {
            "job_type": "all",
            "skills": [],
            "excluded_keywords": [],
            "min_relevance_score": min_relevance_score,
            "max_jobs": max_jobs,
        }

    normalized = [item.strip().lower() for item in filters_list if isinstance(item, str) and item.strip()]
    skills = [item.strip().lower() for item in skills_list if isinstance(item, str) and item.strip()]
    excluded_keywords = [
        item.strip().lower() for item in excluded_keywords_list if isinstance(item, str) and item.strip()
    ]
    if not normalized:
        return {
            "job_type": "all",
            "skills": skills,
            "excluded_keywords": excluded_keywords,
            "min_relevance_score": min_relevance_score,
            "max_jobs": max_jobs,
        }
    return {
        "job_type": normalized[0],
        "skills": skills,
        "excluded_keywords": excluded_keywords,
        "min_relevance_score": min_relevance_score,
        "max_jobs": max_jobs,
    }


def run_orchestration(payload: dict[str, Any]) -> dict[str, Any]:
    platform = str(payload.get("platform", "")).strip().lower()
    mode = str(payload.get("mode", SUPPORTED_MODE)).strip().lower()
    user_id = str(payload.get("user_id", "")).strip()

    if not platform:
        return {"success": False, "error": "Payload must include a non-empty string field: platform."}
    if not user_id:
        return {"success": False, "error": "Payload must include a non-empty string field: user_id."}
    if mode != SUPPORTED_MODE:
        return {"success": False, "error": f"Unsupported mode '{mode}'. Allowed value: {SUPPORTED_MODE}."}

    adapter = get_platform_adapter(platform)
    if adapter is None:
        return {
            "success": False,
            "error": f"Unsupported platform '{platform}'. Currently implemented: asako, getyourjob.",
        }

    config = get_user_platform_config(user_id=user_id, platform=platform)
    if not config:
        return {
            "success": False,
            "error": "No platform configuration found for this user. Add platform configuration first.",
        }

    auth = config.get("auth") or {}
    if not isinstance(auth, dict):
        return {"success": False, "error": "Stored configuration is invalid for this user/platform."}

    user_doc = get_user_by_user_id(user_id)
    if not user_doc:
        return {"success": False, "error": "User not found for this user_id."}
    profile = {
        "name": user_doc.get("full_name"),
        "email": user_doc.get("email"),
    }
    filters = _build_platform_filters(user_doc)

    result = adapter.apply_automatically(profile=profile, filters=filters, auth=auth)
    navigation = result.get("navigation") or {}
    browser_state = navigation.get("browser_state")
    session_storage = navigation.get("session_storage")
    save_browser_state_if_missing(user_id=user_id, platform=platform, browser_state=browser_state)
    result["user_id"] = user_id
    if isinstance(browser_state, dict) and browser_state:
        result["browser_state_saved"] = True
    if isinstance(session_storage, dict) and session_storage:
        result["session_saved"] = True
    return result
