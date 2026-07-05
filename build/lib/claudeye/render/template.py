"""The self-contained HTML report shell.

Kept as one raw string literal with no external assets so the rendered
report is fully offline: CSS, vanilla JS, and hand-rolled SVG all live
inline, and every dynamic value reaches the DOM via textContent (never
innerHTML). __SUMMARY_JSON__ is the only substitution point — the html
renderer replaces it with the embedded summary payload.
"""

_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>claudeye — Claude Code usage report</title>
<style>
:root {
  --bg:#0f1115; --panel:#181b22; --text:#e8eaf0; --muted:#9aa3b2;
  --accent:#7aa2f7; --warn:#e0af68; --bad:#f7768e; --ok:#9ece6a; --border:#2a2f3a;
}
* { box-sizing:border-box; }
body { margin:0; padding:24px; background:var(--bg); color:var(--text);
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }
h1 { font-size:20px; margin:0 0 4px; }
h2 { font-size:15px; margin:0 0 12px; }
h2 .conf { font-size:10px; color:var(--muted); border:1px solid var(--border);
  border-radius:10px; padding:1px 8px; margin-left:8px; vertical-align:2px; }
.meta { color:var(--muted); font-size:12px; }
.cards { display:flex; flex-wrap:wrap; gap:16px 22px; margin-top:16px; }
.card-group { display:flex; flex-direction:column; gap:6px; }
.card-group .group-label { color:var(--muted); font-size:10px; text-transform:uppercase;
  letter-spacing:.09em; }
.card-group .group-cards { display:flex; flex-wrap:wrap; gap:10px; }
.card { background:var(--panel); border:1px solid var(--border); border-radius:8px;
  padding:10px 14px; min-width:120px; }
.card .v { font-size:19px; font-weight:600; }
.card .l { color:var(--muted); font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; }
.card .sub { color:var(--muted); font-size:11px; margin-top:2px; }
.card.warn-on { border-color:rgba(224,175,104,.55); }
.card.warn-on .v { color:var(--warn); }
.card.linked { cursor:pointer; }
.card.linked:hover { border-color:var(--accent); }
section { background:var(--panel); border:1px solid var(--border); border-radius:8px;
  padding:16px 20px; margin-top:16px; overflow-x:auto; }
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
tr:hover td { background:rgba(122,162,247,.05); }
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
.level-tag.info { background:rgba(122,162,247,.16); color:var(--accent); }
.level-tag.warn { background:rgba(224,175,104,.18); color:var(--warn); }
.level-tag.critical { background:rgba(247,118,142,.2); color:var(--bad); }
.advice-item.level-critical { border-left-color:var(--bad); }
.advice-item.level-info { border-left-color:var(--accent); }
.flag-chip.critical { background:rgba(247,118,142,.2); color:var(--bad); }
.flag-chip { display:inline-block; font-size:9.5px; border-radius:8px; padding:0 6px;
  margin-left:6px; background:rgba(224,175,104,.18); color:var(--warn);
  vertical-align:1px; white-space:nowrap; }
.advice-item.linked { cursor:pointer; }
.advice-item.linked:hover { border-left-color:var(--accent); }
.advice-item .rule-def { color:var(--muted); font-size:11px; margin-top:4px; }
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
.wi-inputs input { width:96px; background:#12151c; border:1px solid var(--border);
  color:var(--text); border-radius:6px; padding:3px 7px; font-size:12px;
  font-variant-numeric:tabular-nums; margin-left:6px; }
.wi-inputs button { background:transparent; color:var(--muted); border:1px solid var(--border);
  border-radius:6px; padding:3px 10px; cursor:pointer; font-size:12px; }
.wi-row { display:grid; grid-template-columns:minmax(140px,220px) 120px 60px 1fr;
  gap:4px 10px; align-items:center; font-size:12px; padding:2px 0; }
