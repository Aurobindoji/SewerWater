// The sewer map page (map.html), part 3 of 9: the features drawn on the map, the drawing tools and the summary of the drawing.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---------------------------------------------------------------- features
let selected = null;
function addFeature(layer, kind, props) {
  layer.kind = kind;
  layer.props = Object.assign({ name: "" }, props || {});
  if (layer.setStyle) layer.setStyle(style(kind));
  if (layer.setIcon) layer.setIcon(icon(kind, false));
  layer.on("click", ev => { L.DomEvent.stopPropagation(ev); select(layer); });
  drawn.addLayer(layer);
  label(layer);
  passClicks(layer);
  return layer;
}
// the drawn roads / wards lie above the network's canvas: while a network (layout, zones, design) is shown, clicks go
// through them to the sewers and manholes - a road takes none, a ward / boundary only on its border line. Without a
// network shown (or 'नतीजा दिखाएँ' off) they are clicked as before.
const netShown = () => { try { return [result, zoneLayer, designLayer].some(g => map.hasLayer(g)); } catch (e) { return false; } };  // layers declared further down
function passClicks(l) {
  const el = l.getElement && l.getElement();
  if (!el || !(l instanceof L.Path)) return;
  el.style.pointerEvents = !netShown() ? "" : l.kind === "road" ? "none" : "visibleStroke";
}
map.on("layeradd layerremove", e => { try { if (e.layer === result || e.layer === zoneLayer || e.layer === designLayer) drawn.eachLayer(passClicks); } catch (x) { } });
function label(layer) {
  layer.unbindTooltip();
  const p = layer.props;
  if (layer.kind === "spot" && p.gl !== undefined && p.gl !== "")
    layer.bindTooltip(Number(p.gl).toFixed(2), { permanent: true, direction: "right", className: "gl", offset: [6, 0] });
  else if (layer.kind === "ward")
    layer.bindTooltip(`${esc(p.name || "वार्ड")}: ${p.population ? Number(p.population).toLocaleString("en-IN") : "population ?"}`,
      { sticky: true, direction: "right", offset: [22, 0] });
  else if (layer.kind === "road" && p.name) layer.bindTooltip(esc(p.name), { sticky: true, direction: "right", offset: [22, 0] });
  else if (layer.kind === "crossing")
    layer.bindTooltip(`${esc(p.name || "Crossing")} - ${tr("यहाँ sewer आर-पार", "a sewer goes across here")}`, { sticky: true, direction: "right", offset: [22, 0] });
  else if (layer.kind === "zone_loop")
    layer.bindTooltip(`${esc(p.name || "Zone")} - ${tr("घेरा क्षेत्र एक zone", "the area enclosed: one zone")}`, { sticky: true, direction: "right", offset: [22, 0] });
  else if (layer.kind === "barrier")
    layer.bindTooltip(`${esc(p.name || "")} (${barrierType(p.type)}) - ${tr("कोई sewer पार नहीं करेगा", "no sewer crosses it")}`, { sticky: true, direction: "right", offset: [22, 0] });
}
function select(layer) {
  const reEdit = editing && layer && layer !== editTarget;       // editing: a click on another feature edits that one
  if (reEdit) toggleEdit(false);
  if (selected && drawn.hasLayer(selected)) {
    if (selected.setStyle) selected.setStyle(style(selected.kind));
    if (selected.setIcon) selected.setIcon(icon(selected.kind, false));
  }
  selected = layer;
  if (layer) {
    if (layer.setStyle) layer.setStyle(style(layer.kind, true));
    if (layer.setIcon) layer.setIcon(icon(layer.kind, true));
  }
  showProps();
  if (reEdit) toggleEdit(true);
}
map.on("click", () => { if (!activeHandler && mode === "kml") select(null); });

function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function lengthOf(latlngs) { let L_ = 0; for (let i = 1; i < latlngs.length; i++) L_ += map.distance(latlngs[i - 1], latlngs[i]); return L_; }
function areaOf(layer) { const r = layer.getLatLngs()[0]; return L.GeometryUtil.geodesicArea(r); }

