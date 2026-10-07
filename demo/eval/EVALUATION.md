# Evaluation — Stage Ready against a labelled set

Generated 2026-09-20 by `python3 -m stage_ready evaluate --report` from `demo/eval/set.json` and `demo/eval/results/`. Every item was labelled before it ran (`labels.why` says how); the loop ran as it runs live — INSPECT / FIX / VERIFY measured with OpenCV 5 on this machine, PROCESS the archived render — with the agent on Amazon Bedrock (Claude Sonnet 4.6, the product) and, as the ablation, replaced by the rule table in `stage_ready/rules_agent.py`. The agent runs **blind**: the prompt carries no name, brief or file name for an evaluation input — only the measurements — which is stricter than the demo, whose briefs are the show's intake notes.

## The number the product exists to make zero

| agent | items | outcomes as labelled | **silently wrong deliveries** | labelled defects missed | flags no label explains |
|---|---|---|---|---|---|
| bedrock | 19 (16 through the loop, 3 deliveries verified alone) | 17/19 | **1** gate_frozen_frames | 1 {"sta_30s": ["walk_in"]} | 4 |
| rules | 19 (16 through the loop, 3 deliveries verified alone) | 17/19 | **1** gate_frozen_frames | 1 {"sta_30s": ["walk_in"]} | 4 |

A *silently wrong delivery* is a delivery the label says should not have happened, or a defective delivery every gate passed. A *flag no label explains* is a finding INSPECT raised (fail or warn) or a gate the first VERIFY failed that the item's labels did not predict — each is listed under the item and judged there; some are labels that were incomplete, not measurements that were wrong.

## Every item

