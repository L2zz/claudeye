"""The self-contained HTML report shell.

Kept as one raw string literal with no external assets so the rendered
report is fully offline: CSS, vanilla JS, and hand-rolled SVG all live
inline, and every dynamic value reaches the DOM via textContent (never
innerHTML). Two substitution points — __SUMMARY_JSON__ (the embedded
summary payload) and __UI_STRINGS__ (the UI_STRINGS copy registry from
strings.py) — are filled by the html renderer.
"""

_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>claudeye — Claude Code usage report</title>
<style>
:root {
  /* teal-dark palette (var names kept; only values changed so all usages
     stay valid). role map: accent=info, warn, bad=crit, ok=good. */
  --bg:#080f14; --panel:#0e1b22; --panel-2:#122530; --panel-3:#0c1920;
  --text:#e7f3f1; --muted:#8ea9b1; --text-faint:#516871;
  --accent:#56B4E9; --warn:#E6A100; --bad:#E0491F; --ok:#00B08A;
  --border:#1d3540; --border-soft:#152a33;
  --mono:'SFMono-Regular','JetBrains Mono','IBM Plex Mono','Menlo','Consolas','Liberation Mono',monospace;
}
* { box-sizing:border-box; }
body { margin:0; padding:24px 30px 56px; background:var(--bg); color:var(--text);
  font:13px/1.5 var(--mono); }
h1 { font-size:20px; margin:0 0 4px; }
header { position:relative; }
.lang-toggle { position:absolute; top:0; right:0; display:flex; gap:4px; }
.lang-toggle .lang-btn { background:transparent; color:var(--muted); border:1px solid var(--border);
  border-radius:6px; padding:1px 9px; cursor:pointer; font-size:11.5px; }
.lang-toggle .lang-btn.active { color:var(--text); border-color:var(--accent); }
h2 { font-size:15px; margin:0 0 12px; }
h2 .conf { font-size:10px; color:var(--muted); border:1px solid var(--border);
  border-radius:10px; padding:1px 8px; margin-left:8px; vertical-align:2px; }
.meta { color:var(--muted); font-size:12px; }
header { display:flex; align-items:flex-end; justify-content:space-between; gap:20px;
  border-bottom:1px solid var(--border); padding-bottom:16px; }
.brand { display:flex; flex-direction:column; gap:2px; }
.brand h1 { font-size:19px; font-weight:700; letter-spacing:.5px; margin:0; }
.brand-sub { color:var(--text-faint); font-size:11.5px; letter-spacing:.3px; }
/* equal-width responsive card grid (mockup proportions): cards fill the row
   and reflow on narrow widths, using wide-screen space instead of leaving it
   empty. */
.cards { display:flex; flex-direction:column; gap:18px; margin-top:18px; }
.card-group { display:flex; flex-direction:column; gap:7px; }
.card-group .group-label { color:var(--muted); font-size:10px; text-transform:uppercase;
  letter-spacing:.09em; }
.card-group .group-cards { display:grid; grid-template-columns:repeat(6, 1fr); gap:12px; }
@media (max-width:1100px) { .card-group .group-cards { grid-template-columns:repeat(4, 1fr); } }
@media (max-width:720px)  { .card-group .group-cards { grid-template-columns:repeat(2, 1fr); } }
.card { background:var(--panel); border:1px solid var(--border); border-radius:8px;
  padding:14px 16px; }
.card .v { font-size:22px; font-weight:700; letter-spacing:-.3px; }
.card .l { color:var(--muted); font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; }
.card .sub { color:var(--muted); font-size:11px; margin-top:2px; }
.card.warn-on { border-color:rgba(230,161,0,.55); }
.card.warn-on .v { color:var(--warn); }
.card.linked { cursor:pointer; }
.card.linked:hover { border-color:var(--accent); }
.report-grid { display:flex; flex-direction:column; gap:16px; margin-top:16px; }
/* Diagnostic sections. Their heights vary wildly (a short chart next to a
   50-row table), so pure-CSS 2-column packing either strands a column
   (multi-column) or leaves row gaps (grid). JS (layoutDiagColumns) packs
   them into two balanced columns instead, greedily filling the shorter
   one; below 1000px it falls back to this single full-width flow. */
.diag-stack { display:flex; flex-direction:column; gap:16px; }
.diag-stack.two-col { flex-direction:row; align-items:flex-start; }
.diag-col { flex:1 1 0; min-width:0; display:flex; flex-direction:column; gap:16px; }
section { background:var(--panel); border:1px solid var(--border); border-radius:8px;
  padding:16px 20px; overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:12.5px;
  font-variant-numeric:tabular-nums; }
.card .v, .card .sub { font-variant-numeric:tabular-nums; }
tbody tr:nth-child(even) td { background:rgba(255,255,255,.018); }
tr.col-groups th { text-align:center; font-size:10px; text-transform:uppercase;
  letter-spacing:.08em; border-bottom:none; padding-bottom:0; color:var(--muted); }
tr.col-groups th + th { border-left:1px solid var(--border); }
th, td { padding:5px 8px; text-align:right; border-bottom:1px solid var(--border);
  white-space:nowrap; }
th { color:var(--muted); font-weight:500; }
th.sortable { cursor:pointer; }
th.sortable:hover { color:var(--text); }
th.text, td.text { text-align:left; }
tr:hover td { background:rgba(86,180,233,.05); }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:11.5px; }
.muted { color:var(--muted); }
.bar-grid { display:grid; grid-template-columns:minmax(150px,230px) 70px 1fr 100px;
  gap:4px 10px; align-items:center; font-size:12.5px; }
.bar-grid .tool-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  min-width:0; }
.bar-track { background:rgba(255,255,255,.05); border-radius:4px; height:16px; min-width:120px; }
.bar-fill { background:var(--accent); border-radius:4px; height:16px; }
.bar-fill.warn { background:var(--warn); }
.bar-fill.critical { background:var(--bad); }
.level-tag { display:inline-block; font-size:9.5px; border-radius:8px; padding:0 7px;
  margin-right:8px; text-transform:uppercase; letter-spacing:.04em; vertical-align:1px; }
.level-tag.info { background:rgba(86,180,233,.16); color:var(--accent); }
.level-tag.warn { background:rgba(230,161,0,.18); color:var(--warn); }
.level-tag.critical { background:rgba(224,73,31,.2); color:var(--bad); }
.advice-item.level-critical { border-left-color:var(--bad); }
.advice-item.level-info { border-left-color:var(--accent); }
.flag-chip.critical { background:rgba(224,73,31,.2); color:var(--bad); }
.flag-chip { display:inline-block; font-size:9.5px; border-radius:8px; padding:0 6px;
  margin-left:6px; background:rgba(230,161,0,.18); color:var(--warn);
  vertical-align:1px; white-space:nowrap; }
.advice-item.linked { cursor:pointer; }
.advice-item.linked:hover { border-left-color:var(--accent); }
.advice-item .rule-def { color:var(--muted); font-size:11px; margin-top:4px; }
.advice-item .conf-tag { display:inline-block; margin-left:8px; padding:1px 7px;
  border:1px solid var(--border); border-radius:9px; color:var(--muted);
  font-size:9.5px; line-height:1.35; vertical-align:1px; }
.advice-controls { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-bottom:10px; }
.advice-controls .rule-toggle { background:transparent; color:var(--text);
  border:1px solid var(--border); border-radius:12px; padding:2px 10px; cursor:pointer;
  font-size:11.5px; }
.advice-controls .rule-toggle.off { color:var(--muted); opacity:.55; text-decoration:line-through; }
.advice-controls .lvl-btn { background:transparent; color:var(--muted); border:1px solid var(--border);
  border-radius:12px; padding:2px 10px; cursor:pointer; font-size:11.5px; text-transform:uppercase;
  letter-spacing:.03em; }
.advice-controls .lvl-btn.sel { color:var(--text); border-color:var(--accent); }
#rule-catalog .cat-rule { padding:7px 0; border-bottom:1px solid var(--border); font-size:12px; }
#rule-catalog .cat-rule:last-child { border-bottom:none; }
#rule-catalog .cat-title { font-weight:600; }
#rule-catalog .cat-fire { float:right; font-size:10.5px; color:var(--muted); }
#rule-catalog .cat-fire.on { color:var(--warn); }
#rule-catalog .rule-def { color:var(--muted); font-size:11.5px; margin-top:3px; }
.wi-inputs { display:flex; flex-wrap:wrap; gap:14px; align-items:center; margin:8px 0 10px;
  font-size:12px; }
.wi-inputs label { color:var(--muted); }
.wi-inputs input { width:96px; background:#0c1920; border:1px solid var(--border);
  color:var(--text); border-radius:6px; padding:3px 7px; font-size:12px;
  font-variant-numeric:tabular-nums; margin-left:6px; }
.wi-inputs button { background:transparent; color:var(--muted); border:1px solid var(--border);
  border-radius:6px; padding:3px 10px; cursor:pointer; font-size:12px; }
.wi-row { display:grid; grid-template-columns:minmax(140px,220px) 120px 60px 1fr;
  gap:4px 10px; align-items:center; font-size:12px; padding:2px 0; }
