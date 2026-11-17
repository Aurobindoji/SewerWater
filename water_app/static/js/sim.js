// The Simulation tab (user request 17-Nov-2026: "simulation के लिए dedicated tab ... SSA और EPS ... in-depth detail
// visually"): the network of the last design solved again under a load chosen here (sim_run.py) - without designing
// again. SSA: one moment (average / peak / night / an hour / own factor, a population stage, extra loads and fires at
// junctions picked on the map). EPS: 24 / 48 / 72 h with the OHTs' levels, an own draw-off pattern and filling hours.
// The map: junctions coloured by their head, pipes by velocity / flow / head loss; an EPS has a time slider and a
// player; a junction or pipe clicked shows its values (and its curve through the run). The load cases and the 24 h of
// the design itself (js/results.js loadCaseBox / dayBox) are shown here too.
const simLayer = L.layerGroup();
const SIM = { mode: "ssa", info: null, res: null, hour: 0, colour: "p", timer: null, nodeMk: {}, pipeLn: {}, hadDesign: false,
              ni: {}, pi: {}, pattern: null, extra: [], fires: [], on: false };
const SIM_P = [[null, "#9e9e9e"], [17, "#d32f2f"], [21, "#2e7d32"], [30, "#1565c0"], [Infinity, "#6a1b9a"]];
const SIM_V = [[0.3, "#90caf9"], [1, "#43a047"], [2, "#fdd835"], [3, "#fb8c00"], [Infinity, "#d32f2f"]];
const SIM_Q = [[1, "#b3e5fc"], [5, "#4fc3f7"], [20, "#0288d1"], [50, "#01579b"], [Infinity, "#1a237e"]];
const SIM_HL = [[1, "#43a047"], [5, "#fdd835"], [10, "#fb8c00"], [Infinity, "#d32f2f"]];
const SIM_COLOURS = { p: () => tr("दबाव (m)", "head (m)"), v: () => tr("वेग (m/s)", "velocity (m/s)"),
                      q: () => tr("बहाव (L/s)", "flow (L/s)"), hl: () => tr("Head loss (m/km)", "head loss (m/km)") };

const simHourName = h => { const d = Math.floor(h / 24), x = h % 24;
  return (SIM.res && SIM.res.n_hours > 24 ? tr(`दिन ${d + 1}, `, `day ${d + 1}, `) : "") + `${String(x).padStart(2, "0")}:00-${String(x + 1).padStart(2, "0")}:00`; };
function simScale(scale, v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "#9e9e9e";
  for (const [lim, c] of scale) if (lim !== null && v < lim) return c;
  return scale[scale.length - 1][1];
}
function simRh() { return (SIM.info && SIM.info.residual_head_m) || 17; }
function simPScale() { const rh = simRh(); return [[null, "#9e9e9e"], [rh, "#d32f2f"], [rh + 4, "#2e7d32"], [rh + 13, "#1565c0"], [Infinity, "#6a1b9a"]]; }