| item | kind | labelled defects | expected | bedrock: outcome · path · delivered numbers | rules: outcome · path · delivered numbers |
|---|---|---|---|---|---|
| `brian` — Brian Shirley — untouched | real | under_lit | deliver | ✓ **delivered** · inspect → process → verify ✓ → deliver · sep 2.91× head 0.7% drift 1.2 px | ✓ **delivered** · inspect → process → verify ✓ → deliver · sep 2.91× head 0.7% drift 1.2 px |
| `ethel` — Ethel Chadwick — untouched | real | wardrobe_near_plate | deliver | ✓ **delivered** · inspect → process → verify ✗ → reprocess → verify ✓ → deliver · sep 1.52× head 1.3% drift 3.1 px | ✓ **delivered** · inspect → process → verify ✗ → reprocess → verify ✓ → deliver · sep 1.52× head 1.3% drift 3.1 px |
| `joel` — Joel Pelletier — untouched | real | — | deliver | ✓ **delivered** · inspect → process → verify ✓ → deliver · sep 2.98× head 0.9% drift 2.3 px | ✓ **delivered** · inspect → process → verify ✓ → deliver · sep 2.98× head 0.9% drift 2.3 px |
| `sandy` — Sandy Hackett — untouched | real | pillarbox, too_close, walk_in, crown_cut, head_moves | reshoot | ✓ **reshoot** · inspect → reshoot · cites headroom*, distance_steady*, picture_area* | ✓ **reshoot** · inspect → fix → inspect → reshoot · cites headroom* |
| `zach_v2` — Zach Sain — black-shirt take, untouched | real | wardrobe_near_plate, crown_cut, over_lit | reshoot | ✓ **reshoot** · inspect → reshoot · cites headroom* | ✓ **reshoot** · inspect → reshoot · cites headroom* |
| `zach` — Zach Sain — the demo excerpt (derived) | derived | crown_cut, over_lit | deliver | ✓ **delivered** · inspect → process → verify ✓ → deliver · sep 2.37× head 0.7% drift 1.9 px | ✓ **delivered** · inspect → process → verify ✓ → deliver · sep 2.37× head 0.7% drift 1.9 px |
| `michi` — Michi — club sample (derived) | derived | — | either | ✓ **delivered** · inspect → process → verify ✓ → deliver · sep 1.51× head 1.2% drift 1.6 px · unlabelled: face_exposure | ✓ **delivered** · inspect → process → verify ✓ → deliver · sep 1.51× head 1.2% drift 1.6 px · unlabelled: face_exposure |
| `tehila_45s` — Tehila — seated, striped dress (derived: first 45 s) | derived | — | deliver | ✗ **refused** · prepare ✗ · pose QC failed (above) — the framing anchor would be on the wrong subject for part of this clip | ✗ **refused** · prepare ✗ · pose QC failed (above) — the framing anchor would be on the wrong subject for part of this clip |
| `sta_30s` — sta — walks in, black top on grey | real | walk_in, wardrobe_near_plate | either | ✓ **delivered** · inspect → fix → inspect → process → verify ✗ → reprocess → verify ✓ → deliver · sep 1.83× head 1.4% drift 2.3 px · missed: walk_in · unlabelled: face_exposure, picture_area, subject_size | ✓ **delivered** · inspect → fix → inspect → process → verify ✗ → reprocess → verify ✓ → deliver · sep 1.83× head 1.4% drift 2.3 px · missed: walk_in · unlabelled: face_exposure, picture_area, subject_size |
| `abby_9s` — Abby — close-up, 9 s | real | too_close, crown_cut | either | ✓ **refused** · prepare ✗ · pose found on only 0% of frames — the performer is not reliably visible in this recording. See RECORDING_REQUIREMENTS.md. | ✓ **refused** · prepare ✗ · pose found on only 0% of frames — the performer is not reliably visible in this recording. See RECORDING_REQUIREMENTS.md. |
| `two_sumitas` — Two Sumitas — two subjects (a composite) | real | two_subjects | reshoot | ✓ **refused** · prepare ✗ · pose QC failed (above) — the framing anchor would be on the wrong subject for part of this clip | ✓ **refused** · prepare ✗ · pose QC failed (above) — the framing anchor would be on the wrong subject for part of this clip |
| `brian_padded` — Brian — padded (synthesised: pillarbox) | synthesised | pillarbox, under_lit | deliver | ✓ **delivered** · inspect → fix → inspect → process → verify ✓ → deliver · sep 2.90× head 0.7% drift 1.2 px | ✓ **delivered** · inspect → fix → inspect → process → verify ✓ → deliver · sep 2.90× head 0.7% drift 1.2 px |
| `zach_padded` — Zach — padded (synthesised: pillarbox) | synthesised | pillarbox, crown_cut, over_lit | deliver | ✓ **delivered** · inspect → fix → inspect → process → verify ✓ → deliver · sep 2.36× head 0.7% drift 1.9 px | ✓ **delivered** · inspect → fix → inspect → process → verify ✓ → deliver · sep 2.36× head 0.7% drift 1.9 px |
| `brian_zoomed` — Brian — too close (synthesised: cropped to head and chest) | synthesised | too_close, under_lit | deliver | ✓ **delivered** · inspect → fix → inspect → process → verify ✓ → deliver · sep 3.38× head 1.1% drift 1.9 px | ✓ **delivered** · inspect → fix → inspect → process → verify ✓ → deliver · sep 3.38× head 1.1% drift 1.9 px |
| `brian_crown_cut` — Brian — crown cut (synthesised: top 120 rows removed) | synthesised | crown_cut, under_lit | either | ✓ **reshoot** · inspect → reshoot · cites headroom* | ✓ **reshoot** · inspect → reshoot · cites headroom* |
| `brian_underlit` — Brian — dark room (synthesised: gain ×0.35) | synthesised | under_lit, wardrobe_near_plate | either | ✓ **delivered** · inspect → process → verify ✗ → reprocess → verify ✓ → deliver · sep 1.52× head 0.7% drift 1.2 px | ✓ **delivered** · inspect → process → verify ✗ → reprocess → verify ✓ → deliver · sep 1.52× head 0.7% drift 1.2 px |
| `gate_frame_drop` — Delivery with one frame dropped | gate | frames_dropped | reject | ✓ **rejected** · verify ✗ | ✓ **rejected** · verify ✗ |
| `gate_audio_reencoded` — Delivery with re-encoded audio | gate | audio_reencoded | reject | ✓ **rejected** · verify ✗ | ✓ **rejected** · verify ✗ |
| `gate_frozen_frames` — Delivery with 30 frozen frames | gate | frames_frozen | reject | ✗ **delivered** — **SILENTLY WRONG** · verify ✓ | ✗ **delivered** — **SILENTLY WRONG** · verify ✓ |

