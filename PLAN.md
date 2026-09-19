# PLAN — what has to be true before we shoot the demo video

Working document for the run-up to the OpenCV AI Competition 2026 submission. It covers only the
work that has to land **before** the ≤ 5-minute video is worth recording. It is not a rewrite of
the old `PLAN.md` (that one was merged into `README.md` on 2026-09-14 and deleted); the README
stays the judge-facing description of the product, this file is the build order.

## The fixed points

| | |
|---|---|
| Final deadline | **2026-10-26, 11:59 p.m. Pacific** — 38 days from 2026-09-18 |
| Hard requirement | every entry uses **OpenCV 5 for substantive image or video analysis** |
| Hard requirement | a **meaningful component running on AWS** |
| Hard requirement | a **working web endpoint** or an arranged live screen-share |
| Hard requirement | judge-accessible **code repository or archive**, pinned deps, build/deploy/test instructions |
| Deliverables | technical report · architecture diagram (OpenCV 5 + AWS) · evaluation evidence with failure cases · video ≤ 5 min showing team, working app, architecture, results |
| Overall weights | technical execution 30 · innovation 20 · real-world impact 20 · UX 10 · documentation 10 · cloud delivery 10 |
| Agentic Vision Award | OpenCV 5 + agent integration 30 · orchestration and autonomy 25 · task effectiveness and evaluation 20 · failure handling, observability, security, human control 15 · UX and docs 10 |
| Best Use of COOL | COOL on Graviton/Arm 30 · architecture 25 · measured performance 20 · innovation 15 · reproducibility 10 |

## Why the video is last

Every beat of the video is a recording of the product making a claim, and every claim on screen is
a number. If a number changes afterwards, the video is reshot. So the order is: **measure first,
wire second, shoot third.** The two numbers most likely to move are Ethel's second-attempt
separation (projected today) and anything OpenCV 5 recomputes when it replaces the archived
measurement. Both are P0 below.

## Ready to shoot — the exit checklist

Shooting starts when all of these are true:

- [ ] Ethel's second attempt is a **measured** number, or the demo's climax has been re-scripted
- [ ] `python3 -m stage_ready` INSPECT and VERIFY compute their numbers with **cv2 5.x in this repo**
- [ ] a **meaningful component runs on AWS** and the run can be shown doing it
- [ ] a **public URL** serves the demo, from a clean machine, with media that plays
- [ ] a judge can `git clone` and reach a working demo from the README alone
- [ ] the **evaluation table** exists: N clips, gate precision/recall, silently-wrong deliveries
- [ ] the **architecture diagram** is drawn and matches the code
- [ ] no claim in `README.md` or the UI is ahead of what is measured

---

## P0 — blocking (eligibility, not points)

### 0. Ground truth for Ethel — README milestone 0

**Why:** Ethel's retry is the payoff of the whole demo and 1.58× is projected. The archived shadow
lift alone measured 1.13× → 1.37×.
**Do:** run the separation-targeted composite on Ethel's cached matte in `~/mts/work/midtown_ethel_chadwick_v2`,
measure with `silhouette_qc.py`, write the result into `demo/clips/ethel/verify.attempt_2.json`
with its `provenance`, drop the *projected* tag in the UI.
**Accept:** the number in the fixture is an archived measurement; `README.md` "What is measured and
what is projected" has nothing left in the projected column.
**Decision point:** if the gate cannot be cleared inside the strategy's bounds → the demo's climax
becomes the reshoot exit (`&budget=0`), or Ethel's defect is re-cast as the matte-extent failure and
the strategy change is a re-seed. Either way the video script changes, so this lands **first**.

### 1. A repository a judge can clone

**Why:** `stage-ready/` is not a git repository at all, and `demo/clips/*/stills/` — the media the
demo plays — is git-ignored and symlinked into `~/mts`. A judge who clones today gets stand-ins
drawn from fixture numbers.
**Do:** `git init`, first commit, LICENSE, decide the media question (performer releases for the
clips we ship, or a judge-accessible archive bundle alongside the repo, or substitute footage we own).
Pin dependencies; `pyproject.toml` currently says `opencv-python>=4.9`, which reads as an OpenCV 4
project — it must pin OpenCV 5.
**Accept:** clone into a clean directory on another machine, follow the README, get a demo with
video playing and 17/17 tests passing.

