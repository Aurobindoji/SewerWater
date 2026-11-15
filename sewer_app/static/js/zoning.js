// The sewer map page (map.html), part 6 of 9: zoning and design: the options, the zones, the design and its results.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---------------------------------------------------------------- zoning and design
const zoneLayer = new L.FeatureGroup(), designLayer = new L.FeatureGroup();
// red crosses of a DXF network (manholes on top of each other, not joined): in every view - layout, zones and design
const warnLayer = new L.FeatureGroup();
// zone / design lines use netRenderer, the canvas of the network: a second canvas would lie over it and take every
// click (the manholes could not be selected any more)
let layoutData = null, zoningData = null, curOption = null, designData = null;
const ZCOL = ["#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2", "#bcbd22",
  "#7f7f7f", "#393b79", "#637939", "#843c39", "#7b4173", "#3182bd", "#e6550d"];
// stage-wise check (CPHEEO Table 2.1 p2-9): base year and the populations of the
// base year and +15 years; the design population is +30 years. Empty populations = no stage check.
// user decision 22-Oct-2026: base-year population + census -> the +15 / +30 years population and floating (server)
function stageInputs() { return { base_year: $("byear").value, pop_initial: $("popb").value, census: $("census").value, pop_method: $("popmeth").value, floating_pct: $("popfl").value }; }
function stageRestore(q) {
  if (q.base_year) $("byear").value = q.base_year;
  $("popfl").value = q.floating_pct ?? 10;              // a run from before 11-Nov-2026: the 10 % it was made with
  $("popb").value = q.pop_initial ?? ""; $("census").value = q.census ?? ""; $("popmeth").value = q.pop_method || "geometrical";
}
function showForecast(r) { if (r && r.forecast) { $("popfc").textContent = r.forecast; $("popfc").className = "hint ok"; } }
const STAGE_NAME = { init: () => tr("आधार वर्ष", "base year"), mid: () => tr("+15 वर्ष", "+15 years"), ult: () => tr("+30 वर्ष", "+30 years") };
const stageHead = st => `${STAGE_NAME[st.stage]()}${st.year ? " " + st.year : ""}`;
// the column header of a stage: its year and, in grey, what is designed for it (CPHEEO Table 2.1)
const stageCol = (st, mid, ult) => `<th>${esc(stageHead(st))}${st.stage === "mid" ? `<br><span class="hint">${mid}</span>`
  : st.stage === "ult" ? `<br><span class="hint">${ult}</span>` : ""}</th>`;
function sewerStageBox(stages) {
  if (!stages || !stages.length) return "";
  const role = o => { const x = stages[0].outfalls.find(y => y.outfall === o) || {};
    return x.role === "pumping station" ? "PS" : (x.role || "").startsWith("STP") ? "STP" : ""; };
  const t1 = `<table class="wz"><tr><th>Stage</th><th>${tr("आबादी", "population")}</th><th>${tr("न्यूनतम v", "lowest v")}</th>` +
    `<th>${tr("v सीमा", "v limit")}</th><th>${tr("सीमा से कम", "below it")}</th><th>${tr("अधिकतम d/D", "highest d/D")}</th></tr>` +
    stages.map(st => `<tr title="${esc(st.v_rule)}"><td>${esc(stageHead(st))}${st.stage === "ult" ? ` <span class="hint">design</span>` : ""}</td><td>${fmt(st.pop)}</td><td>${fmt(st.v_min, 2)}</td>` +
      `<td>${st.stage === "mid" ? `<span class="hint">(${fmt(st.v_limit, 1)})</span>` : fmt(st.v_limit, 1)}</td>` +
      `<td>${st.slow_n ? `<b${st.stage === "mid" ? "" : ' style="color:#c62828"'}>${st.slow_n}</b> <span class="hint">${fmt(st.slow_m / 1000, 2)} km</span>` : "0"}</td>` +
      `<td>${fmt(st.dd_max, 2)}</td></tr>`).join("") + `</table>`;
  const t2 = `<table class="wz"><tr><th>Outfall</th>` +
    stages.map(st => stageCol(st, "pumps, STP", "sewers")).join("") + `</tr>` +
    stages[0].outfalls.map(({ outfall: o }) => `<tr><td>${esc(o)} <span class="hint">${role(o)}</span></td>` +
      stages.map(st => { const x = st.outfalls.find(y => y.outfall === o) || {};
        return `<td>${fmt(x.peak_lps, 1)} L/s<br><span class="hint">${tr("औसत", "avg")} ${fmt(x.avg_mld, 2)} MLD</span></td>`; }).join("") +
      `</tr>`).join("") + `</table>`;
  return `<div class="box"><b>${tr("Stage-wise जाँच", "Stage-wise check")}</b>` + t1 +
    `<div class="hint">${tr("v सीमा: आधार वर्ष के initial peak पर 0.6 m/s, +30 वर्ष (ultimate) peak पर 0.8 m/s (CPHEEO Table 3.9, p3-26); +15 वर्ष के लिए manual में सीमा नहीं, 0.6 सिर्फ़ सूचना के लिए। Pipe तालिका के 'जाँच' column में: v (base year) < 0.6 m/s।",
      "v limit: 0.6 m/s at the base-year initial peak, 0.8 m/s at the +30 years (ultimate) peak (CPHEEO Table 3.9, p3-26); the manual gives none for +15 years, 0.6 for information only. Pipe table 'Checks': v (base year) < 0.6 m/s.")}</div>` + t2 +
    `<div class="hint">${tr("हर outfall पर peak flow (infiltration सहित)। Pumping machinery और STP +15 वर्ष के लिए, sewers और pumping main +30 वर्ष के लिए (CPHEEO Table 2.1, p2-9)। दूसरे zone से pump होकर आया flow इसमें नहीं है।",
      "Peak flow (with infiltration) at every outfall. Pumping machinery and STP for +15 years, sewers and pumping mains for +30 years (CPHEEO Table 2.1, p2-9). Flow pumped in from another zone is not included.")}</div></div>`;
}
const fmt = (x, d = 0) => x === null || x === undefined ? "-" : Number(x).toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d });

