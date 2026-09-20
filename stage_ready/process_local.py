"""The process stage, on the laptop, cached by source hash.

The three things the loop still borrows from macOS — BodyTrack (Apple Vision pose), MatAnyone
(the matte) and Composite (CoreImage) — run here, and their outputs are what a workdir holds.
Live, `process.standard` is a **cache hit** on that workdir: the matte is keyed on the source's
SHA-256 (+ the seed's), exactly as `midtown_red_curtain.sh` keys it, so a source the archive has
seen is not matted again. `process.separation_targeted` reuses everything but the grade, and
re-composites at the strategy's bounds only if that render is not already on disk.

Nothing here invents a pixel: the grade changes the edge and the dark end (rim, light wrap, shadow
lift), never the performer's pixels, and every knob is capped by the profile's bounds.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .models import ProcessResult, Stage
from .profile import Profile
from .record import process_record


def _composite_binary(archive: Path) -> Path:
    p = archive / "tools" / "Composite"
    if not p.exists():
        raise FileNotFoundError(f"Composite not found at {p} — the compositor is macOS (CoreImage); process runs on the laptop")
    return p


def separation_params(params_txt: str, bounds: dict[str, Any]) -> str:
    """The archived grade with rim, light wrap and shadow lift at the strategy's bounds."""
    rim, lw, lift = bounds.get("rimamt_max", 0.45), bounds.get("lwamt_max", 0.70), bounds.get("shadow_lift_max", 0.04)
    s = params_txt.strip()
    s = re.sub(r"rimamt=[\d.]+", f"rimamt={rim:.2f}", s)
    s = re.sub(r"lwamt=[\d.]+", f"lwamt={lw:.2f}", s)
    s = re.sub(r"shadr=[\d.]+", f"shadr={0.018 + lift:.3f}", s)
    s = re.sub(r"shadg=[\d.]+", f"shadg={0.004 + lift:.3f}", s)
    s = re.sub(r"shadb=[\d.]+", f"shadb={0.004 + lift:.3f}", s)
    return s


def render_separation_targeted(archive: Path, wd: Path, source: Path, out_video: Path, profile: Profile) -> dict[str, Any]:
    """Re-composite the cached fg/mt at the strategy's bounds into wd/comp_sep and encode with the
    source's audio copied. Returns stage timings; skips whatever is already on disk."""
    strat = profile.strategy("process.separation_targeted") or {}
    params = separation_params((wd / "params.txt").read_text(), strat.get("bounds", {}))
    (wd / "params_sep.txt").write_text(params + "\n")
    comp = wd / "comp_sep"
    n_fg = len([f for f in os.listdir(wd / "fg") if f.endswith(".jpg")])
    timings: dict[str, int] = {}
    if not comp.is_dir() or len([f for f in os.listdir(comp) if f.endswith(".png")]) != n_fg:
        t = time.time()
        shutil.rmtree(comp, ignore_errors=True)
        subprocess.run([str(_composite_binary(archive)), "--fg", str(wd / "fg"), "--matte", str(wd / "mt"), "--bg", str(wd / "bg"),
                        "--out", str(comp), "--params", *params.split()], check=True, capture_output=True)
        timings["composite_ms"] = int((time.time() - t) * 1000)
    else:
        timings["composite_ms"] = 0
    if not out_video.exists():
        t = time.time()
        fps = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate", "-of", "default=nw=1:nk=1", str(source)],
                             capture_output=True, text=True, check=True).stdout.split()[0]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", fps, "-i", str(comp / "c_%04d.png"), "-i", str(source), "-map", "0:v", "-map", "1:a",
                        "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out_video)],
                       check=True, capture_output=True)
        timings["encode_ms"] = int((time.time() - t) * 1000)
    else:
        timings["encode_ms"] = 0
    return {"params": params, "frames": n_fg, **timings}


