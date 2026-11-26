// The sewer map page (map.html), part 5 of 9: the server calls, saving, the names on the map, a click on a sewer / manhole.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---------------------------------------------------------------- server calls, saving
function status(msg, cls) { const s = $("status"); s.textContent = msg; s.className = "status " + (cls || ""); }
// the run's token the server wrote into this page (rewrite stage 2, 26-Nov-2026): every POST carries it
const APP_TOKEN = (document.querySelector('meta[name="app-token"]') || {}).content || "";
async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json", "X-App-Token": APP_TOKEN }, body: JSON.stringify(body) } : {});
  return r.json();
}
async function refreshList() {
  try {
    const r = await api("/api/projects");
    $("plist").innerHTML = '<option value="">— Saved Projects —</option>' +
      r.projects.map(p => `<option value="${esc(p.name)}">${esc(p.name)}${p.kind === "dxf" ? " (DXF)" : ""}</option>`).join("");
  } catch (e) { /* page opened without the server */ }
}
let dirty = false;
function changed() {
  if (mode === "dxf" && NET) { if (selected && !drawn.hasLayer(selected)) select(null); return saveDxfBarriers(); }
  if (mode !== "kml") return;
  dirty = true;
  summary();
  if (selected && !drawn.hasLayer(selected)) select(null);
  try { localStorage.setItem(LS_DRAFT, JSON.stringify({ name: $("pname").value, kml: toKML() })); } catch (e) { }
}
$("psave").onclick = async () => {
  if (mode === "dxf" && NET) {                     // a DXF network: the corrected network + the list of its changes
    const r = await api("/api/net_save", { name: NET.name });
    if (!r.ok) return status("सहेजा नहीं जा सका: " + r.log, "err");
    const base = f => f.split(/[\\/]/).pop();
    return status(tr(`सहेजा: ${base(r.files.manholes)}, बदलावों की सूची ${base(r.files.edits)}`,
                     `saved: ${base(r.files.manholes)}, list of changes ${base(r.files.edits)}`), "ok");
  }
  try { const r = await api("/api/save", { name: $("pname").value, kml: toKML() });
    $("pname").value = r.name; status(`सहेजा: ${r.path}`, "ok"); dirty = false; refreshList(); remember(r.name, "kml");
  } catch (e) { status("सहेजा नहीं जा सका: " + e, "err"); }
};
$("popen").onclick = async () => {
  const nm = $("plist").value; if (!nm) return;
  if (dirty && drawn.getLayers().length && !confirm("अभी का बिना सहेजा काम हट जाएगा। खोलें?")) return;
  await withLoading(tr(`"${nm}" खुल रहा है …`, `Opening "${nm}" …`), async () => {
    const r = await api("/api/project?name=" + encodeURIComponent(nm));
    if (!r.ok) return status(r.log, "err");
    if (r.kind === "dxf") return loadNet(r.name);
    await openKml(r.name, r.kml);
  });
};
// a project drawn on the map: its drawing, and the layout / zoning / design made last (kept on the server). It is
// remembered, so that a page reload (F5) opens it again with all of them - not only the drawing.
async function openKml(name, kml, unsaved) {
  setMode("kml"); hasBase() || gmap.addTo(map);
  $("pname").value = name; const n = fromKML(kml, true); dirty = !!unsaved;
  if (unsaved) try { localStorage.setItem(LS_DRAFT, JSON.stringify({ name, kml })); } catch (e) { }
  remember(name, "kml");
  status(`खोला: ${n.road} सड़कें, ${n.ward} वार्ड, ${n.spot} spot levels`, "ok");
  $("stp").value = ""; $("zd").hidden = true; layoutData = null;
  const lr = await api("/api/layout_result?name=" + encodeURIComponent(name));
  if (lr.ok) { showResult(lr); layoutReady(lr); status(`खोला: ${n.road} सड़कें, ${n.ward} वार्ड; पहले बना layout भी दिखाया`, "ok");
    await restoreResults(name, () => lr.conduits); }
  if (unsaved) status("खोला - नक्शे के बिना सहेजे बदलाव भी वापस लाए गए ('Save करें' दबाएँ)", "ok");
  return n;
}
$("pnew").onclick = () => {
  if (drawn.getLayers().length && !confirm("नक्शे का सब कुछ हटाएँ?")) return;
  setMode("kml"); hasBase() || gmap.addTo(map); NET = null; netLayer.clearLayers(); remember(null);
  drawn.clearLayers(); result.clearLayers(); zoneLayer.clearLayers(); designLayer.clearLayers(); select(null);
  $("pname").value = "new_project"; $("files").innerHTML = ""; $("zd").hidden = true; layoutData = null; $("stp").value = "";
  $("log").hidden = true; changed(); dirty = false;
};
$("kmlget").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([toKML()], { type: "application/vnd.google-earth.kml+xml" }));
  a.download = ($("pname").value || "project") + ".kml"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