const DCOL = d => d <= 200 ? "#2b83ba" : d <= 250 ? "#5fb4a8" : d <= 300 ? "#abdda4" : d <= 400 ? "#e6c84f"
  : d <= 600 ? "#fdae61" : d <= 900 ? "#f46d43" : "#a50026";
const lakh2 = v => v === null || v === undefined ? "-" :          // table: always 2 decimals, the columns line up
  Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const lakh = v => v === null || v === undefined ? "-" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });

function setView(v) {
  curView = v; map.closePopup(); hiLayer.clearLayers();
  for (const g of [result, zoneLayer, designLayer, netLayer, issueLayer]) map.removeLayer(g);
  if (v === "layout" && mode === "dxf") { netLayer.addTo(map); issueLayer.addTo(map); }
  else ({ layout: result, zones: zoneLayer, design: designLayer })[v].addTo(map);
  dimRoads = v !== "layout";
  drawn.eachLayer(l => { if (l.kind === "road" && l !== selected) l.setStyle(style("road")); });
  document.querySelectorAll("#viewseg button").forEach(b => b.classList.toggle("on", b.dataset.v === v));
  $("showres").checked = v === "layout";
  legend(v);
  drawOverlay();
  setTimeout(drawTexts, 0);                  // the drawing's texts: layout view only (after the page's script has run)
}
document.querySelectorAll("#viewseg button").forEach(b => b.onclick = () => {
  if (mode === "dxf" && b.dataset.v !== "layout") { pick = null; $("nhint").textContent = HINT[tool] + " (औज़ार केवल Layout view में - Zones / Design में manholes नहीं दिखते)"; }
  if (b.dataset.v === "zones" && !zoningData) return;
  if (b.dataset.v === "design" && !designData) return;
  setView(b.dataset.v);
});
function legend(v) {
  const el = $("legend");
  if (v === "zones" && curOption) {
    const noStp = !curOption.outlets.some(o => o.role === "STP (gravity)");
    el.innerHTML = (noStp ? `<div class="hint">STP manhole नहीं दिया: लागत में सबसे बड़े flow वाला outlet STP तक gravity से माना गया, बाकी pumping stations - ऊपर "STP manhole" भरें।</div>` : "") +
      `<div class="hint">हर zone की पहचान उसका outlet manhole है (जहाँ उसका sewage इकट्ठा होकर PS / STP जाता है; Excel में यही नाम) - नंबर केवल क्रम हैं।</div>` +
      (() => { const zn = zoneNames(curOption);
        const row = (o, sub) => `<div${sub ? ' style="margin-left:22px"' : ""}><span class="k" style="background:${ZCOL[zn.mains.indexOf(zn.parent[o.manhole]) % ZCOL.length]};${sub ? "height:2px" : ""}"></span>` +
          `<b>${sub ? "sub-zone " : "ज़ोन "}${zn.name[o.manhole]}</b> - outlet ${esc(o.manhole)} (${o.role === "STP (gravity)" ? "STP" : noStp ? "outlet" : "pumping station"}${sub && o.manhole !== zn.parent[o.manhole] ? ", गहराई के लिए" : ""}), ${o.manholes} MH, ` +
          `${lakh(o.flow_lps)} L/s` + (o.area_ha ? `, ${o.area_ha} ha` : "") + `</div>`;
        return zn.mains.map(m => {
          const mo = curOption.outlets.find(x => x.manhole === m);
          const all = curOption.outlets.filter(x => zn.parent[x.manhole] === m);
          if (all.length === 1 && mo) return row(mo, false);
          const tot = all.reduce((a, x) => ({ mh: a.mh + (x.manholes || 0), ha: a.ha + (x.area_ha || 0) }), { mh: 0, ha: 0 });
          const subs = all.filter(x => x.manhole !== m).concat(mo ? [mo] : []);
          return `<div><span class="k" style="background:${ZCOL[zn.mains.indexOf(m) % ZCOL.length]}"></span><b>ज़ोन ${zn.num[m]}</b> - ` +
            `outlet ${esc(m)} (${mo && mo.role === "STP (gravity)" ? "STP" : "pumping station"}); कुल ${tot.mh} MH, ${tot.ha.toFixed(2)} ha, ${all.length} sub-zones</div>` +
            subs.map(x => row(x, true)).join("");
        }).join(""); })() +
      `<div class="hint">${tr("गाढ़ी रंगीन सीमा = ज़मीन की ढलान वाला ज़ोन", "thick coloured boundary = zone from the ground slope")}</div>` +
      `<div><span class="k" style="background:repeating-linear-gradient(90deg,#000 0 7px,#fff 7px 14px);height:4px;outline:1px solid #000"></span>` +
      `${tr("sub-zone की सीमा (ज़ोन के भीतर गहराई के लिए, अपने PS के साथ)", "sub-zone boundary (inside a zone, for depth, with its own PS)")}</div>` +
      `<div><span class="k" style="background:#000;height:2px"></span>कटे sewers (एक सिरा अलग)</div>`;
  } else if (v === "design" && designData) {
    el.innerHTML = `<div class="hint"><b>रंग = pipe का diameter</b> (zones नहीं - zones के लिए ऊपर "Zones" दबाएँ); PS / STP = zones के outlets।</div>` +
      designData.summary.by_diameter.map(([D, L_]) =>
      `<div><span class="k" style="background:${DCOL(D)};height:5px"></span>${D} mm - ${Number(L_).toLocaleString("en-IN")} m</div>`).join("") +
      (designData.sewers.some(d => d.cut) ? `<div><span class="k" style="border:2.5px solid #e65100;border-radius:50%;width:8px;height:8px;background:#fff3e0"></span>` +
        `कटा loop का शुरुआती manhole (...-C1): अलग, पास वाले manhole से जुड़ा नहीं</div>` : "");
  } else el.innerHTML = "";
}

