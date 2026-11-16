// The water map page (map.html), part 6 of 11: zoning and design: the OHTs, standby tube wells, the app's suggestions, the hover card.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---------------------------------------------------------------- zoning and design
const zoneLayer = new L.FeatureGroup(), designLayer = new L.FeatureGroup();
// red crosses of a DXF network (manholes on top of each other, not joined): in every view - layout, zones and design
const warnLayer = new L.FeatureGroup();
// zone / design lines use netRenderer, the canvas of the network: a second canvas would lie over it and take every
// click (the manholes could not be selected any more)
let layoutData = null;
const ZCOL = ["#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2", "#bcbd22",
  "#7f7f7f", "#393b79", "#637939", "#843c39", "#7b4173", "#3182bd", "#e6550d"];
// ================================================================ water module: zoning (OZ / DMA) and design
let wZoning = null, wDesign = null;
const WLEG = {};
const ZPAL = ["#1565c0", "#e65100", "#2e7d32", "#6a1b9a", "#c62828", "#00838f", "#9e9d24", "#ad1457", "#4e342e", "#283593"];
const WSIZE = ["#90caf9", "#42a5f5", "#1e88e5", "#43a047", "#7cb342", "#fdd835", "#fb8c00", "#f4511e", "#e53935", "#8e24aa", "#4a148c"];
function wInputs() {
  const ohts = [];
  drawn.eachLayer(l => { if (l.kind === "oht") { const ll = l.getLatLng();
    ohts.push({ name: l.props.name, lat: ll.lat, lng: ll.lng, existing: isExOht(l.props) ? "1" : "0", capacity_kl: l.props.capacity_kl ?? "",
                staging_m: l.props.staging_m ?? "", tubewells: l.props.tubewells ?? "", rebore: l.props.rebore ?? "", low_head: l.props.low_head || "vfd" }); } });
  const barriers = [];
  drawn.eachLayer(l => { if (l.kind === "barrier") barriers.push({ name: l.props.name, type: l.props.type || "other", gap_m: l.props.gap_m ?? "1",
    latlngs: l.getLatLngs().map(ll => [ll.lat, ll.lng]) }); });
  const loops = [];
  drawn.eachLayer(l => { if (l.kind === "zone_loop") loops.push({ name: l.props.name, on_limit: l.props.on_limit || "",
    latlngs: l.getLatLngs()[0].map(ll => [ll.lat, ll.lng]) }); });
  const crossings = [];
  drawn.eachLayer(l => { if (l.kind === "crossing") crossings.push({ name: l.props.name, tol_m: l.props.tol_m ?? "", snap_m: l.props.snap_m ?? "",
    latlngs: l.getLatLngs().map(ll => [ll.lat, ll.lng]) }); });
  const wards = [];                     // a DXF network's wards (a layout has its population from the layout)
  if (mode === "dxf") drawn.eachLayer(l => { if (l.kind === "ward") wards.push({ name: l.props.name, population: l.props.population ?? "", ward_no: l.props.ward_no ?? "",
    character: l.props.character || "", latlngs: l.getLatLngs()[0].map(ll => [ll.lat, ll.lng]) }); });
  const bulk = [];                      // bulk / institutional consumers (user 30-Oct-2026)
  drawn.eachLayer(l => { if (l.kind === "bulk") { const ll = l.getLatLng();
    bulk.push({ name: l.props.name, lat: ll.lat, lng: ll.lng, kld: l.props.kld ?? "", peak: l.props.peak ?? "" }); } });
  const prvs = [];                      // pressure reducing valves (user 30-Oct-2026)
  drawn.eachLayer(l => { if (l.kind === "prv") { const ll = l.getLatLng(); prvs.push({ name: l.props.name, lat: ll.lat, lng: ll.lng, setting_m: l.props.setting_m ?? "" }); } });
  const tws = [];                       // new tube wells (water phase 2, user 31-Oct-2026)
  drawn.eachLayer(l => { if (l.kind === "tw") { const ll = l.getLatLng(); tws.push({ name: l.props.name, lat: ll.lat, lng: ll.lng, discharge_lpm: l.props.discharge_lpm ?? "" }); } });
  return uiSimple({ name: $("pname").value, ohts, barriers, loops, crossings, wards, bulk, prvs, tws, projection: pjInputs(), pop_factor: $("wpopf").value, floating_pct: $("wfloat").value, load_by: $("wloadby").value, cons: consInputs(), simulate: $("wsim").checked ? "1" : "0", fire_lps: $("wfirelps").value, fire_min_m: $("wfiremin").value, peak: $("wpeak").value === "given" ? $("wpeakv").value : $("wpeak").value, persons_per_connection: $("wppc").value, use_prv: $("wprv").checked ? "1" : "",
           oht_inflow: $("winflow").value, near_m: $("wnearm").value, ward_table: wtInputs(), intze: izInputs(), tw_standby: sbInputs(), sug: SUG,
           pop_total: $("poptot").hidden ? "" : $("poptot").value, edits: WEDITS, ...stageInputs() }, W_SIMPLE);
}
// Simple mode (ui.js, user request 16-Nov-2026): the fields it hides at the app's CPHEEO / UPJN defaults
const W_SIMPLE = { projection: null, ward_table: null, base_year: "", pop_initial: "", pop_mid: "", floating_pct: "10",
  load_by: "length", persons_per_connection: "6", oht_inflow: "5-12, 13-22", near_m: "50", tw_standby: { on: false },
  peak: "urban", use_prv: "", simulate: "1", fire_lps: "", fire_min_m: "", cons: {} };
