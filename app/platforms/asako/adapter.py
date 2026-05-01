from __future__ import annotations

from typing import Any

from app.platforms.base import PlatformAdapter
from app.platforms.asako.scraper import DEFAULT_FILTER, run_apply_session, run_platform_session
from app.services.job_application_service import get_already_applied_job_urls, save_job_application_result


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
        selected_filters = filters.get("job_types") or [selected_filter]
        navigation_result = run_platform_session(
            auth=auth,
            filter_names=selected_filters,
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
        user_id = str(profile.get("user_id", "")).strip()
        jobs_found = bootstrap_result.get("jobs_found", [])
        already_applied_urls = get_already_applied_job_urls(user_id=user_id, platform=self.platform_key) if user_id else set()
        pending_jobs = [
            job
            for job in jobs_found
            if isinstance(job, dict) and str(job.get("url", "")).strip() and str(job.get("url", "")).strip() not in already_applied_urls
        ]

        apply_results = run_apply_session(auth=auth, offers=pending_jobs) if pending_jobs else []
        status_by_url = {str(row.get("job_url", "")).strip(): row for row in apply_results}
        for job in pending_jobs:
            job_url = str(job.get("url", "")).strip()
            result_payload = status_by_url.get(job_url, {"status": "failed", "message": "No apply result returned."})
            if user_id:
                save_job_application_result(
                    user_id=user_id,
                    platform=self.platform_key,
                    job=job,
                    result=result_payload,
                )

        applied_count = sum(1 for row in apply_results if str(row.get("status")) == "applied")
        skipped_existing_count = len(jobs_found) - len(pending_jobs)

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
                "apply_results": apply_results,
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
            "jobs_found": jobs_found,
            "applied_count": applied_count,
            "skipped_existing_count": skipped_existing_count,
            "apply_results": apply_results,
            "message": "Auto-apply flow is active. Registration is not part of this system.",
            "navigation": navigation,
        }