async function loadCatalogs() {
  try {
    const r = await api("/api/catalogs");
    if (r.max_depth) $("maxdepth").value = r.max_depth;          // the project decision of design_criteria.json
    $("catalog").innerHTML = r.catalogs.map(c => `<option title="${esc(c.source)}">${esc(c.name)}</option>`).join("");
    const setJ = () => { const c = r.catalogs.find(x => x.name === $("catalog").value);
      $("joint").innerHTML = (c && c.joints.length ? c.joints : ["ss"]).map(j => `<option${j === "ss" ? " selected" : ""}>${j}</option>`).join(""); };
    $("catalog").onchange = setJ; setJ();
  } catch (e) { }
}
function zmodeChanged() {
  const given = $("zmode").value === "given";
  $("maxzrow").hidden = given; $("maxzhint").hidden = given;
  // only the given outfalls: no pumping station is added for depth - the depth only marks (⚠) and checks
  $("maxdepthlab").textContent = given ? tr("चेतावनी की गहराई (m)", "Warning depth (m)") : tr("अधिकतम गहराई (m)", "Maximum depth (m)");
  $("maxdepthlab").title = given
    ? tr("इस mode में pumping station नहीं जुड़ता - इससे गहरे sewer / manhole सिर्फ़ ⚠ और जाँच (तालिका, report) में दिखते हैं; CPHEEO 6 m, project निर्णय 10 m",
         "in this mode no pumping station is added - sewers / manholes deeper than this are only marked ⚠ and in the checks (tables, report); CPHEEO 6 m, project decision 10 m")
    : tr("इससे गहरे sewer से पहले pumping station (sub-zone) बनता है; CPHEEO 6 m, project निर्णय 10 m",
         "a pumping station (sub-zone) is made before a sewer gets deeper than this; CPHEEO 6 m, project decision 10 m");
  // two buttons (user request 20-Oct-2026): the zoning, then the design of the chosen option (given outfalls: GIVEN)
  $("zrun").textContent = given ? tr("Zoning (केवल दिए outfalls)", "Zoning (given outfalls only)")
                                : tr("Zoning options निकालें", "Work out zoning options");
  $("zrun").title = given ? tr("दिए outfalls / STP पर zoning (एक option: GIVEN) - फिर \"Design\"; network बदलने के बाद फिर से Zoning",
                               "zoning on the given outfalls / STP (one option: GIVEN) - then \"Design\"; zoning again after changing the network")
                          : tr("ज़मीन की ढलान से zoning के options; फिर option चुनकर \"Design\"", "zoning options from the ground slope; then choose an option and \"Design\"");
}
$("zmode").onchange = () => { zmodeChanged(); designButton(); };
$("drun").onclick = () => { if (zoningData && curOption && !$("drun").disabled) runDesign(curOption); };
// the Design button: the option shown on the map, of a zoning made with the design method now chosen
function designButton() {
  const o = curOption, same = zoningData && (zoningData._mode || "auto") === $("zmode").value;
  $("drun").disabled = !o || !same;
  // like the Zoning button: the given-outfalls mode says so, the other names the chosen option
  const given = $("zmode").value === "given";
  $("drun").textContent = given ? tr("Design (केवल दिए outfalls)", "Design (given outfalls only)")
                                : o && same ? `Design: ${o.option}` : "Design";
  $("drun").title = !o ? tr("पहले Zoning करें", "run the zoning first")
    : !same ? tr("Design का तरीका बदला - पहले Zoning फिर से करें", "the design method changed - run the zoning again first")
    : given ? tr("चुने हुए \"Design का तरीका\" से network का design करता है", "Designs the network from the chosen Design Method")
    : tr(`चुने हुए "Design का तरीका" से network का design करता है - option ${o.option} (दूसरा option: तालिका में उसकी पंक्ति पर click)`,
         `Designs the network from the chosen Design Method - option ${o.option} (another option: click its row in the table)`);
}
// the STP drawn on the map (also after the layout was made): its nearest manhole of the layout goes into 'STP
// manhole' unless the user typed one there
function stpFromMap() {
  let kml = true; try { kml = mode === "kml"; } catch (e) { }        // 'mode' is declared further down
  if (!kml || !layoutData || !layoutData.manholes || !layoutData.manholes.length) return;
  const f = $("stp");
  if (f.value.trim() && f.dataset.auto !== "1") return;
  let mk = null; drawn.eachLayer(l => { if (l.kind === "stp") mk = l; });
  if (!mk) return;
  const p = mk.getLatLng();
  let best = null, bd = Infinity;
  for (const m of layoutData.manholes) { const d = p.distanceTo(L.latLng(m.latlng[0], m.latlng[1])); if (d < bd) { bd = d; best = m; } }
  if (!best) return;
  f.value = best.label; f.dataset.auto = "1";
  f.title = tr(`नक्शे के STP से ${bd.toFixed(0)} m पर सबसे पास का manhole`, `the manhole nearest to the STP on the map, ${bd.toFixed(0)} m away`);
}
$("stp").addEventListener("input", () => { $("stp").dataset.auto = ""; $("stp").title = ""; });
function crossingInputs() {
  const crossings = [];
  drawn.eachLayer(l => { if (l.kind === "crossing") crossings.push({ name: l.props.name, latlngs: l.getLatLngs().map(ll => [ll.lat, ll.lng]) }); });
  return crossings;
}
function loopInputs() {
  const loops = [];
  drawn.eachLayer(l => { if (l.kind === "zone_loop") loops.push({ name: l.props.name, on_limit: l.props.on_limit || "",
    latlngs: l.getLatLngs()[0].map(ll => [ll.lat, ll.lng]) }); });
  return loops;
}
function barrierInputs() {
  const out = [];
  drawn.eachLayer(l => { if (l.kind === "barrier") out.push({ name: l.props.name, type: l.props.type || "other", gap_m: l.props.gap_m ?? "1",
    latlngs: l.getLatLngs().map(ll => [ll.lat, ll.lng]) }); });
  return out;
}
// the sewers cut at barrier lines: a mark where each was cut
function drawCuts(r, layer) {
  for (const c of r.cuts || [])
    L.marker(c.latlng, { icon: L.divIcon({ className: "cut-icon", html: "✂", iconSize: [14, 14] }) })
      .bindTooltip(tr(`${c.pipe}: ${c.barrier} पर कटा - दोनों ओर रेखा से पहले बंद`, `${c.pipe}: cut at ${c.barrier} - ends short of it on both sides`)).addTo(layer);
}
// a gap between separate pieces of the drawing (user 30-Oct-2026): a red dashed line between their nearest manholes,
// a ring at its middle (a gap of a metre or two is too short to see as a line)
function drawGaps(r, layer) {
  for (const g of r.near_gaps || []) {
    const tip = tr(`${g.a} - ${g.b}: ${g.dist_m} m का gap - drawing के अलग टुकड़े, कोई sewer नहीं जोड़ता`,
                   `${g.a} - ${g.b}: a gap of ${g.dist_m} m - separate pieces of the drawing, joined by no sewer`);
    L.polyline(g.latlngs, { color: "#d32f2f", weight: 3, dashArray: "4 4", renderer: netRenderer }).bindTooltip(tip).addTo(layer);
    L.circleMarker([(g.latlngs[0][0] + g.latlngs[1][0]) / 2, (g.latlngs[0][1] + g.latlngs[1][1]) / 2],
                   { radius: 8, color: "#d32f2f", weight: 2, fill: false, renderer: netRenderer }).bindTooltip(tip).addTo(layer);
  }
}
// the gaps in a line of the zoning's status: the nearest named
function gapNote(r) {
  const g = r.near_gaps || [];
  if (!g.length) return "";
  const s = g.slice(0, 8).map(x => `${x.a} - ${x.b} ${x.dist_m} m`).join(", ") + (g.length > 8 ? " …" : "");
  return "\n⚠ " + tr(`drawing के अलग टुकड़ों के बीच ${g.length} gap (50 m या कम), कोई sewer नहीं जोड़ता: ${s} - एक ही network हो तो DXF में (या नक्शे पर) जोड़ें; नक्शे पर लाल बिंदीदार रेखा`,
                     `${g.length} gap(s) of 50 m or less between separate pieces of the drawing, joined by no sewer: ${s} - if they are one network, join them in the DXF (or on the map); shown on the map as red dashed lines`);
}
function zdInputs() {
  stpFromMap();
  return { name: $("pname").value, catalog: $("catalog").value, joint: $("joint").value, sewage_lpcd: $("lpcd").value,
    start_depth: $("sdepth").value, stp: $("stp").value.trim(), max_zones: $("maxz").value, pop_total: $("poptot").value, mode: $("zmode").value,
    max_depth: $("maxdepth").value, bend_drop: $("bdrop").checked, mh_spacing: $("mhsp").value, bend_angle: $("bangle").value, edits: SEDITS,
    barriers: barrierInputs(), loops: loopInputs(), crossings: crossingInputs(), ...stageInputs() };
}
function layoutReady(r) {
  layoutData = r;
  zoningData = null; designData = null; tblAfterDesign(null); curOption = null;
  $("drun").disabled = true; $("drun").textContent = "Design"; $("drun").title = tr("पहले Zoning करें", "run the zoning first");
  zoneLayer.clearLayers(); designLayer.clearLayers();
  $("optbox").innerHTML = ""; $("zlist").innerHTML = ""; $("dbox").innerHTML = ""; $("zstatus").textContent = ""; $("dstatus").textContent = "";
  $("zd").hidden = false; $("viewseg").hidden = true; $("legend").innerHTML = "";
  if (r.marks && r.marks.length && !$("stp").value) { $("stp").value = r.marks[0].manhole; $("stp").dataset.auto = "1"; }
  stpFromMap();
  const hasPop = r.population > 0;
  $("popinfo").textContent = hasPop ? tr(`वार्ड / boundary से ${Number(r.population).toLocaleString("en-IN")} - manholes में बँटवारे के लिए; आधार वर्ष की आबादी खाली हो तो यही आधार वर्ष की`,
    `from the wards / boundary ${Number(r.population).toLocaleString("en-IN")} - to share out over the manholes; it is the base-year population when that is empty`) : "वार्ड में population नहीं - नीचे आधार वर्ष की आबादी भरें";
  $("poptot").hidden = true;
}