### 2. OpenCV 5 doing the seeing, inside this repo

**Why:** the rule is OpenCV 5 for substantive analysis, and technical execution (30%) is explicitly
"depth of the OpenCV 5 implementation". Today the repo contains no `cv2`; the 21 OpenCV scripts live
in `~/mts` on 5.0.0 and are not part of the submission.
**Do, in two tiers:**

- **2a — port the measurements.** `detect_band.py`, `pose_qc.py`, `matte_qc.py`, `silhouette_qc.py`
  → `stage_ready/vision/`, called by the live backend's `inspect()` and `verify()` so the numbers are
  computed from the video files, not replayed. Mostly a move-and-pin job.
- **2b — `SubjectSegmenter` on `cv2.dnn`** (README milestone 8). The seam already exists in
  `stage_ready/backends/live.py`. This is what makes the OpenCV 5 claim *deep* rather than
  incidental, and it is the only way the matte's second opinion (Apple Vision today, laptop-only)
  can follow the loop onto AWS.

**Accept:** run OpenCV 5 inspect/verify over the archived clips and reproduce the fixture numbers
within tolerance — including the three `SubjectSegmenter` uses (seed, `matte_extent`, `separation`).
Any disagreement with the archived second opinion is written down before the claim changes from
*planned* to *live*. Where a recomputed number differs, the fixture is updated, not the number.

### 3. A meaningful component on AWS

**Why:** required, and cloud delivery is 10% — "deployment quality, repeatability, observability,
security, responsible-use practices".
**Do:** the hybrid from README milestone 9, smallest honest version first —

- **S3** for sources, mattes and deliveries, keyed by source SHA-256 (already the cache key);
- **AWS compute** (Batch or Lambda) running the OpenCV 5 inspect/verify jobs from step 2;
- **Bedrock** for DECIDE — the Converse API with a tool schema matching `models.Decision`.

Bedrock is the highest-value of the three: the agent is a JSON file today, and the Agentic Vision
award's top line is "substantive OpenCV 5 **and agent** integration."
**Accept:** `?demo=0` completes a real run end to end on at least one clip; credentials still only
via boto3's default chain, never read, printed or stored.

### 4. A working endpoint

**Why:** required deliverable; also the fallback if a live screen-share goes wrong.
**Do:** deploy `stage_ready/server.py` (stdlib, so almost anything hosts it) with the demo fixtures
and media. `?demo=1` must work for a judge with no AWS account and no `~/mts`; the live path sits
behind it.
**Accept:** the URL loads on a phone and on a clean browser profile, media plays, no dangling symlinks.

---

## P1 — where the score actually is

### 5. Evaluation

**Why:** "evaluation evidence including limitations and failure cases" is a stated requirement and
is named inside the 30% criterion. Three hand-picked clips is not an evaluation.
**Do:** build a set from the five archived workdirs (`brian`, `ethel`, `joel`, `sandy`, `zach`) plus
synthesised negatives with known defects — wardrobe recoloured toward the plate, pillarboxing,
crown cropped, frames dropped, audio re-encoded. Report:

- **silently wrong deliveries out of N** — the number the product exists to make zero;
- per-gate precision/recall against our own labels;
- where the loop was wrong, and what it cost.

**Accept:** a table in the report and a script that regenerates it.

### 6. Baseline and ablation

**Why:** the claims are "verification changes behaviour" and "the agent decides". Both need a control.
**Do:** (a) run `midtown_red_curtain.sh` — fixed, linear, warns — against the same set and show where
it ships something wrong that the loop catches; (b) run the loop with the agent replaced by a
threshold table and a fixed strategy order, and find where the agent actually wins.
**Accept:** both results written down, including a tie. "The agent ties the rule table on this set,
and here is the case class where it does not" is a stronger answer than silence — judges will ask.

### 7. A second Target Output Profile

**Why:** "a second destination is a second JSON file" is the innovation and impact argument and
nothing demonstrates it. One profile makes this look like one show's tool.
**Do:** a 16:9 talking-head course delivery, clean-up-only, with real measured samples, exercising a
different subset of the gates and strategies.
**Accept:** it runs through the unchanged loop with no per-recording settings and no code change.

