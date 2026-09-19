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
| Verification gates (8) | pose on ≥ 60 % of frames; one subject on ≥ 95 %; segmentation extent ≥ 90 % of an independent opinion; subject-vs-background luminance separation ≥ 1.5×; head-height spread and drift in tolerance; frame count and audio MD5 equal to the source |
| Allowed strategies (3) | crop + size-capped reframe (a fix) · standard composite · separation-targeted composite — in cost order, each with its bounds, and a retry budget of 2 |
| Reshoot guidance | the capture rule behind each gate, from the show's `RECORDING_REQUIREMENTS.md` |

A second profile — another show's plate, a 16:9 talking head, a clean-up-only delivery — changes
this table and nothing in the loop. Thresholds inform the agent; they do not replace it.

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
- **General-purpose by design.** The profile is the product surface; the loop is the engine. A
  second destination is a second JSON file.
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
- **Honest by construction** — a fixer may reframe, regrade, clean or reprocess recorded content;
  it never invents content that was not captured.
- **No per-recording tuning** — the samples run with the profile alone.
- **General-purpose** — a second profile changes the data, not the loop.

## See it in two minutes

```bash
python3 -m stage_ready serve            # standard library only, no installs
open "http://127.0.0.1:8765/?demo=1"
```

A workspace, one recording at a time:

1. **Drop a recording.** The Target Output Profile is preselected: *Midtown Show · Red Curtain*.
   The browser fingerprints the file (SHA-256 — the same key the live matte cache uses) and the
   server checks for a cached run. The file never leaves the machine. No file at hand? *or try a
   sample recording.*
2. **Make Stage Ready.** The source plays large on the left; one flow runs underneath —
   `INSPECT → DECIDE → PROCESS → VERIFY` — one phrase per step, one sentence of narration in the
   agent's own words, and the output arriving on the right.
3. **Source and output, side by side**, playing from the same moment, with the path as chips —
   *Framing needs adjustment → Reframe → Verified ✓* — then **Add another recording** or
   **View processed recordings (n)**: every recording so far, source over output, from the first one
   on. It never opens by itself.

The three sample recordings are the show's current lineup, in billing order. Each was recorded to
exhibit exactly one thing, and each takes a different path through the same loop with the same
profile and no per-recording settings:

| | **Sandy Hackett** — misframed, complete | **Ethel Chadwick** — wearing the stage | **Zach Sain** — already suitable |
|---|---|---|---|
| What came in | a 3:2 picture pillarboxed inside 16:9, 25 fps; walks into a close-up 4.5 s in | recorded to spec — in a red trouser suit, for a red curtain | to spec: one subject, steady, framed to the rule |
| Inspect finds | picture area smaller than the file; shoulder span over the 55 % cap | nothing outside the profile (one low-confidence note: wardrobe close to the plate) | nothing outside the profile |
| Agent decides | **fix**: crop to the measured picture, size-capped reframe → re-inspect → process | process | process |
| Verify | pass — separation 1.79×, head height held to 1.2 % | **fail** — separation 1.13× against 1.5×; every other gate passes | pass — separation 2.96× |
| Agent decides | deliver | **change strategy**: separation-targeted composite, matte and tracking reused → reprocess | deliver |
| Verify | — | pass — 1.52×, with the grade at its bounds | — |
| On screen | Framing needs adjustment → Reframe → Verified ✓ | Already suitable → Standard process → **Fails ✗** ⟲ Try safer processing → Reprocess → Verified ✓ | Already suitable → Standard process → Verified ✓ |

**Watch Ethel's.** The Verify cell turns red, the first output is stamped ✗ and thrown behind, a
retry arc draws back to Decide, the agent explains why in one sentence and changes strategy, and
the second attempt earns the ✓ — by 0.02×, with every knob of the strategy at its bound. In the Red
Curtain script that failure was a warning in a log; in the profile it is a gate, and the gate
changed the agent's next action. Had the second strategy not cleared it inside those bounds, the
exit would have been the reshoot request — `&budget=0` shows that path.

**The payoff**, in the session view:

```
3 inconsistent raw recordings  ─▶  3 different decision paths  ─▶  3 consistent Red Curtain outputs
   padded / red-on-red / to spec       1 fix / 1 retry / 1 step       same head height, same size,
                                                                       same look, each with its number
```

**Trace** (per recording) opens the full record — every finding, every decision with its reasoning
and citations, every stage with what it costs live, every gate — and, under Ethel's delivery, the
two attempts in luminance only with their two separation numbers. **Details** holds the delivered
numbers side by side and where each one comes from. Both stay closed until asked.

## What is real today, and what is not

Judges should know exactly what they are looking at:

