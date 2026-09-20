"""Live backend — OpenCV 5 measures; the rest is the shape of the real thing, not yet wired.

Each method names the Red Curtain tool it ports and the AWS service it runs on (README, "Under the hood").
AWS access goes through boto3's default credential chain (env, profile, SSO, instance role);
this module never reads, prints or stores a credential.

    recognize — S3 HEAD by source SHA-256: is the matte for this source already cached?
    inspect   — LIVE: `stage_ready.measure` over the clip's workdir with OpenCV 5 (detect_band,
                pose_qc, the dry solve, crown, auto_grade — `stage_ready.vision`)
    decide    — Amazon Bedrock (Converse API with a tool schema matching models.Decision)
    fix       — track_frame.py with SIZE_CAP / HEAD_TARGET_MAX, crop to the measured band
    process   — seed → matte (cached by source hash on S3) → track → warp → grade → Composite → encode
    verify    — LIVE: matte_extent, separation, head spread and drift, frame count, audio MD5,
                computed from the workdir and the delivered file with OpenCV 5

What "the clip's workdir" means today: the Red Curtain archive (`--archive` / $STAGE_READY_ARCHIVE,
default ~/mts), where every sample clip's pose track, matte, solve and composite already exist —
`demo/clips/<id>/clip.json` → `archive` names them. The catalogue is therefore the archived
clips, and a live run goes INSPECT (measured) → DECIDE, where it stops until Bedrock is wired.
A fresh upload has no workdir yet: producing one is `process`, which is milestone 9.

OpenCV 5 DNN subject segmentation — LIVE for the seed and the second opinion, measured
--------------------------------------------------------------------------------------
`SubjectSegmenter` (stage_ready/vision/segment.py, re-exported below) runs a person segmenter on
`cv2.dnn` — U²-Net's human-segmentation weights by default, Apache-2.0 — so the two things the
Red Curtain pipeline borrowed from Apple Vision can leave the laptop:

    seed     — the mask the video matte is propagated from: on Zach, a matte propagated from the
               DNN seed matches the archived (Vision-seeded) matte at IoU 0.98, head widths equal
    verify   — the independent opinion behind the `matte_extent` gate: within 2 % of Vision's
               number on Sandy, Ethel and Zach (`python3 -m stage_ready segcheck`)

Not used for the `separation` edge: measured on the finished composites, a DNN edge lands up to
0.14× from the pipeline's own matte edge on the small upscaled picture, and the matte is where the
pipeline runs anyway. The demo (`?demo=1`) replays archived measurements and does not load a model.
"""
from __future__ import annotations

from typing import Any

from ..models import Clip


class LiveNotWired(NotImplementedError):
    pass


def _msg(step: str) -> str:
    return (f"live backend: {step} is not wired yet — run with ?demo=1. "
            f"See stage_ready/backends/live.py for what this step maps to.")


from ..vision.segment import SubjectSegmenter  # noqa: E402  — the seam, now the implementation


class LiveBackend:
    name = "live"

    def __init__(self, region: str | None = None, bedrock_model_id: str | None = None, archive: str | None = None):
        self.region = region
        self.bedrock_model_id = bedrock_model_id
        self._session = None
        self._archive = archive
        self._measurer = None

    def measurer(self):
        if self._measurer is None:
            from ..measure import ArchiveMeasurer
            self._measurer = ArchiveMeasurer(self._archive)
        return self._measurer

    # boto3 is imported lazily so demo mode has no AWS dependency at all.
    def _boto(self):
        if self._session is None:
            import boto3  # default credential chain; nothing is passed explicitly
            self._session = boto3.session.Session(region_name=self.region)
        return self._session

    def bedrock(self):
        return self._boto().client("bedrock-runtime")

    def s3(self):
        return self._boto().client("s3")

    def clips(self) -> list[Clip]:
        # The sources this backend can measure today: the archived clips whose workdirs exist.
        # Listing sources on S3 by hash replaces this in milestone 9.
        from .cached import CachedBackend
        from ..measure import ArchiveMissing
        out = []
        for c in CachedBackend().clips():
            try:
                self.measurer().workdir(c)
            except ArchiveMissing:
                continue
            out.append(c)
        if not out:
            raise LiveNotWired(_msg("listing sources on S3 (and no Red Curtain archive was found to measure — "
                                    "set --archive or $STAGE_READY_ARCHIVE)"))
        return out

    def clip(self, clip_id: str) -> Clip:
        for c in self.clips():
            if c.id == clip_id:
                return c
        raise LiveNotWired(_msg(f"loading source '{clip_id}' from S3"))

    def recognize(self, sha256: str | None = None, name: str | None = None) -> Clip | None:
        raise LiveNotWired(_msg("looking a source up by SHA-256 on S3"))

    def inspect(self, clip, target, profile, state, focus=None):
        return self.measurer().inspect(clip, target, profile)

    def decide(self, clip, profile, state):
        raise LiveNotWired(_msg("the Bedrock agent"))

    def fix(self, clip, strategy, profile, state):
        raise LiveNotWired(_msg(f"fixer {strategy}"))

    def process(self, clip, strategy, profile, state):
        raise LiveNotWired(_msg(f"processor {strategy}"))

    def verify(self, clip, artifact, profile, state):
        return self.measurer().verify(clip, artifact, profile)
