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


def _run_auto_apply_for_all_users() -> dict[str, int]:
    users = get_users_collection()
    cursor = users.find({}, {"user_id": 1, "platform_configs": 1})

    executions = 0
    successes = 0
    failures = 0
    for user_doc in cursor:
        user_id = str(user_doc.get("user_id", "")).strip()
        if not user_id:
            continue
        platform_configs = user_doc.get("platform_configs") or {}
        if not isinstance(platform_configs, dict):
            continue

        for platform in platform_configs.keys():
            executions += 1
            payload = {"platform": platform, "mode": "auto_apply", "user_id": user_id}
            try:
                result = run_orchestration(payload)
                if result.get("success"):
                    successes += 1
                else:
                    failures += 1
                    logger.warning(
                        "[scheduler] auto-apply failed user_id=%s platform=%s error=%s",
                        user_id,
                        platform,
                        result.get("error"),
                    )
            except Exception as exc:
                failures += 1
                logger.exception(
                    "[scheduler] auto-apply exception user_id=%s platform=%s exc=%s",
                    user_id,
                    platform,
                    exc,
                )

    summary = {
        "executions": executions,
        "successes": successes,
        "failures": failures,
    }
    logger.info(
        "[scheduler] daily auto-apply finished executions=%s successes=%s failures=%s",
        executions,
        successes,
        failures,
    )
    return summary


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
        _run_auto_apply_for_all_users()


def run_auto_apply_now() -> dict[str, int]:
    return _run_auto_apply_for_all_users()


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
