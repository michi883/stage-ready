/* Stage Ready — the workspace.
   One recording at a time. Drop it; it is fingerprinted (SHA-256, in the browser, the way the live
   matte cache is keyed) and recognised; press Make Stage Ready and watch one flow —
   INSPECT → DECIDE → PROCESS → VERIFY — with one phrase per step and one sentence of narration,
   the source large on the left and the output arriving on the right. Add another recording repeats
   it; the session accumulates, and View processed recordings shows every source over its output.
   Everything dense — findings, reasoning, stages, gates, numbers — accumulates behind Trace and
   Details. The loop and the cached backend are untouched: the flow, the narrator and the trace are
   three projections of the same SSE events. ?demo=1 is required for now.
   Stand-in visuals are drawn from the measured numbers; a real still or video in
   demo/clips/<id>/stills/ replaces the stand-in for that artifact. */

const qs = new URLSearchParams(location.search);
const DEMO = qs.get("demo") === "1";
const INSTANT = qs.get("instant") === "1";
const PICK = qs.get("clip");                        // ?clip=sandy puts a sample recording on the bench at once
const BUDGET = qs.get("budget");                    // ?budget=0 shows the other exit: a reshoot request
const CADENCE = INSTANT ? 0 : (Number(qs.get("cadence")) || 750);   // ms per beat; one recording takes ≈15–25 s
const STEP = qs.get("step") === "1";                // ?step=1: Space / → advances one event at a time
const AUTORUN = qs.get("autorun") === "1";          // press Make Stage Ready as soon as a recording is on the bench

let PROFILE = null;
let CLIPS = [];                                      // the recordings the backend knows, in lineup order
const RUNS = [];                                     // the session: one entry per recording, in upload order
const PROV = new Set();
let CUR = null;                                      // the run on the bench
let RUN_ID = 0;                                      // bumps on reset; a stale run stops itself
let RUNNING = false;
let VIEW = "intake";

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const h = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = v => `${(v * 100).toFixed(v * 100 >= 10 ? 0 : 1)} %`;
const secs = ms => ms >= 60000 ? `≈${Math.round(ms / 60000)} min` : `${Math.round(ms / 1000)} s`;
const mb = n => n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : `${(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)} MB`;
const sleep = ms => new Promise(r => setTimeout(r, INSTANT ? 0 : ms));
const projected = r => !!(r && /^PROJECTED/.test(r.provenance || ""));
const firstSentence = s => (s || "").split(/(?<=\.)\s/)[0];
const shortHash = x => x ? `${x.slice(0, 8)}…${x.slice(-8)}` : "";
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

/* ---------- the narrative: one short phrase per step, read off the event data ------------ */
const WORDS = {
  choose: { "fix.reframe": "Reframe", "process.standard": "Standard process", "process.separation_targeted": "Try safer processing" },
  work:   { "fix.reframe": "Reframe", "process.standard": "Red Curtain composite", "process.separation_targeted": "Reprocess" },
  busy:   { "fix.reframe": "Reframing…", "process.standard": "Compositing…", "process.separation_targeted": "Reprocessing…" },
  finding: { picture_area: "Framing needs adjustment", subject_size: "Framing needs adjustment", headroom: "Framing needs adjustment",
             distance_steady: "Framing needs adjustment", pose_coverage: "Performer not clear", one_subject: "Performer not clear",
             face_exposure: "Lighting needs adjustment" },
  gate:   { separation: "blends into the curtain", matte_extent: "outline incomplete", head_spread: "framing unsteady", head_drift: "framing unsteady",
            frame_count: "frames missing", audio_md5: "audio changed", pose_coverage: "performer lost", one_subject: "more than one person" },
};
const stratLabel = id => { const s = PROFILE && PROFILE.strategies.find(s => s.id === id); return s ? s.label : id; };
function inspectPhrase(r) {
  const fails = r.findings.filter(f => f.status === "fail");
  if (!fails.length) return "Already suitable";
  const phrases = [...new Set(fails.map(f => WORDS.finding[f.id] || "Needs adjustment"))];
  return phrases.length === 1 ? phrases[0] : "Needs adjustment";
}
const choosePhrase = d => d.action === "deliver" ? "Deliver" : d.action === "reshoot" ? "Ask for a reshoot" : d.action === "inspect" ? "Look closer"
                        : WORDS.choose[d.strategy] || stratLabel(d.strategy);
const gatePhrase = v => { const g = v.failing[0]; return g ? (WORDS.gate[g.id] || g.label.toLowerCase()) : ""; };

const ICON = {
  inspect: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg>`,
  decide:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h5"/><path d="M9 12c3 0 3-6 6-6h5M9 12c3 0 3 6 6 6h5"/><path d="M17 3l3 3-3 3M17 15l3 3-3 3"/></svg>`,
  process: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M4 12h16M4 17h16"/><circle cx="9" cy="7" r="2" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r="2" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="2" fill="currentColor" stroke="none"/></svg>`,
  verify:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/></svg>`,
  arrow:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h15M13 6l6 6-6 6"/></svg>`,
};

/* ---------- formatting a finding / gate value (the trace) ------------------------------- */
function kindOf(unit = "") {
  if (/fraction|head width ratio/.test(unit)) return "pct";
  if (/px$/.test(unit)) return "px";
  if (/^frames$/.test(unit)) return "int";
  if (/gain|p95 \/ p5|luma ratio|apparent size/.test(unit)) return "x";
  return "raw";
}
function fmtNum(v, kind) {
  if (kind === "pct") return pct(v);
  if (kind === "px") return `${v} px`;
  if (kind === "int") return `${v}`;
  if (kind === "x") return `${v.toFixed(2)}×`;
  return `${v}`;
}
function fmtVal(f) {
  const v = f.value, kind = kindOf(f.unit);
  if (v == null) return "—";
  if (typeof v === "number") return fmtNum(v, kind);
  if (typeof v === "string") return v;
  if (v.w != null) return `${v.w}×${v.h} at +${v.x}+${v.y}`;
  if (v.p95 != null) return `p50 ${pct(v.p50)} · p95 ${pct(v.p95)}`;
  if (v.min != null) return `${pct(v.min)}–${pct(v.max)}`;
  if (v.crown_cut_frames != null) return `crown cut on ${pct(v.crown_cut_frames)}`;
  if (v.predicted_separation != null) return `hue ${v.hue_deg}° · luma ${v.luma_pct} % · pred ${v.predicted_separation}×`;
  return JSON.stringify(v);
}
function fmtThr(t, unit = "") {
  if (t == null) return "";
  const kind = kindOf(unit);
  if (typeof t === "object" && t.op) return `${t.op.replace(">=", "≥").replace("<=", "≤").replace("==", "=")} ${typeof t.value === "number" ? fmtNum(t.value, kind === "raw" ? "raw" : kind) : t.value}`;
  if (typeof t === "object" && t.target) return `target ${t.target}`;
  if (typeof t === "object" && t.recommended) return `rec. ${pct(t.recommended[0])}–${pct(t.recommended[1])}`;
  if (typeof t === "object") return "";
  return `= ${t}`;
}
function fmtChange(v) { return typeof v === "number" ? (v < 1 ? pct(v) : v) : v; }