$("kmlopen").onclick = () => $("kmlfile").click();
$("kmlfile").onchange = async e => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  loading(true, tr(`${f.name} पढ़ रहे हैं …`, `Reading ${f.name} …`));
  try {
    let text;
    if (/\.kmz$/i.test(f.name)) {
      const b = new Uint8Array(await f.arrayBuffer()); let s = "";
      for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
      const r = await api("/api/kmz", { data: btoa(s) }); if (!r.ok) throw new Error(r.log); text = r.kml;
    } else text = await f.text();
    const replace = !drawn.getLayers().length || confirm("नक्शे का अभी का काम हटाकर यह KML खोलें? (Cancel = इसमें जोड़ें)");
    const n = fromKML(text, replace);
    if (replace) $("pname").value = f.name.replace(/\.(kml|kmz)$/i, "");
    status(`पढ़ा: ${n.road} सड़कें, ${n.boundary} boundary, ${n.ward} वार्ड, ${n.spot} spot levels, ${n.stp} STP` +
      (n.skipped ? `; ${n.skipped} बिंदु बिना GL के छोड़े` : ""), "ok");
  } catch (err) { status("KML नहीं खुला: " + err.message, "err"); }
  finally { loading(false); }
};
$("glmode").onchange = () => { $("flatrow").style.display = $("glmode").value === "flat" ? "" : "none"; summary(); };
$("showres").onchange = () => { if ($("showres").checked) result.addTo(map); else map.removeLayer(result); drawOverlay(); };
$("mhlabels").onchange = () => drawOverlay();

$("run").onclick = async () => {
  const s = summary();
  if (!s.roads) return status("पहले सड़कें खींचें।", "err");
  if ($("glmode").value === "spots" && s.spots < 3) return status("कम से कम 3 spot levels (GL के साथ) चाहिए, या GL का दूसरा तरीका चुनें।", "err");
  if (editing) toggleEdit(false);
  stopDraw();
  status("Layout बन रहा है …"); $("run").disabled = true;
  try {
    const r = await api("/api/layout", { name: $("pname").value, kml: toKML(), gl_mode: $("glmode").value,
      flat_gl: $("flatgl").value, snap: parseFloat($("snapm").value) || 1, node_prefix: $("lnpre").value.trim(), pipe_prefix: $("lppre").value.trim(), spacing: isNaN(parseFloat($("spacing").value)) ? 30 : parseFloat($("spacing").value) });
    $("log").hidden = false; $("log").textContent = r.log || "";
    if (!r.ok) { status("Layout नहीं बना - नीचे का संदेश देखें।", "err"); return; }
    dirty = false; refreshList();
    showResult(r);
    layoutReady(r);
    remember(r.name || $("pname").value, "kml");                 // the layout run saved the project
  } catch (e) { status("Server से संपर्क नहीं: " + e, "err"); }
  finally { $("run").disabled = false; }
};

