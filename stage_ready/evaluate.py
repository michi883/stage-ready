"""The evaluation: N labelled inputs through the real loop, scored against the labels (PLAN step 5).

    python3 -m stage_ready evaluate [--agent bedrock|rules] [--items id…] [--prepare] [--report]

`demo/eval/set.json` is the set: real recordings, derived excerpts and synthesised negatives with
one known defect each (input-side: pillarbox, too close, crown cut, dark room, two subjects;
output-side: a delivery with a frame dropped, its audio re-encoded, 30 frames frozen). Every item
is labelled before it runs: the defects present, and the outcome an operator would accept.

For each item the loop runs exactly as it does live — INSPECT / FIX / VERIFY measured here with
OpenCV 5 (`ArchiveMeasurer`, the DNN second opinion), PROCESS the archived render (a cache hit
keyed on the source hash, or the separation-targeted re-composite when the agent asks for it) —
with the agent either Bedrock (the product) or the rule table (`rules_agent.py`, the ablation).
The output-side items skip the loop and run VERIFY alone on the defective delivery.

What is scored, per item and in total:
  * outcome vs the label — and the number the product exists to make zero: **silently wrong
    deliveries**, a delivery the label says should not have happened, or a defective delivery
    every gate passed;
  * per finding/gate precision and recall against the labelled defects;
  * where the loop was wrong, and what it cost (Bedrock tokens and latency, wall time).

Results: demo/eval/results/<agent>/<item>.json, summary.json; `--report` writes
demo/eval/EVALUATION.md from whatever results exist (both agents, side by side).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .backends.cached import ROOT
from .backends.live import LiveBackend
from .loop import run
from .measure import archive_root
from .models import Clip, to_dict
from .profile import Profile

EVAL = ROOT / "demo" / "eval"
SET = EVAL / "set.json"
RESULTS = EVAL / "results"


def load_set() -> dict[str, Any]:
    return json.loads(SET.read_text())


def _clip(item: dict[str, Any]) -> Clip:
    return Clip(id=item["id"], name=item["name"], brief=item["labels"].get("why", ""), source={}, archive=json.loads(json.dumps(item["archive"])),
                recognize={"sha256": "", "names": [Path(item["source"]).name]})


def _sha(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class EvalBackend:
    """The live backend's measurer and process stage, on this machine; the agent is a choice."""

    def __init__(self, agent: str, archive: Path, opinion: str = "dnn"):
        self.name = f"eval:{agent}"
        self.agent = agent
        self.meas = LiveBackend(archive=str(archive), opinion=opinion, local=True)
        self.bedrock = LiveBackend(archive=str(archive), opinion=opinion, local=False) if agent == "bedrock" else None

    def clips(self, lineup=False):
        return []

    def inspect(self, clip, target, profile, state, focus=None):
        return self.meas.inspect(clip, target, profile, state, focus)

    def fix(self, clip, strategy, profile, state):
        return self.meas.fix(clip, strategy, profile, state)

    def process(self, clip, strategy, profile, state):
        return self.meas.process(clip, strategy, profile, state)

    def verify(self, clip, artifact, profile, state):
        return self.meas.verify(clip, artifact, profile, state)

    def decide(self, clip, profile, state):
        if self.bedrock is not None:
            return self.bedrock.decide(clip, profile, state)
        from . import rules_agent
        return rules_agent.decide(profile, state)

    def decisions(self) -> list[dict[str, Any]]:
        return list(self.bedrock._decisions) if self.bedrock is not None else []


# ---- preparation: the pipeline over an item that has no workdir yet ---------------------------------
def _ready(wd: Path) -> bool:
    """A workdir the pipeline finished: composite frames on disk (it creates the directory first)."""
    comp = wd / "comp"
    return comp.is_dir() and any(f.endswith(".png") for f in os.listdir(comp))


def prepare(item: dict[str, Any], archive: Path, log_dir: Path) -> str:
    wd = archive / item["archive"]["workdir"]
    if _ready(wd):
        return "ready"
    if item["kind"] == "gate":
        return "ready"
    src = archive / item["source"]
    out = archive / item["archive"]["artifacts"]["attempt_1"]["video"]
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{item['id']}.log"
    with open(log, "w") as f:
        r = subprocess.run([str(archive / "tools" / "midtown_red_curtain.sh"), str(src), str(out), str(wd)], cwd=archive, stdout=f, stderr=subprocess.STDOUT)
    return "ready" if r.returncode == 0 else f"refused: {_refusal(log)}"


def _refusal(log: Path) -> str:
    lines = [l.strip() for l in log.read_text().splitlines() if l.strip()]
    for l in reversed(lines):
        if l.startswith("ERROR") or "failed" in l or "die" in l:
            return l.removeprefix("ERROR: ")
    return lines[-1] if lines else "pipeline exited non-zero"


