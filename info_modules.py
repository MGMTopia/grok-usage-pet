"""Optional information-module boundary for the desktop-pet core.

The pet window talks to this host, not to provider clients. A module may
refresh, describe permissions, and supply display rows. Exceptions stay inside
the module result so one failure cannot take down the pet or other modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from pet_settings import CLOCK_MODULE_ID, QUOTA_MODULE_ID, QUOTA_SOURCE_IDS, quota_module_enabled

KNOWN_MODULE_IDS = (QUOTA_MODULE_ID, CLOCK_MODULE_ID)


@dataclass(frozen=True)
class ModulePermission:
    title: str
    detail: str


@dataclass(frozen=True)
class ModuleSpec:
    id: str
    title: str
    permissions: tuple[ModulePermission, ...]
    refresh_ms: int | None = 60_000

    def permission_hint(self) -> str:
        return "；".join(f"{item.title}：{item.detail}" for item in self.permissions)


@dataclass
class ModuleRefreshResult:
    ok: bool
    snapshot: dict | None = None
    error: str | None = None
    remainings: list[float] = field(default_factory=list)


class InfoModule(Protocol):
    spec: ModuleSpec

    def wants_refresh(self, enabled: dict[str, bool] | None) -> bool:
        ...

    def refresh(self) -> ModuleRefreshResult:
        ...


class ModuleHost:
    def __init__(self, modules: tuple[InfoModule, ...]):
        self._modules = modules

    def all(self) -> tuple[InfoModule, ...]:
        return self._modules

    def get(self, module_id: str) -> InfoModule | None:
        for module in self._modules:
            if module.spec.id == module_id:
                return module
        return None

    def wants_refresh(self, enabled: dict[str, bool] | None) -> bool:
        return any(module.wants_refresh(enabled) for module in self._modules)

    def refresh_ms(self, enabled: dict[str, bool] | None) -> int | None:
        intervals = [
            module.spec.refresh_ms
            for module in self._modules
            if module.wants_refresh(enabled) and module.spec.refresh_ms
        ]
        return min(intervals) if intervals else None

    def refresh_enabled(self, enabled: dict[str, bool] | None) -> dict[str, ModuleRefreshResult]:
        results: dict[str, ModuleRefreshResult] = {}
        for module in self._modules:
            if not module.wants_refresh(enabled):
                continue
            try:
                results[module.spec.id] = module.refresh()
            except (Exception, SystemExit) as exc:
                results[module.spec.id] = ModuleRefreshResult(ok=False, error=str(exc)[:240])
        return results


def known_modules() -> tuple[str, ...]:
    return KNOWN_MODULE_IDS


def quota_sources() -> tuple[str, ...]:
    return QUOTA_SOURCE_IDS


def is_quota_enabled(state: dict | None) -> bool:
    return quota_module_enabled(state)


def default_host() -> ModuleHost:
    from clock_module import ClockModule
    from quota_module import QuotaModule

    return ModuleHost((QuotaModule(), ClockModule()))
