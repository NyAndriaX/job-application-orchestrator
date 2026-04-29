from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PlatformAdapter(ABC):
    """Common contract for every job platform integration."""

    @property
    @abstractmethod
    def platform_key(self) -> str:
        """Unique platform identifier used by the orchestrator."""

    @abstractmethod
    def authenticate(self, auth: dict[str, Any]) -> dict[str, Any]:
        """Authenticate against the platform (no registration flow)."""

    @abstractmethod
    def apply_automatically(
        self,
        profile: dict[str, Any],
        filters: dict[str, Any],
        auth: dict[str, Any],
    ) -> dict[str, Any]:
        """Run full automated application flow without manual intervention."""
