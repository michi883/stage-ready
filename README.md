# Stage Ready

**Drop a self-recorded video. Get back a verified, stage-ready delivery — or a specific reshoot
request. Never anything in between.**

Stage Ready is an agentic video-quality loop: **OpenCV does the seeing, an agent does the
deciding** — what to look at next, what to try, whether it worked, and when to stop and ask for a
reshoot instead. It measures a raw recording against a *Target Output Profile*, chooses what to
fix, what to process and what to try next, and refuses to deliver anything it has not measured as
correct. Built for the Agentic Vision hackathon on a production pipeline that already puts real
performers on a real stage: the [Midtown Show](https://midtownshow.com/2040) Red Curtain.

> *Different inputs. One output standard.*

What is built today, in one line: measurement and verification with OpenCV 5 on AWS Lambda, the
agent on Amazon Bedrock, the loop's guarantees in code, a public endpoint, a labelled evaluation —
on the recordings the Red Curtain archive holds. A brand-new upload is recognised or told it is
unknown; producing its matte and render is the one milestone still open ([What is real today](#what-is-real-today-and-what-is-not)).

## The problem

Shows, courses and brands run on video that other people record: phones, bedrooms, kitchens,
whatever the performer wore that day. Every submission is inconsistent, and a fixed pipeline
handles that the only way it can — run every step in order and hope. The dangerous failure is not
the crash; it is the **silently wrong delivery**: a clip that passes every count-and-coverage check
and is still unusable. The Red Curtain pipeline met exactly that clip — a performer in a red suit,
composited onto a red curtain. In colour it looked fine. In luminance, the medium a thumbnail, a
heavy re-encode or a colour-blind viewer actually sees, the jacket and the curtain were one shape:
separation **1.13×** against a 1.5× floor. Nothing upstream could have seen it (the pre-composite
predictor scores a known-good clip almost the same); only measuring the *finished* output did. A
pipeline logs that as a warning. A human reviewer, judging by eye, misses it — the eye is the wrong
instrument for the one thing that check measures.

## The goal

Take a raw self-recorded clip and a Target Output Profile, and return one of two things, never
anything in between:

- **a delivered video** — measured, corrected where correction is honest, and verified against the
  profile; or
- **a reshoot request** — naming the defect, the number behind it, and what to change at capture.

Evidence comes from measurement, not assumption.

## The Target Output Profile

A profile is data, not code. It says what "delivered" means for one destination, and every decision
the agent makes is made against it.

| field | Midtown Show · Red Curtain — the first profile |
|---|---|
| Canvas and encode | 1080 × 1920, H.264 CRF 20, source audio copied |
| Background | one fixed still: the red-curtain plate |
| Framing rule | head on the upper third (`head_target` 0.334, a floor), body centred, size held; shoulder span capped at 55 % of canvas width |
| Look | the Red Curtain grade — light wrap, rim, measured face exposure |
| Verification gates (9) | pose on ≥ 60 % of frames; one subject on ≥ 95 %; a recorded crown on ≥ 50 % of frames (the evidence the head metrics need); segmentation extent ≥ 90 % of an independent opinion; subject-vs-background luminance separation ≥ 1.5×; head-height spread and drift in tolerance; frame count and audio MD5 equal to the source |
| Allowed strategies (3) | crop + size-capped reframe (a fix) · standard composite · separation-targeted composite — in cost order, each with its bounds, and a retry budget of 2 |
| Reshoot guidance | the capture rule behind each gate, from the show's `RECORDING_REQUIREMENTS.md` |

A second profile — another show's plate, a 16:9 talking head, a clean-up-only delivery — would
change this table and nothing in the loop; that is the design, and it is untested: only this
profile exists today (PLAN step 7). Thresholds inform the agent; they do not replace it.

## The loop

```
raw recording + Target Output Profile
          │
          ▼
   INSPECT (OpenCV) ──▶ findings, each with its number, threshold, confidence and tool
          │
          ▼
   DECIDE (agent) ──▶ inspect further · fix · process · deliver · stop
          │                              │
          ├── fix: one-sided, bounded ◀──┘   … then re-inspected; rejected if it created a new defect
          ▼
   PROCESS toward the profile      ◀── a different strategy
          │                                   ▲
          ▼                                   │
   VERIFY (OpenCV, against the profile's gates, on the finished output)
          │                                   │
     pass ├── DELIVERED, with its numbers     │
     fail └───────────────────────────────────┘   … until the retry budget is spent:
                                                   RESHOOT REQUEST — the defect, the number,
                                                   the capture change
```

The agent chooses; the loop enforces what the agent may not skip (`stage_ready/loop.py`):

- every **process** is followed by **verify** against the profile's gates, by measurement;
- every **fix** is re-inspected, and rejected if it created a new failing finding;
- **deliver** is refused unless the latest verification passed;
- a strategy must be one the profile allows; the **retry budget** bounds reprocessing;
- when the budget is spent, the exit is a **reshoot request**: the defect, the number, the capture
  change — *"Don't wear the stage. The curtain is deep red: no red, maroon, burgundy or hot pink."*

Every decision is traceable to the findings that prompted it, the action taken, and the measurement
that followed.

## Why it is different

- **Verification changes behaviour.** A failed gate on the finished output is not a log line; it is
  the input to the agent's next decision. The red-suit recording fails, the agent switches to a
  separation-targeted strategy that reuses the matte and the tracking and changes only the edge,
  and the second attempt clears the gate. That is the loop, visibly, in the demo.
- **Measured, never assumed.** Every finding, decision and gate carries a number, a threshold and
  the tool that produced it. The agent's reasoning cites the findings that drove it. Trace shows all
  of it; the default screen shows one phrase per step.
- **Honest by construction.** Fixes are one-sided (crop to the measured picture, size-capped
  reframe — a performer can only get smaller, never invented larger). No generative model touches
  the performer: face, expression, lip sync, gestures, clothing, timing and audio are the recorded
  pixels throughout. Frame count and audio MD5 are gates. Missing pixels stay missing.
- **The other exit is a feature.** When correction would not be honest, the product says so —
  which defect, which number, and what to change at capture — instead of shipping a worse video.
- **No per-recording settings.** Three recordings that could not be more different go through the
  same loop with the same profile and come out the same size, the same head height, the same look,
  each with its number.
- **General-purpose by design — one profile so far.** The profile is the product surface; the
  loop is the engine; nothing in the loop or the agent names the Red Curtain. A second destination
  would be a second JSON file, and none has been written yet (PLAN step 7).
- **Real, not synthetic.** The thresholds, techniques and every measurement in the demo come from a
  production pipeline (`~/mts`) that has delivered five real performer recordings to the Midtown
  Show stage — including the failures that taught it.

### What "done" means

- **No silently wrong deliveries.** Every recording ends as a verified delivery or a reshoot request.
- **Every fix is verified** against the profile; one that creates a new defect is rejected.
- **Verification changes behaviour.** Ethel's trace shows a failed gate followed by a different action.
- **Consistent by measurement, not by eye.** The outputs agree on head height, apparent size and
  separation within the profile's tolerances.
- **Reshoot guidance is specific and actionable** — the defect, the number, the capture change.
- **Reproducible, bounded, traceable** — same recording and profile, same result; retries capped;
  every decision replayable from the findings that drove it.
- **Honest by construction** — a fixer may reframe or regrade recorded content (the two that exist:
  the crop-and-size-cap reframe, the separation-targeted grade); it never invents content that was
  not captured.
- **No per-recording tuning** — the samples run with the profile alone.
- **General-purpose** — a second profile would change the data, not the loop (not yet demonstrated).

## See it in two minutes

**Public endpoint: <https://d4nh99blf9f5j.cloudfront.net/>** — no sign-in, the cached demo by
default (every run replayed from the measured fixtures, instantly; the badge in the header says
*demo · cached*). `?demo=0` on the same URL is the live AWS hybrid: OpenCV 5 on Lambda, the agent
on Bedrock, 4–6 minutes per recording, streamed as it happens. Or locally:

```bash
python3 -m stage_ready serve            # standard library only, no installs
open "http://127.0.0.1:8765/"           # the demo; ?demo=0 is live (needs AWS access)
```

A workspace, one recording at a time:

1. **Drop a recording.** The Target Output Profile is preselected: *Midtown Show · Red Curtain*.
   The browser fingerprints the file (SHA-256 — the same key the live matte cache uses) and the
   server checks for a cached run. The file never leaves the machine. No file at hand? *or try one
   of the three sample cases.*
2. **Make Stage Ready.** The source plays large on the left; one flow runs underneath —
   `INSPECT → DECIDE → PROCESS → VERIFY` — one phrase per step, one sentence of narration in the
   agent's own words, and the output arriving on the right.
3. **Source and output, side by side**, playing from the same moment, with the path as chips —
   *Framing needs adjustment → Reframe → Verified ✓* — then **Add another recording** or
   **View processed recordings (n)**: every recording so far, source over output, from the first one
   on. It never opens by itself.

The three sample cases are three performers and three agent behaviours — each the path its input's
own measurements produce, through the same profile with no per-recording settings
(`demo/lineup.json`; see [Performers and numbers](#performers-and-numbers)). The picker names the
behaviour first and the performer second:

| | **Brian Shirley** — controlled repair: fix what is wrong, verify what comes out | **Ethel Chadwick** — adapt and recover | **Zach Sain** — already suitable, verified |
|---|---|---|---|
| What came in | his untouched recording, **padded on purpose**: the real 1920 × 1080 picture placed unscaled inside a 2560 × 1440 black canvas — the export a Full-HD clip gets when it is dropped on a QHD timeline. A *controlled demo input*: performer pixels and motion untouched ([derived](#polished-demo-vs-evaluation-corpus)) | recorded to spec — in a red trouser suit, for a red curtain (untouched) | a 60 s excerpt of his other take: a 480 × 404 picture, 30 fps; a black shirt on a red wall, mint trousers, one distance ([derived](#polished-demo-vs-evaluation-corpus)) |
| Inspect finds | **picture area smaller than the file** — 1920 × 1080 at +320+180 in 2560 × 1440; every other gate passes; one warning — under-lit (face ×1.55 wanted, held at ×1.25), the key from the right | nothing outside the profile (one low-confidence note: wardrobe close to the plate) | nothing outside the profile's gates; two warnings — the crown leaves the picture on 34 % of frames, and the room is over-lit (face ×0.36 wanted, clamped at ×0.80) |
| Agent decides | **fix**: crop to the measured picture (`1920:1080:320:180`), size-capped reframe — the head target stays at the floor, 0 pixels invented → re-inspect: **clean** → process | process | process |
| Verify | **pass** — separation **2.90×**, matte 100 %, head held to 0.7 %, drift 1.2 px, 1285 frames, audio identical | **fail** — separation 1.13× against 1.5×; every other gate passes | **pass** — separation **2.37×** (the trousers, the face and the hands carry the outline the shirt does not), matte 101 %, head held to 0.7 %, drift 1.9 px, 1800 frames, audio identical |
| Agent decides | deliver, with two capture notes: export without padding, a stop more light | **change strategy**: separation-targeted composite, matte and tracking reused → reprocess | deliver, with two capture notes: headroom for the crown, a stop less light |
| Verify | — | pass — 1.52×, with the grade at its bounds | — |
| Agent decides | — | deliver | — |
| On screen | Framing needs adjustment → Reframe → Verified ✓ | Already suitable → Standard process → **Fails ✗** ⟲ Try safer processing → Reprocess → Verified ✓ | Already suitable → Standard process → Verified ✓ |

The picker, the session view and the Details table stamp each recording with what the agent did,
by one rule (`verdict()` in `web/app.js`, over the run's own end event — for the picker, the cached
run's): **FIXED · VERIFIED** (a fix that held, re-inspected, then a verified render),
**ADAPTED · RECOVERED** (a failed gate, a changed strategy, a verified second attempt),
**VERIFIED · FIRST PASS** (every gate on the first pass, nothing changed). The red stamps —
**FIXED · CAUGHT**, **TRIED · STOPPED**, **STOPPED** — exist for the exit the loop refuses to skip;
Sandy's recording earns one ([`?clip=sandy`](https://d4nh99blf9f5j.cloudfront.net/?clip=sandy), below —
STOPPED at INSPECT since the crown-evidence rule), and `&budget=0` shows it on Ethel. Nothing is labelled a success that was not measured as one.

**Watch Brian's.** INSPECT reads the picture area off the file, not the container — 1920 × 1080
inside 2560 × 1440 — and fails it; the agent picks the one allowed fixer; the fix reports exactly
what it did (crop, head target unchanged, nothing invented); re-inspect passes; the render verifies
at 2.90×, the untouched recording's own number. The Details row *provenance* says what this
input is: *Controlled demo input derived from real performer footage by adding padding. Performer
pixels and motion were not altered.* The defect is injected on purpose so the repair path can be
shown on a recording that verifies — the natural version of this defect, Sandy's pillarboxed
export, ends in a reshoot for a reason no fixer can touch ([below](#polished-demo-vs-evaluation-corpus)).

**Watch Ethel's.** The Verify cell turns red, the first output is stamped ✗ and thrown behind, a
retry arc draws back to Decide, the agent explains why in one sentence and changes strategy, and
the second attempt earns the ✓ — by 0.02×, with every knob of the strategy at its bound. In the Red
Curtain script that failure was a warning in a log; in the profile it is a gate, and the gate
changed the agent's next action. Had the second strategy not cleared it inside those bounds, the
exit would have been the reshoot request — `&budget=0` shows that path for her.

**Zach's is the control**, and it earns that from a number: his other take, in the same black
shirt on the same red wall but with mint trousers, separates at 2.37× — the trousers, the face and
the hands carry the outline in luminance. The report still carries two notes, because the
measurements say so: the crown leaves the small picture on a third of frames (completed from his
own uncut frames), and the room is over-lit for the stage. The take he sent first — black trousers
too — is the recording that *cannot* clear the gate (1.00×, 1.45× at the retry's bounds), and it
stays in the evaluation corpus as exactly that.

**And Sandy's, by deep link** ([`?clip=sandy`](https://d4nh99blf9f5j.cloudfront.net/?clip=sandy)):
INSPECT fails three things — the padding, the close-up, and the crown, recorded on only 24 % of
frames. The first two the fixer addresses; the third nothing does, and without a recorded crown
the head-height verification would be measured against a completed crown or the picture edge, not
him. So the agent asks for a reshoot at its first decision, naming all three, with the profile's
guidance for each. (Before the crown-evidence rule of 2026-09-20 the loop fixed what it could and
the render then failed on head height, 2.9 % against 2 % — the number that exposed the problem;
those records stay in his fixtures.) Every attempt to make a Sandy input deliver failed honestly
and is on record ([below](#polished-demo-vs-evaluation-corpus)), which is why the repair card is Brian's.

**The payoff**, in the session view:

```
3 different inputs            ─▶  3 different agent behaviours     ─▶  3 verified deliveries — each with the number behind it,
   padded / red-on-red /            fix → verify  /  adapt → recover /       verified against every gate; the reshoot exit is measured
   small picture, black shirt        verified first pass                     on Sandy's recording (?clip=sandy), and &budget=0 shows it here
```

**Trace** (per recording) opens the full record — every finding, every decision with its reasoning
and citations, every stage with what it costs live, every gate — and, under Ethel's delivery, the
two attempts in luminance only with their two separation numbers. **Details** holds the delivered
numbers side by side and where each one comes from. Both stay closed until asked.

## What is real today, and what is not

Judges should know exactly what they are looking at:

- **The demo is fully cached and deterministic** — no model calls and no OpenCV measurement at demo time (the page and its replay are served by the API Lambda; nothing is measured or decided).
  Every measurement is replayed from `demo/clips/<id>/*.json`, and every fixture carries a
  `provenance` line naming the archived run and file it was measured from. A dropped file is
  recognised by fingerprint and its cached run replayed; an unknown file is told so, not guessed at.
- **The numbers are real, and each input's own.** Brian's, Ethel's and Zach's measurements are
  their own runs — Brian's on his untouched recording padded on purpose (and labelled so), Zach's
  on a curated excerpt of his other real take — their inspect, fix and verify fixtures written from
  the live OpenCV 5 measurement by `python3 -m stage_ready record <clip>`
  ([Polished demo vs evaluation corpus](#polished-demo-vs-evaluation-corpus)). No fixture borrows
  another clip's numbers; a test checks.
- **Every number is measured.** The last projected one — Ethel's second attempt — was measured on
  2026-09-19: the separation-targeted grade clears the gate at **1.52×**, and only with every knob
  at its bound. The earlier projection (1.58× at softer settings) measured 1.43× and was wrong; the
  fixture's `provenance` says so. Sandy's run is the archive's v4 render, and it fails — see
  [What is measured](#what-is-measured). A fixture that were projected would say so and the UI
  would tag it *projected*; none is, and a test keeps it that way.
- **INSPECT and VERIFY run live, with OpenCV 5, on AWS.** `stage_ready/vision/` ports the Red
  Curtain measurements (picture area, pose QC, the dry framing solve, crown, exposure and key,
  matte extent, separation, head spread and drift, frame count, audio MD5), and
  `python3 -m stage_ready measure` recomputes every fixture number from the archived files and
  prints the two side by side — the three clips agree ([What is measured](#what-is-measured)).
  `--live` / `?demo=0` is the **hybrid**: INSPECT and VERIFY on an AWS Lambda over the workdir
  mirrored from S3 by source hash, DECIDE on Amazon Bedrock, the rendering on the laptop and
  cached by source hash ([The live hybrid on AWS](#the-live-hybrid-on-aws)). All three sample
  cases have completed real runs (Ethel first, 2026-09-19; Brian's padded input and Zach on
  2026-09-20), and so have Sandy's recording and the padded Zach. The fixer runs on the Lambda too (the crop
  and the size-capped solve, deterministic OpenCV); producing a workdir for a fresh upload is
  milestone 9.
- **OpenCV 5 DNN segmentation is live for the seed and the matte's second opinion**, measured
  against the archive's Apple Vision opinions on all three clips (`segcheck`); not used for the
  separation edge, where it measured up to 0.14× off — see [Why OpenCV 5](#why-opencv-5).

## Evaluation

Three hand-picked recordings are not an evaluation, so the loop is scored against a labelled set —
`demo/eval/set.json`, 19 items, every one labelled *before* it ran: ten real recordings and derived
excerpts (Brian, Ethel, Joel, Sandy, both Zach takes, Michi, Tehila, sta, Abby, a two-performer
composite), four synthesised negatives with one known defect each (Brian's clean recording padded,
cropped to a close-up, its crown cut off, in a dark room — `demo/eval/derive_eval.sh`), and three
defective deliveries for the gates alone (a frame dropped, the audio re-encoded, 30 frames frozen).
`python3 -m stage_ready evaluate` runs each through the real loop — OpenCV 5 measurement here, the
archived render, the agent on Bedrock — and again with the agent replaced by a rule table
(`--agent rules`, the ablation); `--report` regenerates
[`demo/eval/EVALUATION.md`](demo/eval/EVALUATION.md), which is the record. The headline, 2026-09-20:

| | Stage Ready (agent on Bedrock, blind) | the same loop with a rule table | the linear pipeline alone |
|---|---|---|---|
| outcomes as labelled | **17 / 19** | 17 / 19 | — |
| silently wrong deliveries | **1** — the frozen-frames delivery, the stated limitation | 1 — the same | **2 + 1** — Sandy's and Zach's black-shirt renders shipped with failing gates, plus the same frozen frames |
| renders it would ship that fail a gate | 0 | 0 | 6 of 13 (the loop caught all six: 3 reshoot requests, 3 recovered by the retry) |
| labelled defects missed by a finding | 1 (a short walk-in at 1.33× against the 1.35× threshold) | the same | — |
| cost of the set | 30 Bedrock calls, 139k in / 12k out tokens, ≈ $0.60; 12 min of measurement | 0 calls; 10 min | — |

Every defective delivery with a wrong frame count or re-encoded audio was rejected. The agent and the rule table reach the same
outcome on every item and differ on one path: Sandy's — the agent stops at its first decision (no fixer addresses the crown
evidence), the rule table fixes what it can and then stops. These are the numbers after the two corrections of 2026-09-20 below;
the run before them is kept under `demo/eval/results/previous/` and the report lists exactly what changed: Sandy and Zach's
black-shirt take now stop at INSPECT on the crown-evidence rule instead of after a render; the synthetic crown-cut input is a reshoot
instead of a delivery; the close-up the size cap had left 0.3 % over the gate now re-inspects at the cap and delivers under both agents.

What the set found, beyond the numbers:

- **Two labels were wrong, and the measurement was right.** Tehila's take, labelled "nothing visibly wrong" from a contact sheet, starts
  with her leaning into the phone (a 1.88× size change) and the pipeline's pose QC refuses it; sta's "portrait" file is a landscape
  picture with black bars top and bottom, which INSPECT found and the label had not. Labels are set before a run and left as they were.
- **The head-height gates went blind when the crown was cut on every frame** — the matte's top is the picture edge and cannot move, so
  a carved crown delivered at 0.1 % spread. **Fixed 2026-09-20 as an evidence rule, not a framing threshold:** the profile now declares
  `crown_visible_min_for_head_metrics: 0.5` — below a recorded crown on half of the frames, Stage Ready does not have enough genuine
  evidence to trust the head-motion verification, so INSPECT fails `headroom` (no fixer addresses it; a reshoot) and VERIFY carries the
  same rule as the `crown_visible` gate. Between 0.5 and 0.95 the finding warns and verification proceeds; the former hardcoded 5 %
  warning is now `crown_visible_pass` in the profile; the 5–12 % headroom recommendation stays a recommendation. 0.5 is a conservative
  operational threshold based on the measurement mechanism (the performer's own uncut frames must be the norm, so the crown completion
  has references and the head metrics measure a recorded crown on most frames) — not a validated framing threshold. It changed one
  recorded run: Sandy's (a recorded crown on 24 % of frames) now stops at INSPECT.
- **The size cap and the size gate measured with different rulers** (a smoothed shoulder span vs the raw p95); a close-up landed 0.3 %
  over the cap after the fix. **Fixed 2026-09-20**: the gate now reads the ruler the cap is solved on — the shoulder span smoothed over
  0.5 s, the eye-to-shoulder drop standing in where the shoulders are not seen — at the floor and at the head target used, so a capped
  recording re-inspects at exactly the cap. The pipeline's solve was already on that ruler; no render changed, and the fixtures moved by
  at most 0.003.
- **The agent reads the intake brief.** With the labels leaking through the brief, the agent reshot three recordings at its first decision,
  quoting the brief; blind, it takes the measured path. The evaluation runs blind; the demo's briefs are the show's intake notes and
  are worth knowing about as an input the agent trusts.
- **Known limitation: Stage Ready currently verifies frame count and visual quality but does not yet detect frozen/repeated-frame
  motion continuity.** Thirty frozen frames pass every gate — the one silently wrong delivery on the set, counted as one and left
  in the set as such.

## Claim audit

Every substantive claim on this page, in the UI and in the architecture text, classified (audited
2026-09-20; the rule: nothing is claimed ahead of what is measured):

| claim | status | evidence |
|---|---|---|
| OpenCV 5 does the seeing: picture area, pose QC, framing solve, crown, exposure, key, matte extent, separation, head stability, frame count, audio MD5 | **live and demonstrated** | `stage_ready/vision/` on `opencv-python-headless 5.0.0.93`; `python3 -m stage_ready measure` recomputes every fixture (0 disagreements); the measurement Lambda runs the same code |
| OpenCV 5 DNN segmentation (U²-Net on `cv2.dnn`) | **live and demonstrated — for the seed and the matte's second opinion**; *not* the separation edge (measured 0.14× off; stays on the pipeline's matte) | `segcheck`, `measure --opinion dnn`, the Lambda's `matte_extent` |
| INSPECT / FIX / VERIFY run on AWS (Lambda `stage-ready-measure`) | **live and demonstrated** | live runs of every lineup recording; traces in `demo/eval/live/`; `?demo=0` on the public URL |
| The agent decides on Amazon Bedrock (Claude Sonnet 4.6) with constrained actions, a retry budget and code guardrails | **live and demonstrated** | the same live runs; `agent-eval`; the blind evaluation (30 Bedrock calls) |
| Automatic fixing | **live and demonstrated for one fixer** — `fix.reframe` (crop to the measured picture, size-capped solve); the only other change to a recording is the separation-targeted *grade* (a process strategy). No other fixer exists | Brian padded, Zach padded, sta (evaluation), Sandy (before the crown rule) |
| Verification against the profile's gates, on every render, before any delivery | **live and demonstrated** | every live run; the gate tests in the evaluation (frame drop and audio re-encode rejected) |
| The public demo (`?demo=1`) | **cached / replayed but measured** — fixtures written by `record` from the live measurement; the agent's decisions cached in its own words; deterministic | `demo/clips/`, `measure`, `tests/test_demo.py` |
| PROCESS: BodyTrack, MatAnyone, Composite | **local, cache-backed on S3 — not on AWS**; live runs use the archived render (a cache hit by source hash) or re-composite the retry on the laptop | `process_local.py`, `process_s3.py`, the diagram |
| A fresh upload gets a matte and a render | **planned / not implemented** (milestone 9) — an unknown upload is recognised as unknown and told so | `LiveNotWired` in `process_s3.py`; the UI's message |
| The render on AWS compute | **planned / not implemented** — the three tools are macOS | PLAN step 3's note; the diagram |
| Frozen / repeated-frame detection | **not implemented, stated** — "Stage Ready currently verifies frame count and visual quality but does not yet detect frozen/repeated-frame motion continuity" | `gate_frozen_frames`, the one silently wrong delivery in the evaluation |
| General-purpose: a second destination is a second profile | **planned / not demonstrated** — the loop and the agent name nothing show-specific, but only `midtown_red_curtain.json` exists | PLAN step 7 |
| The evaluation: 19 labelled items, silently wrong deliveries, per-gate precision/recall, agent vs rule table vs the linear pipeline | **evaluation-only, measured** | `demo/eval/EVALUATION.md`, regenerated by `evaluate --report` |
| Three sample behaviours on the public page | **cached / replayed but measured**, and each reproduced live | the picker; the live traces |
| Human control: approval before delivery, an operator override recorded as an override | **planned / not implemented** (PLAN step 8) | — |
| Behaviour on junk or enormous uploads | **partly implemented** — an unknown file is refused with a message; size and format limits are not enforced (PLAN step 8) | `app.js` intake |
| COOL on Graviton | **not started** (P2) | — |

## Under the hood

### Architecture

![Stage Ready architecture, as built](docs/architecture.svg)

[`docs/architecture.svg`](docs/architecture.svg) — one page, colour-coded by where a thing runs: orange on AWS (the API Lambda,
INSPECT / FIX / VERIFY on the measurement Lambda with OpenCV 5, DECIDE on Bedrock, S3, the trace), grey dashed on the laptop and
cache-backed on S3 (PROCESS: BodyTrack, MatAnyone, Composite — not on AWS today), blue the browser. It marks what is planned and not
built: a workdir for a fresh upload, the render on AWS compute, a second profile.

| layer | responsibility | where |
|---|---|---|
| **Profile** | the target as data: canvas, background, framing rule, look, gates, allowed strategies, retry budget, reshoot corpus | `profiles/midtown_red_curtain.json` |
| **Inspection (OpenCV 5)** | picture area, framing, subject presence and continuity, size and position stability, crop risk, exposure, key direction | live: `stage_ready/vision/` via `stage_ready/measure.py`; demo: `inspect.*.json` |
| **Findings** | typed records — id, measurement, threshold from the profile, confidence, affected frames, tool | `stage_ready/models.py` |
| **Agent** | reads findings, history and the profile; chooses the next action; judges whether a fix held | live: Amazon Bedrock; demo: `decide.*.json` |
| **Fixers / processors** | small, one-sided, composable; each declares what it addresses and what it costs | `fix.*.json`, `process.*.json` |
| **Verification (OpenCV 5)** | re-inspects the result against the profile's gates and diffs it against the pre-fix findings | live: `stage_ready/vision/` via `stage_ready/measure.py`; demo: `verify.*.json` |
| **Loop** | inspect → decide → fix \| process → verify → deliver \| reshoot, with the guarantees above; a generator of plain events | `stage_ready/loop.py` |
| **Backends** | `cached` (the demo) and `live` (INSPECT / FIX / VERIFY on the Lambda, DECIDE on Bedrock, PROCESS a cache hit from S3) behind one interface; the loop never learns which it has | `stage_ready/backends/` |
| **Reporter** | decision trace, delivery report with its numbers, reshoot guidance in capture terms | Trace / Details in `web/` |
| **Server** | static UI, `/api/recognize`, the run as server-sent events, byte-range media | `stage_ready/server.py` |

### The live hybrid on AWS

The minimal shape, built and run on 2026-09-19 (`stage_ready/aws.py`, `stage_ready/lambda_handler.py`):

| | where | what |
|---|---|---|
| **S3** `stage-ready-videos` (us-east-1, public access blocked) | AWS | every prefix is the source's SHA-256 — the matte cache's key: `sources/<sha>/source.<ext>` · `work/<sha>/…` (the workdir in the archive's own layout: pose, matte, mt, seed, the sampled band and composite frames, logs, params) · `artifacts/<sha>/<attempt>.mp4` · `measurements/<sha>/{inspect,verify}.*.json` · `runs/<sha>/<run_id>/trace.jsonl` · `models/u2net_human_seg.onnx` |
| **INSPECT, VERIFY** — Lambda `stage-ready-measure` | AWS | Python 3.12 on arm64, 3 GB, on the `stage-ready-opencv5` layer (opencv-python-headless 5.0.0.93, numpy 2.4.6, a static ffmpeg). Mirrors `work/<sha>/` to `/tmp`, fetches the U²-Net weights, runs `ArchiveMeasurer` exactly as on the laptop — the DNN as the `matte_extent` second opinion — and writes the record to `measurements/<sha>/`. |
| **DECIDE** — Bedrock Converse | AWS | one tool, `decide`, whose input schema is `models.DECISION_TOOL_SCHEMA`; the prompt carries the profile (gates, strategies with what they address and their bounds, retry budget, reshoot guidance), the current findings, the latest verification, the attempts so far, prior decisions and the budget. `global.anthropic.claude-sonnet-4-6` (Opus 5 and Sonnet 5 are listed for the account but not enabled). The loop's guards in `loop.py` still refuse what the profile does not allow. |
| **PROCESS** | laptop | `BodyTrack` (Apple Vision), MatAnyone (MPS) and `Composite` (CoreImage) are macOS. Attempt 1 is a cache hit on the source hash — the archived run; attempt 2 reuses the matte and tracking and re-composites at the strategy's bounds if that render is not already on disk. The delivery goes to `artifacts/<sha>/`. |
| **FIX** — Lambda | AWS | `fix.reframe` is deterministic OpenCV: `detect_band` for the crop, the size-capped dry solve for the head target (`ArchiveMeasurer.fix`); the loop then re-inspects the fixed picture on the Lambda. |

AWS access goes through boto3's default credential chain; nothing in this repo reads, prints, logs
or stores a credential. What is logged is the run's **trace** — every request id, latency, OpenCV
number and Bedrock decision (`.stage_ready/runs/<run_id>.jsonl` and `runs/<sha>/<run_id>/trace.jsonl`
in the bucket; the server streams it as a final `trace` event). No performer media is logged.

**The lineup and the rest, live, 2026-09-20** (the server's SSE stream or `run <clip> --live`;
traces in `demo/eval/live/`). Brian's padded input (run `20260920T105604-08b94c`) — Lambda inspect ✗
picture_area → Bedrock *fix.reframe* → Lambda fix: crop `1920:1080:320:180`, head target unchanged →
Lambda re-inspect: clean → Bedrock *process* → cache hit → Lambda verify ✓ **2.90×** → Bedrock
*deliver*; Lambda 243 s, Bedrock 19 s (13.3k in / 1.2k out tokens), ≈ $0.07. Ethel — as below,
again, delivered on the 1.52× pass; 5 min 55 s. Zach — inspect (warns) → *process* → verify ✓
**2.37×** → *deliver*, through the public endpoint in 2 min 38 s. Sandy — inspect ✗ (picture area,
size) → *fix.reframe* → Lambda fix (head 0.334 → 0.413) → re-inspect: clean → *process* → verify ✗
head spread 2.9 %, drift 5.3 px → *reshoot*, citing the walk-in first; 5 min 21 s. The padded Zach
(run `20260920T081238-c64572`): the same construction, verified at 2.36×. And the black-shirt Zach
take, 1.00× → 1.45× → reshoot. Every live outcome is the trusted measured path.

**Ethel's first live run** (`python3 -m stage_ready run ethel --live`, run id `20260919T220947-528236`):
INSPECT on the Lambda (61 s, every finding the fixture has) → Bedrock: *process, standard* (6.8 s,
3859/452 tokens) → the archived render, a cache hit → VERIFY on the Lambda: **fails separation at
1.12×** (the delivered file, decoded by FFmpeg — the frames say 1.13×), matte extent 0.989 against
the U²-Net opinion over 17 frames (131 s) → Bedrock: *process, separation-targeted* (6.9 s), citing
the one failing gate → re-composite at the bounds, a cache hit → VERIFY: **passes at 1.52×**
(123 s) → Bedrock: *deliver* (3.4 s). Latency 5 min 34 s end to end, of which the Lambda 315 s
(the U²-Net opinion at 2.7 s/frame is most of it), Bedrock 17 s. Cost: ≈ $0.01 of Lambda and
≈ $0.06 of Bedrock at list prices. `python3 -m stage_ready aws status | sync <clip> | deploy`
operate it; `STAGE_READY_LIVE_LOCAL=1` runs the same backend on the laptop's measurer without AWS.

### The public endpoint

`https://d4nh99blf9f5j.cloudfront.net/` — one CloudFront distribution (`EF0GHJDKHLD4G`), two origins,
nothing on any laptop (`stage_ready/deploy_web.py`, `python3 -m stage_ready aws web-deploy`):

| path | origin | how |
|---|---|---|
| `/`, `/app.js`, `/style.css`, `/stills/<clip>/<file>` | the bucket, prefix `public/` | an origin access control signs CloudFront's requests; the bucket stays private (a direct S3 GET is 403); byte ranges pass through, so the videos seek and loop |
| `/api/*` (profile, clips, recognize, the SSE run) | Lambda `stage-ready-web` | `stage_ready.server` unchanged, behind the Lambda Web Adapter on a Function URL in response-stream mode; the URL is IAM-only and a second origin access control signs for it, so the API is reachable only through the endpoint. Caching disabled on this path |

The API Lambda carries the code, the profile and the demo fixtures (never the stills). In
`?demo=0` it invokes the measurement Lambda and Bedrock under its own role and takes the render as
an S3 cache hit for a source the bucket holds (`process_s3.py`); the SSE stream sends a keepalive
every ten seconds so a two-minute verification survives CloudFront's idle limit. Verified from
outside the development machine on 2026-09-20: the page loads without authentication, all three
samples run, the videos play with range requests, Trace / Details and the session view work, no
local path appears anywhere in the shipped files or the rendered page, and a full live run of Zach
(`?demo=0`) streamed through the endpoint to its reshoot request.

**Reproduce the deployment** (from a clone, with AWS access on the default credential chain):
`pip install -e '.[live,aws]'`, `python3 -m stage_ready aws sync brian_padded ethel zach` (the
workdirs and media under their hashes; add `sandy zach_padded` for the deep-linked cases), `aws deploy --layer <dir>` (the OpenCV 5 layer and the
measurement Lambda; the layer directory is `python/` holding the unpacked
`opencv-python-headless==5.0.0.93` and `numpy==2.4.6` wheels for `manylinux_2_28_aarch64` /
Python 3.12 — `pip download --only-binary=:all: --platform manylinux_2_28_aarch64
--python-version 3.12` — plus `bin/ffmpeg`, a static arm64 build, for the audio hash), then
`aws web-deploy` (static files, media, the API Lambda, CloudFront; prints
the URL). `aws web-publish` re-uploads the UI and invalidates the cache after a change.

**Hosting cost, approximately:** S3 ≈ 1.1 GB of workdirs and media ≈ $0.03/month; CloudFront and
both Lambdas sit inside the free tiers at judge traffic (a demo run is one 200 ms invocation; a
live run ≈ $0.07 as above). Under $1/month at rest.

**Which model decides, measured.** `python3 -m stage_ready agent-eval --model <id>` replays the nine
trusted DECIDE states (three per performer, the exact prompt the live backend sends, nothing
adjusted) through a Bedrock model and scores action, strategy, citations, schema, latency and
tokens (`demo/eval/agent_*.json`, 2026-09-20):

| model | states right | schema · cites | latency | tokens per call | where it goes wrong |
|---|---|---|---|---|---|
| **Claude Sonnet 4.6** (default) | **9/9**, twice | 9/9 · 9/9 | 7.3 s | 4.7k in / 450 out | — |
| Amazon Nova 2 Lite | 6/9 (18/27 over three repeats, the same three wrong every time) | 27/27 · 27/27 | 1.3 s | 4.4k in / 180 out | Sandy #3: *inspect* instead of *reshoot* after the head gates failed with no strategy for them; Zach #1: the separation-targeted retry as the *first* attempt, reasoning from the over-lit warning; Zach #3: a second retry at the same bounds instead of stopping — "the budget still allows another attempt" |
| Amazon Nova Pro | 21/27 over three repeats — and **unstable**: three states answered differently across repeats | 27/27 · 27/27 | 1.3 s | 4.1k in / 110 out | Sandy #2: *deliver* before anything was verified (2 of 3); Sandy #3: the separation-targeted *retry* for head-height gates it does not address (2 of 3), *inspect* once; Zach #3: a *reframe fix* for a wardrobe problem (1 of 3) |

Both Novas are five times faster and a tenth of the cost, and both get every routine state right;
what they miss are the stopping decisions and the strategy choices — the judgement the loop exists
for — and Nova Pro does not even miss them consistently. So Sonnet 4.6 stays the agent; the model
is one environment variable (`STAGE_READY_BEDROCK_MODEL`), and the eval is how a replacement earns
the job. (Nova Premier was not tested: Bedrock lists it as legacy.)

`CachedBackend` answers each call from a file keyed on what a live run would cache on, so a hybrid
— cached matte, live agent — is the same interface with a different mix behind it:

| call | fixture | live equivalent |
|---|---|---|
| `recognize(sha256)` | `clip.json` → `recognize` | **live:** S3 list under `sources/<sha256>/` — is this source known, its matte cached? |
| `inspect(target)` | `inspect.<target>.json` | **live:** `vision.detect_band`, `BodyTrack` + `vision.pose_qc`, `vision.track.dry_solve`, `vision.crown_cut`, `vision.grade_qc` |
| `decide(n)` | `decide.<n>.json` | **live:** Amazon Bedrock Converse, the `decide` tool (`aws.AWS.decide`) |
| `fix(strategy)` | `fix.<strategy>.json` | `track_frame.py` with `SIZE_CAP`, crop to the measured band |
| `process(strategy)` | `process.<strategy>.json` | **live, laptop:** a cache hit on the source hash for the standard strategy; a re-composite at the bounds for the retry (`process_local.py`) |
| `verify(artifact)` | `verify.<artifact>.json` | **live:** `vision.matte_extent`, `vision.separation`, `vision.head_height` (spread, drift), `vision.frame_count`, `vision.audio_md5` |

### Why OpenCV 5

OpenCV does the seeing, and the seeing is what keeps the agent honest: every decision is made
against a measurement and every output is verified by one. The measurements live in
`stage_ready/vision/` on OpenCV 5 (`opencv-python==5.0.0.93`, pinned; the package refuses 4.x):
the picture area (`detect_band`), pose QC (`pose_qc`), the framing dry solve and the head's height
on the canvas (`track`), the crown (`crown_cut`), the matte against a second opinion
(`matte_extent`), luminance separation on the finished composite or the delivered file
(`separation`), exposure and key direction (`grade_qc`), and the frame count (`media`). They are
the Red Curtain scripts, ported to the digit — `python3 -m stage_ready measure` shows each number
against the fixture it was archived in. Three things the pipeline still borrows from the laptop:
the body-pose track (`BodyTrack`, Apple Vision), the video matte (MatAnyone on local MPS) and the
compositor (`Composite`, CoreImage). The person *segmentation* it borrowed — the seed the matte is
propagated from, and the matte's independent second opinion — no longer is:

**OpenCV 5 DNN subject segmentation — live for the seed and the second opinion, measured.**
`stage_ready/vision/segment.py::SubjectSegmenter` runs a person segmenter on `cv2.dnn` (CPU,
single-threaded by default, bit-for-bit reproducible). Two Apache-2.0 models are registered and
fetched with hash checks by `python3 -m stage_ready models fetch`; `python3 -m stage_ready segcheck`
measures both against the archive's Apple Vision opinions on the frames the archive itself used —
its seed frame, its 16–17 second-opinion frames, its 24 separation frames — on Sandy, Ethel and
Zach. Measured 2026-09-19:

| use | Vision (archived) | **U²-Net human-seg** (320 px, 176 MB, default) | PP-HumanSeg (OpenCV Zoo, 192 px, 6 MB) |
|---|---|---|---|
| seed — IoU against the Vision seed on the seed frame | — | **0.95 / 0.99 / 0.96** | 0.65 / 0.72 / 0.65 |
| seed → matte: a matte propagated from the DNN seed vs the archived matte (Zach, 106 frames) | — | **IoU 0.98 (min 0.96), alpha diff 1.7/255, head widths 1.000, `matte_extent` 1.006 = 1.006** | not run |
| `matte_extent` — matte head width / opinion head width, median | 0.981 / 0.996 / 1.006 | **1.003 / 0.989 / 1.018** (within 2.3 %) | 0.945 / 1.337 / 1.426 |
| the two opinions' head widths, DNN / Vision | — | 1.00 / 1.03 / 0.99 | 1.04 / 0.96 / 0.82 |
| `separation` with the DNN silhouette as the edge | 1.72 / 1.52 / 1.00→1.45 (matte edge) | 1.72 / 1.46 / 1.14→1.59 | 1.06 / 1.02 / 1.03→1.07 |
| runtime, CPU | — | 2.7 s per frame on 1 thread, 0.24 s on 8 | 39 ms per frame |

So: **the seed and the second opinion are live** on U²-Net — `python3 -m stage_ready measure
--opinion dnn` recomputes the `matte_extent` gate with the DNN as the opinion and every status
agrees with the archive's. **The separation edge stays on the pipeline's own matte**: a DNN edge
lands up to 0.14× from it on Zach's ×3.1-upscaled picture, enough to cross the gate, and the matte
is where the pipeline runs anyway — `edge_separation` remains on the seam as a cross-check, not a
measurement of record. **PP-HumanSeg is too coarse for the head band** — at 192 px it drops hair,
so its opinion is 4–18 % narrower than Vision's and a matte that lost hair would pass against it;
it is kept as the fast baseline. The models are not in the repository (`models/*.onnx` is
ignored); the demo (`?demo=1`) never loads one.

### What comes from the Red Curtain pipeline

`midtown_red_curtain.sh` is a fixed linear pipeline: measure, run every stage in order, warn.
Stage Ready keeps its stages and replaces its control flow with the agent.

| Red Curtain | Stage Ready role |
|---|---|
| `detect_band.py` | inspect — picture area |
| `BodyTrack` + `pose_qc.py` | inspect — subject presence and continuity |
| `pick_seed.py`, `clean_seed.py`, `PersonMatte`, `run_matanyone.py` | process — segmentation |
| `matte_qc.py` | verify — segmentation extent against an independent opinion |
| `track_frame.py`, `warp.py`, `soften_crown.py` | fix / process — drift-removing reframe, size cap, crown |
| `auto_grade.py`, `Composite`, the plate | process — the profile-owned look |
| `silhouette_qc.py` | verify — separation (warning → gate) |
| frame-count and audio-MD5 checks | verify — integrity |
| `contact_sheet.py` | report — human review |
| `RECORDING_REQUIREMENTS.md` | report — reshoot guidance corpus |

**Portability.** The OpenCV scripts are ported (`stage_ready/vision`). `PersonMatte`'s two jobs are
done by `SubjectSegmenter` on `cv2.dnn`. Still on the laptop: `BodyTrack` (the pose track — Apple
Vision), MatAnyone (the matte — local MPS) and `Composite` (CoreImage); local workers for the demo,
to be replaced when the loop moves off the laptop.

**Lessons that carry:** measure, never assume · check the right thing · a second opinion beats
self-consistency · measure the subject against the background · cheap checks before expensive work
· clamp and warn, don't rescue · fix, then re-inspect · missing pixels are missing.

**Not Stage Ready's own:** the plate, the neon sign, the comedy framing, the fixed canvas. They
live in the Red Curtain profile.

## Roadmap

Each milestone advances the demo; nothing is built that the screen does not show. The loop, the
profile, the three paths, the other exit and the workspace exist today, replayed from cached
measurements and reproduced live. What is left is a fresh upload's render and a second profile.

| # | milestone | status |
|---|---|---|
| 0 | **Ground truth.** Run the separation-targeted composite on Ethel's cached matte and measure it | **done 2026-09-19** — 1.52× with the grade at its bounds (`work/midtown_ethel_chadwick_v2/separation.log`); the projection of 1.58× was wrong by 0.06×, in the flattering direction |
| 1 | **Profile + inspect.** The profile as a data file; inspection emits findings against it | done — the profile is data; INSPECT is measured live with OpenCV 5 (`stage_ready/vision`, 2026-09-19) |
| 2 | **Process + verify.** Processing toward the profile, verification against its gates, the report | verification measured live with OpenCV 5 on the Lambda (2026-09-19); processing runs on the laptop, cache-backed on S3 by source hash — not on AWS, and not for a fresh upload (milestone 9) |
| 3 | **Agent loop.** An agent choosing inspect / fix / process / verify / stop, every decision traced, the loop's guardrails around it | done — loop and guardrails in `loop.py` (tested); the agent on Bedrock (Claude Sonnet 4.6) since 2026-09-19, every decision traced with its request id |
| 4 | **Reframe fixer.** Crop to the measured picture area + size-capped reframe, re-inspected | done, live on the Lambda — the controlled repair case (Brian's recording padded: inspect ✗ → crop → re-inspect ✓ → verified 2.90×); on Sandy's recording the fix is not even reached: the crown-evidence rule stops it at INSPECT (`?clip=sandy`) |
| 5 | **Verification-driven retry.** The separation gate fails, the agent switches strategy, reprocesses, passes | done in the demo (Ethel); the pass is measured (milestone 0) |
| 6 | **The other exit.** A failed verification with no allowed strategy left ends in a reshoot request that leads with the cause | done (Sandy — `?clip=sandy`, and live; `&budget=0` shows the spent-budget variant on Ethel in the picker) |
| 7 | **The screen.** One recording at a time, the session view, Trace and Details | done |
| 8 | **OpenCV 5 DNN segmentation / QC.** `SubjectSegmenter`, measured against the samples | live for the seed and the second opinion (U²-Net on `cv2.dnn`, 2026-09-19); the separation edge stays on the matte, by measurement |
| 9 | **Live wiring.** OpenCV inspection and verification on AWS compute, the matte cache on S3 by source hash, Bedrock for the agent | the hybrid runs on every lineup recording (first on Ethel 2026-09-19): Lambda INSPECT / FIX / VERIFY, Bedrock DECIDE, S3 by source hash, the rendering on the laptop. **Open:** a fresh upload's workdir (BodyTrack, MatAnyone, Composite are macOS; nothing renders it yet) and the render on AWS compute |

**Risk, named once — and settled.** Ethel's pass depended on the second strategy clearing the gate
within honest bounds; the archived shadow lift only partly closed it (1.13× → 1.37×). Milestone 0
measured the rest: the lift is the lever (+0.005 ≈ +0.035×), the wrap and the rim add a little
each, and the gate clears at 1.52× only with all three at their bounds. So the pass is real and the
margin is thin, which is the honest shape of the story: the strategy did what it is allowed to do
and no more. Had it not cleared, the exit would have been the reshoot request the demo already
shows, or Ethel's defect would have become the other documented verification failure — a matte
propagated from a poor seed frame measuring narrower than the independent opinion — with a re-seed
as the strategy change.

## For the record

### Layout

```
profiles/midtown_red_curtain.json   the Target Output Profile — data, not code
stage_ready/models.py               Finding, Decision, Stage, Gate, … — the shared language
stage_ready/loop.py                 inspect → decide → fix | process → verify → deliver | reshoot
stage_ready/backends/cached.py      demo backend: every call answered from a fixture; recognises an upload
                                    by SHA-256 (or name alias) from clip.json
stage_ready/backends/live.py        live backend: INSPECT / FIX / VERIFY on the measurement Lambda (OpenCV 5), DECIDE on
                                    Bedrock, PROCESS on the laptop or an S3 cache hit; STAGE_READY_LIVE_LOCAL=1 measures here
stage_ready/vision/                 OpenCV 5 measurements: band, pose, track (dry solve, head height), matte, silhouette,
                                    grade, media — the Red Curtain scripts, ported to the digit
stage_ready/vision/segment.py       SubjectSegmenter — OpenCV 5 DNN person segmentation (U²-Net / PP-HumanSeg), the seed and
                                    the matte's second opinion; segcheck.py measures it against the archive's Vision opinions
stage_ready/measure.py              INSPECT / VERIFY records computed from a workdir's files with stage_ready.vision
stage_ready/aws.py                  S3 by source hash, the measurement Lambda (deploy/invoke), Bedrock DECIDE, the run trace
stage_ready/lambda_handler.py       the Lambda entry: mirror work/<sha>/ from S3, run ArchiveMeasurer, write measurements/
stage_ready/process_local.py        the process stage on the laptop, cached by source hash; the retry at the bounds
stage_ready/server.py               static UI, /api/recognize, SSE run stream, byte-range media
web/                                the workspace
demo/clips/<id>/                    cached fixtures, keyed the way a live cache would be; clip.json → archive names the files
demo/lineup.json                    the polished demo: Brian (padded) → Ethel → Zach (everything else stays replayable by id — ?clip=sandy, ?clip=zach_padded)
demo/derive.sh, demo/derived.json   every derived input (excerpts, the padded controlled input, the corpus's michi sample): exact command, hashes, edits
demo/eval/set.json, derive_eval.sh   the labelled evaluation set (19 items) and the synthesised negatives' exact commands
demo/eval/EVALUATION.md, results/   the generated evaluation report and every item's result, per agent (bedrock, rules)
demo/eval/corpus/, live/            the evaluation corpus: measured candidates, moved fixtures, the live AWS traces
stage_ready/evaluate.py, eval_report.py, rules_agent.py   the evaluation runner, its report, and the rule-table agent (the ablation)
stage_ready/record.py               writes a clip's inspect/verify/process fixtures from the live measurement, not by hand
tests/test_demo.py                  22 tests: the lineup's three behaviours, the corpus's reshoot, determinism, recognition, provenance, the guardrails
tests/test_eval.py                  7 tests: the rule table reproduces every fixture path; the evaluation's scoring rules
tests/test_vision.py                5 tests: OpenCV 5 reproduces the archived numbers; the DNN opinion agrees with Vision (skipped without OpenCV 5 + the archive + the model)
stage_ready/bundle.py               the judge bundle: build from the archive, install into a clone, verify
```

```bash
python3 -m stage_ready run              # the same three runs, as text
python3 -m stage_ready trace ethel      # one run, as JSON lines
python3 -m unittest discover -s tests   # 20 tests, standard library

python3 -m venv .venv && .venv/bin/pip install -e '.[live]'    # OpenCV 5 + numpy, pinned
.venv/bin/python -m stage_ready measure                        # every fixture number, recomputed with OpenCV 5
.venv/bin/python -m stage_ready models fetch                   # the DNN segmenter's weights (176 MB, hash-checked)
.venv/bin/python -m stage_ready segcheck                       # the DNN against the archive's Vision opinions
.venv/bin/python -m stage_ready measure --opinion dnn          # matte_extent with the DNN as the second opinion
.venv/bin/pip install -e '.[live,aws]'                         # + boto3
.venv/bin/python -m stage_ready aws status                     # STS identity, bucket, function, which sources are on S3
.venv/bin/python -m stage_ready aws sync ethel                 # the workdir, source and deliveries under sources/work/artifacts/<sha256>/
.venv/bin/python -m stage_ready aws deploy --layer <dir>       # role, layer (OpenCV 5 + ffmpeg, arm64), function
.venv/bin/python -m stage_ready run ethel --live               # the hybrid: Lambda measures, Bedrock decides, the laptop renders
.venv/bin/python -m unittest discover -s tests                 # 34 tests (5 need OpenCV 5 + the archive + the model)
```

`measure` and `--live` read the Red Curtain archive's workdirs — `--archive <dir>` or
`$STAGE_READY_ARCHIVE`, default `~/mts`, or the judge bundle ([Real stills and videos](#real-stills-and-videos));
without one they say so and the demo is unaffected. Python 3.12 is what the fixtures were measured
with (`.python-version`); any ≥ 3.11 runs, with the one decoder caveat noted under
[What is measured](#what-is-measured).

URL levers: `&clip=ethel` (put a sample on the bench at once), `&autorun=1` (press Make Stage Ready
as soon as a recording is on the bench), `&instant=1` (no pacing), `&step=1` (Space / → advances
one event — for presenting), `&cadence=500` (ms per beat), `&budget=0` (retry budget zero — Ethel's
recording ends as a reshoot request).

### Real stills and videos

`demo/clips/<id>/stills/` holds one frame of the archived source and of each delivered attempt,
named in `clip.json` (`"stills": {"source": "source.jpg", "attempt_1": "attempt_1.jpg"}`), and
optionally the archived videos next to them (`"videos": {…}` — symlinks into `~/mts` are fine; the
server honours byte ranges so they seek and loop). The UI plays a video where there is one, shows
the frame where there is not, and draws a stand-in from the fixture numbers otherwise. A dropped
file plays from the browser's own object URL. `clip.json` also carries `recognize` — the archived
source's SHA-256 (`work/midtown_<clip>/source.key`, the matte-cache key; a list when the same source
exists in two containers) and the file-name aliases the drop zone accepts — and `order`, the lineup
position. Frames are pulled at the same timestamp for source and output, so each pair is the same
moment before and after; the linked videos are these same archive files:

| sample | source frame | delivered frame |
|---|---|---|
| Brian Shirley — padded (controlled) | `brian_shirley_v2_padded.mp4` frame 641 — the untouched recording inside its 2560 × 1440 black canvas (`demo/derived.json`) | `brian_shirley_v2_padded_red_v1.mp4` frame 641 — the archive run of 2026-09-20 on the padded input, measured 2.90× |
| Sandy Hackett (`?clip=sandy`) | `sandy_hackett_v2.mp4` frame 716 — chosen from the 24 % of frames where the crown is inside the picture, after the walk-in | `sandy_hackett_v2_red_v4.mp4` frame 716 — the crown-completion render, the run the workdir holds (fails head height; the still is the render the reshoot request is about) |
| Zach Sain | `zach_sain_v1_demo.mp4` frame 901 (the derived excerpt — `demo/derived.json`) | `zach_sain_v1_demo_red_v1.mp4` frame 901 — the archive run of 2026-09-20, measured 2.37× |
| Ethel Chadwick | `ethel_chadwick_v2.mp4` frame 900 | attempt 1: `ethel_chadwick_v2_v1.mp4` frame 900; attempt 2: `ethel_chadwick_v2_v3.mp4` frame 900 — the separation-targeted render, measured 1.52× (`ethel_chadwick_v2_v2.mp4` is the intermediate shadow-lift-only render, 1.37×) |
| Zach Sain — padded (controlled, `?clip=zach_padded`, superseded by Brian on the left card) | `zach_sain_v1_padded.mp4` frame 901 — the clean excerpt inside its 1280 × 720 black canvas (`demo/derived.json`) | `zach_sain_v1_padded_red_v1.mp4` frame 901 — the archive run of 2026-09-20 on the padded input, measured 2.36× |

The stills directory is git-ignored (performer footage). **Judges get it as a bundle.** The
performers agreed to judges seeing their recordings, not to a public repository, so the footage
and the measured intermediates ship as a private download built by
`python3 -m stage_ready bundle --out <dir>` (1.1 GB: the demo's stills and videos, the archived
sources and deliveries, and every workdir file `measure` reads — whole where a measurement reads
every frame, sampled by the measurements' own `sample_indices` where it reads a spread — with a
`MANIFEST.json` of sizes and SHA-256s). In a clone:

```bash
python3 -m stage_ready bundle --install <bundle-dir>     # links the media into demo/clips/*/stills
python3 -m stage_ready serve                             # the workspace now plays the real videos
export STAGE_READY_ARCHIVE=<bundle-dir>                  # and measure / --live read the bundle
.venv/bin/python -m stage_ready measure                  # 0 disagreements, same as against ~/mts
python3 -m stage_ready bundle --verify <bundle-dir>      # every manifest entry present, hashes equal
```

Verified 2026-09-19 from a fresh `git clone` on this machine: demo tests pass with the standard
library alone, the bundle installs, the videos serve with byte ranges, and the full suite (25 tests)
passes with OpenCV 5 against the bundle.

### Performers and numbers

The visible demo is three performers — Brian Shirley, Ethel Chadwick, Zach Sain (`demo/lineup.json`)
— and every input carries **its own** measurements; a test forbids a fixture that borrows another
clip's numbers. Ethel's input is her archived recording, untouched (`ethel_chadwick_v2`, runs `_v1`
and `_v3`). Zach's is a curated excerpt of his other real take. Brian's is his untouched recording
(`brian_shirley_v2`, verified on its own first) with padding added on purpose — a *controlled*
input, labelled so on the page. Two more inputs are replayable but not offered: Sandy's untouched
recording, the natural reshoot case ([`?clip=sandy`](https://d4nh99blf9f5j.cloudfront.net/?clip=sandy)),
and the same padded construction on Zach ([`?clip=zach_padded`](https://d4nh99blf9f5j.cloudfront.net/?clip=zach_padded)).
The next section is the rule for the whole demo.

### Polished demo vs evaluation corpus

Two sets, kept apart on purpose:

- **The polished demo** uses real performer footage curated to show one Stage Ready behaviour
  clearly. A demo input may be an untouched recording, a **derived** one — a contiguous excerpt,
  a remux, a frame-rate normalisation — or a **controlled** one: a base that verifies on its own,
  with one repairable framing defect injected on purpose (padding into a larger canvas) so the
  repair path can be shown ending in a delivery. Every derivation is recorded in
  `demo/derived.json` (`demo/derive.sh` makes it): original file and SHA-256, exact time range,
  exact command, output SHA-256, the edits applied — and for a controlled input, the base's own
  verification and the injected defect. Nothing is ever synthesised, stabilised, recoloured or
  retouched, nothing inside the picture is scaled or moved, and no threshold moves. A derived input
  is recognised by its own hash; its original is not matched to it. The fixtures are written from
  the derived input's own pipeline run (`stage_ready record`). A controlled input says so in the
  UI — the picker card, the source card and the Details table carry its provenance line.
- **The evaluation corpus** is the untouched archival recordings, with their real failure modes,
  measured and kept: `demo/eval/corpus/`, `demo/eval/live/` (the live AWS traces), and the
  archive's workdirs.

| recording | demo | evaluation corpus |
|---|---|---|
| Brian, padded — `brian_shirley_v2_padded.mp4` | **controlled** (the left card): the untouched recording `brian_shirley_v2.mp4` — re-run through today's pipeline first, on its own: crown inside on every frame, separation **2.91×**, matte 100 %, head 0.7 % / 1.2 px, 1285 frames, audio equal, one warning (under-lit, grade held at ×1.25) — placed unscaled and centred inside a 2560 × 1440 black canvas: `pad=2560:1440:320:180`, one x264 pass, audio stream copied, no trim, no scaling, no retiming. Both band detectors read exactly 1920 × 1080 at +320+180. Run through the pipeline 2026-09-20 and the live loop: inspect ✗ picture_area only → crop, head target unchanged, 0 pixels invented → re-inspect ✓ → **2.90×**, matte 100 %, 0.7 % / 1.2 px, 1285 frames, audio equal → deliver | `brian_shirley_v2.mp4`, untouched — the reference recording (2.96× on the 2026-09-06 pipeline, 2.91× today) |
| Sandy — `sandy_hackett_v2.mp4` | **not in the picker** (`?clip=sandy`) — since the crown-evidence rule (2026-09-20) INSPECT fails `headroom`: a recorded crown on 24 % of frames, under the 50 % the head metrics need, and no fixer addresses it, so the agent asks for a reshoot at its first decision. Before the rule, the fix held (padding cropped, shoulders capped) and the render failed on head height, 2.9 % spread / 5.3 px drift — the number that exposed the crown problem; those records stay in his fixtures. Every attempt at a Sandy input that ends in a delivery failed honestly and is recorded in `demo/eval/corpus/sandy_excerpts/measured.json`: two trimmed excerpts of this take (2.3 % / 2.4 % — his crown is cut on 81–86 % of frames and the completed crown jitters); and the clean-base search over his other two real takes — `sandy_hackett_v1.mov` (Apple Vision finds the seated close-up on 6 % of frames; the pipeline refuses) and `sandy_hackett_0910.mov` (crown inside, matte clean, but chest-up with the arms out of frame — pose on 58 %; a close-up; over-lit; and his own head motion, 5.6 % of the source, reads 2.3–2.4 % against the 2 % gate in the two 74 %-covered windows). No Sandy base verifies on its own, and the one pipeline knob that would make one deliver (crown completion off, the archive's old v3 look) was declined as complexity | the same recording, the natural reshoot case; live result 2026-09-20: reshoot |
| Ethel — `ethel_chadwick_v2.mp4` | **untouched** | the same recording |
| Zach — `zach_sain_v1_demo.mp4` | **derived**: 15 s → 75 s of `zach_sain_v1.mov`, his other real take (mint trousers, the crown inside the picture, one distance); 30 fps unchanged, the container's 180° rotation baked into the pixels by the one re-encode, audio re-encoded AAC. Run through the pipeline 2026-09-20 (380 s): every gate passes, separation **2.37×** | `zach_sain_v2.mov`, the black-shirt take, untouched: separation **1.00×** → **1.45×** at the retry's bounds → reshoot (`demo/eval/corpus/zach_sain_v2/`, `demo/eval/live/zach_20260920T014717.jsonl`) |
| Zach, padded — `zach_sain_v1_padded.mp4` | **controlled, not in the picker** (`?clip=zach_padded`; superseded by Brian on the left card so the picker shows three performers): the clean excerpt above (re-verified first: 2.37×, head 0.7 %, 1800 frames, audio equal) placed unscaled and centred inside a 1280 × 720 black canvas — `pad=1280:720:400:158`, one x264 pass, audio stream copied, no trim, no scaling, no retiming. Both band detectors read exactly 480 × 404 at +400+158. Run through the pipeline 2026-09-20 (308 s) and the live loop: inspect ✗ picture_area only → crop, head target unchanged, 0 pixels invented → re-inspect ✓ → **2.36×**, matte 102 %, 0.7 % / 1.9 px, 1800 frames, audio equal → deliver | — (a demonstration input, by construction; not evaluation data) |
| Michi — `michi_sample_v1.mp4` | not in the demo | derived from a club recording of the author (45 s at 30 fps); the near-threshold pass, 1.51× |

### What is measured

Every number for Sandy's recording and Ethel's first attempt is an
archived measurement from the Red Curtain pipeline (`sandy_hackett_v2`, `ethel_chadwick_v2`),
re-derived from the workdirs on 2026-09-10 where the doc did not record it. **Brian's padded input
was measured on 2026-09-20**: his untouched recording first, through today's pipeline
(`work/midtown_brian_shirley_v2_base`, 948 s — 2.91×, head 0.7 %, 1285 frames), then the padded
copy (`work/midtown_brian_shirley_v2_padded`) and `record brian_padded --fixed` — inspect ✗
picture_area (1920 × 1080 at +320+180 in 2560 × 1440), the fix's crop and unchanged head target,
re-inspect clean, and a first-pass render at **2.90×**, matte 100 % against the DNN opinion,
head 0.7 % / 1.2 px, 1285 frames, audio MD5 equal. The same construction on Zach
(`?clip=zach_padded`, 2.36×) preceded it. **Zach's numbers were measured on 2026-09-20** by
running the derived excerpt of his other take through the pipeline (`work/midtown_zach_sain_v1_demo`,
358 s) and writing the fixtures from `stage_ready.measure` with `python3 -m stage_ready record
zach`: separation **2.37×** (0.267 / 0.113), matte 101 %, head held to 0.7 % with 1.9 px of drift,
1800 frames, audio MD5 equal to the source. His black-shirt take's numbers (1.00× → 1.45×) are the
evaluation corpus's, measured on 2026-09-19 and live on 2026-09-20. **Ethel's second attempt was measured on 2026-09-19** on the cached matte and tracking, with
only the grade changed: the archived shadow lift alone took separation 1.13× → 1.37×, and a grid
over the strategy's three bounded knobs (`work/midtown_ethel_chadwick_v2/separation.log`) shows
the gate clears only with all three at their bounds — rim 0.45, wrap 0.70, lift +0.040 — at
**1.52×** (0.188 / 0.123). The render is `ethel_chadwick_v2_v3.mp4`: 1237 frames, audio MD5 equal to
the source. The fixture had projected 1.58× at softer settings; that measured 1.43× and would have
failed the gate, which is why the number was measured before the video was scripted. Nothing in
the demo is projected any more; a fixture that were would say so in its `provenance`, the UI would
tag it, and `test_no_number_is_ahead_of_its_measurement` would fail.

**Recomputed with OpenCV 5, in this repo, 2026-09-19.** `python3 -m stage_ready measure` runs
`stage_ready/vision` over the archived workdirs and prints every finding and gate beside its
fixture. Ethel and the reference clip agree on every number (separation 1.13× / 1.52× / 2.96×,
head spread 1.3 % / 0.7 %, matte extent, frame counts, audio). One caveat is the decoder's, not
the measurement's: a separation read from a delivered H.264 file (only Ethel's attempt 1, whose
composite frames were overwritten) moves about 1 % with the video backend OpenCV was built
against — 1.13× through AVFoundation, 1.12× through FFmpeg — so the frames are the record and the
result names its decoder. Four fixture entries were corrected
from the re-run, none changing a status: Ethel's key direction (×0.80, from the left — not
flat-lit), her head drift (3.1 px, measured; the fixture had carried an unmeasured 1.5), Sandy's
steadiness (1.75×, as `pose_qc.py` reports it), and face exposure recorded as the gain the grade
applies in all three clips. **One disagreement changed the demo:** Sandy's fixture had carried the
archive's v3 run (`sandy_hackett_v2_red_v3_full.mp4`, head spread 1.2 %, delivered), but his workdir
holds the v4 run — the crown completion of 2026-09-11 — whose solve measures head spread **2.9 %**
and drift **5.3 px**, both over the gates, and v3 cannot be regenerated. The v3 pass was flattered
by the defect the completion fixes: with his crown cut off on 76 % of frames the head top was pinned
to the picture edge and could not move. So Sandy's fixture, video and still are now v4, measured,
and his path ends in a reshoot request — for the reason INSPECT warned about, the walk-in. The
demo lost a "consistent output" and gained the exit the product exists to make honest.
