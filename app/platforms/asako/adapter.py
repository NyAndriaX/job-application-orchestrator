from __future__ import annotations

from typing import Any

from app.platforms.base import PlatformAdapter
from app.platforms.asako.scraper import DEFAULT_FILTER, run_platform_session


class AsakoAdapter(PlatformAdapter):
    @property
    def platform_key(self) -> str:
        return "asako"

    def authenticate(self, auth: dict[str, Any]) -> dict[str, Any]:
        token = auth.get("token")
        email = auth.get("email")
        password = auth.get("password")
        browser_state = auth.get("browser_state")
        session_storage = auth.get("session_storage")
        if token:
            return {
                "success": True,
                "platform": self.platform_key,
                "auth_method": "token",
                "message": "Authenticated using provided token.",
            }
        if isinstance(browser_state, dict) and browser_state:
            return {
                "success": True,
                "platform": self.platform_key,
                "auth_method": "browser_state",
                "message": "Authenticated using reusable browser state.",
            }
        if isinstance(session_storage, dict) and session_storage:
            return {
                "success": True,
                "platform": self.platform_key,
                "auth_method": "session_storage",
                "message": "Authenticated using reusable session storage.",
            }
        if email and password:
            return {
                "success": True,
                "platform": self.platform_key,
                "auth_method": "credentials",
                "message": "Authenticated using provided credentials.",
            }
        return {
            "success": False,
            "platform": self.platform_key,
            "error": "auth must include either token or both email and password.",
        }

    def _bootstrap_navigation(self, profile: dict[str, Any], filters: dict[str, Any], auth: dict[str, Any]) -> dict[str, Any]:
        selected_filter = str(filters.get("job_type", DEFAULT_FILTER))
        navigation_result = run_platform_session(
            auth=auth,
            filter_name=selected_filter,
            skills=filters.get("skills") or [],
            excluded_keywords=filters.get("excluded_keywords") or [],
            min_relevance_score=filters.get("min_relevance_score", 1),
            max_jobs=filters.get("max_jobs", 20),
        )
        if not navigation_result.get("success"):
            return navigation_result

        return {
            "success": True,
            "platform": self.platform_key,
            "profile": {"name": profile.get("name"), "email": profile.get("email")},
            "jobs_found": navigation_result.get("filtered_offers", []),
            "navigation": navigation_result,
            "message": "Platform navigation bootstrap complete on asako.",
        }

    def apply_automatically(
        self,
        profile: dict[str, Any],
        filters: dict[str, Any],
        auth: dict[str, Any],
    ) -> dict[str, Any]:
        auth_result = self.authenticate(auth)
        if not auth_result.get("success"):
            return auth_result

        bootstrap_result = self._bootstrap_navigation(profile=profile, filters=filters, auth=auth)
        if not bootstrap_result.get("success"):
            return bootstrap_result

        navigation = bootstrap_result.get("navigation") or {}
        filter_applied = bool(navigation.get("filter_applied", True))
        filter_warning = navigation.get("filter_warning")
        if not filter_applied:
            return {
                "success": False,
                "platform": self.platform_key,
                "mode": "auto_apply",
                "profile": {"name": profile.get("name"), "email": profile.get("email")},
                "auth": {
                    "authenticated": True,
                    "method": auth_result.get("auth_method"),
                },
                "message": "Authentication succeeded and session was captured, but filter step was skipped.",
                "error": filter_warning or "Filter could not be applied after authentication.",
                "navigation": navigation,
            }

        return {
            "success": True,
            "platform": self.platform_key,
            "mode": "auto_apply",
            "profile": {"name": profile.get("name"), "email": profile.get("email")},
            "auth": {
                "authenticated": True,
                "method": auth_result.get("auth_method"),
            },
            "jobs_found": bootstrap_result.get("jobs_found", []),
            "applied_count": 0,
            "message": "Auto-apply flow is active. Registration is not part of this system.",
            "navigation": navigation,
        }