- **The demo is fully cached and deterministic** — no model calls, no OpenCV, no AWS at demo time.
  Every measurement is replayed from `demo/clips/<id>/*.json`, and every fixture carries a
  `provenance` line naming the archived run and file it was measured from. A dropped file is
  recognised by fingerprint and its cached run replayed; an unknown file is told so, not guessed at.
- **The numbers are real.** Sandy's and Ethel's measurements are their own archived runs. Zach's
  footage is shown over the reference clip's measurements — his own recording (480 × 412, black on
  red, 1.05×) would honestly end as a reshoot request; the fixture, the Trace and
  [Performers and numbers](#performers-and-numbers) all say so.
- **Every number is measured.** The last projected one — Ethel's second attempt — was measured on
  2026-09-19: the separation-targeted grade clears the gate at **1.52×**, and only with every knob
  at its bound. The earlier projection (1.58× at softer settings) measured 1.43× and was wrong; the
  fixture's `provenance` says so. A fixture that were projected would say so and the UI would tag
  it *projected*; none is, and a test keeps it that way.
- **INSPECT and VERIFY run live, with OpenCV 5, in this repo.** `stage_ready/vision/` ports the
  Red Curtain measurements (picture area, pose QC, the dry framing solve, crown, exposure and key,
  matte extent, separation, head spread and drift, frame count, audio MD5), and
  `python3 -m stage_ready measure` recomputes every fixture number from the archived files and
  prints the two side by side — Ethel's and the reference clip's agree to the digit
  ([What is measured](#what-is-measured)). `--live` / `?demo=0` runs a measured INSPECT and stops
  at DECIDE: the agent (Bedrock), the fixers and the processors are still the shape of the real
  thing and raise `LiveNotWired`. A live run needs the archive's workdirs (`$STAGE_READY_ARCHIVE`,
  default `~/mts`) — producing a workdir for a fresh upload is milestone 9.
- **OpenCV 5 DNN segmentation is planned, not implemented** — see below.

## Under the hood

### Architecture

| layer | responsibility | where |
|---|---|---|
| **Profile** | the target as data: canvas, background, framing rule, look, gates, allowed strategies, retry budget, reshoot corpus | `profiles/midtown_red_curtain.json` |
| **Inspection (OpenCV 5)** | picture area, framing, subject presence and continuity, size and position stability, crop risk, exposure, key direction | live: `stage_ready/vision/` via `stage_ready/measure.py`; demo: `inspect.*.json` |
| **Findings** | typed records — id, measurement, threshold from the profile, confidence, affected frames, tool | `stage_ready/models.py` |
| **Agent** | reads findings, history and the profile; chooses the next action; judges whether a fix held | live: Amazon Bedrock; demo: `decide.*.json` |
| **Fixers / processors** | small, one-sided, composable; each declares what it addresses and what it costs | `fix.*.json`, `process.*.json` |
| **Verification (OpenCV 5)** | re-inspects the result against the profile's gates and diffs it against the pre-fix findings | live: `stage_ready/vision/` via `stage_ready/measure.py`; demo: `verify.*.json` |
| **Loop** | inspect → decide → fix \| process → verify → deliver \| reshoot, with the guarantees above; a generator of plain events | `stage_ready/loop.py` |
| **Backends** | `cached` (the demo) and `live` (measured INSPECT/VERIFY; the rest the shape) behind one interface; the loop never learns which it has | `stage_ready/backends/` |
| **Reporter** | decision trace, delivery report with its numbers, reshoot guidance in capture terms | Trace / Details in `web/` |
| **Server** | static UI, `/api/recognize`, the run as server-sent events, byte-range media | `stage_ready/server.py` |

**Minimal AWS shape:** Amazon S3 for sources, intermediates and deliveries (the matte cached by
source SHA-256); AWS compute for OpenCV inspection, verification and fixer jobs; Amazon Bedrock for
the agent (Converse API, tool schema = `models.Decision`). AWS access goes through boto3's default
credential chain; nothing in this repo reads, prints or stores a credential.

`CachedBackend` answers each call from a file keyed on what a live run would cache on, so a hybrid
— cached matte, live agent — is the same interface with a different mix behind it:

| call | fixture | live equivalent |
|---|---|---|
| `recognize(sha256)` | `clip.json` → `recognize` | S3 HEAD by source SHA-256 — is the matte for this source already cached? |
| `inspect(target)` | `inspect.<target>.json` | **live:** `vision.detect_band`, `BodyTrack` + `vision.pose_qc`, `vision.track.dry_solve`, `vision.crown_cut`, `vision.grade_qc` |
| `decide(n)` | `decide.<n>.json` | Amazon Bedrock |
| `fix(strategy)` | `fix.<strategy>.json` | `track_frame.py` with `SIZE_CAP`, crop to the measured band |
| `process(strategy)` | `process.<strategy>.json` | seed → matte (≈12 min, cached by source SHA-256) → track → warp → grade → composite → encode |
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
against the fixture it was archived in. Two things the pipeline still borrows from the laptop are
person segmentation (Apple Vision, Swift — the pose track and the matte's second opinion) and the
video matte (MatAnyone on local MPS) — the parts that cannot follow the loop onto AWS.

**First OpenCV 5 capability to wire: DNN-based subject segmentation and QC — PLANNED, not live.**
An OpenCV 5 `cv2.dnn` person-segmentation model gives the loop a subject mask that runs anywhere
OpenCV runs, and it slots into three places the fixtures already name:

| where | today | with OpenCV 5 DNN |
|---|---|---|
| seed for the video matte | Apple Vision `PersonMatte` + `pick_seed.py` / `clean_seed.py` | `SubjectSegmenter.segment(frame)` |
| `matte_extent` gate — the independent second opinion | Apple Vision head width in `matte_qc.py` | `SubjectSegmenter.matte_extent(matte, mask)` |
| `separation` gate — the subject/background edge | matte edge in `silhouette_qc.py` | `SubjectSegmenter.edge_separation(composite, mask)` |

The seam is `stage_ready/backends/live.py::SubjectSegmenter`. **Nothing there calls OpenCV yet** —
every method raises `LiveNotWired`, the demo does not import it, and the UI's Details panel labels
it *planned*. It becomes live only once it is measured against the archived clips and shown to
agree with the current second opinion on all three samples. Until then, no claim.

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

**Portability.** The OpenCV scripts port as they are. `BodyTrack`, `PersonMatte` and `Composite`
are Apple Vision / Swift and MatAnyone runs on local MPS: local workers for the demo, replaced by
OpenCV-native equivalents when the loop moves off the laptop.

**Lessons that carry:** measure, never assume · check the right thing · a second opinion beats
self-consistency · measure the subject against the background · cheap checks before expensive work
· clamp and warn, don't rescue · fix, then re-inspect · missing pixels are missing.

**Not Stage Ready's own:** the plate, the neon sign, the comedy framing, the fixed canvas. They
live in the Red Curtain profile.

## Roadmap

Each milestone advances the demo; nothing is built that the screen does not show. The loop, the
profile, the three paths, the other exit and the workspace exist today, replayed from cached
measurements. What is left is the ground truth for one number and the live wiring.

| # | milestone | status |
|---|---|---|
| 0 | **Ground truth.** Run the separation-targeted composite on Ethel's cached matte and measure it | **done 2026-09-19** — 1.52× with the grade at its bounds (`work/midtown_ethel_chadwick_v2/separation.log`); the projection of 1.58× was wrong by 0.06×, in the flattering direction |
| 1 | **Profile + inspect.** The profile as a data file; inspection emits findings against it | done — the profile is data; INSPECT is measured live with OpenCV 5 (`stage_ready/vision`, 2026-09-19) |
| 2 | **Process + verify.** Processing toward the profile, verification against its gates, the report | verification measured live with OpenCV 5 (2026-09-19); processing live pending |
| 3 | **Agent loop.** An agent choosing inspect / fix / process / verify / stop, every decision traced, the loop's guardrails around it | loop and guardrails live in `loop.py` (tested); the Bedrock agent pending |
| 4 | **Reframe fixer.** Crop to the measured picture area + size-capped reframe, re-inspected | done in the demo (Sandy); live pending |
| 5 | **Verification-driven retry.** The separation gate fails, the agent switches strategy, reprocesses, passes | done in the demo (Ethel); the pass is measured (milestone 0) |
| 6 | **The other exit.** A spent retry budget ends in a reshoot request with capture guidance | done (`&budget=0`) |
| 7 | **The screen.** One recording at a time, the session view, Trace and Details | done |
| 8 | **OpenCV 5 DNN segmentation / QC.** `SubjectSegmenter`, measured against the samples | planned — the first live OpenCV 5 capability |
| 9 | **Live wiring.** OpenCV inspection and verification on AWS compute, the matte cache on S3 by source hash, Bedrock for the agent | inspection and verification run live from a workdir; Bedrock, S3 and the processors pending — a hybrid (archived matte, live agent) is the next step |

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
stage_ready/backends/live.py        live backend: INSPECT and VERIFY measured (OpenCV 5); S3, Bedrock, fixers and
                                    processors are the shape, not wired; the planned OpenCV 5 DNN seam (SubjectSegmenter)
stage_ready/vision/                 OpenCV 5 measurements: band, pose, track (dry solve, head height), matte, silhouette,
                                    grade, media — the Red Curtain scripts, ported to the digit
stage_ready/measure.py              INSPECT / VERIFY records computed from a workdir's files with stage_ready.vision
stage_ready/server.py               static UI, /api/recognize, SSE run stream, byte-range media
web/                                the workspace
demo/clips/{sandy,ethel,zach}/      cached fixtures, keyed the way a live cache would be; clip.json → archive names the files
tests/test_demo.py                  18 tests: the three paths, determinism, recognition, the guardrails, no projected fixture
tests/test_vision.py                4 tests: OpenCV 5 reproduces the archived numbers (skipped without OpenCV 5 + the archive)
```

```bash
python3 -m stage_ready run              # the same three runs, as text
python3 -m stage_ready trace ethel      # one run, as JSON lines
python3 -m unittest discover -s tests   # 18 tests, standard library

python3 -m venv .venv && .venv/bin/pip install -e '.[live]'    # OpenCV 5 + numpy, pinned
.venv/bin/python -m stage_ready measure                        # every fixture number, recomputed with OpenCV 5
.venv/bin/python -m stage_ready run ethel --live               # measured INSPECT, then stops at DECIDE (Bedrock not wired)
.venv/bin/python -m unittest discover -s tests                 # 22 tests
```

`measure` and `--live` read the Red Curtain archive's workdirs — `--archive <dir>` or
`$STAGE_READY_ARCHIVE`, default `~/mts`; without it they say so and the demo is unaffected.

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
| Sandy Hackett | `sandy_hackett_v2.mp4` frame 716 — chosen from the 24 % of frames where the crown is inside the picture, after the walk-in | `sandy_hackett_v2_red_v3_full.mp4` frame 716 |
| Ethel Chadwick | `ethel_chadwick_v2.mp4` frame 900 | attempt 1: `ethel_chadwick_v2_v1.mp4` frame 900; attempt 2: `ethel_chadwick_v2_v3.mp4` frame 900 — the separation-targeted render, measured 1.52× (`ethel_chadwick_v2_v2.mp4` is the intermediate shadow-lift-only render, 1.37×) |
| Zach Sain | `zach_sain_v2.mov` (480 × 412, 180° display matrix — the browser honours it; `stills/source.mp4` is a stream-copied remux, registered under its own hash) | `zach_sain_v2_v2.mp4` — the archived crown-completion render |

The stills directory is git-ignored (performer footage).

### Performers and numbers

The visible demo is the lineup of [midtownshow.com/2040](https://midtownshow.com/2040) — Sandy
Hackett, Ethel Chadwick, Zach Sain — because those are the recordings we have the right to show.
Sandy's and Ethel's measurements are their own archived runs, and their paths follow from them.

**Zach's is not.** His archived run (`work/midtown_zach_sain_v2`) is a 480 × 412 picture with the
crown cut on 78 % of frames, a face held at the exposure clamp, and a black shirt separating from
the curtain by **1.05×** — under this profile's 1.5× gate, further under it than Ethel's 1.13×, with
no allowed strategy that could close the gap. Run honestly, his recording would end as a reshoot
request. So the "already suitable" path shows **Zach's footage over the reference clip's
measurements** — `brian_shirley_v2`, the one archived recording that genuinely was already suitable
(1080p, headroom, steady, 2.96×). The fixture's `fixture` and `provenance` fields say so, the
Trace's source card says so under *measured on*, and this section says so. Nothing in the Trace is
a number that was not measured. A to-spec recording of Zach replaces Brian's numbers and ends the
substitution; `zach/stills/brian_*.jpg` keep the reference clip's own frames, unwired.

### What is measured

Every number for Sandy's and Zach's recordings, and Ethel's first attempt, is an archived
measurement from the Red Curtain pipeline (`sandy_hackett_v2`, `brian_shirley_v2` — see above —
and `ethel_chadwick_v2`), re-derived from the workdirs on 2026-09-10 where the doc did not record
it. **Ethel's second attempt was measured on 2026-09-19** on the cached matte and tracking, with
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
head spread 1.3 % / 0.7 %, matte extent, frame counts, audio). Four fixture entries were corrected
from the re-run, none changing a status: Ethel's key direction (×0.80, from the left — not
flat-lit), her head drift (3.1 px, measured; the fixture had carried an unmeasured 1.5), Sandy's
steadiness (1.75×, as `pose_qc.py` reports it), and face exposure recorded as the gain the grade
applies in all three clips. **One disagreement is open and written down here rather than papered
over:** Sandy's fixture and the video the demo plays are the archive's v3 run
(`sandy_hackett_v2_red_v3_full.mp4`, head spread 1.2 %), but his workdir now holds the v4 run — the
crown completion of 2026-09-11 — whose solve measures head spread **2.9 %** and drift **5.3 px**,
both over the gates. The v3 numbers were flattered by the defect the completion fixes: with his
crown cut off on 76 % of frames the head top was pinned to the picture edge and could not move.
Measured honestly, Sandy's recording fails the framing gates for the same reason it warned on
steadiness — he walks into a close-up — and that is a script decision, not a fixture edit.
