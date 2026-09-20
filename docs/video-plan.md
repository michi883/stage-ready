# Demo video — production plan (≤ 3 minutes of product, recorded from the public endpoint)

Implementation is frozen (2026-09-20). Nothing in this plan changes architecture, measurements,
thresholds, agent behaviour, fixtures or the evaluation; it is a recording of the product as built.

## Lineup on the public page (verified 2026-09-20)

| card | recording | behaviour | path |
|---|---|---|---|
| 1 · left | Brian Shirley — `brian_shirley_v2_padded.mp4` (his untouched recording, padded on purpose; labelled as a controlled input) | **FIXED · VERIFIED** — controlled repair | inspect ✗ picture area → fix.reframe → re-inspect ✓ → process → verify ✓ 2.90× → deliver |
| 2 · middle | Ethel Chadwick — `ethel_chadwick_v2.mp4` (untouched) | **ADAPTED · RECOVERED** — verification failure, strategy change, retry | inspect → process → verify ✗ 1.13× → separation-targeted → reprocess → verify ✓ 1.52× → deliver |
| 3 · right | Zach Sain — `zach_sain_v1_demo.mp4` (a trimmed excerpt of his take) | **VERIFIED · FIRST PASS** — straightforward success | inspect → process → verify ✓ 2.37× → deliver |

Three performers, three behaviours, one profile, no per-recording settings.

## URL and browser

- **URL:** `https://d4nh99blf9f5j.cloudfront.net/?demo=1` — the default mode, cached and deterministic;
  the header badge reads *demo · cached · replays measured runs · no live model calls*. Two SSE
  streams of the same clip are byte-identical; the API answers in < 0.1 s warm.