// ---- written on the map for the view shown: manhole name (zoom 17+) with GL (18+), sewer number (18+) and - once
// designed, the flow known - a flow arrow on every sewer (17+); fewer zoomed out, where they would lie on top of each
// other. Only what is in sight is drawn, again after every move / zoom.
const overlay = L.layerGroup().addTo(map);
let curView = "layout";
const f2 = x => x === null || x === undefined || x === "" ? "-" : Number(x).toFixed(2);
// a loop cut by the zoning: the cut sewer starts at its own head manhole '<MH>-C1' at the place of <MH>, not joined
// to it (its invert well above, only its own sewage). On the map it is drawn CUT_GAP_M along its sewer, so that the
// sewer is seen not to leave <MH> - drawn on <MH> the sewage looked split in two there.
const CUT_RE = /-C\d+$/, CUT_GAP_M = 3;
function cutHeads(sewers) {
  const hasIn = new Set(sewers.map(d => d.to));
  for (const d of sewers) {
    d.vpts = d.pts;
    d.cut = CUT_RE.test(d.from) && !hasIn.has(d.from);
    // the gap along the sewer's first stretch (a sewer is drawn with its bends); its first piece starts there too
    const gap = pts => { const a = pts[0], b = pts[1], seg = L.latLng(a).distanceTo(L.latLng(b));
      if (!d.cut || seg <= 2 * CUT_GAP_M) return pts;
      const f = CUT_GAP_M / seg; return [[a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f], ...pts.slice(1)]; };
    d.vpts = gap(d.pts);
    for (const [i, p] of (d.pieces || []).entries()) p.vpts = i ? p.pts : gap(p.pts);
  }
}
function designNodes(sewers) {
    const mh = {};
    for (const d of sewers) {
      const P = d.vpts || d.pts;
      for (const [n, ll, gl, il, dep] of [[d.from, P[0], d.gl_up, d.il_up, d.depth_up], [d.to, P[P.length - 1], d.gl_dn, d.il_dn, d.depth_dn]]) {
        const m = mh[n] || (mh[n] = { label: n, latlng: ll, gl, il: null, depth: null, ins: [], outs: [], cut: d.cut && n === d.from });
        if (m.gl === null || m.gl === undefined) m.gl = gl;
        if (il !== null && il !== undefined && (m.il === null || il < m.il)) m.il = il;
        if (dep !== null && dep !== undefined && (m.depth === null || dep > m.depth)) m.depth = dep;
      }
      mh[d.from].outs.push({ label: d.label, il: d.il_up }); mh[d.to].ins.push({ label: d.label, il: d.il_dn });
    }
    return Object.values(mh);
}
function viewData() {
  if (curView === "design" && designData && map.hasLayer(designLayer))
    return { mhs: designNodes(designData.sewers), arrows: true,       // a sewer cut by new manholes: each piece
             cos: designData.sewers.flatMap(d => d.pieces && d.pieces.length ? d.pieces.map(p => ({ label: p.label, pts: p.vpts || p.pts }))
                                                                            : [{ label: d.label, pts: d.vpts || d.pts }]) };
  if (curView === "layout" && mode === "kml" && layoutData && layoutData.manholes && map.hasLayer(result))
    return { mhs: layoutData.manholes, arrows: false,
             cos: layoutData.conduits };
  if (curView === "layout" && mode === "dxf" && NET && map.hasLayer(netLayer))
    return { mhs: Object.entries(NET.nodes).filter(([, v]) => v.latlng).map(([n, v]) => ({ label: n, latlng: v.latlng, gl: v.gl })),
             cos: Object.values(NET.conds), arrows: false };
  return null;
}
// a pipe label in as few lines as fit in w px: whole, then "P-n" / the rest, then one part per line (at its commas)
const LABEL_CTX = document.createElement("canvas").getContext("2d");
LABEL_CTX.font = 'italic 600 9.5px "Segoe UI", sans-serif';
function wrapLabel(text, w) {
  const parts = String(text).split(", ");
  const tries = [[parts.join(", ")]];
  if (parts.length > 2) tries.push([parts[0], parts.slice(1).join(", ")]);
  if (parts.length > 1) tries.push(parts);
  for (const t of tries) if (Math.max(...t.map(x => LABEL_CTX.measureText(x).width)) <= w) return t;
  return tries[tries.length - 1];
}
function drawOverlay() {
  overlay.clearLayers();
  const vd = viewData(); if (!vd) return;
  const z = map.getZoom(), b = map.getBounds().pad(0.2), lab = $("mhlabels").checked;
  const mark = (ll, cls, html, anchor) => L.marker(ll, { interactive: false, keyboard: false,
    zIndexOffset: cls === "flowarrow" ? 5000 : 0,                       // an arrow is never under a label
    icon: L.divIcon({ className: cls, html, iconSize: null, iconAnchor: anchor }) }).addTo(overlay);
  if (lab && z >= 17)
    for (const m of vd.mhs) {
      if (!b.contains(m.latlng)) continue;
      const gl = z >= 18 && m.gl !== null && m.gl !== undefined ? `<br><span>GL ${Number(m.gl).toFixed(2)}</span>` : "";
      mark(m.latlng, "mhlab", `<div>${esc(m.label)}${gl}</div>`, [-6, 7]);
    }
  // a point at a share of the way ALONG a pipe (it may follow the bends of its road) and the direction there
  const along = (P, f) => {
    const tot = P.reduce((s_, p, i) => i ? s_ + p.distanceTo(P[i - 1]) : 0, 0);
    let goal = tot * f;
    for (let i = 1; i < P.length; i++) {
      const L_ = P[i].distanceTo(P[i - 1]);
      if (goal <= L_ || i === P.length - 1) {
        const t = L_ ? Math.min(1, goal / L_) : 0;
        return { p: P[i - 1].add(P[i].subtract(P[i - 1]).multiplyBy(t)), dx: P[i].x - P[i - 1].x, dy: P[i].y - P[i - 1].y, tot };
      }
      goal -= L_;
    }
    return { p: P[0], dx: 1, dy: 0, tot };
  };
  for (const c of vd.cos) {
    const P = c.pts.map(x => map.latLngToLayerPoint(L.latLng(x)));
    const m = along(P, 0.5), len = m.tot;
    const mid = map.layerPointToLatLng(m.p);
    if (!b.contains(mid)) continue;
    if (len < 14) continue;                                                  // too short on screen
    if (vd.arrows && z >= 17 && c.arrow !== false) {                         // ON the pipe, along its direction there
      const deg = Math.atan2(m.dy, m.dx) * 180 / Math.PI;
      mark(mid, "flowarrow", `<i style="transform:rotate(${deg.toFixed(1)}deg)"></i>`, [0, 0]);
    }
    if (lab && z >= 18 && len >= 30) {                                       // the label beside the pipe, parallel to it
      // on the pipe's longest straight piece (it may follow the bends of its road), in its middle, upright, above the
      // line (its near edge 5 px off it - clear of the arrow on the line); longer than the piece: wrapped at commas
      let i0 = 1, best = -1;
      for (let i = 1; i < P.length; i++) { const d = P[i].distanceTo(P[i - 1]); if (d > best) { best = d; i0 = i; } }
      const A = P[i0 - 1], B = P[i0];
      let ux = B.x - A.x, uy = B.y - A.y; const k = Math.hypot(ux, uy) || 1; ux /= k; uy /= k;
      if (ux < 0 || (Math.abs(ux) < 1e-9 && uy > 0)) { ux = -ux; uy = -uy; }            // reads left to right / upwards
      const lines = wrapLabel(c.text || c.label, best - 8);
      const h = lines.length * 10.5, off = 5 + h / 2;
      const q = A.add(B).divideBy(2).add(L.point(uy * off, -ux * off));        // the text's "up" side of the line
      const deg = Math.atan2(uy, ux) * 180 / Math.PI;
      mark(map.layerPointToLatLng(q), "colab",
        `<div style="transform:translate(-50%,-50%) rotate(${deg.toFixed(1)}deg)">${lines.map(esc).join("<br>")}</div>`, [0, 0]);
    }
  }
}
map.on("zoomend moveend", drawOverlay);
// the circles of the new manholes (bends, spacing) of a design: only zoomed in (user request 21-Oct-2026) - zoomed
// out thousands of them hide the sewers' colours
const NEW_MH_ZOOM = 17;
let newMhGroup = null;
function newMhShow() {
  if (!newMhGroup) return;
  const on = map.getZoom() >= NEW_MH_ZOOM, has = designLayer.hasLayer(newMhGroup);
  if (on && !has) designLayer.addLayer(newMhGroup); else if (!on && has) designLayer.removeLayer(newMhGroup);
}
map.on("zoomend", newMhShow);

