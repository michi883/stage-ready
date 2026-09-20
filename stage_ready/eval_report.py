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
    s = load_set()
    agents = [a for a in ("bedrock", "rules") if (RESULTS / a / "summary.json").exists()]
    sums = {a: _load(a) for a in agents}
    L = []
    L.append("# Evaluation — Stage Ready against a labelled set\n")
    L.append(f"Generated {datetime.date.today().isoformat()} by `python3 -m stage_ready evaluate --report` from `demo/eval/set.json` and "
             f"`demo/eval/results/`. Every item was labelled before it ran (`labels.why` says how); the loop ran as it runs live — "
             f"INSPECT / FIX / VERIFY measured with OpenCV 5 on this machine, PROCESS the archived render — with the agent on Amazon Bedrock "
             f"(Claude Sonnet 4.6, the product) and, as the ablation, replaced by the rule table in `stage_ready/rules_agent.py`.\n")
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
            L.append(f"- `{r['id']}`: expected **{sc['expected']}**, got **{sc['got']}** — {r['labels']['why']}"
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
    L.append("## Limitations the set makes visible\n")
    L.append("- **No gate measures motion continuity.** `gate_frozen_frames` — a delivery with 30 frames frozen, the count and the audio intact — "
             "is expected to pass every gate; if it does, it is counted above as a silently wrong delivery, because it is one. The fix is a gate, not a label.")
    L.append("- **VERIFY trusts the composite frames for the picture gates** (separation, matte extent, head height) and the delivered file for the "
             "count and the audio. A delivery whose frames were swapped after compositing is caught only if its count or audio changed.")
    L.append("- **A recording the pipeline cannot matte is refused before the loop** (Apple Vision finds no reliable pose; two subjects) — an honest "
             "exit, but one the agent never sees; the refusal is scored as the reshoot exit.")
    L.append("- **The labels are ours.** `either` marks the items where a delivery and a reshoot are both defensible; the number that matters there "
             "is that a delivery carries a measured pass.")
    OUT.write_text("\n".join(L) + "\n")
    return OUT
