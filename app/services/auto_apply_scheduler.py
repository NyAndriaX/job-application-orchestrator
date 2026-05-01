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


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEFAULT_TARGET_HOUR = _env_int("SCHEDULER_TARGET_HOUR_MADA", 16)
DEFAULT_TARGET_MINUTE = _env_int("SCHEDULER_TARGET_MINUTE_MADA", 0)
DEFAULT_TIMEZONE_NAME = os.getenv("SCHEDULER_TIMEZONE", MADAGASCAR_TIMEZONE_NAME).strip() or MADAGASCAR_TIMEZONE_NAME


def _parse_target_times(raw_value: str) -> list[tuple[int, int]]:
    target_times: list[tuple[int, int]] = []
    for raw_item in raw_value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        parts = item.split(":")
        if len(parts) != 2:
            continue
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            continue
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            target_times.append((hour, minute))
    return sorted(set(target_times))


def _load_target_times() -> list[tuple[int, int]]:
    fallback_time = f"{DEFAULT_TARGET_HOUR:02d}:{DEFAULT_TARGET_MINUTE:02d}"
    raw_target_times = os.getenv("SCHEDULER_TARGET_TIMES_MADA", fallback_time)
    parsed = _parse_target_times(raw_target_times)
    if parsed:
        return parsed
    return [(DEFAULT_TARGET_HOUR, DEFAULT_TARGET_MINUTE)]


DEFAULT_TARGET_TIMES = _load_target_times()

_scheduler_started = False
_scheduler_lock = threading.Lock()


def _get_madagascar_timezone() -> timezone | ZoneInfo:
    try:
        return ZoneInfo(DEFAULT_TIMEZONE_NAME)
    except Exception:
        return timezone(timedelta(hours=3))


def _seconds_until_next_run(now_local: datetime, target_times: list[tuple[int, int]]) -> tuple[float, tuple[int, int]]:
    next_candidates: list[tuple[datetime, tuple[int, int]]] = []
    for target_hour, target_minute in target_times:
        next_run = now_local.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if now_local >= next_run:
            next_run = next_run + timedelta(days=1)
        next_candidates.append((next_run, (target_hour, target_minute)))
    next_run_dt, next_target = min(next_candidates, key=lambda item: item[0])
    return max((next_run_dt - now_local).total_seconds(), 1.0), next_target


def _run_auto_apply_for_all_users(*, trigger: str, scheduled_hour: int, scheduled_minute: int) -> dict[str, Any]:
    task_id = create_scheduler_task(
        trigger=trigger,
        timezone_name=DEFAULT_TIMEZONE_NAME,
        scheduled_time=f"{scheduled_hour:02d}:{scheduled_minute:02d}",
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
    configured_times = ", ".join(f"{hour:02d}:{minute:02d}" for hour, minute in DEFAULT_TARGET_TIMES)
    logger.info(
        "[scheduler] started daily auto-apply at %s (%s)",
        configured_times,
        DEFAULT_TIMEZONE_NAME,
    )
    while True:
        now_local = datetime.now(tz)
        sleep_seconds, (target_hour, target_minute) = _seconds_until_next_run(
            now_local=now_local,
            target_times=DEFAULT_TARGET_TIMES,
        )
        logger.info(
            "[scheduler] next run at %02d:%02d in %.0f seconds",
            target_hour,
            target_minute,
            sleep_seconds,
        )
        time.sleep(sleep_seconds)
        _run_auto_apply_for_all_users(
            trigger="daily_schedule",
            scheduled_hour=target_hour,
            scheduled_minute=target_minute,
        )


def run_auto_apply_now() -> dict[str, Any]:
    return _run_auto_apply_for_all_users(
        trigger="manual_run_now",
        scheduled_hour=DEFAULT_TARGET_TIMES[0][0],
        scheduled_minute=DEFAULT_TARGET_TIMES[0][1],
    )


def start_auto_apply_scheduler() -> None:
    global _scheduler_started

    with _scheduler_lock:
        if _scheduler_started:
            logger.info("[scheduler] start requested but scheduler is already running")
            return

        if not _env_bool("SCHEDULER_ENABLED", True):
            logger.info("[scheduler] disabled by SCHEDULER_ENABLED=false")
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