// ---- the network drawn from the last design (the same geometry as the design's map)
function simGeo() {
  if (!wDesign) return null;
  const geo = {}; (layoutData && layoutData.conduits || []).forEach(c => geo[c.label] = c); withCuts(wDesign, geo);
  const nodes = {}, pipes = {};
  for (const n of wDesign.nodes) nodes[n.label] = n.latlng;
  for (const p of wDesign.pipes) { const c = geo[p.label]; if (c) pipes[p.label] = c.pts; }
  return { nodes, pipes };
}
function simDraw() {
  simLayer.clearLayers(); SIM.nodeMk = {}; SIM.pipeLn = {};
  const g = simGeo(); if (!g) return;
  for (const [lab, pts] of Object.entries(g.pipes))
    SIM.pipeLn[lab] = L.polyline(pts, { color: "#90a4ae", weight: 3, opacity: .9, renderer: netRenderer })
      .on("click", e => { L.DomEvent.stopPropagation(e); simPick("pipe", lab, e.latlng); }).addTo(simLayer);
  for (const [lab, ll] of Object.entries(g.nodes))
    SIM.nodeMk[lab] = L.circleMarker(ll, { radius: 3.5, color: "#263238", weight: 1, fillColor: "#b0bec5", fillOpacity: 1, renderer: netRenderer })
      .on("click", e => { L.DomEvent.stopPropagation(e); simPick("node", lab, e.latlng); }).addTo(simLayer);
  for (const o of wDesign.outlets || [])
    L.marker(o.latlng, { icon: icon("oht", false, { name: o.name, existing: o.existing ? "1" : "0" }) })
      .bindTooltip(esc(o.name)).addTo(simLayer);
  simColour();
}
// the values of the moment shown: SSA its own, EPS the slider's hour
function simVals() {
  const r = SIM.res; if (!r) return null;
  if (r.mode === "ssa") return { P: r.P, Q: r.Q, V: r.V, HL: r.HL };
  const h = SIM.hour; return { P: r.P[h], Q: r.Q[h], V: r.V[h], HL: null };
}
function simColour() {
  const v = simVals(), c = SIM.colour, closed = new Set((SIM.res && SIM.res.closed) || []);
  for (const [lab, ln] of Object.entries(SIM.pipeLn)) {
    const i = SIM.pi[lab];
    if (!v || i === undefined || c === "p") { ln.setStyle({ color: closed.has(lab) ? "#bdbdbd" : "#90a4ae", weight: 2.5, dashArray: closed.has(lab) ? "4 4" : null }); continue; }
    if (closed.has(lab)) { ln.setStyle({ color: "#bdbdbd", weight: 2, dashArray: "4 4" }); continue; }
    const x = c === "v" ? v.V[i] : c === "q" ? Math.abs(v.Q[i]) : v.HL ? v.HL[i] : null;
    const col = simScale(c === "v" ? SIM_V : c === "q" ? SIM_Q : SIM_HL, x);
    ln.setStyle({ color: col, weight: c === "q" ? Math.min(9, 2 + Math.sqrt(Math.abs(x || 0)) * 0.9) : 4, dashArray: null });
  }
  const ps = simPScale();
  for (const [lab, mk] of Object.entries(SIM.nodeMk)) {
    const i = SIM.ni[lab];
    if (!v || i === undefined) { mk.setStyle({ fillColor: "#b0bec5", radius: 3.5 }); continue; }
    mk.setStyle(c === "p" ? { fillColor: simScale(ps, v.P[i]), radius: 4.5 } : { fillColor: "#eceff1", radius: 2.5 });
  }
  simLegend();
}
function simLegend() {
  const box = $("simleg") || document.createElement("div");
  const c = SIM.colour, rh = simRh();
  const items = c === "p" ? [["#d32f2f", `< ${rh}`], ["#2e7d32", `${rh} - ${rh + 4}`], ["#1565c0", `${rh + 4} - ${rh + 13}`], ["#6a1b9a", `> ${rh + 13}`]]
    : c === "v" ? [["#90caf9", tr("< 0.3 (ठहराव)", "< 0.3 (stagnant)")], ["#43a047", "0.3 - 1"], ["#fdd835", "1 - 2"], ["#fb8c00", "2 - 3"], ["#d32f2f", "> 3"]]
    : c === "q" ? [["#b3e5fc", "< 1"], ["#4fc3f7", "1 - 5"], ["#0288d1", "5 - 20"], ["#01579b", "20 - 50"], ["#1a237e", "> 50"]]
    : [["#43a047", "< 1"], ["#fdd835", "1 - 5"], ["#fb8c00", "5 - 10"], ["#d32f2f", "> 10"]];
  box.innerHTML = `<b>${esc(SIM_COLOURS[c]())}</b> ` + items.map(([col, t]) =>
    `<span style="white-space:nowrap;margin-right:8px"><span style="display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:middle;background:${col}"></span> ${esc(t)}</span>`).join("");
  if (SIM.on && $("legend")) $("legend").innerHTML = `<b>Simulation</b>` + (SIM.res ? ` - ${esc(SIM.res.mode === "eps" ? simHourName(SIM.hour) : SIM.res.load)}` : "") +
    `<div>` + items.map(([col, t]) => `<div><span class="k" style="background:${col};height:6px"></span>${esc(t)} ${c === "p" ? "m" : ""}</div>`).join("") + `</div>`;
}