.wi-row .num { text-align:right; }
.wi-status { font-size:10px; border-radius:8px; padding:0 7px; justify-self:start; }
.wi-status.fires { background:rgba(224,175,104,.18); color:var(--warn); }
.wi-status.critical { background:rgba(247,118,142,.2); color:var(--bad); }
.wi-status.blocked { background:rgba(255,255,255,.05); color:var(--muted); }
.wi-status.below { color:var(--muted); }
.wi-export { margin-top:12px; }
.wi-config { background:#12151c; border:1px solid var(--border); border-radius:6px;
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
h2.foldable::after { content:" ▾"; color:var(--muted); font-size:11px; }
h2.foldable.folded::after { content:" ▸"; }
.sec-body.folded { display:none; }
button.show-toggle { display:block; background:transparent; color:var(--muted);
  border:1px solid var(--border); border-radius:6px; padding:3px 12px; margin-top:10px;
  cursor:pointer; font-size:12px; }
button.show-toggle:hover { color:var(--text); border-color:var(--accent); }
.skill-row { border:1px solid var(--border); border-radius:8px; margin-top:6px; }
.skill-head { display:grid; grid-template-columns:16px minmax(150px,230px) 80px 1fr 110px;
  gap:4px 10px; align-items:center; padding:6px 10px; cursor:pointer; font-size:12.5px; }
.skill-head:hover { background:rgba(122,162,247,.05); }
.skill-head .caret { color:var(--muted); font-size:10px; }
.skill-head .skill-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  min-width:0; }
.skill-head .num { text-align:right; }
.skill-detail { padding:4px 12px 10px 36px; font-size:12px; }
.skill-detail.folded { display:none; }
#advice { margin-top:14px; }
.advice-item { border-left:3px solid var(--warn); background:var(--panel);
  border-radius:0 8px 8px 0; padding:8px 14px; margin-top:6px; font-size:13px; }
.advice-item .rule { color:var(--warn); font-size:10.5px; text-transform:uppercase;
  letter-spacing:.05em; margin-right:8px; }
.advice-item .conf-tag { color:var(--muted); font-size:10.5px; margin-left:8px; }
#daily-chart svg { display:block; margin:0 auto; }
#daily-chart svg text { font-variant-numeric:tabular-nums; }
#daily-chart g.day:hover rect { stroke:rgba(255,255,255,.4); stroke-width:1; }
#chart-tip { position:fixed; z-index:10; display:none; pointer-events:none;
  background:#1f2430; border:1px solid var(--border); border-radius:8px;
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
.flag.dup-read { background:rgba(224,175,104,.18); color:var(--warn); }
.flag.low-cache { background:rgba(247,118,142,.18); color:var(--bad); }
.flag.compacted { background:rgba(122,162,247,.18); color:var(--accent); }
.flag.errors { background:rgba(247,118,142,.25); color:var(--bad); }
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
  <h1>claudeye — Claude Code usage</h1>
  <div class="meta" id="meta-line"></div>
</header>
<div class="cards" id="totals-cards"></div>

<section>
  <h2 class="foldable" data-body="body-advice">Advice — flagged patterns<span class="conf" id="conf-advice"></span></h2>
  <div class="sec-body" id="body-advice">
    <div class="advice-controls" id="advice-controls"></div>
    <div id="advice"></div>
    <details><summary>All rules &amp; definitions</summary><div id="rule-catalog"></div></details>
    <details><summary>What-if — tune the skill-spend rule (exploration only)</summary>
      <div class="muted" style="margin:6px 0 2px">Adjust the turns floor and new-tokens/turn threshold to see which skills <em>would</em> fire. This does not change the advice above or the graph colors.</div>
      <div id="skill-whatif"></div>
    </details>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-daily">1 · Daily tokens by model<span class="conf" id="conf-daily"></span></h2>
  <div class="sec-body" id="body-daily">
    <div id="daily-chart"></div>
    <div class="legend" id="daily-legend"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-tools">2 · Tool pollution ranking<span class="conf" id="conf-tools"></span></h2>
  <div class="sec-body" id="body-tools">
    <div class="controls">sort by
      <button id="btn-bytes" class="active">result size</button>
      <button id="btn-calls">calls</button>
      &nbsp;· show
      <button id="flt-all" class="active">all</button>
      <button id="flt-skills">skills only</button>
      <button id="flt-mcp">mcp only</button>
    </div>
    <div id="tool-bars"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-chains">3 · Skill &amp; subagent chains<span class="conf" id="conf-chains"></span></h2>
  <div class="sec-body" id="body-chains">
    <div id="skill-chains"></div>
    <div id="agent-types"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-projects">4 · Projects<span class="conf" id="conf-projects"></span></h2>
  <div class="sec-body" id="body-projects">
    <div id="projects-wrap"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-sessions">5 · Sessions<span class="conf" id="conf-sessions"></span></h2>
  <div class="sec-body" id="body-sessions">
    <div id="sessions-wrap"></div>
  </div>
