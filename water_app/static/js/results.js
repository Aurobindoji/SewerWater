// The water map page (map.html), part 8 of 11: the stages, cuts, joins, the population map, the zoning and design results, Export DXF / DPR.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
function stageRestore(q) {
  if (q.base_year) $("byear").value = q.base_year;
  $("popb").value = q.pop_initial ?? ""; $("popm").value = q.pop_mid ?? "";
}
const STAGE_NAME = { init: () => tr("आधार वर्ष", "base year"), mid: () => tr("+15 वर्ष", "+15 years"), ult: () => tr("+30 वर्ष", "+30 years") };
const stageHead = st => `${STAGE_NAME[st.stage]()}${st.year ? " " + st.year : ""}`;
// the column header of a stage: its year and, in grey, what is designed for it (CPHEEO Table 2.1 / Table 2.7 S.No.1)
const stageCol = (st, mid, ult) => `<th>${esc(stageHead(st))}${st.stage === "mid" ? `<br><span class="hint">${mid}</span>`
  : st.stage === "ult" ? `<br><span class="hint">${ult}</span>` : ""}</th>`;
function waterStageBox(stages) {
  if (!stages || !stages.length) return "";
  const t1 = `<table class="wz"><tr><th>Stage</th><th>${tr("आबादी", "population")}</th><th>${tr("औसत माँग", "avg demand")}</th>` +
    `<th>residual head m</th><th>&lt; 17 m</th><th>&gt; 21 m</th><th>v &lt; 0.3</th><th>v &gt; 3</th></tr>` +
    stages.map(st => `<tr><td>${esc(stageHead(st))}${st.stage === "ult" ? ` <span class="hint">design</span>` : ""}</td><td>${fmt(st.pop)}</td><td>${fmt(st.avg_mld, 2)} MLD<br><span class="hint">peak ${fmt(st.peak_lps, 1)} L/s</span></td>` +
      `<td>${fmt(st.min_p, 1)} - ${fmt(st.max_p, 1)}</td><td>${st.low_n ? `<b style="color:#c62828">${st.low_n}</b>` : "0"}</td><td>${st.over_max_n}</td>` +
      `<td>${st.slow_n} <span class="hint">${fmt(st.slow_m / 1000, 2)} km</span></td><td>${st.fast_n ? `<b style="color:#c62828">${st.fast_n}</b>` : "0"}</td></tr>`).join("") + `</table>`;
  const t2 = `<table class="wz"><tr><th>OHT</th>` +
    stages.map(st => stageCol(st, "pumps", "pipes, ESR")).join("") + `</tr>` +
    stages[0].oz.map(({ oht: o }) => `<tr><td>${esc(o)}</td>` + stages.map(st => { const x = st.oz.find(y => y.oht === o) || {};
      return `<td>${fmt(x.flow_lps, 1)} L/s<br><span class="hint">${fmt(x.lowest_p, 1)} - ${fmt(x.highest_p, 1)} m</span></td>`; }).join("") +
      `</tr>`).join("") + `</table>`;
  return `<div class="box"><b>${tr("Stage-wise जाँच", "Stage-wise check")}</b>` + t1 + t2 +
    `<div class="hint">${tr("बने हुए pipe sizes और OHT staging के साथ हर stage की माँग पर network फिर से हल किया गया। कम माँग पर head loss कम, इसलिए दबाव बढ़ता है और velocity घटती है (0.3 m/s से कम = ठहराव, CPHEEO 6.6(i) p400)। Pipes और ESR +30 वर्ष के लिए, pumps +15 वर्ष के लिए (Table 2.7 S.No.1, p168)। 21 m से ऊपर = Table 2.7 S.No.10 (p173) की 17-21 m सीमा से अधिक; pressure management देखें।",
      "The network as designed (pipe sizes, OHT stagings) solved again at each stage's demand. Less demand: less head loss, so the head rises and the velocity falls (below 0.3 m/s = stagnation, CPHEEO 6.6(i) p400). Pipes and ESRs for +30 years, pumps for +15 years (Table 2.7 S.No.1, p168). Above 21 m = over the 17-21 m of Table 2.7 S.No.10 (p173); see pressure management.")}</div></div>`;
}
// ---- load cases and the 24 h simulation (user request 16-Nov-2026; simulate.py)
const CASE_NAME = { peak: () => tr("Peak (design)", "peak (design)"), average: () => tr("औसत", "average"),
  night: () => tr("रात (सबसे कम घंटा)", "night (lowest hour)"), fire: () => tr("Fire flow + औसत", "fire flow + average") };