// ---- a chart of n hours (or any series): series [{name, color, values}], a dashed guide line, the slider's hour marked
function simChart(series, lo, hi, unit, guide, mark) {
  const n = Math.max(...series.map(s => s.values.length), 2);
  const W = 330, H = 125, Lm = 34, B = 16, T = 8, R = 6;
  const x = h => Lm + (W - Lm - R) * h / (n - 1), y = v => T + (H - T - B) * (1 - (v - lo) / ((hi - lo) || 1));
  let g = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" style="display:block">`;
  for (const v of [lo, (lo + hi) / 2, hi]) g += `<line x1="${Lm}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${Lm - 3}" y="${y(v) + 3}" font-size="9" text-anchor="end" fill="var(--muted)">${fmt(v, Math.abs(hi - lo) < 3 ? 2 : 0)}</text>`;
  const step = n > 48 ? 12 : 6;
  for (let h = 0; h < n; h += step) g += `<text x="${x(h)}" y="${H - 3}" font-size="9" text-anchor="middle" fill="var(--muted)">${h}</text>`;
  if (guide !== undefined && guide !== null && guide >= lo && guide <= hi) g += `<line x1="${Lm}" x2="${W - R}" y1="${y(guide)}" y2="${y(guide)}" stroke="var(--danger)" stroke-dasharray="3 3"/>`;
  if (mark !== undefined && mark !== null) g += `<line x1="${x(mark)}" x2="${x(mark)}" y1="${T}" y2="${H - B}" stroke="var(--accent)" stroke-width="1.2"/>`;
  for (const s of series) g += `<polyline fill="none" stroke="${s.color}" stroke-width="1.7" points="${s.values.map((v, h) => `${x(h).toFixed(1)},${y(v ?? lo).toFixed(1)}`).join(" ")}"><title>${esc(s.name)}</title></polyline>`;
  return g + `<text x="${Lm}" y="${T + 6}" font-size="9" fill="var(--muted)" dx="3">${esc(unit)}</text></svg>`;
}
const simRange = (vals, pad, floor0) => { const f = vals.filter(v => v !== null && !Number.isNaN(v));
  let lo = Math.min(...f), hi = Math.max(...f); if (!f.length) return [0, 1]; if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
  const d = (hi - lo) * pad; return [floor0 ? Math.max(0, lo - d) : lo - d, hi + d]; };

// ---- a junction / pipe clicked: its values now, its curve through an EPS, and (junction) a load or fire there
function simPick(kind, lab, latlng) {
  const r = SIM.res, el = document.createElement("div");
  let html = `<b>${esc(lab)}</b>`;
  if (kind === "node") {
    const i = SIM.ni[lab];
    if (r && i !== undefined) {
      if (r.mode === "ssa") html += `<br>${tr("दबाव", "head")} <b>${fmt(r.P[i], 2)} m</b>, HGL ${fmt(r.H[i], 2)} m<br>OZ ${esc((r.oz || {})[lab] || "-")}`;
      else {
        const vals = r.P.map(row => row[i]); const [lo, hi] = simRange(vals.concat([simRh()]), 0.1);
        html += `<br>${esc(simHourName(SIM.hour))}: <b>${fmt(vals[SIM.hour], 2)} m</b> (${tr("सबसे कम", "lowest")} ${fmt(Math.min(...vals), 2)}, ${tr("सबसे अधिक", "highest")} ${fmt(Math.max(...vals), 2)})` +
          `<div style="width:300px">${simChart([{ name: lab, color: "#1565c0", values: vals }], lo, hi, "m", simRh(), SIM.hour)}</div>`;
      }
    } else html += `<br><span class="hint">${tr("Simulation चलाकर इसके मान देखें", "run a simulation to see its values")}</span>`;
    html += `<div class="row" style="margin-top:4px"><button type="button" data-a="load">+ ${tr("load यहाँ", "load here")}</button>` +
      (SIM.mode === "ssa" ? `<button type="button" data-a="fire">🔥 ${tr("fire यहाँ", "fire here")}</button>` : "") + `</div>`;
  } else {
    const i = SIM.pi[lab];
    if (r && i !== undefined) {
      if (r.mode === "ssa") html += `<br>${tr("बहाव", "flow")} <b>${fmt(Math.abs(r.Q[i]), 2)} L/s</b>, v ${fmt(r.V[i], 2)} m/s<br>head loss ${fmt(r.HL[i], 2)} m/km`;
      else {
        const q = r.Q.map(row => Math.abs(row[i])), v = r.V.map(row => row[i]);
        const [lo, hi] = simRange(q, 0.1, true);
        html += `<br>${esc(simHourName(SIM.hour))}: <b>${fmt(q[SIM.hour], 2)} L/s</b>, v ${fmt(v[SIM.hour], 2)} m/s (max ${fmt(Math.max(...v), 2)})` +
          `<div style="width:300px">${simChart([{ name: tr("बहाव", "flow"), color: "#0288d1", values: q }], lo, hi, "L/s", null, SIM.hour)}</div>`;
      }
    } else html += `<br><span class="hint">${tr("Simulation चलाकर इसके मान देखें", "run a simulation to see its values")}</span>`;
  }
  el.innerHTML = html;
  el.querySelectorAll("button[data-a]").forEach(b => b.onclick = () => {
    (b.dataset.a === "fire" ? SIM.fires : SIM.extra).push({ node: lab, lps: b.dataset.a === "fire" ? ($("wfirelps").value || 10) : 1 });
    simRows(); map.closePopup();
    $(b.dataset.a === "fire" ? "simfirebox" : "simloadbox").open = true;
  });
  L.popup({ maxWidth: 340 }).setLatLng(latlng).setContent(el).openOn(map);
}
function simGoto(kind, lab) {
  const m = kind === "node" ? SIM.nodeMk[lab] : SIM.pipeLn[lab]; if (!m) return;
  const ll = kind === "node" ? m.getLatLng() : m.getBounds().getCenter();
  map.setView(ll, Math.max(map.getZoom(), 17)); simPick(kind, lab, ll);
}

