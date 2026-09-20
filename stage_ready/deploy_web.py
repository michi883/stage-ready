"""The public endpoint: CloudFront in front of the private bucket and a streaming Lambda.

    https://<distribution>.cloudfront.net/            the workspace (demo by default)
        /, /app.js, /style.css, /stills/<clip>/<f>    S3, prefix public/, through an origin access control —
                                                      the bucket stays private; CloudFront serves byte ranges
        /api/*                                        the Lambda `stage-ready-web`: stage_ready.server as it is,
                                                      behind the Lambda Web Adapter on a Function URL in
                                                      response-stream mode, so the SSE run streams through

Nothing here depends on the laptop: the API Lambda carries the code, the profile and the demo
fixtures; the media is the bucket's; live mode (`?demo=0`) calls the measurement Lambda and Bedrock
from the API Lambda's own role and takes the render as an S3 cache hit.

    python3 -m stage_ready aws web-deploy       everything below, idempotent; prints the URL
    python3 -m stage_ready aws web-publish      only the static files and media (a UI change)

Resources: the Lambda `stage-ready-web` + its role `stage-ready-web-role` + a public Function URL,
one CloudFront distribution + one origin access control, and a bucket policy statement granting
that distribution `s3:GetObject` on `public/*` only. Approximate cost at judge traffic: CloudFront
and Lambda inside the free tiers; S3 storage of the media and workdirs ≈ $0.03 / month.
"""
from __future__ import annotations

import io
import json
import mimetypes
import os
import time
import zipfile
from pathlib import Path
from typing import Any

from .aws import AWS, FUNCTION, ROOT, _rid
from .backends.cached import CLIPS

WEB_FUNCTION = os.environ.get("STAGE_READY_WEB_LAMBDA", "stage-ready-web")
WEB_ROLE = "stage-ready-web-role"
LWA_LAYER = "arn:aws:lambda:us-east-1:753240598075:layer:LambdaAdapterLayerArm64:27"   # AWS Lambda Web Adapter, public
PUBLIC = "public"
STATE = ROOT / ".stage_ready" / "deploy.json"
CACHE = {".html": "no-cache", ".js": "public, max-age=300", ".css": "public, max-age=300", ".json": "no-cache",
         ".mp4": "public, max-age=86400", ".mov": "public, max-age=86400", ".jpg": "public, max-age=86400"}


def _state() -> dict[str, Any]:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def _save(d: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=1))


# ---- static files and media --------------------------------------------------------------------
def publish_static(aws: AWS) -> dict[str, int]:
    """web/ and each clip's stills (symlinks resolved) → s3://bucket/public/…, with content types."""
    n_up = n_skip = 0
    items: list[tuple[Path, str]] = [(p, f"{PUBLIC}/{p.name}") for p in (ROOT / "web").iterdir() if p.is_file()]
    for d in sorted(CLIPS.iterdir()):
        st = d / "stills"
        if (d / "clip.json").exists() and st.is_dir():
            for f in sorted(st.iterdir()):
                if f.is_file() or f.is_symlink():
                    items.append((f.resolve(), f"{PUBLIC}/stills/{d.name}/{f.name}"))
    for src, key in items:
        if not src.exists():
            raise FileNotFoundError(f"{src} (a dangling still?)")
        ctype = mimetypes.guess_type(str(key))[0] or ("video/quicktime" if key.endswith(".mov") else "application/octet-stream")
        h = aws.head(key)
        if h and h.get("ContentLength") == src.stat().st_size and h.get("ContentType") == ctype:
            n_skip += 1
            continue
        aws.s3().upload_file(str(src), aws.bucket, key, ExtraArgs={"ContentType": ctype, "CacheControl": CACHE.get(src.suffix.lower(), "public, max-age=300")})
        n_up += 1
    return {"uploaded": n_up, "skipped": n_skip}


