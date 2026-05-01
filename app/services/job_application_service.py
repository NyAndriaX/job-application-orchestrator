from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.services.mongo_service import get_job_applications_collection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_already_applied_job_urls(user_id: str, platform: str) -> set[str]:
    collection = get_job_applications_collection()
    cursor = collection.find(
        {"user_id": user_id, "platform": platform, "status": "applied"},
        {"job_url": 1, "_id": 0},
    )
    return {str(row.get("job_url", "")).strip() for row in cursor if str(row.get("job_url", "")).strip()}


def save_job_application_result(
    *,
    user_id: str,
    platform: str,
    job: dict[str, Any],
    result: dict[str, Any],
    task_id: str | None = None,
) -> None:
    job_url = str(job.get("url", "")).strip()
    if not job_url:
        return

    document = {
        "user_id": user_id,
        "platform": platform,
        "job_url": job_url,
        "job_href": str(job.get("href", "")).strip(),
        "job_title": str(job.get("title", "")).strip(),
        "job_company": str(job.get("company", "")).strip(),
        "job_contract": str(job.get("contract", "")).strip(),
        "status": str(result.get("status", "unknown")).strip().lower(),
        "message": str(result.get("message", "")).strip(),
        "task_id": str(task_id or "").strip() or None,
        "applied_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }

    collection = get_job_applications_collection()
    try:
        collection.insert_one(document)
    except DuplicateKeyError:
        collection.update_one(
            {"user_id": user_id, "platform": platform, "job_url": job_url},
            {
                "$set": {
                    "status": document["status"],
                    "message": document["message"],
                    "task_id": document["task_id"],
                    "updated_at": _utc_now_iso(),
                }
            },
        )