// ---- a click on a sewer / manhole: it is highlighted and its details open in a popup (hover: the same as a tooltip)
const hiLayer = L.layerGroup().addTo(map);
function showPick(layer, html, latlng, shape) {
  map.closePopup();                                    // first: its 'popupclose' clears the highlight
  hiLayer.clearLayers();
  shape.addTo(hiLayer);
  L.popup({ maxWidth: 320, autoPanPadding: [20, 20] }).setLatLng(latlng).setContent(html).openOn(map);
  if (layer.closeTooltip) layer.closeTooltip();
}
map.on("popupclose", () => hiLayer.clearLayers());
function pickable(layer, html, isLine) {
  layer.bindTooltip(html, { sticky: true, direction: "right", offset: [22, 0] });   // to the right of the cursor, not under it
  layer.on("click", ev => {
    L.DomEvent.stopPropagation(ev);
    const shape = isLine ? L.polyline(layer.getLatLngs(), { color: "#ffd600", weight: 9, opacity: .75, interactive: false, renderer: netRenderer })
      : L.circleMarker(layer.getLatLng(), { radius: 11, color: "#ffd600", weight: 4, fill: false, interactive: false, renderer: netRenderer });
    showPick(layer, html, isLine ? ev.latlng : layer.getLatLng(), shape);
  });
  return layer;
}
function showResult(r) {
  result.clearLayers();
  const byMh = {}; for (const m of r.manholes) byMh[m.label] = m;
  for (const c of r.conduits) {
    const a = byMh[c.from] || {}, e = byMh[c.to] || {};
    pickable(L.polyline(c.pts, { color: "#1565c0", weight: 3, opacity: .9, renderer: netRenderer }),
      `<b>${esc(c.label)}</b> ${esc(c.from)} - ${esc(c.to)}<br>लंबाई ${Number(c.length).toFixed(1)} m<br>GL ${f2(a.gl)} - ${f2(e.gl)} m` +
      `<br><span class="hint">बहाव की दिशा zoning / design से तय होगी</span>`, true).addTo(result);
  }
  const stpMh = new Set(r.marks.map(m => m.manhole));
  const deg = {}; for (const c of r.conduits) for (const n of [c.from, c.to]) (deg[n] = deg[n] || []).push(c.label);
  for (const m of r.manholes) {
    const isO = stpMh.has(m.label);
    pickable(L.circleMarker(m.latlng, { radius: isO ? 7 : 3.5, color: isO ? "#0d47a1" : "#1565c0", weight: isO ? 3 : 1,
      fillColor: "#fff", fillOpacity: 1, renderer: netRenderer }),
      `<b>${esc(m.label)}</b>${isO ? " (STP)" : ""}<br>GL ${f2(m.gl)} m` + (m.pop ? `<br>population ${m.pop}` : "") +
      `<br>sewers: ${(deg[m.label] || []).map(esc).join(", ")}`, false).addTo(result);
  }
  drawOverlay();
  const Ltot = r.conduits.reduce((s, c) => s + c.length, 0);
  status(`Layout (PFR): ${r.manholes.length} manholes, ${r.conduits.length} sewers, ${(Ltot / 1000).toFixed(2)} km`, "ok");
  const f = r.files;
  $("files").innerHTML = `<div class="hint">Files: ${esc(r.folder)}<br>` +
    Object.entries(f).map(([k, v]) => `${k}: ${esc(v.split(/[\\/]/).pop())}`).join("<br>") +
    (r.marks.length ? `<br><b>STP → manhole ${esc(r.marks[0].manhole)}</b> (${r.marks[0].dist.toFixed(0)} m) - zoning/design में --stp / --outfall` : "") +
    `</div>`;
  if (!$("showres").checked) { $("showres").checked = true; result.addTo(map); }
  for (const g of [zoneLayer, designLayer]) map.removeLayer(g);
  curView = "layout";                                   // the layout is what is shown now (names / labels follow it)
  document.querySelectorAll("#viewseg button").forEach(b => b.classList.toggle("on", b.dataset.v === "layout"));
  dimRoads = false; drawn.eachLayer(l => { if (l.kind === "road") l.setStyle(style("road", l === selected)); });
  document.querySelectorAll("#viewseg button").forEach(b => b.classList.toggle("on", b.dataset.v === "layout"));
  $("legend").innerHTML = "";
}
