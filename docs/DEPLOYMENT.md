# Deploy the AWS hybrid

The existing judge endpoint is https://d4nh99blf9f5j.cloudfront.net/. Deployment is not necessary
to review the project or replay its fixtures. The commands below create or update AWS resources
in the operator's account and should be run from a source checkout.

## Prerequisites

- Python 3.12 for the deployment build; the functions target Python 3.12 on arm64.
- AWS credentials on boto3's default chain (environment, shared profile, or role), with access
  to S3, IAM roles/policies, Lambda/layers, CloudFront/OAC, CloudWatch Logs, and Bedrock Converse.
- Access to the configured Bedrock model in the chosen region. The submitted runs used
  `global.anthropic.claude-sonnet-4-6`; availability is account-dependent.
- A globally unique S3 bucket name. The repository's default `stage-ready-videos` belongs to
  the existing deployment; choose your own bucket for a new account.
- The private judge bundle or complete archive, installed as described in
  [REPRODUCING.md](REPRODUCING.md), plus the separately downloaded U²-Net model.
- For a new vision layer, a trusted statically linked **Linux arm64** FFmpeg executable.
  A macOS binary or Linux x86 binary will not work. Record its source, version, license, and
  SHA-256 with the deployment; the build script records the hash, but does not download FFmpeg.

The external macOS renderer is not deployed. Live processing on AWS serves already prepared
artifacts from S3. A cache miss cannot render a fresh upload.

## 1. Install and configure

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/build.txt -r requirements/aws.txt -r requirements/headless.txt
python -m pip install --no-build-isolation -e .
python -m pip check
export AWS_PROFILE=your-profile
export STAGE_READY_AWS_REGION=us-east-1
export STAGE_READY_BUCKET=your-globally-unique-stage-ready-bucket
export STAGE_READY_ARCHIVE=/path/to/judge-bundle
python -m stage_ready aws status
python -m stage_ready bundle --verify "$STAGE_READY_ARCHIVE"
python -m stage_ready bundle --install "$STAGE_READY_ARCHIVE"
python -m stage_ready models fetch u2net_human_seg
```

Use your normal AWS authentication method; `AWS_PROFILE` is optional when using a role or
environment credentials. Do not paste credentials into code or commit `.aws/`, `.env`, or
`.stage_ready/`. The application does not load `.env` files automatically.

## 2. Build pinned deployment dependencies

```bash
python scripts/build_lambda.py --ffmpeg /path/to/static-linux-arm64/ffmpeg
```

This downloads exact SDK versions from `requirements/aws.txt` into `build/lambda-sdk/`, and
the arm64 OpenCV 5/NumPy wheels from `requirements/headless.txt` into `build/layer/python/`.
It also copies the SDK into the vision layer and FFmpeg into `build/layer/bin/ffmpeg` with
executable permissions. `build/layer-build.json` records the pins and FFmpeg hash. The API ZIP
vendors the same SDK, so it does not depend on the changing SDK supplied by Lambda's runtime.

The script refuses to mix packages into an existing output. For a rebuild use a new directory:

```bash
python scripts/build_lambda.py --out build/rebuild --ffmpeg /path/to/static-linux-arm64/ffmpeg
export STAGE_READY_SDK_DIR="$PWD/build/rebuild/lambda-sdk"
```

Use `build/rebuild/layer` in the next command if rebuilding. To build only the API SDK while
reusing an existing vision layer, omit `--ffmpeg`. No build command makes AWS calls.

## 3. Deploy measurement and sync data

```bash
python -m stage_ready aws deploy --layer build/layer
python -m stage_ready aws sync brian_padded ethel zach sandy zach_padded
```

`aws deploy` creates the private bucket if needed, the measurement execution role, the layer,
and `stage-ready-measure`. The function uses arm64, 3,008 MB RAM, 2,048 MB temporary storage,
and a 900-second timeout. The layer supplies `cv2`, NumPy, the pinned SDK, and FFmpeg.

`aws sync` uploads workdirs, source videos, prepared renders, and the DNN model to the private
bucket. Files are keyed by source hash. It requires the actual media; the public Git checkout
alone is insufficient. Reusing an existing bucket/function updates resources with those names;
use an isolated account or the documented name overrides when appropriate.

## 4. Deploy the browser endpoint

```bash
python -m stage_ready aws web-deploy
```

This publishes the UI and linked demo media under `public/`, deploys the streaming API Lambda,
and creates CloudFront with two origins: private S3 for static content and an IAM-authorized
Lambda Function URL for `/api/*`. It grants that distribution access to the public prefix and
API and prints the CloudFront URL. Initial distribution deployment can take several minutes.

Keep `.stage_ready/deploy.json` private and retain it for subsequent updates: it identifies the
distribution and origin access controls. The deployment code owns the bucket's CloudFront policy;
use a dedicated bucket, not one with unrelated policies or data. If deployment is interrupted,
inspect resources before retrying; this is a provisioning script, not a transactional rollback.

For static-only updates:

```bash
python -m stage_ready aws web-publish
```

For Python, profile, or fixture changes, rerun `aws web-deploy`. For measurement-code changes,
rerun `aws deploy` (without `--layer` to reuse the most recently published layer). These are
different updates: publishing the UI does not replace the API or measurement code.

## Configuration

| Variable | Default / purpose |
| --- | --- |
| `STAGE_READY_AWS_REGION` | `us-east-1` |
| `STAGE_READY_BUCKET` | `stage-ready-videos`; override for your account |
| `STAGE_READY_LAMBDA` | `stage-ready-measure` |
| `STAGE_READY_WEB_LAMBDA` | `stage-ready-web` |
| `STAGE_READY_BEDROCK_MODEL` | `global.anthropic.claude-sonnet-4-6` |
| `STAGE_READY_LWA_LAYER` | Version 27 of the public arm64 Lambda Web Adapter in us-east-1; supply a layer ARN in your region if different |
| `STAGE_READY_SDK_DIR` | `build/lambda-sdk` under the checkout |
| `STAGE_READY_ARCHIVE` | `~/mts`; set to the private bundle or archive for sync/local measurement |
| `STAGE_READY_MODELS_DIR` | `models/`; measurement Lambda uses `/tmp/models` |
| `STAGE_READY_RUNS_DIR` | `.stage_ready/runs`; API Lambda uses `/tmp/runs` |

## Verify and operate

Open the printed endpoint: the default mode must display **demo · cached**. Run all three
sample cases and Sandy's `?demo=1&clip=sandy` reshoot case. Verify media playback and the Trace
view. Then, with model access and prepared S3 data, run one live hybrid case using `?demo=0`.
The live trace includes measurement/model request IDs, timings, and decisions; traces are also
written under `runs/<source-sha>/` in S3. Check CloudWatch logs for either Lambda on failures.

The public endpoint has no per-user authentication or rate limiting. Live runs consume AWS
resources; configure account budgets and usage monitoring for the demonstration. S3 content
outside `public/` stays private, but anything published in that prefix is served by CloudFront.
The September cost estimates in the technical report are historical measurements/estimates,
not a current pricing guarantee.

To retire the deployment, disable/delete its CloudFront distribution and origins, remove its
Lambda URLs/functions and unused layer versions, and remove the dedicated roles/log groups.
Review and back up media/traces before deleting any S3 data. No cleanup is run automatically.
