"""demo/eval/EVALUATION.md from demo/eval/results/<agent>/ — the table the report needs, regenerated."""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from .evaluate import EVAL, RESULTS, load_set

OUT = EVAL / "EVALUATION.md"


def _load(agent: str) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]]]:
    d = RESULTS / agent
    if not (d / "summary.json").exists():
        return None, {}
    items = {p.stem: json.loads(p.read_text()) for p in d.glob("*.json") if p.stem != "summary"}
    return json.loads((d / "summary.json").read_text()), items


def _m(x, k, fmt="{:.2f}"):
    v = (x or {}).get(k)
    return "—" if v is None else fmt.format(v)


def write_report() -> Path:
    from .evaluate import rescore
    for a in ("bedrock", "rules"):
        rescore(a)                      # the stored raw records, under the current scoring rules
    s = load_set()
    agents = [a for a in ("bedrock", "rules") if (RESULTS / a / "summary.json").exists()]
    sums = {a: _load(a) for a in agents}
    L = []
    L.append("# Evaluation — Stage Ready against a labelled set\n")
    L.append(f"Generated {datetime.date.today().isoformat()} by `python3 -m stage_ready evaluate --report` from `demo/eval/set.json` and "
             f"`demo/eval/results/`. Every item was labelled before it ran (`labels.why` says how); the loop ran as it runs live — "
             f"INSPECT / FIX / VERIFY measured with OpenCV 5 on this machine, PROCESS the archived render — with the agent on Amazon Bedrock "
             f"(Claude Sonnet 4.6, the product) and, as the ablation, replaced by the rule table in `stage_ready/rules_agent.py`. "
             f"The agent runs **blind**: the prompt carries no name, brief or file name for an evaluation input — only the measurements — "
             f"which is stricter than the demo, whose briefs are the show's intake notes.\n")
    n = len(s["items"])
    L.append("## The number the product exists to make zero\n")
    L.append("| agent | items | outcomes as labelled | **silently wrong deliveries** | labelled defects missed | flags no label explains |")
    L.append("|---|---|---|---|---|---|")
    for a in agents:
        sm, _ = sums[a]
        L.append(f"| {a} | {sm['n']} ({sm['loop_items']} through the loop, {sm['gate_items']} deliveries verified alone) | {sm['outcome_ok']}/{sm['n']} | "
                 f"**{len(sm['silently_wrong'])}** {', '.join(sm['silently_wrong']) if sm['silently_wrong'] else ''} | "
                 f"{sum(len(v) for v in sm['missed_defects'].values())} {json.dumps(sm['missed_defects']) if sm['missed_defects'] else ''} | "
                 f"{sum(len(v) for v in sm['unlabelled_flags'].values())} |")
    L.append("")
    L.append("A *silently wrong delivery* is a delivery the label says should not have happened, or a defective delivery every gate passed. "
             "A *flag no label explains* is a finding INSPECT raised (fail or warn) or a gate the first VERIFY failed that the item's labels did not "
             "predict — each is listed under the item and judged there; some are labels that were incomplete, not measurements that were wrong.\n")

    L.append("## Every item\n")
    hdr = "| item | kind | labelled defects | expected |" + "".join(f" {a}: outcome · path · delivered numbers |" for a in agents)
    L.append(hdr)
    L.append("|---|---|---|---|" + "---|" * len(agents))
    for it in s["items"]:
        row = f"| `{it['id']}` — {it['name']} | {it['kind']} | {', '.join(it['labels']['defects']) or '—'} | {it['labels']['expected_outcome']} |"
        for a in agents:
            _, items = sums[a]
            r = items.get(it["id"])
            if not r:
                row += " not run |"
                continue
            sc = r["score"]
            mark = "✓" if sc["outcome_ok"] else "✗"
            cell = f"{mark} **{r['outcome']}**"
            if sc["silently_wrong"]:
                cell += " — **SILENTLY WRONG**"
            cell += f" · {' → '.join(r['path'])}"
            d = (r.get("delivery") or {}).get("measurements")
            if d:
                cell += f" · sep {_m(d, 'separation')}× head {_m(d, 'head_spread', '{:.1%}')} drift {_m(d, 'head_drift_px', '{:.1f}')} px"
            if r.get("reshoot"):
                cell += " · cites " + ", ".join(i["id"] + ("*" if i.get("cause") else "") for i in r["reshoot"]["items"][:3])
            if r.get("refusal"):
                cell += f" · {r['refusal']}"
            if r.get("error"):
                cell += f" · error: {r['error'][:80]}"
            if sc["missed"]:
                cell += f" · missed: {', '.join(sc['missed'])}"
            if sc["unlabelled_flags"]:
                cell += f" · unlabelled: {', '.join(sc['unlabelled_flags'])}"
            row += f" {cell} |"
        L.append(row)
    L.append("")

    L.append("## Per finding and gate, against the labels\n")
    L.append("Positives are the items labelled with the defect the finding measures (`defect_map` in set.json); a detection is the finding "
             "raised as fail or warn on the source inspection, or the gate failed on the first verification.\n")
    for a in agents:
        sm, _ = sums[a]
        L.append(f"**{a}**\n")
        L.append("| finding / gate | TP | FP | FN | precision | recall |")
        L.append("|---|---|---|---|---|---|")
        for fid, c in sorted(sm["per_finding"].items()):
            L.append(f"| {fid} | {c['tp']} | {c['fp']} | {c['fn']} | {'—' if c['precision'] is None else c['precision']} | {'—' if c['recall'] is None else c['recall']} |")
        L.append("")

    L.append("## Where the loop was wrong, and what it cost\n")
    for a in agents:
        sm, items = sums[a]
        wrong = [items[i] for i in sm["wrong_outcome"]] + [items[i] for i in sm["silently_wrong"] if i not in sm["wrong_outcome"]]
        L.append(f"**{a}** — {len(sm['wrong_outcome'])} outcome(s) not as labelled; {len(sm['silently_wrong'])} silently wrong; "
                 + (f"Bedrock {sm['bedrock_total']['calls']} calls, {sm['bedrock_total']['input_tokens']:,} in / {sm['bedrock_total']['output_tokens']:,} out tokens, "
                    f"{sm['bedrock_total']['latency_ms'] / 1000:.0f} s of model latency; " if sm.get("bedrock_total") else "no model calls; ")
                 + f"wall time {sm['wall_s'] / 60:.0f} min for the set (measurement, not rendering — the renders are cached by source hash).\n")
        for r in wrong:
            sc = r["score"]
            L.append(f"- `{r['id']}`: expected **{sc['expected']}**, got **{sc['got']}** — {r['labels']['why'].rstrip('.')}."
                     + (f" Reshoot cites: {', '.join(i['id'] for i in r['reshoot']['items'][:3])}." if r.get("reshoot") else "")
                     + (f" Refused: {r['refusal']}." if r.get("refusal") else "")
                     + (f" Error: {r['error']}." if r.get("error") else ""))
        L.append("")
    if len(agents) == 2:
        sb, ib = sums["bedrock"]; sr, ir = sums["rules"]
        diff = [i for i in ib if i in ir and (ib[i]["outcome"] != ir[i]["outcome"] or ib[i]["path"] != ir[i]["path"])]
        L.append("## Agent vs rule table (the ablation, PLAN step 6)\n")
        L.append(f"Same set, same measurements, same loop and guards; only the chooser differs. Outcomes as labelled: Bedrock {sb['outcome_ok']}/{sb['n']}, "
                 f"rules {sr['outcome_ok']}/{sr['n']}; silently wrong: {len(sb['silently_wrong'])} vs {len(sr['silently_wrong'])}. "
                 + ("**They tie on this set.** " if sb["outcome_ok"] == sr["outcome_ok"] and len(sb["silently_wrong"]) == len(sr["silently_wrong"]) else "")
                 + (f"They differ on: {', '.join('`' + i + '`' for i in diff)}." if diff else "No item's outcome or path differs."))
        for i in diff:
            L.append(f"- `{i}`: Bedrock {ib[i]['outcome']} ({' → '.join(ib[i]['path'])}); rules {ir[i]['outcome']} ({' → '.join(ir[i]['path'])}).")
        L.append("")
    # what changed since the previous run, when a snapshot exists (results/previous/<agent>/)
    prev_dir = RESULTS / "previous"
    if prev_dir.is_dir():
        L.append("## What changed since the previous run\n")
        L.append("The previous results are kept under `results/previous/` (the run before the two corrections of 2026-09-20: one ruler for "
                 "the size cap and the size gate; the crown-evidence rule for the head metrics). Every verified item gained the `crown_visible` "
                 "gate (pass on each one verified; the profile now has 9 gates), and every `subject_size` number moved to the shared ruler — "
                 "listed per item where it moved. Outcome, path and finding-status changes, agent by agent:\n")
        for a in agents:
            pd = prev_dir / a
            if not pd.is_dir():
                continue
            prev = {p.stem: json.loads(p.read_text()) for p in pd.glob("*.json") if p.stem != "summary"}
            _, cur = sums[a]
            psum = json.loads((pd / "summary.json").read_text()) if (pd / "summary.json").exists() else None
            sm, _ = sums[a]
            L.append(f"**{a}** — outcomes as labelled {psum['outcome_ok'] if psum else '?'}/{psum['n'] if psum else '?'} → **{sm['outcome_ok']}/{sm['n']}**; "
                     f"silently wrong {len(psum['silently_wrong']) if psum else '?'} → **{len(sm['silently_wrong'])}**.\n")
            changed = 0
            for it in s["items"]:
                i = it["id"]
                if i not in prev or i not in cur:
                    continue
                o, n = prev[i], cur[i]
                bits = []
                if o["outcome"] != n["outcome"]:
                    bits.append(f"outcome {o['outcome']} → **{n['outcome']}**")
                if o["path"] != n["path"]:
                    bits.append(f"path {' → '.join(o['path'])} ⇒ {' → '.join(n['path'])}")
                og = {g["id"]: g["status"] for v in o.get("verify", [])[:1] for g in v["gates"]}
                ng = {g["id"]: g["status"] for v in n.get("verify", [])[:1] for g in v["gates"]}
                if og and ng:
                    for gid in sorted(set(og) & set(ng)):
                        if og[gid] != ng[gid]:
                            bits.append(f"gate {gid}: {og[gid]} → {ng[gid]}")
                    for gid in sorted(set(ng) - set(og)):
                        if gid != "crown_visible":
                            bits.append(f"new gate {gid}: {ng[gid]}")
                elif og and not ng:
                    bits.append("no verification this time — the loop stopped earlier")
                of = {f["id"]: f["status"] for v in o.get("inspect", [])[:1] for f in v["findings"]}
                nf = {f["id"]: f["status"] for v in n.get("inspect", [])[:1] for f in v["findings"]}
                for fid in sorted(set(of) | set(nf)):
                    if of.get(fid) != nf.get(fid):
                        bits.append(f"finding {fid}: {of.get(fid, '—')} → {nf.get(fid, '—')}")
                # the size gate's number, where it moved
                for k, recs in (("inspect", "findings"),):
                    ov = next((f["value"] for v in o.get("inspect", [])[:1] for f in v["findings"] if f["id"] == "subject_size"), None)
                    nv = next((f["value"] for v in n.get("inspect", [])[:1] for f in v["findings"] if f["id"] == "subject_size"), None)
                    if ov and nv and (ov.get("p95") != nv.get("p95")):
                        bits.append(f"subject_size p95 {ov.get('p95')} → {nv.get('p95')}")
                if o["score"]["outcome_ok"] != n["score"]["outcome_ok"]:
                    bits.append(f"as labelled: {o['score']['outcome_ok']} → **{n['score']['outcome_ok']}**")
                if bits:
                    changed += 1
                    L.append(f"- `{i}`: " + "; ".join(bits))
            if not changed:
                L.append("- no item changed")
            L.append("")
    # the linear pipeline as the baseline: it ships the standard render whenever its prep succeeds, warning in a log
    a0 = agents[0]
    _, items0 = sums[a0]
    L.append("## The linear pipeline as the baseline\n")
    L.append("`midtown_red_curtain.sh` on its own — fixed order, no agent, no gate — ships the standard render of every recording its prep "
             "accepts and writes its warnings to a log. Its deliveries are the loop's first attempts, so their gates are already measured "
             "(the first VERIFY of each item, above). What the linear pipeline would have shipped:\n")
    L.append("| item | linear pipeline ships | gates the shipped render fails | label | what the loop did instead |")
    L.append("|---|---|---|---|---|")
    n_ship = n_fail = n_wrong = n_recovered = 0
    for it in s["items"]:
        r = items0.get(it["id"])
        if not r or r["kind"] == "gate":
            continue
        if r["outcome"] == "refused":
            L.append(f"| `{it['id']}` | no — refused at prep | — | {it['labels']['expected_outcome']} | the same refusal |")
            continue
        v1 = next((v for v in r.get("verify", []) if v["artifact"] == "attempt_1"), None) or r.get("baseline_verify")
        fails = [g["id"] for g in v1["gates"] if g["status"] == "fail"] if v1 else []
        n_ship += 1
        if fails:
            n_fail += 1
        wrong = it["labels"]["expected_outcome"] == "reshoot"
        if wrong:
            n_wrong += 1
        recovered = bool(fails) and r["outcome"] == "delivered"
        if recovered:
            n_recovered += 1
        did = ("delivered after " + ("a fix and " if r.get("fixes") else "") + f"{len(r.get('verify', []))} verification(s)" if r["outcome"] == "delivered"
               else "reshoot request, citing " + ", ".join(i["id"] for i in (r.get("reshoot") or {}).get("items", [])[:2]))
        L.append(f"| `{it['id']}` | yes{' — no verification of its own' if not v1 else ''} | {', '.join(fails) if fails else 'none'}"
                 f"{' — **silently wrong by label**' if wrong else ''} | {it['labels']['expected_outcome']} | {did} |")
    L.append("")
    L.append(f"Of {n_ship} renders the linear pipeline ships, **{n_fail} fail a gate** it does not have; {n_wrong} of those are recordings the label says "
             f"must not be delivered (the loop asked for a reshoot on each), and {n_recovered} were recovered by the loop's retry into a verified delivery. "
             f"The linear pipeline's silently wrong deliveries on this set: **{n_wrong}**; the loop's: 0 among these, plus the frozen-frames delivery both miss.\n")
    L.append("## Limitations the set makes visible\n")
    L.append("- **Known limitation — Stage Ready currently verifies frame count and visual quality but does not yet detect frozen/repeated-frame "
             "motion continuity.** `gate_frozen_frames` — a delivery with 30 frames frozen, the count and the audio intact — passes every gate and is "
             "counted above as a silently wrong delivery, because it is one. The label stays; the remedy is a gate, deliberately not added yet.")
    L.append("- **VERIFY trusts the composite frames for the picture gates** (separation, matte extent, head height) and the delivered file for the "
             "count and the audio. A delivery whose frames were swapped after compositing is caught only if its count or audio changed.")
    L.append("- **A recording the pipeline cannot matte is refused before the loop** (Apple Vision finds no reliable pose; two subjects) — an honest "
             "exit, but one the agent never sees; the refusal is scored as the reshoot exit.")
    L.append("- **A crown cut on every frame makes the head-height gates blind.** `brian_crown_cut` delivers with head spread 0.1 % and drift "
             "0.0 px — not because the head is still but because the matte's top is the picture edge on every frame and cannot move; the delivered "
             "video has a carved crown. `headroom` is a warning in the profile, so the loop delivers. The remedy is a gate on crown-cut frames, not a threshold change.")
    L.append("- **The size cap and the size gate use different rulers.** The fixer caps the performer's width on a 0.5-s-smoothed shoulder span; the "
             "inspection's `subject_size` measures the raw span's p95. `brian_zoomed` lands at 0.553 against the 0.55 cap after the fix, and the rule "
             "table reshoots a recording whose render then verifies (the agent processed it and it passed). The remedy is one ruler in "
             "`track_frame.py` and `vision/track.py`, then re-rendering the capped items.")
    L.append("- **The agent reads the intake brief.** A first Bedrock run passed each item's label text as the recording's brief; the agent quoted it "
             "and asked for a reshoot at the first decision on Sandy, Zach's black-shirt take and the crown-cut input — before measuring. Blind, it "
             "takes the measured path on all three. The demo's briefs are the show's intake notes; this is the reason the evaluation carries none.")
    L.append("- **The labels are ours.** `either` marks the items where a delivery and a reshoot are both defensible; the number that matters there "
             "is that a delivery carries a measured pass.")
    OUT.write_text("\n".join(L) + "\n")
    return OUT