// ---- the load inputs: extra loads and fires (junction, L/s), the hours, the pattern
function simRows() {
  const row = (list, i, kind) => `<div class="row"><input type="text" value="${esc(list[i].node)}" data-k="${kind}" data-i="${i}" data-f="node" placeholder="junction" style="width:8em" list="simnodes">` +
    `<input type="number" value="${esc(list[i].lps)}" data-k="${kind}" data-i="${i}" data-f="lps" min="0" step="0.5" style="width:5em"> L/s` +
    `<button type="button" data-k="${kind}" data-i="${i}" data-del="1" title="${tr("हटाएँ", "remove")}">✕</button></div>`;
  $("simextra").innerHTML = SIM.extra.map((_, i) => row(SIM.extra, i, "extra")).join("") || `<div class="hint">${tr("कोई नहीं", "none")}</div>`;
  $("simfire").innerHTML = SIM.fires.map((_, i) => row(SIM.fires, i, "fires")).join("") || `<div class="hint">${tr("कोई नहीं", "none")}</div>`;
  for (const el of document.querySelectorAll("#simextra [data-k], #simfire [data-k]")) {
    const list = SIM[el.dataset.k === "extra" ? "extra" : "fires"], i = +el.dataset.i;
    if (el.dataset.del) el.onclick = () => { list.splice(i, 1); simRows(); };
    else el.oninput = () => { list[i][el.dataset.f] = el.value; };
  }
}
function simHourOptions() {
  const pat = SIM.pattern || []; $("simhour").innerHTML = pat.map((f, h) =>
    `<option value="${h}"${h === 19 ? " selected" : ""}>${String(h).padStart(2, "0")}:00 (x ${fmt(f, 2)})</option>`).join("");
}
function simPatEditor() {
  const pat = SIM.pattern || [];
  $("simpat").innerHTML = `<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:3px">` + pat.map((f, h) =>
    `<label style="min-width:0;font-size:11px" class="hint">${h}-${h + 1}<input type="number" value="${f}" min="0" max="10" step="0.05" data-h="${h}" style="width:100%"></label>`).join("") +
    `</div><div id="simpatchart"></div>`;
  for (const el of $("simpat").querySelectorAll("input[data-h]"))
    el.oninput = () => { const v = parseFloat(el.value); if (!Number.isNaN(v)) { SIM.pattern[+el.dataset.h] = v; simPatShow(); simHourOptions(); } };
  simPatShow();
}
function simPatShow() {
  const pat = SIM.pattern || [], s = pat.reduce((a, b) => a + b, 0);
  $("simpatsum").innerHTML = `${tr("जोड़", "sum")} ${fmt(s, 2)}` + (Math.abs(s - 24) > 0.05 ? ` <b style="color:var(--danger)">(${tr("24 नहीं: दिन की माँग बदलेगी", "not 24: the day's demand changes")})</b>` : " ✔");
  $("simpatchart").innerHTML = simChart([{ name: "pattern", color: "#6a1b9a", values: pat }], 0, Math.max(3, ...pat), tr("x औसत", "x average"), 1);
}
function simPatChanged() {
  const d = SIM.info && SIM.info.pattern; if (!d || !SIM.pattern) return false;
  return SIM.pattern.some((v, h) => Math.abs(v - d[h]) > 1e-9);
}

