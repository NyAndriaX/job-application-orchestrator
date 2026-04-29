from __future__ import annotations

from typing import Any

from app.platforms.base import PlatformAdapter
from app.platforms.getyourjob.scraper import DEFAULT_FILTER, open_homepage


class GetYourJobAdapter(PlatformAdapter):
    @property
    def platform_key(self) -> str:
        return "getyourjob"

    def authenticate(self, auth: dict[str, Any]) -> dict[str, Any]:
        token = auth.get("token")
        email = auth.get("email")
        password = auth.get("password")
        if token:
            return {
                "success": True,
                "platform": self.platform_key,
                "auth_method": "token",
                "message": "Authenticated using provided token.",
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

    def _bootstrap_navigation(self, profile: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
        selected_filter = str(filters.get("job_type", DEFAULT_FILTER))
        navigation_result = open_homepage(filter_name=selected_filter)
        if not navigation_result.get("success"):
            return navigation_result

        return {
            "success": True,
            "platform": self.platform_key,
            "profile": {"name": profile.get("name"), "email": profile.get("email")},
            "jobs_found": [],
            "navigation": navigation_result,
            "message": "Platform navigation bootstrap complete on getyourjob.",
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

        bootstrap_result = self._bootstrap_navigation(profile=profile, filters=filters)
        if not bootstrap_result.get("success"):
            return bootstrap_result

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
            "navigation": bootstrap_result.get("navigation"),
        }