$("zrun").onclick = async () => {
  if (!layoutData) return;
  $("zrun").disabled = true; $("zstatus").className = "status"; $("zstatus").textContent = "Zoning चल रही है … (बड़े network में कुछ मिनट)";
  try {
    const r = await api("/api/zoning", zdInputs());
    if (!r.ok) { $("zstatus").className = "status err"; $("zstatus").textContent = "Zoning नहीं हुई"; $("log").hidden = false; $("log").textContent = r.log; return; }
    renderZoning(r);
  } catch (e) { $("zstatus").className = "status err"; $("zstatus").textContent = "Server से संपर्क नहीं: " + e; }
  finally { $("zrun").disabled = false; }
};

function renderZoning(r, note) {
  showForecast(r);
    r._mode = r._mode || (r.req && r.req.mode) || $("zmode").value;      // the design method the zoning was made with
    zoningData = r; designData = null; tblAfterDesign(null); designLayer.clearLayers(); $("dbox").innerHTML = ""; $("dstatus").textContent = "";
    $("zstatus").className = "status " + (r.stale ? "err" : "ok");
    $("zstatus").textContent = (note ? note + " - " : "") + `${r.options.length} options (क्रम: pumping stations, गहराई, pipe लागत) - files: ${r.files.xlsx.split(/[\\/]/).pop()}`;
    if (r.options.length && !r.options[0].mains)          // kept from before the zone boundaries were made
      $("zstatus").textContent += "\n(यह zoning पुरानी है - ज़ोन / sub-zone की सीमाएँ और नाम देखने के लिए \"Zoning options निकालें\" फिर से चलाएँ)";
    // outlets made because a part of the network had no outfall: say so (they are counted as pumping stations)
    const added = (r.options.find(o => o.option === "GIVEN") || r.options[0]).outlets.filter(x => /part had no outlet/.test(x.why));
    if (added.length) $("zstatus").textContent += `\n⚠ ${added.length} हिस्सों में कोई outfall चिह्नित नहीं था - उनका सबसे नीचा manhole ` +
      `outlet (PS) बनाया: ${added.map(x => x.manhole).join(", ")}। सही outlets नक्शे पर "Outfall" चिह्नित करके फिर सहेजें।`;
    $("zstatus").textContent += gapNote(r);
    $("optbox").innerHTML = `<table class="opts"><tr><th>Option</th><th title="${tr("ज़मीन की ढलान से बने ज़ोन", "zones made from the ground slope")}">Zones</th><th title="${tr("गहराई-सीमा के कारण ज़ोन के भीतर बने sub-zones (हर एक का अपना PS; ज़ोन का बचा हिस्सा भी एक sub-zone)", "sub-zones made inside a zone for the depth limit (each with its own PS; the rest of the zone is one too)")}">Sub-zones</th><th title="pumping stations (गहराई के लिए जोड़े)">PS</th>
      <th title="सबसे गहरा manhole (m)">गहराई<br><span class="hint">(मीटर)</span></th><th title="pipe लागत (₹ लाख)">Pipe<br><span class="hint">(₹ लाख)</span></th><th title="pipes + pumping stations + O&M + rising mains (₹ लाख, अनुमानित); pumps +15 वर्ष के flow पर जब +15 वर्ष की आबादी दी हो (CPHEEO Table 2.1 p2-9), नहीं तो +30 वर्ष पर">कुल लागत<br><span class="hint">(₹ लाख)</span></th><th></th></tr>` +
      r.options.map((o, i) => `<tr class="opt" data-i="${i}"><td${o.option === "GIVEN" ? ' title="केवल दिए गए outfalls (और STP) - गहराई के लिए कोई pumping station नहीं; क्रम से बाहर"' : ""}>${o.option === "GIVEN" ? "★ GIVEN" : `${o.rank}. ${esc(o.option)}`}</td><td>${zoneCount(o).zones}</td><td>${zoneCount(o).subs || "-"}</td>
        <td>${o.pumping}${o.pumping_for_depth ? ` (${o.pumping_for_depth})` : ""}</td><td>${o.max_depth === null || o.max_depth === undefined ? "-" : Number(o.max_depth).toFixed(2)} <span class="wmark"${o.deep_project ? ' title="project सीमा से गहरा"' : ' style="visibility:hidden"'}>⚠</span></td>
        <td>${lakh2(o.pipe_lakh)}</td><td>${lakh2(o.total_lakh)}</td><td><button data-d="${i}">Design</button></td></tr>`).join("") +
      `</table><div class="hint">पंक्ति पर click = नक्शे पर zones; PS = pumping stations, कोष्ठक में = उनमें से कितने केवल इसलिए जोड़े कि sewer project की गहराई-सीमा से गहरा न जाए। ★ GIVEN = केवल दिए गए outfalls / STP पर - गहराई के लिए कोई pumping station नहीं जोड़ा (पाइप नेटवर्क की गहराई सीमा से ज़्यादा हो सकती है); जिस हिस्से में कोई outfall नहीं, उसका सबसे नीचा manhole outlet बनता है। STP के अलावा हर outlet PS गिना जाता है (वहाँ से STP तक pumping)। "कुल" में pumping station, O&M और rising main अनुमानित हैं, STP नहीं (सब options में बराबर)। <span class="wmark">⚠</span> = project सीमा से गहरा।</div>`;
    document.querySelectorAll("#optbox tr.opt").forEach(tr => tr.onclick = ev => {
      if (ev.target.dataset.d !== undefined) return;
      showOption(r.options[+tr.dataset.i]);
    });
    document.querySelectorAll("#optbox button[data-d]").forEach(b => b.onclick = () => runDesign(r.options[+b.dataset.d]));
    $("viewseg").hidden = false;
    showOption(r.options[0]);
}