### 8. Responsible use, observability, human control

**Why:** 15% of the Agentic Vision award and part of the 10% cloud criterion; also a required
section of the report, which the README does not have.
**Do:**

- write the responsible-use section around the position we already hold — **no generative model
  touches the performer**; face, expression, lip sync, clothing and audio are the recorded pixels;
  frame count and audio MD5 are gates. Add performer consent and data retention. Say plainly that
  the separation gate is an accessibility check: what a colour-blind viewer or a heavy re-encode sees.
- per-stage cost and latency in the trace; structured logs a judge can read.
- a human control: approval before delivery, and an operator override of a gate that is recorded as
  an override rather than a pass.
- behaviour on a junk, adversarial or enormous upload — refuse cleanly, never guess.

**Accept:** each is visible in the UI or the trace, not only in prose.

---

## P2 — only if P0 and P1 are done by week 4

### 9. COOL on Graviton

A separate $1,000 with a rubric that is 30% COOL-on-Arm integration and 20% *measured* performance.
We will be putting OpenCV on AWS compute anyway (step 3), so running it on Graviton with COOL is a
small delta and we already work in measurements. Skip it the moment it competes with step 5 or 7.

---

## Deliverables that gate the video

- **Architecture diagram** — OpenCV 5 and AWS components, matching the code after steps 2–3. The
  README has tables; the rules ask for a diagram. The video has to show it.
- **Technical report** in their shape: problem · users · architecture · OpenCV 5 implementation ·
  AWS deployment · evaluation · responsible use. The README covers roughly 70% and has no users
  section and no evaluation.
- **Build, deploy and test instructions with pinned dependencies** — verified from a clean clone.

## Video beats → what each one needs

| beat | needs |
|---|---|
| the problem: red on red, 1.13× against 1.5× | nothing — archived and true today |
| the loop running on a real recording | step 2 (OpenCV 5 computing it live) |
| Ethel's failed gate changing the agent's next action | **step 0**, then step 3 (Bedrock deciding) |
| the delivered output with its numbers | step 0 |
| the other exit — a reshoot request | nothing — `&budget=0` works today |
| "a second destination is a second JSON file" | step 7 |
| architecture: OpenCV 5 + AWS | steps 2, 3, diagram |
| results and limitations | steps 5, 6 |
| team | — |

## Schedule

| week | lands |
|---|---|
| **1** — Sep 18–24 | step 0 (ground truth) · step 1 (repo, license, media decision) · step 2a (OpenCV 5 measurements in-repo) |
| **2** — Sep 25–Oct 1 | step 2b (`SubjectSegmenter`) · step 3 (S3 + Bedrock DECIDE) · `?demo=0` works |
| **3** — Oct 2–8 | step 4 (endpoint deployed) · step 5 (evaluation set and table) · step 6 (baseline, ablation) |
| **4** — Oct 9–15 | step 7 (second profile) · step 8 (responsible use, observability, control) · diagram · report |
| **5** — Oct 16–22 | **video** — script, shoot, cut · dry-run the screen-share · P2 only if free |
| buffer | Oct 23–26 — submission, re-checks, nothing new |

## Risks and decision points

1. **Ethel's gate does not clear honestly** (step 0). Settle in week 1; the video script depends on it.
2. **Recomputed OpenCV 5 numbers disagree with the archive** (step 2). Then the fixtures change and
   the README's tables change — which is why this is week 1, not week 4.
3. **Media rights** (step 1). If we cannot ship performer footage in a public repo, decide early
   between a private judge-accessible archive and substitute footage; the endpoint needs playable
   media either way.
4. **The agent does not beat the rule table** (step 6). Acceptable, if we say so and show the class of
   case where it does. Not acceptable to leave untested.
5. **AWS scope creep.** Meaningful beats impressive. S3 + one compute job + Bedrock, working and
   observable, scores better than a half-finished platform.

## Explicitly out of scope until after the video

Full live wiring of every stage, multi-tenant anything, a queue, auth, a second cloud, and any
capability the screen does not show. The README's rule stands: nothing is built that the demo does
not show.