- Optional: `&cadence=650` shortens each run by ~15 % if the cut is tight (default 750 ms per beat;
  Ethel's run is ~35 s on screen at the default, Brian's ~30 s, Zach's ~20 s). `&step=1` instead
  pauses after every loop event and advances on Space — use it if the voiceover must be synced
  beat by beat; otherwise let it run.
- Browser: Chrome, one window at **1920 × 1080** (or 1440 × 900 for a 4:3-ish crop), 100 % zoom, no
  bookmarks bar, no extensions badges, dark system theme (the page is dark). Park the cursor off
  the video panes while a run plays; it shows in the capture.
- **Warm up 1–2 minutes before recording:** load the page, run one sample, *Clear session*, reload.
  This warms the API Lambda and the CloudFront cache; a cold first request can take 1–3 s.
- Nothing in the UI needs hiding for the video: every element on the bench, the session view and the
  drawers is either the loop or an honesty label (the mode badge, "sample", the provenance line,
  the cached/live chips). They are small, and they are the point; leave them.

## Click-by-click sequence (≈ 2 min 45 s of screen time)

| # | screen | action | ≈ time |
|---|---|---|---|
| 0 | drop zone | page open, cursor parked | 0:00–0:08 |
| 1 | drop zone | click **or try one of the three sample cases** → three behaviour cards appear | 0:08–0:15 |
| 2 | picker | click **FIXED · VERIFIED · controlled repair** (Brian) → the bench mounts, padded source on the left | 0:15–0:22 |
| 3 | bench | click **Make Stage Ready** → INSPECT flags the padding · DECIDE reframe · re-inspect · PROCESS · VERIFY ✓ · output arrives, badge FIXED · VERIFIED | 0:22–0:55 |
| 4 | bench | click **Add another recording** → drop zone; click **or try one of the three sample cases**; click **ADAPTED · RECOVERED · adaptive recovery** (Ethel) | 0:55–1:05 |
| 5 | bench | click **Make Stage Ready** → first attempt arrives, VERIFY turns red at 1.13×, the retry arc draws back to DECIDE, the agent's sentence, the second attempt verifies at 1.52× | 1:05–1:42 |
| 6 | bench | click **Add another recording** → picker → **VERIFIED · FIRST PASS · straightforward success** (Zach) → **Make Stage Ready** → first-pass delivery, 2.37× | 1:42–2:08 |
| 7 | bench | click **View processed recordings (3)** → the session view: three cards, three badges, source over output, the path chips | 2:08–2:25 |
| 8 | session view | click **Trace** under Recording 2 (Ethel) → the drawer; scroll two flicks to **VERIFY attempt 1 — FAIL 8 / 9 gates** (the red 1.13× ≥ 1.50× line) and **DECIDE #2** just below it | 2:25–2:40 |
| 9 | drawer | click the **Details** tab → the three columns (outcome, provenance, separation 2.90× / 1.52× / 2.37×) | 2:40–2:48 |
| 10 | drawer | **Close** → session view, end on the three badges | 2:48–2:55 |

Recover from a mis-click: **Back to workspace** (header) returns to the bench; **Clear session**
(session view, bottom right) resets everything without a reload; a reload also resets (nothing
persists).

## Voiceover — the facts to say, and what is on screen when

| beat | screen | say (the fact is measured; the number is on screen) |
|---|---|---|
| A | drop zone / picker (0:00–0:20) | **Stage Ready takes a self-recorded video and returns a verified stage-ready delivery or a specific reshoot request — never anything in between.** Three recordings, one Target Output Profile, no per-recording settings. |
| B | Brian's run, INSPECT → FIX (0:25–0:40) | **OpenCV 5 does the seeing.** It reads the picture area off the file — 1920 × 1080 inside a 2560 × 1440 export — and the agent picks the one allowed fix: crop and reframe, zero pixels invented. Every fix is re-inspected before anything is rendered. |
| C | Brian's VERIFY → badge (0:40–0:55) | **Every render is verified against nine gates by measurement** — separation, matte extent against an OpenCV 5 DNN opinion, head stability, crown evidence, frame count, audio identity — before it is delivered. 2.90×. |
| D | Ethel's red VERIFY and the retry arc (1:15–1:30) | **Verification changes the agent's next action.** The first render fails one gate — luminance separation 1.13× against 1.5 — and the agent on Amazon Bedrock changes strategy: the separation-targeted composite, matte and tracking reused, every knob bounded. |
| E | Ethel's second attempt ✓ (1:30–1:42) | The retry verifies at 1.52×, with the grade at its bounds. Had it not, the exit would have been a reshoot request — the loop refuses to deliver anything it has not measured as correct. |
| F | Zach's run (1:45–2:05) | Zach's recording is already suitable: first pass, 2.37×, two capture notes in the report. Same loop, same profile. |
| G | session view (2:08–2:25) | **Different inputs, one output standard**: three raw recordings, three agent behaviours, three deliveries the same size, the same head height, the same look — each with the number behind it. |
| H | Ethel's trace (2:25–2:48) | **Everything is traceable and measured live.** Inspection and verification run with OpenCV 5 on AWS Lambda, the agent on Bedrock, every decision with its reasoning and citations; the demo replays those measured runs. Evaluated blind on 19 labelled recordings: zero silently wrong deliveries the gates can see, and one they cannot — and the report says so. |

Seven facts, in order: (1) verified delivery or reshoot, never in between; (2) OpenCV 5 measures,
the agent decides, the loop enforces; (3) one fix, re-inspected, no pixels invented; (4) nine
gates by measurement before any delivery; (5) a failed gate changes the agent's next action; (6)
one profile, no per-recording settings, one output standard; (7) live on AWS (Lambda + Bedrock),
traced, and evaluated blind with its limitation stated.

Do not say: "runs entirely on AWS" (the render is on the laptop, cache-backed); "any show" or "any
destination" (one profile exists); "detects every defect" (frozen frames are a stated limitation);
"a new upload is rendered" (it is recognised or told it is unknown).

## Optional second take, for the reshoot exit (30 s, if the cut has room)

`https://d4nh99blf9f5j.cloudfront.net/?demo=1&clip=sandy` puts the natural failure case on the bench:
INSPECT fails three findings — the padding, the close-up, and a crown recorded on only 24 % of
frames — and the agent asks for a reshoot at its first decision, with the capture guidance for
each. Say: *when the recording does not carry enough evidence to verify, Stage Ready does not
guess — it asks for the one thing that fixes it, at capture.*
