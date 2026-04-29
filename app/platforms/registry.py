from __future__ import annotations

from app.platforms.asako.adapter import AsakoAdapter
from app.platforms.base import PlatformAdapter
from app.platforms.getyourjob.adapter import GetYourJobAdapter


def get_platform_adapter(platform: str) -> PlatformAdapter | None:
    adapters: dict[str, PlatformAdapter] = {
        "asako": AsakoAdapter(),
        "getyourjob": GetYourJobAdapter(),
    }
    return adapters.get(platform)
