# Judge guide

Stage Ready — OpenCV AI Competition 2026, powered by AWS.

| Submission item | Where to find it |
| --- | --- |
| Code | [michi883/stage-ready](https://github.com/michi883/stage-ready) |
| Working web endpoint | [Stage Ready](https://d4nh99blf9f5j.cloudfront.net/) |
| Demo video | [Stage Ready Demo — 1:56](https://www.youtube.com/watch?v=3vW55n17LIw) |
| Technical report | [Problem, users, implementation, architecture, evaluation, limitations](../TECHNICAL_REPORT.md) |
| Architecture | [As-built diagram](architecture.svg) |
| Build and test | [Quick start](../README.md#install-build-and-test), [reproduction guide](REPRODUCING.md) |
| Deployment | [AWS instructions](DEPLOYMENT.md) |
| Evaluation evidence | [19-case report](../demo/eval/EVALUATION.md), [raw results](../demo/eval/results/), [live AWS traces](../demo/eval/live/) |
| Dependencies | [Exact version pins](../requirements/), [model hashes](../stage_ready/vision/segment.py) |

Requirements checked against the [competition overview](https://opencv26.devpost.com/) and
[rules](https://opencv26.devpost.com/rules) on October 7, 2026. The overview requires substantive
OpenCV 5 use, a meaningful AWS component, a technical report, reproducible instructions,
architecture, evaluation evidence, a working endpoint or live demonstration, and a video of
no more than five minutes showing the team, application, architecture, and principal results.

## Three-minute review

1. Watch the linked video, then open the hosted demo and select the sample cases.
2. Run Ethel. The first output fails separation (1.13× against 1.50×). The next decision selects
   `process.separation_targeted`, reuses the matte/track, and the second output passes at 1.52×.
   Open **Trace** to inspect the measurements and decisions.
3. Run Brian for controlled padding repair, Zach for first-pass success, and
   [Sandy](https://d4nh99blf9f5j.cloudfront.net/?demo=1&clip=sandy) for the reshoot exit.
4. Read the evaluation's failure cases. Both agents score 17/19 and miss frozen-frame corruption;
   those limits remain present in the submitted implementation.

The default page replays measured runs. `?demo=0` requests fresh Lambda measurements and
Bedrock decisions against prepared, cached recordings. That mode makes billable AWS calls;
the cache-backed render remains distinct from live measurement.

## Agentic Vision evidence

The [architecture diagram](architecture.svg) shows INSPECT → DECIDE → FIX/PROCESS → VERIFY,
with failed verification returning to DECIDE and bounded exits to delivery or reshoot.
In [Ethel's live trace](../demo/eval/live/ethel_20260920T015147.jsonl), OpenCV output changes a
later strategy/tool call. The code in [loop.py](../stage_ready/loop.py) requires verification,
rejects disallowed actions, and enforces the profile's budget independently of the model.

The [evaluation](../demo/eval/EVALUATION.md) compares Bedrock decisions to a rules baseline.
There is no demonstrated outcome-accuracy gain over that baseline on this small corpus.
The entry does not use COOL and should not claim the COOL award.

## Responsible use

The application measures technical quality for consented performance recordings. It does not
identify people or assess their talent, health, personality, or emotions. Input filenames/briefs
and numeric findings can reach Bedrock in live demo mode; evaluation prompts omit identifying
briefs/names to reduce label leakage. Video bytes remain in local processing/S3 and are not sent
as Bedrock model input. The browser sends a fingerprint and filename for recognition, not a new
video upload. Unknown recordings are reported as unsupported.

Media is excluded from Git and from distribution archives. The existing project documents
permission for judge review, not blanket public redistribution. Keep the private bundle restricted
to judges and confirm permission for footage depicted in the hosted endpoint and video. The MIT
license applies to code, not performer media or third-party model weights.

S3 blocks public bucket access; CloudFront can serve the designated `public/` prefix. Lambda URLs
use IAM authorization through CloudFront. The public app itself has no user login, so live access
can incur costs. The existing deployment is a competition demonstration, not a multi-tenant
production service. Operators control credentials, model choice, deployment, and shutdown.
Human review is needed for defects outside the nine gates, including frozen frames.

## Owner's final Devpost steps

- Enter the repository, video, and endpoint URLs above in Devpost and attach/link the technical
  report and diagram as requested.
- Supply team identity and confirm the final video shows the team, architecture, and principal
  results. Its accessibility and 1:56 duration were verified; these content requirements still
  need the team's final review.
- Provide the private judge bundle through a judge-accessible restricted link or arrange a
  live demonstration for measurement reproduction. There is no public bundle download in this
  repository. The full local test suite passed with archive access during submission preparation.
- Check the endpoint and judge access again before submitting. Do not include AWS credentials,
  deployment state, model weights, or performer videos in the GitHub upload.

These are submission/account and media-access steps; this repository does not automatically
submit a Devpost entry or create media-sharing permissions.
