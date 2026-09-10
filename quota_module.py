"""AI quota information module.

Provider I/O stays in fetch_usage.py. This adapter exposes quota as one
optional module the pet host can enable, refresh, and describe.
"""

from __future__ import annotations

import fetch_usage as fu
from info_modules import ModulePermission, ModuleRefreshResult, ModuleSpec
from pet_settings import QUOTA_MODULE_ID, QUOTA_SOURCE_IDS, quota_module_enabled
from pet_view_model import build_pools, pool_remainings

QUOTA_SPEC = ModuleSpec(
    id=QUOTA_MODULE_ID,
    title="AI 额度",
    refresh_ms=60_000,
    permissions=(
        ModulePermission(
            "本地登录",
            "只读 Grok / Cursor / Codex 已有登录，不上传聊天或项目文件",
        ),
        ModulePermission(
            "网络",
            "仅额度接口：auth.x.ai、cli-chat-proxy.grok.com、api2.cursor.sh、OpenAI",
        ),
    ),
)


class QuotaModule:
    spec = QUOTA_SPEC

    def wants_refresh(self, enabled: dict[str, bool] | None) -> bool:
        return quota_module_enabled({"enabled": enabled or {}})

    def visible_rows(self, enabled: dict[str, bool] | None) -> tuple[str, ...]:
        values = enabled or {}
        return tuple(key for key in QUOTA_SOURCE_IDS if values.get(key, True))

    def pools(self, snap: dict | None) -> dict:
        return build_pools(snap)

    def remainings(self, snap: dict | None, enabled: dict[str, bool] | None) -> list[float]:
        if not snap:
            return []
        pools = self.pools(snap)
        vals: list[float] = []
        for key in self.visible_rows(enabled):
            vals.extend(pool_remainings(pools[key]))
        return vals

    def refresh(self) -> ModuleRefreshResult:
        try:
            snap = fu.snapshot()
            fu.write_snapshot(snap)
            err = None
            if snap.get("errors"):
                err = "；".join(f"{k}: {v}" for k, v in snap["errors"].items())
            if fu.snapshot_is_usable(snap):
                return ModuleRefreshResult(ok=True, snapshot=snap, error=err)
            return ModuleRefreshResult(ok=False, snapshot=None, error=err)
        except (Exception, SystemExit) as exc:
            return ModuleRefreshResult(ok=False, snapshot=None, error=fu.redact_sensitive_text(exc))