function loadCaseBox(r) {
  const cs = r.load_cases;
  if (!cs || !cs.length) return "";
  const t = `<table class="wz"><tr><th>${tr("Load", "load")}</th><th>x ${tr("औसत", "avg")}</th><th>L/s</th><th>${tr("दबाव", "head")} m</th><th>&lt; 17 m</th><th>v max</th></tr>` +
    cs.map(c => `<tr><td>${esc(CASE_NAME[c.case] ? CASE_NAME[c.case]() : c.case)}</td><td>${fmt(c.factor, 2)}</td><td>${fmt(c.demand_lps, 1)}</td>` +
      `<td title="${esc(c.min_at || "")} - ${esc(c.max_at || "")}">${fmt(c.min_p, 1)} - ${fmt(c.max_p, 1)}</td>` +
      `<td>${c.low_n ? `<b style="color:var(--danger)">${c.low_n}</b>` : "0"}</td><td>${fmt(c.v_max, 2)}</td></tr>`).join("") + `</table>`;
  const f = (r.fires || []).length ? `<table class="wz"><tr><th>OZ</th><th>junction</th><th>fire L/s</th><th>${tr("दबाव", "head")} m</th><th>peak m</th></tr>` +
    r.fires.map(x => `<tr><td>${esc(x.oz)}</td><td>${esc(x.node)}</td><td>${fmt(x.fire_lps)}</td>` +
      `<td>${x.ok === false ? `<b style="color:var(--danger)">${fmt(x.p, 2)}</b>` : fmt(x.p, 2)}</td><td>${fmt(x.p_peak, 2)}</td></tr>`).join("") + `</table>` : "";
  return `<div class="box"><b>${tr("Load cases", "Load cases")}</b>` + t + f +
    `<div class="hint">${tr("बने हुए pipe sizes और OHT staging के साथ network हर load पर फिर से हल किया गया (OHT पर design का head - सबसे निचला जल स्तर)। रात = draw-off pattern का सबसे कम घंटा; fire = हर OZ के सबसे कमज़ोर junction पर दिया fire flow, औसत माँग के साथ।",
      "The network as designed solved again at each load (the OHTs at the design head - their lowest water level). Night = the lowest hour of the draw-off pattern; fire = the given fire flow at each OZ's weakest junction, with the average demand.")}</div></div>`;
}
// a small line chart of 24 hours: series [{name, color, values[24]}], y from lo to hi
function dayChart(series, lo, hi, unit, guide) {
  const W = 320, H = 120, L = 30, B = 16, T = 6, R = 6;
  const x = h => L + (W - L - R) * h / 23, y = v => T + (H - T - B) * (1 - (v - lo) / ((hi - lo) || 1));
  let g = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" style="display:block">`;
  for (const v of [lo, (lo + hi) / 2, hi]) g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${L - 3}" y="${y(v) + 3}" font-size="9" text-anchor="end" fill="var(--muted)">${fmt(v)}</text>`;
  for (const h of [0, 6, 12, 18, 23]) g += `<text x="${x(h)}" y="${H - 3}" font-size="9" text-anchor="middle" fill="var(--muted)">${h}</text>`;
  if (guide !== undefined) g += `<line x1="${L}" x2="${W - R}" y1="${y(guide)}" y2="${y(guide)}" stroke="var(--danger)" stroke-dasharray="3 3"/>`;
  for (const s of series) g += `<polyline fill="none" stroke="${s.color}" stroke-width="1.6" points="${s.values.map((v, h) => `${x(h).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}"><title>${esc(s.name)}</title></polyline>`;
  return g + `<text x="${L}" y="${T + 7}" font-size="9" fill="var(--muted)" dx="3">${esc(unit)}</text></svg>`;
}
const DAY_COLORS = ["#1f6feb", "#2e7d32", "#e65100", "#6a1b9a", "#00838f", "#ad1457", "#5d4037", "#827717"];
function dayBox(d) {
  if (!d || !d.hours || !d.hours.length) return "";
  const names = Object.keys(d.tanks);
  const lvl = names.map((n, i) => ({ name: n, color: DAY_COLORS[i % DAY_COLORS.length], values: d.hours.map(r => r.tanks[n].full_pct) }));
  const pmin = d.hours.map(r => r.min_p), pmax = d.hours.map(r => r.max_p);
  const lo = Math.min(17, ...pmin), hi = Math.max(...pmax);
  const t1 = `<table class="wz"><tr><th>OHT</th><th>KL</th><th>${tr("दैनिक", "daily")} KL</th><th>0 h %</th><th>${tr("न्यूनतम", "lowest")} %</th><th>24 h %</th><th>${tr("खाली", "dry")}</th></tr>` +
    names.map((n, i) => { const t = d.tanks[n];
      return `<tr><td><span class="k" style="background:${DAY_COLORS[i % DAY_COLORS.length]};display:inline-block;width:10px;height:3px;vertical-align:middle"></span> ${esc(n)}</td><td>${fmt(t.kl)}</td><td>${fmt(t.daily_kl)}</td><td>${fmt(t.start_pct)}</td>` +
        `<td>${fmt(t.min_pct)}</td><td>${fmt(t.end_pct)}</td><td>${t.empty_h.length ? `<b style="color:var(--danger)">${t.empty_h.map(h => h + "-" + (h + 1)).join(", ")}</b>` : "-"}</td></tr>`; }).join("") + `</table>`;
  const hrs = `<details><summary class="hint" style="cursor:pointer">${tr("घंटे-दर-घंटे तालिका", "hour by hour")}</summary><table class="wz"><tr><th>h</th><th>x</th><th>L/s</th><th>${tr("दबाव", "head")} m</th>` +
    names.map(n => `<th>${esc(n)} %</th>`).join("") + `</tr>` +
    d.hours.map(r => `<tr><td>${r.h}-${r.h + 1}</td><td>${fmt(r.factor, 2)}</td><td>${fmt(r.demand_lps, 1)}</td>` +
      `<td>${r.low_n ? `<b style="color:var(--danger)">${fmt(r.min_p, 1)}</b>` : fmt(r.min_p, 1)} - ${fmt(r.max_p, 1)}</td>` +
      names.map(n => { const x = r.tanks[n]; return `<td title="in ${fmt(x.in_kl)} / out ${fmt(x.out_kl)} KL">${fmt(x.full_pct)}</td>`; }).join("") + `</tr>`).join("") +
    `</table></details>`;
  return `<div class="box"><b>${tr("24 घंटे की simulation", "24 h simulation")}</b>` + t1 +
    `<div class="hint" style="margin-bottom:0">${tr("OHT में पानी (उपयोग योग्य का %)", "water in the OHTs (% of the usable)")}</div>` + dayChart(lvl, 0, 100, "%") +
    `<div class="hint" style="margin-bottom:0">${tr("Network का सबसे कम / सबसे अधिक दबाव (m); लाल = 17 m", "the network's lowest / highest head (m); red = 17 m")}</div>` +
    dayChart([{ name: tr("सबसे कम", "lowest"), color: "#c62828", values: pmin }, { name: tr("सबसे अधिक", "highest"), color: "#1565c0", values: pmax }], Math.floor(lo), Math.ceil(hi), "m", 17) +
    hrs + `<div class="hint">${tr(`हर घंटे की माँग = औसत x draw-off pattern; OHT भरने के घंटों (${d.windows.map(w => w[0] + "-" + w[1]).join(", ")}) में OZ की दैनिक माँग से भरती है, outlet के बहाव से खाली। उपयोग योग्य = क्षमता - fire का 1/3 (CPHEEO p138: outlet उसके ठीक ऊपर); 0 बजे mass balance की सबसे बड़ी कमी जितना पानी (औसत घंटे का x ${fmt(d.start_share, 2)}); टंकी side water depth का बेलन मानी गई।`,
      `Each hour's demand = average x the draw-off pattern; an OHT fills in its filling hours (${d.windows.map(w => w[0] + "-" + w[1]).join(", ")}) at its OZ's daily demand and empties by its outlet's flow. Usable = capacity - one third of the fire demand (CPHEEO p138: the outlet just above it); at 0 h the mass balance's largest deficit (x ${fmt(d.start_share, 2)} of an average hour); the tank as a cylinder of its side water depth.`)}</div></div>`;
}
const fmt = (x, d = 0) => x === null || x === undefined ? "-" : Number(x).toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d });
// the pipes cut at barrier lines: their parts (not in the layout the page has) and a mark where each was cut
function withCuts(r, geo) { for (const c of r.cut_parts || []) geo[c.label] = c; return geo; }
function drawCuts(r, layer) {
  for (const c of r.cuts || [])
    L.marker(c.latlng, { icon: L.divIcon({ className: "cut-icon", html: "✂", iconSize: [14, 14] }) })
      .bindTooltip(tr(`${c.pipe}: ${c.barrier} पर कटा - दोनों ओर रेखा से पहले बंद`, `${c.pipe}: cut at ${c.barrier} - ends short of it on both sides`)).addTo(layer);
}
// a gap between separate pieces of the drawing (user 30-Oct-2026): a red dashed line between their nearest junctions,
// a ring at its middle (a gap of a metre or two is too short to see as a line)
function drawGaps(r, layer) {
  for (const g of r.near_gaps || []) {
    const tip = tr(`${g.a} - ${g.b}: ${g.dist_m} m का gap - drawing के अलग टुकड़े, कोई pipe नहीं जोड़ता`,
                   `${g.a} - ${g.b}: a gap of ${g.dist_m} m - separate pieces of the drawing, joined by no pipe`);
    L.polyline(g.latlngs, { color: "#d32f2f", weight: 3, dashArray: "4 4", renderer: netRenderer }).bindTooltip(tip).addTo(layer);
    L.circleMarker([(g.latlngs[0][0] + g.latlngs[1][0]) / 2, (g.latlngs[0][1] + g.latlngs[1][1]) / 2],
                   { radius: 8, color: "#d32f2f", weight: 2, fill: false, renderer: netRenderer }).bindTooltip(tip).addTo(layer);
  }
}
// the isolated pieces of a DXF network joined by themselves (user request 30-Oct-2026): the server proposes a straight
// pipe from each piece to the nearest junction of the served network on its own side (no barrier / zone loop crossed,
// within JOINMAX m - 500 m from 7-Nov-2026: the user asked to join the pieces farther than 50 m to the main network);
// the page shows them first with the warning that joining by hand is better, then joins them on
// the user's word ('connect', one Undo) - purple on the map
const JOIN_COL = "#8e24aa";
let JOINMAX = 500;
const joinLayer = new L.FeatureGroup();
function joinPreview() {
  if (!NET) return notify(tr("DXF network नहीं", "No DXF network"), tr("यह सिर्फ़ DXF network पर है।", "This is for a DXF network only."), "err");
  const m = Number($("wjoinmax").value);
  if (m > 0) JOINMAX = m;
  let jr = null;
  longTask(tr("अलग टुकड़ों के जोड़ (झलक)", "Joins of the isolated pieces (preview)"), async () => {
    jr = await api("/api/water_join_plan", Object.assign(wInputs(), { join_max_m: JOINMAX }));
    if (jr.ok) showJoins(jr);
  }, () => !jr || !jr.ok ? [tr("झलक नहीं बनी", "No preview"), (jr && jr.log) || "error", "err"]
    : [tr("जोड़ों की झलक", "Preview of the joins"), joinSummary(jr) + "\n\n" + JOIN_WARN(), jr.joins.length ? "warn" : "ok"]);
}
const JOIN_WARN = () => tr("⚠ अपने-आप जोड़ सीधी रेखा में है: टुकड़े के सबसे पास वाले junction से उसी ओर (barrier या zone लूप पार किए बिना) के network के सबसे पास वाले junction तक - असली सड़क का रास्ता नहीं देखा जाता। बेहतर है कि हर टुकड़ा हाथ से (✎ / सड़क के साथ) जोड़ें; यहाँ नक्शे पर बैंगनी रेखाएँ जाँचकर ही जोड़ें।",
  "⚠ A join made by itself is a straight line: from the piece's nearest junction to the nearest junction of the network on the same side (no barrier or zone loop crossed) - the real road is not looked at. Joining each piece by hand (✎ / along the road) is better; join here only after checking the purple lines on the map.");
function joinSummary(jr) {
  const n = jr.joins.reduce((a, j) => a + j.nodes, 0), p = jr.joins.reduce((a, j) => a + j.population, 0),
        len = jr.joins.reduce((a, j) => a + j.dist_m, 0), mx = Math.max(0, ...jr.joins.map(j => j.dist_m));
  const cut = jr.left.filter(x => x.cut).length;
  return tr(`${jr.pieces} अलग टुकड़े (${fmt(jr.unserved)} junctions)। ${jr.joins.length} जोड़: ${fmt(n)} junctions, आबादी ${fmt(p)}, नए pipe कुल ${fmt(len, 1)} m (सबसे लंबा ${fmt(mx, 1)} m)।`,
            `${jr.pieces} isolated pieces (${fmt(jr.unserved)} junctions). ${jr.joins.length} joins: ${fmt(n)} junctions, population ${fmt(p)}, new pipes ${fmt(len, 1)} m in all (longest ${fmt(mx, 1)} m).`) +
    (jr.left.length ? "\n" + tr(`${jr.left.length} टुकड़े नहीं जुड़ेंगे (${fmt(jr.max_m)} m में अपनी ओर कोई junction नहीं; नक्शे पर नारंगी घेरा - ${leftList(jr, true)})` +
                                (cut ? `: ${cut} barrier से कटे - वहाँ crossing रेखा खींचें या OHT रखें` : "") + "; बाकी: हाथ से जोड़ें, OHT रखें या हटाएँ।",
                                `${jr.left.length} pieces stay apart (no junction on their side within ${fmt(jr.max_m)} m; orange ring on the map - ${leftList(jr, false)})` +
                                (cut ? `: ${cut} cut off by a barrier - draw a crossing line there or place an OHT` : "") + "; the rest: join by hand, place an OHT or delete.") : "");
}
// the pieces left: their junctions and straight distance to the network (a piece just beyond the 'within' m: raise it;
// one far away: an OHT of its own, or delete it)
const nearTxt = m => m == null ? "-" : m >= 1000 ? `${fmt(m / 1000, 1)} km` : `${fmt(m)} m`;
const leftList = (jr, hi) => jr.left.map(x => hi ? `${x.nodes} junctions, network से ${nearTxt(x.near_m)}`
                                                 : `${x.nodes} junctions, ${nearTxt(x.near_m)} from the network`).join("; ");
