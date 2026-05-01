from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.services.mongo_service import get_users_collection
from app.services.orchestrator_service import run_orchestration
from app.services.scheduler_task_service import (
    append_scheduler_task_execution,
    complete_scheduler_task,
    create_scheduler_task,
)

logger = logging.getLogger(__name__)

MADAGASCAR_TIMEZONE_NAME = "Indian/Antananarivo"
DEFAULT_TARGET_HOUR = 16
DEFAULT_TARGET_MINUTE = 0

_scheduler_started = False
_scheduler_lock = threading.Lock()


def _get_madagascar_timezone() -> timezone | ZoneInfo:
    try:
        return ZoneInfo(MADAGASCAR_TIMEZONE_NAME)
    except Exception:
        return timezone(timedelta(hours=3))


def _seconds_until_next_run(now_local: datetime, target_hour: int, target_minute: int) -> float:
    next_run = now_local.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    if now_local >= next_run:
        next_run = next_run + timedelta(days=1)
    return max((next_run - now_local).total_seconds(), 1.0)


def _run_auto_apply_for_all_users(*, trigger: str) -> dict[str, Any]:
    task_id = create_scheduler_task(
        trigger=trigger,
        timezone_name=MADAGASCAR_TIMEZONE_NAME,
        scheduled_time=f"{DEFAULT_TARGET_HOUR:02d}:{DEFAULT_TARGET_MINUTE:02d}",
    )
    users = get_users_collection()
    cursor = users.find({}, {"user_id": 1, "platform_configs": 1})

    executions = 0
    successes = 0
    failures = 0
    offers_today_total = 0
    offers_matched_total = 0
    applied_total = 0
    skipped_existing_total = 0
    for user_doc in cursor:
        user_id = str(user_doc.get("user_id", "")).strip()
        if not user_id:
            continue
        platform_configs = user_doc.get("platform_configs") or {}
        if not isinstance(platform_configs, dict):
            continue

        for platform in platform_configs.keys():
            executions += 1
            payload = {"platform": platform, "mode": "auto_apply", "user_id": user_id, "task_id": task_id}
            try:
                result = run_orchestration(payload)
                if result.get("success"):
                    successes += 1
                    execution_status = "success"
                else:
                    failures += 1
                    execution_status = "failed"
                    logger.warning(
                        "[scheduler] auto-apply failed user_id=%s platform=%s error=%s",
                        user_id,
                        platform,
                        result.get("error"),
                    )
                offers_matched_count = int((result.get("navigation") or {}).get("offers_matched_count", 0))
                offers_today_count = int((result.get("navigation") or {}).get("offers_today_count", 0))
                applied_count = int(result.get("applied_count", 0))
                skipped_existing_count = int(result.get("skipped_existing_count", 0))
                offers_today_total += offers_today_count
                offers_matched_total += offers_matched_count
                applied_total += applied_count
                skipped_existing_total += skipped_existing_count

                append_scheduler_task_execution(
                    task_id,
                    {
                        "user_id": user_id,
                        "platform": platform,
                        "status": execution_status,
                        "error": result.get("error"),
                        "offers_matched_count": offers_matched_count,
                        "offers_today_count": offers_today_count,
                        "applied_count": applied_count,
                        "skipped_existing_count": skipped_existing_count,
                        "jobs_found_urls": [
                            str(job.get("url", "")).strip()
                            for job in (result.get("jobs_found") or [])
                            if isinstance(job, dict) and str(job.get("url", "")).strip()
                        ],
                        "executed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as exc:
                failures += 1
                logger.exception(
                    "[scheduler] auto-apply exception user_id=%s platform=%s exc=%s",
                    user_id,
                    platform,
                    exc,
                )
                append_scheduler_task_execution(
                    task_id,
                    {
                        "user_id": user_id,
                        "platform": platform,
                        "status": "failed",
                        "error": str(exc),
                        "offers_matched_count": 0,
                        "offers_today_count": 0,
                        "applied_count": 0,
                        "skipped_existing_count": 0,
                        "jobs_found_urls": [],
                        "executed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

    summary = {
        "executions": executions,
        "successes": successes,
        "failures": failures,
        "offers_today_count": offers_today_total,
        "offers_matched_count": offers_matched_total,
        "applied_count": applied_total,
        "skipped_existing_count": skipped_existing_total,
    }
    complete_scheduler_task(task_id, summary)
    logger.info(
        "[scheduler] daily auto-apply finished executions=%s successes=%s failures=%s",
        executions,
        successes,
        failures,
    )
    return {"task_id": task_id, **summary}


def _scheduler_loop() -> None:
    tz = _get_madagascar_timezone()
    logger.info(
        "[scheduler] started daily auto-apply at %02d:%02d (%s)",
        DEFAULT_TARGET_HOUR,
        DEFAULT_TARGET_MINUTE,
        MADAGASCAR_TIMEZONE_NAME,
    )
    while True:
        now_local = datetime.now(tz)
        sleep_seconds = _seconds_until_next_run(
            now_local=now_local,
            target_hour=DEFAULT_TARGET_HOUR,
            target_minute=DEFAULT_TARGET_MINUTE,
        )
        logger.info("[scheduler] next run in %.0f seconds", sleep_seconds)
        time.sleep(sleep_seconds)
        _run_auto_apply_for_all_users(trigger="daily_schedule")


def run_auto_apply_now() -> dict[str, Any]:
    return _run_auto_apply_for_all_users(trigger="manual_run_now")


def start_auto_apply_scheduler() -> None:
    global _scheduler_started

    with _scheduler_lock:
        if _scheduler_started:
            logger.info("[scheduler] start requested but scheduler is already running")
            return

        # Prevent double scheduler in Flask debug reloader parent process.
        if os.getenv("FLASK_ENV") == "development" and os.getenv("WERKZEUG_RUN_MAIN") != "true":
            logger.info("[scheduler] skipped in reloader parent process")
            return

        thread = threading.Thread(
            target=_scheduler_loop,
            name="auto-apply-scheduler",
            daemon=True,
        )
        thread.start()
        _scheduler_started = True
        logger.info("[scheduler] background thread launched")
