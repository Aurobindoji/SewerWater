// The water map page (map.html), part 9 of 11: the rate xlsx, the Intze OHT drawings, the pipe / junction tables.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---- the DPR's rates: Export / Import rate xlsx (rates.py, user decisions 15-Nov-2026)
function wrStatus(s) {
  if (!s) return;
  $("wrst").textContent = s.changed
    ? tr(`आपके rates लागू: ${s.changed} rate बदले (${s.file || "xlsx"}, ${s.time})`, `Your rates in use: ${s.changed} rates changed (${s.file || "xlsx"}, ${s.time})`)
    : tr("App के अपने rates (SOR 2025-26, UPJN)", "The app's own rates (SOR 2025-26, UPJN)");
  $("wrreset").disabled = !s.changed;
}
api("/api/water_rates", { act: "status" }).then(r => r && r.ok && wrStatus(r.status)).catch(() => {});
$("wrexp").onclick = () => {
  let r = null;
  longTask(tr("Rate xlsx", "Rate xlsx"), async () => { r = await api("/api/water_rates", { act: "export", name: $("pname").value }); },
    () => !r || !r.ok ? [tr("Rate xlsx नहीं बनी", "No rate xlsx"), (r && r.log) || "error", "err"]
      : [tr("Rate xlsx तैयार", "Rate xlsx ready"), `folder: ${r.folder}\n\nExcel : ${r.path.split(/[\\/]/).pop()}\n` +
         (r.design ? tr(`पीले: SOR ${r.sor_used} item, UPJN ${r.upjn_used} rate (आख़िरी Design की DPR में उपयोग)`, `Yellow: ${r.sor_used} SOR items, ${r.upjn_used} UPJN rates (used by the last design's DPR)`)
                   : tr("इस project का Design नहीं - कोई पीला नहीं।", "No design of this project - none yellow.")) +
         (r.changed ? "\n" + tr(`${r.changed} rate आपके import किए हुए।`, `${r.changed} rates are your imported ones.`) : "") + "\n" +
         tr(r.opened ? "Excel में खुल रही है। Rate column बदलकर सहेजें, फिर 'Import rate xlsx…'।" : "Excel नहीं खुला, folder से खोलें।",
            r.opened ? "Opening in Excel. Change the Rate column, save, then 'Import rate xlsx…'." : "Excel did not open; open it from the folder."),
         "ok"]);
};
$("wrimp").onclick = () => $("wrfile").click();
$("wrfile").onchange = async e => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  loading(true, tr(`${f.name} पढ़ रहे हैं …`, `Reading ${f.name} …`));
  try {
    const u8 = new Uint8Array(await f.arrayBuffer());
    let bin = ""; for (let i = 0; i < u8.length; i += 0x8000) bin += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    const r = await api("/api/water_rates", { act: "import", file: f.name, b64: btoa(bin) });
    if (!r.ok) { $("wrst").textContent = tr("Rate xlsx नहीं पढ़ी: ", "Rate xlsx not read: ") + (r.log || ""); return; }
    wrStatus(r.status);
    $("wrst").innerHTML += `<div class="hint">${esc(tr(`${f.name}: SOR ${r.sor_changed}, UPJN ${r.upjn_changed} rate app से अलग - सब projects की अगली Design / Export DPR में लगेंगे`,
      `${f.name}: ${r.sor_changed} SOR, ${r.upjn_changed} UPJN rates differ from the app's - in every project's next design / Export DPR`))}</div>` +
      (r.notes || []).map(n => `<div class="wflag warn">⚠ ${esc(EN ? n[1] : n[0])}</div>`).join("");
  } catch (err) { $("wrst").textContent = tr("Rate xlsx नहीं पढ़ी: ", "Rate xlsx not read: ") + err.message; }
  finally { loading(false); }
};
$("wrreset").onclick = async () => {
  if (!confirm(tr("Import किए सब rates हटाकर app के अपने rates वापस लें?", "Remove all imported rates and go back to the app's own?"))) return;
  const r = await api("/api/water_rates", { act: "reset" });
  if (r && r.ok) wrStatus(r.status);
};