/* ---------- stand-in visuals, from the measured numbers ----------------------------------- */
let SVG_N = 0;                                       // ids are per instance: the same still is drawn in several places
function figure(cx, top, S, bottom, v, opts = {}) {
  // S = shoulder joint span in viewBox px. Proportions are stylised; positions are measured.
  const headRx = 0.42 * S, headRy = 0.55 * S, headCy = top + headRy;
  const shY = top + 1.45 * S;
  const half = 0.95 * S;
  const wardrobe = opts.lift ? lighten(v.wardrobe, opts.lift) : v.wardrobe;
  const torso = `M ${cx - half} ${bottom} L ${cx - half} ${shY + 0.35 * S} Q ${cx - half} ${shY} ${cx - 0.55 * S} ${shY}
                 L ${cx + 0.55 * S} ${shY} Q ${cx + half} ${shY} ${cx + half} ${shY + 0.35 * S} L ${cx + half} ${bottom} Z`;
  const neck = `M ${cx - 0.16 * S} ${headCy + headRy * 0.7} L ${cx - 0.16 * S} ${shY + 0.05 * S} L ${cx + 0.16 * S} ${shY + 0.05 * S} L ${cx + 0.16 * S} ${headCy + headRy * 0.7} Z`;
  const rim = opts.rim ? `<g filter="url(#${opts.rimId})" opacity="${opts.rim}">
      <path d="${torso}" fill="none" stroke="#ffb3a0" stroke-width="${0.09 * S}"/>
      <ellipse cx="${cx}" cy="${headCy}" rx="${headRx}" ry="${headRy}" fill="none" stroke="#ffb3a0" stroke-width="${0.09 * S}"/></g>` : "";
  return `${rim}
    <path d="${torso}" fill="${wardrobe}"/>
    <path d="${neck}" fill="${v.skin}"/>
    <ellipse cx="${cx}" cy="${headCy - 0.12 * S}" rx="${headRx * 1.08}" ry="${headRy * 0.9}" fill="${v.hair}"/>
    <ellipse cx="${cx}" cy="${headCy}" rx="${headRx}" ry="${headRy}" fill="${v.skin}"/>
    <path d="M ${cx - headRx} ${headCy - 0.2 * S} Q ${cx} ${headCy - 0.75 * S} ${cx + headRx} ${headCy - 0.2 * S} Q ${cx} ${headCy - 0.35 * S} ${cx - headRx} ${headCy - 0.2 * S} Z" fill="${v.hair}"/>`;
}
function lighten(hex, amt) {
  const n = parseInt(hex.slice(1), 16), a = Math.round(amt * 255);
  const c = x => Math.min(255, x + a).toString(16).padStart(2, "0");
  return `#${c(n >> 16)}${c((n >> 8) & 255)}${c(n & 255)}`;
}
function sourceSVG(clip) {
  const v = clip.visual, W = 192, H = 108, u = `pic${++SVG_N}`;
  const px = v.pillars * W, pw = W - 2 * px;
  const cx = px + pw / 2, S = v.shoulder_span * W, top = v.head_y * H;
  const key = v.key_side === "right" ? `<rect x="${px + pw * 0.72}" y="12" width="${pw * 0.2}" height="60" fill="${v.room_accent}" opacity=".9"/>`
            : v.key_side === "flat" ? `<rect x="${px + 10}" y="16" width="${pw * 0.14}" height="72" fill="${v.room_accent}" opacity=".5"/>` : "";
  return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
    <rect width="${W}" height="${H}" fill="#000"/>
    <clipPath id="${u}"><rect x="${px}" y="0" width="${pw}" height="${H}"/></clipPath>
    <g clip-path="url(#${u})">
      <rect x="${px}" y="0" width="${pw}" height="${H}" fill="${v.room}"/>${key}
      <rect x="${px}" y="${H * 0.82}" width="${pw}" height="${H * 0.18}" fill="#000" opacity=".08"/>
      ${figure(cx, top, S, H, v)}
    </g>
    ${v.pillars ? `<text x="${px / 2}" y="${H / 2 + 3}" text-anchor="middle" font-size="7" fill="#666" font-family="monospace">${Math.round(px / W * 1920)}</text>` : ""}
  </svg>`;
}
function outputSVG(clip, m, opts = {}) {
  const v = clip.visual, W = 108, H = 192, u = `o${++SVG_N}`;
  const S = m.shoulder_span_p50 * W, top = m.head_target * H, cx = W / 2;
  const folds = Array.from({ length: 12 }, (_, i) => `<rect x="${i * 9}" y="0" width="4.5" height="${H}" fill="#000" opacity="${0.10 + (i % 3) * 0.04}"/>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="${u}-cur" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7c1216"/><stop offset="1" stop-color="#4c0a0d"/></linearGradient>
      <radialGradient id="${u}-vig" cx=".5" cy=".45" r=".75"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".45"/></radialGradient>
      <filter id="${u}-neon" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <filter id="${u}-rim" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="1.4"/></filter>
    </defs>
    <rect width="${W}" height="${H}" fill="url(#${u}-cur)"/>${folds}
    <rect width="${W}" height="${H}" fill="url(#${u}-vig)"/>
    <text x="${cx}" y="${H * 0.145 + 4}" text-anchor="middle" font-size="11" font-style="italic" font-family="'Snell Roundhand','Brush Script MT',cursive" fill="#ffd98a" filter="url(#${u}-neon)">Midtown Show</text>
    ${figure(cx, top, S, H, v, { ...opts, rimId: `${u}-rim` })}
  </svg>`;
}
const gradeOpts = pr => ({ rim: pr && pr.params.rimamt > 0.3 ? 0.9 : 0, lift: pr ? pr.params.shadow_lift || 0 : 0 });
const outputStandIn = (clip, pr) => outputSVG(clip, { head_target: pr.output.head_target, shoulder_span_p50: pr.output.shoulder_span_p50 }, gradeOpts(pr));

/* ---------- media: a real video if there is one, else a real still, else the stand-in --------
   `prefer: "still"` keeps the session view light (sources as frames, outputs playing). */
function media(run, artifact, standIn, opts = {}) {
  const clip = run.clip, f = run.file;
  const video = artifact === "source" && f && f.url ? f.url : clip.videos && clip.videos[artifact] ? `/stills/${clip.id}/${clip.videos[artifact]}` : null;
  const still = clip.stills && clip.stills[artifact] ? `/stills/${clip.id}/${clip.stills[artifact]}` : null;
  if (video && opts.prefer !== "still") {
    // if the browser cannot decode the file (an exotic container), fall back to the frame
    const fallback = still ? `<img src="${still}" alt="${artifact}">` : standIn;
    return `<video src="${esc(video)}" muted autoplay loop playsinline preload="auto" ${still ? `poster="${esc(still)}"` : ""} onerror="this.outerHTML=${esc(JSON.stringify(fallback))}"></video>`;
  }
  if (still) return `<img src="${esc(still)}" alt="${artifact}">`;
  return standIn;
}
const still = (run, artifact, standIn, cls = "") => `<div class="${cls}">${media(run, artifact, standIn, { prefer: "still" })}</div>`;

/* ---------- the session: one run per recording, in upload order ------------------------- */
function newRun(clip, file) {
  const trace = h("div", "trace");
  const run = { n: RUNS.length + 1, clip, file, trace, attempts: {}, verifies: {}, fixes: [], lastInspect: null, story: [], end: null,
                queue: [], timer: null, es: null, onEnd: null, lane: { attempt: 1, lastVerify: null, fixed: false } };
  trace.dataset.run = run.n;
  $("#traces").appendChild(trace);
  RUNS.push(run);
  return run;
}
const label = run => `Recording ${run.n}`;
/* The three outcomes, one rule: ACCEPT — verified on the first pass, nothing changed; ADAPT — verified
   after the loop changed something (a fix, or a different strategy after a failed gate); REFUSE — a
   reshoot request. The same rule labels the bench, the session view and the Details table. */
function verdict(ev) {
  if (!ev) return null;
  if (ev.outcome !== "delivered") {
    const item = ev.reshoot.items[0];
    return { key: "refuse", word: "REFUSE", line: `Reshoot requested — ${firstSentence(item ? item.guidance : "the retry budget is spent")}` };
  }
  const d = ev.delivery;
  if (d.attempts === 1 && d.fixes.length === 0) return { key: "accept", word: "ACCEPT", line: "Verified on the first pass — nothing to change." };
  const how = d.attempts > 1 ? "the first attempt failed a gate and the strategy changed" : "the framing was fixed and re-inspected";
  return { key: "adapt", word: "ADAPT", line: `Verified after adapting — ${how}.` };
}
const verdictBadge = (v, big = false) => v ? `<span class="verdict ${v.key}${big ? " big" : ""}">${v.word}</span>` : "";
const doneRuns = () => RUNS.filter(r => r.end);
function header() {
  const n = doneRuns().length;
  const b = $("#processed-nav");
  b.hidden = !n;
  b.textContent = VIEW === "processed" ? "Back to workspace" : `Processed (${n})`;
}

/* ---------- views ------------------------------------------------------------------------ */
function showView(v) {
  VIEW = v;
  $("#intake").hidden = v !== "intake";
  $("#bench").hidden = v !== "bench";
  $("#processed").hidden = v !== "processed";
  if (v === "bench") { fit(); $$("#bench video").forEach(x => x.play().catch(() => {})); }
  else $$("#bench video").forEach(x => x.pause());
  if (v === "processed") $$("#processed video").forEach(x => x.play().catch(() => {}));
  else $$("#processed video").forEach(x => x.pause());
  header();
}

/* ---------- 1. intake ---------------------------------------------------------------------- */
function dropStatus(html) { const s = $("#drop-status"); s.hidden = !html; s.innerHTML = html || ""; }
async function sha256(file) {
  if (!crypto.subtle) return null;                   // not a secure context (http:// on a LAN address): fall back to the name
  const buf = await file.arrayBuffer();
  const dig = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(dig)].map(b => b.toString(16).padStart(2, "0")).join("");
}
function probe(url) {                                // duration and picture size, from the browser's decoder
  return new Promise(resolve => {
    const v = document.createElement("video"); v.preload = "metadata"; v.muted = true;
    v.onloadedmetadata = () => resolve({ duration: v.duration, w: v.videoWidth, h: v.videoHeight });
    v.onerror = () => resolve(null);
    v.src = url;
  });
}
const metaLine = m => m ? `${m.w}×${m.h} · ${Math.round(m.duration)} s` : "";
async function useFile(file) {
  const drop = $("#drop"); drop.classList.add("busy");
  const url = URL.createObjectURL(file);
  const head = `<div class="st-file">${esc(file.name)}<span>${mb(file.size)}</span></div>`;
  dropStatus(`${head}<div class="st-line"><span class="spinner"></span>Reading the file…</div>`);
  const meta = await probe(url);
  dropStatus(`${head}<div class="st-line"><span class="spinner"></span>Fingerprinting — SHA-256, the key the matte cache uses…</div>`);
  const hash = await sha256(file);
  const r = await (await fetch(`/api/recognize?demo=1&sha256=${hash || ""}&name=${encodeURIComponent(file.name)}`)).json();
  if (!r.clip) {
    drop.classList.remove("busy");
    dropStatus(`${head}<div class="st-line bad">No cached run for this recording${hash ? ` — <code>${shortHash(hash)}</code>` : ""}.</div>
      <div class="st-line">Demo mode replays cached runs only; live processing is not wired yet. Drop one of the sample recordings, or pick one above.</div>`);
    URL.revokeObjectURL(url);
    return;
  }
  dropStatus(`${head}<div class="st-line ok">Recognised — a cached run exists for this recording${hash ? `&nbsp;· <code>${shortHash(hash)}</code>` : ""}</div>`);
  await sleep(500);
  drop.classList.remove("busy");
  start(r.clip, { name: file.name, size: file.size, url, meta: metaLine(meta), sha256: hash, matched_by: r.matched_by });
}
async function useSample(clip) {
  const name = (clip.recognize && clip.recognize.names || [])[0] || clip.name;
  const run = start(clip, { name, size: null, url: null, meta: "", sha256: null, matched_by: "sample" });
  const v = clip.videos && clip.videos.source;
  if (v) { const m = await probe(`/stills/${clip.id}/${v}`); if (run === CUR && m) { run.file.meta = metaLine(m); $("#src-meta").textContent = run.file.meta; } }
}
function start(clip, file) {
  const run = newRun(clip, file);
  mountBench(run);
  dropStatus("");
  showView("bench");
  if (AUTORUN) runCurrent();
  return run;
}

/* ---------- 2. the bench -------------------------------------------------------------------- */
const STEP_COL = { inspect: 1, decide: 3, process: 5, verify: 7 };
const STEP_INDEX = { inspect: 1, decide: 2, process: 3, verify: 4, output: 5 };
const TITLE = { inspect: "Inspect", decide: "Decide", process: "Process", verify: "Verify" };

function mountBench(run) {
  if (CUR && CUR.es) { CUR.es.close(); CUR.es = null; }
  CUR = run;
  const clip = run.clip, f = run.file;
  $("#bench").className = "view bench";
  // the source
  $("#src-frame").innerHTML = media(run, "source", sourceSVG(clip));
  $("#src-label").textContent = label(run);
  $("#src-name").textContent = f.name;
  $("#src-meta").textContent = f.meta || "";
  $("#src-performer").textContent = clip.name;
  const how = $("#src-how");
  how.hidden = false;
  how.textContent = f.matched_by === "sha256" ? "recognised" : f.matched_by === "name" ? "recognised by name" : "sample";
  how.title = f.sha256 ? `SHA-256 ${f.sha256} — the cached run for this recording is replayed` : "the cached run for this recording is replayed";
  // the flow
  const flow = $("#flow");
  $$(".step, .arr", flow).forEach(e => e.remove());
  const step = id => `<div class="step ${id}" data-step="${id}" style="grid-column:${STEP_COL[id]}"><span class="ttl">${TITLE[id]}</span><span class="ico">${ICON[id]}</span><div class="rows"></div></div>`;
  const arr = col => `<span class="arr" data-into="${(col + 1) / 2}" style="grid-column:${col}">${ICON.arrow}</span>`;
  flow.insertAdjacentHTML("beforeend", `${step("inspect")}${arr(2)}${step("decide")}${arr(4)}${step("process")}${arr(6)}${step("verify")}`);
  flow.classList.remove("retrying");
  $(".retry", flow).className = "retry";
  $(".retry .lbl", flow).textContent = "retry";
  // the output
  const out = $("#out");
  out.className = "thumb out";
  out.innerHTML = `<div class="frame placeholder"><span>output</span></div><span class="cap"></span>`;
  narrate("");
  // the trace: a fresh record for this run
  run.attempts = {}; run.verifies = {}; run.fixes = []; run.lastInspect = null; run.story = []; run.end = null;
  run.lane = { attempt: 1, lastVerify: null, fixed: false };
  run.trace.innerHTML = `<div class="trace-intro">Every card is one loop event, in order. Chips say what each call costs live and where its numbers come from.</div>`;
  const facts = clip.source;
  const meta = f.meta ? ` · ${esc(f.meta)}` : "";
  const ident = f.sha256
    ? `<div class="hash">upload <b>${esc(f.name)}</b> · ${f.size.toLocaleString()} bytes${meta} · SHA-256 <b>${esc(f.sha256)}</b><br>${f.matched_by === "sha256" ? "recognised by fingerprint — byte for byte the archived source; the cached run is replayed" : "recognised by name only — the fingerprint differs from the archived source; the cached run is replayed for the demo"}</div>`
    : f.matched_by === "name" ? `<div class="hash">upload <b>${esc(f.name)}</b>${meta} · recognised by name (no fingerprint: not a secure context) — the cached run is replayed</div>`
    : `<div class="hash">sample recording <b>${esc(f.name)}</b>${meta} — the cached run is replayed</div>`;
  addCard(run, "src", `${label(run)} <b>${esc(clip.name)}</b>`,
    `${ident}<div class="brief">${esc(clip.brief)}</div>
     <div class="facts-row"><span class="k">measured on</span><span>${esc(facts.picture || `${facts.width}×${facts.height}`)}</span><span>${facts.fps} fps</span><span>${facts.duration_s} s · ${facts.frames} frames</span><span>${esc(facts.wardrobe)}</span><span>${esc(facts.framing)}</span><span>${esc(facts.room)}</span></div>
     ${clip.fixture ? `<div class="brief">numbers from <i>${esc(clip.fixture)}</i></div>` : ""}`);
  buttons();
  header();
}

/* one cell, one phrase. state: working | done | failed; opts: sub, flag, keep (leave the phrase), tag */
function rowFor(id) {
  const rows = $(`#flow .step[data-step="${id}"] .rows`);
  let row = $(`.row[data-attempt="${CUR.lane.attempt}"]`, rows);
  if (!row) { row = h("div", "row", `<span class="phrase"></span><span class="sub"></span>`); row.dataset.attempt = CUR.lane.attempt; rows.appendChild(row); }
  return row;
}
function lightArrows(upto) { $$("#flow .arr").forEach(a => a.classList.toggle("on", Number(a.dataset.into) <= upto)); }
function focus(el) { $$("#bench .current").forEach(s => s.classList.remove("current")); el.classList.add("current"); }
function setStep(id, state, phrase, opts = {}) {
  const stp = $(`#flow .step[data-step="${id}"]`);
  const row = rowFor(id);
  if (phrase != null && !opts.keep) $(".phrase", row).textContent = phrase;
  if (!opts.keep || opts.sub != null) $(".sub", row).textContent = opts.sub || "";
  row.classList.toggle("failed", state === "failed");
  if (opts.tag) { $(".ptag", row)?.remove(); row.appendChild(h("span", "ptag", esc(opts.tag))); }
  stp.classList.remove("working", "done", "failed", "flag");
  stp.classList.add(state);
  if (opts.flag) stp.classList.add("flag");
  focus(stp);
  lightArrows(STEP_INDEX[id]);
}
function setOutput(state, phrase) {
  const out = $("#out");
  out.classList.remove("working", "done", "failed");
  out.classList.add(state);
  $(".cap", out).textContent = phrase || "";
  focus(out);
  lightArrows(STEP_INDEX.output);
}
function narrate(text, cls = "") {
  const n = $("#narrator");
  n.className = `narrator ${cls}`;
  n.innerHTML = text ? `<span>${text}</span>` : "";
}
const storyChips = st => st.map((x, j) => `<span class="sp">${j ? `<span class="sarr">→</span>` : ""}<span class="schip ${x.state}">${esc(x.phrase)}</span></span>`).join("");
function pathOf(run) {                               // the short summary of the path taken
  let st = run.story;
  const firstFail = st.findIndex(x => x.state === "fail");
  const delivered = run.end && run.end.outcome === "delivered";
  // On a delivered retry the failure is where the story starts. On a refusal the whole path is
  // the story — a fix that held, then a gate the fix could not touch — so nothing is trimmed.
  if (firstFail > 0 && (delivered || !run.end)) st = st.slice(firstFail);
  return st;
}
function narrateEnd(run, sentence, cls) {
  const n = $("#narrator");
  n.className = `narrator end ${cls}`;
  n.innerHTML = `<span class="story">${storyChips(pathOf(run))}</span><span class="line">${sentence}</span>`;
}
function newAttempt() {
  CUR.lane.attempt += 1;
  CUR.lane.fixed = false;
  $$("#flow .step:not(.inspect) .row").forEach(r => r.classList.add("past"));   // the inspection stands
}
function showAttempt(pr) {
  const out = $("#out");
  $(".placeholder", out)?.remove();
  $$(".attempt.front", out).forEach(a => { a.classList.remove("front"); a.classList.add("behind"); $("video", a)?.pause(); });
  const a = h("div", "attempt front", `<div class="frame">${media(CUR, pr.artifact, outputStandIn(CUR.clip, pr))}</div><span class="alabel">attempt ${pr.artifact.replace(/\D/g, "")}</span><span class="mark"></span>`);
  a.dataset.artifact = pr.artifact;
  out.insertBefore(a, $(".cap", out));
}
function markAttempt(artifact, ok) {
  const a = $(`#out .attempt[data-artifact="${artifact}"]`);
  if (!a) return;
  a.classList.add(ok ? "pass" : "fail");
  $(".mark", a).textContent = ok ? "✓" : "✗";
}
function syncPlayback() {                            // the delivered output and the source, from the same moment
  const vids = [$("#src-frame video"), $("#out .attempt.front video")].filter(Boolean);
  vids.forEach(v => { try { v.currentTime = 0; v.play().catch(() => {}); } catch (e) { /* not ready yet */ } });
}
const story = (phrase, state) => CUR.story.push({ phrase, state });

