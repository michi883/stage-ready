"""Live backend — the hybrid: AWS for the seeing and the deciding, the laptop for the rendering.

AWS access goes through boto3's default credential chain (env, profile, SSO, instance role); this
module never reads, prints, logs or stores a credential. What it does record, in `Trace`, is every
request id, latency, OpenCV number and Bedrock decision (`stage_ready/aws.py`).

    recognize — S3: is this source (by SHA-256) already under sources/<sha>/ — seen, matte cached?
    inspect   — AWS Lambda `stage-ready-measure`: `stage_ready.measure` with OpenCV 5 over the
                workdir mirrored from work/<sha>/ (detect_band, pose_qc, the dry solve, crown, grade)
    decide    — Amazon Bedrock, Converse API, one tool whose schema is models.Decision; the loop's
                guards in loop.py still refuse what the profile does not allow
    process   — the laptop, cached by source hash: BodyTrack, MatAnyone and Composite are macOS;
                attempt 1 is the archived run for the source, attempt 2 re-composites at the bounds
    verify    — AWS Lambda: matte_extent (U²-Net second opinion on cv2.dnn), separation, head
                spread and drift, frame count, audio MD5 — over work/<sha>/ and artifacts/<sha>/
    fix       — not wired (Sandy's reframe); LiveNotWired

`STAGE_READY_LIVE_LOCAL=1` runs inspect/verify on the laptop's measurer instead of the Lambda and
skips Bedrock — for tests and for a machine without AWS. `?demo=1` never touches this module.

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

    def __init__(self, region: str | None = None, bedrock_model_id: str | None = None, archive: str | None = None,
                 opinion: str = "dnn", local: bool | None = None):
        import os
        from ..aws import BEDROCK_MODEL, REGION
        self.region = region or REGION
        self.bedrock_model_id = bedrock_model_id or BEDROCK_MODEL
        self._archive = archive
        self.opinion = opinion
        self.local = (os.environ.get("STAGE_READY_LIVE_LOCAL") == "1") if local is None else local
        self._measurer = None
        self._aws = None
        self._decisions: list[dict[str, Any]] = []

    # ---- pieces ----------------------------------------------------------------------------
    def measurer(self):
        if self._measurer is None:
            from ..measure import ArchiveMeasurer
            self._measurer = ArchiveMeasurer(self._archive, opinion=self.opinion if self.local else "vision")
        return self._measurer

    def aws(self):
        if self._aws is None:
            from ..aws import AWS
            self._aws = AWS(region=self.region)
        return self._aws

    @property
    def trace(self):
        return self.aws().trace if self._aws is not None else None

    @staticmethod
    def sha_of(clip: Clip) -> str:
        h = clip.recognize.get("sha256")
        return h if isinstance(h, str) else h[0]

    def s3_clip(self, clip: Clip) -> dict[str, Any]:
        """The clip as the Lambda sees it: the archive block in S3 terms."""
        from ..aws import s3_archive_block
        from ..models import to_dict
        d = to_dict(clip)
        d["archive"] = s3_archive_block(clip.archive, self.sha_of(clip))
        return d

    # ---- the catalogue ---------------------------------------------------------------------
    def clips(self) -> list[Clip]:
        from .cached import CachedBackend
        from ..measure import ArchiveMissing
        out = []
        for c in CachedBackend().clips():
            if not c.archive.get("workdir"):
                continue
            if self.local:
                try:
                    self.measurer().workdir(c)
                except ArchiveMissing:
                    continue
            elif not self.aws().recognize(self.sha_of(c)):
                continue                                    # not on S3 yet: python3 -m stage_ready aws sync <clip>
            out.append(c)
        if not out:
            raise LiveNotWired(_msg("listing sources on S3 — none of the catalogue's sources is under sources/<sha256>/ "
                                    "(python3 -m stage_ready aws sync <clip>)"))
        return out

    def clip(self, clip_id: str) -> Clip:
        for c in self.clips():
            if c.id == clip_id:
                return c
        raise LiveNotWired(_msg(f"loading source '{clip_id}' from S3"))

    def recognize(self, sha256: str | None = None, name: str | None = None) -> Clip | None:
        if self.local or not sha256:
            raise LiveNotWired(_msg("looking a source up by SHA-256 on S3"))
        if not self.aws().recognize(sha256.lower()):
            return None
        for c in self.clips():
            if self.sha_of(c).lower() == sha256.lower():
                c.recognize = {**c.recognize, "matched_by": "sha256"}
                return c
        return None

    # ---- INSPECT / VERIFY: the Lambda ------------------------------------------------------
    def _result(self, kind, rec: dict[str, Any]):
        from ..models import Finding, Gate, InspectResult, VerifyResult
        aws = rec.get("aws") or {}
        if kind == "inspect":
            return InspectResult(target=rec["target"], findings=[Finding(**f) for f in rec["findings"]], facts=rec.get("facts", {}),
                                 duration_ms=rec.get("lambda_ms", rec.get("duration_ms", 0)), cached=False, provenance=rec.get("provenance", ""))
        return VerifyResult(artifact=rec["artifact"], gates=[Gate(**g) for g in rec["gates"]], measurements=rec.get("measurements", {}),
                            duration_ms=rec.get("lambda_ms", rec.get("duration_ms", 0)), cached=False, provenance=rec.get("provenance", ""))

    def inspect(self, clip, target, profile, state, focus=None):
        if self.local:
            return self.measurer().inspect(clip, target, profile)
        self.aws().trace.sha, self.aws().trace.clip = self.sha_of(clip), clip.id
        rec = self.aws().invoke_measure("inspect", self.s3_clip(clip), profile.data, target=target, opinion=self.opinion)
        return self._result("inspect", rec)

    def verify(self, clip, artifact, profile, state):
        if self.local:
            return self.measurer().verify(clip, artifact, profile)
        rec = self.aws().invoke_measure("verify", self.s3_clip(clip), profile.data, artifact=artifact, opinion=self.opinion)
        return self._result("verify", rec)

    # ---- DECIDE: Bedrock -------------------------------------------------------------------
    SYSTEM = (
        "You are the deciding agent of Stage Ready, a video-quality loop. OpenCV measures; you decide the next action; "
        "the loop enforces the rules in code, so a disallowed choice is refused and recorded, not executed.\n\n"
        "Actions: inspect (look again at the working picture — say what to focus on), fix (one allowed fixer, kind 'fix'), "
        "process (render an attempt with one allowed processor, kind 'process'), deliver (only after the latest verification "
        "passed every gate), reshoot (no allowed action can honestly satisfy the profile: ask for a new recording, and say what to "
        "change at capture).\n\n"
        "Rules you must respect: a fixer may only reframe, regrade, clean or reprocess recorded content — never invent content; "
        "no fixer changes what was worn or how the room was lit. Choose a process strategy only if it addresses a failing gate "
        "(its 'addresses' list) or it is the standard strategy for a first attempt. Each retry spends the retry budget; a strategy "
        "already tried at its bounds has nowhere further to go. Warnings are recorded-content limits for the report, not defects to fix. "
        "Deliver only when the latest verification passed. When a gate fails and no allowed strategy addresses it, or the retry "
        "budget is spent, the honest exit is reshoot.\n\n"
        "Answer by calling the `decide` tool exactly once. Reasoning: one paragraph, plain words, the numbers from the findings "
        "(never a number that is not there), citing finding and gate ids, and naming the exit if this action fails."
    )

    def _prompt(self, clip, profile, state) -> str:
        import json
        from ..models import to_dict
        p = profile.data
        strategies = [{k: s.get(k) for k in ("id", "kind", "label", "addresses", "cost", "bounds", "reuses", "note") if k in s} for s in p["strategies"]]
        findings = [{k: v for k, v in to_dict(f).items() if k in ("id", "label", "status", "value", "unit", "threshold", "confidence", "detail")} for f in state.findings]
        last = None
        if state.last_verify is not None:
            last = {"artifact": state.last_verify.artifact, "passed": state.last_verify.passed,
                    "gates": [{k: v for k, v in to_dict(g).items() if k in ("id", "label", "status", "value", "threshold", "unit", "detail")} for g in state.last_verify.gates],
                    "measurements": state.last_verify.measurements}
        attempts = [{"n": a.n, "strategy": a.strategy, "passed": a.verify.passed if a.verify else None,
                     "failing": [g.id for g in a.verify.failing] if a.verify else [], "params": a.process.params} for a in state.attempts]
        prior = [{"action": d.action, "strategy": d.strategy, "cites": d.cites} for d in state.decisions]
        doc = {
            "recording": {"id": clip.id, "name": clip.name, "brief": clip.brief, "source": clip.source},
            "profile": {"name": p["name"], "canvas": p["canvas"], "framing": p["framing"], "gates": p["gates"], "strategies": strategies,
                        "retry_budget": p.get("retry_budget", 1), "reshoot_guidance": p.get("reshoot_guidance", {})},
            "working_picture": state.working,
            "current_findings": findings,
            "latest_verification": last,
            "attempts_so_far": attempts,
            "fixes_applied": [f.strategy for f in state.fixes],
            "prior_decisions": prior,
            "budget": state.budget(),
            "decision_number": state.decide_ordinal,
        }
        return "Decide the next action.\n\n" + json.dumps(doc, ensure_ascii=False, indent=1)

    def decide(self, clip, profile, state):
        from ..models import Decision
        if self.local:
            raise LiveNotWired(_msg("the Bedrock agent (STAGE_READY_LIVE_LOCAL=1 has no agent)"))
        inp, meta = self.aws().decide(self.SYSTEM, self._prompt(clip, profile, state), model=self.bedrock_model_id)
        cites = [c for c in inp.get("cites", []) if isinstance(c, str)]
        d = Decision(action=inp.get("action", "reshoot"), reasoning=str(inp.get("reasoning", "")).strip(), strategy=inp.get("strategy") or None,
                     cites=cites, confidence=float(inp.get("confidence", 0.5)), model=f"bedrock:{meta['model']}", duration_ms=meta["latency_ms"], cached=False)
        self._decisions.append({"ordinal": state.decide_ordinal, **to_dict_safe(d), "request_id": meta["request_id"],
                                "input_tokens": meta["input_tokens"], "output_tokens": meta["output_tokens"]})
        return d

    # ---- PROCESS: the laptop, cached by source hash ----------------------------------------
    def process(self, clip, strategy, profile, state):
        from pathlib import Path
        from ..measure import archive_root
        from ..process_local import process_separation_targeted, process_standard
        archive = archive_root(self._archive)
        if strategy == "process.standard":
            pr = process_standard(archive, clip, profile)
        elif strategy == "process.separation_targeted":
            pr = process_separation_targeted(archive, clip, profile)
            # the fixture-free case: attempt_2 was just rendered and the clip's archive block does not name it yet
            clip.archive.setdefault("artifacts", {}).setdefault("attempt_2", {"video": str(Path(clip.archive["source"]).with_name(Path(clip.archive["source"]).stem + "_sep_v1.mp4")), "composite": "comp_sep"})
        else:
            raise LiveNotWired(_msg(f"processor {strategy}"))
        if not self.local:
            # the delivery and the retry's sampled composite go up under the source hash so the Lambda can verify them
            from ..aws import artifact_key, work_prefix
            from ..vision import sample_indices
            import os
            sha = self.sha_of(clip)
            spec = clip.archive["artifacts"][pr.artifact]
            t0 = __import__("time").time()
            n_up = 0
            if spec.get("video") and (archive / spec["video"]).exists():
                n_up += int(self.aws().upload(archive / spec["video"], artifact_key(sha, pr.artifact)))
            if spec.get("composite"):
                comp = archive / clip.archive["workdir"] / spec["composite"]
                mt_n = len([f for f in os.listdir(archive / clip.archive["workdir"] / "mt") if f.endswith(".png")])
                for i in sample_indices(mt_n, 24):
                    f = comp / f"c_{i + 1:04d}.png"
                    if f.exists():
                        n_up += int(self.aws().upload(f, f"{work_prefix(sha)}/{spec['composite']}/{f.name}"))
                for extra in ("params_sep.txt", "separation.log"):
                    if (archive / clip.archive["workdir"] / extra).exists():
                        n_up += int(self.aws().upload(archive / clip.archive["workdir"] / extra, f"{work_prefix(sha)}/{extra}"))
            self.aws().trace.add("process", "s3", op="upload_artifact", artifact=pr.artifact, uploaded=n_up, latency_ms=int((__import__("time").time() - t0) * 1000))
            pr.provenance += f"; uploaded to s3://{self.aws().bucket}/{artifact_key(sha, pr.artifact)}"
        return pr

    def fix(self, clip, strategy, profile, state):
        raise LiveNotWired(_msg(f"fixer {strategy}"))

    # ---- the run's record ------------------------------------------------------------------
    def flush(self) -> dict[str, Any]:
        if self._aws is None:
            return {}
        out = self.aws().flush_trace()
        out["summary"] = self.aws().trace.summary()
        out["decisions"] = self._decisions
        return out


def to_dict_safe(d) -> dict[str, Any]:
    from ..models import to_dict
    return to_dict(d)
