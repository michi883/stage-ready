"""Demo backend: every tool call is answered from a fixture file. No model, no OpenCV.

Layout, one directory per clip under demo/clips/:

    clip.json                          the performer, the source, its brief, how an upload is recognised,
                                       and the stand-in visual numbers
    inspect.<target>.json              findings on "source", "fixed", …
    decide.<n>.json                    the agent's n-th decision in this run
    fix.<strategy>.json                e.g. fix.reframe.json
    process.<strategy>.json            e.g. process.standard.json, process.separation_targeted.json
    verify.<artifact>.json             e.g. verify.attempt_1.json

The keys are what a live run would cache on (artifact, strategy) — so a later hybrid can
replace any one of these with a real measurement and the loop will not notice. A lookup that
misses raises, loudly: an answer the fixtures do not hold is not an answer.

Every fixture carries a `provenance` line saying where its numbers come from.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import (Clip, Decision, Finding, FixResult, Gate, InspectResult, ProcessResult,
                      Stage, VerifyResult)
from ..profile import Profile

ROOT = Path(__file__).resolve().parent.parent.parent
CLIPS = ROOT / "demo" / "clips"
LINEUP = ROOT / "demo" / "lineup.json"


def lineup() -> list[dict[str, Any]]:
    """The polished demo's lineup (demo/lineup.json): the clips the sample picker offers, in order.
    Every clip under demo/clips/ stays replayable by id; the lineup is what the public page shows."""
    if not LINEUP.exists():
        return []
    return json.loads(LINEUP.read_text()).get("lineup", [])


class FixtureMissing(LookupError):
    pass


def _load(clip_id: str, key: str) -> dict[str, Any]:
    path = CLIPS / clip_id / f"{key}.json"
    if not path.exists():
        raise FixtureMissing(f"demo fixture missing: {path.relative_to(ROOT)} — the demo does not "
                             f"cover this call; record it or change the decision")
    return json.loads(path.read_text())


def _findings(items: list[dict[str, Any]]) -> list[Finding]:
    return [Finding(**f) for f in items]


def _stages(items: list[dict[str, Any]]) -> list[Stage]:
    return [Stage(**s) for s in items]


def _gates(items: list[dict[str, Any]]) -> list[Gate]:
    return [Gate(**g) for g in items]


class CachedBackend:
    name = "cached"
    CLIPS_DIR = CLIPS

    def clips(self, lineup: bool = False) -> list[Clip]:
        """Every clip with fixtures, in the show's billing order — or, with `lineup`, only the polished
        demo's three, in the lineup's order (demo/lineup.json)."""
        out = []
        for d in sorted(CLIPS.iterdir()):
            if (d / "clip.json").exists():
                out.append(self.clip(d.name))
        out = sorted(out, key=lambda c: (c.order, c.id))   # the billing, not the directory listing
        if not lineup:
            return out
        by_id = {c.id: c for c in out}
        return [by_id[e["id"]] for e in globals()["lineup"]() if e["id"] in by_id]

    def clip(self, clip_id: str) -> Clip:
        return Clip(**_load(clip_id, "clip"))

    def recognize(self, sha256: str | None = None, name: str | None = None) -> Clip | None:
        """The upload is never read here — the browser fingerprints it and asks. A SHA-256 match
        is the honest one (it is the archived source, byte for byte); a name match is a
        convenience for renamed copies and says so in `matched_by`."""
        base = (name or "").rsplit("/", 1)[-1].lower()
        by_name = None
        for c in self.clips():
            r = c.recognize
            hashes = r.get("sha256") or []
            hashes = [hashes] if isinstance(hashes, str) else hashes   # one source may exist in two containers
            if sha256 and sha256.lower() in [x.lower() for x in hashes]:
                c.recognize = {**r, "matched_by": "sha256"}
                return c
            if base and by_name is None and base in [n.lower() for n in r.get("names", [])]:
                by_name = c
        if by_name is not None:
            by_name.recognize = {**by_name.recognize, "matched_by": "name"}
        return by_name

    def inspect(self, clip, target, profile, state, focus=None) -> InspectResult:
        d = _load(clip.id, f"inspect.{target}")
        return InspectResult(target=target, findings=_findings(d["findings"]), facts=d.get("facts", {}),
                             duration_ms=d.get("duration_ms", 0), cached=True,
                             provenance=d.get("provenance", ""))

    def decide(self, clip, profile, state) -> Decision:
        d = _load(clip.id, f"decide.{state.decide_ordinal}")
        dec = Decision(action=d["action"], reasoning=d["reasoning"], strategy=d.get("strategy"),
                       cites=d.get("cites", []), confidence=d.get("confidence", 1.0),
                       model=d.get("model", "cached"), duration_ms=d.get("duration_ms", 0), cached=True)
        # A recorded decision must still be about the findings in front of it. Cheap honesty check:
        # everything it cites has to exist in the current findings or the latest verification.
        known = {f.id for f in state.findings}
        if state.last_verify is not None:
            known |= {g.id for g in state.last_verify.gates}
        unknown = [c for c in dec.cites if c not in known]
        if unknown:
            raise FixtureMissing(f"decide.{state.decide_ordinal} for clip {clip.id} cites {unknown}, "
                                 f"which the current findings do not contain")
        return dec

    def fix(self, clip, strategy, profile, state) -> FixResult:
        d = _load(clip.id, strategy)   # "fix.reframe" → fix.reframe.json
        return FixResult(strategy=strategy, artifact=d["artifact"], stages=_stages(d["stages"]),
                         changes=d.get("changes", {}), duration_ms=d.get("duration_ms", 0), cached=True,
                         provenance=d.get("provenance", ""))

    def process(self, clip, strategy, profile, state) -> ProcessResult:
        d = _load(clip.id, strategy)   # "process.standard" → process.standard.json
        return ProcessResult(strategy=strategy, artifact=d["artifact"], stages=_stages(d["stages"]),
                             params=d.get("params", {}), output=d.get("output", {}),
                             duration_ms=d.get("duration_ms", 0), cached=True,
                             provenance=d.get("provenance", ""))

    def verify(self, clip, artifact, profile, state) -> VerifyResult:
        d = _load(clip.id, f"verify.{artifact}")
        gates = _gates(d["gates"])
        # The gate list is the profile's, not the fixture's: a fixture may not quietly drop one.
        want = [g["id"] for g in profile.gates]
        have = [g.id for g in gates]
        if have != want:
            raise FixtureMissing(f"verify.{artifact} for clip {clip.id} reports gates {have}, "
                                 f"profile requires {want}")
        return VerifyResult(artifact=artifact, gates=gates, measurements=d.get("measurements", {}),
                            duration_ms=d.get("duration_ms", 0), cached=True,
                            provenance=d.get("provenance", ""))
