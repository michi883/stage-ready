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

# ---- sandy: the repairable framing problem without the walk-in (polished demo) ---------------
# sandy_hackett_v2.mp4 walks into a close-up 4.5 s in and then holds one distance; the full take
# fails the head-height gates on that walk-in (the evaluation corpus keeps it). 4 s → 25 s is the
# longest stretch from the first steady moment whose head-top spread (2.8 % of the picture, against
# 8.9 % over the take) leaves a margin under the 2 % canvas gate after the solve; a first candidate,
# 4 s → 34 s, measured 2.3 % on the canvas and was rejected — he bobs and leans from 19 s on. The
# pillarbox is in every frame, so the fixer still has its job. 25 fps unchanged; video re-encoded
# once, single thread; audio copied.
SRC2=sandy_hackett_v2.mp4; DST2=sandy_hackett_v2_demo.mp4
CMD2="ffmpeg -v error -y -ss 4 -t 21 -i $SRC2 -c:v libx264 -crf 18 -preset medium -threads 1 -pix_fmt yuv420p -c:a copy -movflags +faststart $DST2"
if [ ! -f "$DST2" ]; then eval "$CMD2"; fi

# ---- zach: a real alternate take (polished demo) -----------------------------------------------
# zach_sain_v1.mov is the other recording of Zach in hand: the same black shirt and red wall, but
# mint trousers, the crown inside the picture, one distance, 137 s at 480×404 with a 180° display
# matrix. 15 s → 75 s. Re-encoding bakes the container's rotation flag into the pixels (the
# picture is unchanged, upright either way); 30 fps unchanged; audio re-encoded (the .mov's audio is
# not carried into MP4 as-is). setpts/asetpts zero the timestamps: after seeking, the first frame
# otherwise carries a 33 ms offset that the pipeline's demux fills with a duplicate frame — the
# render then has one frame more than the source, and the live frame-count gate (rightly) fails it.
SRC3=zach_sain_v1.mov; DST3=zach_sain_v1_demo.mp4
CMD3="ffmpeg -v error -y -ss 15 -t 60 -i $SRC3 -vf setpts=PTS-STARTPTS -af asetpts=PTS-STARTPTS -c:v libx264 -crf 18 -preset medium -threads 1 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart $DST3"
if [ ! -f "$DST3" ]; then eval "$CMD3"; fi

# ---- zach_padded: the controlled repair demonstration (polished demo) -----------------------------
# A demo input whose defect is injected on purpose, on a base that verifies on its own: Zach's demo
# recording (zach_sain_v1_demo.mp4, every gate on the first pass, separation 2.37×) placed unscaled
# and centred inside a 1280×720 black canvas — the padded export a phone clip gets when it is dropped
# on a 720p timeline. Nothing inside the picture is scaled, moved, trimmed or retimed; the video is
# re-encoded once (the pad needs a new frame), the audio stream is copied. This is not a naturally
# occurring defect and is never presented as one (README, "Polished demo vs evaluation corpus").
SRC4=zach_sain_v1_demo.mp4; DST4=zach_sain_v1_padded.mp4
CMD4="ffmpeg -v error -y -i $SRC4 -vf pad=1280:720:400:158:black -c:v libx264 -crf 18 -preset medium -threads 1 -pix_fmt yuv420p -c:a copy -movflags +faststart $DST4"
if [ ! -f "$DST4" ]; then eval "$CMD4"; fi

# ---- brian_padded: the controlled repair demonstration, on Brian (polished demo, 2026-09-20 pm) ----
# The same construction on a different performer, at the user's request (the left card should not
# be a second Zach): brian_shirley_v2.mp4, untouched and verified on its own with today's pipeline
# (crown inside on every frame, separation 2.91x, head 0.7 %, 1285 frames), placed unscaled and
# centred inside a 2560x1440 black canvas — the padded export a Full-HD clip gets when it is dropped
# on a QHD timeline. Nothing inside the picture is scaled, moved, trimmed or retimed; one re-encode;
# the audio stream is copied.
SRC5=brian_shirley_v2.mp4; DST5=brian_shirley_v2_padded.mp4
CMD5="ffmpeg -v error -y -i $SRC5 -vf pad=2560:1440:320:180:black -c:v libx264 -crf 18 -preset medium -threads 1 -pix_fmt yuv420p -c:a copy -movflags +faststart $DST5"
if [ ! -f "$DST5" ]; then eval "$CMD5"; fi

python3 - "$OUT" "$SRC" "$(sha "$SRC")" "$DST" "$(sha "$DST")" "$CMD" "$FFV" "$SRC2" "$(sha "$SRC2")" "$DST2" "$(sha "$DST2")" "$CMD2" "$SRC3" "$(sha "$SRC3")" "$DST3" "$(sha "$DST3")" "$CMD3" "$SRC4" "$(sha "$SRC4")" "$DST4" "$(sha "$DST4")" "$CMD4" "$SRC5" "$(sha "$SRC5")" "$DST5" "$(sha "$DST5")" "$CMD5" <<'EOF'
import json, sys, datetime
out, src, ssha, dst, dsha, cmd, ffv, src2, ssha2, dst2, dsha2, cmd2, src3, ssha3, dst3, dsha3, cmd3, src4, ssha4, dst4, dsha4, cmd4, src5, ssha5, dst5, dsha5, cmd5 = sys.argv[1:]
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
d["derived"]["sandy_demo"] = {"role": "polished demo candidate (Sandy)", "original": src2, "original_sha256": ssha2, "output": dst2, "output_sha256": dsha2,
                              "time_range": "00:00:04 → 00:00:25 (21 s)", "command": cmd2,
                              "edits": ["trim 4 s → 25 s (from the first steady moment; the walk-in at 0–4.5 s and the bobbing from 19 s on excluded)", "25 fps unchanged", "video re-encoded once (x264 crf 18, 1 thread)", "audio stream copied", "pillarbox and framing untouched"],
                              "rejected_candidate": {"time_range": "00:00:04 → 00:00:34 (30 s)", "measured": "after the fix and the pipeline's own solve: head spread 2.3 % on the canvas against the 2 % gate (drift 3.6 px, separation 1.77×, matte 103 %) — failed honestly, not used"},
                              "derived_on": datetime.date.today().isoformat()}