// stage-wise check (CPHEEO sewer Table 2.1 p2-9, water Table 2.7 S.No.1 p168): base year and the populations of the
// base year and +15 years; the design population is +30 years. Empty populations = no stage check.
// the design's constraints of the page (user request 16-Nov-2026): a value only when its box is ticked
const CONS = ["cases", "pmax", "dmin", "dmax", "hdpe_max", "hl", "stg", "margin"];
function consInputs() {
  const c = {};
  for (const k of CONS) c[k] = $("wcon_" + k).checked ? (k === "cases" ? "1" : $("wc_" + k).value) : "";
  return c;
}
function consRestore(c) {
  c = c || {};
  for (const k of CONS) {
    const v = c[k];
    $("wcon_" + k).checked = v !== undefined && v !== "" && v !== null;
    if ($("wc_" + k) && $("wcon_" + k).checked && k !== "cases") $("wc_" + k).value = v;
  }
  if (CONS.some(k => $("wcon_" + k).checked)) $("wcons").open = true;
}
function stageInputs() { return { base_year: $("byear").value, pop_initial: $("popb").value, pop_mid: $("popm").value }; }
// ---- standby tube wells (user 15-Nov-2026): CPHEEO 5.7.5 by default; the page's own table when switched on - the new
// tube wells only (booster / CWR pumps: always CPHEEO). Rows [working up to, standby]; beyond the last: its standby.
const SB_DEF = [[2, 1], [5, 2], [10, 3]];
let SB = SB_DEF.map(r => r.slice());
function sbInputs() { return { on: $("wsbon").checked ? "1" : "", rows: SB.map(r => r.slice()) }; }
function sbRender() {
  const on = $("wsbon").checked, box = $("wsbtab");
  box.classList.toggle("off", !on);
  box.innerHTML = `<table><tr><th>${tr("working tube wells तक", "working tube wells up to")}</th><th>standby</th><th></th></tr>` +
    SB.map((r, i) => `<tr><td>≤ <input type="number" min="1" step="1" data-i="${i}" data-c="0" value="${r[0]}"${on ? "" : " disabled"}></td>` +
      `<td><input type="number" min="0" max="20" step="1" data-i="${i}" data-c="1" value="${r[1]}"${on ? "" : " disabled"}></td>` +
      `<td>${on && SB.length > 1 ? `<button type="button" data-del="${i}" title="${tr("पंक्ति हटाएँ", "remove the row")}">✕</button>` : ""}</td></tr>`).join("") +
    `</table>` + (on ? `<button type="button" id="wsbadd">+ ${tr("पंक्ति", "row")}</button> <button type="button" id="wsbdef">${tr("CPHEEO वाली", "CPHEEO's")}</button>` : "") +
    `<div class="hint">${tr("अंतिम पंक्ति से अधिक working हों तो अंतिम पंक्ति के standby। Zoning / Design दोबारा चलाने पर लागू।", "More working than the last row: the last row's standby. Applies when Zoning / Design run again.")}</div>`;
  box.querySelectorAll("input").forEach(el => el.onchange = () => { SB[+el.dataset.i][+el.dataset.c] = Math.max(0, Math.round(+el.value || 0)); changed(); });
  box.querySelectorAll("[data-del]").forEach(el => el.onclick = () => { SB.splice(+el.dataset.del, 1); sbRender(); changed(); });
  if ($("wsbadd")) $("wsbadd").onclick = () => { const l = SB[SB.length - 1] || [0, 0]; SB.push([l[0] + 5, l[1] + 1]); sbRender(); changed(); };
  if ($("wsbdef")) $("wsbdef").onclick = () => { SB = SB_DEF.map(r => r.slice()); sbRender(); changed(); };
}
$("wsbon").onchange = () => { sbRender(); changed(); };
$("wpeak").onchange = () => { $("wpeakv").hidden = $("wpeak").value !== "given"; };
$("wsbinfo").onclick = ev => {
  document.querySelectorAll(".cpop").forEach(e => e.remove());
  const d = document.createElement("div"); d.className = "cpop";
  d.innerHTML = `<b>${tr("Standby - CPHEEO का नियम", "Standby - the CPHEEO rule")}</b> <button type="button" style="float:right">✕</button>
    <div>CPHEEO Manual on Water Supply and Treatment Systems, Part A (2024), 5.7.5 (p245-246) - ${tr("working pumps के अनुसार standby:", "standby by the working pumps:")}</div>
    <table><tr><th>working</th><th>standby</th></tr><tr><td>1</td><td>1</td></tr><tr><td>2</td><td>1 (${tr("सामान्यतः", "generally")})</td></tr>
    <tr><td>3 - 5</td><td>2</td></tr><tr><td>6 - 10</td><td>3</td></tr></table>
    <div>${tr("App नए tube wells पर यही लगाता है (निर्णय 7-Nov-2026): हर standby एक पूरा tube well - boring, pump house, pump, बिजली कनेक्शन, अपनी rising main। Design में OHT से सड़क के रास्ते सबसे दूर वाले standby गिने जाते हैं। Booster और CWR pumps पर हमेशा यही table।",
      "The app applies it to the new tube wells (decision 7-Nov-2026): each standby a whole tube well - boring, pump house, pump, power connection, its own rising main. In the design the farthest from the OHT along the roads are the standby ones. Booster and CWR pumps always take this table.")}</div>
    <div class="hint">${tr("अपने हिसाब से (checkbox) चालू करने पर ऊपर की table सिर्फ़ नए tube wells पर लगेगी।", "Switched on (checkbox), the table above applies to the new tube wells only.")}</div>`;
  document.body.appendChild(d);
  const r = ev.target.getBoundingClientRect();
  d.style.left = Math.max(8, Math.min(r.left, innerWidth - d.offsetWidth - 8)) + "px";
  d.style.top = Math.min(r.bottom + 6, innerHeight - d.offsetHeight - 8) + "px";
  d.querySelector("button").onclick = () => d.remove();
};
sbRender();

