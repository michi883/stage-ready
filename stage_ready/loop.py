"""The core loop: inspect → decide → fix | process → verify → deliver | reshoot.

The agent chooses; the loop enforces what the agent may not skip (README, "The loop"):

  * a fix is always re-inspected, and rejected if it created a new failing finding;
  * a process is always verified against the profile's gates;
  * deliver is refused unless the latest verification passed;
  * a strategy must be one the profile allows;
  * the retry budget bounds reprocessing; when it is spent, the exit is a reshoot request.

`run()` is a generator of plain-dict events so a server can stream them and a test can
collect them. It does not know whether the backend is cached or live.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from .backends import Backend
from .models import (Attempt, Clip, Decision, FixResult, InspectResult, ProcessResult,
                     VerifyResult, to_dict)
from .profile import Profile

MAX_STEPS = 12   # hard stop on decisions per run; the retry budget is the real bound


@dataclass
class RunState:
    clip: Clip
    profile: Profile
    working: str = "source"                     # artifact the next fix/process reads
    findings: list = field(default_factory=list)
    inspections: list[InspectResult] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    fixes: list[FixResult] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    reprocesses_used: int = 0
    path: list[str] = field(default_factory=list)

    @property
    def decide_ordinal(self) -> int:
        return len(self.decisions) + 1

    @property
    def last_verify(self) -> VerifyResult | None:
        for a in reversed(self.attempts):
            if a.verify is not None:
                return a.verify
        return None

    @property
    def failing_finding_ids(self) -> set[str]:
        return {f.id for f in self.findings if f.status == "fail"}

    def budget(self) -> dict[str, int]:
        return {"reprocesses_used": self.reprocesses_used, "retry_budget": self.profile.retry_budget}


def _ev(kind: str, clip_id: str, **payload: Any) -> dict[str, Any]:
    return {"type": kind, "clip": clip_id, **to_dict(payload)}


def _guard(state: RunState, d: Decision) -> str | None:
    """Return a reason if the decision is not allowed as made."""
    p = state.profile
    if d.action in ("fix", "process"):
        s = p.strategy(d.strategy or "")
        if s is None:
            return f"strategy {d.strategy!r} is not in the profile's allowed strategies"
        if s["kind"] != d.action:
            return f"strategy {d.strategy!r} is a {s['kind']}, not a {d.action}"
    if d.action == "process" and state.attempts and state.reprocesses_used >= p.retry_budget:
        return f"retry budget spent ({state.reprocesses_used}/{p.retry_budget}); only reshoot remains"
    if d.action == "deliver":
        v = state.last_verify
        if v is None:
            return "nothing has been verified yet"
        if not v.passed:
            return "latest verification failed: " + ", ".join(g.id for g in v.failing)
    return None


def _reshoot_request(state: RunState) -> dict[str, Any]:
    """The other exit: the defect, the number behind it, the capture change."""
    items = []
    v = state.last_verify
    if v is not None:
        for g in v.failing:
            items.append({"id": g.id, "label": g.label, "value": g.value, "threshold": g.threshold,
                          "unit": g.unit, "detail": g.detail, "guidance": state.profile.guidance(g.id)})
    for f in state.findings:
        if f.status == "fail" and all(i["id"] != f.id for i in items):
            items.append({"id": f.id, "label": f.label, "value": f.value, "threshold": f.threshold,
                          "unit": f.unit, "detail": f.detail, "guidance": state.profile.guidance(f.id)})
    return {"items": items, "attempts": len(state.attempts), "budget": state.budget()}


def _delivery(state: RunState) -> dict[str, Any]:
    a = state.attempts[-1]
    return {
        "artifact": a.process.artifact,
        "strategy": a.strategy,
        "output": a.process.output,
        "measurements": a.verify.measurements if a.verify else {},
        "attempts": len(state.attempts),
        "fixes": [f.strategy for f in state.fixes],
        "budget": state.budget(),
    }


def run(clip: Clip, profile: Profile, backend: Backend) -> Iterator[dict[str, Any]]:
    cid = clip.id
    state = RunState(clip=clip, profile=profile)
    yield _ev("run.start", cid, clip=clip, profile=profile.summary(), backend=backend.name)

    # ---- inspect the source: cheap checks before anything expensive --------------------
    yield _ev("phase", cid, phase="inspect", target="source")
    ins = backend.inspect(clip, "source", profile, state)
    state.inspections.append(ins)
    state.findings = ins.findings
    state.path.append("inspect")
    yield _ev("inspect.result", cid, result=ins)

    for _ in range(MAX_STEPS):
        # ---- decide -------------------------------------------------------------------
        yield _ev("phase", cid, phase="decide", ordinal=state.decide_ordinal, budget=state.budget())
        d = backend.decide(clip, profile, state)
        reason = _guard(state, d)
        if reason:
            yield _ev("guard", cid, decision=d, reason=reason)
            # The loop, not the agent, owns the exits. A refused decision falls through to the
            # only action that is always allowed once the budget is spent: the reshoot request.
            if d.action in ("process", "deliver") and state.reprocesses_used >= profile.retry_budget \
                    and state.last_verify is not None and not state.last_verify.passed:
                d = Decision(action="reshoot", reasoning=f"forced by the loop: {reason}",
                             cites=[g.id for g in state.last_verify.failing], model="loop")
            else:
                state.decisions.append(d)
                continue
        state.decisions.append(d)
        yield _ev("decide.result", cid, decision=d, ordinal=len(state.decisions))

        # ---- act ----------------------------------------------------------------------
        if d.action == "inspect":
            state.path.append("inspect")
            yield _ev("phase", cid, phase="inspect", target=state.working, focus=d.cites)
            ins = backend.inspect(clip, state.working, profile, state, focus=d.cites)
            state.inspections.append(ins)
            state.findings = ins.findings
            yield _ev("inspect.result", cid, result=ins)

        elif d.action == "fix":
            state.path.append("fix")
            yield _ev("phase", cid, phase="fix", strategy=d.strategy)
            fx = backend.fix(clip, d.strategy, profile, state)
            yield _ev("fix.result", cid, result=fx)
            # A fix is always re-inspected; one that creates a new defect is rejected.
            before = state.failing_finding_ids
            yield _ev("phase", cid, phase="inspect", target=fx.artifact, after_fix=d.strategy)
            ins = backend.inspect(clip, fx.artifact, profile, state)
            state.inspections.append(ins)
            new_defects = {f.id for f in ins.failing} - before
            state.path.append("inspect")
            yield _ev("inspect.result", cid, result=ins, before=sorted(before),
                      resolved=sorted(before - {f.id for f in ins.failing}), new_defects=sorted(new_defects))
            if new_defects:
                yield _ev("fix.rejected", cid, strategy=d.strategy, new_defects=sorted(new_defects))
            else:
                state.fixes.append(fx)
                state.working = fx.artifact
                state.findings = ins.findings

        elif d.action == "process":
            n = len(state.attempts) + 1
            if state.attempts:
                state.reprocesses_used += 1
            state.path.append("process" if n == 1 else "reprocess")
            yield _ev("phase", cid, phase="process", strategy=d.strategy, attempt=n, source=state.working)
            pr = backend.process(clip, d.strategy, profile, state)
            yield _ev("process.result", cid, result=pr, attempt=n)
            # A process is always verified, against the profile's gates, by measurement.
            state.path.append("verify")
            yield _ev("phase", cid, phase="verify", artifact=pr.artifact, attempt=n)
            vr = backend.verify(clip, pr.artifact, profile, state)
            state.attempts.append(Attempt(n=n, strategy=d.strategy, process=pr, verify=vr))
            state.path[-1] = "verify ✓" if vr.passed else "verify ✗"
            yield _ev("verify.result", cid, result=vr, attempt=n, passed=vr.passed, budget=state.budget())

        elif d.action == "deliver":
            state.path.append("deliver")
            yield _ev("phase", cid, phase="deliver")
            yield _ev("run.end", cid, outcome="delivered", delivery=_delivery(state),
                      path=list(state.path), attempts=[{"n": a.n, "strategy": a.strategy,
                      "passed": a.verify.passed if a.verify else None} for a in state.attempts])
            return

        elif d.action == "reshoot":
            state.path.append("reshoot")
            yield _ev("phase", cid, phase="reshoot")
            yield _ev("run.end", cid, outcome="reshoot", reshoot=_reshoot_request(state),
                      path=list(state.path), attempts=[{"n": a.n, "strategy": a.strategy,
                      "passed": a.verify.passed if a.verify else None} for a in state.attempts])
            return

    yield _ev("run.end", cid, outcome="reshoot", reshoot=_reshoot_request(state),
              path=list(state.path) + ["stopped: step limit"], attempts=[])