</section>

<section>
  <h2 class="foldable" data-body="body-dup">6 · Duplicate reads<span class="conf" id="conf-dup"></span></h2>
  <div class="sec-body" id="body-dup">
    <div id="dup-wrap"></div>
  </div>
</section>

<section>
  <details id="warnings-details">
    <summary id="warnings-summary"></summary>
    <div id="warnings-wrap"></div>
  </details>
  <details>
    <summary>Confidence notes — what is measured vs inferred</summary>
    <dl class="conf-notes" id="conf-notes"></dl>
  </details>
</section>

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
    expanded ? "show top " + limit + " only" : "show all " + total + " " + noun);
  btn.addEventListener("click", onClick);
  return btn;
}

/* header */
(function renderMeta() {
  const m = S.meta;
  const parts = [
    "generated " + m.generated_at,
    "input " + m.input_root,
    m.since ? "since " + m.since : null,
    m.project_filter ? "project ~ " + m.project_filter : null,
    m.redact_paths ? "paths redacted" : null,
    "v" + m.version,
  ].filter(Boolean);
  document.getElementById("meta-line").textContent = parts.join(" · ");
  document.getElementById("conf-tools").textContent = "bytes: measured";
  document.getElementById("conf-daily").textContent = "tokens: measured";
  document.getElementById("conf-advice").textContent = "rules over measured metrics";
  document.getElementById("conf-chains").textContent = "attributionSkill · agentId: measured";
  document.getElementById("conf-projects").textContent = "measured";
  document.getElementById("conf-sessions").textContent = "cache eff: measured";
  document.getElementById("conf-dup").textContent = "inferred (Read only)";
  const notes = document.getElementById("conf-notes");
  Object.entries(m.confidence).forEach(([key, note]) => {
    notes.appendChild(el("dt", null, key));
    notes.appendChild(el("dd", null, note));
  });
})();

