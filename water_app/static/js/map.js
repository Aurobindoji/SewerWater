// The water map page (map.html), part 2 of 11: the map, its base layers and the maps from a URL.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---------------------------------------------------------------- map
const map = L.map("map", { zoomControl: true }).setView([25.3176, 82.9739], 14);
const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" });
const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 19, attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics" });
const labels = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 19, attribution: "Labels &copy; Esri" });
// the default base map: Google's standard street map (user, 14-Oct-2026)
const gmap = L.tileLayer("https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
  { maxZoom: 21, attribution: "Map data &copy; Google" });
gmap.addTo(map);
const layersCtl = L.control.layers({ "Google Map": gmap, "नक्शा (OSM)": osm, "Satellite (Esri)": sat }, { "नाम (satellite पर)": labels }).addTo(map);
L.control.scale({ imperial: false }).addTo(map);

// ---- maps from a URL (as in QGIS): XYZ tiles, ArcGIS MapServer, WMS; kept in this browser (all projects)
const LS_MAPS = "sewer_app_url_maps";
const urlMaps = [];                                    // {def, layer}
const hasBase = () => [gmap, osm, sat, ...urlMaps.filter(m => m.def.kind === "base").map(m => m.layer)].some(l => map.hasLayer(l));
function urlLayer(d) {
  let u = d.url.trim();
  const zmax = Math.min(22, Math.max(1, parseInt(d.maxz) || 19));
  const o = { maxNativeZoom: zmax, maxZoom: Math.max(21, zmax), opacity: d.kind === "overlay" ? Math.min(1, Math.max(0.1, parseFloat(d.op) || 1)) : 1,
              attribution: esc(d.name) };
  if (/\/MapServer\/?$/i.test(u)) u = u.replace(/\/?$/, "/tile/{z}/{y}/{x}");            // ArcGIS REST: its tiles
  if (/\{z\}/i.test(u)) {
    if (/\{-y\}/i.test(u)) { u = u.replace(/\{-y\}/ig, "{y}"); o.tms = true; }
    return L.tileLayer(u.replace(/\{([zxys])\}/gi, (m, c) => `{${c.toLowerCase()}}`), o);
  }
  const base = u.split("?")[0];                        // a WMS: GetMap requests for its layers
  const ver = (u.match(/[?&]version=([\d.]+)/i) || [])[1];
  return L.tileLayer.wms(base, Object.assign(o, { layers: d.layers || "", format: "image/png", transparent: d.kind === "overlay",
                                                   version: ver || "1.1.1" }));
}
function addUrlMap(d, show) {
  const layer = urlLayer(d);
  let errs = 0;
  layer.on("tileerror", () => { if (++errs === 6) status(tr(`"${d.name}": tiles नहीं मिल रहीं - URL / internet जाँचें`, `"${d.name}": tiles not loading - check the URL / internet`), "err"); });
  layer.on("tileload", () => { errs = 0; });
  if (d.kind === "base") layersCtl.addBaseLayer(layer, "🌐 " + d.name); else layersCtl.addOverlay(layer, "🌐 " + d.name);
  urlMaps.push({ def: d, layer });
  if (show) {
    if (d.kind === "base") { [gmap, osm, sat, ...urlMaps.map(m => m.def.kind === "base" ? m.layer : null)].forEach(l => l && l !== layer && map.removeLayer(l)); }
    layer.addTo(map);
  }
}
function saveUrlMaps() { try { localStorage.setItem(LS_MAPS, JSON.stringify(urlMaps.map(m => m.def))); } catch (e) { } }
function listUrlMaps() {
  $("u_list").innerHTML = urlMaps.length ? urlMaps.map((m, i) => `<div><span title="${esc(m.def.url)}">🌐 <b>${esc(m.def.name)}</b>
    <span class="hint">${m.def.kind === "base" ? tr("आधार", "base") : tr("ऊपर की परत", "overlay")} - ${esc(m.def.url)}</span></span>
    <button data-i="${i}" class="danger" title="${tr("हटाएँ", "Remove")}">✕</button></div>`).join("") : "";
  $("u_list").querySelectorAll("button").forEach(b => b.onclick = () => {
    const m = urlMaps.splice(+b.dataset.i, 1)[0];
    layersCtl.removeLayer(m.layer);
    if (map.hasLayer(m.layer)) { map.removeLayer(m.layer); if (!hasBase()) gmap.addTo(map); }
    saveUrlMaps(); listUrlMaps();
  });
}
try { (JSON.parse(localStorage.getItem(LS_MAPS) || "[]") || []).forEach(d => d && d.url && addUrlMap(d, false)); } catch (e) { }
L.Control.UrlMaps = L.Control.extend({ options: { position: "topright" }, onAdd() {
  const div = L.DomUtil.create("div", "leaflet-bar urlbtn");
  div.innerHTML = `<a href="#" title="${tr("URL से नक्शा जोड़ें (XYZ / WMS, QGIS जैसा)", "Add a map from a URL (XYZ / WMS, as in QGIS)")}">🌐 URL</a>`;
  L.DomEvent.disableClickPropagation(div);
  div.firstChild.onclick = e => { e.preventDefault(); listUrlMaps(); $("urlmodal").classList.add("show"); $("u_url").focus(); };
  return div;
} });
new L.Control.UrlMaps().addTo(map);