// zones of an option counted as the page names them: main zones (slope of the ground) and, apart, their sub-zones
// (a main zone split for depth: each pumping station added and the rest of the zone) - not all outlets as "zones"
// why a zone (user request 30-Oct-2026, as the water module's): its outlet's reason from the zoning - the STP by
// gravity, an outfall given on the map, a zone loop, a pumping station added for the depth limit, a part of the network
// without an outlet (cut off by a barrier line, or joined to the rest by no sewer - isolation), a basin of the ground
function whyZone(x) {
  const w = x && x.reason;
  if (!w) return "";
  const L_ = a => a.join(", "), out = [];
  out.push({
    stp: tr("ढलान से STP की ओर (gravity) - STP का zone", "draining to the STP by gravity - the STP's zone"),
    given: tr("नक्शे पर चिह्नित outfall - वहाँ pumping station", "an outfall marked on the map - a pumping station there"),
    loop: tr(`Zone लूप "${w.loop}" का क्षेत्र - outlet उसका सबसे नीचा manhole (pumping station)`, `zone loop "${w.loop}" - its outlet the lowest manhole inside (pumping station)`),
    depth: tr(`sewer project की गहराई-सीमा (${w.max_depth} m) से गहरा जाता - यहाँ pumping station जोड़ा (sub-zone)`,
              `the sewer would go deeper than the project limit (${w.max_depth} m) - a pumping station added here (sub-zone)`),
    part: tr("network के इस हिस्से में कोई outfall नहीं था - उसका सबसे नीचा manhole outlet (pumping station) बनाया",
             "this part of the network had no outfall - its lowest manhole made its outlet (pumping station)"),
    terrain: tr("ज़मीन की ढलान से बना अलग basin - इसके sewers इस निचले manhole की ओर बहते हैं; STP तक gravity से ले जाने में ऊँची ज़मीन / अधिक गहराई आती, इसलिए outlet पर pumping station",
                "a basin of its own by the ground slope - its sewers drain to this low manhole; to the STP by gravity would cross higher ground / go too deep, so a pumping station at the outlet"),
  }[w.kind] || "");
  if (w.barriers && w.barriers.length) out.push(tr(`रुकावट रेखा (${L_(w.barriers)}) से कटा network का हिस्सा`, `a part of the network cut off by the barrier line(s) ${L_(w.barriers)}`));
  if (w.loop && w.kind !== "loop") out.push(tr(`Zone लूप "${w.loop}" की सीमा से अलग`, `cut off at the zone loop "${w.loop}"`));
  if (w.isolated) out.push(tr("drawing में किसी sewer से बाकी network से नहीं जुड़ा (isolation)", "joined to the rest by no sewer in the drawing (isolation)"));
  return tr("यह zone क्यों: ", "Why this zone: ") + out.filter(Boolean).join("; ");
}
function zoneCount(o) { const zn = zoneNames(o); return { zones: zn.mains.length, subs: Object.keys(zn.sub).length }; }
// names of the zones of an option: main zones (slope of the ground) 1, 2, ... (the STP's first, then by size);
// sub-zones (pumping station added where the sewer got too deep) 1-A, 1-B, ... inside their main zone
function zoneNames(o) {
  // main zones (slope of the ground) 1, 2, ... (the STP's first, then by size); in a main zone with pumping stations
  // added for depth, the sub-zones are n-A, n-B, ... and the rest of the main zone (reaching its own outlet) gets the
  // next letter
  const parent = o.parent || Object.fromEntries(o.outlets.map(x => [x.manhole, x.manhole]));
  const byOut = Object.fromEntries(o.outlets.map(x => [x.manhole, x]));
  const size = {};
  for (const x of o.outlets) size[parent[x.manhole]] = (size[parent[x.manhole]] || 0) + (x.manholes || 0);
  const mains = [...new Set(Object.values(parent))].sort((a, b) =>
    ((byOut[b] && byOut[b].role === "STP (gravity)") - (byOut[a] && byOut[a].role === "STP (gravity)")) || (size[b] - size[a]));
  const num = {}, sub = {};
  mains.forEach((m, i) => num[m] = i + 1);
  const letters = {};
  for (const x of o.outlets) {
    const m = parent[x.manhole];
    if (x.manhole === m) continue;
    letters[m] = (letters[m] || 0) + 1;
    sub[x.manhole] = `${num[m]}-${String.fromCharCode(64 + letters[m])}`;
  }
  for (const m of mains) if (letters[m]) sub[m] = `${num[m]}-${String.fromCharCode(65 + letters[m])}`;   // the rest
  const name = {};
  for (const x of o.outlets) name[x.manhole] = sub[x.manhole] || String(num[parent[x.manhole]]);
  // "ज़ोन 1 / sub-zone 1-C"
  const full = z => `ज़ोन ${num[parent[z]] ?? "?"}` + (sub[z] ? ` / sub-zone ${sub[z]}` : "");
  return { name, parent, mains, num, sub, full };
}

