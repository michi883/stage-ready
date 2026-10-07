# Reproduce the demo and measurements

## No credentials or media required

From a source checkout with Python 3.11+:

```bash
python3 -m unittest discover -s tests -v
python3 -m stage_ready run brian_padded ethel zach sandy
python3 -m stage_ready serve
```

The UI is at http://127.0.0.1:8765/. These commands replay committed measurements and decisions.
Without the private bundle, visual stand-ins are used instead of original video.

For a clean wheel build, install `requirements/build.txt` into a virtual environment and run
`python -m build --no-isolation`. Install `dist/stage_ready-0.2.0-py3-none-any.whl` in a second
environment and run `stage-ready run ethel` from outside the checkout. This verifies that
runtime assets travel with the package. Source archives include tests and documentation too.

## OpenCV without private media

```bash
python -m pip install -r requirements/headless.txt
python -m unittest discover -s tests -p test_vision_synthetic.py -v
```

This creates padded test images, decodes them with OpenCV 5, detects their picture area, and
checks the frame count and dimensions. It validates the vision runtime, not the performer
evaluation. OpenCV 4 is refused. Use the desktop `live.txt` or server `headless.txt`, never both.

## Recompute original measurements

Prerequisites: the private judge bundle from the project owner, OpenCV 5/NumPy, and FFmpeg on
`PATH` for decoded-audio MD5. The bundle is intentionally excluded from Git because it contains
performer footage. It includes prepared workdirs and archived renders; it does not include the
macOS renderer or support new recordings.

```bash
python -m stage_ready bundle --verify /path/to/judge-bundle
python -m stage_ready bundle --install /path/to/judge-bundle
export STAGE_READY_ARCHIVE=/path/to/judge-bundle
python -m stage_ready measure ethel
python -m unittest discover -s tests -v
```

`measure` prints every fixture value beside the recomputed value, with `!` for a different
status and `~` for a numeric difference beyond tolerance. Inspect those comparisons; a zero
process exit code alone is not an assertion that every archived number agrees. Codec differences
can cause small pixel/measurement variation. The expected original measurements are recorded in
the fixtures and technical report.

For the DNN second opinion used by Lambda:

```bash
python -m stage_ready models fetch u2net_human_seg
python -m stage_ready measure ethel --opinion dnn
python -m unittest discover -s tests -p test_vision.py -v
```

The model is downloaded from its registered upstream and verified by SHA-256. Missing media
causes archive-dependent tests to skip by default; if `STAGE_READY_ARCHIVE` is explicitly set,
the suite checks that Ethel's required media exists and fails when it is incomplete.

The owner can create a bundle from a complete archive:

```bash
python -m stage_ready bundle --out /path/to/judge-bundle --archive /path/to/archive
python -m stage_ready bundle --verify /path/to/judge-bundle
```

## Evaluation evidence

The [committed report](../demo/eval/EVALUATION.md) records the September 20 evaluation. Source
labels are in `demo/eval/set.json`; per-item traces, measurements, and scored outcomes are under
`demo/eval/results/{bedrock,rules}/`. Inspect those files without credentials.

`python -m stage_ready evaluate --report` regenerates the report from committed results and
rescoring logic, without making new measurements or model calls; it modifies report/summary
files. To perform a new evaluation, use a separate checkout with the complete evaluation archive,
FFmpeg, the model, and (for Bedrock) the pinned AWS dependencies and model access:

```bash
python -m stage_ready evaluate --agent rules --archive /path/to/full-evaluation-archive
python -m stage_ready evaluate --agent bedrock --archive /path/to/full-evaluation-archive
python -m stage_ready evaluate --report
```

The five-clip judge bundle is not the complete 19-case evaluation archive. `--prepare` additionally
requires the external macOS Red Curtain tools and can render new outputs; it is not needed for
the submitted replay. Bedrock evaluation makes billable calls and can choose different actions
on a rerun. Do not describe replayed evidence as a newly run evaluation.