function showJoins(jr) {
  joinLayer.clearLayers();
  for (const j of jr.joins) {
    const tip = esc(tr(`${j.a} → ${j.b}: ${j.dist_m} m का नया pipe (प्रस्ताव) - ${j.nodes} junctions, आबादी ${fmt(j.population)}`,
                       `${j.a} → ${j.b}: a new pipe of ${j.dist_m} m (proposed) - ${j.nodes} junctions, population ${fmt(j.population)}`));
    L.polyline(j.latlngs, { color: JOIN_COL, weight: 4, dashArray: "6 4", renderer: netRenderer }).bindTooltip(tip).addTo(joinLayer);
    L.circleMarker(j.latlngs[0], { radius: 7, color: JOIN_COL, weight: 2, fill: false, renderer: netRenderer }).bindTooltip(tip).addTo(joinLayer);
  }
  for (const x of jr.left) if (x.latlng)
    L.circleMarker(x.latlng, { radius: 11, color: "#ef6c00", weight: 2, fill: false, dashArray: "3 3", renderer: netRenderer })
      .bindTooltip(esc(tr(`नहीं जुड़ेगा: ${x.nodes} junctions, आबादी ${fmt(x.population)}, network से ${nearTxt(x.near_m)}${x.cut ? " - barrier से कटा (crossing रेखा / OHT)" : ""}`,
                          `not joined: ${x.nodes} junctions, population ${fmt(x.population)}, ${nearTxt(x.near_m)} from the network${x.cut ? " - cut off by a barrier (crossing line / OHT)" : ""}`))).addTo(joinLayer);
  const box = $("wjoinres"); if (!box) return;
  box.innerHTML = `<div class="hint">${esc(joinSummary(jr)).replace(/\n/g, "<br>")}</div><div class="warn" style="margin-top:4px">${esc(JOIN_WARN())}</div>` +
    (jr.joins.length ? `<details><summary class="hint">${tr("जोड़ों की सूची", "The joins")}</summary><div class="hint">` +
      jr.joins.map(j => `${esc(j.a)} → ${esc(j.b)} ${j.dist_m} m (${j.nodes} junctions, ${fmt(j.population)})`).join("<br>") + `</div></details>` +
      `<div class="row" style="margin-top:4px"><button id="wjoingo" class="primary">${tr(`जोड़ें (${jr.joins.length} pipes)`, `Join (${jr.joins.length} pipes)`)}</button>` +
      `<button id="wjoinoff">${tr("झलक हटाएँ", "Clear the preview")}</button></div>` : "");
  if ($("wjoinoff")) $("wjoinoff").onclick = () => { joinLayer.clearLayers(); box.innerHTML = ""; };
  if ($("wjoingo")) $("wjoingo").onclick = async () => {
    if (!confirm(tr(`${jr.joins.length} नए सीधे pipes network में जुड़ेंगे (बैंगनी; एक Undo से सब वापस)। हाथ से जोड़ना बेहतर है - फिर भी जोड़ें?`,
                    `${jr.joins.length} new straight pipes go into the network (purple; one Undo takes them all back). Joining by hand is better - join anyway?`))) return;
    NET._before = new Set(Object.keys(NET.nodes));
    const r2 = await api("/api/net_edit", { name: NET.name, ops: jr.joins.map(j => ({ op: "connect", a: j.a, b: j.b, auto: true })) });
    if (!r2.ok) return notify(tr("नहीं जुड़े", "Not joined"), r2.log || "error", "err");
    applyNet(r2, null);                                  // the zoning is of the network before: cleared (netChanged)
    setView("layout");                                   // the Zones view has nothing now: the network with the new pipes
    const msg = tr(`${jr.joins.length} pipes जोड़े (नक्शे पर बैंगनी; वापस लेना हो तो Undo)। अब Zoning दोबारा चलाएँ।`,
                   `${jr.joins.length} pipes joined (purple on the map; to take them back: Undo). Now run the Zoning again.`);
    $("wstatus").className = "status ok"; $("wstatus").textContent = msg;
    notify(tr("टुकड़े जोड़े", "Pieces joined"), msg, "ok");
  };
}
// the checking map (user request 30-Oct-2026): each junction's population after the zoning, in 5 classes of equal
// count (quintiles) on one blue ramp, light = less (validated as an ordinal ramp, dataviz); none: grey; a bulk
// consumer's junction: a brown ring. Off by default (16,000 dots); the choice is kept for the session.
let LOADMAP = false;
const loadLayer = new L.FeatureGroup();
const LOAD_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"];
function drawLoad(r) {
  loadLayer.clearLayers();
  WLEG.zones = WLEG.zones_base || WLEG.zones;
  if (!LOADMAP || !r.node_load) { zoneLayer.removeLayer(loadLayer); return; }
  const pops = r.node_load.map(x => x[3]).filter(p => p > 0).sort((a, b) => a - b);
  const brk = [1, 2, 3, 4].map(i => pops[Math.floor(i * pops.length / 5)] ?? 0);   // upper ends of classes 1-4
  const cls = p => brk.findIndex(b => p <= b) < 0 ? 4 : brk.findIndex(b => p <= b);
  for (const [n, lat, lng, p, bulk] of r.node_load) {
    const tip = `${esc(n)}: ${tr("आबादी", "population")} ${fmt(p)}${bulk ? `, bulk ${fmt(bulk)} KLD` : ""}`;
    if (bulk) L.circleMarker([lat, lng], { radius: 7, color: "#6d4c41", weight: 2, fill: false, renderer: netRenderer }).bindTooltip(tip).addTo(loadLayer);
    L.circleMarker([lat, lng], p > 0 ? { radius: 3.5, stroke: false, fillColor: LOAD_RAMP[cls(p)], fillOpacity: 1, renderer: netRenderer }
                                     : { radius: 2.5, color: "#9e9e9e", weight: 1, fill: false, renderer: netRenderer }).bindTooltip(tip).addTo(loadLayer);
  }
  zoneLayer.addLayer(loadLayer);
  const lo = [0, ...brk], f1 = x => fmt(Math.round(x * 10) / 10);
  WLEG.zones += `<div style="margin-top:6px"><b>${tr("Junction की आबादी", "Junction population")}</b></div>` +
    LOAD_RAMP.map((c, i) => `<div><span class="k" style="background:${c};width:10px;height:10px;border-radius:50%"></span>` +
      `${i === 4 ? `> ${f1(lo[4])}` : `${f1(lo[i])} - ${f1(brk[i])}`}</div>`).join("") +
    `<div><span class="k" style="border:1px solid #9e9e9e;width:8px;height:8px;border-radius:50%"></span>0</div>` +
    `<div><span class="k" style="border:2px solid #6d4c41;width:10px;height:10px;border-radius:50%"></span>bulk consumer</div>` +
    `<div class="hint">${tr("हर रंग में लगभग बराबर junctions (5 हिस्से)", "about equal junctions in each colour (5 shares)")}</div>`;
}
// why an OZ was made (user request 30-Oct-2026): a tank given on the map; or a piece of the network the given tanks
// could not take, cut off by a barrier line / a zone loop, joined to the rest by no pipe (isolation) - and cut into
// OZs for the 50,000 limit
function whyZone(z) {
  const w = z && z.why;
  if (!w) return "";
  if (w.kind === "given") return w.existing ? tr("नक्शे पर दी गई पुरानी टंकी का OZ", "the OZ of an existing tank given on the map")
                                           : tr("नक्शे पर रखी नई टंकी का OZ", "the OZ of a new tank placed on the map");
  const L_ = (a) => a.join(", "), out = [];
  if (w.loop) out.push(w.loop_mode === "split" ? tr(`Zone लूप "${w.loop}" का क्षेत्र (स्वतः नए zone)`, `zone loop "${w.loop}" (new zones by itself)`)
                                               : tr(`Zone लूप "${w.loop}" का क्षेत्र (जैसा खींचा)`, `zone loop "${w.loop}" (as drawn)`));
  if (w.next_to && w.next_to.length) out.push(tr(`पास की टंकियाँ (${L_(w.next_to)}) इसे नहीं ले सकीं - उनकी क्षमता, 50,000 की सीमा या ऊँचाई के कारण`,
                                                `the tanks next to it (${L_(w.next_to)}) could not take it - their capacity, the 50,000 limit or the height`));
  if (w.barriers && w.barriers.length) out.push(tr(`रुकावट रेखा (${L_(w.barriers)}) से कटकर अलग हुआ network का टुकड़ा`,
                                                  `a piece of the network cut off by the barrier line(s) ${L_(w.barriers)}`));
  if (w.loops_closed && w.loops_closed.length) out.push(tr(`Zone लूप (${L_(w.loops_closed)}) की सीमा के valves से अलग हुआ टुकड़ा`,
                                                          `a piece cut off by the boundary valves of the zone loop(s) ${L_(w.loops_closed)}`));
  if (w.main) out.push(tr("नक्शे पर कोई टंकी नहीं दी गई - network के मुख्य हिस्से के लिए नई टंकी", "no tank given on the map - a new tank for the main part of the network"));
  if (w.isolated) out.push(tr("network का अलग टुकड़ा - drawing में किसी pipe से बाकी network से नहीं जुड़ा (isolation)",
                              "a separate piece of the network - joined to the rest by no pipe in the drawing (isolation)"));
  out.push(w.parts > 1
    ? tr(`इस टुकड़े की आबादी ${fmt(w.piece_population)} - एक OZ की सीमा 50,000 (CPHEEO Table 2.7 S.No.20, p180) से अधिक, इसलिए ${w.parts} OZ में बाँटा: ${L_(w.piece_zones || [])}`,
         `this piece's population ${fmt(w.piece_population)} - above the 50,000 of one OZ (CPHEEO Table 2.7 S.No.20, p180), so cut into ${w.parts} OZs: ${L_(w.piece_zones || [])}`)
    : tr(`इस टुकड़े की आबादी ${fmt(w.piece_population)} - एक OZ काफ़ी`, `this piece's population ${fmt(w.piece_population)} - one OZ`));
  return tr("यह zone क्यों: ", "Why this zone: ") + out.join("; ");
}
// a zoning message: in Hindi when the page is (the server sends both; the files keep the English - user 30-Oct-2026)
const flagText = f => (!EN && f.hi) ? f.hi : f.text;
const checkText = c => (!EN && c.check_hi) ? `${c.check_hi}: ${c.detail_hi}` : `${c.check}: ${c.detail}`;
function zoneColor(names) { const c = {}; names.forEach((n, i) => c[n] = ZPAL[i % ZPAL.length]); return c; }

