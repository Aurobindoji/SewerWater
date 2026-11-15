// The sewer map page (map.html), part 7 of 9: the pipe / manhole tables of a design, the last zoning / design shown again.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---- pipe / manhole tables of a design (user request 19-Oct-2026): every row with the manual checks; sort, search,
// only failing rows, click = the pipe / manhole on the map; editable cells (yellow = changed) and "design again" with
// the changes; CSV of the rows shown. The changes (SEDITS) are sent with zdInputs.
let SEDITS = { conduits: {}, manholes: {}, trunk: [] };
const TBL = { tab: null, sort: null, dir: 1, rows: [], sel: null, RH: 23 };
const tnum = (x, d) => x === null || x === undefined || x === "" || Number.isNaN(x) ? "" : Number(x).toFixed(d);
const oneIn = s => s > 0 ? Math.round(1 / s) : "";
function tblTabs() {
  if (!designData) return null;
  const sizes = (designData.sizes || []).map(z => ({ v: z.id_mm, t: z.nominal || `${z.id_mm} mm` }));
  return {
    conduits: { title: "Conduits", rows: designData.sewers, ed: SEDITS.conduits, cols: [
      { k: "label", h: "Conduit", l: 1 }, { k: "from", h: tr("से", "From"), l: 1 }, { k: "to", h: tr("तक", "To"), l: 1 },
      { k: "length", h: "L m", f: x => tnum(x, 1) },
      { k: "D", h: "D mm", f: x => tnum(x, 0), edit: { field: "D", opts: sizes, get: r => r.D } },
      { k: "slope", h: "1 in", f: oneIn, sv: r => r.slope > 0 ? 1 / r.slope : null,
        edit: { field: "slope", get: r => r.slope, show: oneIn, parse: v => v > 0 ? 1 / v : null } },
      { k: "s_min", h: tr("Table 3.13 1 in", "Table 3.13 1 in"), f: oneIn, sv: r => r.s_min > 0 ? 1 / r.s_min : null },
      { k: "q", h: "Q L/s", f: x => tnum(x, 2) }, { k: "v", h: "v m/s", f: x => tnum(x, 2) }, { k: "dd", h: "d/D", f: x => tnum(x, 2) },
      ...(designData.stages && designData.stages.length ? [
        { k: "v_init", h: tr("v आधार वर्ष", "v base year"), f: x => tnum(x, 2) },
        { k: "v_mid", h: tr("v +15 वर्ष", "v +15 years"), f: x => tnum(x, 2) }] : []),
      { k: "depth_up", h: tr("गहराई u/s", "Depth u/s"), f: x => tnum(x, 2) }, { k: "depth_dn", h: tr("गहराई d/s", "Depth d/s"), f: x => tnum(x, 2) },
      { k: "il_up", h: "IL u/s", f: x => tnum(x, 3) }, { k: "il_dn", h: "IL d/s", f: x => tnum(x, 3) },
      { k: "gl_up", h: "GL u/s", f: x => tnum(x, 2) }, { k: "gl_dn", h: "GL d/s", f: x => tnum(x, 2) },
      { k: "cover_dn", h: "Cover d/s", f: x => tnum(x, 2) }, { k: "checks", h: tr("जाँच", "Checks"), l: 1 },
      { k: "flags", h: tr("सूचना", "Flags"), l: 1 },
      { k: "trunk", h: "Trunk (3.31)", l: 1, toggle: true, f: x => x ? "✔ trunk" : "",
        tip: tr("Click = यह sewer trunk / outfall sewer (घरों के connection नहीं): manholes CPHEEO Table 3.31 (p3-127) की दूरी पर - " +
                "600 mm तक 60 m, 900 तक 90 m, 1200 तक 120 m, 1500 तक 150 m; दोबारा click = हटाएँ। \"बदलाव के साथ design दोबारा\" से लगेगा",
                "Click = this sewer is a trunk / outfall sewer (no house connections): manholes at the spacing of CPHEEO Table 3.31 " +
                "(p3-127) - up to 600 mm 60 m, 900 90 m, 1200 120 m, 1500 150 m; click again = not trunk. Used by \"design again with the changes\"") },
      { k: "pieces", h: tr("टुकड़े (नए MH से)", "Pieces (new MH)"), l: 1, f: x => (x || []).map(p => p.label).join(", "),
        sv: r => (r.pieces || []).length }] },
    manholes: { title: "Manholes", rows: designData.manholes || [], ed: SEDITS.manholes, cols: [
      { k: "label", h: "Manhole", l: 1 },
      { k: "new", h: tr("नया MH", "New MH"), l: 1, f: x => !x ? "" : x.startsWith("bend") ? tr("मोड़ ", "bend ") + x.replace("bend ", "").replace(" deg", "°") : tr("30 m दूरी", "spacing"),
        tip: tr("मोड़ पर / दूरी के लिए डाला गया नया manhole - उसका GL sewer के साथ interpolate किया है; survey का GL हो तो 'GL m' में भरें",
                "A new manhole put in at a bend / for the spacing - its GL is interpolated along the sewer; give the survey GL in 'GL m'") },
      { k: "gl", h: "GL m", f: x => tnum(x, 3), edit: { field: "gl", get: r => r.gl } },
      { k: "invert", h: tr("Invert (जाने वाला) m", "Invert (outgoing) m"), f: x => tnum(x, 3), edit: { field: "invert", get: r => r.invert } },
      { k: "depth", h: tr("गहराई m", "Depth m"), f: x => tnum(x, 2) }, { k: "max_in_drop", h: "Drop m", f: x => tnum(x, 2) },
      { k: "ins", h: tr("आने वाले", "Incoming"), l: 1 }, { k: "outs", h: tr("जाने वाले", "Outgoing"), l: 1 },
      { k: "checks", h: tr("जाँच", "Checks"), l: 1 }, { k: "drop", h: "Drop manhole", l: 1 }] } };
}
const cellText = (c, r) => { const v = r[c.k]; return c.f ? c.f(v) : Array.isArray(v) ? v.join("; ") : (v ?? ""); };
function tblEdits() { return SEDITS; }
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
// default). The widths dragged are kept per tab (this browser) - fixed while scrolling / filtering.
const TBL_CTX = document.createElement("canvas").getContext("2d");
const TBLW_KEY = "sewer_app_table_widths";
function tblSavedW() { try { return JSON.parse(localStorage.getItem(TBLW_KEY) || "{}"); } catch (e) { return {}; } }
function tblDefaultW(t) {
  TBL_CTX.font = '600 12px "Segoe UI", "Nirmala UI", sans-serif';
  const w = Math.max(98, ...t.cols.map(c => TBL_CTX.measureText(c.h).width + 26));    // header + sort arrow + handle
  return t.cols.map(() => Math.ceil(w));
}
function tblWidths(t) {
  const saved = tblSavedW()[`sewer:${TBL.tab}`];
  return Array.isArray(saved) && saved.length === t.cols.length ? saved : tblDefaultW(t);
}
function tblSetW(t, W) {
  const all = tblSavedW();
  if (W) all[`sewer:${TBL.tab}`] = W; else delete all[`sewer:${TBL.tab}`];
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
  $("tblt").innerHTML = `<colgroup>${W.map(x => `<col style="width:${x}px">`).join("")}<col></colgroup><thead><tr>${t.cols.map((c, i) => `<th data-k="${c.k}" class="${c.l ? "l" : ""} ${TBL.sort === c.k ? "sorted" : ""}"${c.tip ? ` title="${esc(c.tip)}"` : ""}>${esc(c.h)}${TBL.sort === c.k ? (TBL.dir > 0 ? " ▲" : " ▼") : ""}<span class="rsz" data-i="${i}" title="${esc(hint)}"></span></th>`).join("")}</tr></thead><tbody></tbody>`;
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
      if (c.toggle) {                                  // trunk: marked now / in the design
        const on = isTrunk(r), chg = on !== !!r.trunk;
        return `<td class="l ed ${chg ? "chg" : ""}" data-k="${c.k}" title="${esc(c.tip)}">${on ? "✔ trunk" : ""}</td>`;
      }
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
  if (c && c.toggle) { toggleTrunk(r); tblNote(); tblRender(); }
  else if (c && c.edit) tblEditCell(td, r, t, c); else tblRender();
});
// trunk sewers (user request 21-Oct-2026): marked by the network's own conduit (a piece cut by a new manhole marks
// its whole conduit) - the next design spaces their manholes by Table 3.31 instead of 30 m
const isTrunk = r => SEDITS.trunk.includes(r.orig || r.label);
function toggleTrunk(r) {
  const o = r.orig || r.label;
  SEDITS.trunk = isTrunk(r) ? SEDITS.trunk.filter(x => x !== o) : SEDITS.trunk.concat([o]);
}
function tblShowOnMap(r) {
  hiLayer.clearLayers(); map.closePopup();
  let shape = null;
  if (r.pts || r.vpts) shape = L.polyline(r.vpts || r.pts, { color: "#ffd600", weight: 9, opacity: .8, interactive: false });
  else if (r.latlng) shape = L.circleMarker(r.latlng, { radius: 11, color: "#ffd600", weight: 4, fill: false, interactive: false });
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
  SEDITS = { conduits: {}, manholes: {}, trunk: [] };
  tblNote(); tblOpen(TBL.tab);
};
$("tblrun").onclick = () => {
  const opt = (zoningData && zoningData.options.find(o => o.option === designData.summary.option)) || { option: designData.summary.option };
  runDesign(opt);
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
  SEDITS = { conduits: {}, manholes: {}, trunk: [] }; TBL.sel = null; TBL.sort = null;
  tblAfterDesign(null);
}
// after a design is shown: the changes it was made with, the table button, the table itself if open
function tblAfterDesign(r) {
  if (r && r.edits) {
    SEDITS = { conduits: Object.assign({}, r.edits.conduits), manholes: Object.assign({}, r.edits.manholes),
               trunk: (r.edits.trunk || []).slice() };
  }
  $("tblrow").hidden = !r; tblNote();
  if (!r) { $("tbl").hidden = true; map.invalidateSize(); return; }
  if (!$("tbl").hidden) tblOpen(TBL.tab);
}