function showProps() {
  const box = $("props");
  if (!selected) { box.className = "empty"; box.innerHTML = "नक्शे पर किसी वस्तु पर click करें।"; return; }
  const k = selected.kind, p = selected.props;
  let info = "";
  if (k === "road" || k === "barrier" || k === "crossing") info = `लंबाई ${lengthOf(selected.getLatLngs()).toFixed(0)} m, ${selected.getLatLngs().length} बिंदु`;
  if (k === "ward" || k === "boundary" || k === "zone_loop") info = `क्षेत्रफल ${(areaOf(selected) / 1e4).toFixed(2)} ha`;
  if (k === "spot" || k === "stp") { const ll = selected.getLatLng(); info = `${ll.lat.toFixed(6)}, ${ll.lng.toFixed(6)}`; }
  box.className = "";
  box.innerHTML = `<b style="color:${KIND[k].color}">${KIND[k].name}</b> <span class="hint">${info}</span>
    <div class="row"><label>नाम</label><input type="text" id="f_name" value="${esc(p.name)}"></div>
    ${k === "ward" ? `<div class="row"><label>Population</label><input type="number" id="f_pop" min="0" step="1" value="${esc(p.population)}"></div>` : ""}
    ${k === "boundary" ? `<div class="row"><label>Population</label><input type="number" id="f_pop" min="0" step="1" value="${esc(p.population ?? "")}"></div>
       <div class="hint">पूरे क्षेत्र की population - तभी ली जाती है जब किसी वार्ड में population न भरी हो (वार्ड हों तो वार्ड-वार भरें)।</div>` : ""}
    ${k === "crossing" ? `<div class="hint">${tr("जहाँ यह रेखा किसी रुकावट रेखा या zone लूप को काटती है, वहाँ 10 m के भीतर का sewer नहीं कटता (sewer सीमा के पार बहता है)। वहाँ कोई sewer न हो तो यही रेखा नया sewer बनती है, जिसके दोनों सिरे सबसे पास के manhole (100 m तक) से जुड़ते हैं। बदलने पर Zoning और Design दोबारा चलाएँ।",
         "Where this line crosses a barrier line or a zone loop, the sewer within 10 m there is not cut (the sewer flows across). Where no sewer crosses there, this line is a new sewer, its ends joined to the nearest manhole (within 100 m). After a change run Zoning and Design again.")}</div>` : ""}
    ${k === "zone_loop" ? `<div class="hint">${tr("घेरे क्षेत्र के manholes एक zone बनते हैं, उसका सबसे नीचा manhole outlet (pumping station); सीमा पार करने वाले sewers सीमा पर रुकते हैं। बदलने पर Zoning और Design दोबारा चलाएँ।",
         "The manholes inside form one zone, its lowest manhole the outlet (pumping station); the sewers crossing the loop stop at it. After a change run Zoning and Design again.")}</div>` : ""}
    ${k === "barrier" ? `<div class="row"><label>${tr("प्रकार", "Type")}</label><select id="f_btype">${BARRIER_TYPES.map(b =>
         `<option value="${b[0]}"${(p.type || "other") === b[0] ? " selected" : ""}>${EN ? b[2] : b[1]}</option>`).join("")}</select></div>
       <div class="row"><label title="${tr(`रेखा को काटने वाला ${PIPE} रेखा से इतने मीटर पहले, दोनों ओर, बंद होता है`, `a ${PIPE} crossing the line ends this many metres short of it, on both sides`)}">${tr("रेखा से पहले बंद (m)", "Ends short of the line (m)")}</label>
         <input type="number" id="f_gap" min="0" max="100" step="0.5" value="${esc(p.gap_m ?? 1)}"></div>
       <div class="hint">${tr("कोई sewer इस रेखा को पार नहीं करेगा: Zoning / Design में काटने वाला sewer रेखा पर कटता है - दोनों हिस्से अपनी सड़क पर रहते हैं, रेखा से ऊपर दी दूरी (m) पहले बंद। कटकर अलग हुआ हिस्सा अपने outlet (pumping station / STP) में जाता है। बदलने पर Zoning और Design दोबारा चलाएँ।",
         "No sewer crosses this line: in Zoning / Design a sewer crossing it is cut there - both parts stay on their road, ending the distance above (m) short of the line. A part so cut off drains to an outlet of its own (pumping station / STP). After a change run Zoning and Design again.")}</div>` : ""}
    ${k === "spot" ? `<div class="row"><label>GL (m)</label><input type="number" id="f_gl" step="0.01" value="${esc(p.gl)}"></div>
       <div class="hint">Google Earth में cursor की ऊँचाई (Elev) या survey का स्तर - PFR अनुमान।</div>` : ""}
    <div class="row">${k === "ward" ? '<button id="f_kind">Boundary बनाएँ</button>' : k === "boundary" ? '<button id="f_kind">वार्ड बनाएँ</button>' : ""}
      <button class="danger" id="f_del">हटाएँ (Delete)</button></div>`;
  const bind = (id, key) => { const el = $(id); if (el) el.addEventListener("input", () => { p[key] = el.value; label(selected); changed(); }); };
  bind("f_name", "name"); bind("f_pop", "population"); bind("f_gl", "gl");
  if ($("f_btype")) $("f_btype").onchange = () => { p.type = $("f_btype").value; label(selected); changed(); barrierTouched(); };
  if ($("f_onlimit")) $("f_onlimit").onchange = () => { p.on_limit = $("f_onlimit").value; changed(); barrierTouched(); };
  if ($("f_gap")) $("f_gap").onchange = () => { p.gap_m = $("f_gap").value; changed(); barrierTouched(); };
  $("f_del").onclick = () => removeSelected();
  if ($("f_kind")) $("f_kind").onclick = () => {        // a polygon read as ward / boundary the wrong way round
    const to = k === "ward" ? "boundary" : "ward";
    if (to === "boundary") drawn.eachLayer(l => { if (l.kind === "boundary" && l !== selected) { l.kind = "ward"; l.props.population = l.props.population || ""; l.setStyle(style("ward")); label(l); } });
    selected.kind = to;
    if (to === "ward") selected.props.population = selected.props.population || "";
    selected.setStyle(style(to, true)); label(selected); showProps(); changed();
  };
  const focus = $(k === "spot" ? "f_gl" : k === "ward" ? "f_pop" : "f_name");
  if (focus && (k === "spot" || k === "ward") && (focus.value === "")) setTimeout(() => focus.focus(), 30);
}
function removeSelected() {
  if (!selected) return;
  if (editing) toggleEdit(false);
  if (selected.kind === "barrier" || selected.kind === "zone_loop" || selected.kind === "crossing") barrierTouched();
  drawn.removeLayer(selected); selected = null; showProps(); changed();
}
// a barrier line / zone loop drawn / changed / removed after zoning / design: they are of the lines as they were
function barrierTouched() {
  if (!(zoningData || designData) || !$("zstatus")) return;
  $("zstatus").className = "status err";
  $("zstatus").textContent = tr("Zoning औज़ार (रेखा / लूप) बदला गया - Zoning और Design दोबारा चलाएँ", "A zoning tool (line / loop) changed - run Zoning and Design again");
}