// ---- what the last design allows; the tab shown / left
async function simLoadInfo() {
  const nm = $("pname").value;
  const r = nm ? await api("/api/water_sim_info?name=" + encodeURIComponent(nm)).catch(() => null) : null;
  SIM.info = r && r.ok ? r : null;
  $("simrun").disabled = !SIM.info;
  if (!SIM.info) { $("siminfo").textContent = (r && r.log) || tr("पहले Design चलाएँ - simulation उसी network पर चलती है।", "Run the design first - the simulation runs on its network."); return; }
  $("siminfo").textContent = tr(`आख़िरी Design (${r.made || "-"}) का network - ${r.tanks.length} टंकियाँ; pipe sizes, staging और PRV वही, बिना दोबारा design किए।`,
                                `The network of the last design (${r.made || "-"}) - ${r.tanks.length} tanks; its pipe sizes, stagings and PRVs, without designing again.`);
  for (const o of $("simstage").options) o.disabled = o.value !== "ult" && !(r.stages || {})[o.value];
  if ($("simstage").selectedOptions[0].disabled) $("simstage").value = "ult";
  if (!SIM.pattern || SIM.pattern.length !== 24) SIM.pattern = r.pattern.slice();
  $("siminflow").placeholder = (r.windows || []).map(w => `${w[0]}-${w[1]}`).join(", ");
  simHourOptions(); simPatEditor(); simRows();
  const dl = $("simnodes") || document.body.appendChild(Object.assign(document.createElement("datalist"), { id: "simnodes" }));
  dl.innerHTML = (wDesign ? wDesign.nodes : []).slice(0, 20000).map(n => `<option value="${esc(n.label)}">`).join("");
}
function simOnTab(on) {
  if (on === SIM.on) return;
  SIM.on = on;
  const seg = $("viewseg");
  if (on) {
    SIM.hadDesign = map.hasLayer(designLayer); if (SIM.hadDesign) map.removeLayer(designLayer);
    simLayer.addTo(map); if (!Object.keys(SIM.nodeMk).length) simDraw();
    if (seg) seg.style.visibility = "hidden";                 // Layout / Zones / Design: not on this tab
    simLegend(); simLoadInfo();
  } else {
    simStop(); map.removeLayer(simLayer); map.closePopup();
    if (seg) seg.style.visibility = "";
    if (SIM.hadDesign) designLayer.addTo(map);
    if ($("legend") && typeof WLEG !== "undefined") $("legend").innerHTML = WLEG[curView] || "";
  }
}
// the design ran (or was cleared): its own load cases / 24 h here, the tab's run out of date
function simAfterDesign(r) {
  $("simdesign").innerHTML = r ? loadCaseBox(r) + dayBox(r.day) : "";
  SIM.res = null; SIM.ni = {}; SIM.pi = {}; simStop(); $("simres").innerHTML = ""; $("simstatus").textContent = "";
  simLayer.clearLayers(); SIM.nodeMk = {}; SIM.pipeLn = {};
  if (SIM.on) { simDraw(); simLoadInfo(); }
}

// ---- run
function simReq() {
  const num = (list, what) => list.filter(x => String(x.node || "").trim()).map(x => ({ node: String(x.node).trim(), lps: x.lps }));
  const q = { name: $("pname").value, mode: SIM.mode, stage: $("simstage").value, extra: num(SIM.extra) };
  if (simPatChanged()) q.pattern = SIM.pattern;
  if (SIM.mode === "ssa") Object.assign(q, { base: $("simbase").value, hour: $("simhour").value, factor: $("simfactor").value,
                                             fires: num(SIM.fires), min_m: $("simfiremin").value });
  else Object.assign(q, { hours: $("simhours").value, inflow: $("siminflow").value.trim() });
  return q;
}
async function simRun() {
  if (!SIM.info) await simLoadInfo();
  if (!SIM.info) return;
  if (!Object.keys(SIM.nodeMk).length) simDraw();
  $("simstatus").className = "status"; $("simstatus").textContent = tr("चल रही है …", "running …");
  const r = await withLoading(tr("Simulation चल रही है …", "Running the simulation …"), () => api("/api/water_sim", simReq()));
  if (!r.ok) { $("simstatus").className = "status err"; $("simstatus").textContent = r.log || "error"; return; }
  SIM.res = r; SIM.hour = 0; SIM.ni = {}; SIM.pi = {};
  r.nodes.forEach((n, i) => SIM.ni[n] = i); r.pipes.forEach((p, i) => SIM.pi[p] = i);
  if (r.mode === "eps" && SIM.colour === "hl") SIM.colour = "p";
  $("simstatus").className = "status ok";
  $("simstatus").textContent = tr(`हो गई (${fmt(r.seconds, 1)} s)`, `done (${fmt(r.seconds, 1)} s)`);
  simShow(); simColour();
}
function simStop() { if (SIM.timer) { clearInterval(SIM.timer); SIM.timer = null; } const b = $("simplay"); if (b) b.textContent = "▶"; }
function simSetHour(h) {
  const r = SIM.res; if (!r || r.mode !== "eps") return;
  SIM.hour = Math.max(0, Math.min(r.n_hours - 1, h));
  $("simslider").value = SIM.hour; simColour(); simHourBox(); simEpsCharts();
}