/* ---------- event → the flow and the narrator -------------------------------------------- */
function flow(ev) {
  const L = CUR.lane, run = CUR;
  switch (ev.type) {
    case "run.start": narrate(`Target: <b>${esc(ev.profile.name)}</b> · ${ev.profile.canvas.w} × ${ev.profile.canvas.h} · ${ev.profile.gates.length} verification gates`); break;
    case "phase":
      switch (ev.phase) {
        case "inspect":
          if (ev.after_fix) { setStep("process", "working", null, { keep: true, sub: "checking the fix…" }); narrate("Re-inspecting the fixed picture — a fix that creates a new defect is rejected."); }
          else { setStep("inspect", "working", "Inspecting…"); narrate("Measuring the source: picture area, pose, subject size, steadiness, headroom, exposure."); }
          break;
        case "decide":
          if (L.lastVerify === "fail") { newAttempt(); $("#flow").classList.add("retrying"); L.budget = ev.budget; L.retrySub = `retry ${ev.budget.reprocesses_used + 1} of ${ev.budget.retry_budget}`; setStep("decide", "working", "Deciding…", { sub: L.retrySub }); narrate("Verification failed — the agent is choosing what to try next.", "retry"); }
          else if (L.lastVerify === "pass") { setOutput("working", "Delivering…"); narrate("Every gate passed — the agent is confirming delivery."); }
          else if (L.fixed) { setStep("decide", "working", null, { keep: true }); narrate("The fix held — the agent is deciding how to process."); }
          else { setStep("decide", "working", "Deciding…"); narrate("The agent is reading the findings against the profile…"); }
          break;
        case "fix": setStep("process", "working", WORDS.busy[ev.strategy] || "Fixing…"); narrate("Cropping to the measured picture area and re-solving the framing under the size cap — one-sided, no pixels invented."); break;
        case "process":
          setStep("process", "working", ev.attempt > 1 ? "Reprocessing…" : L.fixed ? "Compositing…" : WORDS.busy[ev.strategy] || "Processing…");
          narrate(ev.attempt > 1 ? "Reprocessing with the separation-targeted grade — the matte and the tracking are reused, only the edge changes."
                                 : "Compositing on the Red Curtain plate: seed → matte → track → warp → grade → composite → encode.");
          break;
        case "verify": setStep("verify", "working", "Verifying…"); narrate(`Measuring the finished output against the profile's ${PROFILE.gates.length} gates…`); break;
        case "deliver": setOutput("working", "Delivering…"); break;
        case "reshoot": setOutput("failed", "Reshoot"); break;
      }
      break;
    case "inspect.result": {
      const r = ev.result;
      if (ev.resolved) {                             // the re-inspection after a fix
        if (ev.new_defects.length) { setStep("process", "failed", "Fix rejected ✗"); L.fixed = false; narrate(`The fix created a new defect (${ev.new_defects.join(", ")}) — rejected.`, "fail"); }
        else { setStep("process", "done", null, { keep: true, sub: "" }); narrate(`The fix held: ${ev.resolved.join(" and ").replace(/_/g, " ")} resolved, nothing new outside the profile.`); }
      } else {
        const fails = r.findings.filter(f => f.status === "fail");
        const phrase = inspectPhrase(r);
        setStep("inspect", "done", phrase, { flag: fails.length > 0 });
        story(phrase, fails.length ? "flag" : "pass");
        narrate(fails.length ? `${fails.length} finding${fails.length > 1 ? "s" : ""} outside the profile: ${fails.map(f => `<b>${esc(f.label.toLowerCase())}</b> ${esc(fmtVal(f))}`).join(", ")}.`
                             : `Nothing outside the profile — ${r.findings.length} measurements, all inside.`);
      }
      break;
    }
    case "decide.result": {
      const d = ev.decision;
      const quote = firstSentence(d.reasoning);
      if (d.action === "deliver") { setOutput("working", "Delivering…"); narrate(esc(quote), "quote"); break; }
      if (d.action === "reshoot") {
        // Why the arc is blocked is a fact, not a phrase: the budget is spent, or nothing in the profile addresses this defect.
        const spent = L.budget && L.budget.reprocesses_used >= L.budget.retry_budget;
        setStep("decide", "failed", "Ask for a reshoot"); $("#flow .retry").classList.add("blocked"); $("#flow .retry .lbl").textContent = spent ? "no retry left" : "no strategy for this";
        story("Ask for a reshoot", "fail"); narrate(esc(quote), "quote fail"); break;
      }
      if (d.action === "process" && L.fixed) { setStep("decide", "done", null, { keep: true }); narrate(esc(quote), "quote"); break; }   // "Reframe" stands; the work shows it
      const phrase = choosePhrase(d);
      setStep("decide", "done", phrase, L.lastVerify === "fail" ? { sub: L.retrySub } : {});
      story(phrase, "decide");
      narrate(esc(quote), L.lastVerify === "fail" ? "quote retry" : "quote");
      break;
    }
    case "guard": break;                             // the trace has it; the forced decision follows
    case "fix.result":
      L.fixed = true; run.fixes.push(ev.result);
      setStep("process", "working", WORDS.work[ev.result.strategy] || stratLabel(ev.result.strategy), { sub: "checking the fix…" });
      { const c = ev.result.changes; narrate(`Reframed: head height ${c.head_target ? `${c.head_target.before} → ${c.head_target.after}` : "adjusted"}, shoulders ${c.shoulder_span_p50 ? `${pct(c.shoulder_span_p50.before)} → ${pct(c.shoulder_span_p50.after)}` : "under the cap"} of the canvas. Re-inspecting…`); }
      break;
    case "fix.rejected": setStep("process", "failed", "Fix rejected ✗"); L.fixed = false; break;
    case "process.result": {
      const r = ev.result;
      run.attempts[r.artifact] = r;
      const work = WORDS.work[r.strategy] || stratLabel(r.strategy);
      const fixWork = L.fixed && run.fixes.length ? (WORDS.work[run.fixes[run.fixes.length - 1].strategy] || "Fix") : null;
      setStep("process", "done", fixWork ? `${fixWork} + composite` : work);   // a projected process is marked where it matters: on its verification
      if (ev.attempt > 1) story(work, "decide");
      showAttempt(r);
      narrate(`Attempt ${ev.attempt} rendered — ${r.output.canvas.join(" × ")}, ${r.output.frames} frames${r.stages.some(x => x.reused) ? ", matte and tracking reused" : ""}.`);
      break;
    }
    case "verify.result": {
      const r = ev.result, m = r.measurements;
      run.verifies[r.artifact] = r;
      L.lastVerify = ev.passed ? "pass" : "fail";
      if (ev.passed) {
        setStep("verify", "done", "Verified ✓", { sub: m.separation ? `separation ${m.separation.toFixed(2)}×` : "", tag: projected(r) ? "projected" : null });
        story("Verified ✓", "pass");
        narrate(`Verified ✓ — ${r.gates.length} of ${r.gates.length} gates${m.separation ? `, separation <b>${m.separation.toFixed(2)}×</b>` : ""}${m.head_spread != null ? `, head height held to ${pct(m.head_spread)}` : ""}, frames and audio identical to the source.${projected(r) ? " <i>(separation projected — pending ground truth)</i>" : ""}`, "pass");
      } else {
        const g = r.failing[0];
        setStep("verify", "failed", "Fails ✗", { sub: gatePhrase(r) });
        story(ev.attempt === 1 ? "First output fails ✗" : "Fails again ✗", "fail");
        narrate(`✗ Fails ${r.failing.length === 1 ? "one gate" : `${r.failing.length} gates`}: <b>${esc(g.label.toLowerCase())} ${esc(fmtVal(g))}</b> against ${esc(fmtThr(g.threshold, g.unit))}. ${esc(g.detail.split(/(?<=\.)\s/).slice(1).join(" ") || g.detail)} No capture-side check could see this — only the finished output.`, "fail");
      }
      markAttempt(r.artifact, ev.passed);
      break;
    }
    case "run.end":
      run.end = ev;
      if (ev.outcome === "delivered") {
        const v = verdict(ev);
        setOutput("done", "Delivered ✓");
        $(".cap", $("#out")).innerHTML = `${verdictBadge(v)} Delivered ✓`;
        $("#bench").classList.add("done");
        const d = ev.delivery;
        narrateEnd(run, `${verdictBadge(v)} <b>Stage Ready.</b> ${d.attempts > 1 ? `Second attempt delivered — the first was measured, failed, and replaced.` : d.fixes.length ? `One fix, one attempt.` : `First attempt, no fixes.`} Verified against every gate in the profile.`, `pass ${v.key}`);
        syncPlayback();
      } else {
        const out = $("#out");
        const item = ev.reshoot.items[0];
        out.insertBefore(h("div", "attempt front", `<div class="frame reshoot"><b>Reshoot requested</b><span>${esc(firstSentence(item ? item.guidance : ""))}</span></div>`), $(".cap", out));
        $$(".attempt", out).forEach(a => { if (!a.classList.contains("front") || a.querySelector(".reshoot") == null) { a.classList.remove("front"); a.classList.add("behind"); } });
        setOutput("failed", "Not delivered ✗");
        $(".cap", $("#out")).innerHTML = `${verdictBadge(verdict(ev))} Not delivered ✗`;
        $("#bench").classList.add("done");
        story("Reshoot requested", "fail");
        narrateEnd(run, `${verdictBadge(verdict(ev))} Reshoot requested — ${esc(item ? item.guidance : "the retry budget is spent")}`, "fail refuse");
      }
      break;
    case "error": {
      const cur = $("#flow .step.current");
      if (cur) setStep(cur.dataset.step, "failed", "Error"); else setOutput("failed", "Error");
      narrate(esc(ev.message), "fail");
      break;
    }
  }
}