// ---- the app's suggestions taken away (user decision 15-Nov-2026): a proposed OHT just goes (its area to the
// neighbouring OZs); a suggested tube well goes and none comes in its place - its OZ's tube wells are then the map's,
// too few: the design fails and tells how many the demand needs. Sites are kept (an OZ is renamed when the zoning
// runs again): those of the OHTs taken away, and the OHT sites of the OZs whose tube wells are the user's.
let SUG = { oht_off: [], oht_off_all: false, tw_off: [], tw_off_all: false };
function sugRender() {
  const o = SUG.oht_off_all ? tr("सभी हटाई", "all taken away") : SUG.oht_off.length ? tr(`${SUG.oht_off.length} हटाई`, `${SUG.oht_off.length} taken away`) : "";
  const t = SUG.tw_off_all ? tr("सभी हटाए", "all taken away") : SUG.tw_off.length ? tr(`${SUG.tw_off.length} OZ में हटाए`, `taken away in ${SUG.tw_off.length} OZ`) : "";
  $("wsug").innerHTML =
    `<div><b>${tr("सुझाई OHT", "Suggested OHTs")}</b>: ${o ? `${o} <button type="button" id="wsugo1">${tr("वापस लाएँ", "bring back")}</button>`
       : `<button type="button" id="wsugo0">${tr("सभी सुझाई OHT हटाएँ", "Remove all suggested OHTs")}</button>`}</div>` +
    `<div style="margin-top:3px"><b>${tr("सुझाए tube wells", "Suggested tube wells")}</b>: ${t ? `${t} <button type="button" id="wsugt1">${tr("वापस लाएँ", "bring back")}</button>`
       : `<button type="button" id="wsugt0">${tr("सभी सुझाए tube wells हटाएँ", "Remove all suggested tube wells")}</button>`}</div>` +
    `<div class="hint">${tr("हटाई OHT: उसका इलाका पड़ोसी OZ लेते हैं (न ले सकें तो किसी OHT से नहीं जुड़ा)। हटाए tube wells: उस OZ में सिर्फ़ नक्शे वाले लिए जाते हैं - कम हों तो design अधूरा (✖) और कमी वाले tube wells की जगहें लाल T! से। Zoning / Design दोबारा चलाने पर लागू।",
      "An OHT taken away: its area goes to the neighbouring OZs (or stays joined to none). Tube wells taken away: that OZ takes the map's only - too few: the design fails (✖) and the sites for the rest show as red T!. Applies when Zoning / Design run again.")}</div>`;
  const on = (id, fn) => { if ($(id)) $(id).onclick = () => { fn(); sugRender(); changed(); }; };
  on("wsugo0", () => { if (confirm(tr("सभी सुझाई OHT हटाएँ? Zoning तब सिर्फ़ नक्शे पर रखी OHT लेगी।", "Remove all suggested OHTs? The zoning then takes the OHTs on the map only."))) SUG.oht_off_all = true; });
  on("wsugo1", () => { SUG.oht_off_all = false; SUG.oht_off = []; });
  on("wsugt0", () => { if (confirm(tr("सभी सुझाए tube wells हटाएँ? Design तब सिर्फ़ नक्शे पर रखे tube wells लेगा।", "Remove all suggested tube wells? The design then takes the tube wells on the map only."))) SUG.tw_off_all = true; });
  on("wsugt1", () => { SUG.tw_off_all = false; SUG.tw_off = []; });
}
sugRender();
function sugTwOff(t, also) {                       // one suggested tube well taken away: its OZ's are now the map's
  const site = ohtLatLng(t.oz);
  if (site && !SUG.tw_off.some(p => Math.abs(p.lat - site[0]) < 1e-7 && Math.abs(p.lng - site[1]) < 1e-7))
    SUG.tw_off.push({ lat: site[0], lng: site[1] });
  for (const x of (wDesign && wDesign.rising && wDesign.rising.tws) || [])          // the others of its OZ stay: on the map
    if (x.oz === t.oz && !x.placed && x !== t && x.latlng && !x._mapped) x._mapped = addFeature(L.marker(x.latlng), "tw", { name: nextTw(), discharge_lpm: "" });
  (also || []).forEach(m => m && m.remove());
  sugRender(); changed();
  if ($("wstatus")) { $("wstatus").className = "status"; $("wstatus").textContent = tr(`${t.name} हटाया - ${t.oz} के बाकी tube wells अब नक्शे पर आपके; Design दोबारा चलाएँ`, `${t.name} taken away - the other tube wells of ${t.oz} are now yours on the map; run the Design again`); }
}
function sugOhtOff(name, ll, also) {                // a proposed OHT taken away: it just goes
  if (!confirm(tr(`${name} हटाएँ? अगली Zoning में यह OHT नहीं होगी, उसका इलाका पड़ोसी OZ लेंगे।`, `Remove ${name}? The next zoning has no OHT there; the neighbouring OZs take its area.`))) return;
  SUG.oht_off.push({ lat: ll[0], lng: ll[1] });
  (also || []).forEach(m => m && m.remove());
  sugRender(); changed();
}