function renderWZoning(r, note) {
  wZoning = r;
  const sbOwn = r.req ? !!(r.req.tw_standby && r.req.tw_standby.on) : $("wsbon").checked;   // the standby table used
  $("wzbox").before($("wstatus"));       // its message in the zoning step (the sidebar's steps, 10-Nov-2026)
  zoneLayer.clearLayers();
  const col = zoneColor(r.zones.map(z => z.name));
  const geo = {}; (layoutData && layoutData.conduits || []).forEach(c => geo[c.label] = c); withCuts(r, geo);
  const zwhy = {}; for (const z of r.zones) zwhy[z.name] = whyZone(z);     // the reason on each pipe of the OZ too
  for (const [lab, z] of Object.entries(r.pipe_zone)) {
    const c = geo[lab]; if (!c) continue;
    pickable(L.polyline(c.pts, { color: col[z] || "#888", weight: 3, opacity: .9, dashArray: r.pipe_dma[lab] ? null : "6 5", renderer: netRenderer }),
      `<b>${esc(lab)}</b><br>OZ ${esc(z || "-")}<br>DMA ${esc(r.pipe_dma[lab] || tr("दो DMA के बीच", "between two DMAs"))}` +
      (zwhy[z] ? `<div class="why-line">${esc(zwhy[z])}</div>` : ""), true).addTo(zoneLayer);
  }
  for (const d of r.dmas)
    for (const ring of d.rings) L.polygon(ring, { color: col[d.zone], weight: 1.5, dashArray: "4 5", fill: false, interactive: false }).addTo(zoneLayer);
  for (const z of r.zones) {
    for (const ring of z.rings) L.polygon(ring, { color: col[z.name], weight: 4, fillColor: col[z.name], fillOpacity: .06, interactive: false }).addTo(zoneLayer);
    if (z.label) L.marker(z.label, { keyboard: false, icon: L.divIcon({ className: "", html: `<div class="zlabel" style="color:${col[z.name]}">${esc(z.name)}</div>`, iconSize: null }) })
      .bindTooltip(esc(whyZone(z)), { className: "why-tip" }).addTo(zoneLayer);
  }
  for (const d of r.dmas)
    if (d.label && r.dmas.filter(x => x.zone === d.zone).length > 1)
      L.marker(d.label, { interactive: false, icon: L.divIcon({ className: "", html: `<div class="zlabel sub">${esc(d.name.split("/")[1])}</div>`, iconSize: null }) }).addTo(zoneLayer);
  const drawnOht = {}; drawn.eachLayer(l => { if (l.kind === "oht") drawnOht[l.props.name] = l; });
  const placed = (r.proposed || []).length > 0 && r.proposed.every(p => drawnOht[p.name]);
  for (const z of r.zones.filter(z => z.proposed && !drawnOht[z.name])) {
    const m = L.marker(z.latlng, { icon: icon("oht", false, { name: z.name, existing: "0" }) }).addTo(zoneLayer);
    hoverCard(m, () => ({ html: ohtCardHtml(z.name, false) +
      `<div class="hint">${tr("Move: OHT (और उसके OZ के सुझाए tube wells) आपके हो जाएँगे, नक्शे पर।", "Move: the OHT (and its OZ's suggested tube wells) become yours, on the map.")}</div>`,
      acts: [["✕", tr("हटाएँ - अगली Zoning में यह OHT नहीं", "remove - no OHT here in the next zoning"), () => sugOhtOff(z.name, z.latlng, [m]), "del"],
             ["✥ move", tr("आपकी बनाकर खींचें", "make it yours and drag it"), () => hcMove(convertOht(z.name, z.latlng, [m]))]] }));
  }
  for (const p of r.unserved_pts || [])
    L.circleMarker(p, { radius: 5, color: "#616161", weight: 2, fill: false, dashArray: "2 2", renderer: netRenderer })
      .bindTooltip(tr("किसी OHT से जुड़ा नहीं (सड़क का अलग टुकड़ा)", "joined to no OHT (a separate road piece)")).addTo(zoneLayer);
  // a closed pipe's valve: half way along the pipe as drawn (it may follow the bends of its road)
  const pgeo = {}; (layoutData && layoutData.conduits || []).forEach(c => pgeo[c.label] = c.pts);
  for (const c of r.cut_parts || []) pgeo[c.label] = c.pts;
  drawCuts(r, zoneLayer);
  drawGaps(r, zoneLayer);
  // bulk consumers: a line to the junction their demand joins (user 30-Oct-2026)
  for (const b of r.bulk_pts || [])
    L.polyline(b.latlngs, { color: "#6d4c41", weight: 2, dashArray: "3 4", renderer: netRenderer })
      .bindTooltip(esc(`${b.name}: ${b.kld} KL/day, peak ${b.peak} → ${b.node} (${b.dist_m} m)`)).addTo(zoneLayer);
  // junctions of a DXF network in no ward: no population there (user 30-Oct-2026)
  for (const p of r.ward_out_pts || [])
    L.circleMarker(p, { radius: 3, color: "#ef6c00", weight: 1, fillColor: "#ff9800", fillOpacity: .9, renderer: netRenderer })
      .bindTooltip(tr("किसी वार्ड में नहीं - आबादी 0", "in no ward - no population")).addTo(zoneLayer);
  const midAlong = P => {
    const Q = P.map(x => L.latLng(x)), seg = Q.slice(1).map((q, i) => q.distanceTo(Q[i]));
    let goal = seg.reduce((a, b) => a + b, 0) / 2;
    for (let i = 0; i < seg.length; i++) {
      if (goal <= seg[i] || i === seg.length - 1) { const t = seg[i] ? Math.min(1, goal / seg[i]) : 0;
        return L.latLng(Q[i].lat + (Q[i + 1].lat - Q[i].lat) * t, Q[i].lng + (Q[i + 1].lng - Q[i].lng) * t); }
      goal -= seg[i];
    }
    return Q[0];
  };
  for (const c of r.closed)
    L.marker(pgeo[c.pipe] && pgeo[c.pipe].length > 1 ? midAlong(pgeo[c.pipe]) : c.latlng, { icon: L.divIcon({ className: "closed-icon", html: "⊗", iconSize: [14, 14] }) })
      .bindTooltip(tr(`${c.pipe}: बंद (OZ / DMA सीमा का valve)`, `${c.pipe}: closed (OZ / DMA boundary valve)`)).addTo(zoneLayer);
  // OHT capacity: max(33 %, mass balance) of the OZ's daily demand (CPHEEO Table 2.7 S.No.12 p175)
  const st = r.storage, pc = x => (x * 100).toFixed(1) + " %";
  const stShare = st ? pc(st.share) : "33 %";
  const stNote = st ? `<div class="hint">${tr(
    `OHT क्षमता = दैनिक माँग (fire के बिना) का ${pc(st.share)}: mass balance ${pc(st.mass_balance)} (${st.hours} घंटे भराई), न्यूनतम ${pc(st.min_share)} - जो अधिक हो (CPHEEO Table 2.7 S.No.12, p175); + fire demand का ${st.fire_share ? pc(st.fire_share) : "1/3"} (S.No.13, p176)`,
    `OHT capacity = ${pc(st.share)} of the daily demand (without fire): mass balance ${pc(st.mass_balance)} (filled ${st.hours} h), minimum ${pc(st.min_share)} - the larger (CPHEEO Table 2.7 S.No.12, p175); + ${st.fire_share ? pc(st.fire_share) : "1/3"} of the fire demand (S.No.13, p176)`)}</div>` : "";
  const flags = r.flags.map(f => `<div class="wflag ${f.level}">${f.level === "error" ? "✖" : f.level === "info" ? "ℹ" : "⚠"} ${esc(flagText(f))}</div>`).join("");
  $("wzbox").innerHTML = `<div class="row"><label style="min-width:0" title="${tr("हर junction की आबादी रंग से (हल्का = कम, गहरा = अधिक; 5 बराबर हिस्से), आबादी 0 वाले धूसर, bulk consumer वाले भूरे घेरे में - बँटवारा जाँचने के लिए",
      "each junction's population by colour (light = less, dark = more; 5 equal shares), none: grey, a bulk consumer: brown ring - to check the population as spread")}">` +
      `<input type="checkbox" id="wloadmap"${LOADMAP ? " checked" : ""}> ${tr("आबादी का नक्शा (हर junction)", "Population map (every junction)")}</label></div>` +
    `<table class="wz"><tr><th>OZ (OHT)</th><th>आबादी</th><th title="${tr("आबादी / OZ का क्षेत्रफल (नक्शे पर खिंची सीमा)", "population / the OZ's area (its boundary drawn on the map)")}">${tr("घनत्व /ha", "Density /ha")}</th><th>कनेक्शन</th><th>माँग KLD</th><th>OHT KL</th><th>CWR KL</th><th>DMA</th><th>DMA आबादी</th></tr>` +
    r.zones.map(z => `<tr><td style="color:${col[z.name]};font-weight:600;cursor:help" title="${esc(whyZone(z))}">${esc(z.name)}${z.proposed ? ` <span class="hint">(${tr("प्रस्तावित", "proposed")})</span>` : ""}</td><td>${fmt(z.population)}</td>` +
      `<td title="${z.area_ha ? `${fmt(z.area_ha)} ha` : ""}">${z.density != null ? fmt(z.density) : "-"}</td><td>${fmt(z.connections)}</td>` +
      `<td title="${z.fire_kld != null ? tr(`इसमें fire ${fmt(z.fire_kld)} KLD`, `fire ${fmt(z.fire_kld)} KLD of it`) : ""}">${fmt(z.demand_kld)}</td>` +
      `<td title="${(z.existing ? tr(`मौजूदा क्षमता / आवश्यक (${stShare})`, `existing / required (${stShare})`) : tr(`नई टंकी: आवश्यक क्षमता (${stShare})`, `new OHT: required capacity (${stShare})`)) +
        (z.fire_store_kl != null ? tr(` = संतुलन ${fmt(z.balancing_kl)} + अग्निशमन ${fmt(z.fire_store_kl)} KL (fire का 1/3), ऊपर पूर्णांकित`, ` = balancing ${fmt(z.balancing_kl)} + fire ${fmt(z.fire_store_kl)} KL (1/3 of the fire), rounded up`) : "")}">` +
      `${z.existing ? `${fmt(z.capacity_kl)} / ${fmt(z.required_kl)}` : `${tr("नई", "new")} ${fmt(z.required_kl)}`}</td>` +
      // tube wells filling the OHT: given on the map + new for the +15 years demand (UPJN: more than 3 -> CWR)
      `<td title="${tr(`नलकूप: नक्शे पर ${z.tubewells}${z.rebore ? ` + rebore ${z.rebore}` : ""} + नए ${z.tubewells_new ?? 0} (+15 वर्ष की माँग) + standby ${z.tubewells_standby ?? 0} (${sbOwn ? "page की table" : "CPHEEO 5.7.5"}; हर एक पूरा नया नलकूप); नए चालू 3 से अधिक हों तो CWR (जल निगम नियम; पुराने नलकूप पुराने structures से जुड़े रहते हैं)`,
                       `tube wells: ${z.tubewells} on the map${z.rebore ? ` + ${z.rebore} rebored` : ""} + ${z.tubewells_new ?? 0} new (+15 years demand) + ${z.tubewells_standby ?? 0} standby (${sbOwn ? "the page's table" : "CPHEEO 5.7.5"}; each a whole new tube well); more than 3 new working: CWR (UPJN rule; the existing ones stay with the existing structures)`)}">` +
      `${z.cwr_kl ? fmt(z.cwr_kl) : "-"}</td><td>${z.dma_count}</td>` +
      // the population of each DMA of the OZ (user request 21-Oct-2026), its connections in the tooltip
      `<td title="${esc(r.dmas.filter(d => d.zone === z.name).map(d => `${d.name}: ${fmt(d.connections)} ${tr("कनेक्शन", "connections")}` +
        (d.density != null ? `, ${fmt(d.density)} /ha` : "")).join("; "))}">` +
      `${r.dmas.filter(d => d.zone === z.name).map(d => fmt(d.population)).join(" / ")}</td></tr>`).join("") + `</table>` +
    (r.proposed && r.proposed.length ? `<div class="warn" style="margin-top:4px">${tr(
      `पुरानी टंकियाँ पूरे क्षेत्र के लिए काफ़ी नहीं: ${r.proposed.length} नई टंकी प्रस्तावित (नक्शे पर ${r.proposed.map(p => esc(p.name)).join(", ")}) - क्षमता ऊपर तालिका में, staging Design से।`,
      `The existing tanks cannot serve the whole area: ${r.proposed.length} new tank(s) proposed (${r.proposed.map(p => esc(p.name)).join(", ")} on the map) - capacity in the table, staging from the Design.`)}
      ${placed ? `<div class="hint" style="color:var(--ok)">✔ ${tr("प्रस्तावित OHT नक्शे पर रख दी गई हैं - किसी टंकी पर click करें: क्षमता / staging बदलें या उसे खींचकर खिसकाएँ; फिर Zoning और Design दोबारा चलाएँ।",
        "The proposed OHTs are placed on the map - click a tank to change its capacity / staging or drag it to move it; then run Zoning and Design again.")}</div>`
      : `<div class="row" style="margin-top:4px"><button id="wplace">${tr("प्रस्तावित OHT नक्शे पर रखें (फिर खिसका सकते हैं)", "Place the proposed OHTs on the map (then move them)")}</button></div>`}</div>` : "") +
    `<div class="hint">${r.dmas.map(d => `${esc(d.name)}: ${fmt(d.connections)} ${tr("कनेक्शन", "connections")}`).join("; ")}</div>` +
    `<div class="hint">${r.closed.length} ${tr("pipes OZ / DMA सीमा पर बंद (⊗) - हर OZ / DMA अलग, एक inlet", "pipes closed at OZ / DMA boundaries (⊗) - each OZ / DMA discrete, one inlet")}` +
    (r.moved ? `; ${r.moved} ${tr("nodes सीमा पर पड़ोसी OZ को दिए (क्षमता / 50,000)", "nodes given to a neighbouring OZ (capacity / 50,000)")}` : "") + `</div>` + stNote + flags +
    (r.unserved && mode === "dxf" ? `<div class="box" style="margin-top:4px"><div class="row"><button id="wjoin" title="${tr(
      "किसी OHT से न जुड़े (धूसर घेरे वाले) टुकड़ों को मुख्य network के सबसे पास के junction से सीधे pipe द्वारा जोड़ने का प्रस्ताव (अधिकतम दूरी तक, barrier पार नहीं) - पहले नक्शे पर झलक, फिर आपके कहने पर",
      "a proposal to join the pieces joined to no OHT (grey rings) by a straight pipe to the nearest junction of the main network (within the distance, no barrier crossed) - a preview on the map first, joined on your word")}">🔗 ${tr("मुख्य network से जोड़ें (झलक)…", "Join to the main network (preview)…")}</button>` +
      `<label style="min-width:0">${tr("अधिकतम", "within")} <input id="wjoinmax" type="number" min="1" step="10" value="${JOINMAX}" style="width:64px"> m</label></div><div id="wjoinres"></div></div>` : "");
  joinLayer.clearLayers(); zoneLayer.addLayer(joinLayer);
  if ($("wjoin")) $("wjoin").onclick = () => joinPreview();
  if ($("wplace")) $("wplace").onclick = () => {          // the proposals become OHTs of the drawing (new: no capacity / staging)
    for (const z of r.zones.filter(z => z.proposed && !drawnOht[z.name]))
      addFeature(L.marker(z.latlng), "oht", { name: z.name, existing: "0", capacity_kl: "", staging_m: "", tubewells: "" });
    changed();
    renderWZoning(r, note);                            // the note instead of the button, no second marker
    notify(tr("OHT रखी गईं", "OHTs placed"), tr("प्रस्तावित OHT अब नक्शे पर हैं - किसी टंकी पर click करें: क्षमता / staging बदलें या उसे खींचकर ऊँची / उपलब्ध ज़मीन पर ले जाएँ; फिर Zoning और Design दोबारा चलाएँ।",
      "The proposed OHTs are now on the map - click a tank to change its capacity / staging or drag it to high / available land; then run Zoning and Design again."), "ok");
  };
  WLEG.zones = r.zones.map(z => `<div><span class="k" style="background:${col[z.name]};height:5px"></span>${esc(z.name)}</div>`).join("") +
    `<div class="hint">${tr("मोटी रेखा = OZ, बिंदीदार = DMA, ⊗ = बंद pipe, टूटी रेखा = दो DMA के बीच का pipe", "thick = OZ, dotted = DMA, ⊗ = closed pipe, dashed = pipe between two DMAs")}</div>`;
  WLEG.zones_base = WLEG.zones;
  drawLoad(r);
  $("wloadmap").onchange = () => { LOADMAP = $("wloadmap").checked; drawLoad(r); legend("zones"); };
  $("wstatus").className = "status " + (r.stale ? "err" : r.flags.some(f => f.level === "error") ? "err" : "ok");
  $("wstatus").textContent = (note ? note + " - " : "") + tr(`${r.zones.length} OZ, ${r.dmas.length} DMA, आबादी ${fmt(r.population)}`,
    `${r.zones.length} OZ, ${r.dmas.length} DMA, population ${fmt(r.population)}`);
  $("viewseg").hidden = false;
  setView("zones");
}