function showOption(o) {
  curOption = o;
  designButton();
  $("exprow").hidden = !o.mains;
  document.querySelectorAll("#optbox tr.opt").forEach(tr => tr.classList.toggle("cur", zoningData.options[+tr.dataset.i] === o));
  zoneLayer.clearLayers();
  const zn = zoneNames(o);
  const col = {}; zn.mains.forEach((m, i) => col[m] = ZCOL[i % ZCOL.length]);
  const colOf = z => col[zn.parent[z]] || "#999";
  // a cut piece of a conduit the new manholes divided (piece_of): the conduit drawn on the map shows the cut
  const cuts = new Set(o.cuts.flatMap(l => [l, (zoningData.piece_of || {})[l]]).filter(Boolean));
  // a sewer cut at a barrier line: drawn as its parts on either side of the line, not as it was
  const barCut = new Set((zoningData.cuts || []).map(c => c.pipe));
  const why = {}; for (const x of o.outlets) why[x.manhole] = whyZone(x);   // the zone's reason, on its sewers too
  for (const c of layoutData.conduits.filter(c => !barCut.has(c.label)).concat(zoningData.cut_parts || [])) {
    const z = o.conduit_zone[c.label];
    L.polyline(c.pts, cuts.has(c.label) ? { color: "#000", weight: 2, dashArray: "4 4", renderer: netRenderer }
                                        : { color: colOf(z), weight: 3, opacity: .75, renderer: netRenderer })
      .bindTooltip(`${esc(c.label)}${cuts.has(c.label) ? " (कटा)" : ""} → ${z ? `${zn.full(z)} (outlet ${esc(z)})` : "-"}` +
        (z && why[z] ? `<div class="why-line">${esc(why[z])}</div>` : ""), { sticky: true, direction: "right", offset: [22, 0] }).addTo(zoneLayer);
  }
  // boundaries: main zones thick in their colour, sub-zones black-white dashed; their names in the middle
  const zlabel = (ll, text, cls, tip) => ll && L.marker(ll, { icon: L.divIcon({ className: cls, html: text, iconSize: null }),
    interactive: !!tip, keyboard: false }).bindTooltip(esc(tip || ""), { className: "why-tip" }).addTo(zoneLayer);
  for (const mz of o.mains || []) {
    for (const ring of mz.rings) L.polygon(ring, { color: col[mz.outlet] || "#333", weight: 4, opacity: .95, fill: true,
      fillOpacity: .06, renderer: netRenderer, interactive: false }).addTo(zoneLayer);
    for (const p of (mz.ring_labels || []).filter(Boolean).length ? mz.ring_labels.filter(Boolean) : [mz.label])
      zlabel(p, `ज़ोन ${zn.num[mz.outlet]}`, "zlabel", why[mz.outlet]);
  }
  for (const [so, sz] of Object.entries(o.subs || {})) {
    for (const ring of sz.rings) {
      L.polygon(ring, { color: "#fff", weight: 3, opacity: 1, fill: false, renderer: netRenderer, interactive: false }).addTo(zoneLayer);
      L.polygon(ring, { color: "#000", weight: 3, opacity: 1, dashArray: "8 8", fill: false, renderer: netRenderer, interactive: false }).addTo(zoneLayer);
    }
    for (const p of (sz.ring_labels || []).filter(Boolean).length ? sz.ring_labels.filter(Boolean) : [sz.label])
      zlabel(p, `${zn.sub[so] || zn.name[so]}`, "zlabel sub", why[so]);
  }
  for (const x of o.outlets) if (x.latlng) {
    const stp = x.role === "STP (gravity)";
    L.marker(x.latlng, { icon: stp ? icon("stp") : L.divIcon({ className: "ps-icon", html: `PS ${zn.name[x.manhole]}`, iconSize: [40, 16] }) })
      .bindTooltip(`${zn.full(x.manhole)} का outlet ${esc(x.manhole)}: ${stp ? "STP" : "pumping station"} (${esc(x.why)})<br>${lakh(x.flow_lps)} L/s, wet well ${x.depth ?? "-"} m` +
        (why[x.manhole] ? `<br>${esc(why[x.manhole])}` : ""), { className: "why-tip" })
      .addTo(zoneLayer);
  }
  drawCuts(zoningData, zoneLayer);
  drawGaps(zoningData, zoneLayer);
  $("zlist").innerHTML = `<div class="hint" style="margin-top:6px"><b>Option ${esc(o.option)}: ${tr("ज़ोन", "zones")}</b> ${tr("(नाम पर mouse = यह zone क्यों)", "(mouse on a name = why this zone)")}</div>` +
    `<table class="opts"><tr><th>${tr("ज़ोन", "Zone")}</th><th>Outlet</th><th>${tr("भूमिका", "Role")}</th><th>manholes</th><th>L/s</th></tr>` +
    o.outlets.map(x => `<tr><td style="cursor:help" title="${esc(why[x.manhole])}">${esc(zn.full(x.manhole))}</td><td>${esc(x.manhole)}</td>` +
      `<td>${x.role === "STP (gravity)" ? "STP" : "PS"}</td><td>${x.manholes ?? "-"}</td><td>${lakh(x.flow_lps)}</td></tr>`).join("") + `</table>`;
  setView("zones");
}