// ---- the results
const simCard = (k, v, bad) => `<div style="flex:1;min-width:92px;border:1px solid var(--line);border-radius:6px;padding:4px 6px">` +
  `<div class="hint" style="margin:0">${esc(k)}</div><div style="font-weight:600${bad ? ";color:var(--danger)" : ""}">${v}</div></div>`;
function simWorst(w, eps) {
  const li = (kind, list, unit) => list.map(([lab, v]) => `<a href="#" data-k="${kind}" data-l="${esc(lab)}">${esc(lab)}</a> ${fmt(v, 2)} ${unit}`).join("<br>");
  return `<details open><summary class="hint" style="cursor:pointer;font-weight:600">${tr("कमज़ोर जगहें (click = नक्शे पर)", "weak spots (click = on the map)")}</summary>` +
    `<div style="display:flex;gap:8px;font-size:12px"><div style="flex:1"><b>${eps ? tr("सबसे कम दबाव (रन में)", "lowest head (in the run)") : tr("सबसे कम दबाव", "lowest head")}</b><br>${li("node", w.low, "m")}</div>` +
    `<div style="flex:1"><b>${tr("सबसे अधिक दबाव", "highest head")}</b><br>${li("node", w.high, "m")}</div>` +
    `<div style="flex:1"><b>${tr("सबसे तेज़ pipes", "fastest pipes")}</b><br>${li("pipe", w.fast, "m/s")}</div></div></details>`;
}
function simColourSeg(eps) {
  const keys = eps ? ["p", "v", "q"] : ["p", "v", "q", "hl"];
  return `<div class="seg" id="simcol">${keys.map(k => `<button data-c="${k}" class="${k === SIM.colour ? "on" : ""}">${esc(SIM_COLOURS[k]())}</button>`).join("")}</div><div id="simleg" class="hint"></div>`;
}
function simShow() {
  const r = SIM.res, s = r.summary || {}, rh = simRh(), info = SIM.info || {};
  let h = "";
  if (r.mode === "ssa") {
    h += `<div class="box"><b>SSA</b>: ${esc(r.load)}, ${esc(r.stage)} - ${tr("माँग", "demand")} ${fmt(r.demand_lps, 1)} L/s` +
      (r.extra_lps ? ` (${tr("अतिरिक्त", "extra")} ${fmt(r.extra_lps, 1)})` : "") +
      `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">` +
      simCard(tr("सबसे कम दबाव", "lowest head"), `${fmt(s.min_p, 2)} m <span class="hint">${esc(s.min_at || "")}</span>`, s.min_p < rh) +
      simCard(tr("सबसे अधिक दबाव", "highest head"), `${fmt(s.max_p, 2)} m <span class="hint">${esc(s.max_at || "")}</span>`, info.max_pressure_m && s.max_p > info.max_pressure_m) +
      simCard(tr(`${rh} m से कम`, `below ${rh} m`), `${s.low_n} junctions`, s.low_n > 0) +
      simCard(tr("सबसे तेज़", "fastest"), `${fmt(s.v_max, 2)} m/s`, s.v_max > (info.max_velocity_mps || 3)) + `</div>`;
    if (r.fires.length) h += `<table class="wz" style="margin-top:4px"><tr><th>fire junction</th><th>L/s</th><th>${tr("दबाव", "head")} m</th><th>peak m</th></tr>` +
      r.fires.map(f => `<tr><td><a href="#" data-k="node" data-l="${esc(f.node)}">${esc(f.node)}</a></td><td>${fmt(f.lps, 1)}</td><td>${f.ok === false ? `<b style="color:var(--danger)">${fmt(f.p, 2)}</b>` : fmt(f.p, 2)}</td><td>${fmt(f.p_peak, 2)}</td></tr>`).join("") + `</table>`;
    h += simColourSeg(false) + simWorst(r.worst, false) +
      `<div class="hint">${tr("टंकियाँ design के head पर (सबसे निचला जल स्तर) - दबाव का सबसे कमज़ोर हाल; EPS में स्तर घंटे के साथ बदलता है।", "Tanks at the design head (their lowest level) - the weakest case for the head; in an EPS the level changes hour by hour.")}</div></div>`;
  } else {
    const n = r.n_hours;
    h += `<div class="box"><b>EPS</b>: ${n} ${tr("घंटे", "hours")}, ${esc(r.stage)}` + (r.extra_lps ? `, ${tr("अतिरिक्त", "extra")} ${fmt(r.extra_lps, 1)} L/s` : "") +
      (r.note ? `<div class="warn">${esc(r.note)}</div>` : "") +
      `<div class="row" style="margin-top:6px"><button type="button" id="simplay" title="${tr("घंटे-दर-घंटे चलाएँ", "play hour by hour")}">▶</button>` +
      `<input type="range" id="simslider" min="0" max="${n - 1}" value="${SIM.hour}" style="flex:1"><span id="simhourlbl" style="min-width:9em;text-align:right"></span></div>` +
      `<div id="simhourbox"></div>` + simColourSeg(true) + `<div id="simcharts"></div>` + simTankTable(r) + simWorst(r.worst, true) +
      `<div class="hint">${tr("हर घंटे की माँग = औसत x pattern; OHT भरने के घंटों में भरती, outlet के बहाव से खाली; टंकी का head उसके स्तर से (design का सबसे निचला स्तर + पानी)।", "Each hour's demand = average x the pattern; an OHT fills in its filling hours and empties by its outlet; its head follows its level (the design's lowest level + the water).")}</div></div>`;
  }
  $("simres").innerHTML = h;
  for (const a of $("simres").querySelectorAll("a[data-k]")) a.onclick = e => { e.preventDefault(); simGoto(a.dataset.k, a.dataset.l); };
  for (const b of $("simres").querySelectorAll("#simcol button")) b.onclick = () => { SIM.colour = b.dataset.c;
    $("simres").querySelectorAll("#simcol button").forEach(x => x.classList.toggle("on", x === b)); simColour(); };
  if (r.mode === "eps") {
    $("simslider").oninput = () => simSetHour(+$("simslider").value);
    $("simplay").onclick = () => {
      if (SIM.timer) return simStop();
      $("simplay").textContent = "⏸";
      SIM.timer = setInterval(() => { if (SIM.hour >= r.n_hours - 1) { simStop(); return; } simSetHour(SIM.hour + 1); }, 700);
    };
    simHourBox(); simEpsCharts();
  }
  simLegend();
}
function simHourBox() {
  const r = SIM.res, row = r.hours[SIM.hour], rh = simRh();
  $("simhourlbl").textContent = simHourName(SIM.hour);
  $("simhourbox").innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:4px;margin:4px 0">` +
    simCard(tr("माँग", "demand"), `${fmt(row.demand_lps, 1)} L/s <span class="hint">x ${fmt(row.factor, 2)}</span>`) +
    simCard(tr("सबसे कम दबाव", "lowest head"), `${fmt(row.min_p, 2)} m <span class="hint">${esc(row.min_at || "")}</span>`, row.min_p < rh) +
    simCard(tr("सबसे अधिक दबाव", "highest head"), `${fmt(row.max_p, 2)} m`) +
    simCard(tr("सबसे तेज़", "fastest"), `${fmt(row.v_max, 2)} m/s`) + `</div>` +
    `<div style="font-size:12px">` + Object.entries(row.tanks).map(([n, t]) =>
      `<span style="white-space:nowrap;margin-right:10px">${esc(n)}: <b>${fmt(t.full_pct, 0)} %</b> <span class="hint">(+${fmt(t.in_kl)} / -${fmt(t.out_kl)} KL${t.short_kl ? `, <b style="color:var(--danger)">${tr("कमी", "short")} ${fmt(t.short_kl)}</b>` : ""})</span></span>`).join("") + `</div>`;
}
function simEpsCharts() {
  const r = SIM.res, names = Object.keys(r.tanks), rh = simRh();
  const lvl = names.map((n, i) => ({ name: n, color: DAY_COLORS[i % DAY_COLORS.length], values: r.hours.map(x => x.tanks[n].full_pct) }));
  const pmin = r.hours.map(x => x.min_p), pmax = r.hours.map(x => x.max_p), dem = r.hours.map(x => x.demand_lps);
  const [plo, phi] = simRange(pmin.concat(pmax, [rh]), 0.05);
  const [dlo, dhi] = simRange(dem, 0.1, true);
  $("simcharts").innerHTML =
    `<div class="hint" style="margin-bottom:0">${tr("OHT में पानी (उपयोग योग्य का %)", "water in the OHTs (% of the usable)")} - ` +
    names.map((n, i) => `<span style="color:${DAY_COLORS[i % DAY_COLORS.length]}">■</span> ${esc(n)}`).join(" ") + `</div>` +
    simChart(lvl, 0, 100, "%", null, SIM.hour) +
    `<div class="hint" style="margin-bottom:0">${tr(`Network का सबसे कम / अधिक दबाव (m); लाल = ${rh} m`, `the network's lowest / highest head (m); red = ${rh} m`)}</div>` +
    simChart([{ name: tr("सबसे कम", "lowest"), color: "#c62828", values: pmin }, { name: tr("सबसे अधिक", "highest"), color: "#1565c0", values: pmax }], plo, phi, "m", rh, SIM.hour) +
    `<div class="hint" style="margin-bottom:0">${tr("माँग (L/s)", "demand (L/s)")}</div>` +
    simChart([{ name: tr("माँग", "demand"), color: "#6a1b9a", values: dem }], dlo, dhi, "L/s", null, SIM.hour);
}
function simTankTable(r) {
  const names = Object.keys(r.tanks);
  return `<table class="wz"><tr><th>OHT</th><th>KL</th><th>${tr("दैनिक", "daily")} KL</th><th>${tr("शुरू", "start")} %</th><th>${tr("न्यूनतम", "lowest")} %</th><th>${tr("अंत", "end")} %</th><th>${tr("खाली (घंटे)", "dry (hours)")}</th><th>${tr("छलका", "spilt")} KL</th></tr>` +
    names.map((n, i) => { const t = r.tanks[n];
      return `<tr><td><span style="color:${DAY_COLORS[i % DAY_COLORS.length]}">■</span> ${esc(n)}</td><td>${fmt(t.kl)}</td><td>${fmt(t.daily_kl)}</td><td>${fmt(t.start_pct)}</td>` +
        `<td>${t.min_pct < 5 ? `<b style="color:var(--danger)">${fmt(t.min_pct)}</b>` : fmt(t.min_pct)}</td><td>${fmt(t.end_pct)}</td>` +
        `<td>${t.empty_h.length ? `<b style="color:var(--danger)">${t.empty_h.slice(0, 6).map(h => `<a href="#" data-h="${h}">${h}</a>`).join(", ")}${t.empty_h.length > 6 ? " …" : ""}</b>` : "-"}</td><td>${fmt(t.spill_kl)}</td></tr>`; }).join("") + `</table>`;
}