/* totals cards — volume vs waste-signal groups */
(function renderCards() {
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
      node.title = "jump to the matching section";
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
    card("total tokens", fmt(t.total_tokens),
      t.sessions + " sessions · " + fmt(t.requests + t.subagent_requests) + " req"),
    card("new tokens spent", fmt(newTokens), "input + output + cache write"),
    card("cache reuse", fmt(t.cache_read_tokens), cacheShare + " of total"),
    card("tool activity", fmt(t.tool_calls), "calls"),
    peakDay ? card("peak day", peakDay.slice(5), fmt(peakTotal) + " tokens") : null,
    topModel ? card("model mix", topModel[0].replace(/^claude-/, ""),
      Math.round((topModel[1] / grand) * 100) + "%"
      + (models.length > 1 ? " · +" + (models.length - 1) + " more" : "")) : null,
  ];
  const waste = [
    card("tool pollution", fmtBytes(t.tool_result_bytes), "re-entered context", false,
      () => jumpTo("body-tools")),
    card("waste signals",
      fmt(t.wasted_reads) + " · " + t.compactions + " · " + t.errors,
      "re-reads · compactions · errors",
      t.wasted_reads + t.compactions + t.errors > 0,
      () => jumpTo("body-dup")),
  ];
  if (S.meta.parse_warnings_total > 0) {
    waste.push(card("parse warnings", S.meta.parse_warnings_total, "see details below", true,
      () => {
        const details = document.getElementById("warnings-details");
        details.open = true;
        details.scrollIntoView({ behavior: "smooth", block: "start" });
      }));
  }

  const wrap = document.getElementById("totals-cards");
  wrap.appendChild(group("volume", volume));
  wrap.appendChild(group("waste signals", waste));
})();

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
  if (!pool.length) { wrap.appendChild(el("div", "empty", "no tools match this filter")); return; }
  const all = [...pool].sort((a, b) => b[metric] - a[metric]);
  const rows = toolsExpanded ? all : all.slice(0, TOOL_LIMIT);
  const max = Math.max(...all.map(r => r[metric]), 1);
  const grid = el("div", "bar-grid");
  rows.forEach(row => {
    const name = el("div", "mono tool-name", row.name);
    name.title = row.name + " — max single result " + fmtBytes(row.max_result_bytes)
      + (row.errors ? " · " + row.errors + " errors" : "");
    grid.appendChild(name);
    const toolLvl = flagLevel("tool", row.name);
    if (toolLvl) {
      name.appendChild(el("span", "flag-chip" + (toolLvl === "critical" ? " critical" : ""), "advice"));
      name.title += " · flagged by advice below";
    }
    grid.appendChild(el("div", "num muted", fmt(row.calls) + "×"));
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill" + flagClass(toolLvl));
    fill.style.width = Math.max(0.5, (row[metric] / max) * 100) + "%";
    track.appendChild(fill);
    grid.appendChild(track);
    grid.appendChild(el("div", "num",
      metric === "result_bytes" ? fmtBytes(row.result_bytes) : fmt(row.calls) + " calls"));
  });
  wrap.appendChild(grid);
  const toggle = showToggle(all.length, TOOL_LIMIT, toolsExpanded, "tools", () => {
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
      ? "no advice at this level/filter — lower the level or re-enable a rule above"
      : "no patterns crossed a threshold — see the rule catalog below"));
    return;
  }
  items.forEach(item => {
    const level = lvlOf(item);
    const div = el("div", "advice-item level-" + level + (item.target ? " linked" : ""));
    div.appendChild(el("span", "level-tag " + level, level));
    div.appendChild(el("span", "rule", item.rule));
    div.appendChild(document.createTextNode(item.message));
    div.appendChild(el("span", "conf-tag", item.confidence));
    const rule = adviceRules[item.rule];
    if (rule) div.appendChild(el("div", "rule-def", rule.definition));
    if (item.target) {
      div.title = "jump to the flagged " + item.target.kind;
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
function refreshAdviceViews() {
  recomputeTargets();
  renderAdviceControls();
  renderAdvice();
  renderToolBars(currentMetric); // graph flags follow the active rules/level
  renderSkillChains();
}
function renderAdviceControls() {
  const wrap = document.getElementById("advice-controls");
  wrap.textContent = "";
  if (!advice.length) return;
  const present = [...new Set(advice.map(a => a.rule))];
  wrap.appendChild(el("span", "muted", "show:"));
  present.forEach(ruleId => {
    const rule = adviceRules[ruleId];
    const btn = el("button", "rule-toggle" + (hiddenRules.has(ruleId) ? " off" : ""),
      rule ? rule.title : ruleId);
    btn.addEventListener("click", () => {
      if (hiddenRules.has(ruleId)) hiddenRules.delete(ruleId); else hiddenRules.add(ruleId);
      refreshAdviceViews();
    });
    wrap.appendChild(btn);
  });
  wrap.appendChild(el("span", "muted", " level ≥"));
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
      n ? n + " firing" : "dormant"));
    if (rule.level) div.appendChild(el("span", "level-tag " + rule.level, rule.level));
    div.appendChild(el("span", "cat-title", rule.title));
    div.appendChild(el("div", "rule-def", rule.definition));
    wrap.appendChild(div);
  });
}
function renderSkillWhatif() {
  const host = document.getElementById("skill-whatif");
  if (!host) return;
  host.textContent = "";
  if (!S.by_skill_chain || !S.by_skill_chain.length || !adviceTh.skill_min_turns) {
    host.appendChild(el("div", "empty", "no skill data to explore")); return;
  }
  const inputs = el("div", "wi-inputs");
  const turnsLabel = el("label", null, "min turns");
  const turnsInput = el("input"); turnsInput.type = "number"; turnsInput.min = "1";
  turnsInput.value = adviceTh.skill_min_turns; turnsLabel.appendChild(turnsInput);
  const spendLabel = el("label", null, "warn ≥");
  const spendInput = el("input"); spendInput.type = "number"; spendInput.min = "0";
  spendInput.step = "5000"; spendInput.value = adviceTh.skill_new_spend_per_turn;
  spendLabel.appendChild(spendInput);
  const critLabel = el("label", null, "critical ≥");
  const critInput = el("input"); critInput.type = "number"; critInput.min = "0";
  critInput.step = "5000"; critInput.value = adviceTh.skill_critical_new_spend_per_turn;
  critLabel.appendChild(critInput);
  const reset = el("button", null, "reset");
  inputs.appendChild(turnsLabel); inputs.appendChild(spendLabel);
  inputs.appendChild(critLabel); inputs.appendChild(reset);
  host.appendChild(inputs);
  const list = el("div"); host.appendChild(list);
  const exportWrap = el("div", "wi-export");
  exportWrap.appendChild(el("div", "muted",
    "Save to ~/.config/claudeye/config.json (or pass --config PATH) to persist:"));
  const snippet = el("pre", "wi-config");
  const copyBtn = el("button", "wi-copy", "copy");
  copyBtn.addEventListener("click", () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(snippet.textContent).then(() => {
        copyBtn.textContent = "copied";
        setTimeout(() => { copyBtn.textContent = "copy"; }, 1200);
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
      if (t < Tturns) { status = "blocked · " + t + " turns < " + Tturns; cls = "blocked"; }
      else if (signal && newSpend >= Tcrit) { status = "would fire · critical"; cls = "critical"; }
      else if (signal) { status = "would fire · warn"; cls = "fires"; }
      else { status = "below thresholds"; cls = "below"; }
      return { name: r.skill, newSpend, t, status, cls };
    }).sort((a, b) => b.newSpend - a.newSpend).slice(0, 15);
    rows.forEach(r => {
      const row = el("div", "wi-row");
      const name = el("div", "mono tool-name", r.name); name.title = r.name;
      row.appendChild(name);
      row.appendChild(el("div", "num", fmt(r.newSpend) + " /turn"));
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
  if (!S.by_day.length) { wrap.appendChild(el("div", "empty", "no dated usage found")); return; }
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
  const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  function showDayTip(day) {
    chartTip.textContent = "";
    const rows = (byDay[day] || []).slice()
      .sort((a, b) => models.indexOf(a.model) - models.indexOf(b.model));
    const weekday = WEEKDAYS[new Date(day + "T00:00:00Z").getUTCDay()];
    chartTip.appendChild(el("div", "tip-title",
      day + " (" + weekday + ") — " + fmt(dayTotal(day)) + " tokens"));
    rows.forEach(r => {
      const line = el("div", "tip-row");
      const sw = el("span", "sw");
      sw.style.background = color(r.model);
      line.appendChild(sw);
      line.appendChild(document.createTextNode(
        r.model.replace(/^claude-/, "") + " · new " + fmt(newSpend(r))
        + " · reuse " + fmt(r.cache_read_tokens)));
      chartTip.appendChild(line);
    });
    const sum = rows.reduce((acc, r) => ({
      i: acc.i + r.input_tokens, o: acc.o + r.output_tokens,
      cw: acc.cw + r.cache_creation_tokens, cr: acc.cr + r.cache_read_tokens,
    }), { i: 0, o: 0, cw: 0, cr: 0 });
    chartTip.appendChild(el("div", "tip-total",
      "input " + fmt(sum.i) + " · output " + fmt(sum.o)
      + " · cache write " + fmt(sum.cw) + " · cache read " + fmt(sum.cr)));
    chartTip.style.display = "block";
  }
  const byDay = {};
  S.by_day.forEach(r => { (byDay[r.date] = byDay[r.date] || []).push(r); });
  const dayTotal = d => (byDay[d] || []).reduce((acc, r) =>
    acc + r.input_tokens + r.output_tokens + r.cache_read_tokens + r.cache_creation_tokens, 0);
  const maxTotal = Math.max(...days.map(dayTotal), 1);

  const barW = 34, gap = 14, left = 58, bottom = 34, top = 12, H = 240;
  const W = left + days.length * (barW + gap) + 16;
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("width", W); svg.setAttribute("height", H + top + bottom);
  const scale = v => (v / maxTotal) * H;

  [0, 0.5, 1].forEach(f => {
    const y = top + H - scale(maxTotal * f);
    const line = document.createElementNS(svgNS, "line");
    line.setAttribute("x1", left - 6); line.setAttribute("x2", W - 8);
    line.setAttribute("y1", y); line.setAttribute("y2", y);
    line.setAttribute("stroke", "#2a2f3a"); line.setAttribute("stroke-width", "1");
    svg.appendChild(line);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("x", left - 10); label.setAttribute("y", y + 4);
    label.setAttribute("text-anchor", "end");
    label.setAttribute("fill", "#9aa3b2"); label.setAttribute("font-size", "10");
    label.textContent = fmt(maxTotal * f);
    svg.appendChild(label);
  });

  days.forEach((day, i) => {
    let y = top + H;
    const x = left + i * (barW + gap);
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
    label.setAttribute("fill", isWeekend ? "#7aa2f7" : "#9aa3b2");
    label.setAttribute("font-size", "10");
    label.textContent = day.slice(5);
    if (isWeekend) {
      const tip = document.createElementNS(svgNS, "title");
      tip.textContent = weekday === 0 ? "Sunday" : "Saturday";
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
  const shade = el("span", "muted",
    "solid = new tokens spent (input + output + cache write) · muted = cache reuse · weekend labels tinted");
  legend.appendChild(shade);
  const toggle = showToggle(allDays.length, DAY_LIMIT, daysExpanded, "days", () => {
    daysExpanded = !daysExpanded;
    renderDaily();
  });
  if (toggle) wrap.appendChild(toggle);
}
renderDaily();

/* 3 — skill chains: cumulative-token ranking, click row to unfold the
   chained tool composition graph */
let skillChainsExpanded = false;
let chainMode = "total"; // "total" (누적) | "percall" (회당)
const skillOpen = new Set();
function renderSkillChains() {
  const wrap = document.getElementById("skill-chains");
  wrap.textContent = "";
  if (!S.by_skill_chain || !S.by_skill_chain.length) {
    wrap.appendChild(el("div", "empty", "no skill-attributed turns found"));
    return;
  }
  const controls = el("div", "controls");
  controls.appendChild(document.createTextNode("tool composition"));
  [["total", "cumulative"], ["percall", "per call"]].forEach(([key, label]) => {
    const btn = el("button", chainMode === key ? "active" : null, label);
    btn.addEventListener("click", () => { chainMode = key; renderSkillChains(); });
    controls.appendChild(btn);
  });
  controls.appendChild(el("span", "muted", chainMode === "total"
    ? " — totals; bar scale shared across all skills"
    : " — skill bars = tokens per turn, tool bars = result size per call; counts shown as the basis"));
  wrap.appendChild(controls);
  const title = el("div", "muted",
    (chainMode === "total"
      ? "cumulative new tokens per skill"
      : "new tokens per turn per skill")
    + " — ranked by new tokens (input + output + cache write); cache read is "
    + "ambient call-time context, shown separately. Click a row for its tools.");
  title.style.margin = "0 0 6px";
  wrap.appendChild(title);
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
    const box = el("div", "skill-row");
    const head = el("div", "skill-head");
    head.appendChild(el("span", "caret", skillOpen.has(row.skill) ? "▾" : "▸"));
    const skillLvl = flagLevel("skill", row.skill);
    const name = el("span", "mono skill-name", row.skill);
    name.title = row.skill + " — "
      + Math.round((row.new_tokens / grandSkillTokens) * 100)
      + "% of skill new tokens"
      + (skillLvl ? " · flagged by advice (" + skillLvl + ")" : "");
    if (skillLvl) {
      name.appendChild(el("span", "flag-chip" + (skillLvl === "critical" ? " critical" : ""),
        skillLvl === "critical" ? "critical" : "needs review"));
    }
    head.appendChild(name);
    head.appendChild(el("span", "num muted", fmt(row.requests) + " turns"));
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill" + flagClass(skillLvl));
    fill.style.width = Math.max(0.5, (skillValue(row) / maxSkill) * 100) + "%";
    track.appendChild(fill);
    head.appendChild(track);
    const headValue = el("span", "num", chainMode === "total"
      ? fmt(row.new_tokens)
      : fmt(skillValue(row)) + " /turn");
    headValue.title = "new tokens (input + output + cache write); cache read "
      + fmt(row.cache_read_tokens) + " ambient, excluded from ranking"
      + (chainMode === "total"
          ? " · over " + row.requests + " turns"
          : " · average over " + row.requests + " turns, total new " + fmt(row.new_tokens));
    head.appendChild(headValue);
    box.appendChild(head);

    const detail = el("div", "skill-detail");
    if (!skillOpen.has(row.skill)) detail.classList.add("folded");
    detail.appendChild(el("div", "muted",
      "new " + fmt(row.new_tokens) + " (input " + fmt(row.input_tokens)
      + " · output " + fmt(row.output_tokens)
      + " · cache write " + fmt(row.cache_creation_tokens) + ")"
      + " · cache read " + fmt(row.cache_read_tokens) + " (ambient)"
      + " — " + fmt(row.tool_calls) + " tool calls, "
      + fmtBytes(row.tool_result_bytes) + " results"));
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
          ? tool.calls + " calls in total"
          : "average over " + tool.calls + " calls";
        grid.appendChild(calls);
        const tTrack = el("div", "bar-track");
        const tFill = el("div", "bar-fill");
        tFill.style.width = Math.max(0.5, (value / scale) * 100) + "%";
        tTrack.appendChild(tFill);
        grid.appendChild(tTrack);
        const valueCell = el("div", "num", chainMode === "total"
          ? fmtBytes(tool.result_bytes)
          : fmtBytes(perCall) + " /call");
        valueCell.title = chainMode === "total"
          ? "total of " + tool.calls + " calls"
          : fmtBytes(tool.result_bytes) + " total over " + tool.calls + " calls";
        grid.appendChild(valueCell);
      });
      detail.appendChild(grid);
      if (row.tools.some(t => t.name.startsWith("Skill:"))) {
        detail.appendChild(el("div", "muted",
          "nested Skill dispatches above are counted under their own skill rows"));
      }
    } else {
      detail.appendChild(el("div", "empty", "no tool calls on this skill's turns"));
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
    "skills", () => { skillChainsExpanded = !skillChainsExpanded; renderSkillChains(); });
  if (toggle) wrap.appendChild(toggle);
}
renderSkillChains();

/* 3b — subagent tokens by dispatch type */
(function renderAgentTypes() {
  const wrap = document.getElementById("agent-types");
  if (!S.by_agent_type || !S.by_agent_type.length) return;
  const title = el("div", "muted",
    "Subagent new tokens by dispatch type (cache read is ambient, excluded)");
  title.style.margin = "16px 0 6px";
  wrap.appendChild(title);
  const table = el("table");
  const head = el("tr");
  [["type", true], ["agents", false], ["req", false], ["new tokens", false]]
    .forEach(([label, text]) => head.appendChild(el("th", text ? "text" : null, label)));
  const thead = el("thead"); thead.appendChild(head); table.appendChild(thead);
  const tbody = el("tbody");
  S.by_agent_type.forEach(row => {
    const tr = el("tr");
    tr.appendChild(el("td", "text mono", row.type));
    tr.appendChild(el("td", null, row.agents));
    tr.appendChild(el("td", null, row.requests));
    const tokens = el("td", null, fmt(row.new_tokens));
    tokens.title = "new tokens = input " + fmt(row.input_tokens)
      + " · output " + fmt(row.output_tokens)
      + " · cache write " + fmt(row.cache_creation_tokens)
      + " — cache read " + fmt(row.cache_read_tokens) + " ambient, excluded";
    tr.appendChild(tokens);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
})();

/* 4 — projects rollup */
(function renderProjects() {
  const wrap = document.getElementById("projects-wrap");
  if (!S.by_project || !S.by_project.length) {
    wrap.appendChild(el("div", "empty", "no projects found")); return;
  }
  const table = el("table");
  const head = el("tr");
  [["project", true], ["sessions", false], ["req", false], ["tokens", false],
   ["cache eff", false], ["tools", false], ["result size", false],
   ["dup rd", false], ["cmp", false], ["err", false]]
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
    tokens.title = "input " + fmt(row.input_tokens) + " · output " + fmt(row.output_tokens)
      + " · cache read " + fmt(row.cache_read_tokens)
      + " · cache creation " + fmt(row.cache_creation_tokens);
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
})();

/* 5 — sessions table */
(function renderSessions() {
  const wrap = document.getElementById("sessions-wrap");
  if (!S.sessions.length) { wrap.appendChild(el("div", "empty", "no sessions found")); return; }
  const COLS = [
    { key: "project", label: "project", text: true },
    { key: "session_id", label: "session", text: true, render: (row, td) => {
        td.classList.add("mono"); td.title = row.session_id;
        td.textContent = row.session_id.slice(0, 8);
        if (row.subagents) {
          const chip = el("span", "muted", " +" + row.subagents + " sub");
          td.appendChild(chip);
        }
      } },
    { key: "first_ts", label: "start", text: true, render: (row, td) => {
        td.textContent = row.first_ts ? row.first_ts.slice(0, 16).replace("T", " ") : "–";
      } },
    { key: "duration_min", label: "min" },
    { key: "requests", label: "req", render: (row, td) => {
        td.textContent = row.requests + (row.subagent_requests ? "+" + row.subagent_requests : "");
      } },
    { key: "total_tokens", label: "tokens", render: (row, td) => {
        td.textContent = fmt(row.total_tokens); td.title =
          "input " + fmt(row.input_tokens) + " · output " + fmt(row.output_tokens)
          + " · cache read " + fmt(row.cache_read_tokens)
          + " · cache creation " + fmt(row.cache_creation_tokens)
          + (row.subagent_total_tokens ? " · subagents " + fmt(row.subagent_total_tokens) : "");
      } },
    { key: "cache_efficiency", label: "cache eff", render: (row, td) => {
        if (row.cache_efficiency === null) { td.textContent = "–"; return; }
        const pct = Math.round(row.cache_efficiency * 100);
        td.textContent = pct + "%";
        td.className = pct < 50 ? "eff-bad" : pct < 80 ? "eff-warn" : "eff-ok";
      } },
    { key: "tool_calls", label: "tools", render: (row, td) => { td.textContent = fmt(row.tool_calls); } },
    { key: "wasted_reads", label: "dup rd" },
    { key: "compactions", label: "cmp", render: (row, td) => {
        td.textContent = row.compactions || "";
        if (row.compact_pre_tokens && row.compact_pre_tokens.length)
          td.title = "pre-compact tokens: " + row.compact_pre_tokens.map(fmt).join(", ");
      } },
    { key: "errors", label: "err", render: (row, td) => { td.textContent = row.errors || ""; } },
    { key: "flags", label: "flags", text: true, sortValue: row => row.flags.length,
      render: (row, td) => {
        row.flags.forEach(flag => td.appendChild(el("span", "flag " + flag, flag)));
      } },
  ];
  let sortKey = "total_tokens", sortDir = -1, showAll = false;
  const table = el("table");
  const thead = el("thead");
  const groupRow = el("tr", "col-groups");
  [["identity", 4], ["tokens", 3], ["activity", 1], ["waste", 4]]
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
      ? "show top " + SESSION_LIMIT + " only"
      : "show all " + S.sessions.length + " sessions";
    toggleBtn.style.display = S.sessions.length > SESSION_LIMIT ? "" : "none";
  }
  const toggleBtn = el("button", "show-toggle");
  toggleBtn.addEventListener("click", () => { showAll = !showAll; drawBody(); });
  drawBody(); markSorted();
  wrap.appendChild(table);
  wrap.appendChild(toggleBtn);
})();

/* 6 — duplicate reads */
let dupExpanded = false;
function renderDup() {
  const wrap = document.getElementById("dup-wrap");
  wrap.textContent = "";
  if (!S.dup_reads.length) { wrap.appendChild(el("div", "empty",
    "no duplicate reads detected — nothing was Read twice in one context")); return; }
  const table = el("table");
  const head = el("tr");
  [["file", true], ["reads", false], ["wasted", false], ["sessions", false], ["max in one context", false]]
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
  const toggle = showToggle(S.dup_reads.length, DUP_LIMIT, dupExpanded, "files", () => {
    dupExpanded = !dupExpanded;
    renderDup();
  });
  if (toggle) wrap.appendChild(toggle);
}
renderDup();

/* warnings + footer */
(function renderWarnings() {
  const total = S.meta.parse_warnings_total;
  document.getElementById("warnings-summary").textContent =
    "Parse warnings (" + total + (S.parse_warnings.length < total
      ? ", showing first " + S.parse_warnings.length : "") + ")";
  const wrap = document.getElementById("warnings-wrap");
  if (!S.parse_warnings.length) { wrap.appendChild(el("div", "empty", "none")); return; }
  const table = el("table");
  const head = el("tr");
  [["file", true], ["line", false], ["reason", true]].forEach(([label, text]) =>
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
})();
document.getElementById("footer").textContent =
  "claudeye v" + S.meta.version
  + " — local closed-loop analysis; not a billing source (use ccusage for cost).";
</script>
</body>
</html>
"""
