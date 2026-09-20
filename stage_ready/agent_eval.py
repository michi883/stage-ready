"""Replay the trusted decision states through a Bedrock model and score its answers.

The demo's cached decisions are the trusted record of what the agent should do at each DECIDE:
nine states over Sandy, Ethel and Zach (three each). This drives the loop along those exact paths
with the cached backend, and at every DECIDE snapshots the prompt the live backend would send —
`LiveBackend.SYSTEM` and `LiveBackend._prompt`, unchanged — plus the expected decision. Then a
candidate model (Nova 2 Lite, Claude Sonnet 4.6, …) answers each state through the same
`AWS.decide` call the live run uses, and the answer is scored:

    action     the same action as the trusted decision
    strategy   the same strategy id, where the action takes one
    cites      names at least one of the measured findings the state turns on — the failing gates
               of the latest verification, else the failing findings; a clean state has no such requirement
    schema     the tool was called and its input validates against models.DECISION_TOOL_SCHEMA
    latency, tokens

Nothing here changes a prompt, a finding, a threshold or an allowed action: a model either makes
the trusted decision from the same evidence, or it does not.

    python3 -m stage_ready agent-eval [--model ID] [--repeat N] [--clips …] [--json]
"""
from __future__ import annotations

import json
import time
from typing import Any

from .backends.cached import CachedBackend
from .backends.live import LiveBackend
from .loop import run
from .models import DECISION_TOOL_SCHEMA, Decision, to_dict
from .profile import Profile


class _Capturing(CachedBackend):
    """The cached backend, recording each DECIDE's exact prompt and the trusted answer."""
    name = "cached"

    def __init__(self):
        self.states: list[dict[str, Any]] = []
        self._proxy = LiveBackend(local=True)

    def decide(self, clip, profile, state):
        d = super().decide(clip, profile, state)
        relevant: list[str] = []
        v = state.last_verify
        if v is not None and not v.passed:
            relevant = [g.id for g in v.failing]
        elif state.findings and any(f.status == "fail" for f in state.findings):
            relevant = [f.id for f in state.findings if f.status == "fail"]
        self.states.append({
            "clip": clip.id, "ordinal": state.decide_ordinal, "prompt": self._proxy._prompt(clip, profile, state),
            "expected": {"action": d.action, "strategy": d.strategy, "cites": list(d.cites)}, "relevant": relevant,
            "known_ids": sorted({f.id for f in state.findings} | ({g.id for g in v.gates} if v is not None else set())),
        })
        return d


def capture_states(clip_ids: list[str] | None = None) -> list[dict[str, Any]]:
    b = _Capturing()
    profile = Profile.load()
    for c in b.clips():
        if clip_ids and c.id not in clip_ids:
            continue
        list(run(c, profile, b))
    return b.states


def validate(inp: Any) -> list[str]:
    """Problems with a decision against DECISION_TOOL_SCHEMA (a light validator; no jsonschema dependency)."""
    problems = []
    if not isinstance(inp, dict):
        return ["input is not an object"]
    props = DECISION_TOOL_SCHEMA["properties"]
    for k in DECISION_TOOL_SCHEMA["required"]:
        if k not in inp:
            problems.append(f"missing {k}")
    if "action" in inp and inp["action"] not in props["action"]["enum"]:
        problems.append(f"action {inp['action']!r} not in enum")
    if "strategy" in inp and inp["strategy"] is not None and not isinstance(inp["strategy"], str):
        problems.append("strategy is not a string or null")
    if "reasoning" in inp and not isinstance(inp["reasoning"], str):
        problems.append("reasoning is not a string")
    if "cites" in inp and not (isinstance(inp["cites"], list) and all(isinstance(x, str) for x in inp["cites"])):
        problems.append("cites is not a list of strings")
    if "confidence" in inp and not (isinstance(inp["confidence"], (int, float)) and 0 <= inp["confidence"] <= 1):
        problems.append("confidence not a number in [0, 1]")
    extra = set(inp) - set(props)
    if extra:
        problems.append(f"unexpected fields {sorted(extra)}")
    return problems


def score(state: dict[str, Any], inp: dict[str, Any]) -> dict[str, Any]:
    exp = state["expected"]
    action_ok = inp.get("action") == exp["action"]
    strategy_ok = (inp.get("strategy") or None) == (exp["strategy"] or None) if exp["action"] in ("fix", "process") else True
    cites = [c for c in inp.get("cites", []) if isinstance(c, str)]
    cites_ok = (not state["relevant"]) or any(c in state["relevant"] for c in cites)
    cites_known = all(c in state["known_ids"] or c.startswith("attempt") or c.startswith("process.") or c.startswith("fix.") for c in cites)
    problems = validate(inp)
    return {"action_ok": action_ok, "strategy_ok": strategy_ok, "cites_ok": cites_ok, "cites_all_known": cites_known,
            "schema_ok": not problems, "schema_problems": problems,
            "pass": action_ok and strategy_ok and cites_ok and not problems}