d["derived"]["zach_demo"] = {"role": "polished demo candidate (Zach)", "original": src3, "original_sha256": ssha3, "output": dst3, "output_sha256": dsha3,
                             "time_range": "00:00:15 → 00:01:15 (60 s)", "command": cmd3,
                             "edits": ["alternate real take (zach_sain_v1.mov, mint trousers, crown inside the picture)", "trim 15 s → 75 s", "30 fps unchanged; timestamps zeroed (setpts/asetpts) so the frame count is unambiguous — 1800 by the container, by decoding, and by the pipeline's demux", "container rotation (180°) baked into the pixels by the re-encode — the picture is unchanged", "video re-encoded once (x264 crf 18, 1 thread)", "audio re-encoded AAC 160k (the .mov audio is not MP4-compatible as-is)"],
                             "rejected_candidate": {"note": "the same excerpt without the timestamp zeroing: the source decodes to 1800 frames but the pipeline's demux emitted 1801 (a duplicate at t=0), so the render had 1801 — caught by the live frame-count gate on AWS (FFmpeg decoder: 1801 ≠ 1800) while the local check, which counts through AVFoundation, read 1801 = 1801. Not used."},
                             "derived_on": datetime.date.today().isoformat()}
d["derived"]["zach_padded"] = {"role": "polished demo: the controlled repair demonstration (Zach, padded)", "kind": "controlled demo input — the defect is injected on purpose",
                               "original": src4, "original_sha256": ssha4, "original_role": "the clean base: Zach's demo recording, verified on its own (2.37×, head 0.7 %, 1800 frames) before the defect was injected",
                               "output": dst4, "output_sha256": dsha4, "time_range": "00:00:00 → 00:01:00 (60 s — the whole base, untrimmed)", "command": cmd4,
                               "injected_defect": "picture_area: the 480×404 picture placed unscaled and centred inside a 1280×720 black canvas (+400+158)",
                               "edits": ["no trim, no frame-rate change, no scaling, no mis-centering — 1800 frames, 30 fps, timestamps as the base", "video re-encoded once (x264 crf 18, 1 thread); inside the picture the pixels differ from the base by the compression pass only (frame 900: mean 0.86/255, p99 5/255)", "audio stream copied (decoded MD5 identical to the base)"],
                               "measured": "2026-09-20, real pipeline + live loop (Lambda + Bedrock): inspect ✗ picture_area only → fix.reframe crop 480:404:400:158, head_target 0.334 unchanged, 0 pixels invented → re-inspect passes → process.standard → verify ✓ separation 2.36×, matte 102 %, head 0.7 % / 1.9 px, 1800 frames, audio equal → deliver",
                               "derived_on": datetime.date.today().isoformat()}
d["derived"]["brian_padded"] = {"role": "polished demo: the controlled repair demonstration (Brian, padded) — the left card", "kind": "controlled demo input — the defect is injected on purpose",
                                "original": src5, "original_sha256": ssha5, "original_role": "the clean base: the untouched recording, verified on its own with today's pipeline before the defect was injected (2026-09-20: separation 2.91×, matte 100 %, head 0.7 % / 1.2 px, 1285 frames, audio equal; one warning — under-lit, grade held at ×1.25)",
                                "output": dst5, "output_sha256": dsha5, "time_range": "00:00:00 → 00:00:42.8 (the whole recording, untrimmed)", "command": cmd5,
                                "injected_defect": "picture_area: the 1920×1080 picture placed unscaled and centred inside a 2560×1440 black canvas (+320+180)",
                                "edits": ["no trim, no frame-rate change, no scaling, no mis-centering — 1285 frames, 30 fps, timestamps as the source", "video re-encoded once (x264 crf 18, 1 thread); inside the picture the pixels differ from the source by the compression pass only", "audio stream copied (decoded MD5 identical to the source)"],
                                "derived_on": datetime.date.today().isoformat()}
d["evaluation_corpus"] = {"sandy_hackett_v2.mp4": "untouched — walks into a close-up; live result 2026-09-20: fix holds, verify fails head spread 2.9 % / drift 5.3 px → reshoot",
                          "zach_sain_v2.mov": "untouched — black shirt on the red wall; live result 2026-09-20: separation 1.00× → 1.45× at the bounds → reshoot",
                          "ethel_chadwick_v2.mp4": "untouched — the demo's Ethel is this recording",
                          "michi_sample_v1.mp4": "derived — the near-threshold pass (1.51×)"}
d["demo_lineup"] = {"brian_padded": "brian_shirley_v2_padded.mp4 (controlled: see derived.brian_padded) — the left card, fix → verified",
                    "ethel": "archived recording, unchanged", "zach": "zach_sain_v1_demo.mp4 (derived: see derived.zach_demo) — ran 2026-09-20, verified first pass",
                    "not in the picker": "sandy (untouched, fix → caught → reshoot — the natural failure case; ?clip=sandy), zach_padded (the same construction on Zach; ?clip=zach_padded)"}
json.dump(d, open(out, "w"), indent=2, ensure_ascii=False); open(out, "a").write("\n")
print(f"{dst}: {dsha[:16]}…  from {src}: {ssha[:16]}…")
EOF
echo "written: $OUT"
