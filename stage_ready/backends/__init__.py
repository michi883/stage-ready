"""Backends do the seeing, the deciding and the doing. The loop only knows this interface.

    cached  — demo mode: every call is answered from demo/clips/<id>/*.json. Deterministic,
              no model calls, no OpenCV. The fixtures are shaped exactly like live results.
    live    — OpenCV inspection and fixers, AWS compute and S3, Bedrock for the agent.
              Uses the default AWS SDK credential chain; never handles credentials itself.

A hybrid (cached matte by source hash, live agent) is the same interface with a different
mix behind it, which is why the loop must never learn which one it has.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..models import Clip, Decision, FixResult, InspectResult, ProcessResult, VerifyResult
    from ..profile import Profile
    from ..loop import RunState


class Backend(Protocol):
    name: str

    def clips(self) -> list["Clip"]: ...

    def clip(self, clip_id: str) -> "Clip": ...

    def recognize(self, sha256: str | None = None, name: str | None = None) -> "Clip | None":
        """Match an uploaded source to a clip this backend knows, by SHA-256 first, then by
        name. The hash is what the live matte cache is keyed on, so a live backend answers
        this with the same lookup that decides whether the expensive step is a cache hit."""
        ...

    def inspect(self, clip: "Clip", target: str, profile: "Profile", state: "RunState",
                focus: list[str] | None = None) -> "InspectResult": ...

    def decide(self, clip: "Clip", profile: "Profile", state: "RunState") -> "Decision": ...

    def fix(self, clip: "Clip", strategy: str, profile: "Profile", state: "RunState") -> "FixResult": ...

    def process(self, clip: "Clip", strategy: str, profile: "Profile", state: "RunState") -> "ProcessResult": ...

    def verify(self, clip: "Clip", artifact: str, profile: "Profile", state: "RunState") -> "VerifyResult": ...


def get_backend(demo: bool) -> Backend:
    if demo:
        from .cached import CachedBackend
        return CachedBackend()
    from .live import LiveBackend
    return LiveBackend()
