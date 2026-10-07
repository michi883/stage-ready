# Stage Ready

**OpenCV 5 measures. An agent decides. The loop verifies before delivery.**

Stage Ready checks self-recorded performer videos against a shared output profile, chooses a
bounded correction or retry, and returns a verified delivery or a specific reshoot request.
Built for the [OpenCV AI Competition 2026, powered by AWS](https://opencv26.devpost.com/),
with evidence for the Agentic Vision path.

**[Try the demo](https://d4nh99blf9f5j.cloudfront.net/)** ·
**[Watch the video (1:56)](https://www.youtube.com/watch?v=3vW55n17LIw)** ·
[Technical report](TECHNICAL_REPORT.md) · [Evaluation](demo/eval/EVALUATION.md) ·
[Judge guide](docs/SUBMISSION.md)

## Product goals and operating principles

The first users are show producers and video editors receiving inconsistent self-recorded
performances. The goal is a common, measurable delivery standard with fewer manual retries:
either all required checks pass, or the performer gets the defect, its measurement, and a
specific capture change. The current destination is Midtown Show's Red Curtain stage.

- Measure the finished output; a successful render alone is not acceptance.
- Re-inspect every correction and verify every processing attempt.
- Keep corrections within the profile's bounds, reuse expensive matte/track work, and stop
  when no allowed strategy can fix the remaining defect.
- Preserve recorded content and decoded audio; do not claim to recover pixels the camera
  never captured. Use independent segmentation evidence to check matte coverage.
- Trace the evidence behind each action and report limitations alongside successes.

## Try it locally

Python 3.11 or newer. The cached demo uses only the standard library: no AWS account, API key,
OpenCV installation, or model download is needed.

```bash
git clone https://github.com/michi883/stage-ready.git
cd stage-ready
python3 -m stage_ready serve
```

Open **http://127.0.0.1:8765/** and select **or try one of the three sample cases**.

| Recording | What to look for |
| --- | --- |
| Brian, deliberately padded | Inspection finds padding → reframe → re-inspect → verify and deliver |
| Ethel, unchanged recording | Separation fails at 1.13× → agent selects a bounded retry → passes at 1.52× |
| Zach, excerpt | First attempt passes at 2.37× |
| [Sandy, reshoot example](https://d4nh99blf9f5j.cloudfront.net/?demo=1&clip=sandy) | Insufficient crown evidence → specific capture guidance |

The local demo replays measured JSON records. Performer footage is excluded from Git; without
the private media bundle, the local UI uses illustrative stand-ins. The hosted demo includes
playback. A file dropped in the browser is fingerprinted locally and matched to known inputs;
fresh uploads do **not** yet get a new matte or render.

```bash
python3 -m stage_ready run brian_padded ethel zach sandy
python3 -m stage_ready trace ethel
python3 -m unittest discover -s tests -v
```

## Architecture and scope

![Stage Ready architecture](docs/architecture.svg)

In **live hybrid mode** (`?demo=0` on the hosted endpoint), OpenCV 5 inspection, reframe solving,
and verification run on AWS Lambda; Amazon Bedrock selects actions; S3 stores workdirs,
rendered artifacts, measurements, and traces. The loop enforces allowed strategies, retry
budgets, re-inspection after a fix, and verification before delivery.

Rendering uses the existing macOS Red Curtain pipeline (BodyTrack, MatAnyone, Composite),
with archived outputs cached by source hash on S3. That renderer is not included here and does
not run on AWS. Live hybrid mode works on prepared recordings; arbitrary new uploads remain
out of scope. The default demo is a deterministic replay, with no live model or vision calls.
This project does not claim COOL integration.

See the [claim audit](TECHNICAL_REPORT.md#claim-audit),
[OpenCV implementation](TECHNICAL_REPORT.md#why-opencv-5), and
[AWS deployment guide](docs/DEPLOYMENT.md).

## Results and limits

The committed evaluation contains **19 labelled cases: 16 loop inputs and 3 output checks**.
Both the Bedrock agent and the rules baseline match **17/19** expected outcomes. Both miss the
frozen-frame corruption case (one silently wrong delivery), and both wrongly refuse a seated
performer during pose preparation. The walk-in detector also misses one labelled defect.
These results do not establish an accuracy advantage for the language-model agent.

The [evaluation report](demo/eval/EVALUATION.md) includes per-case outcomes, failure cases,
precision/recall, and cost/latency records. [Live AWS traces](demo/eval/live/) show vision evidence
changing subsequent tool calls. The small, show-specific corpus and one output profile limit
generalization; human review is still needed for defects outside the measured gates.

## Install, build, and test

For an editable install and optional live measurement dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/build.txt
python -m pip install --no-build-isolation -e .
# Optional: OpenCV and the fully pinned AWS client
python -m pip install -r requirements/live.txt -r requirements/aws.txt
python -m pip check
python -m unittest discover -s tests -v
```

On a server/CI runner use `requirements/headless.txt` **instead of** `requirements/live.txt`;
both provide `cv2` and must not be installed together. AWS access uses boto3's default
credential chain; no credentials belong in the repository.

Build distributable archives with `python -m build --no-isolation`. The wheel includes the
profile, web UI, cached fixtures, and evaluation JSON; it excludes footage and model weights.
`stage-ready serve` and `stage-ready run ethel` also work from an installed wheel. Development,
media installation, evaluation regeneration, and AWS deployment should use a source checkout.

Tests cover loop guards, replay determinism, recognition, evaluation scoring, HTTP/SSE,
media ranges, deployment packaging, and generated-image OpenCV measurements. Private-archive
tests explicitly skip when required media/models are absent. Supplying an incomplete
`STAGE_READY_ARCHIVE` makes the archive prerequisite test fail instead of silently accepting it.
[CI](.github/workflows/ci.yml) tests the dependency-free demo, a clean wheel install, and
OpenCV 5 with synthetic input; it has no AWS credentials or private media.

For measurement against original recordings, install the private judge bundle and FFmpeg,
then follow [the reproduction guide](docs/REPRODUCING.md). The bundle contains source media,
renders, and measured intermediates; it is not a fresh-upload renderer.

## Repository map

| Path | Purpose |
| --- | --- |
| `stage_ready/loop.py` | Perception → decision → action loop and delivery guards |
| `stage_ready/vision/` | OpenCV 5 measurements and DNN segmentation |
| `stage_ready/backends/` | Cached replay and live hybrid implementations |
| `stage_ready/aws.py`, `stage_ready/deploy_web.py` | AWS storage, Bedrock, Lambda, CloudFront deployment |
| `profiles/` | Target profile, gates, permitted strategies, and retry bounds |
| `web/` | Browser workspace and trace view |
| `demo/clips/`, `demo/eval/` | Measured fixtures, evaluation records, and traces |
| `scripts/build_lambda.py` | Pinned SDK and arm64 vision-layer assembly |
| `tests/` | Automated checks |

## Delivery status and roadmap

The measured retry, OpenCV 5 implementation, DNN second opinion, AWS hybrid, hosted workspace,
19-case evaluation, rules baseline, architecture, and recorded demo are implemented. Ethel's
1.52× result is measured at the allowed bounds; it is not a projected result. The crown-evidence
rule and the shared size-cap measurement are enforced in the current code.

The next product milestones are separate from the submitted capabilities:

| Priority | Remaining work | Acceptance criterion |
| --- | --- | --- |
| 1 | Fresh-upload preparation and cloud rendering | An unseen, consented recording gets a new pose track, matte, render, and verification without a local macOS workdir |
| 2 | Access control, resource limits, and data lifecycle | Authenticated jobs have upload limits, bounded concurrency/cost, and explicit retention/deletion behavior |
| 3 | Human approval and audited overrides | An operator can approve delivery or record an override without relabelling a failed gate as a pass |
| 4 | Frozen-frame detection and broader evaluation | Corrupted motion is rejected; a larger, more varied labelled set quantifies false accepts and refusals |
| 5 | Second output profile | A measured 16:9 or cleanup-only destination works through the same loop without per-recording code changes |

Only one output profile is validated. Operator approval/override controls, multi-tenant queues,
and COOL acceleration are not implemented. The [judge guide](docs/SUBMISSION.md) lists the
remaining Devpost and restricted-media sharing steps. Build history and superseded planning
artifacts are retained in Git history rather than maintained alongside the product documentation.

## License and responsible use

Code is [MIT licensed](LICENSE). Model weights retain their upstream licenses and are downloaded
separately with SHA-256 verification; see [models/README.md](models/README.md) and
[third-party notices](THIRD_PARTY_NOTICES.md). Performer footage is not covered by the code
license and must not be committed or redistributed. This is a technical quality check for
consented recordings, not an identity, emotion, or talent assessment. See the
[responsible-use notes](docs/SUBMISSION.md#responsible-use).
