"""Typed records shared by the loop, the backends and the UI.

These are the shared language of the system (README, "Architecture"). A cached backend and a live
backend both produce exactly these, so the loop and the screen do not know which one they
are talking to.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Status = Literal["pass", "fail", "warn", "info"]
Action = Literal["inspect", "fix", "process", "deliver", "reshoot"]


@dataclass
class Finding:
    """One measurement against the profile."""
    id: str                       # profile inspection id, e.g. "subject_size"
    label: str
    status: Status
    value: Any                    # the number (or dict of numbers)
    unit: str = ""
    threshold: Any = None         # what the profile says, e.g. {"op": "<=", "value": 0.55}
    confidence: float = 1.0
    frames: str = ""              # affected frames, in words: "92% of frames", "frame 1"
    detail: str = ""              # one sentence with the number in it
    tool: str = ""                # what measured it: "detect_band.py", "pose_qc.py" …


@dataclass
class InspectResult:
    target: str                   # "source" | "fixed" | "attempt_1" …
    findings: list[Finding]
    facts: dict[str, Any] = field(default_factory=dict)   # resolution, fps, frames, duration
    duration_ms: int = 0
    cached: bool = False
    provenance: str = ""

    @property
    def failing(self) -> list[Finding]:
        return [f for f in self.findings if f.status == "fail"]


@dataclass
class Decision:
    """What the agent chose, and why. Every field is traceable to findings."""
    action: Action
    reasoning: str
    strategy: str | None = None   # a strategy id from the profile, for fix / process
    cites: list[str] = field(default_factory=list)   # finding ids that drove this
    confidence: float = 1.0
    model: str = ""               # "cached" in demo mode; a Bedrock model id live
    duration_ms: int = 0
    cached: bool = False


@dataclass
class Stage:
    id: str                       # "matte", "track", "composite" …
    label: str
    tool: str = ""
    duration_ms: int = 0          # what this costs live
    cached: bool = False          # replayed from the cache (by source hash live, by fixture in demo)
    reused: bool = False          # carried over from a previous attempt
    summary: str = ""             # the one line the pipeline prints for this stage
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class FixResult:
    strategy: str
    artifact: str                 # "fixed"
    stages: list[Stage]
    changes: dict[str, Any]       # what the fix did, in numbers
    duration_ms: int = 0
    cached: bool = False
    provenance: str = ""


@dataclass
class ProcessResult:
    strategy: str
    artifact: str                 # "attempt_1", "attempt_2"
    stages: list[Stage]
    params: dict[str, Any] = field(default_factory=dict)   # the grade actually applied
    output: dict[str, Any] = field(default_factory=dict)   # canvas, frames, head_target …
    duration_ms: int = 0
    cached: bool = False
    provenance: str = ""


@dataclass
class Gate:
    id: str
    label: str
    status: Status
    value: Any
    threshold: Any
    unit: str = ""
    detail: str = ""
    tool: str = ""


@dataclass
class VerifyResult:
    artifact: str
    gates: list[Gate]
    measurements: dict[str, Any] = field(default_factory=dict)  # numbers the UI shows
    duration_ms: int = 0
    cached: bool = False
    provenance: str = ""

    @property
    def passed(self) -> bool:
        return all(g.status != "fail" for g in self.gates)

    @property
    def failing(self) -> list[Gate]:
        return [g for g in self.gates if g.status == "fail"]


@dataclass
class Attempt:
    n: int
    strategy: str
    process: ProcessResult
    verify: VerifyResult | None = None


@dataclass
class Clip:
    id: str
    name: str                     # the performer, as billed
    brief: str                    # what this clip was recorded to exhibit
    source: dict[str, Any]        # resolution, fps, duration, frames, wardrobe …
    order: int = 0                # lineup order (the show's billing), for listings and samples
    fixture: str = ""             # archive clip the numbers come from
    stills: dict[str, str] = field(default_factory=dict)   # optional real images by artifact id
    videos: dict[str, str] = field(default_factory=dict)   # optional real videos by artifact id
    visual: dict[str, Any] = field(default_factory=dict)   # numbers the stand-in renderer uses
    recognize: dict[str, Any] = field(default_factory=dict) # how an upload is matched to this clip:
                                                            # {"sha256": hex | [hex…], "names": […]} — the
                                                            # same SHA-256 the live matte cache is keyed on
    archive: dict[str, Any] = field(default_factory=dict)   # where the archived run's files are, relative to
                                                            # the Red Curtain archive root: {"workdir", "source",
                                                            # "artifacts": {id: {"video", "composite"}}} — what
                                                            # `stage_ready.measure` computes the numbers from


def to_dict(obj: Any) -> Any:
    """Dataclasses → plain dicts, recursively, for JSON."""
    if hasattr(obj, "__dataclass_fields__"):
        d = asdict(obj)
        # expose the handy derived properties too
        for prop in ("passed", "failing"):
            if hasattr(type(obj), prop):
                v = getattr(obj, prop)
                d[prop] = to_dict(v)
        return d
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