# ---- one item ------------------------------------------------------------------------------------
def run_item(item: dict[str, Any], backend: EvalBackend, profile: Profile, archive: Path, defect_map: dict[str, Any]) -> dict[str, Any]:
    t0 = time.time()
    clip = _clip(item)
    labels = item["labels"]
    out: dict[str, Any] = {"id": item["id"], "name": item["name"], "kind": item["kind"], "agent": backend.agent, "labels": labels,
                           "source": item["source"], "source_sha256": _sha(archive / item["source"]) if (archive / item["source"]).exists() else None}
    wd = archive / item["archive"]["workdir"]
    prep_log = RESULTS / "prepare" / f"{item['id']}.log"
    if item["kind"] != "gate" and not _ready(wd):
        out["outcome"] = "refused"
        out["refusal"] = _refusal(prep_log) if prep_log.exists() else "no workdir — run `evaluate --prepare`"
        out["path"] = ["prepare ✗"]
        out["wall_s"] = round(time.time() - t0, 1)
        return _score(out, defect_map)

    if item["kind"] == "gate":
        from .loop import RunState
        st = RunState(clip=clip, profile=profile)
        vr = backend.verify(clip, "attempt_1", profile, st)
        out["verify"] = [to_dict(vr)]
        out["outcome"] = "rejected" if not vr.passed else "delivered"
        out["path"] = ["verify ✗" if not vr.passed else "verify ✓"]
        out["delivery_sha256"] = _sha(archive / item["archive"]["artifacts"]["attempt_1"]["video"])
        out["wall_s"] = round(time.time() - t0, 1)
        return _score(out, defect_map)

    events = []
    n_before = len(backend.decisions())
    try:
        for ev in run(clip, profile, backend):
            events.append(ev)
    except Exception as e:  # a live stage that cannot run here is a result too
        out["outcome"] = "error"
        out["error"] = f"{type(e).__name__}: {e}"
        out["path"] = [e_["type"] for e_ in events if e_["type"] == "phase"]
        out["wall_s"] = round(time.time() - t0, 1)
        return _score(out, defect_map)
    end = events[-1]
    out["outcome"] = end["outcome"]
    out["path"] = end["path"]
    out["inspect"] = [to_dict(e["result"]) for e in events if e["type"] == "inspect.result"]
    out["fixes"] = [to_dict(e["result"]) for e in events if e["type"] == "fix.result"]
    out["verify"] = [to_dict(e["result"]) for e in events if e["type"] == "verify.result"]
    out["decisions"] = [to_dict(e["decision"]) for e in events if e["type"] == "decide.result"]
    out["guards"] = [e["reason"] for e in events if e["type"] == "guard"]
    if end["outcome"] == "delivered":
        out["delivery"] = end["delivery"]
    else:
        out["reshoot"] = end["reshoot"]
    bd = backend.decisions()[n_before:]
    out["bedrock"] = {"calls": len(bd), "input_tokens": sum(d.get("input_tokens", 0) for d in bd), "output_tokens": sum(d.get("output_tokens", 0) for d in bd),
                      "latency_ms": sum(d.get("duration_ms", 0) for d in bd)} if bd else None
    out["wall_s"] = round(time.time() - t0, 1)
    return _score(out, defect_map)


def _status(recs: list[dict[str, Any]], key: str, fid: str) -> str | None:
    for r in recs[:1]:
        for f in r.get(key, []):
            if f["id"] == fid:
                return f["status"]
    return None


def _score(out: dict[str, Any], defect_map: dict[str, Any]) -> dict[str, Any]:
    labels = out["labels"]
    expected = labels["expected_outcome"]
    outcome = out["outcome"]
    # outcome vs label: a pipeline refusal is the reshoot exit reached before the loop
    got = "reshoot" if outcome in ("reshoot", "refused") else "deliver" if outcome == "delivered" else "reject" if outcome == "rejected" else outcome
    ok = expected == "either" or expected == got or (expected == "reject" and got == "reject")
    silently_wrong = (got == "deliver" and expected in ("reshoot", "reject")) or (outcome == "delivered" and out["kind"] == "gate")
    # per-defect detection: the labelled defect's finding, in the phase where it shows
    detections = {}
    for d in labels.get("defects", []):
        m = defect_map.get(d, {})
        fid = m.get("finding")
        if outcome == "refused":
            # the pipeline refused before the loop: its pose QC is the one_subject measure (the same pose_qc.py the
            # finding wraps), so a two-subject refusal is a detection; every other label is simply not measured
            qc = "pose QC" in out.get("refusal", "")
            detections[d] = {"finding": fid, "status": "refused", "detected": True if (d == "two_subjects" and qc) else None,
                             "note": "refused before the loop: " + out.get("refusal", "")}
            continue
        if fid is None:
            detections[d] = {"finding": None, "status": None, "detected": False, "note": m.get("note", "")}
            continue
        recs = out.get("inspect", []) if m["phase"] == "inspect" else out.get("verify", [])
        st = _status(recs, "findings" if m["phase"] == "inspect" else "gates", fid)
        detections[d] = {"finding": fid, "status": st, "detected": st is not None and st != "pass"}
    # findings flagged that no label explains (false positives), over the source inspect and the first verify
    labelled = {defect_map[d]["finding"] for d in labels.get("defects", []) if defect_map.get(d, {}).get("finding")}
    flagged = set()
    for r in out.get("inspect", [])[:1]:
        flagged |= {f["id"] for f in r["findings"] if f["status"] in ("fail", "warn")}
    for r in out.get("verify", [])[:1]:
        flagged |= {g["id"] for g in r["gates"] if g["status"] == "fail"}
    out["score"] = {"expected": expected, "got": got, "outcome_ok": ok, "silently_wrong": silently_wrong, "detections": detections,
                    "unlabelled_flags": sorted(flagged - labelled), "missed": sorted(d for d, v in detections.items() if v["finding"] and v["detected"] is False)}
    if out.get("fixes"):
        fx = out["fixes"][0]
        out["score"]["fix"] = {"strategy": fx["strategy"], "expected": labels.get("expected_fix"), "resolved": bool(out.get("inspect", [])[1:]) and not any(f["status"] == "fail" for f in out["inspect"][1]["findings"])}
    return out


