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

The three sample recordings are the show's lineup, in billing order — and three different agent
behaviours, each the path the recording's own measurements produce, through the same profile with
no per-recording settings (see [Performers and numbers](#performers-and-numbers)):

| | **Sandy Hackett** — fix what can be fixed, then catch what cannot | **Ethel Chadwick** — adapt and recover | **Zach Sain** — stop when processing cannot honestly satisfy the profile |
|---|---|---|---|
| What came in | a 3:2 picture pillarboxed inside 16:9, 25 fps; walks into a close-up 4.5 s in | recorded to spec — in a red trouser suit, for a red curtain | a 480 × 412 picture, 30 fps; a black shirt against a red wall, the crown tight to the top |
| Inspect finds | picture area smaller than the file; shoulder span over the 55 % cap; a warning — apparent size changes 1.75× across the take | nothing outside the profile (one low-confidence note: wardrobe close to the plate) | nothing outside the profile's gates; two warnings — the crown leaves the picture on 78 % of frames, and the room is over-lit (face ×0.37 wanted, clamped at ×0.80) |
| Agent decides | **fix**: crop to the measured picture, size-capped reframe → re-inspect → process | process | process |
| Verify | **fail** — head height moves 2.9 % of the output (2 % allowed) and drifts 5.3 px (4 allowed); matte 98 %, separation 1.72×, frames and audio pass | **fail** — separation 1.13× against 1.5×; every other gate passes | **fail** — separation **1.00×**: inside 0.116, outside 0.116, the shirt and the curtain are the same luminance; every other gate passes (matte 101 %, head held to 0.6 %, crown completed from his own frames) |
| Agent decides | **reshoot**: no allowed strategy moves where he stood; the cause is the walk-in INSPECT warned about → *be at your final distance before the take starts* | **change strategy**: separation-targeted composite, matte and tracking reused → reprocess | **change strategy**: the same separation-targeted composite → reprocess |
| Verify | — | pass — 1.52×, with the grade at its bounds | **fail** — 1.45×, with the grade at its bounds: the retry moved the edge 0.116 → 0.173 and is still short |
| Agent decides | — | deliver | **reshoot**: the strategy has nowhere further to go; a second retry would be the same knobs at the same bounds → *don't wear the stage* |
| On screen | Framing needs adjustment → Reframe → **Fails ✗** → Ask for a reshoot | Already suitable → Standard process → **Fails ✗** ⟲ Try safer processing → Reprocess → Verified ✓ | Already suitable → Standard process → **Fails ✗** ⟲ Try safer processing → Reprocess → **Fails ✗** → Ask for a reshoot |

The session view and the Details table stamp each recording with what the agent did, by one rule
(`verdict()` in `web/app.js`): **FIXED · CAUGHT** (a fix that held, then a gate the fix could not
touch), **ADAPTED · RECOVERED** (a failed gate, a changed strategy, a verified second attempt),
**TRIED · STOPPED** (a retry measured and still short — the loop stops rather than deliver).
Nothing is labelled a success that was not measured as one.

**Watch Ethel's.** The Verify cell turns red, the first output is stamped ✗ and thrown behind, a
retry arc draws back to Decide, the agent explains why in one sentence and changes strategy, and
the second attempt earns the ✓ — by 0.02×, with every knob of the strategy at its bound. In the Red
Curtain script that failure was a warning in a log; in the profile it is a gate, and the gate
changed the agent's next action. Had the second strategy not cleared it inside those bounds, the
exit would have been the reshoot request — `&budget=0` shows that path for her.

**And watch Zach's**, because it is Ethel's story with the other ending. The same gate fails, the
agent reaches for the same strategy, the retry is rendered and measured — and it comes back at
1.45× against 1.5. Every knob of the strategy is at its bound; a second retry would be the same
grade again. The loop does not spend it. It stops, says why in one sentence, and asks for the one
thing that would fix it: a shirt that is not the colour of the stage. The difference between Ethel
and Zach is 0.07× at the edge, and the loop lands on the right side of it both times because it
measured, not because it hoped.

**And watch Sandy's.** The fix does exactly what it promises — the padding is cropped, the size cap
holds his shoulders at 55 % — and the render still fails, on a gate the fix could never address:
with his crown completed from his own frames, the head the solve is holding is a real crown that
walks toward the lens. The agent does not retry a grade change against a framing defect; it names
the cause INSPECT already warned about and asks for the one thing that fixes it, at capture. The
same gate passed on the archive's earlier render, when the cut crown pinned the head top to the
picture edge — which is the argument for measuring the delivery, not the log.

**The payoff**, in the session view:

```
3 inconsistent raw recordings  ─▶  3 different agent behaviours  ─▶  1 delivery, 2 reshoot requests
   padded+walk-in / red-on-red /      fix → catch  /  adapt → recover  /   each with the number behind it — the delivery verified
   black-on-red, small picture         try → stop                          against every gate, the requests naming the capture change
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
- **The numbers are real, and each recording's own.** Sandy's, Ethel's and Zach's measurements
  are their own archived runs — Zach's inspect and verify fixtures written from the live OpenCV 5
  measurement by `python3 -m stage_ready record zach`, his retry rendered and measured on
  2026-09-19. No fixture borrows another clip's numbers; a test checks.
- **Every number is measured.** The last projected one — Ethel's second attempt — was measured on
  2026-09-19: the separation-targeted grade clears the gate at **1.52×**, and only with every knob
  at its bound. The earlier projection (1.58× at softer settings) measured 1.43× and was wrong; the
  fixture's `provenance` says so. Sandy's run is the archive's v4 render, and it fails — see
  [What is measured](#what-is-measured). Zach's retry is 1.45× — short by 0.05×, and the loop stops.
  A fixture that were projected would say so and the UI would tag it *projected*; none is, and a
  test keeps it that way.
- **INSPECT and VERIFY run live, with OpenCV 5, on AWS.** `stage_ready/vision/` ports the Red
  Curtain measurements (picture area, pose QC, the dry framing solve, crown, exposure and key,
  matte extent, separation, head spread and drift, frame count, audio MD5), and
  `python3 -m stage_ready measure` recomputes every fixture number from the archived files and
  prints the two side by side — the three clips agree ([What is measured](#what-is-measured)).
  `--live` / `?demo=0` is the **hybrid**: INSPECT and VERIFY on an AWS Lambda over the workdir
  mirrored from S3 by source hash, DECIDE on Amazon Bedrock, the rendering on the laptop and
  cached by source hash ([The live hybrid on AWS](#the-live-hybrid-on-aws)). Ethel completed a
  real run on 2026-09-19: three Bedrock decisions, two AWS verifications, delivered on the 1.52×
  pass. The fixer (Sandy's reframe) is still `LiveNotWired`; producing a workdir for a fresh
  upload is milestone 9.
- **OpenCV 5 DNN segmentation is live for the seed and the matte's second opinion**, measured
  against the archive's Apple Vision opinions on all three clips (`segcheck`); not used for the
  separation edge, where it measured up to 0.14× off — see [Why OpenCV 5](#why-opencv-5).

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

### The live hybrid on AWS

The minimal shape, built and run on 2026-09-19 (`stage_ready/aws.py`, `stage_ready/lambda_handler.py`):

| | where | what |
|---|---|---|
| **S3** `stage-ready-videos` (us-east-1, public access blocked) | AWS | every prefix is the source's SHA-256 — the matte cache's key: `sources/<sha>/source.<ext>` · `work/<sha>/…` (the workdir in the archive's own layout: pose, matte, mt, seed, the sampled band and composite frames, logs, params) · `artifacts/<sha>/<attempt>.mp4` · `measurements/<sha>/{inspect,verify}.*.json` · `runs/<sha>/<run_id>/trace.jsonl` · `models/u2net_human_seg.onnx` |
| **INSPECT, VERIFY** — Lambda `stage-ready-measure` | AWS | Python 3.12 on arm64, 3 GB, on the `stage-ready-opencv5` layer (opencv-python-headless 5.0.0.93, numpy 2.4.6, a static ffmpeg). Mirrors `work/<sha>/` to `/tmp`, fetches the U²-Net weights, runs `ArchiveMeasurer` exactly as on the laptop — the DNN as the `matte_extent` second opinion — and writes the record to `measurements/<sha>/`. |
| **DECIDE** — Bedrock Converse | AWS | one tool, `decide`, whose input schema is `models.DECISION_TOOL_SCHEMA`; the prompt carries the profile (gates, strategies with what they address and their bounds, retry budget, reshoot guidance), the current findings, the latest verification, the attempts so far, prior decisions and the budget. `global.anthropic.claude-sonnet-4-6` (Opus 5 and Sonnet 5 are listed for the account but not enabled). The loop's guards in `loop.py` still refuse what the profile does not allow. |
| **PROCESS** | laptop | `BodyTrack` (Apple Vision), MatAnyone (MPS) and `Composite` (CoreImage) are macOS. Attempt 1 is a cache hit on the source hash — the archived run; attempt 2 reuses the matte and tracking and re-composites at the strategy's bounds if that render is not already on disk. The delivery goes to `artifacts/<sha>/`. |
| **FIX** | — | not wired (Sandy's reframe): `LiveNotWired`. |

AWS access goes through boto3's default credential chain; nothing in this repo reads, prints, logs
or stores a credential. What is logged is the run's **trace** — every request id, latency, OpenCV
number and Bedrock decision (`.stage_ready/runs/<run_id>.jsonl` and `runs/<sha>/<run_id>/trace.jsonl`
in the bucket; the server streams it as a final `trace` event). No performer media is logged.

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
measurements. What is left is the ground truth for one number and the live wiring.

| # | milestone | status |
|---|---|---|
| 0 | **Ground truth.** Run the separation-targeted composite on Ethel's cached matte and measure it | **done 2026-09-19** — 1.52× with the grade at its bounds (`work/midtown_ethel_chadwick_v2/separation.log`); the projection of 1.58× was wrong by 0.06×, in the flattering direction |
| 1 | **Profile + inspect.** The profile as a data file; inspection emits findings against it | done — the profile is data; INSPECT is measured live with OpenCV 5 (`stage_ready/vision`, 2026-09-19) |
| 2 | **Process + verify.** Processing toward the profile, verification against its gates, the report | verification measured live with OpenCV 5 (2026-09-19); processing live pending |
| 3 | **Agent loop.** An agent choosing inspect / fix / process / verify / stop, every decision traced, the loop's guardrails around it | loop and guardrails live in `loop.py` (tested); the Bedrock agent pending |
| 4 | **Reframe fixer.** Crop to the measured picture area + size-capped reframe, re-inspected | done in the demo (Sandy — the fix holds, and the render still fails on a gate the fix cannot address); live pending |
| 5 | **Verification-driven retry.** The separation gate fails, the agent switches strategy, reprocesses, passes | done in the demo (Ethel); the pass is measured (milestone 0) |
| 6 | **The other exit.** A failed verification with no allowed strategy left ends in a reshoot request that leads with the cause | done (Sandy; `&budget=0` shows the spent-budget variant on Ethel) |
| 7 | **The screen.** One recording at a time, the session view, Trace and Details | done |
| 8 | **OpenCV 5 DNN segmentation / QC.** `SubjectSegmenter`, measured against the samples | live for the seed and the second opinion (U²-Net on `cv2.dnn`, 2026-09-19); the separation edge stays on the matte, by measurement |
| 9 | **Live wiring.** OpenCV inspection and verification on AWS compute, the matte cache on S3 by source hash, Bedrock for the agent | the hybrid ran on Ethel 2026-09-19: Lambda INSPECT/VERIFY, Bedrock DECIDE, S3 by source hash, the rendering on the laptop; the fixer and a fresh upload's workdir pending |

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
stage_ready/vision/segment.py       SubjectSegmenter — OpenCV 5 DNN person segmentation (U²-Net / PP-HumanSeg), the seed and
                                    the matte's second opinion; segcheck.py measures it against the archive's Vision opinions
stage_ready/measure.py              INSPECT / VERIFY records computed from a workdir's files with stage_ready.vision
stage_ready/aws.py                  S3 by source hash, the measurement Lambda (deploy/invoke), Bedrock DECIDE, the run trace
stage_ready/lambda_handler.py       the Lambda entry: mirror work/<sha>/ from S3, run ArchiveMeasurer, write measurements/
stage_ready/process_local.py        the process stage on the laptop, cached by source hash; the retry at the bounds
stage_ready/server.py               static UI, /api/recognize, SSE run stream, byte-range media
web/                                the workspace
demo/clips/{sandy,ethel,zach}/      cached fixtures, keyed the way a live cache would be; clip.json → archive names the files
demo/derive.sh, demo/derived.json   a derived evaluation-corpus input (michi_sample_v1), its exact command and hashes
stage_ready/record.py               writes a clip's inspect/verify/process fixtures from the live measurement, not by hand
tests/test_demo.py                  20 tests: the three behaviours, determinism, recognition, the guardrails, no projected fixture
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
.venv/bin/python -m stage_ready run ethel --live               # measured INSPECT, then stops at DECIDE (Bedrock not wired)
.venv/bin/python -m unittest discover -s tests                 # 25 tests
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
| Sandy Hackett | `sandy_hackett_v2.mp4` frame 716 — chosen from the 24 % of frames where the crown is inside the picture, after the walk-in | `sandy_hackett_v2_red_v4.mp4` frame 716 — the crown-completion render, the run the workdir holds (fails head height; the still is the render the reshoot request is about) |
| Zach Sain | `zach_sain_v2.mov` frame 1058 (480 × 412, 180° display matrix — the browser honours it; `stills/source.mp4` is a stream-copied remux, registered under its own hash) | attempt 1: `zach_sain_v2_v2.mp4` — the crown-completion render, 1.00×; attempt 2: `zach_sain_v2_v3.mp4` — the separation-targeted grade at its bounds, 1.45× |
| Ethel Chadwick | `ethel_chadwick_v2.mp4` frame 900 | attempt 1: `ethel_chadwick_v2_v1.mp4` frame 900; attempt 2: `ethel_chadwick_v2_v3.mp4` frame 900 — the separation-targeted render, measured 1.52× (`ethel_chadwick_v2_v2.mp4` is the intermediate shadow-lift-only render, 1.37×) |

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

The visible demo is the lineup of [midtownshow.com/2040](https://midtownshow.com/2040) — Sandy
Hackett, Ethel Chadwick, Zach Sain — the recordings we have the right to show, and every one of
them carries **its own** measurements; a test forbids a fixture that borrows another clip's numbers.
All three are archived recordings, untouched: Sandy's (`sandy_hackett_v2`, run `_red_v4`), Ethel's
(`ethel_chadwick_v2`, runs `_v1` and `_v3`) and Zach's (`zach_sain_v2`, runs `_v2` and `_v3`).

**Zach's own numbers, and what they made the demo say.** An earlier version of this demo showed
Zach's footage over the reference clip's measurements, labelled as such, because his own recording
was known not to clear the profile. Measured with the live OpenCV 5 measurer, that is exactly the
story worth telling: every INSPECT gate passes (two warnings — the crown leaves the 480 × 412
picture on 78 % of frames and is completed from his own uncut frames; the room is over-lit), the
delivery fails separation at **1.00×** — the black shirt is the curtain's luminance — the agent
reaches for the same strategy that recovered Ethel, the retry is rendered at the strategy's bounds
and measures **1.45×**, still short, and the loop stops. No threshold moved, nothing about him was
altered to make a pass; his run is the third behaviour, not a substitute for someone else's first.

**Not in the lineup: a fourth, derived recording.** `demo/derive.sh` cuts a 45 s, 30 fps input from
a club recording of the author (`michi_sample_v1.mp4`; exact command, ffmpeg version and hashes in
`demo/derived.json`) and it was run through the pipeline and measured: every gate passes, with
separation 1.51× — by 0.01×, the shirt darker than the curtain. It is kept in the evaluation corpus
as the near-threshold pass; it is not in the polished demo, whose three recordings are the show's.

### What is measured

Every number for Sandy's recording and Ethel's first attempt is an archived measurement from the
Red Curtain pipeline (`sandy_hackett_v2`, `ethel_chadwick_v2`), re-derived from the workdirs on
2026-09-10 where the doc did not record it. **Zach's numbers were measured on 2026-09-19** on his
own archived run (`work/midtown_zach_sain_v2`, the crown-completion render of 2026-09-11): his
inspect and verify fixtures are written from `stage_ready.measure` by `python3 -m stage_ready
record zach`, and his second attempt — the separation-targeted grade at its bounds — was rendered
in full (`zach_sain_v2_v3.mp4`, 2116 frames, audio MD5 equal to the source) and measured at
**1.45×** (0.173 / 0.119; `work/midtown_zach_sain_v2/separation.log`), from **1.00×** (0.116 /
0.116). **Ethel's second attempt was measured on 2026-09-19** on the cached matte and tracking, with
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
