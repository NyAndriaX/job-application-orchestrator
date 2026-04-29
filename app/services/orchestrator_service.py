from __future__ import annotations

from typing import Any

from app.platforms.registry import get_platform_adapter

SUPPORTED_MODE = "auto_apply"


def run_orchestration(payload: dict[str, Any]) -> dict[str, Any]:
    platform = str(payload.get("platform", "")).strip().lower()
    mode = str(payload.get("mode", SUPPORTED_MODE)).strip().lower()
    profile = payload.get("profile") or {}
    filters = payload.get("filters") or {}
    auth = payload.get("auth") or {}

    if not platform:
        return {"success": False, "error": "Payload must include a non-empty string field: platform."}
    if mode != SUPPORTED_MODE:
        return {"success": False, "error": f"Unsupported mode '{mode}'. Allowed value: {SUPPORTED_MODE}."}
    if not isinstance(profile, dict):
        return {"success": False, "error": "profile must be an object."}
    if not isinstance(filters, dict):
        return {"success": False, "error": "filters must be an object."}
    if not isinstance(auth, dict):
        return {"success": False, "error": "auth must be an object."}
    if not auth:
        return {
            "success": False,
            "error": "auth is required. Provide token or credentials (email/password).",
        }

    adapter = get_platform_adapter(platform)
    if adapter is None:
        return {
            "success": False,
            "error": f"Unsupported platform '{platform}'. Currently implemented: asako, getyourjob.",
        }

    return adapter.apply_automatically(profile=profile, filters=filters, auth=auth)