// ---------------------------------------------------------------- drawing
let activeHandler = null, activeKind = null;
function startDraw(kind) {
  stopDraw();
  if (editing) toggleEdit(false);
  activeKind = kind;
  const opt = { shapeOptions: style(kind), repeatMode: kind === "road" || kind === "spot" || kind === "ward",
                guidelineDistance: 7 };                                // guide dots every 7 px (default 20)
  if (kind === "road" || kind === "barrier" || kind === "crossing" || kind === "boundary" || kind === "ward" || kind === "zone_loop" || kind === "lasso")
    opt.icon = opt.touchIcon = vertexIcon(kind === "road" || kind === "barrier" || kind === "crossing");
  if (kind === "road" || kind === "barrier" || kind === "crossing") activeHandler = new L.Draw.Polyline(map, Object.assign(opt, { showLength: true, metric: true }));
  else if (kind === "boundary" || kind === "ward" || kind === "zone_loop" || kind === "lasso") activeHandler = new L.Draw.Polygon(map, Object.assign(opt, { showArea: false, allowIntersection: false }));
  else activeHandler = new L.Draw.Marker(map, Object.assign(opt, { icon: icon(kind) }));
  activeHandler.enable();
  // a small slip of the mouse during a click must not pan the map (see CLICK_TOL_PX)
  if (activeHandler.addVertex && map.dragging._draggable) map.dragging._draggable.options.clickTolerance = CLICK_TOL_PX;
  document.querySelectorAll(".tools button[data-kind]").forEach(b => b.classList.toggle("on", b.dataset.kind === kind));
  $("drawbar").classList.toggle("show", kind === "road" || kind === "barrier" || kind === "crossing" || kind === "boundary" || kind === "ward" || kind === "zone_loop" || kind === "lasso");
  uiToolHint("draw", kind === "lasso" ? toolName('#ntools button[data-t="lasso"]') : toolName(`.tools button[data-kind="${kind}"]`) || kind,
             toolWhat(kind), true);                                   // the tool on, at the mouse (ui.js)
}
function stopDraw() {
  if (map.dragging._draggable) map.dragging._draggable.options.clickTolerance = map.options.clickTolerance || 3;
  if (activeHandler) activeHandler.disable();
  activeHandler = null; activeKind = null;
  document.querySelectorAll(".tools button[data-kind]").forEach(b => b.classList.remove("on"));
  $("drawbar").classList.remove("show");
  uiToolHint("draw", null);
}
document.querySelectorAll(".tools button[data-kind]").forEach(b =>
  b.addEventListener("click", () => activeKind === b.dataset.kind ? stopDraw() : startDraw(b.dataset.kind)));