/* ---------- event → trace card ------------------------------------------------------------ */
function addCard(run, cls, head, body) {
  const c = h("div", `card ${cls}`, `<div class="card-h">${head}</div>${body}`);
  run.trace.appendChild(c);
  return c;
}
const provChip = p => p && /^PROJECTED/.test(p) ? `<span class="chip proj" title="${esc(p)}">projected</span>` : "";
function cachedChip(r) { if (r.provenance) PROV.add(r.provenance); return `${r.cached ? `<span class="chip cached">cached</span>` : ""}${provChip(r.provenance)}${r.duration_ms ? `<span class="chip live" title="what this costs live">${secs(r.duration_ms)} live</span>` : ""}`; }

function card(run, ev) {
  switch (ev.type) {
    case "run.start": case "phase": break;
    case "inspect.result": {
      const r = ev.result;
      const rows = r.findings.map(f => `<div class="finding ${f.status}">
          <span class="dot ${f.status}"></span><span class="lbl">${esc(f.label)}</span>
          <span class="val ${f.status}">${esc(fmtVal(f))}${f.threshold ? ` <span title="threshold">· ${esc(fmtThr(f.threshold, f.unit))}</span>` : ""}</span>
          <span class="det">${esc(f.detail)}${f.tool ? ` <i>· ${esc(f.tool)}</i>` : ""}</span></div>`).join("");
      const fails = r.findings.filter(f => f.status === "fail").length;
      const diff = ev.resolved ? `<div class="report">Fix re-inspected — resolved: <b>${ev.resolved.join(", ") || "none"}</b> · new defects: <b>${ev.new_defects.length ? ev.new_defects.join(", ") : "none"}</b></div>` : "";
      addCard(run, "inspect", `Inspect <b>${esc(r.target)}</b> <span class="chip">${r.findings.length} findings · ${fails ? `<span style="color:var(--fail)">${fails} outside the profile</span>` : "nothing outside the profile"}</span><span class="right">${cachedChip(r)}</span>`,
        `<div class="findings">${rows}</div>${diff}`);
      break;
    }
    case "decide.result": {
      const d = ev.decision;
      const act = d.action === "process" && ev.ordinal > 1 && run.lane.lastVerify === "fail" ? "reprocess" : d.action;
      addCard(run, "decide", `Decide <b>#${ev.ordinal}</b> <span class="chip action ${act}">${act.toUpperCase()}</span>${d.strategy ? `<span class="chip">${esc(stratLabel(d.strategy))}</span>` : ""}<span class="right">${d.cached ? `<span class="chip cached">cached decision</span>` : `<span class="chip">${esc(d.model)}</span>`} conf ${d.confidence}</span>`,
        `<div class="reason">${esc(d.reasoning)}</div><div class="cites">${d.cites.map(c => `<span class="chip">${esc(c)}</span>`).join("")}</div>`);
      break;
    }
    case "guard":
      addCard(run, "guard", `Loop refused <b>${esc(ev.decision.action)}</b>`, `<div class="reason">${esc(ev.reason)}</div>`);
      break;
    case "fix.result": {
      const r = ev.result;
      const stages = r.stages.map(x => `<div class="stage"><span class="id">${esc(x.id)}</span><span class="sum">${esc(x.summary)}</span><span class="chip live">${secs(x.duration_ms)}</span></div>`).join("");
      const ch = Object.entries(r.changes).map(([k, v]) => `<span class="k">${esc(k)}</span><span>${typeof v === "object" ? `${esc(fmtChange(v.before))} → <span class="after">${esc(fmtChange(v.after))}</span>` : esc(v)}</span>`).join("");
      addCard(run, "act", `Fix <b>${esc(stratLabel(r.strategy))}</b> <span class="chip">one-sided · no pixels invented</span><span class="right">${cachedChip(r)}</span>`,
        `<div class="stages">${stages}</div><div class="changes">${ch}</div>`);
      break;
    }
    case "fix.rejected":
      addCard(run, "guard", `Fix rejected <b>${esc(ev.strategy)}</b>`, `<div class="reason">It created new defects: ${ev.new_defects.join(", ")}. Reverting to the previous artifact.</div>`);
      break;
    case "process.result": {
      const r = ev.result;
      const stages = r.stages.map(x => `<div class="stage ${x.reused ? "reused" : x.cached ? "cached" : ""}"><span class="id">${esc(x.id)}</span><span class="sum">${esc(x.summary)}</span>${x.reused ? `<span class="chip reused">reused</span>` : x.cached ? `<span class="chip cached">cached · ${secs(x.duration_ms)} live</span>` : `<span class="chip live">${secs(x.duration_ms)}</span>`}</div>`).join("");
      addCard(run, "act", `${ev.attempt > 1 ? "Reprocess" : "Process"} <b>attempt ${ev.attempt}</b> <span class="chip">${esc(stratLabel(r.strategy))}</span><span class="right">${cachedChip(r)}</span>`,
        `<div class="stages">${stages}</div>`);
      break;
    }
    case "verify.result": {
      const r = ev.result;
      const rows = r.gates.map(g => `<tr class="${g.status}"><td class="g-mark">${g.status === "pass" ? "✓" : g.status === "fail" ? "✗" : "!"}</td><td>${esc(g.label)}</td><td class="g-val">${esc(fmtVal(g))} <span style="color:var(--muted)">${esc(fmtThr(g.threshold, g.unit))}</span></td></tr>${g.status === "fail" ? `<tr class="fail"><td></td><td colspan="2" class="g-det">${esc(g.detail)}</td></tr>` : ""}`).join("");
      addCard(run, `verify ${ev.passed ? "" : "failed"}`, `Verify <b>attempt ${ev.attempt}</b> <span class="verdict ${ev.passed ? "pass" : "fail"}">${ev.passed ? "PASS" : "FAIL"}</span> <span class="chip">${r.gates.filter(g => g.status !== "fail").length} / ${r.gates.length} gates</span><span class="chip">retries ${ev.budget.reprocesses_used} / ${ev.budget.retry_budget}</span><span class="right">${cachedChip(r)}</span>`,
        `<table class="gates">${rows}</table>`);
      break;
    }
    case "run.end": endCard(run, ev); break;
    case "error": addCard(run, "guard", `Error`, `<div class="error">${esc(ev.message)}</div>`); break;
  }
}