# ---- the run ---------------------------------------------------------------------------------------
def evaluate(agent: str = "bedrock", items: list[str] | None = None, prepare_missing: bool = False, archive: str | None = None, opinion: str = "dnn") -> dict[str, Any]:
    root = archive_root(archive)
    s = load_set()
    profile = Profile.load()
    backend = EvalBackend(agent, root, opinion=opinion)
    out_dir = RESULTS / agent
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for item in s["items"]:
        if items and item["id"] not in items:
            continue
        if prepare_missing:
            st = prepare(item, root, RESULTS / "prepare")
            print(f"  prepare {item['id']}: {st}", flush=True)
        r = run_item(item, backend, profile, root, s["defect_map"])
        (out_dir / f"{item['id']}.json").write_text(json.dumps(r, indent=1, ensure_ascii=False, default=str) + "\n")
        sc = r["score"]
        print(f"  {item['id']:22s} {r['outcome']:10s} expected {sc['expected']:8s} {'ok ' if sc['outcome_ok'] else 'NOT ok'}"
              f"{'  SILENTLY WRONG' if sc['silently_wrong'] else ''}  missed {sc['missed'] or '-'}  path {' → '.join(r['path'])}", flush=True)
        results.append(r)
    summary = summarize(results, s["defect_map"], agent)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    return summary


def summarize(results: list[dict[str, Any]], defect_map: dict[str, Any], agent: str) -> dict[str, Any]:
    n = len(results)
    loop_items = [r for r in results if r["kind"] != "gate"]
    gate_items = [r for r in results if r["kind"] == "gate"]
    per_finding: dict[str, dict[str, int]] = {}
    for r in results:
        labelled = {defect_map[d]["finding"]: d for d in r["labels"].get("defects", []) if defect_map.get(d, {}).get("finding")}
        for d, v in r["score"]["detections"].items():
            if v["finding"] and v["detected"] is not None:          # None: refused before the loop, not measured
                pf = per_finding.setdefault(v["finding"], {"tp": 0, "fp": 0, "fn": 0})
                pf["tp" if v["detected"] else "fn"] += 1
        for fid in r["score"]["unlabelled_flags"]:
            per_finding.setdefault(fid, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
    for fid, c in per_finding.items():
        c["precision"] = round(c["tp"] / (c["tp"] + c["fp"]), 2) if c["tp"] + c["fp"] else None
        c["recall"] = round(c["tp"] / (c["tp"] + c["fn"]), 2) if c["tp"] + c["fn"] else None
    bd = [r["bedrock"] for r in results if r.get("bedrock")]
    return {
        "agent": agent, "n": n, "loop_items": len(loop_items), "gate_items": len(gate_items),
        "outcome_ok": sum(r["score"]["outcome_ok"] for r in results),
        "silently_wrong": [r["id"] for r in results if r["score"]["silently_wrong"]],
        "wrong_outcome": [r["id"] for r in results if not r["score"]["outcome_ok"]],
        "missed_defects": {r["id"]: r["score"]["missed"] for r in results if r["score"]["missed"]},
        "unlabelled_flags": {r["id"]: r["score"]["unlabelled_flags"] for r in results if r["score"]["unlabelled_flags"]},
        "per_finding": per_finding,
        "outcomes": {r["id"]: {"outcome": r["outcome"], "path": r["path"], "expected": r["score"]["expected"], "ok": r["score"]["outcome_ok"],
                               "delivery": (r.get("delivery") or {}).get("measurements"), "reshoot": [i["id"] + (" (cause)" if i.get("cause") else "") for i in (r.get("reshoot") or {}).get("items", [])][:3] if r.get("reshoot") else None,
                               "wall_s": r["wall_s"], "bedrock": r.get("bedrock"), "refusal": r.get("refusal"), "error": r.get("error")} for r in results},
        "bedrock_total": {"calls": sum(b["calls"] for b in bd), "input_tokens": sum(b["input_tokens"] for b in bd), "output_tokens": sum(b["output_tokens"] for b in bd),
                          "latency_ms": sum(b["latency_ms"] for b in bd)} if bd else None,
        "wall_s": round(sum(r["wall_s"] for r in results), 1),
    }
