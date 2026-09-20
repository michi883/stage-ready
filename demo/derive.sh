#!/bin/bash
# ============================================================================
#  Derived evaluation-corpus inputs — reproducible, documented, measured.
#
#    demo/derive.sh [archive-dir]        (default: $STAGE_READY_ARCHIVE or ~/mts)
#
#  The polished demo runs on three archived recordings untouched (Sandy, Ethel, Zach — README,
#  "Performers and numbers"). This script derives *additional* inputs for the evaluation set by
#  capture-like, deterministic edits only — trimming and frame-rate normalisation — so a long
#  recording becomes a bench-sized one that is still the performer's own pixels, performance and
#  audio. Nothing is painted, nothing is retouched, no threshold moves.
#
#  Every derivation writes its exact command, the original's SHA-256 and the result's SHA-256 to
#  demo/derived.json. The untouched originals remain the evaluation corpus.
#
#  michi_sample_v1.mp4 (45 s of michi.mp4 at 30 fps) is the near-threshold pass: run through the
#  pipeline 2026-09-19, every gate passes, separation 1.51x — by 0.01x, the shirt darker than the
#  curtain. Kept for the evaluation set; not in the demo lineup.
# ============================================================================
set -euo pipefail
ARCHIVE="${1:-${STAGE_READY_ARCHIVE:-$HOME/mts}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/derived.json"
cd "$ARCHIVE"

sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
FFV="$(ffmpeg -version | head -1)"

# ---- michi: the near-threshold pass (evaluation corpus) ----------------------------------
# michi.mp4 is a 3 min 55 s club recording at 59.94 fps. 45 s from 30 s in, where the performer
# is standing at one distance mid-frame; 30 fps by dropping frames (fps filter, deterministic);
# video re-encoded once with a single thread (x264 output is then reproducible); audio copied,
# cut at the packet boundary (≤ 21 ms), bit-identical within the cut.
SRC=michi.mp4; DST=michi_sample_v1.mp4
CMD="ffmpeg -v error -y -ss 30 -t 45 -i $SRC -vf fps=30 -c:v libx264 -crf 18 -preset medium -threads 1 -pix_fmt yuv420p -c:a copy -movflags +faststart $DST"
if [ ! -f "$DST" ]; then eval "$CMD"; fi

python3 - "$OUT" "$SRC" "$(sha "$SRC")" "$DST" "$(sha "$DST")" "$CMD" "$FFV" <<'EOF'
import json, sys, datetime
out, src, ssha, dst, dsha, cmd, ffv = sys.argv[1:]
d = {"note": "Derived inputs for the evaluation corpus. The polished demo runs on the three archived recordings untouched (Sandy, Ethel, Zach).",
     "ffmpeg": ffv, "derived": {}}
try:
    d = json.load(open(out)); d["ffmpeg"] = ffv
except FileNotFoundError:
    pass
d.setdefault("derived", {})
d["derived"]["michi"] = {"role": "evaluation corpus (not in the demo)", "original": src, "original_sha256": ssha, "output": dst, "output_sha256": dsha,
                         "command": cmd, "edits": ["trim 30 s → 75 s", "59.94 → 30 fps (frames dropped, none interpolated)", "video re-encoded once (x264 crf 18, 1 thread)", "audio stream copied"],
                         "derived_on": datetime.date.today().isoformat()}
d["demo_lineup"] = {"sandy": "archived recording, unchanged", "ethel": "archived recording, unchanged", "zach": "archived recording, unchanged — attempt 2 rendered 2026-09-19 at the strategy's bounds (1.45x)"}
json.dump(d, open(out, "w"), indent=2, ensure_ascii=False); open(out, "a").write("\n")
print(f"{dst}: {dsha[:16]}…  from {src}: {ssha[:16]}…")
EOF
echo "written: $OUT"