// ---- Intze OHT drawings of the new OHTs of the last design (intze_api, user decisions 9-Nov-2026)
const IZ = { zone: "izzone", sbc: "izsbc", soil: "izsoil", vb: "izvb", depth: "izdepth", fck: "izfck", fckf: "izfckf", fy: "izfy", per: "izper" };
function izInputs() { const o = {}; for (const k in IZ) o[k] = $(IZ[k]).value; return o; }
function izRestore(q) { if (!q) return; for (const k in IZ) if (q[k] !== undefined && q[k] !== null && q[k] !== "") $(IZ[k]).value = q[k]; }
// the new OHTs of the last design, each with its own Design button (user decision 10-Nov-2026: one tank at a time,
// not all at once): its capacity, staging and whether its drawings are made (⚠ before the last design)
async function izList() {
  if (!$("pname").value) { $("izlist").innerHTML = ""; return; }
  let r = null; try { r = await api("/api/water_intze_list", { name: $("pname").value }); } catch (e) { r = null; }
  if (!r || !r.ok) { $("izlist").innerHTML = `<div class="hint">${esc((r && r.log) || tr("पहले Design चलाएँ", "run the Design first"))}</div>`; return; }
  if (!r.ohts.length) { $("izlist").innerHTML = `<div class="hint">${tr("आख़िरी design में कोई नई OHT नहीं - पुरानी टंकियों की drawing नहीं बनती", "no new OHT in the last design - the existing tanks are not drawn")}</div>`; return; }
  $("izlist").innerHTML = `<div style="overflow-x:auto"><table class="wz"><tr><th>OHT</th><th>KL</th><th>${tr("Staging m", "Staging m")}</th><th>${tr("Drawings", "Drawings")}</th><th></th></tr>` +
    r.ohts.map((o, i) => { const d = esc(o.made.slice(0, 5) + o.made.slice(10));         // "dd-mm hh:mm", the year in the title
      return `<tr><td style="white-space:nowrap">${esc(o.name)}</td><td>${fmt(o.capacity_kl)}</td><td>${o.staging_m}</td><td style="white-space:nowrap">${!o.made ? "-"
      : o.stale ? `<span class="wflag warn" style="padding:0 4px" title="${esc(o.made)} - ${tr("आख़िरी Design से पहले की - capacity / staging बदली हो सकती है, फिर बनाएँ", "made before the last Design - the capacity / staging may have changed, make them again")}">⚠ ${d}</span>`
      : `<span title="${esc(o.made)}: ${esc(Object.values(o.files).join(", "))}">✔ ${d}</span>`}</td>` +
      `<td><button data-iz="${i}" style="padding:1px 6px" title="${o.made ? tr("फिर Design करें (पुरानी files बदलेंगी)", "design again (the old files replaced)") : tr("सिर्फ़ इस टंकी का design और drawings", "this tank's design and drawings only")}">Design</button></td></tr>`; }).join("") + `</table></div>` +
    `<div class="hint" style="word-break:break-all">folder: ${esc(r.folder)}</div>`;
  document.querySelectorAll("#izlist button[data-iz]").forEach(b => b.onclick = () => izRun(r.ohts[+b.dataset.iz].name));
}
$("izbox").addEventListener("toggle", () => { if ($("izbox").open) izList(); });
function izRun(oht) {
  let r = null;
  longTask(tr(`Intze OHT ${oht}`, `Intze OHT ${oht}`), async () => {
    r = await api("/api/water_intze", { name: $("pname").value, intze: izInputs(), oht });
  }, () => { izList(); return !r || !r.ok ? [tr(`${oht}: drawings नहीं बनीं`, `${oht}: drawings not made`), (r && r.log) || "error", "err"]
    : [tr(`${oht}: Intze drawings तैयार`, `${oht}: Intze drawings ready`), `folder: ${r.folder}\n\n` +
       r.ohts.map(o => `${o.name}: ${o.capacity_kl} KL, staging ${o.staging_m} m - D ${o.D_m} m, ${o.columns} mm columns, ` +
         `annular raft ${o.raft_m} m dia (net SBC ${o.sbc}); ${o.concrete_m3} m³ concrete, ${o.steel_t} t steel` +
         (o.warnings.length ? "\n   ⚠ " + o.warnings.join("; ") : "")).join("\n") + (r.log ? "\n\n" + r.log : "") +
       "\n\n" + tr("हर टंकी: .dxf (AutoCAD, A1 sheets), .pdf (drawings), _calc.pdf (design calculation), _design.xlsx (calculation की तालिका, BBS, quantities)। निर्माण से पहले structural engineer से जाँच करवाएँ।",
                     "Each tank: .dxf (AutoCAD, A1 sheets), .pdf (drawings), _calc.pdf (design calculation), _design.xlsx (calculation table, BBS, quantities). Have a structural engineer check it before construction."), "ok"]; });
}