const drawn = new L.FeatureGroup().addTo(map);
let hoverTip = null;
map.on("tooltipopen", e => {
  if (e.tooltip.options.permanent) return;                       // GL labels of spot levels stay
  if (hoverTip && hoverTip !== e.tooltip && hoverTip._source) hoverTip._source.closeTooltip();
  hoverTip = e.tooltip;
});
map.getContainer().addEventListener("mouseleave", () => { if (hoverTip && hoverTip._source) hoverTip._source.closeTooltip(); hoverTip = null; });
const result = new L.FeatureGroup().addTo(map);

L.drawLocal.draw.handlers.polyline.tooltip = { start: "पहला बिंदु click करें", cont: "अगला बिंदु click करें",
  end: "अगला बिंदु, या आखिरी बिंदु पर दोबारा click / Enter / right-click" };
L.drawLocal.draw.handlers.polygon.tooltip = { start: "पहला कोना click करें", cont: "अगला कोना click करें",
  end: "पहले कोने पर click / Enter / right-click से बंद करें" };
// small vertex boxes (Leaflet.draw's own are 20 px on a touch screen): a diamond on a line, a square on an area
const vertexIcon = line => L.divIcon({ iconSize: [12, 12], className: "leaflet-editing-icon vx " + (line ? "vx-line" : "vx-area"), html: "<i></i>" });
{
  const make = L.Edit.PolyVerticesEdit.prototype._createMarker;
  L.Edit.PolyVerticesEdit.prototype._createMarker = function (latlng, index) {
    const m = make.call(this, latlng, index);
    m.setIcon(vertexIcon(!(this._poly instanceof L.Polygon)));
    return m;
  };
}
// drawing a line / area with the mouse: Leaflet.draw's own clicks lost points - a press and release more than 9 px
// apart (the mouse moving along a curve) counted as a drag, new points were blocked for a moment after each one,
// and a release on a point box left it stuck. Here every left press + release within CLICK_TOL_PX is a point, where
// the button went down; the map pans only on a longer drag. A click on the last point (line) / the first point
// (area) still finishes; on another point of a line it adds a point exactly there (closes a loop).
const CLICK_TOL_PX = 20;
L.Draw.Polyline.prototype._onMouseDown = function () { };        // mouse handled below; touch keeps Leaflet.draw's own
L.Draw.Polyline.prototype._onMouseUp = function () { };
{
  const c = map.getContainer();
  const drawingPoly = () => activeHandler && activeHandler.addVertex && activeHandler._markers;
  let down = null;
  c.addEventListener("pointerdown", e => {
    down = null;
    if (e.pointerType !== "mouse" || e.button !== 0 || !drawingPoly() || e.target.closest(".leaflet-control")) return;
    down = { x: e.clientX, y: e.clientY, ll: map.mouseEventToLatLng(e) };
  }, true);
  c.addEventListener("pointerup", e => {
    const d = down; down = null;
    if (!d || e.pointerType !== "mouse" || e.button !== 0 || !drawingPoly()) return;
    if (Math.hypot(e.clientX - d.x, e.clientY - d.y) > CLICK_TOL_PX) return;          // a drag: the map was panned
    const h = activeHandler, ms = h._markers;
    const mk = ms.find(m => m.getElement() && m.getElement().contains(e.target));
    if (mk) {
      const i = ms.indexOf(mk);
      if (h.type === L.Draw.Polyline.TYPE ? i === ms.length - 1 : i === 0 && ms.length >= 3) return;   // its click finishes
      h.addVertex(mk.getLatLng());
    } else h.addVertex(d.ll);
  }, true);
}
L.drawLocal.draw.handlers.marker.tooltip = { start: "स्थान पर click करें" };
L.drawLocal.edit.handlers.edit.tooltip = { subtext: "कोने या marker खींचकर सरकाएँ।",    // subtext is the top line
  text: "बदलाव रखें: Enter या right-click; रद्द करें: Esc (बाएँ panel में भी बटन हैं)।" };

