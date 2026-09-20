"""The process stage where there is no laptop: a cache hit from S3, or an honest refusal.

The public endpoint's API runs on a Lambda with no Red Curtain archive on disk. For a source
whose run is under `work/<sha>/` and `artifacts/<sha>/` — the three sample recordings — the
process stage is a cache hit keyed on the source hash, exactly as it is on the laptop: the
matte was propagated once, the render exists, nothing is re-done. The stage summaries come from
the run's own logs, read from S3. For any other source the render needs BodyTrack, MatAnyone and
Composite, which are macOS, so the stage says so rather than pretending.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .backends.live import LiveNotWired
from .models import ProcessResult, Stage
from .profile import Profile
from .record import process_record


def _texts(aws, sha: str, names: tuple[str, ...]) -> dict[str, str]:
    from botocore.exceptions import ClientError
    out = {}
    for n in names:
        try:
            out[n] = aws.s3().get_object(Bucket=aws.bucket, Key=f"work/{sha}/{n}")["Body"].read().decode()
        except ClientError:
            out[n] = ""
    return out


def _count(aws, prefix: str) -> int:
    n, token = 0, None
    while True:
        kw = {"Bucket": aws.bucket, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        r = aws.s3().list_objects_v2(**kw)
        n += r.get("KeyCount", 0)
        if not r.get("IsTruncated"):
            return n
        token = r.get("NextContinuationToken")


def process_from_s3(aws, clip, strategy: str, profile: Profile, tmp: Path = Path("/tmp/archive")) -> ProcessResult:
    from .aws import artifact_key
    sha = clip.recognize["sha256"] if isinstance(clip.recognize["sha256"], str) else clip.recognize["sha256"][0]
    artifact = "attempt_1" if strategy == "process.standard" else "attempt_2" if strategy == "process.separation_targeted" else None
    if artifact is None:
        raise LiveNotWired(f"live backend: processor {strategy} is not wired")
    if aws.head(artifact_key(sha, artifact)) is None:
        raise LiveNotWired(f"live backend: no cached render for this source under artifacts/{sha[:12]}…/{artifact}.mp4 — "
                           f"the render (BodyTrack, MatAnyone, Composite) runs on the laptop, and this source has not been rendered")
    names = ("seed_pick.log", "track.log", "crown.log", "params.txt", "params_sep.txt", "matte.key", "seed_frame.txt")
    texts = _texts(aws, sha, names)
    wd = tmp / "work" / sha
    wd.mkdir(parents=True, exist_ok=True)
    for n, t in texts.items():
        if t:
            (wd / n).write_text(t)
    n_frames = _count(aws, f"work/{sha}/mt/")
    if strategy == "process.standard":
        rec = process_record(wd, tmp, None, profile, "attempt_1", n_frames=n_frames)
        stages = [Stage(id=s["id"], label=s["label"], tool=s.get("tool", ""), duration_ms=0, cached=True,
                        summary="cache hit, keyed on the source SHA-256" + (" + seed SHA-256" if s["id"] == "matte" else "") + " — " + s["summary"],
                        params=s.get("params", {})) for s in rec["stages"]]
        return ProcessResult(strategy=strategy, artifact="attempt_1", stages=stages, params=rec["params"], output=rec["output"], duration_ms=0, cached=True,
                             provenance=f"live: the archived run for this source, a cache hit from s3://{aws.bucket}/work/{sha[:12]}… (matte.key = source SHA-256 + seed SHA-256); "
                                        f"BodyTrack, MatAnyone and Composite run on the laptop and are not re-run for a source the cache holds")
    # the retry: the render at the bounds must already exist (comp_sep/ sampled frames + the encode)
    if _count(aws, f"work/{sha}/comp_sep/") == 0:
        raise LiveNotWired("live backend: the separation-targeted render for this source is not cached — it runs on the laptop (Composite is CoreImage)")
    strat = profile.strategy("process.separation_targeted") or {}
    b = strat.get("bounds", {})
    grade = {k: float(v) for k, v in re.findall(r"(keydx|rimdx|fgexp)=(-?[\d.]+)", texts.get("params_sep.txt", ""))}
    stages = [
        Stage(id="seed", label="Seed mask", tool="PersonMatte + pick_seed.py + clean_seed.py", reused=True, summary="Reused from attempt 1 — the seed is not what failed."),
        Stage(id="matte", label="Video matte", tool="MatAnyone 2 (local MPS)", reused=True, cached=True, summary="Reused from attempt 1 — keyed on the source SHA-256; nothing to redo."),
        Stage(id="track", label="Tracked reframe solve", tool="track_frame.py", reused=True, summary="Reused — the framing passed every gate."),
        Stage(id="warp", label="Reframe to canvas", tool="warp.py", reused=True, summary="Reused — the same canvas frames and matte."),
        Stage(id="grade", label="Separation-targeted grade", tool="Composite params (bounded override)", duration_ms=0,
              summary=f"rim → {b.get('rimamt_max', 0.45)} (the bound), light wrap → {b.get('lwamt_max', 0.7)} (the bound), shadow lift +{b.get('shadow_lift_max', 0.04)} (the bound); the curtain is untouched.",
              params={"rimamt": b.get("rimamt_max", 0.45), "lwamt": b.get("lwamt_max", 0.7), "shadow_lift": b.get("shadow_lift_max", 0.04), **grade}),
        Stage(id="composite", label="Composite", tool="Composite (CoreImage, laptop)", duration_ms=0, cached=True,
              summary=f"{n_frames} frames re-composited with the separation-targeted grade — cache hit on this source and these bounds."),
        Stage(id="encode", label="Encode", tool="ffmpeg", duration_ms=0, cached=True, summary="H.264 CRF 20, faststart, source audio copied."),
    ]
    return ProcessResult(strategy=strategy, artifact="attempt_2", stages=stages,
                         params={"look": profile.data["look"]["id"] + " + separation override", **grade, "rimamt": b.get("rimamt_max"), "lwamt": b.get("lwamt_max"),
                                 "shadow_lift": b.get("shadow_lift_max"), "bounds": b},
                         output={"canvas": [profile.data["canvas"]["w"], profile.data["canvas"]["h"]], "frames": n_frames}, duration_ms=0, cached=True,
                         provenance=f"live: the separation-targeted render for this source, a cache hit from s3://{aws.bucket}/work/{sha[:12]}…/comp_sep and artifacts/{sha[:12]}…/attempt_2.mp4")