// right-click on the map = Enter: finishes the line / area being drawn, keeps the changes in edit mode (the right
// button itself adds no point, and the browser menu does not open)
{
  const c = map.getContainer();
  const busyHere = () => (activeHandler && activeHandler.completeShape) || editing;
  for (const t of ["mousedown", "mouseup", "pointerdown", "pointerup"])
    c.addEventListener(t, e => { if (e.button === 2 && busyHere()) e.stopPropagation(); }, true);
  c.addEventListener("contextmenu", e => {
    if (!busyHere()) return;
    e.preventDefault(); e.stopPropagation();
    if (activeHandler && activeHandler.completeShape) activeHandler.completeShape();
    else toggleEdit(false);
  }, true);
}
// Esc, everywhere and at once (user, 14-Oct-2026): drawing / editing cancelled, the tool back to none (DXF network:
// "select"), nothing selected, popups and the URL dialog closed, the focus off - the plain arrow cursor again
function escapeAll() {
  if (editing) cancelEdit();
  stopDraw();
  if (selected) select(null);
  if (mode === "dxf") { pick = null; if (tool !== "select") setTool("select"); else $("nhint").textContent = HINT.select; netSelect(null); }
  map.closePopup(); hiLayer.clearLayers();
  if ($("urlmodal").classList.contains("show")) $("urlmodal").classList.remove("show");
  const a = document.activeElement;
  if (a && a !== document.body && a.blur) a.blur();
}
$("dfinish").onclick = () => { if (activeHandler && activeHandler.completeShape) activeHandler.completeShape(); };
$("dundo").onclick = () => { if (activeHandler && activeHandler.deleteLastVertex) activeHandler.deleteLastVertex(); };
$("dcancel").onclick = stopDraw;
document.addEventListener("keydown", e => {
  const typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName);
  if (e.key === "Enter" && activeHandler && activeHandler.completeShape && !typing) { activeHandler.completeShape(); e.preventDefault(); }
  // Ctrl+Z while drawing a line / area: the last point goes, one per press
  if ((e.ctrlKey || e.metaKey) && (e.key || "").toLowerCase() === "z" && activeHandler && activeHandler.deleteLastVertex && !typing) {
    e.preventDefault();
    const n = activeHandler._markers ? activeHandler._markers.length : 0;
    if (n > 1) activeHandler.deleteLastVertex();
    else if (n === 1) startDraw(activeKind);           // Leaflet.draw keeps the first point: start the same tool afresh
  }
  if (e.key === "Enter" && editing && !typing) { toggleEdit(false); e.preventDefault(); }
  if (e.key === "Escape") escapeAll();
  if (e.key === "Delete" && selected && !typing) removeSelected();
});