// the PRVs of a design (prv.py, user 30-Oct-2026): those on the map with what each did, the suggested ones (a dashed
// ring on their pipe) and a button placing them
// the PRV option (user 31-Oct-2026, off by default): the PRV tool shown only when it is on
function prvTools() { document.querySelectorAll('button[data-kind="prv"]').forEach(b => b.hidden = !$("wprv").checked); }
$("wprv").onchange = prvTools;
prvTools();
function prvBox(r) {
  const P = r.prvs || [], S = r.prv_suggest || [];
  if (!P.length && !S.length) return "";
  const row = p => `<tr><td>${esc(p.name)}</td><td>${esc(p.pipe || "-")}<br><span class="hint">${esc(p.size || "")}</span></td>` +
    (p.active ? `<td><b>${fmt(p.setting_m, 1)}</b>${p.auto ? ` <span class="hint">${tr("अपने-आप", "auto")}</span>` : ""}</td>` +
                `<td>-${fmt(p.cut_m, 1)}</td><td>${fmt(p.nodes)}</td><td>${fmt(p.max_before, 1)} → ${fmt(p.max_after, 1)}</td></tr>`
              : `<td colspan="4" style="color:${p.pipe && !/loop|closed/.test(p.note || "") ? "inherit" : "#c62828"}">${esc((c => c ? (EN ? c.detail : c.detail_hi) : p.note || "")(r.checks.find(c => c.check === `PRV ${p.name}`)))}</td></tr>`);
  const srow = g => `<tr><td>${tr("सुझाव", "suggested")}</td><td>${esc(g.pipe)}<br><span class="hint">${esc(g.size || "")}</span></td>` +
    `<td>${fmt(g.setting_m, 1)}</td><td>-${fmt(g.cut_m, 1)}</td><td>${fmt(g.nodes)}</td><td>${tr("31 m से ऊपर", "above 31 m")} ${g.high_before} → ${g.high_after}</td></tr>`;
  return `<div class="box"><b>PRV</b><table class="wz"><tr><th></th><th>pipe</th><th>setting m</th><th>${tr("घटा", "cut")} m</th><th>junctions</th><th>${tr("अधिकतम दबाव m", "highest head m")}</th></tr>` +
    P.map(row).join("") + S.map(srow).join("") + `</table>` +
    (S.length ? `<div class="row" style="margin-top:4px"><button id="wprvplace">${tr(`सुझाए ${S.length} PRV नक्शे पर रखें`, `Place the ${S.length} suggested PRVs on the map`)}</button></div>` : "") +
    (r.prv_left ? `<div class="hint">${tr(`${r.prv_left} junctions 31 m से ऊपर छोटी शाखाओं पर (एक PRV पर 5 से कम) - चाहें तो हाथ से PRV रखें`,
                                          `${r.prv_left} junctions above 31 m on small branches (fewer than 5 for one PRV) - a PRV by hand if wanted`)}</div>` : "") +
    `<div class="hint">${tr("Setting = PRV के बाद का residual head; अपने-आप = सबसे कम जिससे आगे हर junction पर 17 m (+30 वर्ष peak), हर stage में वही। सुझाव वहाँ जहाँ 31 m से ऊपर के junctions हों; DPR (D2) में पीली सूचक rate।",
      "Setting = the residual head after the PRV; auto = the lowest keeping 17 m at every junction beyond it (+30 years peak), the same at every stage. Suggested where junctions are above 31 m; DPR (D2) at a yellow indicative rate.")}</div></div>`;
}
function drawPrvs(r) {
  for (const p of r.prvs || []) if (p.latlng)
    L.marker(p.latlng, { icon: L.divIcon({ className: "prv-icon" + (p.active ? "" : " bad"), html: "P", iconSize: [20, 20] }), zIndexOffset: 900 })
      .bindTooltip(esc(p.active ? `${p.name} (${p.pipe}): setting ${p.setting_m} m, -${p.cut_m} m, ${p.nodes} junctions, ${tr("अधिकतम", "highest")} ${p.max_before} → ${p.max_after} m`
                                : `${p.name} (${p.pipe || "-"}): ${p.note || ""}`)).addTo(designLayer);
  for (const g of r.prv_suggest || []) if (g.latlng)
    L.marker(g.latlng, { icon: L.divIcon({ className: "prv-icon sug", html: "P?", iconSize: [20, 20] }), zIndexOffset: 800 })
      .bindTooltip(esc(tr(`सुझाया PRV (${g.pipe}): setting ${g.setting_m} m, -${g.cut_m} m, ${g.nodes} junctions; 31 m से ऊपर ${g.high_before} → ${g.high_after}`,
                          `suggested PRV (${g.pipe}): setting ${g.setting_m} m, -${g.cut_m} m, ${g.nodes} junctions; above 31 m ${g.high_before} → ${g.high_after}`))).addTo(designLayer);
}
// the new tube wells and their rising mains (water phase 2, rising.py, user 31-Oct-2026): a table, the mains on the map
// along the roads, the suggested sites as dashed rings and a button placing them
function rmBox(r) {
  const R = r.rising, T = (R && R.tws) || [];
  if (!T.length && !((R && R.needed) || []).length) return "";
  const sug = T.filter(t => !t.placed && !t.auto).length + ((R && R.needed) || []).length, D = (R && R.dropped) || [];
  const row = t => `<tr><td>${esc(t.name)}${t.placed ? "" : ` <span class="hint">${tr("सुझाव", "suggested")}</span>`}</td><td>${esc(t.oz)}</td>` +
    (t.size ? `<td>${fmt(t.length_m)}</td><td><b>${esc(t.size)}</b>${t.cls === "K9" ? ` <span style="color:#6a1b9a">K9</span>` : ""}</td><td>${fmt(t.v, 2)}</td><td>${fmt(t.hf_m, 2)}</td><td>${fmt(t.head_m, 1)}</td>` +
              `<td${t.surge_ok ? "" : ' style="color:#c62828"'}>${fmt(t.max_m, 0)} / ${fmt(t.rating_m, 0)}</td></tr>`
            : `<td colspan="6" style="color:#c62828">${esc(t.note || "")}</td></tr>`);
  return `<div class="box"><b>${tr("नए tube wells और rising mains", "New tube wells and rising mains")}</b>` +
    `<table class="wz"><tr><th>TW</th><th>OZ</th><th>${tr("लंबाई m", "length m")}</th><th>size</th><th>V m/s</th><th>${tr("घर्षण m", "friction m")}</th><th>head m</th>` +
    `<th title="${tr("pump head + surge (h = cV/g) / pipe का working pressure", "pump head + surge (h = cV/g) / the pipe's working pressure")}">surge m</th></tr>` +
    T.map(row).join("") + `</table>` +
    (D.length ? `<div class="hint" style="margin-top:4px">${tr(`नक्शे के ${D.length} tube wells नहीं लिए (हर OZ में सिर्फ़ ज़रूरत भर)`, `${D.length} tube wells of the map not taken (each OZ only as many as it needs)`)}:<br>` +
      [...new Set(D.map(d => d.oz))].sort().map(oz => { const g = D.filter(d => d.oz === oz), need = (R.need || {})[oz];
        return `<b>${esc(oz)}</b> (${g[0].why === "auto" ? tr("OHT zoning की", "the zoning's OHT") : tr(`${need ?? "?"} चाहिए`, `${need ?? "?"} needed`)}): ` +
          g.map(d => esc(d.name)).join(", "); }).join("<br>") +
      `<br>${tr("Proposed OHT वाले OZ के tube wells OHT के साथ सुझाए जाते हैं; नक्शे वाले तब लिए जाते हैं जब OHT भी नक्शे पर रखी हो (या सुझाने को जगह न मिले)।", "In an OZ of a proposed OHT the tube wells are suggested with the OHT; the map's are taken when the OHT too is placed on the map (or no site is found).")}</div>` : "") +
    (sug ? `<div class="row" style="margin-top:4px"><button id="wtwplace">${tr(`सुझाए ${sug} tube wells नक्शे पर रखें`, `Place the ${sug} suggested tube wells on the map`)}</button></div>` : "") +
    `<div class="hint">${tr("हर नए TW की अपनी main सड़क के रास्ते OHT तक; size = economic (pipe + pumps + 30 वर्ष की बिजली का सबसे कम, CPHEEO 6.7 / Annexure 6.1); surge = pump रुकने पर (CPHEEO 6.16.4)। सुझाए TW OHT के पास, आपस में 100 m दूर - उपलब्ध ज़मीन पर खिसकाएँ। DPR: T15 Rising Main, D5 Rising Main।",
      "Each new tube well its own main along the roads to the OHT; size = economical (least pipe + pumps + 30 years of energy, CPHEEO 6.7 / Annexure 6.1); surge = on a pump stop (CPHEEO 6.16.4). Suggested tube wells near the OHT, 100 m apart - move them to available land. DPR: T15 Rising Main, D5 Rising Main.")}</div></div>`;
}
function drawRising(r) {
  for (const t of (r.rising && r.rising.tws) || []) {
    const tip = esc(t.size ? `${t.name} → ${t.oz}: ${fmt(t.length_m)} m ${t.size}${t.cls ? " " + t.cls : ""}, ${fmt(t.q_lps, 1)} L/s, V ${fmt(t.v, 2)} m/s, ${tr("घर्षण", "friction")} ${fmt(t.hf_m, 2)} m, head ${fmt(t.head_m, 1)} m`
                               : `${t.name}: ${t.note || ""}`);
    if (t.path) L.polyline(t.path, { color: "#00897b", weight: 4, opacity: .85, dashArray: "10 6", renderer: netRenderer }).bindTooltip(tip).addTo(designLayer);
    const line = t.path ? designLayer.getLayers()[designLayer.getLayers().length - 1] : null;
    const m = L.marker(t.latlng, { icon: L.divIcon({ className: "tw-icon" + (t.placed ? "" : " sug") + (t.standby ? " sb" : ""), html: t.placed ? "T" : "T?", iconSize: [20, 20] }), zIndexOffset: 850 })
      .addTo(designLayer);
    if (t.placed) hoverCard(m, () => { const l = drawnBy("tw", t.name);
      return { html: twCardHtml(t.name, t.lpm, true) + hcStale(), acts: l ? [["✕", tr("नक्शे से हटाएँ", "remove from the map"), () => hcDelete(l, [m, line]), "del"],
                                                                         ["✥ move", tr("खींचकर नई जगह", "drag to a new place"), () => { m.remove(); if (line) line.remove(); hcMove(l); }]] : [] }; });
    else hoverCard(m, () => ({ html: twCardHtml(t.name, t.lpm, false) +
      `<div class="hint">${t.auto ? tr("Move: इसका OZ (OHT और सुझाए tube wells) आपका हो जाएगा, नक्शे पर।", "Move: its OZ (the OHT and the suggested tube wells) becomes yours, on the map.")
                                  : tr("Move: यह tube well आपका हो जाएगा, नक्शे पर।", "Move: this tube well becomes yours, on the map.")}</div>`,
      acts: [["✕", tr("हटाएँ - उसकी जगह कोई नहीं सुझाया जाएगा", "remove - none suggested in its place"), () => sugTwOff(t, [m, line]), "del"],
             ["✥ move", tr("आपका बनाकर खींचें", "make it yours and drag it"), () => moveSuggestedTw(t, [m, line])]] }));
  }
  for (const t of (r.rising && r.rising.needed) || []) {   // the sites the shortfall needs: not in the design
    const m = L.marker(t.latlng, { icon: L.divIcon({ className: "tw-icon need", html: "T!", iconSize: [20, 20] }), zIndexOffset: 840 }).addTo(designLayer);
    hoverCard(m, () => ({ html: `<b>${esc(t.oz)}</b>: ${tr("आवश्यक tube well - design में नहीं (कमी पूरी करने के लिए सुझाई जगह)", "a tube well needed - not in the design (a site suggested for the shortfall)")}` +
      `<div class="hint">${tr("Move: नक्शे पर आपका बनेगा; फिर Design दोबारा चलाएँ।", "Move: it becomes yours on the map; then run the Design again.")}</div>`,
      acts: [["✥ move", tr("आपका बनाकर खींचें", "make it yours and drag it"), () => { m.remove(); hcMove(addFeature(L.marker(t.latlng), "tw", { name: nextTw(), discharge_lpm: "" })); }]] }));
  }
}
function renderWDesign(r, note) {
  wDesign = r;
  $("wdbox").before($("wstatus"));       // its message in the design step
  designLayer.clearLayers();
  const geo = {}; (layoutData && layoutData.conduits || []).forEach(c => geo[c.label] = c); withCuts(r, geo); drawCuts(r, designLayer);
  const dwhy = {}; for (const z of (wZoning && wZoning.zones) || []) dwhy[z.name] = whyZone(z);   // the OZ reason on its pipes
  const sizes = Object.keys(r.summary.length_by_size);
  const order = sizes.slice().sort((a, b) => (parseFloat(a.replace(/\D+/g, " ")) || 0) - (parseFloat(b.replace(/\D+/g, " ")) || 0));
  const scol = {}; order.forEach((n, i) => scol[n] = WSIZE[Math.min(i, WSIZE.length - 1)]);
  for (const p of r.pipes) {
    const c = geo[p.label]; if (!c) continue;
    const w = p.nominal >= 300 ? 6 : p.nominal >= 200 ? 5 : 3.5;
    pickable(L.polyline(c.pts, p.closed ? { color: "#9e9e9e", weight: 2, dashArray: "4 4", renderer: netRenderer }
      : { color: scol[p.size] || "#555", weight: w, opacity: .95, renderer: netRenderer }),
      `<b>${esc(p.label)}</b> ${esc(p.from)} - ${esc(p.to)}<br>${p.closed ? tr("बंद (OZ / DMA सीमा)", "closed (OZ / DMA boundary)") + "<br>" : ""}` +
      `${esc(p.size || "-")} (${tr("अंदरूनी", "internal")} ${fmt(p.id_mm, 1)} mm), ${fmt(p.length, 1)} m<br>` +
      `${tr("peak बहाव", "peak flow")} ${fmt(Math.abs(p.flow), 2)} L/s, v ${fmt(p.v, 2)} m/s<br>head loss ${fmt(p.hl_km, 2)} m/km<br>OZ ${esc(p.oz || "-")}, ${esc(p.dma || "-")}` +
      (dwhy[p.oz] ? `<div class="why-line">${esc(dwhy[p.oz])}</div>` : ""), true).addTo(designLayer);
  }
  const pcol = p => p === null ? "#9e9e9e" : p < 17 ? "#d32f2f" : p <= 21 ? "#2e7d32" : p <= 30 ? "#1565c0" : "#6a1b9a";
  for (const n of r.nodes)
    pickable(L.circleMarker(n.latlng, { radius: 4, color: "#263238", weight: 1, fillColor: pcol(n.p), fillOpacity: 1, renderer: netRenderer }),
      `<b>${esc(n.label)}</b><br>GL ${fmt(n.gl, 2)} m, HGL ${fmt(n.head, 2)} m<br><b>residual head ${fmt(n.p, 2)} m</b><br>` +
      `${tr("peak माँग", "peak demand")} ${fmt(n.q, 3)} L/s<br>${esc(n.dma || n.oz || "-")}`, false).addTo(designLayer);
  for (const p of r.unsupplied_pts || [])
    L.circleMarker(p, { radius: 5, color: "#616161", weight: 2, fill: false, dashArray: "2 2", renderer: netRenderer })
      .bindTooltip(tr("किसी OHT से जुड़ा नहीं (सड़क का अलग टुकड़ा)", "joined to no OHT (a separate road piece)")).addTo(designLayer);
  for (const o of r.outlets) {
    const om = L.marker(o.latlng, { icon: icon("oht", false, { name: o.name, existing: o.existing ? "1" : "0" }) })
      .on("click", ev => { let t = null; drawn.eachLayer(l => { if (l.kind === "oht" && l.props.name === o.name) t = l; });
                           if (t) { L.DomEvent.stopPropagation(ev); select(t); } });
    hoverCard(om, () => { const l = drawnBy("oht", o.name);
      return { html: ohtCardHtml(o.name, !!l, l && l.props) + (l ? hcStale() :
               `<div class="hint">${tr("Move: OHT (और उसके OZ के सुझाए tube wells) आपके हो जाएँगे, नक्शे पर।", "Move: the OHT (and its OZ's suggested tube wells) become yours, on the map.")}</div>`),
               acts: l ? [["✕", tr("नक्शे से हटाएँ", "remove from the map"), () => hcDelete(l, [om]), "del"],
                          ["✥ move", tr("खींचकर नई जगह", "drag to a new place"), () => { om.remove(); hcMove(l); }]]
                       : [["✕", tr("हटाएँ - अगली Zoning में यह OHT नहीं", "remove - no OHT here in the next zoning"), () => sugOhtOff(o.name, o.latlng, [om]), "del"],
                          ["✥ move", tr("आपकी बनाकर खींचें", "make it yours and drag it"), () => hcMove(convertOht(o.name, o.latlng, [om]))]] }; });
    om.addTo(designLayer);                         // its data in the hover card
  }
  const otab = `<table class="wz"><tr><th>OHT</th><th>${tr("क्षमता KL", "capacity KL")}</th><th>staging m</th><th>VFD</th><th>CWR KL</th><th>${tr("आबादी", "population")}</th><th>DMA</th><th>${tr("न्यूनतम दबाव", "lowest head")}</th></tr>` +
    r.outlets.map(o => `<tr><td>${esc(o.name)} <span class="hint">${o.proposed ? tr("प्रस्तावित", "proposed") : o.existing ? tr("मौजूदा", "existing") : tr("नई", "new")}</span></td>` +
      `<td>${o.existing ? `${fmt(o.capacity_kl)}${o.required_kl > o.capacity_kl ? " ⚠" : ""}` : `<b>${fmt(o.required_kl)}</b>`}</td>` +
      `<td>${o.staging_auto ? `<b>${fmt(o.staging_m, 1)}</b>` : fmt(o.staging_m, 1)}${o.short_m ? ` <span style="color:#c62828">+${o.short_m}</span>` : ""}</td>` +
      `<td>${o.vfd_head_m ? `<b style="color:#6a1b9a">+${fmt(o.vfd_head_m, 1)} m</b> <span class="hint">${fmt(o.vfd_kw, 1)} kW</span>` : "-"}</td>` +
      `<td>${o.cwr_kl ? fmt(o.cwr_kl) : "-"}</td><td>${fmt(o.population)}</td><td>${o.dmas ?? "-"}</td><td>${fmt(o.lowest_p, 2)}</td></tr>`).join("") + `</table>` +
    `<div class="hint">${tr("मोटे अंक = आवश्यक (नई टंकी की क्षमता OZ की माँग (fire के बिना) का 33% या mass balance, जो अधिक हो, + fire का 1/3; staging design से - 17 m के लिए जितनी चाहिए, 0.5 m तक); लाल +x = पुरानी टंकी की staging इतनी कम; VFD = पुरानी टंकी के outlet पर pump का head (CPHEEO Table 2.7 S.No.10)", "bold = required (new tank capacity 33% of the OZ demand without fire or mass balance, the larger, + 1/3 of the fire; staging from the design - what 17 m needs, to 0.5 m); red +x = the existing tank's staging is this much too low; VFD = head of the pump at the existing tank's outlet (CPHEEO Table 2.7 S.No.10)")}</div>`;
  const s = r.summary;
  $("wdbox").innerHTML = otab + `<div class="box"><b>${tr("Design (PFR)", "Design (PFR)")}</b>: ${tr("आबादी", "population")} ${fmt(s.population)}, ` +
    `${tr("औसत माँग (fire के बिना)", "average demand (without fire)")} ${fmt(s.demand_avg_lps, 1)} L/s × ${s.peak_factor}; residual head ${fmt(s.min_pressure, 2)} - ${fmt(s.max_pressure, 2)} m` +
    (s.missing_head_m ? `<div class="warn">${tr(`OHT की ऊँचाई कम: सबसे कमज़ोर node को ${s.missing_head_m} m और चाहिए (staging बढ़ाएँ या booster)`, `OHT too low: the weakest node needs ${s.missing_head_m} m more (higher staging or a booster)`)}</div>` : "") +
    r.checks.map(c => `<div class="wflag ${c.ok ? (c.warn ? "alert" : "") : "error"}" title="${esc(c.ref)}">${c.ok ? (c.warn ? "⚠" : c.note ? "ℹ" : "✔") : "✖"} ${esc(checkText(c))}</div>`).join("") +
    (r.files && r.files.excel ? `<div class="hint">Excel: ${esc(r.files.excel.split(/[\\/]/).pop())}</div>` : "") +
    (r.files && r.files.dpr ? `<div class="hint">DPR Excel: ${esc(r.files.dpr.split(/[\\/]/).pop())}</div>` : "") + `</div>` +
    prvBox(r) + rmBox(r) + waterStageBox(r.stages) + loadCaseBox(r) + dayBox(r.day);
  drawPrvs(r);
  drawRising(r);
  if ($("wtwplace")) $("wtwplace").onclick = () => {     // the suggested sites become tube wells of the drawing
    let n = countOf("tw");
    for (const t of (r.rising && r.rising.tws) || []) if (!t.placed && !t.auto && t.latlng)   // a proposed OHT's: with it
      addFeature(L.marker(t.latlng), "tw", { name: `TW ${++n}`, discharge_lpm: "" });
    for (const t of (r.rising && r.rising.needed) || [])                                     // the shortfall's sites
      addFeature(L.marker(t.latlng), "tw", { name: `TW ${++n}`, discharge_lpm: "" });
    changed();
    $("wtwplace").replaceWith(Object.assign(document.createElement("div"), { className: "hint", style: "color:var(--ok)",
      textContent: "✔ " + tr("सुझाए tube wells नक्शे पर रख दिए - उन्हें उपलब्ध ज़मीन पर खिसकाएँ, फिर Design दोबारा चलाएँ।",
                             "The suggested tube wells are on the map - move them to available land, then run the Design again.") }));
  };
  if ($("wprvplace")) $("wprvplace").onclick = () => {   // the suggestions become PRVs of the drawing (by itself)
    let n = countOf("prv");
    for (const g of r.prv_suggest || []) if (g.latlng)
      addFeature(L.marker(g.latlng), "prv", { name: `PRV ${++n}`, setting_m: "" });
    changed();
    $("wprvplace").replaceWith(Object.assign(document.createElement("div"), { className: "hint", style: "color:var(--ok)",
      textContent: "✔ " + tr("सुझाए PRV नक्शे पर रख दिए - Design दोबारा चलाएँ (PRV पर click करके setting भर सकते हैं)।",
                             "The suggested PRVs are on the map - run the Design again (click a PRV to give its setting).") }));
  };
  WLEG.design = order.map(n => `<div><span class="k" style="background:${scol[n]};height:5px"></span>${esc(n)} - ${fmt(s.length_by_size[n])} m</div>`).join("") +
    `<div style="margin-top:4px">${[["#d32f2f", "< 17 m"], ["#2e7d32", "17 - 21 m"], ["#1565c0", "21 - 30 m"], ["#6a1b9a", "> 30 m"]]
      .map(([c, t]) => `<span class="k" style="background:${c};border-radius:50%;width:9px;height:9px"></span>${t}`).join(" &nbsp; ")}</div>` +
    `<div class="hint">${tr("बिंदु = node का residual head; धूसर टूटी रेखा = बंद pipe; तीर = बहाव की दिशा", "dot = residual head of the node; grey dashed = closed pipe; arrow = flow direction")}</div>`;
  $("wstatus").className = "status " + (r.stale ? "err" : r.checks.every(c => c.ok) ? "ok" : "err");
  $("wstatus").textContent = (note ? note + " - " : "") + (r.checks.every(c => c.ok) ? tr("Design सब जाँचों पर ठीक", "Design passes every check")
    : tr("Design: कुछ जाँचें पूरी नहीं", "Design: some checks not met"));
  $("viewseg").hidden = false;
  setView("design");
  tblAfterDesign(r);
}