function endCard(run, ev) {
  const clip = run.clip;
  const path = ev.path.join(" → ");
  if (ev.outcome === "delivered") {
    const d = ev.delivery, m = d.measurements, pr = run.attempts[d.artifact];
    const failedArts = Object.keys(run.verifies).filter(a => !run.verifies[a].passed);
    let inset = "";
    if (failedArts.length) {
      const a1 = failedArts[0], v1 = run.verifies[a1], p1 = run.attempts[a1];
      inset = `<div class="luma"><h4>In luminance only — what a thumbnail, a heavy re-encode or a colour-blind viewer sees</h4>
        <div class="luma-row">
          <div class="luma-item">${still(run, a1, outputSVG(clip, v1.measurements, gradeOpts(p1)), "out-still")}<b class="fail">attempt 1 · ${v1.measurements.separation.toFixed(2)}× ✗</b></div>
          <div class="luma-item">${still(run, d.artifact, outputSVG(clip, m, gradeOpts(pr)), "out-still")}<b class="pass">attempt ${d.attempts} · ${m.separation.toFixed(2)}× ✓</b></div>
        </div><small>Gate: edge luminance separation ≥ 1.50×. Measured on the finished composite; no capture-side predictor saw it.</small></div>`;
    }
    addCard(run, "end", `<span class="outcome delivered"><span class="big">Delivered</span></span><span class="chip">${d.attempts} attempt${d.attempts > 1 ? "s" : ""}</span><span class="chip">${d.fixes.length} fix${d.fixes.length === 1 ? "" : "es"}</span><span class="chip">retries ${d.budget.reprocesses_used} / ${d.budget.retry_budget}</span>`,
      `<div class="path">${esc(path)}</div>
      <div class="out-row">
        <div class="out-main">${still(run, d.artifact, outputSVG(clip, m, gradeOpts(pr)), "out-still")}<div class="out-cap">${d.artifact} · ${d.strategy}</div></div>
        <div class="numbers">
          <span class="k">canvas</span><span>${d.output.canvas.join("×")} · ${d.output.fps} fps</span>
          <span class="k">head height</span><span>${m.head_target.toFixed(3)} of frame</span>
          <span class="k">shoulder span</span><span>${pct(m.shoulder_span_p50)} of width</span>
          <span class="k">separation</span><span>${m.separation.toFixed(2)}× (≥ 1.50)</span>
          <span class="k">head spread</span><span>${pct(m.head_spread)} of height</span>
          <span class="k">frames</span><span>${m.frames} = source</span>
          <span class="k">audio</span><span>MD5 = source</span>
        </div>
      </div>${inset}${reportNotes(run)}`);
  } else {
    const r = ev.reshoot;
    addCard(run, "end", `<span class="outcome reshoot"><span class="big">Reshoot request</span></span><span class="chip">${r.attempts} attempt${r.attempts === 1 ? "" : "s"}</span><span class="chip">retries ${r.budget.reprocesses_used} / ${r.budget.retry_budget}</span>`,
      `<div class="path">${esc(path)}</div>
      <ul class="reshoot-list">${r.items.map(i => `<li><b>${esc(i.label)}</b>: ${esc(fmtVal(i))} vs ${esc(fmtThr(i.threshold, i.unit))}<br>${esc(i.detail)}<br><i>${esc(i.guidance)}</i></li>`).join("")}</ul>`);
  }
}
function reportNotes(run) {
  // capture-side warnings the delivery carries as guidance, from the last inspection
  const last = run.lastInspect;
  if (!last) return "";
  const warns = last.findings.filter(f => f.status === "warn");
  if (!warns.length) return "";
  const g = PROFILE.reshoot_guidance || {};
  return `<div class="report"><b>Report · capture guidance for next time</b><br>${warns.map(f => `• <b>${esc(f.label)}</b> ${esc(fmtVal(f))} — ${esc(g[f.id] || f.detail)}`).join("<br>")}</div>`;
}