// ---- hover card of a tube well / tank (user 15-Nov-2026): its zone, capacity, staging, by whom, main / standby; ✕ and
// move for those on the map. A suggested tube well or a proposed OHT moved becomes the user's: a proposed OHT moved
// comes on the map with its OZ's suggested tube wells (else the next design would leave them out), a suggested tube
// well of a proposed OHT's OZ the same way (the map's tube wells of such an OZ are not taken).
let hcPop = null, hcTimer = null;
function hcClose(now) {
  clearTimeout(hcTimer);
  const go = () => { if (hcPop) map.closePopup(hcPop); hcPop = null; };
  if (now) go(); else hcTimer = setTimeout(go, 350);
}
function hoverCard(marker, build) {
  if (marker._hc) return;
  marker._hc = true;
  marker.on("mouseover", () => {
    if (marker._hcDrag) return;
    clearTimeout(hcTimer);
    const c = build(); if (!c) return;
    const el = document.createElement("div");
    el.innerHTML = c.html;
    if (c.acts && c.acts.length) {
      const bar = document.createElement("div"); bar.className = "hc-act";
      for (const [lab, title, fn, cls] of c.acts) {
        const b = document.createElement("button"); b.type = "button"; b.textContent = lab; b.title = title; if (cls) b.className = cls;
        b.onclick = ev => { L.DomEvent.stopPropagation(ev); hcClose(true); fn(); };
        bar.appendChild(b);
      }
      el.appendChild(bar);
    }
    L.DomEvent.disableClickPropagation(el);
    el.addEventListener("mouseenter", () => clearTimeout(hcTimer));
    el.addEventListener("mouseleave", () => hcClose());
    if (hcPop) map.closePopup(hcPop);
    hcPop = L.popup({ closeButton: false, autoPan: false, autoClose: false, className: "hovcard", offset: [0, -10] })
      .setLatLng(marker.getLatLng()).setContent(el).openOn(map);
  });
  marker.on("mouseout", () => hcClose());
}
const hcRow = (k, v) => v === undefined || v === null || v === "" ? "" : `<div><span class="hc-k">${k}:</span> ${v}</div>`;
const hcStale = () => `<div class="hint">${tr("बदलाव के बाद Zoning / Design दोबारा चलाएँ।", "After a change run Zoning / Design again.")}</div>`;
function hcMove(layer) {                         // a marker of the map dragged once to its new place
  if (!layer.dragging) return;
  layer._hcDrag = true;
  layer.dragging.enable();
  const el = layer.getElement && layer.getElement();
  if (el) el.classList.add("hc-moving");
  layer.once("dragend", () => {
    if (!(selected === layer && layer.kind === "oht")) layer.dragging.disable();
    layer._hcDrag = false;
    if (el) el.classList.remove("hc-moving");
    label(layer); changed();
  });
  if ($("wstatus")) { $("wstatus").className = "status"; $("wstatus").textContent = tr(`${layer.props.name}: खींचकर नई जगह पर छोड़ें`, `${layer.props.name}: drag it to its new place`); }
}
function hcDelete(layer, also) {
  if (!confirm(tr(`${layer.props.name} नक्शे से हटाएँ?`, `Remove ${layer.props.name} from the map?`))) return;
  if (selected === layer) select(null);
  drawn.removeLayer(layer);
  (also || []).forEach(m => m && m.remove());
  showProps(); changed();
}
function nextTw() {                               // a name after the highest "TW n" on the map
  let n = 0; drawn.eachLayer(l => { const m = l.kind === "tw" && /^TW (\d+)$/.exec(l.props.name || ""); if (m) n = Math.max(n, +m[1]); });
  return `TW ${n + 1}`;
}
const drawnBy = (kind, name) => { let t = null; drawn.eachLayer(l => { if (l.kind === kind && l.props.name === name) t = l; }); return t; };
function twInfo(name) {
  const R = wDesign && wDesign.rising;
  return { t: R && (R.tws || []).find(x => x.name === name), d: R && (R.dropped || []).find(x => x.name === name) };
}
function twCardHtml(name, lpm, user) {
  const { t, d } = twInfo(name);
  return `<b>${esc(name)}</b> <span class="hint">${user ? tr("आपका (नक्शे पर)", "yours (on the map)") : tr("auto - app का सुझाव", "auto - suggested by the app")}</span>` +
    hcRow("Zone", t ? esc(t.oz) : d ? esc(d.oz) : "") +
    hcRow("Discharge", `${fmt(+(lpm || (t && t.lpm) || 1500))} LPM`) +
    (t ? hcRow(tr("भूमिका", "role"), t.standby ? `<b style="color:#e65100">standby</b>` : `<b>main</b> (working)`) : "") +
    (t && t.size ? hcRow("Rising main", `${fmt(t.length_m)} m ${esc(t.size)}${t.cls ? " " + esc(t.cls) : ""}, head ${fmt(t.head_m, 1)} m`) : "") +
    (d ? `<div style="color:#c62828">${d.why === "auto" ? tr("इस design में नहीं लिया: OHT zoning की proposed है", "Not taken in this design: its OHT is the zoning's proposed one")
                                                      : tr("इस design में नहीं लिया: OZ में ज़रूरत से ज़्यादा", "Not taken in this design: more than its OZ needs")}</div>` : "") +
    (!t && !d ? `<div class="hint">${tr("Design के बाद zone और main / standby दिखेगा।", "Zone and main / standby show after a design.")}</div>` : "");
}
function ohtInfo(name) {
  const o = wDesign && (wDesign.outlets || []).find(x => x.name === name);
  const z = wZoning && (wZoning.zones || []).find(x => x.name === name);
  const tws = ((wDesign && wDesign.rising && wDesign.rising.tws) || []).filter(t => t.oz === name);
  return { o, z, tws };
}
function ohtCardHtml(name, user, props) {
  const { o, z, tws } = ohtInfo(name), ex = o ? o.existing : z ? z.existing : isExOht(props);
  const cap = ex ? (o ? o.capacity_kl : z ? z.capacity_kl : props && props.capacity_kl) : (o ? o.required_kl : z ? z.required_kl : "");
  const stg = o && o.staging_m !== null && o.staging_m !== undefined ? `${fmt(o.staging_m, 1)} m${o.staging_auto ? " (" + tr("design से", "from the design") + ")" : ""}`
            : props && props.staging_m ? `${props.staging_m} m` : tr("design से", "from the design");
  const sb = tws.filter(t => t.standby).length;
  return `<b>${esc(name)}</b> <span class="hint">${user ? tr("आपकी (नक्शे पर)", "yours (on the map)") : tr("auto - zoning की proposed", "auto - proposed by the zoning")}, ${ex ? tr("पुरानी", "existing") : tr("नई", "new")}</span>` +
    hcRow("Zone", o || z ? `${esc(name)}${z && z.dma_count ? `, ${z.dma_count} DMA` : ""}` : "") +
    hcRow(ex ? tr("क्षमता", "capacity") : tr("आवश्यक क्षमता", "required capacity"), cap ? `${fmt(cap)} KL` : "") +
    hcRow("CWR", (o && o.cwr_kl) || (z && z.cwr_kl) ? `${fmt((o && o.cwr_kl) || z.cwr_kl)} KL` : "") +
    hcRow("Staging", stg) +
    hcRow(tr("आबादी", "population"), o ? fmt(o.population) : z ? fmt(z.population) : "") +
    (o ? hcRow(tr("निकास", "outlet"), `${fmt(o.flow, 1)} L/s, ${esc(o.size || "")}`) + hcRow(tr("OZ में न्यूनतम residual head", "lowest residual head in the OZ"), `${fmt(o.lowest_p, 2)} m`) : "") +
    (o && o.vfd_head_m ? `<div><b style="color:#6a1b9a">${tr("outlet पर VFD pump", "VFD pump at the outlet")}: +${fmt(o.vfd_head_m, 1)} m, ~${fmt(o.vfd_kw, 1)} kW</b></div>` : "") +
    (o && o.short_m ? `<div><b style="color:#c62828">${tr(`staging कम: ${o.short_m} m और चाहिए`, `staging too low: ${o.short_m} m more needed`)}</b></div>` : "") +
    hcRow(tr("नए tube wells", "new tube wells"), tws.length ? `${tws.length - sb} main + ${sb} standby` : z && z.tubewells_new !== undefined ? `${z.tubewells_new} + ${z.tubewells_standby || 0} standby (zoning)` : "");
}
function convertOht(name, ll, also) {              // a proposed OHT becomes the user's, with its OZ's suggested tube wells
  let o = drawnBy("oht", name);
  if (!o) o = addFeature(L.marker(ll), "oht", { name, existing: "0", capacity_kl: "", staging_m: "", tubewells: "" });
  for (const t of (wDesign && wDesign.rising && wDesign.rising.tws) || [])
    if (t.oz === name && !t.placed && t.latlng && !t._mapped) t._mapped = addFeature(L.marker(t.latlng), "tw", { name: nextTw(), discharge_lpm: "" });
  (also || []).forEach(m => m && m.remove());
  ohtTouched(); changed();
  return o;
}
function ohtLatLng(name) {
  const { o, z } = ohtInfo(name);
  return (o && o.latlng) || (z && z.latlng);
}
function moveSuggestedTw(t, also) {
  let l;
  if (t.auto) { convertOht(t.oz, ohtLatLng(t.oz)); l = t._mapped; }
  else { l = t._mapped || addFeature(L.marker(t.latlng), "tw", { name: nextTw(), discharge_lpm: "" }); t._mapped = l; changed(); }
  (also || []).forEach(m => m && m.remove());
  if (l) hcMove(l);
}