map.on(L.Draw.Event.CREATED, e => {
  let kind = activeKind || "road";
  if (kind === "lasso") { stopDraw(); setTool("select"); return lassoSelect(e.layer.getLatLngs()[0]); }   // not kept
  if ((kind === "ward" || kind === "boundary" || kind === "zone_loop") && areaOf(e.layer) < 10) {
    // clicks on (nearly) one spot: a polygon without area - not kept (it would count as a ward without population)
    $("drawhint").textContent = tr("यह आकार बहुत छोटा था (क्षेत्रफल लगभग 0) - नहीं रखा। कोने अलग-अलग जगह click करें।",
      "That shape had (almost) no area - not kept. Click the corners at different places.");
    return;
  }
  if (kind === "boundary") drawn.eachLayer(l => { if (l.kind === "boundary") drawn.removeLayer(l); });
  if (kind === "stp") drawn.eachLayer(l => { if (l.kind === "stp") drawn.removeLayer(l); });
  const n = 1 + countOf(kind);
  const props = kind === "road" ? { name: `Road ${n}` } : kind === "barrier" ? { name: `Barrier ${n}`, type: "highway", gap_m: "1" } : kind === "zone_loop" ? { name: `Zone ${n}`, on_limit: "" } : kind === "crossing" ? { name: `Crossing ${n}` } : kind === "ward" ? { name: `Ward ${n}`, population: "" }
    : kind === "spot" ? { name: "", gl: "" } : kind === "stp" ? { name: "STP" }
    : { name: "Project boundary", population: "" };
  const layer = addFeature(e.layer, kind, props);
  if (kind === "road") snapRoad(layer);
  select(layer);
  if (kind === "boundary" || kind === "stp" || kind === "barrier" || kind === "zone_loop" || kind === "crossing") stopDraw();
  if (kind === "barrier" || kind === "zone_loop" || kind === "crossing") barrierTouched();
  changed();
});

// a road end close to another road (SNAP_PX on screen) is moved onto it, so that 'layout' joins them
function snapRoad(layer) {
  const pts = layer.getLatLngs();
  let moved = 0;
  for (const idx of [0, pts.length - 1]) {
    const p = map.latLngToLayerPoint(pts[idx]);
    let best = null, bd = SNAP_PX;
    drawn.eachLayer(o => {
      if (o === layer || o.kind !== "road") return;
      const q = o.getLatLngs().map(ll => map.latLngToLayerPoint(ll));
      for (let i = 1; i < q.length; i++) {
        const c = L.LineUtil.closestPointOnSegment(p, q[i - 1], q[i]);
        // prefer the other road's end / vertex when it is nearly as close
        for (const v of [q[i - 1], q[i]]) if (v.distanceTo(p) <= SNAP_PX && v.distanceTo(c) < 4) { c.x = v.x; c.y = v.y; }
        const d = c.distanceTo(p);
        if (d < bd) { bd = d; best = c; }
      }
    });
    if (best) { pts[idx] = map.layerPointToLatLng(best); moved++; }
  }
  if (moved) layer.setLatLngs(pts);
}

// edit mode: move the vertices of the SELECTED feature only (Leaflet.draw edit handler) - a ward from a GIS file can
// have thousands of points, and handles on every feature at once froze the page; a feature with more than
// EDIT_MAX_PTS points is first simplified (asked)
const EDIT_MAX_PTS = 400;
let editing = null, editTarget = null, editOrig = null;
const cloneLL = a => Array.isArray(a) ? a.map(cloneLL) : L.latLng(a.lat, a.lng);
const vertexCount = l => l.getLatLngs ? l.getLatLngs().flat(3).length : 1;
function simplifyLayer(l, tolM) {
  const z = 18, lat = l.getBounds().getCenter().lat;
  const tol = tolM / (40075016.686 * Math.cos(lat * Math.PI / 180) / Math.pow(2, z + 8));     // metres -> pixels at z
  const go = a => Array.isArray(a[0]) ? a.map(go)
    : L.LineUtil.simplify(a.map(ll => map.project(ll, z)), tol).map(p => map.unproject(p, z));
  l.setLatLngs(go(l.getLatLngs()));
  if (L.Edit.Poly) l.editing = new L.Edit.Poly(l);               // its edit handler keeps the old point array
}
function toggleEdit(on) {
  if (on === undefined) on = !editing;
  if (on) {
    stopDraw();
    if (editing) toggleEdit(false);
    if (!selected || !drawn.hasLayer(selected)) {
      $("drawhint").textContent = "पहले नक्शे पर वह वस्तु चुनें (click) जिसे बदलना है, फिर '✎ बदलें / हटाएँ' दबाएँ।"; return; }
    const n = vertexCount(selected);
    if (n > EDIT_MAX_PTS) {
      if (!confirm(tr(`इसमें ${n} बिंदु हैं - इतने handles से पेज अटक जाता है। बदलने के लिए इसे सरल कर दें (बिंदु कम होंगे, आकार लगभग वही रहेगा)?`,
                      `It has ${n} points - that many handles freeze the page. Simplify it for editing (fewer points, the shape stays almost the same)?`))) return;
      editOrig = { layer: selected, lls: cloneLL(selected.getLatLngs()) };
      for (const t of [1, 2, 5, 10, 20, 50]) { simplifyLayer(selected, t); if (vertexCount(selected) <= EDIT_MAX_PTS) break; }
      changed();
    }
    editTarget = selected;
    editing = new L.EditToolbar.Edit(map, { featureGroup: L.featureGroup([selected]) });
    editing.enable();
    $("editbtn").classList.add("on");
    $("editbar").classList.add("show");
    $("drawhint").textContent = "बिंदु खींचकर सरकाएँ; खत्म होने पर फिर '✎ बदलें / हटाएँ' दबाएँ। दूसरी वस्तु पर click करें तो वह बदलने लगेगी। हटाने के लिए Delete।";
  } else if (editing) {
    editing.save(); editing.disable(); editing = null; editTarget = null; editOrig = null;   // save() fires draw:edited (snaps edited roads)
    $("editbtn").classList.remove("on");
    $("editbar").classList.remove("show");
    $("drawhint").textContent = "एक औज़ार चुनें।";
    changed();
  }
}
// cancel: the points moved in this edit go back (and the points from before a simplification)
function cancelEdit() {
  if (!editing) return;
  editing.revertLayers(); editing.disable(); editing = null; editTarget = null;
  if (editOrig) { editOrig.layer.setLatLngs(editOrig.lls); if (L.Edit.Poly) editOrig.layer.editing = new L.Edit.Poly(editOrig.layer); editOrig = null; }
  $("editbtn").classList.remove("on");
  $("editbar").classList.remove("show");
  $("drawhint").textContent = "बदलाव रद्द किए गए।";
  changed();
}
$("editbtn").onclick = () => toggleEdit();
$("esave").onclick = () => toggleEdit(false);
$("ecancel").onclick = cancelEdit;
map.on(L.Draw.Event.EDITED, e => e.layers.eachLayer(l => { if (l.kind === "road") snapRoad(l); }));