async function restoreWater(name) {
  const r = await api("/api/water_last?name=" + encodeURIComponent(name));
  if (!r.ok || !r.network_saved) return;
  const q = (r.zoning || r.design || {}).req || {};
  if (q.pop_factor) $("wpopf").value = q.pop_factor;
  $("wfloat").value = q.floating_pct ?? 10;
  $("wloadby").value = q.load_by || "length";            // a run from before 16-Nov-2026: by the pipe length
  const qd = (r.design && r.design.req) || q;             // the design's own: the load cases and the 24 h run
  $("wsim").checked = qd.simulate === undefined ? true : qd.simulate === "1";
  $("wfirelps").value = qd.fire_lps ?? ""; $("wfiremin").value = qd.fire_min_m ?? "";
  const pk = String(qd.peak || "urban");                  // the peak factor: urban / rural / a number
  $("wpeak").value = pk === "urban" || pk === "rural" ? pk : "given";
  if ($("wpeak").value === "given") $("wpeakv").value = pk;
  $("wpeakv").hidden = $("wpeak").value !== "given";             // a run from before 11-Nov-2026: the 10 % it was made with
  if (q.persons_per_connection) $("wppc").value = q.persons_per_connection;
  if (q.oht_inflow) $("winflow").value = q.oht_inflow;
  const qs = q.tw_standby || (r.design && r.design.req && r.design.req.tw_standby) || {};   // a zoning from before it: the design's
  $("wsbon").checked = !!qs.on;
  SB = Array.isArray(qs.rows) && qs.rows.length ? qs.rows.map(r => [+r[0], +r[1]]) : SB_DEF.map(r => r.slice());
  sbRender();
  const qg = q.sug || (r.design && r.design.req && r.design.req.sug) || {};
  SUG = { oht_off: Array.isArray(qg.oht_off) ? qg.oht_off : [], oht_off_all: !!qg.oht_off_all,
          tw_off: Array.isArray(qg.tw_off) ? qg.tw_off : [], tw_off_all: !!qg.tw_off_all };
  sugRender();
  if (q.ward_table && q.ward_table.rows) {
    const g = JSON.parse(JSON.stringify(WARD_GROWTH_DEF));
    const qg = charKeys(q.ward_table.growth), qd = q.ward_table.dens ? charKeys(q.ward_table.dens) : null, qc = charKeys(q.ward_table.city);   // the old names as the new (9-Nov-2026)
    for (const k in g) if (Array.isArray(qg[k]) && qg[k].length === 3) g[k] = qg[k].map(Number);
    const dn = Object.assign({}, WARD_DENS_DEF);
    for (const k in dn) if (qd && qd[k] !== undefined && +qd[k] >= 0) dn[k] = +qd[k];
    // a saved table from before the density rule (7-Nov-2026): its characters were chosen by the user
    const old = !q.ward_table.dens;
    const cy = Object.assign({}, WARD_TOWN_DEF);
    for (const k in cy) if (qc[k] !== undefined && qc[k] !== "" && +qc[k] >= 0) cy[k] = +qc[k];
    const st = q.ward_table.sat === undefined ? WARD_SAT_DEF : q.ward_table.sat === "" || q.ward_table.sat === null ? "" : +q.ward_table.sat;
    WT = { year: q.ward_table.year || 2025, rows: q.ward_table.rows.map(x => Object.assign({}, x, x.char ? { char: charName(x.char) } : {}, old && x.char ? { charby: "user" } : {})), growth: g, dens: dn, city: cy, sat: st,
           citylist: q.ward_table.citylist || "" }; $("wtn").value = WT.rows.length; $("wtyear").value = WT.year; wtRender();
    await cwList(WT.citylist); await cwLoad(WT.citylist, false); }      // the town's list: for the search and the sums
  if (q.near_m) $("wnearm").value = q.near_m;
  izRestore(q.intze);
  $("wprv").checked = !!((r.design || {}).req || {}).use_prv; prvTools();
  if (q.pop_total) $("poptot").value = q.pop_total;
  stageRestore((r.design || r.zoning || {}).req || {});      // the stages belong to the design
  const pj = ((r.design || r.zoning || {}).req || {}).projection;   // a projection: its base population and census
  if (pj) { $("popb").value = pj.base_pop; pjcSet(pj.census); PJ_METHOD = pj.method || ""; await pjRun(true); }
  if (r.zoning) renderWZoning(r.zoning, r.zoning.stale ? tr(`पुरानी zoning (${r.zoning.time}) - layout बदला, फिर चलाएँ`, `old zoning (${r.zoning.time}) - layout changed, run again`) : tr(`पिछली zoning (${r.zoning.time})`, `last zoning (${r.zoning.time})`));
  if (r.design) renderWDesign(r.design, r.design.stale ? tr(`पुराना design (${r.design.time})`, `old design (${r.design.time})`) : tr(`पिछला design (${r.design.time})`, `last design (${r.design.time})`));
}

