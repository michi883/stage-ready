"""INSPECT and VERIFY computed from the files, with OpenCV 5 — not replayed.

`ArchiveMeasurer` turns the measurements in `stage_ready.vision` into the loop's own records
(`InspectResult`, `VerifyResult`) for a clip whose intermediate files exist in a Red Curtain
workdir: the source, the pose track, the matte, the solved transform, the composite. That is
what every archived clip has (`demo/clips/<id>/clip.json` → `archive`), and it is what a live
run leaves behind on S3 keyed by source hash (README, milestone 9) — so the same measurer serves
the live backend today over the archive, and later over a workdir that AWS compute produced.

What is *not* here: producing those files. The pose track, the matte and the solve are the
process stages (BodyTrack, MatAnyone, track_frame); today they come from the archive. INSPECT on
a fresh upload therefore reaches as far as the picture area and the container facts, and says so.

Every number below is computed by the same arithmetic the archive scripts used — the fixtures
were measured with those scripts, and `python3 -m stage_ready measure` prints both side by side.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .models import Clip, Finding, Gate, InspectResult, VerifyResult
from .profile import Profile


class ArchiveMissing(LookupError):
    pass


def archive_root(explicit: str | None = None) -> Path:
    """Where the Red Curtain archive lives: --archive, $STAGE_READY_ARCHIVE, or ~/mts."""
    return Path(os.path.expanduser(explicit or os.environ.get("STAGE_READY_ARCHIVE", "~/mts")))


def _pct(x: float) -> str:
    return f"{x * 100:.0f} %"


class ArchiveMeasurer:
    def __init__(self, root: Path | str | None = None):
        self.root = archive_root(None if root is None else str(root))
        self._anchors: dict[str, Any] = {}
        self._pose: dict[str, list[dict]] = {}
        self._md5: dict[str, str] = {}
        self._frames: dict[str, int] = {}

    # ---- the workdir ------------------------------------------------------------------------
    def workdir(self, clip: Clip) -> Path:
        a = clip.__dict__.get("archive") or {}
        if not a.get("workdir"):
            raise ArchiveMissing(f"clip {clip.id} names no archive workdir; nothing to measure")
        wd = self.root / a["workdir"]
        if not wd.is_dir():
            raise ArchiveMissing(f"archive workdir missing: {wd} (set --archive or $STAGE_READY_ARCHIVE)")
        return wd

    def source(self, clip: Clip) -> Path:
        p = self.root / clip.__dict__["archive"]["source"]
        if not p.is_file():
            raise ArchiveMissing(f"archived source missing: {p}")
        return p

    def artifact(self, clip: Clip, artifact: str) -> dict[str, Any]:
        arts = clip.__dict__["archive"].get("artifacts", {})
        if artifact not in arts:
            raise ArchiveMissing(f"clip {clip.id}: no archived artifact '{artifact}'")
        return arts[artifact]

    @staticmethod
    def _pick(wd: Path, ext: str, plain: str) -> Path:
        # The solve ran on the crown-completed picture where the archive extended it (§6);
        # measurements of the delivered framing must read the same files the solve did.
        return wd / ext if (wd / ext).exists() else wd / plain

    def pose(self, wd: Path, ext: bool = False) -> list[dict]:
        from .vision import read_pose
        p = self._pick(wd, "pose_ext.csv", "pose.csv") if ext else wd / "pose.csv"
        key = str(p)
        if key not in self._pose:
            self._pose[key] = read_pose(str(p))
        return self._pose[key]

    def anchors(self, wd: Path):
        from .vision.track import anchors
        key = str(wd)
        if key not in self._anchors:
            self._anchors[key] = anchors(str(self._pick(wd, "matte_ext", "matte")), self.pose(wd, ext=True))
        return self._anchors[key]

    def frames(self, path: Path) -> int:
        from .vision import frame_count
        key = str(path)
        if key not in self._frames:
            self._frames[key] = frame_count(str(path))
        return self._frames[key]

    def md5(self, path: Path) -> str:
        from .vision import audio_md5
        key = str(path)
        if key not in self._md5:
            self._md5[key] = audio_md5(str(path))
        return self._md5[key]

    # ---- INSPECT ------------------------------------------------------------------------------
    def inspect(self, clip: Clip, target: str, profile: Profile) -> InspectResult:
        from .vision import crown_cut, detect_band, pose_qc, probe
        from .vision.grade import grade_qc
        from .vision.track import dry_solve

        t0 = time.time()
        wd, src = self.workdir(clip), self.source(clip)
        insp = profile.data["inspection"]
        fr = profile.data["framing"]
        canvas = (int(profile.data["canvas"]["w"]), int(profile.data["canvas"]["h"]))
        pr = probe(str(src))
        facts = {"picture": f"{pr.width}×{pr.height}", "fps": round(pr.fps, 3), "frames": pr.frames_declared,
                 "duration_s": round(pr.duration_s, 1)}
        findings: list[Finding] = []

        band = detect_band(str(src))
        facts["picture"] = f"{band.w}×{band.h} at +{band.x}+{band.y}"
        # After the reframe fix the picture *is* the band: the fixer crops to it.
        fixed = target != "source"
        val = {"w": band.w, "h": band.h, "x": 0 if fixed else band.x, "y": 0 if fixed else band.y}
        findings.append(Finding(
            id="picture_area", label=insp["picture_area"]["label"], status="pass" if (band.fills_file or fixed) else "fail",
            value=val, unit="px", threshold=f"fills the {band.file_w}×{band.file_h} file",
            confidence=1.0, frames=f"sampled every 30th frame ({band.frames_sampled} of {band.frames_read})",
            detail=(f"The recorded picture fills the file: {band}, no padding." if band.fills_file else
                    f"The recorded picture is {band.w}×{band.h} inside a {band.file_w}×{band.file_h} file, at +{band.x}+{band.y}"
                    + (" — cropped to the picture." if fixed else ": padding the fixer must crop before framing.")),
            tool="vision.detect_band (OpenCV 5)"))

        q = pose_qc(self.pose(wd))
        pc = insp["pose_coverage"]
        findings.append(Finding(id="pose_coverage", label=pc["label"], status="pass" if q.coverage >= pc["value"] else "fail",
                                value=round(q.coverage, 3), unit="fraction of frames", threshold={"op": pc["op"], "value": pc["value"]},
                                frames=f"{int(round(q.coverage * q.frames))} / {q.frames}",
                                detail=f"A body pose on {_pct(q.coverage)} of frames.", tool="BodyTrack + vision.pose_qc"))
        os_ = insp["one_subject"]
        findings.append(Finding(id="one_subject", label=os_["label"], status="pass" if q.one_subject >= os_["value"] else "fail",
                                value=round(q.one_subject, 3), unit="fraction of frames", threshold={"op": os_["op"], "value": os_["value"]},
                                frames=f"{q.off_subject} frames off-subject ({q.off_by_size} by size, {q.off_by_position} by position)",
                                detail=f"The same subject, of the same size, in the same place, on {q.one_subject * 100:.1f} % of frames.",
                                tool="vision.pose_qc"))

        d = dry_solve(str(self._pick(wd, "matte_ext", "matte")), self.pose(wd, ext=True), canvas, pr.fps or 30.0,
                      head_target=fr["head_target"], stab_sec=fr["stab_sec"], size_cap=fr["size_cap"], head_target_max=fr["head_target_max"])
        ss = insp["subject_size"]
        p50, p95 = (d.span_p50_used, d.span_p95_used) if fixed else (d.span_p50, d.span_p95)
        ht = d.head_target_used if fixed else d.head_target
        ok = p95 <= ss["value"] + 1e-9
        detail = (f"At head_target {ht:.3f} the shoulders span {_pct(p50)} of the canvas (p95 {_pct(p95)}) — "
                  + (f"under the {_pct(ss['value'])} cap." if ok else
                     f"over the {_pct(ss['value'])} cap. Holding their size means moving the head down to {d.head_target_used:.3f}."))
        findings.append(Finding(id="subject_size", label=ss["label"], status="pass" if ok else "fail",
                                value={"p50": round(p50, 3), "p95": round(p95, 3)} | ({} if ok else {"reach": round(d.widest, 3)}),
                                unit=ss["unit"].split(",")[0], threshold={"op": ss["op"], "value": ss["value"]}, frames="all frames",
                                detail=detail, tool="vision.track.dry_solve (OpenCV 5)"))

        ds = insp["distance_steady"]
        steady = q.drift <= ds["value"] if q.drift == q.drift else True
        findings.append(Finding(id="distance_steady", label=ds["label"], status="pass" if steady else ds.get("severity", "warn"),
                                value=round(q.drift, 2), unit=ds["unit"], threshold={"op": ds["op"], "value": ds["value"]},
                                frames="all frames",
                                detail=(f"Apparent size steady to {q.drift:.2f}×." if steady else
                                        f"Apparent size changes by {q.drift:.2f}× across the take — the performer walks toward or away from the camera; perspective cannot be undone downstream."),
                                tool="vision.pose_qc"))

        a = self.anchors(wd)
        cut = crown_cut(str(wd / "matte"))
        hr = insp["headroom"]
        top = [t / a.picture_h for t in a.top]
        hr_val: dict[str, Any] = {"crown_cut_frames": round(cut, 2)}
        if cut < 0.05:
            hr_val |= {"min": round(min(top), 3), "max": round(max(top), 3)}
        findings.append(Finding(id="headroom", label=hr["label"], status="pass" if cut < 0.05 else "warn",
                                value=hr_val, unit="fraction of frames with the crown outside the picture", threshold={"recommended": hr["recommended"]},
                                frames="all frames",
                                detail=(f"The crown is inside the picture on every frame." if cut == 0 else
                                        f"The crown leaves the picture on {_pct(cut)} of frames — rows that were never recorded."),
                                tool="vision.crown_cut (OpenCV 5)"))

        g = grade_qc(str(wd / "band"), str(wd / "matte"), self.pose(wd), face_target=profile.data["look"]["face_target"],
                     clamp=tuple(profile.data["look"]["fgexp_clamp"]))
        fe = insp["face_exposure"]
        findings.append(Finding(id="face_exposure", label=fe["label"], status="warn" if g.clamped else "pass",
                                value=round(g.fgexp, 3), unit=f"exposure gain toward the {fe['target']:.2f} target",
                                threshold={"target": fe["target"], "clamp": profile.data["look"]["fgexp_clamp"]}, frames="median over the take",
                                detail=(f"Face luma {g.face:.3f}: the grade brings it ×{g.fgexp:.2f} to the target, inside the clamp." if not g.clamped else
                                        f"Face luma {g.face:.3f} asked for ×{g.gain:.2f} and was held at ×{g.fgexp:.2f} — the recording is {'under' if g.gain > 1 else 'over'}-lit for the stage."),
                                tool="vision.grade_qc (OpenCV 5)"))
        kd = insp["key_direction"]
        flat = 1 / 1.08 < g.ratio < 1.08
        findings.append(Finding(id="key_direction", label=kd["label"], status="info", value=round(g.ratio, 2),
                                unit=kd["unit"], threshold={"flat_below": 1.08}, frames="median over the take",
                                detail=(f"Flat-lit (L {g.left:.3f} / R {g.right:.3f}); the stage convention stands." if flat else
                                        f"Key from the {'right' if g.keydx > 0 else 'left'} (L {g.left:.3f} / R {g.right:.3f}, ×{g.ratio:.2f}); the stage's key and rim follow it."),
                                tool="vision.grade_qc (OpenCV 5)"))

        return InspectResult(target=target, findings=findings, facts=facts, duration_ms=int((time.time() - t0) * 1000), cached=False,
                             provenance=f"measured: OpenCV 5 over {wd.relative_to(self.root)} and {src.name}")

    # ---- VERIFY -------------------------------------------------------------------------------
    def verify(self, clip: Clip, artifact: str, profile: Profile) -> VerifyResult:
        from .vision import matte_extent, pose_qc, probe, separation
        from .vision.track import dry_solve, head_height, read_affine

        t0 = time.time()
        wd, src = self.workdir(clip), self.source(clip)
        art = self.artifact(clip, artifact)
        video = self.root / art["video"] if art.get("video") else None
        comp = wd / art["composite"] if art.get("composite") else None
        measured_on = comp if comp is not None and comp.is_dir() else video
        if measured_on is None or not measured_on.exists():
            raise ArchiveMissing(f"clip {clip.id}: artifact '{artifact}' has neither a composite directory nor a delivered file on disk")
        canvas_h = int(profile.data["canvas"]["h"])
        fps = probe(str(src)).fps or 30.0
        th = {g["id"]: g for g in profile.gates}

        q = pose_qc(self.pose(wd))
        mq = matte_extent(str(wd / "matte"), str(wd / "seed"), self.pose(wd))
        sep = separation(str(measured_on), str(wd / "mt"))
        hh = head_height(str(self._pick(wd, "matte_ext", "matte")), self.pose(wd, ext=True), read_affine(str(wd / "affine.csv")), canvas_h, fps)
        n_src = self.frames(src)
        n_out = self.frames(video) if video is not None and video.exists() else None
        a_src, a_out = (self.md5(src), self.md5(video)) if video is not None and video.exists() else (None, None)
        d = dry_solve(str(self._pick(wd, "matte_ext", "matte")), self.pose(wd, ext=True), (int(profile.data["canvas"]["w"]), canvas_h), fps,
                      head_target=profile.data["framing"]["head_target"], stab_sec=profile.data["framing"]["stab_sec"],
                      size_cap=profile.data["framing"]["size_cap"], head_target_max=profile.data["framing"]["head_target_max"])

        def gate(gid, status, value, detail, tool):
            g = th[gid]
            thr = {"op": g["op"], "value": g["value"]} if g["value"] != "source" else None
            return Gate(id=gid, label=g["label"], status=status, value=value, threshold=thr, unit=g.get("unit", ""), detail=detail, tool=tool)

        gates = []
        for g in profile.gates:
            gid = g["id"]
            if gid == "pose_coverage":
                gates.append(gate(gid, "pass" if q.coverage >= g["value"] else "fail", round(q.coverage, 3),
                                  f"{_pct(q.coverage)} of {q.frames} frames.", "BodyTrack + vision.pose_qc"))
            elif gid == "one_subject":
                gates.append(gate(gid, "pass" if q.one_subject >= g["value"] else "fail", round(q.one_subject, 3),
                                  f"{q.one_subject * 100:.1f} %.", "vision.pose_qc"))
            elif gid == "matte_extent":
                gates.append(gate(gid, "pass" if mq.median >= g["value"] else "fail", round(mq.median, 3),
                                  f"Matte head width {_pct(mq.median)} of the second opinion's over {mq.frames} frames "
                                  f"(worst frame {mq.worst_frame}: {mq.worst_matte_px} px vs {mq.worst_opinion_px} px).", "vision.matte_extent (OpenCV 5)"))
            elif gid == "separation":
                margin = round(sep.ratio, 2) - g["value"]
                side = "the performer is the brighter side" if sep.inside > sep.outside else "the performer is the darker side — the silhouette is carried by the curtain being the brighter of the two"
                gates.append(gate(gid, "pass" if sep.ratio >= g["value"] else "fail", round(sep.ratio, 2),
                                  f"Edge luma {sep.inside:.3f} inside / {sep.outside:.3f} outside — separation {sep.ratio:.2f}× "
                                  f"over {sep.frames} frames of {measured_on.name}; {side}; "
                                  + (f"clears the {g['value']}× gate by {margin:.2f}×" if margin >= 0 else f"short of the {g['value']}× gate by {-margin:.2f}×")
                                  + (f". Decoded by {sep.decoder}: a file-sourced number moves ~1 % with the decoder; the frames are the record." if sep.decoder else "."),
                                  "vision.separation (OpenCV 5)"))
            elif gid == "head_spread":
                gates.append(gate(gid, "pass" if hh.spread <= g["value"] else "fail", round(hh.spread, 3),
                                  f"{hh.source_spread * 100:.1f} % of source → {hh.spread * 100:.1f} % of output.", "vision.head_height (OpenCV 5)"))
            elif gid == "head_drift":
                gates.append(gate(gid, "pass" if hh.drift_px <= g["value"] else "fail", round(hh.drift_px, 1),
                                  f"{hh.drift_px:.1f} px of head-top motion slower than 2 s after the solve.", "vision.head_height (OpenCV 5)"))
            elif gid == "frame_count":
                if n_out is None:
                    gates.append(Gate(id=gid, label=g["label"], status="info", value=None, threshold=n_src, unit="frames",
                                      detail="No delivered file on disk to count.", tool="vision.frame_count"))
                else:
                    gates.append(Gate(id=gid, label=g["label"], status="pass" if n_out == n_src else "fail", value=n_out, threshold=n_src,
                                      unit="frames", detail=f"{n_out} = {n_src}." if n_out == n_src else f"{n_out} ≠ {n_src}.", tool="vision.frame_count (OpenCV 5)"))
            elif gid == "audio_md5":
                if a_out is None:
                    gates.append(Gate(id=gid, label=g["label"], status="info", value=None, threshold="equal", detail="No delivered file on disk to hash.", tool="vision.audio_md5"))
                else:
                    same = a_out == a_src
                    gates.append(Gate(id=gid, label=g["label"], status="pass" if same else "fail", value="equal" if same else "differs", threshold="equal",
                                      detail=("Decoded audio MD5 identical to the source." if same else f"Decoded audio differs from the source ({a_out[:8]}… vs {a_src[:8]}…)."),
                                      tool="vision.audio_md5 (ffmpeg)"))
            else:
                gates.append(Gate(id=gid, label=g["label"], status="info", value=None, threshold=None, detail="Not measured by this backend.", tool=""))

        measurements = {"head_target": round(hh.head_median, 3), "shoulder_span_p50": round(d.span_p50_used, 3),
                        "separation": round(sep.ratio, 2), "edge_luma_in": round(sep.inside, 3), "edge_luma_out": round(sep.outside, 3),
                        "head_spread": round(hh.spread, 3), "head_drift_px": round(hh.drift_px, 1), "frames": n_out if n_out is not None else n_src}
        return VerifyResult(artifact=artifact, gates=gates, measurements=measurements, duration_ms=int((time.time() - t0) * 1000), cached=False,
                            provenance=f"measured: OpenCV 5 over {wd.relative_to(self.root)}, {measured_on.relative_to(self.root)}")