async function runDesign(o) {
  $("dstatus").className = "status"; $("dstatus").textContent = `Option ${o.option} का design चल रहा है …`;
  document.querySelectorAll("#optbox button[data-d]").forEach(b => b.disabled = true);
  try {
    const r = await api("/api/design", Object.assign(zdInputs(), { option: o.option }));
    $("log").hidden = false; $("log").textContent = r.log || "";
    if (!r.ok) { $("dstatus").className = "status err"; $("dstatus").textContent = "Design नहीं हुआ - नीचे का संदेश देखें।"; return; }
    renderDesign(r);
  } catch (e) { $("dstatus").className = "status err"; $("dstatus").textContent = "Server से संपर्क नहीं: " + e; }
  finally { document.querySelectorAll("#optbox button[data-d]").forEach(b => b.disabled = false); }
}

// GL at a sewer's end: from the design (newer results) or, for an older one, from the network's manhole
function glOf(d, end) {
  let g = d["gl_" + end];
  if (g === undefined || g === null) { const n = NET && NET.nodes[end === "up" ? d.from : d.to]; g = n ? n.gl : null; }
  return g === undefined || g === null ? "-" : Number(g).toFixed(2);
}
function renderDesign(r, note) {
  showForecast(r);
    designData = r;
    designLayer.clearLayers();
    cutHeads(r.sewers);
    drawCuts(r, designLayer);
    for (const d of r.sewers) {
      const sl = d.slope > 0 ? `1 in ${Math.round(1 / d.slope)}` : "-";
      // a sewer the new manholes (30 m spacing, bends) cut into pieces: each piece its own conduit, as in the DXF -
      // the design (diameter, slope, flow) is that of the whole sewer
      if (d.pieces && d.pieces.length) {
        d.pieces.forEach((p, i) => pickable(L.polyline(p.vpts || p.pts, { color: DCOL(d.D), weight: d.D >= 400 ? 6 : 4, opacity: .95, renderer: netRenderer }),
          `<b>${esc(p.label)}</b> ${esc(p.from)} → ${esc(p.to)}<br><span class="hint">${tr(`${esc(d.label)} का हिस्सा ${i + 1}/${d.pieces.length} (नए manholes से बँटा; design पूरे ${esc(d.label)} पर, ${d.length.toFixed(1)} m)`,
            `piece ${i + 1}/${d.pieces.length} of ${esc(d.label)} (cut by the new manholes; designed as the whole ${esc(d.label)}, ${d.length.toFixed(1)} m)`)}</span>` +
          `<br>${d.D} mm, ${sl}, ${p.length.toFixed(1)} m<br>Q ${d.q.toFixed(2)} L/s, v ${d.v.toFixed(2)} m/s` +
          `<br>${tr("पाइप गहराई", "pipe depth")} ${f2(p.depth_up)} → ${f2(p.depth_dn)} m<br>GL ${f2(p.gl_up)} → ${f2(p.gl_dn)} m<br>IL ${f2(p.il_up)} → ${f2(p.il_dn)} m` +
          (d.flags.length ? `<br><span style="color:#c62828">${d.flags.map(esc).join("<br>")}</span>` : ""), true).addTo(designLayer));
        continue;
      }
      pickable(L.polyline(d.vpts, { color: DCOL(d.D), weight: d.D >= 400 ? 6 : 4, opacity: .95, renderer: netRenderer }),
        `<b>${esc(d.label)}</b> ${esc(d.from)} → ${esc(d.to)}<br>${d.D} mm, ${sl}, ${d.length.toFixed(1)} m<br>` +
          `Q ${d.q.toFixed(2)} L/s, v ${d.v.toFixed(2)} m/s<br>पाइप गहराई ${d.depth_up?.toFixed(2) ?? "-"} → ${d.depth_dn?.toFixed(2) ?? "-"} m` +
          `<br>GL ${glOf(d, "up")} → ${glOf(d, "dn")} m` + (d.il_up !== undefined ? `<br>IL ${f2(d.il_up)} → ${f2(d.il_dn)} m` : "") +
          (d.flags.length ? `<br><span style="color:#c62828">${d.flags.map(esc).join("<br>")}</span>` : ""), true)
        .addTo(designLayer);
    }
    // the manholes of the design, with GL, the lowest invert and the depth
    const nodes = designNodes(r.sewers), byN = {}; for (const m of nodes) byN[m.label] = m;
    for (const m of nodes) {
      const main = m.cut ? byN[m.label.replace(CUT_RE, "")] : null;
      pickable(L.circleMarker(m.latlng, m.cut ? { radius: 4.5, color: "#e65100", weight: 2.5, fillColor: "#fff3e0", fillOpacity: 1, renderer: netRenderer }
        : { radius: 3.5, color: "#263238", weight: 1, fillColor: "#fff", fillOpacity: 1, renderer: netRenderer }),
        `<b>${esc(m.label)}</b>` + (m.cut ? `<br><span style="color:#e65100">कटा loop: अलग शुरुआती manhole, ${esc(m.label.replace(CUT_RE, ""))} से जुड़ा नहीं` +
          (main && main.il !== null && m.il !== null ? ` (IL ${f2(m.il)} m, वहाँ ${f2(main.il)} m)` : "") + `</span>` : "") +
        `<br>GL ${f2(m.gl)} m` + (m.depth !== null ? `<br>गहराई ${f2(m.depth)} m` : "") +
        // the invert of every pipe at this manhole: each incoming one arrives at its own level, the outgoing leaves lower
        `<br>आने वाले: ${m.ins.map(x => `${esc(x.label)}` + (x.il !== null && x.il !== undefined ? ` (IL ${f2(x.il)} m)` : "")).join(", ") || "-"}` +
        `<br>जाने वाले: ${m.outs.map(x => `${esc(x.label)}` + (x.il !== null && x.il !== undefined ? ` (IL ${f2(x.il)} m)` : "")).join(", ") || "-"}`, false).addTo(designLayer);
    }
    // the new manholes of the drawing (30 m spacing, bends - CPHEEO 3.71): the map shows what the DXF has - only
    // zoomed in (newMhShow)
    newMhGroup = L.layerGroup();
    for (const m of r.new_manholes || []) {
      const bend = m.why.startsWith("bend");
      pickable(L.circleMarker(m.latlng, { radius: 3.5, color: bend ? "#6a1b9a" : "#00838f", weight: 1.5, fillColor: "#fff", fillOpacity: 1, renderer: netRenderer }),
        `<b>${esc(m.label)}</b> <span class="hint">${tr("नया", "new")}</span><br>` +
        (bend ? tr(`मोड़ पर (${esc(m.why.replace("bend ", "").replace(" deg", "°"))}), CPHEEO 3.71`, `at a bend (${esc(m.why.replace("bend ", "").replace(" deg", "°"))}), CPHEEO 3.71`)
              : tr("30 m की दूरी के लिए, CPHEEO 3.71.1", "for the 30 m spacing, CPHEEO 3.71.1")) +
        `<br>${tr("conduit पर", "on conduit")} ${esc(m.conduit)}<br>GL ${f2(m.gl)} m (${m.gl_edited ? tr("table से - survey", "from the table - survey") : "interpolated"})<br>IL ${f2(m.invert)} m` +
        (m.depth !== null ? `<br>${tr("गहराई", "depth")} ${f2(m.depth)} m` : ""), false).addTo(newMhGroup);
    }
    newMhShow();
    // the outlets of the designed option (STP / pumping stations) on the design view too
    const opt = zoningData && zoningData.options.find(o => o.option === r.summary.option);
    if (opt) { const zn = zoneNames(opt); opt.outlets.forEach(x => { if (!x.latlng) return;
      const stp = x.role === "STP (gravity)";
      L.marker(x.latlng, { icon: stp ? icon("stp") : L.divIcon({ className: "ps-icon", html: `PS ${zn.name[x.manhole]}`, iconSize: [40, 16] }) })
        .bindTooltip(`${zn.full(x.manhole)} का outlet ${esc(x.manhole)}: ${stp ? "STP" : "pumping station"}`).addTo(designLayer); }); }
    const s = r.summary;
    $("dstatus").className = "status " + (r.stale ? "err" : "ok"); $("dstatus").textContent = (note ? note + " - " : "") + `Design (${s.grade}) - option ${s.option}`;
    $("dbox").innerHTML = `<div class="box"><b>${s.sewers} sewers, ${(s.length / 1000).toFixed(2)} km</b>; सबसे गहरा ${s.max_depth} m;
      pipe लागत ₹ ${lakh(s.pipe_lakh)} लाख; outfalls ${s.outfalls.map(esc).join(", ")}` +
      (s.new_manholes ? tr(`; नए manholes ${s.new_manholes} (मोड़ पर ${s.new_manholes_bend || 0}, 30 m के लिए ${s.new_manholes - (s.new_manholes_bend || 0)}; नक्शे पर बैंगनी / हरा-नीला घेरा, zoom ${NEW_MH_ZOOM}+ पर)`,
                           `; new manholes ${s.new_manholes} (at bends ${s.new_manholes_bend || 0}, for 30 m ${s.new_manholes - (s.new_manholes_bend || 0)}; purple / teal circle on the map from zoom ${NEW_MH_ZOOM})`) : "") +
      (r.warnings.length ? `<div class="warn" style="margin-top:4px">${((!EN && r.warnings_hi) || r.warnings).map(w => "• " + esc(w)).join("<br>")}</div>` : "") +
      `<div class="hint" style="margin-top:4px">Files: ${Object.values(r.files).map(f => esc(f.split(/[\\/]/).pop())).join("<br>")}</div></div>` +
      sewerStageBox(r.stages);
    setView("design");
    tblAfterDesign(r);
}
