"""The minimal AWS shape: S3 by source hash, one Lambda for the OpenCV 5 measurements, Bedrock for DECIDE.

Credentials come from boto3's default chain (env, profile, SSO, instance role) and nothing in this
module reads, prints, logs or stores one. What *is* logged, on purpose: every AWS request's id,
its latency, the stage it served, and the OpenCV numbers and Bedrock decisions that came back —
`Trace`, written to `runs/<sha256>/<run_id>/trace.jsonl` in the bucket and to `.stage_ready/runs/`
locally. No performer media is logged; media lives only under its source-hash prefix.

S3 layout — every prefix is the source's SHA-256, the key the matte cache has always used:

    sources/<sha>/source.<ext>           the recording, as uploaded
    work/<sha>/…                          the workdir, in the archive's own layout: pose.csv, pose_ext.csv,
                                          affine.csv, matte.key, track.log, params*.txt, separation.log,
                                          seed/, matte/, matte_ext/, mt/ (whole), band/ and comp*/ (the sampled frames)
    artifacts/<sha>/<artifact>.mp4        deliveries (attempt_1, attempt_2 …)
    measurements/<sha>/inspect.<t>.json   INSPECT and VERIFY as the Lambda measured them
    measurements/<sha>/verify.<a>.json
    runs/<sha>/<run_id>/trace.jsonl       the run's observability record
    models/<file>.onnx                    the DNN segmenter's weights, fetched by the Lambda at cold start

The workdir key maps 1:1 onto the archive's `work/midtown_<clip>/` so `ArchiveMeasurer` runs on
the Lambda unchanged, with `/tmp/archive` as its root.

AWS resources this module creates, all in one region: the bucket (if absent), an IAM role for the
Lambda (basic execution + this bucket), one Lambda layer (OpenCV 5 + numpy + a static ffmpeg) and
one Lambda function (`stage-ready-measure`, arm64, Python 3.12). Bedrock needs no resource.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REGION = os.environ.get("STAGE_READY_AWS_REGION", "us-east-1")
BUCKET = os.environ.get("STAGE_READY_BUCKET", "stage-ready-videos")
FUNCTION = os.environ.get("STAGE_READY_LAMBDA", "stage-ready-measure")
LAYER = "stage-ready-opencv5"
ROLE = "stage-ready-lambda-role"
# The agent. Claude Sonnet 4.6: 9/9 of the trusted DECIDE states, twice (`agent-eval`, 2026-09-20).
# Amazon Nova 2 Lite measured 6/9 — right on every routine state, wrong on the stopping decisions
# (Sandy #3, Zach #3) and one strategy choice (Zach #1) — so it is not the default. Opus 5 / Sonnet 5
# are listed for the account but not enabled (AccessDenied). One variable swaps the model.
BEDROCK_MODEL = os.environ.get("STAGE_READY_BEDROCK_MODEL", "global.anthropic.claude-sonnet-4-6")
ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / ".stage_ready" / "runs"


# ---- keys -------------------------------------------------------------------------------------
def source_key(sha: str, ext: str) -> str:
    return f"sources/{sha}/source.{ext.lstrip('.')}"


def work_prefix(sha: str) -> str:
    return f"work/{sha}"


def artifact_key(sha: str, artifact: str) -> str:
    return f"artifacts/{sha}/{artifact}.mp4"


def measurement_key(sha: str, kind: str, name: str) -> str:
    return f"measurements/{sha}/{kind}.{name}.json"


def run_key(sha: str, run_id: str) -> str:
    return f"runs/{sha}/{run_id}/trace.jsonl"


def s3_archive_block(clip_archive: dict[str, Any], sha: str) -> dict[str, Any]:
    """The clip's `archive` block rewritten in S3 terms — what the Lambda measures against, with
    `/tmp/archive` as the root. The composite directories keep their names under work/<sha>/."""
    ext = Path(clip_archive["source"]).suffix.lstrip(".") or "mp4"
    arts = {}
    for name, spec in clip_archive.get("artifacts", {}).items():
        a = {}
        if spec.get("video"):
            a["video"] = artifact_key(sha, name)
        if spec.get("composite"):
            a["composite"] = spec["composite"]
        arts[name] = a
    return {"workdir": work_prefix(sha), "source": source_key(sha, ext), "artifacts": arts}


# ---- observability ----------------------------------------------------------------------------
@dataclass
class Trace:
    run_id: str = field(default_factory=lambda: time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6])
    sha: str = ""
    clip: str = ""
    records: list[dict[str, Any]] = field(default_factory=list)

    def add(self, stage: str, service: str, **kw: Any) -> dict[str, Any]:
        rec = {"t": round(time.time(), 3), "run_id": self.run_id, "clip": self.clip, "stage": stage, "service": service, **kw}
        self.records.append(rec)
        return rec

    def dumps(self) -> str:
        return "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in self.records)

    def summary(self) -> dict[str, Any]:
        by = {}
        for r in self.records:
            by.setdefault(r["service"], []).append(r)
        return {"run_id": self.run_id, "clip": self.clip, "sha256": self.sha, "records": len(self.records),
                "latency_ms": {k: sum(x.get("latency_ms", 0) for x in v) for k, v in by.items()},
                "bedrock_tokens": {"input": sum(x.get("input_tokens", 0) for x in by.get("bedrock", [])),
                                   "output": sum(x.get("output_tokens", 0) for x in by.get("bedrock", []))},
                "errors": [r for r in self.records if r.get("error")]}


def _rid(resp: dict[str, Any]) -> str:
    return (resp.get("ResponseMetadata") or {}).get("RequestId", "")


# ---- the client -------------------------------------------------------------------------------
class AWS:
    def __init__(self, region: str = REGION, bucket: str = BUCKET, trace: Trace | None = None):
        import boto3  # default credential chain; nothing is passed explicitly
        self.region, self.bucket = region, bucket
        self.session = boto3.session.Session(region_name=region)
        self.trace = trace or Trace()

    # boto3 clients are cheap to hold; each is created once
    def s3(self):
        if not hasattr(self, "_s3"):
            self._s3 = self.session.client("s3")
        return self._s3

    def lam(self):
        if not hasattr(self, "_lam"):
            from botocore.config import Config
            self._lam = self.session.client("lambda", config=Config(read_timeout=930, connect_timeout=10, retries={"max_attempts": 0}))
        return self._lam

    def bedrock(self):
        if not hasattr(self, "_br"):
            from botocore.config import Config
            self._br = self.session.client("bedrock-runtime", config=Config(read_timeout=300, retries={"max_attempts": 2}))
        return self._br

    def identity(self) -> dict[str, str]:
        d = self.session.client("sts").get_caller_identity()
        acct = d["Account"]
        return {"account": acct[:4] + "…" + acct[-3:], "arn_type": d["Arn"].split(":")[5].split("/")[0], "principal": d["Arn"].split("/")[-1]}

    # ---- S3 ------------------------------------------------------------------------------------
    def bucket_status(self) -> str:
        """'ours' | 'missing' | 'not-ours' — a 403 means the name is taken in another account."""
        from botocore.exceptions import ClientError
        try:
            self.s3().head_bucket(Bucket=self.bucket)
            return "ours"
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in ("404", "NoSuchBucket") or status == 404:
                return "missing"
            if code in ("403", "AccessDenied") or status == 403:
                return "not-ours"
            raise

    def ensure_bucket(self) -> str:
        st = self.bucket_status()
        if st == "not-ours":
            raise RuntimeError(f"bucket {self.bucket} exists in another account — stopping rather than choosing another name")
        if st == "missing":
            kw = {"Bucket": self.bucket}
            if self.region != "us-east-1":
                kw["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
            r = self.s3().create_bucket(**kw)
            self.s3().put_public_access_block(Bucket=self.bucket, PublicAccessBlockConfiguration={
                "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
            self.trace.add("bucket", "s3", op="create_bucket", request_id=_rid(r), bucket=self.bucket)
            return "created"
        return "exists"

    def head(self, key: str) -> dict[str, Any] | None:
        from botocore.exceptions import ClientError
        try:
            return self.s3().head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return None
            raise

    def upload(self, path: Path, key: str, skip_same_size: bool = True) -> bool:
        if skip_same_size:
            h = self.head(key)
            if h and h.get("ContentLength") == path.stat().st_size:
                return False
        self.s3().upload_file(str(path), self.bucket, key)
        return True

    def sync_clip(self, clip, archive_root: Path, progress=None) -> dict[str, Any]:
        """Upload what `measure` needs for one clip (the bundle's selection) under its source-hash
        prefixes. Idempotent: same-size objects are skipped."""
        from .bundle import plan
        sha = clip.recognize["sha256"] if isinstance(clip.recognize.get("sha256"), str) else clip.recognize["sha256"][0]
        items = plan(archive_root, [clip.id])
        wd_rel = clip.archive["workdir"]; src_rel = clip.archive["source"]
        videos = {spec["video"]: name for name, spec in clip.archive.get("artifacts", {}).items() if spec.get("video")}
        from concurrent.futures import ThreadPoolExecutor
        todo = []
        for src, rel in items:
            if rel.startswith("demo-media/"):
                continue
            if rel == src_rel:
                key = source_key(sha, Path(rel).suffix)
            elif rel in videos:
                key = artifact_key(sha, videos[rel])
            elif rel.startswith(wd_rel + "/"):
                key = f"{work_prefix(sha)}/{rel[len(wd_rel) + 1:]}"
            else:
                continue
            todo.append((src, key))
        total = sum(src.stat().st_size for src, _ in todo)
        # thousands of small mattes: what is already there (same size) is skipped, the rest goes up in parallel
        present = {}
        token = None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": f"work/{sha}/"}
            if token:
                kw["ContinuationToken"] = token
            r = self.s3().list_objects_v2(**kw)
            for o in r.get("Contents", []):
                present[o["Key"]] = o["Size"]
            if not r.get("IsTruncated"):
                break
            token = r.get("NextContinuationToken")
        need = [(src, key) for src, key in todo if present.get(key) != src.stat().st_size and not (not key.startswith("work/") and (self.head(key) or {}).get("ContentLength") == src.stat().st_size)]
        done = [0]
        def up(item):
            self.s3().upload_file(str(item[0]), self.bucket, item[1])
            done[0] += 1
            if progress and done[0] % 500 == 0:
                progress(done[0], len(need))
        with ThreadPoolExecutor(max_workers=32) as ex:
            list(ex.map(up, need))
        return {"sha256": sha, "uploaded": len(need), "skipped": len(todo) - len(need), "bytes": total}

    def sync_model(self, name: str = "u2net_human_seg") -> str:
        from .vision.segment import MODELS, MODELS_DIR, fetch
        path = fetch(name)
        key = f"models/{MODELS[name]['file']}"
        self.upload(path, key)
        return key

    def put_json(self, key: str, data: Any) -> str:
        r = self.s3().put_object(Bucket=self.bucket, Key=key, Body=json.dumps(data, ensure_ascii=False, indent=1).encode(), ContentType="application/json")
        return _rid(r)

    def get_json(self, key: str) -> Any:
        return json.loads(self.s3().get_object(Bucket=self.bucket, Key=key)["Body"].read())

    def recognize(self, sha: str) -> bool:
        """Is this source on S3 — i.e. has it been seen (and its matte cached) before?"""
        from botocore.exceptions import ClientError
        try:
            r = self.s3().list_objects_v2(Bucket=self.bucket, Prefix=f"sources/{sha}/", MaxKeys=1)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchBucket":
                return False
            raise
        return r.get("KeyCount", 0) > 0

    # ---- Lambda --------------------------------------------------------------------------------
    def ensure_role(self) -> str:
        iam = self.session.client("iam")
        from botocore.exceptions import ClientError
        trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
        try:
            arn = iam.get_role(RoleName=ROLE)["Role"]["Arn"]
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchEntity":
                raise
            r = iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(trust), Description="Stage Ready: the OpenCV 5 measurement Lambda")
            arn = r["Role"]["Arn"]
            self.trace.add("deploy", "iam", op="create_role", request_id=_rid(r), role=ROLE)
            iam.attach_role_policy(RoleName=ROLE, PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
            time.sleep(8)   # IAM propagation before the function can assume it
        policy = {"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
             "Resource": [f"arn:aws:s3:::{self.bucket}", f"arn:aws:s3:::{self.bucket}/*"]}]}
        iam.put_role_policy(RoleName=ROLE, PolicyName="stage-ready-bucket", PolicyDocument=json.dumps(policy))
        return arn

    @staticmethod
    def _zip_dir(root: Path, arcroot: str = "", exclude=("__pycache__",)) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(root.rglob("*")):
                if p.is_file() and not any(x in p.parts for x in exclude) and not p.name.endswith(".pyc"):
                    info = zipfile.ZipInfo(str(Path(arcroot) / p.relative_to(root)) if arcroot else str(p.relative_to(root)))
                    info.date_time = (2026, 1, 1, 0, 0, 0)          # reproducible zips
                    info.external_attr = (0o755 if os.access(p, os.X_OK) else 0o644) << 16
                    z.writestr(info, p.read_bytes())
        return buf.getvalue()

    def deploy_layer(self, layer_dir: Path) -> str:
        """Publish the OpenCV 5 + numpy + ffmpeg layer from an assembled directory (python/, bin/).
        Uploaded through S3 (the zip is larger than the direct-upload limit)."""
        data = self._zip_dir(layer_dir)
        key = f"deploy/{LAYER}-{hashlib.sha256(data).hexdigest()[:12]}.zip"
        self.s3().put_object(Bucket=self.bucket, Key=key, Body=data)
        r = self.lam().publish_layer_version(LayerName=LAYER, Description="opencv-python-headless 5.0.0.93, numpy 2.4.6, static ffmpeg (arm64)",
                                             Content={"S3Bucket": self.bucket, "S3Key": key}, CompatibleRuntimes=["python3.12"], CompatibleArchitectures=["arm64"])
        self.trace.add("deploy", "lambda", op="publish_layer_version", request_id=_rid(r), layer=r["LayerVersionArn"], bytes=len(data))
        return r["LayerVersionArn"]

    def deploy_function(self, layer_arn: str, role_arn: str) -> str:
        """Create or update `stage-ready-measure`: the stage_ready package + profiles, on the layer."""
        from botocore.exceptions import ClientError
        code = self._zip_dir(ROOT / "stage_ready", "stage_ready")
        prof = self._zip_dir(ROOT / "profiles", "profiles")
        # merge the two zips
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for blob in (code, prof):
                with zipfile.ZipFile(io.BytesIO(blob)) as src:
                    for info in src.infolist():
                        z.writestr(info, src.read(info))
        data = buf.getvalue()
        env = {"Variables": {"STAGE_READY_BUCKET": self.bucket, "STAGE_READY_MODELS_DIR": "/tmp/models", "OPENCV_LOG_LEVEL": "ERROR"}}
        cfg = dict(Runtime="python3.12", Role=role_arn, Handler="stage_ready.lambda_handler.handler", Timeout=900, MemorySize=3008,
                   Architectures=["arm64"], Layers=[layer_arn], Environment=env, EphemeralStorage={"Size": 2048},
                   Description="Stage Ready: INSPECT and VERIFY with OpenCV 5 and the U²-Net segmenter, from a workdir on S3")
        try:
            r = self.lam().get_function(FunctionName=FUNCTION)
            arn = r["Configuration"]["FunctionArn"]
            self.lam().update_function_code(FunctionName=FUNCTION, ZipFile=data, Architectures=["arm64"])
            self._wait_updated()
            r2 = self.lam().update_function_configuration(FunctionName=FUNCTION, **{k: v for k, v in cfg.items() if k != "Architectures"})
            self.trace.add("deploy", "lambda", op="update_function", request_id=_rid(r2), function=FUNCTION, bytes=len(data))
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
            r = self.lam().create_function(FunctionName=FUNCTION, Code={"ZipFile": data}, PackageType="Zip", **cfg)
            arn = r["FunctionArn"]
            self.trace.add("deploy", "lambda", op="create_function", request_id=_rid(r), function=FUNCTION, bytes=len(data))
        self._wait_updated()
        return arn

    def _wait_updated(self, timeout: float = 180):
        t0 = time.time()
        while time.time() - t0 < timeout:
            c = self.lam().get_function_configuration(FunctionName=FUNCTION)
            if c.get("LastUpdateStatus", "Successful") == "Successful" and c.get("State", "Active") == "Active":
                return
            time.sleep(2)

    def invoke_measure(self, op: str, clip_dict: dict[str, Any], profile_data: dict[str, Any], **kw: Any) -> dict[str, Any]:
        """One INSPECT or VERIFY on the Lambda. Returns the measurer's record plus the Lambda's own
        timings; records the request id and latency in the trace."""
        payload = {"op": op, "clip": clip_dict, "profile": profile_data, "run_id": self.trace.run_id, **kw}
        t0 = time.time()
        r = self.lam().invoke(FunctionName=FUNCTION, InvocationType="RequestResponse", LogType="Tail", Payload=json.dumps(payload).encode())
        latency = int((time.time() - t0) * 1000)
        body = json.loads(r["Payload"].read() or b"{}")
        rec = self.trace.add(op, "lambda", request_id=_rid(r), latency_ms=latency, function=FUNCTION, status=r.get("StatusCode"),
                             function_error=r.get("FunctionError"), **{k: v for k, v in kw.items() if isinstance(v, (str, int))})
        if r.get("FunctionError") or "errorMessage" in body:
            rec["error"] = body.get("errorMessage") or body
            raise RuntimeError(f"lambda {op}: {body.get('errorType', 'error')}: {body.get('errorMessage', body)}")
        rec.update({k: body.get(k) for k in ("lambda_ms", "sync_ms", "measure_ms", "cold", "measurements")})
        return body

    # ---- Bedrock -------------------------------------------------------------------------------
    def decide(self, system: str, user: str, model: str = BEDROCK_MODEL) -> tuple[dict[str, Any], dict[str, Any]]:
        """DECIDE through the Converse API with one tool, `decide`, whose input schema is
        models.Decision. Returns (decision input, usage/metadata). The loop's guards still apply to
        whatever comes back; this only asks the question."""
        from .models import DECISION_TOOL_SCHEMA
        tool = {"toolSpec": {"name": "decide", "description": "Choose the loop's next action from the findings, the profile and the history. Exactly one call.",
                             "inputSchema": {"json": DECISION_TOOL_SCHEMA}}}
        req = dict(modelId=model, system=[{"text": system}], messages=[{"role": "user", "content": [{"text": user}]}],
                   toolConfig={"tools": [tool], "toolChoice": {"tool": {"name": "decide"}}}, inferenceConfig={"maxTokens": 4096})
        t0 = time.time()
        try:
            r = self.bedrock().converse(**req)
        except Exception as e:  # forced tool choice may be refused with thinking on some models: fall back to auto + instruction
            msg = str(e)
            if "tool_choice" in msg or "toolChoice" in msg or "thinking" in msg:
                req["toolConfig"]["toolChoice"] = {"auto": {}}
                req["messages"][0]["content"][0]["text"] += "\n\nCall the `decide` tool exactly once with your decision. Do not answer in prose."
                r = self.bedrock().converse(**req)
            else:
                raise
        latency = int((time.time() - t0) * 1000)
        usage = r.get("usage", {})
        content = r.get("output", {}).get("message", {}).get("content", [])
        tool_use = next((c["toolUse"] for c in content if "toolUse" in c), None)
        text = " ".join(c.get("text", "") for c in content if "text" in c).strip()
        meta = {"request_id": _rid(r), "latency_ms": latency, "model": model, "stop_reason": r.get("stopReason"),
                "input_tokens": usage.get("inputTokens", 0), "output_tokens": usage.get("outputTokens", 0),
                "tool_choice": req["toolConfig"]["toolChoice"]}
        self.trace.add("decide", "bedrock", **meta, decision=(tool_use or {}).get("input"), text=text[:400] if not tool_use else "")
        if tool_use is None:
            raise RuntimeError(f"bedrock: the model answered in prose instead of calling `decide` (stop {r.get('stopReason')}): {text[:200]}")
        return tool_use["input"], meta

    # ---- the run's record ----------------------------------------------------------------------
    def flush_trace(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.trace.sha:                                  # the bucket first: it is the record that outlives the machine
            key = run_key(self.trace.sha, self.trace.run_id)
            self.s3().put_object(Bucket=self.bucket, Key=key, Body=self.trace.dumps().encode(), ContentType="application/x-ndjson")
            out["s3"] = f"s3://{self.bucket}/{key}"
        runs_dir = Path(os.environ.get("STAGE_READY_RUNS_DIR", RUNS_DIR))
        try:
            runs_dir.mkdir(parents=True, exist_ok=True)
            local = runs_dir / f"{self.trace.run_id}.jsonl"
            local.write_text(self.trace.dumps())
            out["local"] = str(local)
        except OSError:                                     # a read-only code directory (Lambda): the bucket has it
            pass
        return out