let dimRoads = false;                   // zones / design shown: the drawn roads stay faint underneath
function style(kind, selected) {
  const c = KIND[kind].color, w = selected ? 3 : 0;
  if (kind === "road") return { color: c, weight: 4 + w, opacity: dimRoads && !selected ? .25 : .9 };
  if (kind === "barrier") return { color: c, weight: 6 + w, opacity: .85, dashArray: "14 5 3 5", lineCap: "butt" };
  if (kind === "crossing") return { color: c, weight: 5 + w, opacity: .95 };
  if (kind === "lasso") return { color: c, weight: 2 + w, dashArray: "6 4", fillColor: c, fillOpacity: .1 };
  if (kind === "zone_loop") return { color: c, weight: 3 + w, dashArray: "10 6", fillColor: c, fillOpacity: .07 };
  if (kind === "boundary") return { color: c, weight: 3 + w, dashArray: "8 6", fill: false };
  if (kind === "ward") return { color: c, weight: 2 + w, fillColor: c, fillOpacity: .12 };
  return {};
}
function icon(kind, selected, props) {
  if (kind === "oht" || kind === "oht_ex" || kind === "oht_new") {
    const ex = kind === "oht_ex" || (kind === "oht" && isExOht(props));
    const nm = props && props.name ? props.name : ex ? "Ex-OHT" : "Prop-OHT";
    return L.divIcon({ className: "oht-icon" + (ex ? "" : " prop") + (selected ? " sel-icon" : ""), html: `<div>${esc(nm)}</div>`, iconSize: null });
  }
  if (kind === "spot") return L.divIcon({ className: "spot-icon" + (selected ? " sel-icon" : ""), iconSize: [12, 12] });
  if (kind === "bulk") return L.divIcon({ className: "bulk-icon" + (selected ? " sel-icon" : ""), html: "B", iconSize: [20, 20] });
  if (kind === "prv") return L.divIcon({ className: "prv-icon" + (selected ? " sel-icon" : ""), html: "P", iconSize: [20, 20] });
  if (kind === "tw") return L.divIcon({ className: "tw-icon" + (selected ? " sel-icon" : ""), html: "T", iconSize: [20, 20] });
  return L.divIcon({ className: "stp-icon" + (selected ? " sel-icon" : ""), html: "STP", iconSize: [30, 18] });
}