// ---------------------------------------------------------------- summary
function countOf(kind) { let n = 0; drawn.eachLayer(l => { if (l.kind === kind) n++; }); return n; }
function summary() {
  let barriers = 0, roadsL = 0, roads = 0, wards = 0, pop = 0, noPop = 0, spots = 0, noGl = 0, bArea = null, stp = 0, bPop = 0;
  drawn.eachLayer(l => {
    if (l.kind === "road") { roads++; roadsL += lengthOf(l.getLatLngs()); }
    if (l.kind === "ward") { wards++; const v = parseFloat(l.props.population); if (v > 0) pop += v; else noPop++; }
    if (l.kind === "spot") { spots++; if (l.props.gl === "" || isNaN(parseFloat(l.props.gl))) noGl++; }
    if (l.kind === "boundary") { bArea = areaOf(l); bPop = parseFloat(l.props.population) || 0; }
    if (l.kind === "stp") stp++;
    if (l.kind === "barrier") barriers++;
  });
  $("sum").innerHTML = [
    ["सड़कें", `${roads} (${(roadsL / 1000).toFixed(2)} km)`],
    ["Boundary", bArea ? `${(bArea / 1e4).toFixed(1)} ha` + (bPop ? `, population ${bPop.toLocaleString("en-IN")}${pop ? " " + tr("(नहीं ली जाएगी - वार्डों में है)", "(not used - the wards have it)") : ""}` : "") : tr("नहीं", "no")],
    ["वार्ड", `${wards}, population ${pop.toLocaleString("en-IN")}`],
    ["Spot levels", `${spots}`],
    ["STP", stp ? tr("है", "yes") : tr("नहीं", "no")],
    ...(barriers ? [[tr("रुकावट रेखाएँ", "Barrier lines"), `${barriers}`]] : []),
  ].map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join("");
  const w = [];
  if (!roads) w.push("कम से कम एक सड़क खींचें।");
  if (noPop && !(bPop && !pop)) w.push(`${noPop} वार्ड की population नहीं भरी।`);
  if (noGl) w.push(`${noGl} spot level का GL नहीं भरा (वे नहीं गिने जाएँगे)।`);
  if ($("glmode").value === "spots" && spots - noGl < 3) w.push("Spot levels से GL के लिए कम से कम 3 spot levels चाहिए।");
  if (!stp) w.push("STP का स्थान नहीं - layout outfall नहीं सुझाएगा।");
  $("checks").innerHTML = w.map(x => `<div class="warn">• ${x}</div>`).join("");
  return { roads, spots: spots - noGl };
}