.wi-row .num { text-align:right; }
.wi-status { font-size:10px; border-radius:8px; padding:0 7px; justify-self:start; }
.wi-status.fires { background:rgba(230,161,0,.18); color:var(--warn); }
.wi-status.critical { background:rgba(224,73,31,.2); color:var(--bad); }
.wi-status.blocked { background:rgba(255,255,255,.05); color:var(--muted); }
.wi-status.below { color:var(--muted); }
.wi-export { margin-top:12px; }
.wi-config { background:#0c1920; border:1px solid var(--border); border-radius:6px;
  padding:8px 10px; font-size:11.5px; overflow-x:auto; margin:4px 0; white-space:pre;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
.wi-copy { background:transparent; color:var(--muted); border:1px solid var(--border);
  border-radius:6px; padding:2px 10px; cursor:pointer; font-size:12px; }
.wi-copy:hover { color:var(--text); border-color:var(--accent); }
.bar-grid .num { text-align:right; }
.controls { margin-bottom:10px; font-size:12px; color:var(--muted); }
.controls button { background:transparent; color:var(--muted); border:1px solid var(--border);
  border-radius:6px; padding:2px 10px; margin-left:6px; cursor:pointer; font-size:12px; }
.controls button.active { color:var(--text); border-color:var(--accent); }
h2.foldable { cursor:pointer; user-select:none; }
h2.foldable::before { content:""; display:inline-block; width:7px; height:7px;
  border-radius:2px; background:var(--text-faint); margin-right:9px; vertical-align:1.5px; }
h2.foldable.attn::before { background:var(--warn); }
h2.foldable.crit::before { background:var(--bad); }
h2.foldable::after { content:" ▾"; color:var(--muted); font-size:11px; }
h2.foldable.folded::after { content:" ▸"; }
.sec-body.folded { display:none; }
button.show-toggle { display:block; background:transparent; color:var(--muted);
  border:1px solid var(--border); border-radius:6px; padding:3px 12px; margin-top:10px;
  cursor:pointer; font-size:12px; }
button.show-toggle:hover { color:var(--text); border-color:var(--accent); }
/* borderless skill rows — hover tint (and open row's brighter name) is the
   only foldability cue; no box, no caret. */
.skill-row { margin-top:1px; border-radius:6px; }
.skill-head { display:grid; grid-template-columns:minmax(150px,230px) 80px 1fr 110px;
  gap:4px 10px; align-items:center; padding:6px 10px; cursor:pointer; font-size:12.5px;
  border-radius:6px; }
.skill-head:hover { background:rgba(86,180,233,.07); }
.skill-head:hover .skill-name { color:var(--accent); }
.skill-row.open .skill-name { color:var(--text); }
.skill-head .skill-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  min-width:0; color:var(--muted); }
.skill-head .num { text-align:right; }
.skill-detail { padding:4px 12px 12px 12px; font-size:12px; }
.skill-detail.folded { display:none; }
#advice { margin-top:14px; }
.advice-item { border-left:3px solid var(--warn); background:var(--panel);
  border-radius:0 8px 8px 0; padding:8px 14px; margin-top:6px; font-size:13px; }
.advice-item .rule { color:var(--warn); font-size:10.5px; text-transform:uppercase;
  letter-spacing:.05em; margin-right:8px; }
.advice-item .conf-tag { color:var(--muted); font-size:10.5px; margin-left:8px; }
#daily-chart svg { display:block; margin:0; max-width:100%; }
#daily-chart svg text { font-variant-numeric:tabular-nums; }
#daily-chart g.day:hover rect { stroke:rgba(255,255,255,.4); stroke-width:1; }
#chart-tip { position:fixed; z-index:10; display:none; pointer-events:none;
  background:#122530; border:1px solid var(--border); border-radius:8px;
  padding:8px 12px; font-size:12px; box-shadow:0 4px 16px rgba(0,0,0,.45);
  font-variant-numeric:tabular-nums; }
#chart-tip .tip-title { font-weight:600; margin-bottom:4px; }
#chart-tip .tip-row { display:flex; align-items:center; gap:6px; margin-top:2px;
  white-space:nowrap; }
#chart-tip .sw { width:9px; height:9px; border-radius:2px; flex:none; }
#chart-tip .tip-total { color:var(--muted); margin-top:5px; padding-top:5px;
  border-top:1px solid var(--border); white-space:nowrap; }
#daily-chart .show-toggle { margin-left:auto; margin-right:auto; }
#daily-legend { justify-content:center; }
.flag { display:inline-block; font-size:10px; border-radius:9px; padding:0 7px; margin-left:4px; }
.flag.dup-read { background:rgba(230,161,0,.18); color:var(--warn); }
.flag.low-cache { background:rgba(224,73,31,.18); color:var(--bad); }
.flag.compacted { background:rgba(86,180,233,.18); color:var(--accent); }
.flag.errors { background:rgba(224,73,31,.25); color:var(--bad); }
.eff-ok { color:var(--ok); } .eff-warn { color:var(--warn); } .eff-bad { color:var(--bad); }
.legend { display:flex; flex-wrap:wrap; gap:14px; margin-top:10px; font-size:11.5px; color:var(--muted); }
.legend .sw { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:-1px; }
details { margin-top:12px; }
summary { cursor:pointer; color:var(--muted); font-size:13px; }
dl.conf-notes { font-size:12px; }
dl.conf-notes dt { color:var(--text); font-weight:600; margin-top:8px; }
dl.conf-notes dd { color:var(--muted); margin:0; }
.empty { color:var(--muted); font-size:13px; padding:12px 0; }
footer { color:var(--muted); font-size:11px; margin-top:24px; }
</style>
</head>
<body>
<header>
  <div class="brand">
    <h1>claudeye</h1>
    <div class="brand-sub" data-i18n="brand_sub">measurement layer for a self-improving harness</div>
  </div>
  <div class="lang-toggle" id="lang-toggle"></div>
  <div class="meta" id="meta-line"></div>
</header>
<div class="cards" id="totals-cards"></div>

<div class="report-grid">
<section class="span-full">
  <h2 class="foldable" data-body="body-advice"><span data-i18n="sec_advice">Advice — flagged patterns</span><span class="conf" id="conf-advice"></span></h2>
  <div class="sec-body" id="body-advice">
    <div class="advice-controls" id="advice-controls"></div>
    <div id="advice"></div>
    <details><summary data-i18n="sum_rules">All rules &amp; definitions</summary><div id="rule-catalog"></div></details>
    <details><summary data-i18n="sum_whatif">What-if — tune the skill-spend rule (exploration only)</summary>
      <div class="muted" style="margin:6px 0 2px" data-i18n="whatif_hint">Adjust the turns floor and new-tokens/turn threshold to see which skills would fire. This does not change the advice above or the graph colors.</div>
      <div id="skill-whatif"></div>
    </details>
  </div>
</section>

<div class="diag-stack">
<section>
  <h2 class="foldable" data-body="body-daily"><span data-i18n="sec_daily">Daily tokens by model</span><span class="conf" id="conf-daily"></span></h2>
  <div class="sec-body" id="body-daily">
    <div id="daily-chart"></div>
    <div class="legend" id="daily-legend"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-tools"><span data-i18n="sec_tools">Tool-result sizes</span><span class="conf" id="conf-tools"></span></h2>
  <div class="sec-body" id="body-tools">
    <div class="controls"><span data-i18n="ctl_sortby">sort by</span>
      <button id="btn-bytes" class="active" data-i18n="ctl_resultsize">result size</button>
      <button id="btn-calls" data-i18n="ctl_calls">calls</button>
      &nbsp;· <span data-i18n="ctl_show">show</span>
      <button id="flt-all" class="active" data-i18n="ctl_all">all</button>
      <button id="flt-skills" data-i18n="ctl_skills">skills only</button>
      <button id="flt-mcp" data-i18n="ctl_mcp">mcp only</button>
    </div>
    <div id="tool-bars"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-chains"><span data-i18n="sec_chains">Skill &amp; subagent chains</span><span class="conf" id="conf-chains"></span></h2>
  <div class="sec-body" id="body-chains">
    <div id="skill-chains"></div>
    <div id="agent-types"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-dup"><span data-i18n="sec_dup">Duplicate reads</span><span class="conf" id="conf-dup"></span></h2>
  <div class="sec-body" id="body-dup">
    <div id="dup-wrap"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-projects"><span data-i18n="sec_projects">Projects</span><span class="conf" id="conf-projects"></span></h2>
  <div class="sec-body" id="body-projects">
    <div id="projects-wrap"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-sessions"><span data-i18n="sec_sessions">Sessions</span><span class="conf" id="conf-sessions"></span></h2>
  <div class="sec-body" id="body-sessions">
    <div id="sessions-wrap"></div>
  </div>
</section>

</div>

<section class="span-full">
  <details id="warnings-details">
    <summary id="warnings-summary"></summary>
    <div id="warnings-wrap"></div>
  </details>
  <details>
    <summary data-i18n="sum_conf_notes">Confidence notes — what is measured vs inferred</summary>
    <dl class="conf-notes" id="conf-notes"></dl>
  </details>
