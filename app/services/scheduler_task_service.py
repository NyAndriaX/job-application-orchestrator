from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services.mongo_service import get_scheduler_tasks_collection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_scheduler_task(*, trigger: str, timezone_name: str, scheduled_time: str) -> str:
    task_id = str(uuid4())
    collection = get_scheduler_tasks_collection()
    collection.insert_one(
        {
            "task_id": task_id,
            "trigger": trigger,
            "timezone": timezone_name,
            "scheduled_time": scheduled_time,
            "status": "running",
            "started_at": _utc_now_iso(),
            "finished_at": None,
            "summary": {"executions": 0, "successes": 0, "failures": 0},
            "executions": [],
        }
    )
    return task_id


def append_scheduler_task_execution(task_id: str, execution: dict[str, Any]) -> None:
    collection = get_scheduler_tasks_collection()
    collection.update_one(
        {"task_id": task_id},
        {"$push": {"executions": execution}},
    )


def complete_scheduler_task(task_id: str, summary: dict[str, Any]) -> None:
    collection = get_scheduler_tasks_collection()
    normalized_summary = {key: int(value) for key, value in summary.items()}
    collection.update_one(
        {"task_id": task_id},
        {
            "$set": {
                "status": "finished",
                "finished_at": _utc_now_iso(),
                "summary": normalized_summary,
            }
        },
    )