// ---- the controls
for (const b of document.querySelectorAll("#simmode button")) b.onclick = () => {
  SIM.mode = b.dataset.m; simStop();
  document.querySelectorAll("#simmode button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll("#side .simssa").forEach(el => el.hidden = SIM.mode !== "ssa");
  document.querySelectorAll("#side .simeps").forEach(el => el.hidden = SIM.mode !== "eps");
};
$("simbase").onchange = () => { $("simhour").hidden = $("simbase").value !== "hour"; $("simfactor").hidden = $("simbase").value !== "factor"; };
$("simpatreset").onclick = () => { if (SIM.info) { SIM.pattern = SIM.info.pattern.slice(); simPatEditor(); simHourOptions(); } };
$("simextraadd").onclick = () => { SIM.extra.push({ node: "", lps: 1 }); simRows(); };
$("simfireadd").onclick = () => { SIM.fires.push({ node: "", lps: $("wfirelps").value || 10 }); simRows(); };
$("simrun").onclick = simRun;
$("simclear").onclick = () => { SIM.res = null; SIM.ni = {}; SIM.pi = {}; simStop(); $("simres").innerHTML = ""; $("simstatus").textContent = ""; simColour(); map.closePopup(); };
document.addEventListener("click", e => { const a = e.target.closest("#simres a[data-h]"); if (a) { e.preventDefault(); simSetHour(+a.dataset.h); } });
simRows();
// the tab bar (ui.js): the Simulation layer only on its tab, the design's back elsewhere
{
  const uiTab0 = uiTab;
  uiTab = function (key) { uiTab0(key); simOnTab(key === "sim"); };
  if (document.body.dataset.tab === "sim") setTimeout(() => simOnTab(true), 0);
}
