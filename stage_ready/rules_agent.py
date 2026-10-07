"""The agent replaced by a rule table — the ablation's control.

One fixed policy, no model: fix what a fixer addresses, process with the standard strategy first,
retry with the one strategy that addresses the failing gate while the budget allows, deliver on a
pass, otherwise ask for a reshoot. It reads the same `RunState` the Bedrock agent reads and returns
the same `Decision`, so the loop, its guards and the trace are identical; only the chooser differs.
`python3 -m stage_ready evaluate --agent rules` runs the evaluation set with it.
"""
from __future__ import annotations

from .models import Decision


def decide(profile, state) -> Decision:
    failing = list(state.failing_finding_ids)
    tried_fixes = {f.strategy for f in state.fixes}
    rejected = {d.strategy for d in state.decisions if d.action == "fix"} - tried_fixes
    last = state.last_verify

    # 1. inspect failed something → the fixer that addresses it, once; something no fixer addresses → reshoot
    if failing and last is None:
        for s in profile.strategies("fix"):
            hits = sorted(set(s.get("addresses", [])) & set(failing))
            if hits and s["id"] not in tried_fixes and s["id"] not in rejected:
                return Decision(action="fix", strategy=s["id"], cites=hits, model="rules", confidence=1.0,
                                reasoning=f"Rule 1: inspect fails {', '.join(failing)}; {s['id']} addresses {', '.join(hits)} and has not been tried.")
        unaddressed = [f for f in failing if not any(f in s.get("addresses", []) for s in profile.strategies("fix"))]
        return Decision(action="reshoot", cites=failing, model="rules", confidence=1.0,
                        reasoning=f"Rule 1b: inspect fails {', '.join(failing)} and no allowed fixer addresses {', '.join(unaddressed) or 'them'}; a reshoot is the only honest exit.")

    # 2. nothing processed yet → the standard render
    if last is None:
        return Decision(action="process", strategy="process.standard", cites=[], model="rules", confidence=1.0,
                        reasoning="Rule 2: every inspected finding is inside the profile; process with the standard strategy first.")

    # 3. the latest verification passed → deliver
    if last.passed:
        return Decision(action="deliver", cites=[g.id for g in last.gates], model="rules", confidence=1.0,
                        reasoning="Rule 3: the latest verification passes every gate; deliver.")

    # 4. it failed → the untried process strategy that addresses every failing gate, within budget; else reshoot
    fails = [g.id for g in last.failing]
    tried = {a.strategy for a in state.attempts}
    if state.reprocesses_used < profile.retry_budget:
        for s in profile.strategies("process"):
            if s["id"] not in tried and set(fails) <= set(s.get("addresses", [])):
                return Decision(action="process", strategy=s["id"], cites=fails, model="rules", confidence=1.0,
                                reasoning=f"Rule 4: verify fails {', '.join(fails)}; {s['id']} addresses exactly that and is untried; budget {state.reprocesses_used}/{profile.retry_budget} used.")
    return Decision(action="reshoot", cites=fails, model="rules", confidence=1.0,
                    reasoning=f"Rule 4b: verify fails {', '.join(fails)} and no untried strategy addresses it within the budget ({state.reprocesses_used}/{profile.retry_budget}); reshoot.")