## Per finding and gate, against the labels

Positives are the items labelled with the defect the finding measures (`defect_map` in set.json); a detection is the finding raised as fail or warn on the source inspection, or the gate failed on the first verification.

**bedrock**

| finding / gate | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|
| audio_md5 | 1 | 0 | 0 | 1.0 | 1.0 |
| distance_steady | 1 | 0 | 1 | 1.0 | 0.5 |
| face_exposure | 8 | 2 | 0 | 0.8 | 1.0 |
| frame_count | 1 | 0 | 0 | 1.0 | 1.0 |
| headroom | 5 | 0 | 0 | 1.0 | 1.0 |
| one_subject | 1 | 0 | 0 | 1.0 | 1.0 |
| picture_area | 3 | 1 | 0 | 0.75 | 1.0 |
| separation | 3 | 0 | 0 | 1.0 | 1.0 |
| subject_size | 2 | 1 | 0 | 0.67 | 1.0 |

**rules**

| finding / gate | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|
| audio_md5 | 1 | 0 | 0 | 1.0 | 1.0 |
| distance_steady | 1 | 0 | 1 | 1.0 | 0.5 |
| face_exposure | 8 | 2 | 0 | 0.8 | 1.0 |
| frame_count | 1 | 0 | 0 | 1.0 | 1.0 |
| headroom | 5 | 0 | 0 | 1.0 | 1.0 |
| one_subject | 1 | 0 | 0 | 1.0 | 1.0 |
| picture_area | 3 | 1 | 0 | 0.75 | 1.0 |
| separation | 3 | 0 | 0 | 1.0 | 1.0 |
| subject_size | 2 | 1 | 0 | 0.67 | 1.0 |

## Where the loop was wrong, and what it cost

**bedrock** — 2 outcome(s) not as labelled; 1 silently wrong; Bedrock 30 calls, 138,740 in / 12,225 out tokens, 179 s of model latency; wall time 12 min for the set (measurement, not rendering — the renders are cached by source hash).

- `tehila_45s`: expected **deliver**, got **reshoot** — seated at one distance, crown inside, a black-and-white striped dress on a beige wall; nothing visibly wrong. Refused: pose QC failed (above) — the framing anchor would be on the wrong subject for part of this clip.
- `gate_frozen_frames`: expected **reject**, got **deliver** — Brian's delivery with frames 600–629 replaced by frame 600 — the count and the audio are intact; no gate measures motion continuity, so this is expected to pass every gate: a known limitation, counted as a silently wrong delivery if it does.

**rules** — 2 outcome(s) not as labelled; 1 silently wrong; no model calls; wall time 10 min for the set (measurement, not rendering — the renders are cached by source hash).

- `tehila_45s`: expected **deliver**, got **reshoot** — seated at one distance, crown inside, a black-and-white striped dress on a beige wall; nothing visibly wrong. Refused: pose QC failed (above) — the framing anchor would be on the wrong subject for part of this clip.
- `gate_frozen_frames`: expected **reject**, got **deliver** — Brian's delivery with frames 600–629 replaced by frame 600 — the count and the audio are intact; no gate measures motion continuity, so this is expected to pass every gate: a known limitation, counted as a silently wrong delivery if it does.

## Agent vs rule table (ablation)

Same set, same measurements, same loop and guards; only the chooser differs. Outcomes as labelled: Bedrock 17/19, rules 17/19; silently wrong: 1 vs 1. **They tie on this set.** They differ on: `sandy`.
- `sandy`: Bedrock reshoot (inspect → reshoot); rules reshoot (inspect → fix → inspect → reshoot).

## The linear pipeline as the baseline