/* ---------- 3. the session view and the numbers ------------------------------------------ */
function buildProcessed() {
  const runs = doneRuns();
  const wrap = $("#processed-cards"); wrap.innerHTML = "";
  const vs = runs.map(r => verdict(r.end));
  $("#processed-title").innerHTML = `${plural(runs.length, "recording")} processed — ${vs.map(v => verdictBadge(v)).join(`<span class="varr">·</span>`)}`;
  wrap.dataset.n = Math.min(runs.length, 4);
  runs.forEach((run, i) => {
    const ev = run.end, clip = run.clip;
    let out, cap;
    const v = verdict(ev);
    if (ev.outcome === "delivered") {
      const d = ev.delivery, pr = run.attempts[d.artifact];
      out = `<div class="frame">${media(run, d.artifact, outputStandIn(clip, pr))}</div>`;
      cap = `<span class="ftag pass">Verified ✓</span>${projected(run.verifies[d.artifact]) ? `<span class="chip proj" title="separation on this attempt is projected, pending ground truth">projected</span>` : ""}`;
    } else {
      const item = ev.reshoot.items[0];
      out = `<div class="frame reshoot"><b>Reshoot requested</b><span>${esc(firstSentence(item ? item.guidance : ""))}</span></div>`;
      cap = `<span class="ftag fail">Reshoot ✗</span>`;
    }
    const col = h("div", `pcard ${v.key}`, `
      <div class="pcard-h">${verdictBadge(v, true)}<span class="vline">${esc(v.line)}</span><b>${label(run)}</b><span class="fname">${esc(run.file.name)}</span><span class="who">${esc(clip.name)}</span></div>
      <div class="fsrc">${still(run, "source", sourceSVG(clip), "frame")}</div>
      <div class="fdown"><span class="vee">↓</span><div class="story">${storyChips(pathOf(run))}</div><span class="vee">↓</span></div>
      <div class="fout ${ev.outcome}">${out}</div>
      <div class="fcap">${cap}<button class="ghost small" data-trace="${run.n}">Trace</button></div>`);
    col.style.setProperty("--i", i);
    wrap.appendChild(col);
  });
  $$("#processed-cards [data-trace]").forEach(b => b.onclick = () => openDrawer(Number(b.dataset.trace)));
}
function updateNumbers() {
  const runs = doneRuns();
  const table = $("#payoff-table");
  $("#payoff-empty").hidden = runs.length > 0;
  if (!runs.length) { $("thead", table).innerHTML = ""; $("tbody", table).innerHTML = ""; $("#provenance ul").innerHTML = ""; return; }
  $("thead", table).innerHTML = `<tr><th></th>${runs.map(r => `<th>${label(r)}</th>`).join("")}</tr>`;
  const row = (k, f) => `<tr><td class="k">${k}</td>${runs.map(r => `<td>${f(r.end, r)}</td>`).join("")}</tr>`;
  const m = r => r.delivery ? r.delivery.measurements : null;
  $("tbody", table).innerHTML = [
    row("outcome", r => verdictBadge(verdict(r))),
    row("file", (r, run) => esc(run.file.name)),
    row("source", (r, run) => esc(run.clip.brief.split(" — ")[0])),
    row("decision path", r => esc(r.path.join(" → "))),
    row("fixes / attempts", r => r.delivery ? `${r.delivery.fixes.length} / ${r.delivery.attempts}` : "reshoot"),
    row("head height", r => m(r) ? m(r).head_target.toFixed(3) : "—"),
    row("shoulder span", r => m(r) ? pct(m(r).shoulder_span_p50) : "—"),
    row("separation", r => m(r) ? `${m(r).separation.toFixed(2)}×` : "—"),
    row("head spread", r => m(r) ? pct(m(r).head_spread) : "—"),
    row("frames · audio", r => m(r) ? `${m(r).frames} · MD5 =` : "—"),
  ].join("");
  $("#provenance ul").innerHTML = [...PROV].map(p => `<li>${esc(p)}</li>`).join("");
}