$("zexport").onclick = () => {
  if (!curOption) return;
  let r = null;
  // with a design the zones are drawn into a copy of its plan drawing - a large network takes a while
  longTask(tr("Export (DXF + KML + Excel)", "Export (DXF + KML + Excel)"), async () => {
    r = await api("/api/zoning_export", { name: $("pname").value, option: curOption.option });
  }, () => !r || !r.ok ? [tr("Export नहीं हुआ", "Export failed"), (r && r.log) || "error", "err"] : [tr("Export तैयार", "Export ready"), exportMsg(r), "ok"]);
};
function exportMsg(r) {
  return `Option ${curOption.option} - folder: ${r.folder}\n\n` +
    `AutoCAD : ${r.files.dxf.split(/[\\/]/).pop()}  (drawing वाले coordinates; layers ZONE_BOUNDARY_n, SUBZONE_BOUNDARY_x, ZONE_NAME, SUBZONE_NAME, STP, PS, SEWER_ZONE_n, WARN_MH_OVERLAP = लाल ✕)\n` +
    (r.design ? tr(`Design भी इसी drawing में: ${r.design} (layers SEW_PIPE, SEW_PIPE_TEXT, SEW_MH, SEW_MH_TEXT, SEW_FLOW_ARROW ...; SEWER_ZONE_n बंद)\n`,
                   `The design is in this drawing too: ${r.design} (layers SEW_PIPE, SEW_PIPE_TEXT, SEW_MH, SEW_MH_TEXT, SEW_FLOW_ARROW ...; SEWER_ZONE_n off)\n`)
              : tr("इस option का ताज़ा design नहीं - drawing में केवल zoning (पहले Design चलाएँ)\n",
                   "no current design of this option - the drawing has the zoning only (run the Design first)\n")) +
    `Google Earth : ${r.files.kml.split(/[\\/]/).pop()}\n` +
    `Excel : ${r.files.xlsx.split(/[\\/]/).pop()}  (Summary, Zones, Sewers)`;
}