def evaluate(model: str, repeat: int = 1, clip_ids: list[str] | None = None, states: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from .aws import AWS
    aws = AWS()
    states = states or capture_states(clip_ids)
    rows = []
    for st in states:
        for rep in range(repeat):
            t0 = time.time()
            try:
                inp, meta = aws.decide(LiveBackend.SYSTEM, st["prompt"], model=model)
                sc = score(st, inp)
                rows.append({"clip": st["clip"], "ordinal": st["ordinal"], "rep": rep, "expected": st["expected"], "relevant": st["relevant"],
                             "got": {"action": inp.get("action"), "strategy": inp.get("strategy"), "cites": inp.get("cites"), "confidence": inp.get("confidence"),
                                     "reasoning": (inp.get("reasoning") or "")[:600]},
                             **sc, "latency_ms": meta["latency_ms"], "input_tokens": meta["input_tokens"], "output_tokens": meta["output_tokens"],
                             "tool_choice": list(meta["tool_choice"])[0], "request_id": meta["request_id"], "error": None})
            except Exception as e:  # noqa: BLE001 — a refused or malformed answer is a result, not a crash
                rows.append({"clip": st["clip"], "ordinal": st["ordinal"], "rep": rep, "expected": st["expected"], "relevant": st["relevant"], "got": None,
                             "action_ok": False, "strategy_ok": False, "cites_ok": False, "cites_all_known": False, "schema_ok": False, "schema_problems": [],
                             "pass": False, "latency_ms": int((time.time() - t0) * 1000), "input_tokens": 0, "output_tokens": 0, "tool_choice": None,
                             "request_id": (aws.trace.records[-1].get("request_id") if aws.trace.records else None), "error": str(e)[:400]})
    n = len(rows)
    summ = {"model": model, "states": len(states), "repeat": repeat, "calls": n,
            "pass": sum(r["pass"] for r in rows), "action_ok": sum(r["action_ok"] for r in rows), "strategy_ok": sum(r["strategy_ok"] for r in rows),
            "cites_ok": sum(r["cites_ok"] for r in rows), "schema_ok": sum(r["schema_ok"] for r in rows), "errors": sum(1 for r in rows if r["error"]),
            "latency_ms_mean": round(sum(r["latency_ms"] for r in rows) / max(1, n)), "latency_ms_max": max((r["latency_ms"] for r in rows), default=0),
            "input_tokens": sum(r["input_tokens"] for r in rows), "output_tokens": sum(r["output_tokens"] for r in rows),
            "tool_choice": sorted({str(r["tool_choice"]) for r in rows})}
    return {"summary": summ, "rows": rows}


def print_report(res: dict[str, Any]) -> None:
    s = res["summary"]
    print(f"== {s['model']}: {s['pass']}/{s['calls']} pass ({s['states']} states × {s['repeat']}) · action {s['action_ok']} · strategy {s['strategy_ok']} · "
          f"cites {s['cites_ok']} · schema {s['schema_ok']} · errors {s['errors']} · latency mean {s['latency_ms_mean']} ms, max {s['latency_ms_max']} ms · "
          f"tokens {s['input_tokens']} in / {s['output_tokens']} out · tool_choice {s['tool_choice']}")
    for r in res["rows"]:
        g = r["got"] or {}
        mark = "✓" if r["pass"] else "✗"
        why = "" if r["pass"] else " — " + ", ".join(x for x in [
            "" if r["action_ok"] else f"action {g.get('action')!r} ≠ {r['expected']['action']!r}",
            "" if r["strategy_ok"] else f"strategy {g.get('strategy')!r} ≠ {r['expected']['strategy']!r}",
            "" if r["cites_ok"] else f"cites {g.get('cites')} miss {r['relevant']}",
            "" if r["schema_ok"] else f"schema {r['schema_problems']}",
            r["error"] or ""] if x)
        print(f"   {mark} {r['clip']:<6} #{r['ordinal']} rep{r['rep']}  {(g.get('action') or '-'):<8} {(g.get('strategy') or '-'):<28} {r['latency_ms']:5d} ms  {r['input_tokens']}/{r['output_tokens']} tok{why}")