async function askLoops(r) {
  let any = false;
  for (const x of (r && r.loop_ask) || []) {
    let layer = null; drawn.eachLayer(l => { if (l.kind === "zone_loop" && l.props.name === x.name) layer = layer || l; });
    if (!layer) continue;
    const why = x.over
      ? tr(`आबादी ${fmt(x.population)} (${fmt(x.connections)} कनेक्शन) - एक OZ की सीमा ${fmt(x.max_population)} आबादी / 10,000 कनेक्शन (CPHEEO Table 2.7 S.No.20, p180) से अधिक।`,
           `population ${fmt(x.population)} (${fmt(x.connections)} connections) - above the limit of one OZ, ${fmt(x.max_population)} / 10,000 connections (CPHEEO Table 2.7 S.No.20, p180).`)
      : tr(`आबादी ${fmt(x.population)} (${fmt(x.connections)} कनेक्शन) - एक DMA (${fmt(x.min_connections)} कनेक्शन, CPHEEO Table 2.7 S.No.21, p181) से भी कम।`,
           `population ${fmt(x.population)} (${fmt(x.connections)} connections) - below even one DMA (${fmt(x.min_connections)} connections, CPHEEO Table 2.7 S.No.21, p181).`);
    const v = await choose(tr(`Zone लूप "${x.name}": सीमा पार`, `Zone loop "${x.name}": beyond the limits`),
      why + "\n\n" + tr(`अभी यह एक OZ (${x.zones.join(", ") || "-"}) के रूप में रखा है। क्या करें? (जवाब लूप के साथ रहेगा, बाद में लूप चुनकर बदल सकते हैं)`,
                         `For now it is kept as one OZ (${x.zones.join(", ") || "-"}). What to do? (the answer stays with the loop; change it later by selecting the loop)`),
      LOOP_MODES.slice(1).map(m => [m[0], EN ? m[2] : m[1]]));
    if (!v) continue;
    layer.props.on_limit = v; any = true;
  }
  if (any) { changed(); if (selected) showProps(); $("wzrun").click(); }
}
$("wzrun").onclick = () => longTask(tr("पेयजल zoning (OZ / DMA)", "Water zoning (OZ / DMA)"), async () => {
  $("wzbox").before($("wstatus"));
  const r = await api("/api/water_zoning", wInputs());
  if (!r.ok) { $("wstatus").className = "status err"; $("wstatus").textContent = r.log || "error"; return; }
  wDesign = null; tblAfterDesign(null); designLayer.clearLayers(); $("wdbox").innerHTML = "";
  renderWZoning(r);
}, () => /err/.test($("wstatus").className) && !wZoning ? [tr("Zoning नहीं हुई", "Zoning failed"), $("wstatus").textContent, "err"]
  : [tr("Zoning हो गई", "Zoning done"), $("wstatus").textContent + (wZoning && wZoning.flags.length ? "\n\n" + wZoning.flags.map(f => "• " + flagText(f)).join("\n") : ""),
     wZoning && wZoning.flags.some(f => f.level === "error") ? "warn" : "ok"]).then(() => askLoops(wZoning));