const lakh2 = v => v === null || v === undefined ? "-" :          // table: always 2 decimals, the columns line up
  Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

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
  if (mode === "dxf" && b.dataset.v !== "layout") { pick = null; $("nhint").textContent = HINT[tool] + " (औज़ार केवल Layout view में - Zones / Design में junctions नहीं दिखते)"; }
  if (b.dataset.v === "zones" && !wZoning) return;
  if (b.dataset.v === "design" && !wDesign) return;
  setView(b.dataset.v);
});
function legend(v) {
  $("legend").innerHTML = WLEG[v] || "";
}

function layoutReady(r) {
  layoutData = r;
  tblAfterDesign(null);
  zoneLayer.clearLayers(); designLayer.clearLayers();
  $("zd").hidden = false; $("viewseg").hidden = true; $("legend").innerHTML = "";
  popUi();
}
// where the population comes from: a layout's wards (made with it); a DXF network's wards drawn on the map (user
// 30-Oct-2026 - then the total below is not used); else the total given below, spread by pipe length
function popUi() {
  popSource();
  if (PJ) {                               // a projection: the total of the page is the base-year population itself
    $("poptot").hidden = true;
    $("popinfo").textContent += PJ.from_year
      ? tr(` - projection: ${PJ.from_year} की आबादी × ${PJ.ratio_from.ult.toFixed(3)} (+30 वर्ष ${PJ.years.ult})`,
           ` - projection: the ${PJ.from_year} population x ${PJ.ratio_from.ult.toFixed(3)} (+30 years ${PJ.years.ult})`)
      : tr(` - projection: आधार वर्ष की आबादी × ${PJ.ratio.ult.toFixed(3)} (+30 वर्ष)`,
           ` - projection: base-year population x ${PJ.ratio.ult.toFixed(3)} (+30 years)`);
  }
}
function popSource() {
  $("wtbox").hidden = mode !== "dxf";
  if (mode === "dxf" && wtTotal() > 0) {
    let onMap = 0; drawn.eachLayer(l => { if (l.kind === "ward" && wtRow(l.props.ward_no)) onMap++; });
    $("popinfo").textContent = tr(`वार्ड तालिका: ${WT.rows.length} वार्ड, project में ${fmt(wtTotal())} (${WT.year}); नक्शे पर सीमा ${onMap}`,
                                  `ward table: ${WT.rows.length} wards, ${fmt(wtTotal())} in the project (${WT.year}); boundaries on the map ${onMap}`);
    $("poptot").hidden = true;
    return;
  }
  if (mode === "dxf") {
    let wards = 0, pop = 0, noPop = 0;
    drawn.eachLayer(l => { if (l.kind === "ward") { wards++; const v = parseFloat(l.props.population); if (v > 0) pop += v; else noPop++; } });
    $("popinfo").textContent = wards
      ? tr(`${wards} वार्डों से ${pop.toLocaleString("en-IN")}` + (noPop ? ` (${noPop} में population नहीं)` : "") + "; वार्ड से बाहर के junctions पर 0",
           `${pop.toLocaleString("en-IN")} from ${wards} wards` + (noPop ? ` (${noPop} without population)` : "") + "; junctions in no ward: none")
      : tr("वार्ड नहीं - कुल population भरें (pipe लंबाई से पूरे network पर), या वार्ड खींचें / KML से लाएँ",
           "no wards - give the total population (spread by pipe length), or draw wards / read them from a KML");
    $("poptot").hidden = wards > 0;
    return;
  }
  const hasPop = layoutData && layoutData.population > 0;
  $("popinfo").textContent = hasPop ? `वार्ड / boundary से ${Number(layoutData.population).toLocaleString("en-IN")} (layout के समय)` : "वार्ड में population नहीं - नीचे कुल भरें";
  $("poptot").hidden = !!hasPop;
}