/* ---------- the drawer ---------------------------------------------------------------- */
function openDrawer(which) {                         // "details" or a run number
  updateNumbers();
  $("#backdrop").hidden = false; $("#drawer").hidden = false;
  $("#details").hidden = which !== "details";
  $$("#traces .trace").forEach(t => t.classList.toggle("show", Number(t.dataset.run) === which));
  const tabs = [["details", "Details"], ...RUNS.map(r => [r.n, `${label(r)} trace`])];
  $("#drawer-tabs").innerHTML = tabs.map(([k, l]) => `<button class="${k === which ? "on" : ""}" data-k="${k}">${esc(l)}</button>`).join("");
  $$("#drawer-tabs button").forEach(b => b.onclick = () => openDrawer(b.dataset.k === "details" ? "details" : Number(b.dataset.k)));
  if (which === "details") { $("#drawer-title").textContent = "Details"; $("#drawer-sub").textContent = "the numbers behind the outputs, and where they come from"; }
  else { const r = RUNS[which - 1]; $("#drawer-title").textContent = `${label(r)} — trace`; $("#drawer-sub").textContent = `${r.file.name} · how the decisions were made: every finding, decision, stage and gate`; }
}
function closeDrawer() { $("#backdrop").hidden = true; $("#drawer").hidden = true; }