# ---- the API Lambda ------------------------------------------------------------------------------
def _web_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        def add(p: Path, arc: str, mode: int = 0o644):
            info = zipfile.ZipInfo(arc); info.date_time = (2026, 1, 1, 0, 0, 0); info.external_attr = mode << 16
            z.writestr(info, p.read_bytes())
        for p in sorted((ROOT / "stage_ready").rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc"):
                add(p, str(p.relative_to(ROOT)))
        for p in sorted((ROOT / "profiles").glob("*.json")):
            add(p, str(p.relative_to(ROOT)))
        for p in sorted((ROOT / "web").iterdir()):
            if p.is_file():
                add(p, str(p.relative_to(ROOT)))
        for p in sorted(CLIPS.rglob("*.json")):              # fixtures only — never the stills
            add(p, str(p.relative_to(ROOT)))
        run_sh = "#!/bin/bash\n# Lambda Web Adapter starts this; the server listens on $PORT.\nexec python3 -m stage_ready serve --host 0.0.0.0 --port \"${PORT:-8080}\"\n"
        info = zipfile.ZipInfo("run.sh"); info.date_time = (2026, 1, 1, 0, 0, 0); info.external_attr = 0o755 << 16
        z.writestr(info, run_sh)
    return buf.getvalue()


def ensure_web_role(aws: AWS) -> str:
    iam = aws.session.client("iam")
    from botocore.exceptions import ClientError
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
    try:
        arn = iam.get_role(RoleName=WEB_ROLE)["Role"]["Arn"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        arn = iam.create_role(RoleName=WEB_ROLE, AssumeRolePolicyDocument=json.dumps(trust), Description="Stage Ready: the public API")["Role"]["Arn"]
        iam.attach_role_policy(RoleName=WEB_ROLE, PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
        time.sleep(8)
    acct = aws.session.client("sts").get_caller_identity()["Account"]
    policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"], "Resource": [f"arn:aws:s3:::{aws.bucket}", f"arn:aws:s3:::{aws.bucket}/*"]},
        {"Effect": "Allow", "Action": ["lambda:InvokeFunction"], "Resource": [f"arn:aws:lambda:{aws.region}:{acct}:function:{FUNCTION}"]},
        {"Effect": "Allow", "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"], "Resource": ["*"]},
    ]}
    iam.put_role_policy(RoleName=WEB_ROLE, PolicyName="stage-ready-web", PolicyDocument=json.dumps(policy))
    return arn


def deploy_web_lambda(aws: AWS, role_arn: str) -> dict[str, str]:
    from botocore.exceptions import ClientError
    from .aws import BEDROCK_MODEL
    lam = aws.lam()
    code = _web_zip()
    env = {"Variables": {"PORT": "8080", "AWS_LAMBDA_EXEC_WRAPPER": "/opt/bootstrap", "AWS_LWA_INVOKE_MODE": "response_stream",
                         "STAGE_READY_BUCKET": aws.bucket, "STAGE_READY_LAMBDA": FUNCTION, "STAGE_READY_PROCESS": "s3",
                         "STAGE_READY_BEDROCK_MODEL": BEDROCK_MODEL, "STAGE_READY_RUNS_DIR": "/tmp/runs", "PYTHONUNBUFFERED": "1"}}
    cfg = dict(Runtime="python3.12", Role=role_arn, Handler="run.sh", Timeout=900, MemorySize=1024, Architectures=["arm64"],
               Layers=[LWA_LAYER], Environment=env, Description="Stage Ready: the workspace and its API (stage_ready.server behind the Lambda Web Adapter)")
    try:
        lam.get_function(FunctionName=WEB_FUNCTION)
        lam.update_function_code(FunctionName=WEB_FUNCTION, ZipFile=code, Architectures=["arm64"])
        _wait(lam)
        r = lam.update_function_configuration(FunctionName=WEB_FUNCTION, **{k: v for k, v in cfg.items() if k != "Architectures"})
        aws.trace.add("deploy", "lambda", op="update_function", request_id=_rid(r), function=WEB_FUNCTION, bytes=len(code))
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        r = lam.create_function(FunctionName=WEB_FUNCTION, Code={"ZipFile": code}, PackageType="Zip", **cfg)
        aws.trace.add("deploy", "lambda", op="create_function", request_id=_rid(r), function=WEB_FUNCTION, bytes=len(code))
    _wait(lam)
    # The Function URL is IAM-only, in response-stream mode; CloudFront signs its requests through an
    # origin access control (below), so the API is reachable only through the public endpoint. (A
    # public NONE-auth URL is refused in this account regardless of its resource policy.)
    try:
        u = lam.get_function_url_config(FunctionName=WEB_FUNCTION)
        if u.get("InvokeMode") != "RESPONSE_STREAM" or u.get("AuthType") != "AWS_IAM":
            u = lam.update_function_url_config(FunctionName=WEB_FUNCTION, AuthType="AWS_IAM", InvokeMode="RESPONSE_STREAM")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        u = lam.create_function_url_config(FunctionName=WEB_FUNCTION, AuthType="AWS_IAM", InvokeMode="RESPONSE_STREAM")
    try:
        lam.remove_permission(FunctionName=WEB_FUNCTION, StatementId="public-url")
    except ClientError:
        pass
    return {"function_url": u["FunctionUrl"], "function": WEB_FUNCTION}


def _wait(lam, timeout: float = 180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        c = lam.get_function_configuration(FunctionName=WEB_FUNCTION)
        if c.get("LastUpdateStatus", "Successful") == "Successful" and c.get("State", "Active") == "Active":
            return
        time.sleep(2)


# ---- CloudFront ----------------------------------------------------------------------------------
def deploy_cloudfront(aws: AWS, function_url: str) -> dict[str, str]:
    cf = aws.session.client("cloudfront")
    st = _state()
    acct = aws.session.client("sts").get_caller_identity()["Account"]
    bucket_domain = f"{aws.bucket}.s3.{aws.region}.amazonaws.com"
    api_domain = function_url.replace("https://", "").rstrip("/")
    # the origin access control: CloudFront signs its requests to S3; the bucket stays private
    oac_id = st.get("oac_id")
    if not oac_id:
        r = cf.create_origin_access_control(OriginAccessControlConfig={"Name": "stage-ready-oac", "Description": "Stage Ready public/ prefix",
                                                                       "SigningProtocol": "sigv4", "SigningBehavior": "always", "OriginAccessControlOriginType": "s3"})
        oac_id = r["OriginAccessControl"]["Id"]
        st["oac_id"] = oac_id; _save(st)
    lambda_oac_id = st.get("lambda_oac_id")
    if not lambda_oac_id:
        r = cf.create_origin_access_control(OriginAccessControlConfig={"Name": "stage-ready-api-oac", "Description": "Stage Ready API (Lambda URL)",
                                                                       "SigningProtocol": "sigv4", "SigningBehavior": "always", "OriginAccessControlOriginType": "lambda"})
        lambda_oac_id = r["OriginAccessControl"]["Id"]
        st["lambda_oac_id"] = lambda_oac_id; _save(st)
    # managed policies: CachingOptimized, CachingDisabled, AllViewerExceptHostHeader
    CACHING_OPTIMIZED, CACHING_DISABLED, ALL_VIEWER_EXCEPT_HOST = "658327ea-f89d-4fab-a63d-7e88639e58f6", "4135ea2d-6df8-44a3-9df3-4b5a84be39ad", "b689b0a8-53d0-40ab-baf2-68738e2966ac"
    config = {
        "CallerReference": st.get("caller_reference") or f"stage-ready-{int(time.time())}",
        "Comment": "Stage Ready — the workspace (demo by default) and its API",
        "Enabled": True, "DefaultRootObject": "index.html", "HttpVersion": "http2and3", "PriceClass": "PriceClass_100", "IsIPV6Enabled": True,
        "Origins": {"Quantity": 2, "Items": [
            {"Id": "s3-public", "DomainName": bucket_domain, "OriginPath": f"/{PUBLIC}", "OriginAccessControlId": oac_id,
             "S3OriginConfig": {"OriginAccessIdentity": ""}, "CustomHeaders": {"Quantity": 0}},
            {"Id": "api", "DomainName": api_domain, "OriginPath": "", "CustomHeaders": {"Quantity": 0}, "OriginAccessControlId": lambda_oac_id,
             "CustomOriginConfig": {"HTTPPort": 80, "HTTPSPort": 443, "OriginProtocolPolicy": "https-only", "OriginReadTimeout": 60, "OriginKeepaliveTimeout": 5,
                                    "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]}}},
        ]},
        "DefaultCacheBehavior": {"TargetOriginId": "s3-public", "ViewerProtocolPolicy": "redirect-to-https", "Compress": True,
                                 "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"], "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}},
                                 "CachePolicyId": CACHING_OPTIMIZED},
        "CacheBehaviors": {"Quantity": 1, "Items": [
            {"PathPattern": "/api/*", "TargetOriginId": "api", "ViewerProtocolPolicy": "redirect-to-https", "Compress": False,
             "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"], "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}},
             "CachePolicyId": CACHING_DISABLED, "OriginRequestPolicyId": ALL_VIEWER_EXCEPT_HOST}]},
        "ViewerCertificate": {"CloudFrontDefaultCertificate": True, "MinimumProtocolVersion": "TLSv1.2_2021"},
    }
    def overlay(base, new):
        """Recursively lay `new` over `base`; lists of Items are matched by Id / PathPattern so
        CloudFront's complete-config requirement on update is met without restating every field."""
        if isinstance(base, dict) and isinstance(new, dict):
            out = dict(base)
            for k, v in new.items():
                out[k] = overlay(base.get(k), v) if k in base else v
            return out
        if isinstance(base, list) and isinstance(new, list) and all(isinstance(x, dict) for x in base + new):
            key = lambda d: d.get("Id") or d.get("PathPattern")
            by = {key(d): d for d in base}
            return [overlay(by[key(d)], d) if key(d) in by else d for d in new]
        return new

    dist_id = st.get("distribution_id")
    if dist_id:
        cur = cf.get_distribution_config(Id=dist_id)
        config["CallerReference"] = cur["DistributionConfig"]["CallerReference"]
        merged = overlay(cur["DistributionConfig"], config)
        r = cf.update_distribution(Id=dist_id, IfMatch=cur["ETag"], DistributionConfig=merged)
        domain = r["Distribution"]["DomainName"]; arn = r["Distribution"]["ARN"]
    else:
        st["caller_reference"] = config["CallerReference"]; _save(st)
        r = cf.create_distribution(DistributionConfig=config)
        dist_id = r["Distribution"]["Id"]; domain = r["Distribution"]["DomainName"]; arn = r["Distribution"]["ARN"]
        st.update({"distribution_id": dist_id, "domain": domain}); _save(st)
        aws.trace.add("deploy", "cloudfront", op="create_distribution", request_id=_rid(r), distribution=dist_id)
    # the bucket policy: only this distribution, only public/*
    policy = {"Version": "2012-10-17", "Statement": [{
        "Sid": "AllowCloudFrontPublicPrefix", "Effect": "Allow", "Principal": {"Service": "cloudfront.amazonaws.com"},
        "Action": "s3:GetObject", "Resource": f"arn:aws:s3:::{aws.bucket}/{PUBLIC}/*",
        "Condition": {"StringEquals": {"AWS:SourceArn": arn}}}]}
    aws.s3().put_bucket_policy(Bucket=aws.bucket, Policy=json.dumps(policy))
    # the function's resource policy: only this distribution may invoke the URL
    from botocore.exceptions import ClientError
    lam = aws.lam()
    # Both actions: the Lambda URL service checks InvokeFunctionUrl for the URL and InvokeFunction for
    # the call behind it — with only the first, an OAC-signed request is refused with a 403.
    for sid, action in (("cloudfront-oac", "lambda:InvokeFunctionUrl"), ("cloudfront-oac-invoke", "lambda:InvokeFunction")):
        try:
            lam.remove_permission(FunctionName=WEB_FUNCTION, StatementId=sid)
        except ClientError:
            pass
        lam.add_permission(FunctionName=WEB_FUNCTION, StatementId=sid, Action=action, Principal="cloudfront.amazonaws.com", SourceArn=arn)
    st.update({"distribution_id": dist_id, "domain": domain, "distribution_arn": arn, "function_url": function_url}); _save(st)
    return {"distribution_id": dist_id, "domain": domain, "url": f"https://{domain}/"}


def wait_deployed(aws: AWS, dist_id: str, timeout: float = 900) -> str:
    cf = aws.session.client("cloudfront")
    t0 = time.time()
    while time.time() - t0 < timeout:
        status = cf.get_distribution(Id=dist_id)["Distribution"]["Status"]
        if status == "Deployed":
            return status
        time.sleep(10)
    return "InProgress"


def invalidate(aws: AWS, dist_id: str, paths: list[str] | None = None) -> str:
    cf = aws.session.client("cloudfront")
    r = cf.create_invalidation(DistributionId=dist_id, InvalidationBatch={"Paths": {"Quantity": len(paths or ["/*"]), "Items": paths or ["/*"]}, "CallerReference": str(time.time())})
    return r["Invalidation"]["Id"]


def deploy(aws: AWS, wait: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["static"] = publish_static(aws)
    role = ensure_web_role(aws); out["role"] = role
    out.update(deploy_web_lambda(aws, role))
    out.update(deploy_cloudfront(aws, out["function_url"]))
    if wait:
        out["status"] = wait_deployed(aws, out["distribution_id"])
    return out