`midtown_red_curtain.sh` on its own — fixed order, no agent, no gate — ships the standard render of every recording its prep accepts and writes its warnings to a log. Its deliveries are the loop's first attempts, so their gates are already measured (the first VERIFY of each item, above). What the linear pipeline would have shipped:

| item | linear pipeline ships | gates the shipped render fails | label | what the loop did instead |
|---|---|---|---|---|
| `brian` | yes | none | deliver | delivered after 1 verification(s) |
| `ethel` | yes | separation | deliver | delivered after 2 verification(s) |
| `joel` | yes | none | deliver | delivered after 1 verification(s) |
| `sandy` | yes | crown_visible, head_spread, head_drift — **silently wrong by label** | reshoot | reshoot request, citing headroom, distance_steady |
| `zach_v2` | yes | crown_visible, separation — **silently wrong by label** | reshoot | reshoot request, citing headroom |
| `zach` | yes | none | deliver | delivered after 1 verification(s) |
| `michi` | yes | none | either | delivered after 1 verification(s) |
| `tehila_45s` | no — refused at prep | — | deliver | the same refusal |
| `sta_30s` | yes | separation | either | delivered after a fix and 2 verification(s) |
| `abby_9s` | no — refused at prep | — | either | the same refusal |
| `two_sumitas` | no — refused at prep | — | reshoot | the same refusal |
| `brian_padded` | yes | none | deliver | delivered after a fix and 1 verification(s) |
| `zach_padded` | yes | none | deliver | delivered after a fix and 1 verification(s) |
| `brian_zoomed` | yes | none | deliver | delivered after a fix and 1 verification(s) |
| `brian_crown_cut` | yes | crown_visible | either | reshoot request, citing headroom |
| `brian_underlit` | yes | separation | either | delivered after 2 verification(s) |

Of 13 renders the linear pipeline ships, **6 fail a gate** it does not have; 2 of those are recordings the label says must not be delivered (the loop asked for a reshoot on each), and 3 were recovered by the loop's retry into a verified delivery. The linear pipeline's silently wrong deliveries on this set: **2**; the loop's: 0 among these, plus the frozen-frames delivery both miss.

## Limitations the set makes visible

- **Known limitation — Stage Ready currently verifies frame count and visual quality but does not yet detect frozen/repeated-frame motion continuity.** `gate_frozen_frames` — a delivery with 30 frames frozen, the count and the audio intact — passes every gate and is counted above as a silently wrong delivery, because it is one. The label stays; the remedy is a gate, deliberately not added yet.
- **VERIFY trusts the composite frames for the picture gates** (separation, matte extent, head height) and the delivered file for the count and the audio. A delivery whose frames were swapped after compositing is caught only if its count or audio changed.
- **A recording the pipeline cannot matte is refused before the loop** (Apple Vision finds no reliable pose; two subjects) — an honest exit, but one the agent never sees; the refusal is scored as the reshoot exit.
- **A crown cut on every frame makes the head-height gates blind.** `brian_crown_cut` delivers with head spread 0.1 % and drift 0.0 px — not because the head is still but because the matte's top is the picture edge on every frame and cannot move; the delivered video has a carved crown. `headroom` is a warning in the profile, so the loop delivers. The remedy is a gate on crown-cut frames, not a threshold change.
- **The size cap and the size gate use different rulers.** The fixer caps the performer's width on a 0.5-s-smoothed shoulder span; the inspection's `subject_size` measures the raw span's p95. `brian_zoomed` lands at 0.553 against the 0.55 cap after the fix, and the rule table reshoots a recording whose render then verifies (the agent processed it and it passed). The remedy is one ruler in `track_frame.py` and `vision/track.py`, then re-rendering the capped items.
- **The agent reads the intake brief.** A first Bedrock run passed each item's label text as the recording's brief; the agent quoted it and asked for a reshoot at the first decision on Sandy, Zach's black-shirt take and the crown-cut input — before measuring. Blind, it takes the measured path on all three. The demo's briefs are the show's intake notes; this is the reason the evaluation carries none.
- **The labels are ours.** `either` marks the items where a delivery and a reshoot are both defensible; the number that matters there is that a delivery carries a measured pass.