/* ---------- streaming + pacing --------------------------------------------------------- */
function beat(ev) {
  const C = CADENCE;
  switch (ev.type) {
    case "run.start": return C * 0.8;
    case "phase": return ev.phase === "deliver" || ev.phase === "reshoot" ? C * 0.6 : C * 1.1;
    case "inspect.result": return C * 1.6;
    case "decide.result": return ev.decision.action === "deliver" ? C * 0.6 : C * 2.0;
    case "fix.result": return C * 1.2;
    case "process.result": return C * 1.4;
    case "verify.result": return ev.passed ? C * 1.6 : C * 3.0;   // the failure is the moment: let it land
    case "run.end": return C * 1.0;
    default: return C * 0.6;
  }
}
let ADVANCE = null;                                  // step mode: the tick waiting for a key
function pump(run) {
  if (run.timer) return;
  const tick = () => {
    if (run !== CUR) return;                         // a stale run stops itself
    const ev = run.queue.shift();
    if (!ev) { run.timer = null; return; }
    if (ev.type === "stream.end") { run.timer = null; if (run.onEnd) run.onEnd(); return; }
    if (ev.type === "inspect.result") run.lastInspect = ev.result;
    flow(ev);
    card(run, ev);
    if (ev.type === "run.end" || ev.type === "error") { run.timer = null; run.queue = []; if (run.onEnd) run.onEnd(); return; }   // the run is over the moment its outcome lands
    if (STEP && ev.type !== "run.start") { run.timer = -1; ADVANCE = () => { run.timer = null; ADVANCE = null; tick(); }; }
    else run.timer = setTimeout(tick, INSTANT ? 0 : beat(ev));
  };
  tick();
}
function stream(run) {
  return new Promise(resolve => {
    run.onEnd = resolve;
    const es = run.es = new EventSource(`/api/run/${run.clip.id}?demo=${DEMO ? 1 : 0}${BUDGET != null ? `&budget=${BUDGET}` : ""}`);
    let closed = false;
    es.onmessage = e => { run.queue.push(JSON.parse(e.data)); pump(run); };
    es.addEventListener("end", () => { closed = true; es.close(); run.queue.push({ type: "stream.end" }); pump(run); });
    es.onerror = () => { if (closed) return; closed = true; es.close(); run.queue.push({ type: "error", message: "stream closed" }, { type: "stream.end" }); pump(run); };
  });
}
async function runCurrent() {
  if (!CUR || RUNNING || CUR.end) return;
  const run = CUR, token = ++RUN_ID;
  RUNNING = true; buttons();
  $("#bench").classList.add("running");
  await stream(run);
  if (token !== RUN_ID || run !== CUR) return;
  RUNNING = false;
  $("#bench").classList.remove("running");
  buttons(); header();
}
function stopRun() {
  RUN_ID++;
  if (CUR) { clearTimeout(CUR.timer); CUR.timer = null; CUR.queue = []; if (CUR.es) { CUR.es.close(); CUR.es = null; } CUR.onEnd = null; }
  ADVANCE = null; RUNNING = false;
  $("#bench").classList.remove("running");
  buttons();
}
function discardCurrent() {                          // a recording that was never run is not part of the session
  if (CUR && !CUR.end) {
    const i = RUNS.indexOf(CUR);
    if (i >= 0) RUNS.splice(i, 1);
    if (CUR.file && CUR.file.url) URL.revokeObjectURL(CUR.file.url);
    CUR.trace.remove();
  }
  CUR = null;
}
function addAnother() {
  stopRun();
  discardCurrent();
  $("#file").value = "";
  dropStatus("");
  showView("intake");
}
function viewProcessed() {
  if (RUNNING) return;
  buildProcessed();
  showView("processed");
}
function backFromProcessed() {
  if (CUR) showView("bench"); else addAnother();
}
function clearSession() {
  stopRun();
  for (const r of RUNS) { if (r.file && r.file.url) URL.revokeObjectURL(r.file.url); r.trace.remove(); }
  RUNS.length = 0;
  PROV.clear();
  CUR = null;
  $("#file").value = "";
  dropStatus("");
  closeDrawer();
  showView("intake");
}
function buttons() {
  const done = !!(CUR && CUR.end), n = doneRuns().length;
  $("#make").hidden = RUNNING || done;
  $("#stop").hidden = !RUNNING;
  $("#add").hidden = !done;
  $("#view-processed").hidden = !done;
  $("#view-processed").textContent = `View processed recordings (${n})`;
  $("#change").hidden = RUNNING || done;
  $("#trace-btn").hidden = !CUR || (!RUNNING && !done && !CUR.story.length);
}

/* the media row takes the height left under the header and above the flow */
function fit() {
  const media = $("#media"); if (!media || $("#bench").hidden) return;
  const below = ["#flow", "#narrator", "#actions"].reduce((a, s) => a + $(s).getBoundingClientRect().height, 0);
  const availH = window.innerHeight - media.getBoundingClientRect().top - below - 14 - 12 * 3 - 46;   // 46: the two caption lines
  const availW = window.innerWidth - 44 - 110 - 26 * 2 - 24;
  const hFromW = availW / (16 / 9 + 9 / 16);
  const hgt = Math.max(200, Math.min(640, availH, hFromW));
  document.documentElement.style.setProperty("--media-h", `${Math.floor(hgt)}px`);
}

/* ---------- boot ----------------------------------------------------------------------- */
async function boot() {
  if (INSTANT) document.body.classList.add("instant");
  const mode = $("#mode");
  if (!DEMO) {
    mode.textContent = "live · not wired"; mode.classList.add("live");
    const n = $("#notice"); n.hidden = false;
    n.innerHTML = `<b>Live mode is not wired yet.</b><br>Open <code>?demo=1</code> — every measurement is replayed from the cached archive fixtures, deterministically, with no model calls.<br><br><a href="/?demo=1" style="color:var(--decide)">Open the demo →</a>`;
    $("#intake").hidden = true;
    return;
  }
  mode.innerHTML = `demo · cached<span class="more"> · no live model calls</span>`; mode.classList.add("demo");
  mode.title = "Every measurement and decision is replayed from demo/clips/<id>/*.json — deterministic, no OpenCV, no AWS.";
  PROFILE = await (await fetch("/api/profile")).json();
  const f = PROFILE;
  $("#profile-facts").textContent = `${f.name} · ${f.canvas.w}×${f.canvas.h} · head ${f.framing.head_target} · size cap ${pct(f.framing.size_cap)} · ${f.gates.length} gates · retry budget ${BUDGET != null ? `${BUDGET} (overridden)` : f.retry_budget}`;
  $("#out-cap").innerHTML = `<span class="muted">${f.canvas.w} × ${f.canvas.h} · verified against ${f.gates.length} gates</span>`;
  CLIPS = await (await fetch("/api/clips?demo=1")).json();

  // intake
  const drop = $("#drop"), file = $("#file");
  $("#choose").onclick = () => file.click();
  file.onchange = () => { if (file.files[0]) useFile(file.files[0]); };
  ["dragenter", "dragover"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => { const f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) useFile(f); });
  document.addEventListener("dragover", e => e.preventDefault());
  document.addEventListener("drop", e => e.preventDefault());
  const samples = $("#samples");
  samples.innerHTML = CLIPS.map(c => `<button class="sample" data-clip="${c.id}"><b>${esc(c.name)}</b><span>${esc((c.recognize && c.recognize.names || [c.id])[0])}</span></button>`).join("");
  $$("#samples .sample").forEach(b => b.onclick = () => { const c = CLIPS.find(c => c.id === b.dataset.clip); if (c) useSample(c); });
  $("#samples-toggle").onclick = () => { samples.hidden = !samples.hidden; };

  // bench
  $("#make").onclick = runCurrent;
  $("#stop").onclick = () => { stopRun(); if (CUR) mountBench(CUR); };
  $("#add").onclick = addAnother;
  $("#change").onclick = addAnother;
  $("#view-processed").onclick = viewProcessed;
  $("#trace-btn").onclick = () => CUR && openDrawer(CUR.n);
  // the session view
  $("#processed-nav").onclick = () => VIEW === "processed" ? backFromProcessed() : viewProcessed();
  $("#processed-back").onclick = backFromProcessed;
  $("#processed-add").onclick = addAnother;
  $("#clear-session").onclick = clearSession;
  $("#details-btn").onclick = () => openDrawer("details");
  $("#drawer-close").onclick = closeDrawer;
  $("#backdrop").onclick = closeDrawer;
  window.addEventListener("resize", fit);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") { closeDrawer(); return; }
    if (e.target.tagName === "BUTTON" || e.target.tagName === "SELECT" || e.target.tagName === "INPUT") return;
    if (e.key === " " || e.key === "Enter" || e.key === "ArrowRight") {
      e.preventDefault();
      if (ADVANCE) return ADVANCE();
      if (e.key === "ArrowRight") return;
      if (VIEW === "bench" && CUR && !RUNNING) { if (CUR.end) addAnother(); else runCurrent(); }
    }
  });
  buttons(); header();
  if (PICK) { const c = CLIPS.find(c => c.id === PICK); if (c) useSample(c); }
}
boot();