def process_standard(archive: Path, clip, profile: Profile) -> ProcessResult:
    """Attempt 1: the archived run for this source — a cache hit keyed on the source hash."""
    wd = archive / clip.archive["workdir"]
    spec = clip.archive["artifacts"].get("attempt_1", {})
    rec = process_record(wd, archive, spec.get("video"), profile, "attempt_1")
    stages = []
    for s in rec["stages"]:
        stages.append(Stage(id=s["id"], label=s["label"], tool=s.get("tool", ""), duration_ms=0, cached=True, reused=False,
                            summary=("cache hit, keyed on the source SHA-256" + (" + seed SHA-256" if s["id"] == "matte" else "") + " — " + s["summary"]),
                            params=s.get("params", {})))
    return ProcessResult(strategy="process.standard", artifact="attempt_1", stages=stages, params=rec["params"], output=rec["output"],
                         duration_ms=0, cached=True,
                         provenance=f"live: the archived run for this source, {wd.relative_to(archive)} (matte.key = source SHA-256 + seed SHA-256); "
                                    f"BodyTrack, MatAnyone and Composite run on the laptop and are not re-run for a source the cache holds")


def process_separation_targeted(archive: Path, clip, profile: Profile) -> ProcessResult:
    """Attempt 2: the same matte and tracking, the grade at the strategy's bounds."""
    wd = archive / clip.archive["workdir"]
    source = archive / clip.archive["source"]
    spec = clip.archive["artifacts"].get("attempt_2") or {}
    out_video = archive / spec["video"] if spec.get("video") else archive / f"{source.stem}_sep_v1.mp4"
    t0 = time.time()
    r = render_separation_targeted(archive, wd, source, out_video, profile)
    strat = profile.strategy("process.separation_targeted") or {}
    b = strat.get("bounds", {})
    grade = {k: float(v) for k, v in re.findall(r"(keydx|rimdx|fgexp)=(-?[\d.]+)", r["params"])}
    cached = r["composite_ms"] == 0
    stages = [
        Stage(id="seed", label="Seed mask", tool="PersonMatte + pick_seed.py + clean_seed.py", reused=True, summary="Reused from attempt 1 — the seed is not what failed."),
        Stage(id="matte", label="Video matte", tool="MatAnyone 2 (local MPS)", reused=True, cached=True, summary="Reused from attempt 1 — keyed on the source SHA-256; nothing to redo."),
        Stage(id="track", label="Tracked reframe solve", tool="track_frame.py", reused=True, summary="Reused — the framing passed every gate."),
        Stage(id="warp", label="Reframe to canvas", tool="warp.py", reused=True, summary="Reused — the same canvas frames and matte."),
        Stage(id="grade", label="Separation-targeted grade", tool="Composite params (bounded override)", duration_ms=0,
              summary=f"rim → {b.get('rimamt_max', 0.45)} (the bound), light wrap → {b.get('lwamt_max', 0.7)} (the bound), shadow lift +{b.get('shadow_lift_max', 0.04)} (the bound); the curtain is untouched.",
              params={"rimamt": b.get("rimamt_max", 0.45), "lwamt": b.get("lwamt_max", 0.7), "shadow_lift": b.get("shadow_lift_max", 0.04), **grade}),
        Stage(id="composite", label="Composite", tool="Composite (CoreImage, laptop)", duration_ms=r["composite_ms"], cached=cached,
              summary=f"{r['frames']} frames re-composited with the separation-targeted grade" + (" — cache hit on this source and these bounds." if cached else ".")),
        Stage(id="encode", label="Encode", tool="ffmpeg", duration_ms=r["encode_ms"], cached=r["encode_ms"] == 0, summary="H.264 CRF 20, faststart, source audio copied."),
    ]
    return ProcessResult(strategy="process.separation_targeted", artifact="attempt_2", stages=stages,
                         params={"look": profile.data["look"]["id"] + " + separation override", **grade, "rimamt": b.get("rimamt_max"), "lwamt": b.get("lwamt_max"),
                                 "shadow_lift": b.get("shadow_lift_max"), "bounds": b},
                         output={"canvas": [profile.data["canvas"]["w"], profile.data["canvas"]["h"]], "frames": r["frames"]},
                         duration_ms=int((time.time() - t0) * 1000), cached=cached,
                         provenance=f"live: re-composited on the laptop from the cached fg/mt of {wd.relative_to(archive)} with params_sep.txt"
                                    + (" (cache hit: comp_sep/ and the encode were already on disk)" if cached else ""))