// ---- pipe / manhole tables of a design (user request 19-Oct-2026): every row with the manual checks; sort, search,
// only failing rows, click = the pipe / manhole on the map; editable cells (yellow = changed) and "design again" with
// the changes; CSV of the rows shown. Changes: WEDITS, sent with wInputs.
let WEDITS = { pipes: {}, junctions: {} };
const TBL = { tab: null, sort: null, dir: 1, rows: [], sel: null, RH: 23 };
const tnum = (x, d) => x === null || x === undefined || x === "" || Number.isNaN(x) ? "" : Number(x).toFixed(d);
const oneIn = s => s > 0 ? Math.round(1 / s) : "";
function tblTabs() {
  {
    if (!wDesign) return null;
    const sizes = wDesign.sizes || [];
    return {
      pipes: { title: tr("Pipes", "Pipes"), rows: wDesign.pipes, ed: WEDITS.pipes, cols: [
        { k: "label", h: "Pipe", l: 1 }, { k: "from", h: tr("से", "From"), l: 1 }, { k: "to", h: tr("तक", "To"), l: 1 },
        { k: "length", h: "L m", f: x => tnum(x, 1) },
        { k: "size", h: "Size", l: 1, edit: { field: "size", opts: sizes, get: r => r.size } },
        { k: "id_mm", h: "ID mm", f: x => tnum(x, 1) }, { k: "flow", h: "Q L/s", f: x => tnum(Math.abs(x), 2) },
        { k: "v", h: "v m/s", f: x => tnum(x, 2) },
        ...(wDesign.stages && wDesign.stages.length ? [{ k: "v_init", h: tr("v आधार वर्ष", "v base year"), f: x => tnum(x, 2) }] : []),
        { k: "hl_km", h: "Head loss m/km", f: x => tnum(x, 2) },
        { k: "oz", h: "OZ", l: 1 }, { k: "dma", h: "DMA", l: 1 }, { k: "checks", h: tr("जाँच", "Checks"), l: 1 }] },
      junctions: { title: tr("Junctions", "Junctions"), rows: wDesign.nodes, ed: WEDITS.junctions, cols: [
        { k: "label", h: "Junction", l: 1 },
        { k: "gl", h: "GL m", f: x => tnum(x, 2), edit: { field: "gl", get: r => r.gl } },
        { k: "head", h: "HGL m", f: x => tnum(x, 2) }, { k: "p", h: tr("दबाव m", "Head m"), f: x => tnum(x, 2) },
        { k: "q", h: tr("Peak माँग L/s", "Peak demand L/s"), f: x => tnum(x, 3) },
        { k: "pop", h: tr("आबादी", "Population"), f: x => tnum(x, 0), edit: { field: "pop", get: r => r.pop } },
        { k: "oz", h: "OZ", l: 1 }, { k: "dma", h: "DMA", l: 1 }, { k: "checks", h: tr("जाँच", "Checks"), l: 1 }] } };
  }
}
const cellText = (c, r) => { const v = r[c.k]; return c.f ? c.f(v) : Array.isArray(v) ? v.join("; ") : (v ?? ""); };
function tblEdits() { return WEDITS; }
function tblEditCount() { const e = tblEdits(); return Object.values(e).reduce((s, g) => s + Object.keys(g).length, 0); }
function tblNote() {
  const n = tblEditCount();
  $("tbledits").textContent = n ? tr(`${n} बदलाव (अगले design में लगेंगे)`, `${n} change(s) (used by the next design)`) : "";
}
function tblOpen(tab) {
  const T = tblTabs(); if (!T) return;
  TBL.tab = tab && T[tab] ? tab : (TBL.tab && T[TBL.tab] ? TBL.tab : Object.keys(T)[0]);
  $("tbl").hidden = false; map.invalidateSize();
  $("tbltabs").innerHTML = Object.entries(T).map(([k, t]) => `<button data-t="${k}" class="${k === TBL.tab ? "on" : ""}">${esc(t.title)} (${t.rows.length})</button>`).join("");
  $("tbltabs").querySelectorAll("button").forEach(b => b.onclick = () => { TBL.sort = null; TBL.sel = null; tblOpen(b.dataset.t); });
  tblBuild();
}
// column widths of a tab: by default all the same (the widest header fits; long text cut, the full text in the cell's
// tooltip); a handle at the right edge of each header drags a column wider / narrower (double-click: all back to the
// default). The widths dragged are kept per module and tab (this browser) - fixed while scrolling / filtering.
const TBL_CTX = document.createElement("canvas").getContext("2d");
const TBLW_KEY = "sewer_app_table_widths";
function tblSavedW() { try { return JSON.parse(localStorage.getItem(TBLW_KEY) || "{}"); } catch (e) { return {}; } }
function tblDefaultW(t) {
  TBL_CTX.font = '600 12px "Segoe UI", "Nirmala UI", sans-serif';
  const w = Math.max(98, ...t.cols.map(c => TBL_CTX.measureText(c.h).width + 26));    // header + sort arrow + handle
  return t.cols.map(() => Math.ceil(w));
}
function tblWidths(t) {
  const saved = tblSavedW()[`${MODULE}:${TBL.tab}`];
  return Array.isArray(saved) && saved.length === t.cols.length ? saved : tblDefaultW(t);
}
function tblSetW(t, W) {
  const all = tblSavedW();
  if (W) all[`${MODULE}:${TBL.tab}`] = W; else delete all[`${MODULE}:${TBL.tab}`];
  try { localStorage.setItem(TBLW_KEY, JSON.stringify(all)); } catch (e) { }
}
// the table's width: its columns, and an empty last column filling up to the right edge of the view - so that a
// column made narrower does not pull the table back under a horizontal scroll (the columns on its left stay put)
function tblFit(W) {
  const wrap = $("tblwrap"), sum = W.reduce((a, b) => a + b, 0);
  const fill = Math.max(0, wrap.scrollLeft + wrap.clientWidth - sum);
  const cols = $("tblt").querySelectorAll("col");
  W.forEach((x, i) => { if (cols[i]) cols[i].style.width = x + "px"; });
  if (cols[W.length]) cols[W.length].style.width = fill + "px";
  $("tblt").style.width = sum + fill + "px";
}
// double-click on a handle: the column as wide as its longest text (all rows of the tab) - to read it whole
function tblFitCol(i, t) {
  const c = t.cols[i];
  TBL_CTX.font = '12px "Segoe UI", "Nirmala UI", sans-serif';
  let best = "";
  for (const r of t.rows) { const x = String(cellText(c, r)); if (x.length > best.length) best = x; }
  TBL_CTX.font = '600 12px "Segoe UI", "Nirmala UI", sans-serif';
  const head = TBL_CTX.measureText(c.h).width + 26;
  TBL_CTX.font = '12px "Segoe UI", "Nirmala UI", sans-serif';
  const W = tblWidths(t).slice();
  W[i] = Math.ceil(Math.min(2400, Math.max(head, TBL_CTX.measureText(best).width + 22, c.edit ? 98 : 40)));
  tblSetW(t, W); tblFit(W);
}
// a header's handle dragged: that column's width follows the mouse; the columns on its left do not move
function tblResize(ev, i, t) {
  ev.preventDefault(); ev.stopPropagation();
  const W = tblWidths(t).slice(), x0 = ev.clientX, w0 = W[i];
  TBL.resizing = true; document.body.style.cursor = "col-resize";
  const move = e => { W[i] = Math.max(40, Math.round(w0 + e.clientX - x0)); tblFit(W); };
  const up = () => {
    document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up);
    document.body.style.cursor = ""; tblSetW(t, W);
    setTimeout(() => { TBL.resizing = false; }, 0);                    // the click that ends a drag does not sort
  };
  document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
}
function tblBuild() {
  const T = tblTabs(); if (!T || !T[TBL.tab]) return;
  const t = T[TBL.tab], q = $("tblq").value.trim().toLowerCase(), fail = $("tblfail").checked;
  let rows = t.rows.filter(r => (!fail || (r.checks && r.checks.length)) &&
    (!q || [r.label, r.from, r.to, ...(r.ins || []), ...(r.outs || []),
            ...(r.pieces || []).flatMap(p => [p.label, p.to])].some(x => x && String(x).toLowerCase().includes(q))));
  if (TBL.sort) {
    const c = t.cols.find(c => c.k === TBL.sort), get = c.sv || (r => { const v = r[c.k]; return Array.isArray(v) ? v.join("; ") : v; });
    rows = rows.slice().sort((a, b) => {
      const x = get(a), y = get(b);
      if (x === null || x === undefined || x === "") return 1;
      if (y === null || y === undefined || y === "") return -1;
      return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })) * TBL.dir;
    });
  }
  TBL.rows = rows;
  // the failing checks of all rows of this tab, counted
  const cnt = {}; for (const r of t.rows) for (const c of r.checks || []) cnt[c] = (cnt[c] || 0) + 1;
  $("tblsum").innerHTML = `${rows.length} / ${t.rows.length} ${tr("पंक्तियाँ", "rows")}` +
    (Object.keys(cnt).length ? " &nbsp; " + Object.entries(cnt).map(([k, v]) => `${esc(k)}: <b>${v}</b>`).join(", ") : ` &nbsp; ${tr("सब जाँचें ठीक", "all checks pass")}`);
  const W = tblWidths(t);
  const hint = tr("खींचकर चौड़ाई बदलें; double-click = पूरा text दिखे इतना चौड़ा", "drag to change the width; double-click = wide enough for the whole text");
  $("tblt").innerHTML = `<colgroup>${W.map(x => `<col style="width:${x}px">`).join("")}<col></colgroup><thead><tr>${t.cols.map((c, i) => `<th data-k="${c.k}" class="${c.l ? "l" : ""} ${TBL.sort === c.k ? "sorted" : ""}">${esc(c.h)}${TBL.sort === c.k ? (TBL.dir > 0 ? " ▲" : " ▼") : ""}<span class="rsz" data-i="${i}" title="${esc(hint)}"></span></th>`).join("")}</tr></thead><tbody></tbody>`;
  $("tblt").querySelectorAll("th").forEach(th => th.onclick = ev => {
    if (TBL.resizing || ev.target.classList.contains("rsz")) return;
    TBL.dir = TBL.sort === th.dataset.k ? -TBL.dir : 1; TBL.sort = th.dataset.k; tblBuild(); });
  $("tblt").querySelectorAll("th .rsz").forEach(h => {
    h.onmousedown = ev => tblResize(ev, +h.dataset.i, t);
    h.ondblclick = ev => { ev.stopPropagation(); tblFitCol(+h.dataset.i, t); };
  });
  $("tblwrap").scrollTop = 0;
  tblFit(W);
  tblRender();
}
// only the rows in sight are in the table (12,000 sewers stay quick); spacer rows keep the scroll height
function tblRender() {
  const T = tblTabs(); if (!T || !T[TBL.tab]) return;
  const t = T[TBL.tab], w = $("tblwrap"), RH = TBL.RH;
  const first = Math.max(0, Math.floor(w.scrollTop / RH) - 20), last = Math.min(TBL.rows.length, first + Math.ceil(w.clientHeight / RH) + 40);
  const html = [`<tr style="height:${first * RH}px"></tr>`];
  for (let i = first; i < last; i++) {
    const r = TBL.rows[i], e = t.ed[r.label] || {}, bad = new Set((r.checks || []).length ? ["checks"] : []);
    html.push(`<tr class="trow ${TBL.sel === r.label ? "sel" : ""}" data-i="${i}">` + t.cols.map(c => {
      const ed = c.edit, chg = ed && e[ed.field] !== undefined;
      const txt = chg ? (ed.show ? ed.show(e[ed.field]) : e[ed.field]) : cellText(c, r);
      return `<td class="${c.l ? "l" : ""} ${ed ? "ed" : ""} ${chg ? "chg" : ""} ${bad.has(c.k) ? "bad" : ""}" data-k="${c.k}"` +
        `${chg ? ` title="${esc(tr("बदला हुआ - design में: ", "changed - in the design: ") + cellText(c, r))}"`
               : c.l && String(txt).length > 30 ? ` title="${esc(txt)}"` : ""}>${esc(txt)}</td>`;
    }).join("") + `</tr>`);
  }
  html.push(`<tr style="height:${(TBL.rows.length - last) * RH}px"></tr>`);
  $("tblt").tBodies[0].innerHTML = html.join("");
}
$("tblwrap").addEventListener("scroll", () => requestAnimationFrame(tblRender));
$("tblq").addEventListener("input", tblBuild);
$("tblfail").addEventListener("change", tblBuild);
$("tblt").addEventListener("click", ev => {
  const td = ev.target.closest("td"), tr_ = ev.target.closest("tr.trow");
  if (!tr_ || !td || ev.target.closest("input,select")) return;
  const T = tblTabs(), r = TBL.rows[+tr_.dataset.i];
  if (!T || !T[TBL.tab] || !r) return;                       // the design changed under the table
  const t = T[TBL.tab], c = t.cols.find(c => c.k === td.dataset.k);
  TBL.sel = r.label; tblShowOnMap(r);
  if (c && c.edit) tblEditCell(td, r, t, c); else tblRender();
});
function tblShowOnMap(r) {
  hiLayer.clearLayers(); map.closePopup();
  let shape = null;
  if (r.pts || r.vpts) shape = L.polyline(r.vpts || r.pts, { color: "#ffd600", weight: 9, opacity: .8, interactive: false });
  else if (r.latlng) shape = L.circleMarker(r.latlng, { radius: 11, color: "#ffd600", weight: 4, fill: false, interactive: false });
  else if (layoutData) { const c = (layoutData.conduits || []).find(c => c.label === r.label);
    if (c) shape = L.polyline(c.pts, { color: "#ffd600", weight: 9, opacity: .8, interactive: false }); }
  if (!shape) return;
  if (curView !== "design") setView("design");
  shape.addTo(hiLayer);
  if (shape.getBounds) map.fitBounds(shape.getBounds(), { maxZoom: Math.max(map.getZoom(), 18), padding: [60, 60] });
  else map.setView(shape.getLatLng(), Math.max(map.getZoom(), 18));
}
function tblEditCell(td, r, t, c) {
  const ed = c.edit, e = t.ed[r.label] || {};
  const cur = e[ed.field] !== undefined ? e[ed.field] : ed.get(r);
  const shown = ed.show ? ed.show(cur) : cur;
  if (ed.opts) {
    const opts = ed.opts.map(o => typeof o === "object" ? o : { v: o, t: o });
    td.innerHTML = `<select><option value="">${tr("— design वाला —", "— as designed —")}</option>` +
      opts.map(o => `<option value="${esc(o.v)}" ${String(o.v) === String(cur) && e[ed.field] !== undefined ? "selected" : ""}>${esc(o.t)}</option>`).join("") + `</select>`;
  } else td.innerHTML = `<input type="number" step="any" value="${esc(shown ?? "")}">`;
  const inp = td.firstChild; inp.focus();
  const done = save => {
    if (save) {
      const raw = inp.value.trim();
      let v = raw === "" ? null : ed.opts ? (typeof (ed.opts[0] ?? {}) === "object" ? Number(raw) : raw) : Number(raw);
      if (v !== null && ed.parse) v = ed.parse(v);
      if (v !== null && typeof v === "number" && !Number.isFinite(v)) v = null;
      const g = t.ed; const x = Object.assign({}, g[r.label]);
      if (v === null) delete x[ed.field]; else x[ed.field] = v;
      if (Object.keys(x).length) g[r.label] = x; else delete g[r.label];
      tblNote();
    }
    tblRender();
  };
  inp.addEventListener("keydown", k => { if (k.key === "Enter") done(true); if (k.key === "Escape") done(false); });
  inp.addEventListener(ed.opts ? "change" : "blur", () => done(true));
  if (ed.opts) inp.addEventListener("blur", () => setTimeout(() => done(false), 0));
}
$("tblbtn").onclick = () => $("tbl").hidden ? tblOpen() : ($("tbl").hidden = true, map.invalidateSize());
$("tblwreset").onclick = () => { const t = tblTabs() && tblTabs()[TBL.tab]; if (!t) return; tblSetW(t, null); tblBuild(); };
$("tblclose").onclick = () => { $("tbl").hidden = true; map.invalidateSize(); };
$("tblclear").onclick = () => {
  WEDITS = { pipes: {}, junctions: {} };
  tblNote(); tblOpen(TBL.tab);
};
$("tblrun").onclick = () => {
  return $("wdrun").onclick();
};
$("tblcsv").onclick = () => {
  const t = tblTabs()[TBL.tab], q = v => /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
  const lines = [t.cols.map(c => q(c.h)).join(",")].concat(TBL.rows.map(r => t.cols.map(c => q(String(cellText(c, r)))).join(",")));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
  a.download = `${$("pname").value || "project"}_${TBL.tab}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
// another project opened: no changes, no table
function tblReset() {
  WEDITS = { pipes: {}, junctions: {} }; TBL.sel = null; TBL.sort = null;
  tblAfterDesign(null);
}
// after a design is shown: the changes it was made with, the table button, the table itself if open
function tblAfterDesign(r) {
  if (r && r.edits) {
    WEDITS = { pipes: Object.assign({}, r.edits.pipes), junctions: Object.assign({}, r.edits.junctions) };
  }
  $("tblrow").hidden = !r; tblNote();
  if (!r) { $("tbl").hidden = true; map.invalidateSize(); return; }
  if (!$("tbl").hidden) tblOpen(TBL.tab);
}
