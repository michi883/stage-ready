#!/bin/bash
# ============================================================================
#  Derived demo inputs — reproducible, documented, measured.
#
#    demo/derive.sh [archive-dir]        (default: $STAGE_READY_ARCHIVE or ~/mts)
#
#  The polished demo runs on three inputs. Two are the archived recordings untouched
#  (Ethel's red-on-red retry and Sandy's unrecoverable walk-in are real, and stay real).
#  One is derived from an original by capture-like, deterministic edits only — trimming and
#  frame-rate normalisation — so it is short enough for a bench and still the performer's own
#  pixels, performance and audio. Nothing is painted, nothing is retouched, no threshold moves.
#
#  Every derivation writes its exact command, the original's SHA-256 and the result's SHA-256
#  to demo/derived.json. The untouched originals remain the evaluation corpus.
#
#  Zach (zach_sain_v2.mov) is deliberately NOT derived: his measured separation is 1.00x — his
#  black shirt is the curtain's luminance — and a passing control would need a different shirt.
#  That is altering the performer, which this script does not do (README, "Performers").
# ============================================================================
set -euo pipefail
ARCHIVE="${1:-${STAGE_READY_ARCHIVE:-$HOME/mts}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/derived.json"
cd "$ARCHIVE"

sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
FFV="$(ffmpeg -version | head -1)"

# ---- michi: the ACCEPT input ----------------------------------------------------------
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
d = {"note": "Derived demo inputs. Originals untouched; Ethel and Sandy run on their originals (identity). Zach not derived: see demo/derive.sh.",
     "ffmpeg": ffv, "derived": {}}
try:
    d = json.load(open(out)); d["ffmpeg"] = ffv
except FileNotFoundError:
    pass
d.setdefault("derived", {})
d["derived"]["michi"] = {"role": "ACCEPT", "original": src, "original_sha256": ssha, "output": dst, "output_sha256": dsha,
                         "command": cmd, "edits": ["trim 30 s → 75 s", "59.94 → 30 fps (frames dropped, none interpolated)", "video re-encoded once (x264 crf 18, 1 thread)", "audio stream copied"],
                         "derived_on": datetime.date.today().isoformat()}
d["derived"]["ethel"] = {"role": "ADAPT", "original": "ethel_chadwick_v2.mp4", "output": "ethel_chadwick_v2.mp4", "edits": [], "note": "identity — the archived recording, unchanged"}
d["derived"]["sandy"] = {"role": "REFUSE", "original": "sandy_hackett_v2.mp4", "output": "sandy_hackett_v2.mp4", "edits": [], "note": "identity — the archived recording, unchanged"}
d["not_derived"] = {"zach": "zach_sain_v2.mov measures separation 1.00x (retry at the strategy's bounds: 1.45x): the black shirt is the curtain's luminance. A passing control would need different clothing, which is altering the performer. Stopped; reported."}
json.dump(d, open(out, "w"), indent=2, ensure_ascii=False); open(out, "a").write("\n")
print(f"{dst}: {dsha[:16]}…  from {src}: {ssha[:16]}…")
EOF
echo "written: $OUT"