// ---- the last zoning / design of a project, shown again when it is opened (reload, app restart)
async function restoreResults(name, conduits) {
  const r = await api("/api/last_results?name=" + encodeURIComponent(name));
  if (!r.ok || !r.network_saved) return;
  // keep what the opened layout already gave (its manholes - for the STP drawn on the map -, marks, population)
  layoutReady(Object.assign({ marks: [], population: 0 }, layoutData || {}, { conduits: conduits() }));
  const q = (r.zoning || r.design || {}).req || {};
  const set = (id, v) => { if (v !== undefined && v !== null && v !== "") $(id).value = v; };
  set("catalog", q.catalog); if ($("catalog").onchange) $("catalog").onchange(); set("joint", q.joint);
  set("lpcd", q.sewage_lpcd); set("sdepth", q.start_depth); set("stp", q.stp); set("maxz", q.max_zones); set("poptot", q.pop_total);
  set("zmode", q.mode); zmodeChanged(); set("maxdepth", q.max_depth);
  $("bdrop").checked = q.bend_drop !== false;                  // a run saved before this setting: on (CPHEEO)
  $("mhsp").value = q.mh_spacing || 30;                          // a run saved before this setting: 30 m (CPHEEO 3.71.1)
  $("bangle").value = q.bend_angle || 20;                        // ... and 20 deg (project decision)
  stageRestore((r.design || r.zoning || {}).req || {});      // the stages belong to the design
  if (r.zoning) {
    renderZoning(r.zoning, r.zoning.stale ? `पुरानी zoning (${r.zoning.time}) - उसके बाद network बदला, फिर से चलाएँ` : `पिछली zoning (${r.zoning.time})`);
    if (r.design) {
      const i = r.zoning.options.findIndex(o => o.option === r.design.summary.option);
      if (i >= 0) showOption(r.zoning.options[i]);
      renderDesign(r.design, `पिछला design (${r.design.time})`);
    }
  }
}