$("wdrun").onclick = () => longTask(tr("पेयजल design (मौजूदा zoning पर)", "Water design (with the current zoning)"), async () => {
  $("wdbox").before($("wstatus"));
  const r = await api("/api/water_design", wInputs());
  if (!r.ok) { $("wstatus").className = "status err"; $("wstatus").textContent = r.log || "error"; wDesign = null; tblAfterDesign(null); return; }
  const z = await api("/api/water_last?name=" + encodeURIComponent($("pname").value));
  if (z.ok && z.zoning) { wZoning = z.zoning; renderWZoning(z.zoning); }
  renderWDesign(r);
  if ($("izbox").open) izList();               // the Intze tanks of this design (10-Nov-2026)
}, () => !wDesign ? [tr("Design नहीं हुआ", "Design failed"), $("wstatus").textContent, "err"]
  : [tr("Design हो गया", "Design done"), $("wstatus").textContent + "\n" + wDesign.checks.map(c => (c.ok ? "✔ " : "✖ ") + checkText(c)).join("\n"),
     wDesign.checks.every(c => c.ok) ? "ok" : "warn"]);

// DXF (user requests 21-Oct-2026, 14-Nov-2026): each button its own drawing, never the two named together -
// beside "Zoning": the zoning alone; beside "Design": the design made with the current zoning
function exportDxf(what) {
  let r = null;
  const label = what === "zoning" ? tr("DXF export (zoning)", "DXF export (zoning)")
    : tr("DXF export (design, मौजूदा zoning पर)", "DXF export (design with the current zoning)");
  longTask(label, async () => {
    r = await api("/api/water_export", { name: $("pname").value, what });
  }, () => !r || !r.ok ? [tr("Export नहीं हुआ", "Export failed"), (r && r.log) || "error", "err"]
    : [tr("DXF तैयार", "DXF ready"), `folder: ${r.folder}\n\nAutoCAD : ${r.path.split(/[\\/]/).pop()}  (${tr("drawing वाले coordinates", "the drawing's coordinates")})\n` +
       (what === "zoning" ? tr("Zoning की drawing: OZ / DMA सीमाएँ, बंद valves, DMA inlets, OHT और network। Design की drawing \"Design\" के पास वाले बटन से।",
                               "The zoning's drawing: OZ / DMA boundaries, closed valves, DMA inlets, OHTs and the network. The design's drawing: the button beside \"Design\".")
                          : tr("Design की drawing, मौजूदा zoning पर: pipe size, लंबाई, flow, GL / HGL / residual head, और zoning की सीमाएँ।",
                               "The design's drawing, with the current zoning: pipe sizes, lengths, flow, GL / HGL / residual head, and the zoning's boundaries.")) +
       `\n\n${r.counts.oz} OZ (W_OZ_n), ${r.counts.dma} DMA (W_DMA_BOUNDARY), ${r.counts.valves} ${tr("बंद valves", "closed valves")} (W_VALVE), ` +
       `${r.counts.inlets} DMA inlets (W_DMA_INLET), ${r.counts.ohts} OHT (W_OHT)${r.counts.prvs ? `, ${r.counts.prvs} PRV (W_PRV)` : ""}\n${r.counts.pipes} pipes (W_PIPE${r.counts.design ? ", W_PIPE_TEXT, W_FLOW_ARROW" : ""}), ` +
       `${r.counts.junctions} junctions (W_JUNCTION, W_JUNCTION_TEXT${r.counts.low ? `; ${r.counts.low} ${tr("17 m से कम", "below 17 m")}: W_JUNCTION_LOW` : ""})` +
       `\n${tr("Text की ऊँचाई", "Text height")} ${r.counts.text_height} (${r.counts.text_height_from})`, "ok"]);
}
$("wexportz").onclick = () => exportDxf("zoning");
$("wexport").onclick = () => exportDxf("design");
$("wexportdpr").onclick = () => {                 // the DPR of the last design, opened in Excel (15-Nov-2026)
  let r = null;
  longTask(tr("DPR (xlsx)", "DPR (xlsx)"), async () => { r = await api("/api/water_dpr", { name: $("pname").value }); },
    () => !r || !r.ok ? [tr("DPR नहीं मिली", "No DPR"), (r && r.log) || "error", "err"]
      : [tr("DPR तैयार", "DPR ready"), `folder: ${r.folder}\n\nExcel : ${r.path.split(/[\\/]/).pop()}\n` +
         tr(`Design ${r.time || ""} की DPR` + (r.opened ? " - Excel में खुल रही है।" : " - Excel नहीं खुला, folder से खोलें।"),
            `The DPR of the design of ${r.time || ""}` + (r.opened ? " - opening in Excel." : " - Excel did not open; open it from the folder.")) +
         (r.stale ? "\n\n" + tr("⚠ Network उस Design के बाद बदला है - नई DPR के लिए Design दोबारा चलाएँ।", "⚠ The network changed after that design - run the Design again for a new DPR.") : ""),
         r.stale ? "warn" : "ok"]);
};
