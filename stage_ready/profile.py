"""A Target Output Profile is data, not code. Load it, and answer questions about it."""
from __future__ import annotations

import json
from typing import Any

from .paths import ROOT
PROFILES = ROOT / "profiles"


class Profile:
    def __init__(self, data: dict[str, Any]):
        self.data = data

    @classmethod
    def load(cls, profile_id: str = "midtown_red_curtain") -> "Profile":
        path = PROFILES / f"{profile_id}.json"
        return cls(json.loads(path.read_text()))

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def gates(self) -> list[dict[str, Any]]:
        return self.data["gates"]

    @property
    def retry_budget(self) -> int:
        return int(self.data.get("retry_budget", 1))

    def strategy(self, strategy_id: str) -> dict[str, Any] | None:
        for s in self.data["strategies"]:
            if s["id"] == strategy_id:
                return s
        return None

    def strategies(self, kind: str | None = None) -> list[dict[str, Any]]:
        return [s for s in self.data["strategies"] if kind is None or s["kind"] == kind]

    def guidance(self, finding_id: str) -> str:
        return self.data.get("reshoot_guidance", {}).get(finding_id, "")

    def summary(self) -> dict[str, Any]:
        """What the screen shows in the profile header."""
        d = self.data
        return {
            "id": d["id"],
            "name": d["name"],
            "canvas": d["canvas"],
            "background": d["background"],
            "framing": d["framing"],
            "gates": d["gates"],
            "strategies": [{k: s[k] for k in ("id", "kind", "label", "cost") if k in s} for s in d["strategies"]],
            "retry_budget": d.get("retry_budget", 1),
        }
