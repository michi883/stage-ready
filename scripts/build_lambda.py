#!/usr/bin/env python3
"""Build pinned AWS SDK files and, optionally, the Python 3.12 / arm64 vision layer.

No AWS calls. Supply a trusted, statically linked Linux arm64 ffmpeg for --ffmpeg.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def install(requirements, target):
    # Refuse stale outputs: mixed dependency versions would defeat the pins.
    if target.exists():
        raise SystemExit(f"{target} already exists; choose a new --out directory")
    subprocess.run([sys.executable, "-m", "pip", "install", "--only-binary=:all:",
                    "--platform", "manylinux_2_28_aarch64", "--platform", "manylinux2014_aarch64",
                    "--implementation", "cp", "--python-version", "3.12", "--no-compile",
                    "--target", str(target), "-r", str(ROOT / "requirements" / requirements)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build")
    parser.add_argument("--ffmpeg", type=Path, help="static Linux arm64 ffmpeg; also builds the vision layer")
    args = parser.parse_args()
    if args.ffmpeg:
        with args.ffmpeg.open("rb") as source:
            header = source.read(20)
        if header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\xb7\x00":
            parser.error("--ffmpeg must be a 64-bit little-endian Linux arm64 ELF executable")
        if (args.out / "layer").exists():
            parser.error("layer already exists; choose a new --out directory")
    sdk = args.out / "lambda-sdk"
    install("aws.txt", sdk)
    if args.ffmpeg:
        layer = args.out / "layer"
        install("headless.txt", layer / "python")
        shutil.copytree(sdk, layer / "python", dirs_exist_ok=True)
        (layer / "bin").mkdir()
        shutil.copyfile(args.ffmpeg, layer / "bin" / "ffmpeg")
        (layer / "bin" / "ffmpeg").chmod(0o755)
        (args.out / "layer-build.json").write_text(json.dumps({
            "runtime": "python3.12", "architecture": "arm64",
            "ffmpeg_sha256": hashlib.sha256(args.ffmpeg.read_bytes()).hexdigest(),
            "requirements": {name: (ROOT / "requirements" / name).read_text() for name in ("aws.txt", "headless.txt")},
        }, indent=2) + "\n")
    print(f"SDK ready: {sdk.resolve()}")
    if args.ffmpeg:
        print(f"Layer ready: {(args.out / 'layer').resolve()}")


if __name__ == "__main__":
    main()