</section>
</div>

<footer id="footer"></footer>

<script id="summary-data" type="application/json">__SUMMARY_JSON__</script>
<script>
"use strict";
const S = JSON.parse(document.getElementById("summary-data").textContent);

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}
function fmt(n) {
  if (n === null || n === undefined) return "–";
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(Math.round(n * 10) / 10);
}
function fmtBytes(b) {
  if (b === null || b === undefined) return "–";
  if (b >= 1024 * 1024 * 1024) return (b / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  if (b >= 1024 * 1024) return (b / (1024 * 1024)).toFixed(2) + " MB";
  if (b >= 1024) return (b / 1024).toFixed(1) + " KB";
  return Math.round(b * 10) / 10 + " B";
}
/* Okabe-Ito colorblind-safe qualitative palette, blue lightened and gray
   raised for dark backgrounds (codex-debate D4). */
const PALETTE = ["#56B4E9","#E69F00","#009E73","#F0E442","#CC79A7","#4C9FE8","#D55E00","#A6A6A6"];
const TOOL_LIMIT = 10, SESSION_LIMIT = 15, DUP_LIMIT = 10, DAY_LIMIT = 14;

/* i18n — every human-facing string lives in UI_STRINGS (strings.py),
   injected here by the html renderer. applyStatic() fills the static
   chrome labels (elements carrying data-i18n="key") from the active
   language and live-toggles them; the render functions read dynamic
   data labels from T = STRINGS[lang] at the report's generated language.
   Extensible: add a language by adding one dictionary plus a toggle entry. */
const STRINGS = __UI_STRINGS__;
let lang = STRINGS[(S.meta && S.meta.lang) || "en"] ? S.meta.lang : "en";
let T = STRINGS[lang];
function applyStatic() {
  document.querySelectorAll("[data-i18n]").forEach(node => {
    const v = STRINGS[lang][node.dataset.i18n];
    if (v !== undefined) node.textContent = v;
  });
  document.documentElement.lang = lang;
}
function renderLangToggle() {
  const wrap = document.getElementById("lang-toggle");
  wrap.textContent = "";
  [["en", "EN"], ["ko", "한국어"]].forEach(([code, label]) => {
    const btn = el("button", "lang-btn" + (lang === code ? " active" : ""), label);
    btn.addEventListener("click", () => {
      lang = code;
      T = STRINGS[lang];
      applyStatic();
      renderLangToggle();
      renderLocalized();
    });
    wrap.appendChild(btn);
  });
}
applyStatic();
renderLangToggle();

/* Warning state is derived from advice targets only — the graphs can
   never disagree with the advice list. Toggling a rule off (below) drops
   both its advice items and its graph flags. */
const advice = S.advice || [];
const adviceRules = S.advice_rules || {};
const adviceTh = S.advice_thresholds || {};
const LEVEL_ORDER = ["info", "warn", "critical"];
const hiddenRules = new Set();
let minLevel = "info"; // like a log level: show items at this severity or above
const lvlOf = a => a.level || "warn";
const activeAdvice = () => advice.filter(a =>
  !hiddenRules.has(a.rule)
  && LEVEL_ORDER.indexOf(lvlOf(a)) >= LEVEL_ORDER.indexOf(minLevel));
let TARGET_LEVEL = new Map(); // "kind:name" -> highest active level flagging it
function recomputeTargets() {
  TARGET_LEVEL = new Map();
  activeAdvice().filter(a => a.target).forEach(a => {
    const key = a.target.kind + ":" + a.target.name;
    if (!TARGET_LEVEL.has(key)
        || LEVEL_ORDER.indexOf(lvlOf(a)) > LEVEL_ORDER.indexOf(TARGET_LEVEL.get(key)))
      TARGET_LEVEL.set(key, lvlOf(a));
  });
}
recomputeTargets();
const flagLevel = (kind, name) => TARGET_LEVEL.get(kind + ":" + name) || null;
const isFlagged = (kind, name) => TARGET_LEVEL.has(kind + ":" + name);
const flagClass = lvl => (lvl === "warn" || lvl === "critical") ? " " + lvl : "";

/* fold/unfold: clicking a section heading collapses its body */
document.querySelectorAll("h2.foldable").forEach(heading => {
  heading.addEventListener("click", () => {
    const body = document.getElementById(heading.dataset.body);
    heading.classList.toggle("folded", body.classList.toggle("folded"));
  });
});

function showToggle(total, limit, expanded, noun, onClick) {
  if (total <= limit) return null;
  const btn = el("button", "show-toggle",
    expanded
      ? T.show_top_only_pre + limit + T.show_top_only_post
      : T.show_all_pre + total + " " + noun);
  btn.addEventListener("click", onClick);
  return btn;
}

/* header */
function renderMeta() {
  const m = S.meta;
  const parts = [
    T.meta_generated + m.generated_at,
    T.meta_input + m.input_root,
    m.since ? T.meta_since + m.since : null,
    m.project_filter ? T.meta_project + m.project_filter : null,
    m.redact_paths ? T.meta_redacted : null,
    "v" + m.version,
  ].filter(Boolean);
  document.getElementById("meta-line").textContent = parts.join(" · ");
  document.getElementById("conf-tools").textContent = T.conf_tools;
  document.getElementById("conf-daily").textContent = T.conf_daily;
  document.getElementById("conf-advice").textContent = T.conf_advice;
  document.getElementById("conf-chains").textContent = T.conf_chains;
  document.getElementById("conf-projects").textContent = T.conf_projects;
  document.getElementById("conf-sessions").textContent = T.conf_sessions;
  document.getElementById("conf-dup").textContent = T.conf_dup;
  const notes = document.getElementById("conf-notes");
  notes.textContent = "";
  Object.entries(m.confidence).forEach(([key, note]) => {
    notes.appendChild(el("dt", null, T["confname_" + key] || key));
    notes.appendChild(el("dd", null, T["confnote_" + key] || note));
  });
}

/* totals cards — volume vs waste-signal groups */
function renderCards() {
  const t = S.totals;
  const newTokens = t.input_tokens + t.output_tokens + t.cache_creation_tokens;
  const cacheShare = t.total_tokens > 0
    ? Math.round((t.cache_read_tokens / t.total_tokens) * 100) + "%" : "–";

  let peakDay = null, peakTotal = 0;
  const dayTotals = {};
  (S.by_day || []).forEach(r => {
    const sum = r.input_tokens + r.output_tokens + r.cache_read_tokens + r.cache_creation_tokens;
    dayTotals[r.date] = (dayTotals[r.date] || 0) + sum;
  });
  Object.entries(dayTotals).forEach(([date, sum]) => {
    if (sum > peakTotal) { peakTotal = sum; peakDay = date; }
  });

  const modelTotals = {};
  (S.by_day || []).forEach(r => {
    const sum = r.input_tokens + r.output_tokens + r.cache_read_tokens + r.cache_creation_tokens;
    modelTotals[r.model] = (modelTotals[r.model] || 0) + sum;
  });
  const models = Object.entries(modelTotals).sort((a, b) => b[1] - a[1]);
  const grand = models.reduce((acc, m) => acc + m[1], 0);
  const topModel = models.length ? models[0] : null;

  function jumpTo(bodyId) {
    const body = document.getElementById(bodyId);
    if (!body) return;
    body.classList.remove("folded");
    const heading = document.querySelector('h2.foldable[data-body="' + bodyId + '"]');
    if (heading) heading.classList.remove("folded");
    body.closest("section").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function card(label, value, sub, warnOn, anchor) {
    const node = el("div", "card" + (warnOn ? " warn-on" : ""));
    node.appendChild(el("div", "v", value));
    node.appendChild(el("div", "l", label));
    if (sub) node.appendChild(el("div", "sub", sub));
    if (anchor) {
      node.classList.add("linked");
      node.title = T.card_jump_title;
      node.addEventListener("click", anchor);
    }
    return node;
  }
  function group(label, cards) {
    const wrap = el("div", "card-group");
    wrap.appendChild(el("div", "group-label", label));
    const inner = el("div", "group-cards");
    cards.forEach(c => c && inner.appendChild(c));
    wrap.appendChild(inner);
    return wrap;
  }

  const volume = [
    card(T.card_total_tokens, fmt(t.total_tokens),
      t.sessions + " " + T.unit_sessions + " · "
      + fmt(t.requests + t.subagent_requests) + " " + T.unit_req),
    card(T.card_new_tokens, fmt(newTokens), T.card_new_tokens_sub),
    card(T.card_cache_reuse, fmt(t.cache_read_tokens),
      lang === "ko" ? T.card_cache_reuse_sub + " " + cacheShare
        : cacheShare + " " + T.card_cache_reuse_sub),
    card(T.card_tool_activity, fmt(t.tool_calls), T.card_tool_activity_sub),
    peakDay ? card(T.card_peak_day, peakDay.slice(5), fmt(peakTotal) + " " + T.unit_tokens) : null,
    topModel ? card(T.card_model_mix, topModel[0].replace(/^claude-/, ""),
      Math.round((topModel[1] / grand) * 100) + "%"
      + (models.length > 1 ? " · +" + (models.length - 1) + " " + T.unit_more : "")) : null,
  ];
  const waste = [
    card(T.card_tool_pollution, fmtBytes(t.tool_result_bytes), T.card_tool_pollution_sub, false,
      () => jumpTo("body-tools")),
    card(T.card_waste_signals,
      fmt(t.wasted_reads) + " · " + t.compactions + " · " + t.errors,
      T.card_waste_signals_sub,
      t.wasted_reads + t.compactions + t.errors > 0,
      () => jumpTo("body-dup")),
  ];
  if (S.meta.parse_warnings_total > 0) {
    waste.push(card(T.card_parse_warnings, S.meta.parse_warnings_total,
      T.card_parse_warnings_sub, true,
      () => {
        const details = document.getElementById("warnings-details");
        details.open = true;
        details.scrollIntoView({ behavior: "smooth", block: "start" });
      }));
  }

  const wrap = document.getElementById("totals-cards");
  wrap.textContent = "";
  wrap.appendChild(group(T.group_volume, volume));
  wrap.appendChild(group(T.group_waste, waste));
}

/* 2 — tool bars */
let toolsExpanded = false;
let currentMetric = "result_bytes";
let currentFilter = "all";
const TOOL_FILTERS = {
  all: () => true,
  skills: row => row.name === "Skill" || row.name.startsWith("Skill:"),
  mcp: row => row.name.startsWith("mcp__"),
};
function renderToolBars(metric) {
  currentMetric = metric;
  const wrap = document.getElementById("tool-bars");
  wrap.textContent = "";
  const pool = S.by_tool.filter(TOOL_FILTERS[currentFilter]);
  if (!pool.length) { wrap.appendChild(el("div", "empty", T.tools_empty)); return; }
  const all = [...pool].sort((a, b) => b[metric] - a[metric]);
  const rows = toolsExpanded ? all : all.slice(0, TOOL_LIMIT);
  const max = Math.max(...all.map(r => r[metric]), 1);
  const grid = el("div", "bar-grid");
  rows.forEach(row => {
    const name = el("div", "mono tool-name", row.name);
    name.title = row.name + T.tool_max_result_title + fmtBytes(row.max_result_bytes)
      + (row.errors ? " · " + row.errors + T.tool_errors_title : "");
    grid.appendChild(name);
    const toolLvl = flagLevel("tool", row.name);
    if (toolLvl) {
      name.appendChild(el("span", "flag-chip" + (toolLvl === "critical" ? " critical" : ""),
        T.tool_flag_chip));
      name.title += T.tool_flagged_title;
    }
    grid.appendChild(el("div", "num muted", fmt(row.calls) + "×"));
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill" + flagClass(toolLvl));
    fill.style.width = Math.max(0.5, (row[metric] / max) * 100) + "%";
    track.appendChild(fill);
    grid.appendChild(track);
    grid.appendChild(el("div", "num",
      metric === "result_bytes" ? fmtBytes(row.result_bytes) : fmt(row.calls) + T.unit_calls_suffix));
  });
  wrap.appendChild(grid);
  const toggle = showToggle(all.length, TOOL_LIMIT, toolsExpanded, T.noun_tools, () => {
    toolsExpanded = !toolsExpanded;
    renderToolBars(currentMetric);
  });
  if (toggle) wrap.appendChild(toggle);
}
document.getElementById("btn-bytes").addEventListener("click", () => {
  document.getElementById("btn-bytes").classList.add("active");
  document.getElementById("btn-calls").classList.remove("active");
  renderToolBars("result_bytes");
});
document.getElementById("btn-calls").addEventListener("click", () => {
  document.getElementById("btn-calls").classList.add("active");
  document.getElementById("btn-bytes").classList.remove("active");
  renderToolBars("calls");
});
["all", "skills", "mcp"].forEach(key => {
  document.getElementById("flt-" + key).addEventListener("click", () => {
    currentFilter = key;
    ["all", "skills", "mcp"].forEach(other =>
      document.getElementById("flt-" + other).classList.toggle("active", other === key));
    renderToolBars(currentMetric);
  });
});
renderToolBars("result_bytes");

/* advice dashboard — items, per-rule toggles, rule catalog, what-if */
function renderAdvice() {
  const wrap = document.getElementById("advice");
  wrap.textContent = "";
  const items = activeAdvice();
  if (!items.length) {
    wrap.appendChild(el("div", "empty", advice.length
      ? T.advice_empty_filtered
      : T.advice_empty_none));
    return;
  }
  items.forEach(item => {
    const level = lvlOf(item);
    const div = el("div", "advice-item level-" + level + (item.target ? " linked" : ""));
    div.appendChild(el("span", "level-tag " + level, level));
    const rule = adviceRules[item.rule];
    const ruleTitle = rule && rule.title_i18n && rule.title_i18n[lang]
      ? rule.title_i18n[lang] : (rule ? rule.title : item.rule);
    div.appendChild(el("span", "rule", ruleTitle));
    const message = item.message_i18n && item.message_i18n[lang]
      ? item.message_i18n[lang] : item.message;
    const confidence = item.confidence_i18n && item.confidence_i18n[lang]
      ? item.confidence_i18n[lang] : item.confidence;
    div.appendChild(document.createTextNode(message));
    div.appendChild(el("span", "conf-tag", confidence));
    if (rule) {
      const definition = rule.definition_i18n && rule.definition_i18n[lang]
        ? rule.definition_i18n[lang] : rule.definition;
      div.appendChild(el("div", "rule-def", definition));
    }
    if (item.target) {
      div.title = T.advice_jump_title + item.target.kind;
      div.addEventListener("click", () => {
        const bodyId = item.target.kind === "skill" ? "body-chains" : "body-tools";
        const body = document.getElementById(bodyId);
        body.classList.remove("folded");
        const heading = document.querySelector('h2.foldable[data-body="' + bodyId + '"]');
        if (heading) heading.classList.remove("folded");
        if (item.target.kind === "skill") {
          skillOpen.add(item.target.name);
          skillChainsExpanded = true; // the flagged skill may sit below the top-N cut
          renderSkillChains();
        }
        body.closest("section").scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
    wrap.appendChild(div);
  });
}
function markerLevel(items) {
  let best = -1;
  items.forEach(a => { const i = LEVEL_ORDER.indexOf(a.level || "warn"); if (i > best) best = i; });
  return best >= 0 ? LEVEL_ORDER[best] : null;
}
function setMarker(bodyId, lvl) {
  const h = document.querySelector('h2.foldable[data-body="' + bodyId + '"]');
  if (!h) return;
  h.classList.remove("attn", "crit");
  if (lvl === "critical") h.classList.add("crit");
  else if (lvl === "warn") h.classList.add("attn");
}
function updateSectionMarkers() {
  // Section-title LED follows advice (single source): the Advice header shows
  // the worst active level; tool/skill sections light up when advice targets them.
  const act = activeAdvice();
  setMarker("body-advice", markerLevel(act));
  setMarker("body-tools", markerLevel(act.filter(a => a.target && a.target.kind === "tool")));
  setMarker("body-chains", markerLevel(act.filter(a => a.target && a.target.kind === "skill")));
}
function refreshAdviceViews() {
  recomputeTargets();
  renderAdviceControls();
  renderAdvice();
  renderToolBars(currentMetric); // graph flags follow the active rules/level
  renderSkillChains();
  updateSectionMarkers();
}
function renderAdviceControls() {
  const wrap = document.getElementById("advice-controls");
  wrap.textContent = "";
  if (!advice.length) return;
  const present = [...new Set(advice.map(a => a.rule))];
  wrap.appendChild(el("span", "muted", T.advice_show));
  present.forEach(ruleId => {
    const rule = adviceRules[ruleId];
    const title = rule && rule.title_i18n && rule.title_i18n[lang]
      ? rule.title_i18n[lang] : (rule ? rule.title : ruleId);
    const btn = el("button", "rule-toggle" + (hiddenRules.has(ruleId) ? " off" : ""), title);
    btn.addEventListener("click", () => {
      if (hiddenRules.has(ruleId)) hiddenRules.delete(ruleId); else hiddenRules.add(ruleId);
      refreshAdviceViews();
    });
    wrap.appendChild(btn);
  });
  wrap.appendChild(el("span", "muted", T.advice_level_ge));
  LEVEL_ORDER.forEach(lv => {
    const btn = el("button", "lvl-btn" + (minLevel === lv ? " sel" : ""), lv);
    btn.addEventListener("click", () => { minLevel = lv; refreshAdviceViews(); });
    wrap.appendChild(btn);
  });
}
function renderRuleCatalog() {
  const wrap = document.getElementById("rule-catalog");
  if (!wrap) return;
  wrap.textContent = "";
  const fireCount = {};
  advice.forEach(a => { fireCount[a.rule] = (fireCount[a.rule] || 0) + 1; });
  Object.entries(adviceRules).forEach(([id, rule]) => {
    const div = el("div", "cat-rule");
    const n = fireCount[id] || 0;
    div.appendChild(el("span", "cat-fire" + (n ? " on" : ""),
      n ? n + " " + T.rulecat_firing : T.rulecat_dormant));
    if (rule.level) div.appendChild(el("span", "level-tag " + rule.level, rule.level));
    const title = rule.title_i18n && rule.title_i18n[lang]
      ? rule.title_i18n[lang] : rule.title;
    const definition = rule.definition_i18n && rule.definition_i18n[lang]
      ? rule.definition_i18n[lang] : rule.definition;
    div.appendChild(el("span", "cat-title", title));
    div.appendChild(el("div", "rule-def", definition));
    wrap.appendChild(div);
  });
}
function renderSkillWhatif() {
  const host = document.getElementById("skill-whatif");
  if (!host) return;
  host.textContent = "";
  if (!S.by_skill_chain || !S.by_skill_chain.length || !adviceTh.skill_min_turns) {
    host.appendChild(el("div", "empty", T.wi_empty)); return;
  }
  const inputs = el("div", "wi-inputs");
  const turnsLabel = el("label", null, T.wi_min_turns);
  const turnsInput = el("input"); turnsInput.type = "number"; turnsInput.min = "1";
  turnsInput.value = adviceTh.skill_min_turns; turnsLabel.appendChild(turnsInput);
  const spendLabel = el("label", null, T.wi_warn_ge);
  const spendInput = el("input"); spendInput.type = "number"; spendInput.min = "0";
  spendInput.step = "5000"; spendInput.value = adviceTh.skill_new_spend_per_turn;
  spendLabel.appendChild(spendInput);
  const critLabel = el("label", null, T.wi_critical_ge);
  const critInput = el("input"); critInput.type = "number"; critInput.min = "0";
  critInput.step = "5000"; critInput.value = adviceTh.skill_critical_new_spend_per_turn;
  critLabel.appendChild(critInput);
  const reset = el("button", null, T.wi_reset);
  inputs.appendChild(turnsLabel); inputs.appendChild(spendLabel);
  inputs.appendChild(critLabel); inputs.appendChild(reset);
  host.appendChild(inputs);
  const list = el("div"); host.appendChild(list);
  const exportWrap = el("div", "wi-export");
  exportWrap.appendChild(el("div", "muted", T.wi_persist_hint));
  const snippet = el("pre", "wi-config");
  const copyBtn = el("button", "wi-copy", T.wi_copy);
  copyBtn.addEventListener("click", () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(snippet.textContent).then(() => {
        copyBtn.textContent = T.wi_copied;
        setTimeout(() => { copyBtn.textContent = T.wi_copy; }, 1200);
      }).catch(() => {});
    }
  });
  exportWrap.appendChild(snippet);
  exportWrap.appendChild(copyBtn);
  host.appendChild(exportWrap);
  function draw() {
    list.textContent = "";
    const Tturns = Number(turnsInput.value) || 0;
    const Tspend = Number(spendInput.value) || 0;
    const Tcrit = Number(critInput.value) || 0;
    snippet.textContent = JSON.stringify({ advice: {
      skill_min_turns: Tturns,
      skill_new_spend_per_turn: Tspend,
      skill_critical_new_spend_per_turn: Tcrit,
    } }, null, 2);
    const rows = S.by_skill_chain.map(r => {
      const t = r.requests || 0;
      const newSpend = t > 0 ? (r.input_tokens + r.output_tokens + r.cache_creation_tokens) / t : 0;
      const bytesPT = t > 0 ? r.tool_result_bytes / t : 0;
      const fanout = t > 0 ? r.tool_calls / t : 0;
      const signal = newSpend >= Tspend
        || bytesPT >= adviceTh.skill_result_bytes_per_turn
        || fanout >= adviceTh.skill_fanout_per_turn;
      let status, cls;
      if (t < Tturns) {
        status = T.wi_status_blocked + t + T.wi_status_turns_lt + Tturns; cls = "blocked";
      }
      else if (signal && newSpend >= Tcrit) { status = T.wi_status_fire_critical; cls = "critical"; }
      else if (signal) { status = T.wi_status_fire_warn; cls = "fires"; }
      else { status = T.wi_status_below; cls = "below"; }
      return { name: r.skill, newSpend, t, status, cls };
    }).sort((a, b) => b.newSpend - a.newSpend).slice(0, 15);
    rows.forEach(r => {
      const row = el("div", "wi-row");
      const name = el("div", "mono tool-name", r.name); name.title = r.name;
      row.appendChild(name);
      row.appendChild(el("div", "num", fmt(r.newSpend) + " " + T.per_turn));
      row.appendChild(el("div", "num muted", r.t + "t"));
      row.appendChild(el("span", "wi-status " + r.cls, r.status));
      list.appendChild(row);
    });
  }
  turnsInput.addEventListener("input", draw);
  spendInput.addEventListener("input", draw);
  critInput.addEventListener("input", draw);
  reset.addEventListener("click", () => {
    turnsInput.value = adviceTh.skill_min_turns;
    spendInput.value = adviceTh.skill_new_spend_per_turn;
    critInput.value = adviceTh.skill_critical_new_spend_per_turn;
    draw();
  });
  draw();
}
renderAdviceControls();
renderAdvice();
renderRuleCatalog();
renderSkillWhatif();
updateSectionMarkers();

/* chart tooltip — one shared floating panel, immediate on hover */
const chartTip = el("div");
chartTip.id = "chart-tip";
document.body.appendChild(chartTip);
function moveTip(evt) {
  const pad = 14, edge = 8;
  const w = chartTip.offsetWidth, h = chartTip.offsetHeight;
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + w > window.innerWidth - edge) x = evt.clientX - w - pad;
  if (y + h > window.innerHeight - edge) y = evt.clientY - h - pad;
  // Clamp so the panel never leaves the viewport even when it is wider
  // or taller than the space on either side of the cursor.
  x = Math.max(edge, Math.min(x, window.innerWidth - w - edge));
  y = Math.max(edge, Math.min(y, window.innerHeight - h - edge));
  chartTip.style.left = x + "px";
  chartTip.style.top = y + "px";
}
function hideTip() { chartTip.style.display = "none"; }

/* 1 — daily stacked bars (SVG) */
let daysExpanded = false;
function renderDaily() {
  const wrap = document.getElementById("daily-chart");
  wrap.textContent = "";
  document.getElementById("daily-legend").textContent = "";
  if (!S.by_day.length) { wrap.appendChild(el("div", "empty", T.daily_empty)); return; }
  const allDays = [...new Set(S.by_day.map(r => r.date))].sort();
  const days = daysExpanded ? allDays : allDays.slice(-DAY_LIMIT);
  const modelTotals = {};
  S.by_day.forEach(r => {
    const total = r.input_tokens + r.output_tokens + r.cache_read_tokens + r.cache_creation_tokens;
    modelTotals[r.model] = (modelTotals[r.model] || 0) + total;
  });
  const models = Object.keys(modelTotals).sort((a, b) => modelTotals[b] - modelTotals[a]);
  const color = m => PALETTE[models.indexOf(m) % PALETTE.length];
  // Two layers per model (codex-debate D2): solid = new tokens actually
  // spent (input + output + cache creation), muted = cache-read reuse.
  const newSpend = r => r.input_tokens + r.output_tokens + r.cache_creation_tokens;
  const LAYERS = [
    [newSpend, 1.0],
    [r => r.cache_read_tokens, 0.32],
  ];
  const WEEKDAYS = [T.weekday_sun, T.weekday_mon, T.weekday_tue, T.weekday_wed,
    T.weekday_thu, T.weekday_fri, T.weekday_sat];

  function showDayTip(day) {
    chartTip.textContent = "";
    const rows = (byDay[day] || []).slice()
      .sort((a, b) => models.indexOf(a.model) - models.indexOf(b.model));
    const weekday = WEEKDAYS[new Date(day + "T00:00:00Z").getUTCDay()];
    chartTip.appendChild(el("div", "tip-title",
      day + " (" + weekday + ") — " + fmt(dayTotal(day)) + " " + T.unit_tokens));
    rows.forEach(r => {
      const line = el("div", "tip-row");
      const sw = el("span", "sw");
      sw.style.background = color(r.model);
      line.appendChild(sw);
      line.appendChild(document.createTextNode(
        r.model.replace(/^claude-/, "") + T.daily_tip_new + fmt(newSpend(r))
        + T.daily_tip_reuse + fmt(r.cache_read_tokens)));
      chartTip.appendChild(line);
    });
    const sum = rows.reduce((acc, r) => ({
      i: acc.i + r.input_tokens, o: acc.o + r.output_tokens,
      cw: acc.cw + r.cache_creation_tokens, cr: acc.cr + r.cache_read_tokens,
    }), { i: 0, o: 0, cw: 0, cr: 0 });
    chartTip.appendChild(el("div", "tip-total",
      T.daily_tip_input + fmt(sum.i) + T.daily_tip_output + fmt(sum.o)
      + T.daily_tip_cache_write + fmt(sum.cw) + T.daily_tip_cache_read + fmt(sum.cr)));
    chartTip.style.display = "block";
  }
  const byDay = {};
  S.by_day.forEach(r => { (byDay[r.date] = byDay[r.date] || []).push(r); });
  const dayTotal = d => (byDay[d] || []).reduce((acc, r) =>
    acc + r.input_tokens + r.output_tokens + r.cache_read_tokens + r.cache_creation_tokens, 0);
  const maxTotal = Math.max(...days.map(dayTotal), 1);

  const left = 58, bottom = 34, top = 12, H = 260;
  // Cap the per-day slot so a handful of days cluster tightly at the left
  // rather than stretching across the whole width (which pushed the bars
  // far apart); many days still divide the space and fill it.
  const cw = document.getElementById("daily-chart").clientWidth || 900;
  const slot = Math.min((cw - left - 16) / days.length, 88);
  const W = Math.round(left + days.length * slot + 16);
  const barW = Math.max(Math.min(slot * 0.72, 72), 6);
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("width", W); svg.setAttribute("height", H + top + bottom);
  const scale = v => (v / maxTotal) * H;

  [0, 0.5, 1].forEach(f => {
    const y = top + H - scale(maxTotal * f);
    const line = document.createElementNS(svgNS, "line");
    line.setAttribute("x1", left - 6); line.setAttribute("x2", W - 8);
    line.setAttribute("y1", y); line.setAttribute("y2", y);
    line.setAttribute("stroke", "#1d3540"); line.setAttribute("stroke-width", "1");
    svg.appendChild(line);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("x", left - 10); label.setAttribute("y", y + 4);
    label.setAttribute("text-anchor", "end");
    label.setAttribute("fill", "#8ea9b1"); label.setAttribute("font-size", "10");
    label.textContent = fmt(maxTotal * f);
    svg.appendChild(label);
  });

  days.forEach((day, i) => {
    let y = top + H;
    const x = left + i * slot + (slot - barW) / 2;
    const dayGroup = document.createElementNS(svgNS, "g");
    dayGroup.setAttribute("class", "day");
    models.forEach(model => {
      const row = (byDay[day] || []).find(r => r.model === model);
      if (!row) return;
      LAYERS.forEach(([valueOf, opacity]) => {
        const value = valueOf(row);
        if (!value) return;
        const h = Math.max(scale(value), 0.5);
        y -= h;
        const rect = document.createElementNS(svgNS, "rect");
        rect.setAttribute("x", x); rect.setAttribute("y", y);
        rect.setAttribute("width", barW); rect.setAttribute("height", h);
        rect.setAttribute("fill", color(model)); rect.setAttribute("fill-opacity", opacity);
        dayGroup.appendChild(rect);
      });
    });
    dayGroup.addEventListener("mouseenter", evt => { showDayTip(day); moveTip(evt); });
    dayGroup.addEventListener("mousemove", moveTip);
    dayGroup.addEventListener("mouseleave", hideTip);
    svg.appendChild(dayGroup);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("x", x + barW / 2); label.setAttribute("y", top + H + 16);
    label.setAttribute("text-anchor", "middle");
    const weekday = new Date(day + "T00:00:00Z").getUTCDay();
    const isWeekend = weekday === 0 || weekday === 6;
    label.setAttribute("fill", isWeekend ? "#56B4E9" : "#8ea9b1");
    label.setAttribute("font-size", "10");
    label.textContent = day.slice(5);
    if (isWeekend) {
      const tip = document.createElementNS(svgNS, "title");
      tip.textContent = weekday === 0 ? T.weekend_sunday : T.weekend_saturday;
      label.appendChild(tip);
    }
    svg.appendChild(label);
  });
  wrap.appendChild(svg);

  const legend = document.getElementById("daily-legend");
  models.forEach(model => {
    const item = el("span");
    const sw = el("span", "sw"); sw.style.background = color(model);
    item.appendChild(sw); item.appendChild(document.createTextNode(model));
    legend.appendChild(item);
  });
  const shade = el("span", "muted", T.daily_legend);
  legend.appendChild(shade);
  const toggle = showToggle(allDays.length, DAY_LIMIT, daysExpanded, T.noun_days, () => {
    daysExpanded = !daysExpanded;
    renderDaily();
  });
  if (toggle) wrap.appendChild(toggle);
}
renderDaily();
// Refit the bars whenever the chart's own width changes — not just on window
// resize but also when the two-column packer moves it into a narrower column.
// Guard on width so redraws (which change height) can't loop.
let dailyResizeTimer, lastChartW = document.getElementById("daily-chart").clientWidth;
function refitDaily() {
  const w = document.getElementById("daily-chart").clientWidth;
  if (w === lastChartW) return;
  lastChartW = w;
  renderDaily();
}
if (window.ResizeObserver) {
  new ResizeObserver(() => {
    clearTimeout(dailyResizeTimer);
    dailyResizeTimer = setTimeout(refitDaily, 100);
  }).observe(document.getElementById("daily-chart"));
} else {
  window.addEventListener("resize", () => {
    clearTimeout(dailyResizeTimer);
    dailyResizeTimer = setTimeout(renderDaily, 150);
  });
}

/* 3 — skill chains: cumulative-token ranking, click row to unfold the
   chained tool composition graph */
let skillChainsExpanded = false;
let chainMode = "total"; // "total" (누적) | "percall" (회당)
const skillOpen = new Set();
function renderSkillChains() {
  const wrap = document.getElementById("skill-chains");
  wrap.textContent = "";
  if (!S.by_skill_chain || !S.by_skill_chain.length) {
    wrap.appendChild(el("div", "empty", T.chains_empty));
    return;
  }
  const controls = el("div", "controls");
  controls.appendChild(document.createTextNode(T.chain_tool_composition));
  [["total", T.chain_mode_total], ["percall", T.chain_mode_percall]].forEach(([key, label]) => {
    const btn = el("button", chainMode === key ? "active" : null, label);
    btn.addEventListener("click", () => { chainMode = key; renderSkillChains(); });
    controls.appendChild(btn);
  });
  controls.appendChild(el("span", "muted", chainMode === "total"
    ? T.chain_hint_total
    : T.chain_hint_percall));
  wrap.appendChild(controls);
  // Heading and its explainer stay separate lines: a short scannable title,
  // the long ranking note below it.
  const title = el("div", "muted",
    chainMode === "total" ? T.chain_title_total : T.chain_title_percall);
  title.style.margin = "0 0 2px";
  title.style.fontWeight = "600";
  wrap.appendChild(title);
  const titleNote = el("div", "muted", T.chain_title_suffix);
  titleNote.style.margin = "0 0 6px";
  wrap.appendChild(titleNote);
  // Shared scales so bars are comparable ACROSS skills in both modes.
  let globalToolMax = 1, globalAvgMax = 1;
  S.by_skill_chain.forEach(r => r.tools.forEach(t => {
    if (t.result_bytes > globalToolMax) globalToolMax = t.result_bytes;
    const avg = t.calls > 0 ? t.result_bytes / t.calls : 0;
    if (avg > globalAvgMax) globalAvgMax = avg;
  }));
  // Attribution slices rank by NEW tokens, not total: cache_read is
  // ambient and double-counted across skills in one fat session.
  const skillValue = r => chainMode === "total"
    ? r.new_tokens
    : (r.requests > 0 ? r.new_tokens / r.requests : 0);
  const maxSkill = Math.max(...S.by_skill_chain.map(skillValue), 1);
  const grandSkillTokens = Math.max(
    S.by_skill_chain.reduce((acc, r) => acc + r.new_tokens, 0), 1);
  // Rank by the displayed metric so bar length and row order agree; the
  // top-N cut then keeps the biggest under the current mode.
  const ranked = [...S.by_skill_chain].sort((a, b) => skillValue(b) - skillValue(a));
  const rows = skillChainsExpanded ? ranked : ranked.slice(0, TOOL_LIMIT);
  rows.forEach(row => {
    const box = el("div", "skill-row" + (skillOpen.has(row.skill) ? " open" : ""));
    const head = el("div", "skill-head");
    const skillLvl = flagLevel("skill", row.skill);
    const name = el("span", "mono skill-name", row.skill);
    name.title = row.skill + " — "
      + Math.round((row.new_tokens / grandSkillTokens) * 100)
      + T.chain_name_pct_title
      + (skillLvl ? T.chain_name_flagged_title + skillLvl + ")" : "");
    if (skillLvl) {
      name.appendChild(el("span", "flag-chip" + (skillLvl === "critical" ? " critical" : ""),
        skillLvl === "critical" ? T.chain_flag_critical : T.chain_flag_review));
    }
    head.appendChild(name);
    head.appendChild(el("span", "num muted", fmt(row.requests) + " " + T.unit_turns));
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill" + flagClass(skillLvl));
    fill.style.width = Math.max(0.5, (skillValue(row) / maxSkill) * 100) + "%";
    track.appendChild(fill);
    head.appendChild(track);
    const headValue = el("span", "num", chainMode === "total"
      ? fmt(row.new_tokens)
      : fmt(skillValue(row)) + " " + T.per_turn);
    headValue.title = T.chain_head_new_tokens_title
      + fmt(row.cache_read_tokens) + T.chain_head_ambient_title
      + (chainMode === "total"
          ? T.chain_head_over_turns + row.requests + " " + T.unit_turns
          : T.chain_head_avg_over + row.requests + T.chain_head_turns_total_new
            + fmt(row.new_tokens));
    head.appendChild(headValue);
    box.appendChild(head);

    const detail = el("div", "skill-detail");
    if (!skillOpen.has(row.skill)) detail.classList.add("folded");
    detail.appendChild(el("div", "muted",
      T.chain_detail_new + fmt(row.new_tokens) + T.chain_detail_input + fmt(row.input_tokens)
      + T.chain_detail_output + fmt(row.output_tokens)
      + T.chain_detail_cache_write + fmt(row.cache_creation_tokens) + ")"
      + T.chain_detail_cache_read + fmt(row.cache_read_tokens) + T.chain_detail_ambient
      + " — " + fmt(row.tool_calls) + T.chain_detail_tool_calls
      + fmtBytes(row.tool_result_bytes) + T.chain_detail_results));
    if (row.tools.length) {
      const grid = el("div", "bar-grid");
      grid.style.marginTop = "6px";
      row.tools.forEach(tool => {
        const perCall = tool.calls > 0 ? tool.result_bytes / tool.calls : 0;
        const value = chainMode === "total" ? tool.result_bytes : perCall;
        const scale = chainMode === "total" ? globalToolMax : globalAvgMax;
        const toolName = el("div", "mono tool-name", tool.name);
        toolName.title = tool.name;
        grid.appendChild(toolName);
        const calls = el("div", "num muted", fmt(tool.calls) + "×");
        calls.title = chainMode === "total"
          ? tool.calls + T.chain_tool_calls_total_title
          : T.chain_tool_avg_title + tool.calls + T.chain_tool_calls_title;
        grid.appendChild(calls);
        const tTrack = el("div", "bar-track");
        const tFill = el("div", "bar-fill");
        tFill.style.width = Math.max(0.5, (value / scale) * 100) + "%";
        tTrack.appendChild(tFill);
        grid.appendChild(tTrack);
        const valueCell = el("div", "num", chainMode === "total"
          ? fmtBytes(tool.result_bytes)
          : fmtBytes(perCall) + " " + T.per_call);
        valueCell.title = chainMode === "total"
          ? T.chain_tool_total_of_title + tool.calls + T.chain_tool_calls_title
          : fmtBytes(tool.result_bytes) + T.chain_tool_total_over_title
            + tool.calls + T.chain_tool_calls_title;
        grid.appendChild(valueCell);
      });
      detail.appendChild(grid);
      if (row.tools.some(t => t.name.startsWith("Skill:"))) {
        detail.appendChild(el("div", "muted", T.chain_nested_note));
      }
    } else {
      detail.appendChild(el("div", "empty", T.chain_no_tools));
    }
    box.appendChild(detail);

    head.addEventListener("click", () => {
      if (skillOpen.has(row.skill)) skillOpen.delete(row.skill);
      else skillOpen.add(row.skill);
      renderSkillChains();
    });
    wrap.appendChild(box);
  });
  const toggle = showToggle(S.by_skill_chain.length, TOOL_LIMIT, skillChainsExpanded,
    T.noun_skills, () => { skillChainsExpanded = !skillChainsExpanded; renderSkillChains(); });
  if (toggle) wrap.appendChild(toggle);
}
renderSkillChains();

/* 3b — subagent tokens by dispatch type */
function renderAgentTypes() {
  const wrap = document.getElementById("agent-types");
  wrap.textContent = "";
  if (!S.by_agent_type || !S.by_agent_type.length) return;
  const title = el("div", "muted", T.agent_title);
  title.style.margin = "16px 0 2px";
  title.style.fontWeight = "600";
  wrap.appendChild(title);
  const titleNote = el("div", "muted", T.agent_title_sub);
  titleNote.style.margin = "0 0 6px";
  wrap.appendChild(titleNote);
  const table = el("table");
  const head = el("tr");
  [[T.agent_col_type, true], [T.agent_col_agents, false], [T.agent_col_req, false],
   [T.agent_col_new_tokens, false]]
    .forEach(([label, text]) => head.appendChild(el("th", text ? "text" : null, label)));
  const thead = el("thead"); thead.appendChild(head); table.appendChild(thead);
  const tbody = el("tbody");
  S.by_agent_type.forEach(row => {
    const tr = el("tr");
    tr.appendChild(el("td", "text mono", row.type));
    tr.appendChild(el("td", null, row.agents));
    tr.appendChild(el("td", null, row.requests));
    const tokens = el("td", null, fmt(row.new_tokens));
    tokens.title = T.agent_new_tokens_title + fmt(row.input_tokens)
      + T.agent_output_title + fmt(row.output_tokens)
      + T.agent_cache_write_title + fmt(row.cache_creation_tokens)
      + T.agent_cache_read_title + fmt(row.cache_read_tokens) + T.agent_ambient_title;
    tr.appendChild(tokens);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
}

/* 4 — projects rollup */
function renderProjects() {
  const wrap = document.getElementById("projects-wrap");
  wrap.textContent = "";
  if (!S.by_project || !S.by_project.length) {
    wrap.appendChild(el("div", "empty", T.projects_empty)); return;
  }
  const table = el("table");
  const head = el("tr");
  [[T.proj_col_project, true], [T.proj_col_sessions, false], [T.proj_col_req, false],
   [T.proj_col_tokens, false], [T.proj_col_cache_eff, false],
   [T.proj_col_tools, false], [T.proj_col_result_size, false], [T.proj_col_dup_rd, false],
   [T.proj_col_cmp, false], [T.proj_col_err, false]]
    .forEach(([label, text]) => head.appendChild(el("th", text ? "text" : null, label)));
  const thead = el("thead"); thead.appendChild(head); table.appendChild(thead);
  const tbody = el("tbody");
  S.by_project.forEach(row => {
    const tr = el("tr");
    const name = el("td", "text mono", row.project);
    name.title = row.project;
    tr.appendChild(name);
    tr.appendChild(el("td", null, row.sessions));
    tr.appendChild(el("td", null,
      row.requests + (row.subagent_requests ? "+" + row.subagent_requests : "")));
    const tokens = el("td", null, fmt(row.total_tokens));
    tokens.title = T.tokens_input_title + fmt(row.input_tokens)
      + T.tokens_output_title + fmt(row.output_tokens)
      + T.tokens_cache_read_title + fmt(row.cache_read_tokens)
      + T.tokens_cache_creation_title + fmt(row.cache_creation_tokens);
    tr.appendChild(tokens);
    const eff = el("td");
    if (row.cache_efficiency === null) eff.textContent = "–";
    else {
      const pct = Math.round(row.cache_efficiency * 100);
      eff.textContent = pct + "%";
      eff.className = pct < 50 ? "eff-bad" : pct < 80 ? "eff-warn" : "eff-ok";
    }
    tr.appendChild(eff);
    tr.appendChild(el("td", null, fmt(row.tool_calls)));
    tr.appendChild(el("td", null, fmtBytes(row.tool_result_bytes)));
    tr.appendChild(el("td", null, row.wasted_reads || ""));
    tr.appendChild(el("td", null, row.compactions || ""));
    tr.appendChild(el("td", null, row.errors || ""));
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
}

/* 5 — sessions table */
function renderSessions() {
  const wrap = document.getElementById("sessions-wrap");
  wrap.textContent = "";
  if (!S.sessions.length) { wrap.appendChild(el("div", "empty", T.sessions_empty)); return; }
  const COLS = [
    { key: "project", label: T.sess_col_project, text: true },
    { key: "session_id", label: T.sess_col_session, text: true, render: (row, td) => {
        td.classList.add("mono"); td.title = row.session_id;
        td.textContent = row.session_id.slice(0, 8);
        if (row.subagents) {
          const chip = el("span", "muted", " +" + row.subagents + " " + T.unit_sub);
          td.appendChild(chip);
        }
      } },
    { key: "first_ts", label: T.sess_col_start, text: true, render: (row, td) => {
        td.textContent = row.first_ts ? row.first_ts.slice(0, 16).replace("T", " ") : "–";
      } },
    { key: "duration_min", label: T.sess_col_min },
    { key: "requests", label: T.sess_col_req, render: (row, td) => {
        td.textContent = row.requests + (row.subagent_requests ? "+" + row.subagent_requests : "");
      } },
    { key: "total_tokens", label: T.sess_col_tokens, render: (row, td) => {
        td.textContent = fmt(row.total_tokens); td.title =
          T.tokens_input_title + fmt(row.input_tokens) + T.tokens_output_title + fmt(row.output_tokens)
          + T.tokens_cache_read_title + fmt(row.cache_read_tokens)
          + T.tokens_cache_creation_title + fmt(row.cache_creation_tokens)
          + (row.subagent_total_tokens ? T.sess_subagents_title + fmt(row.subagent_total_tokens) : "");
      } },
    { key: "cache_efficiency", label: T.sess_col_cache_eff, render: (row, td) => {
        if (row.cache_efficiency === null) { td.textContent = "–"; return; }
        const pct = Math.round(row.cache_efficiency * 100);
        td.textContent = pct + "%";
        td.className = pct < 50 ? "eff-bad" : pct < 80 ? "eff-warn" : "eff-ok";
      } },
    { key: "tool_calls", label: T.sess_col_tools, render: (row, td) => { td.textContent = fmt(row.tool_calls); } },
    { key: "wasted_reads", label: T.sess_col_dup_rd },
    { key: "compactions", label: T.sess_col_cmp, render: (row, td) => {
        td.textContent = row.compactions || "";
        if (row.compact_pre_tokens && row.compact_pre_tokens.length)
          td.title = T.sess_precompact_title + row.compact_pre_tokens.map(fmt).join(", ");
      } },
    { key: "errors", label: T.sess_col_err, render: (row, td) => { td.textContent = row.errors || ""; } },
    { key: "flags", label: T.sess_col_flags, text: true, sortValue: row => row.flags.length,
      render: (row, td) => {
        row.flags.forEach(flag => td.appendChild(
          el("span", "flag " + flag, T["flag_" + flag] || flag)));
      } },
  ];
  let sortKey = "total_tokens", sortDir = -1, showAll = false;
  const table = el("table");
  const thead = el("thead");
  const groupRow = el("tr", "col-groups");
  [[T.sess_group_identity, 4], [T.sess_group_tokens, 3], [T.sess_group_activity, 1],
   [T.sess_group_waste, 4]]
    .forEach(([label, span]) => {
      const th = el("th", null, label);
      th.colSpan = span;
      groupRow.appendChild(th);
    });
  thead.appendChild(groupRow);
  const headRow = el("tr");
  COLS.forEach(col => {
    const th = el("th", "sortable" + (col.text ? " text" : ""), col.label);
    th.addEventListener("click", () => {
      if (sortKey === col.key) sortDir *= -1; else { sortKey = col.key; sortDir = -1; }
      drawBody(); markSorted();
    });
    th.dataset.key = col.key;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow); table.appendChild(thead);
  const tbody = el("tbody"); table.appendChild(tbody);
  function markSorted() {
    headRow.querySelectorAll("th").forEach(th => {
      const base = th.dataset.key === sortKey ? (sortDir < 0 ? " ▾" : " ▴") : "";
      th.textContent = COLS.find(c => c.key === th.dataset.key).label + base;
    });
  }
  function drawBody() {
    const col = COLS.find(c => c.key === sortKey);
    const value = row => col.sortValue ? col.sortValue(row)
      : row[sortKey] === null || row[sortKey] === undefined ? -Infinity : row[sortKey];
    const sorted = [...S.sessions].sort((a, b) => {
      const va = value(a), vb = value(b);
      if (typeof va === "string" || typeof vb === "string")
        return String(va).localeCompare(String(vb)) * sortDir;
      return (va - vb) * sortDir;
    });
    const rows = showAll ? sorted : sorted.slice(0, SESSION_LIMIT);
    tbody.textContent = "";
    rows.forEach(row => {
      const tr = el("tr");
      COLS.forEach(col2 => {
        const td = el("td", col2.text ? "text" : null);
        if (col2.render) col2.render(row, td);
        else td.textContent = row[col2.key] === null || row[col2.key] === undefined
          ? "–" : row[col2.key];
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    toggleBtn.textContent = showAll
      ? T.show_top_only_pre + SESSION_LIMIT + T.show_top_only_post
      : T.show_all_pre + S.sessions.length + " " + T.noun_sessions;
    toggleBtn.style.display = S.sessions.length > SESSION_LIMIT ? "" : "none";
  }
  const toggleBtn = el("button", "show-toggle");
  toggleBtn.addEventListener("click", () => { showAll = !showAll; drawBody(); });
  drawBody(); markSorted();
  wrap.appendChild(table);
  wrap.appendChild(toggleBtn);
}

/* 6 — duplicate reads */
let dupExpanded = false;
function renderDup() {
  const wrap = document.getElementById("dup-wrap");
  wrap.textContent = "";
  if (!S.dup_reads.length) { wrap.appendChild(el("div", "empty", T.dup_empty)); return; }
  const table = el("table");
  const head = el("tr");
  [[T.dup_col_file, true], [T.dup_col_reads, false], [T.dup_col_wasted, false],
   [T.dup_col_sessions, false], [T.dup_col_max, false]]
    .forEach(([label, text]) => head.appendChild(el("th", text ? "text" : null, label)));
  const thead = el("thead"); thead.appendChild(head); table.appendChild(thead);
  const tbody = el("tbody");
  const rows = dupExpanded ? S.dup_reads : S.dup_reads.slice(0, DUP_LIMIT);
  rows.forEach(row => {
    const tr = el("tr");
    const pathCell = el("td", "text mono");
    pathCell.title = row.path;
    pathCell.textContent = row.path.length > 80 ? "…" + row.path.slice(-79) : row.path;
    tr.appendChild(pathCell);
    tr.appendChild(el("td", null, row.reads));
    tr.appendChild(el("td", null, row.wasted_reads));
    tr.appendChild(el("td", null, row.sessions));
    tr.appendChild(el("td", null, row.max_in_one_context));
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
  const toggle = showToggle(S.dup_reads.length, DUP_LIMIT, dupExpanded, T.noun_files, () => {
    dupExpanded = !dupExpanded;
    renderDup();
  });
  if (toggle) wrap.appendChild(toggle);
}
renderDup();

/* warnings + footer */
function renderWarnings() {
  const total = S.meta.parse_warnings_total;
  document.getElementById("warnings-summary").textContent =
    T.warn_summary_pre + total + (S.parse_warnings.length < total
      ? T.warn_summary_showing + S.parse_warnings.length : "") + ")";
  const wrap = document.getElementById("warnings-wrap");
  wrap.textContent = "";
  if (!S.parse_warnings.length) { wrap.appendChild(el("div", "empty", T.warn_empty)); return; }
  const table = el("table");
  const head = el("tr");
  [[T.warn_col_file, true], [T.warn_col_line, false], [T.warn_col_reason, true]].forEach(([label, text]) =>
    head.appendChild(el("th", text ? "text" : null, label)));
  const thead = el("thead"); thead.appendChild(head); table.appendChild(thead);
  const tbody = el("tbody");
  S.parse_warnings.forEach(w => {
    const tr = el("tr");
    const file = el("td", "text mono");
    file.title = w.file;
    file.textContent = w.file.length > 70 ? "…" + w.file.slice(-69) : w.file;
    tr.appendChild(file);
    tr.appendChild(el("td", null, w.line));
    tr.appendChild(el("td", "text", w.reason));
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
}
function renderFooter() {
  document.getElementById("footer").textContent =
    "claudeye v" + S.meta.version + T.footer_suffix;
}

function renderLocalized() {
  renderMeta();
  renderCards();
  renderToolBars(currentMetric);
  renderAdviceControls();
  renderAdvice();
  renderRuleCatalog();
  renderSkillWhatif();
  renderDaily();
  renderSkillChains();
  renderAgentTypes();
  renderProjects();
  renderSessions();
  renderDup();
  renderWarnings();
  renderFooter();
  updateSectionMarkers();
}

renderMeta();
renderCards();
renderAgentTypes();
renderProjects();
renderSessions();
renderWarnings();
renderFooter();

/* Two-column masonry for the diagnostic sections: greedily drop each into
   the shorter column so no column is left stranded with whitespace (pure
   CSS can't pack such uneven heights). One column below 1000px; re-packs
   on resize. A later fold/expand just shortens its column in place. */
(function layoutDiagColumns() {
  const stack = document.querySelector(".diag-stack");
  if (!stack) return;
  const sections = Array.prototype.slice.call(stack.querySelectorAll(":scope > section"));
  let built = false;
  function pack() {
    if (built) {  // tear down: restore original order, drop the column wrappers
      sections.forEach(s => stack.appendChild(s));
      stack.querySelectorAll(":scope > .diag-col").forEach(c => c.remove());
      stack.classList.remove("two-col");
      built = false;
    }
    if (window.innerWidth <= 1000) { refitDaily(); return; }  // single-column fallback
    // Longest-processing-time bin-packing: place the tallest sections first
    // into the shorter column. Greedy DOM order lets one late tall section
    // (e.g. Sessions) strand a column; tallest-first keeps the two balanced.
    const ordered = sections
      .map(s => ({ s, h: s.offsetHeight }))  // measured full-width, pre-split
      .sort((a, b) => b.h - a.h);
    stack.classList.add("two-col");
    const cols = [document.createElement("div"), document.createElement("div")];
    cols.forEach(c => { c.className = "diag-col"; stack.appendChild(c); });
    const h = [0, 0];
    ordered.forEach(({ s }) => {
      const i = h[0] <= h[1] ? 0 : 1;   // shorter column wins ties left
      cols[i].appendChild(s);
      h[i] += s.offsetHeight;           // measured at the real 50% column width
    });
    built = true;
    refitDaily();  // the daily chart now sits in a narrower column — refit its bars
  }
  pack();
  let t;
  window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(pack, 150); });
})();
</script>
</body>
</html>
"""
