// The water map page (map.html), part 4 of 11: KML write / read.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---------------------------------------------------------------- KML write / read
function xml(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" }[c])); }
function coords(lls, close) {
  const a = lls.map(ll => `${ll.lng.toFixed(7)},${ll.lat.toFixed(7)},0`);
  if (close && lls.length) a.push(a[0]);
  return a.join(" ");
}
function toKML() {
  const F = { road: [], barrier: [], zone_loop: [], crossing: [], boundary: [], ward: [], spot: [], stp: [], oht: [], bulk: [], prv: [], tw: [] };
  drawn.eachLayer(l => F[l.kind].push(l));
  const pm = (l, geom, data, nm) => `<Placemark><name>${xml(nm ?? l.props.name)}</name><styleUrl>#${l.kind}</styleUrl>` +
    (data ? `<ExtendedData>${Object.entries(data).map(([k, v]) => `<Data name="${k}"><value>${xml(v)}</value></Data>`).join("")}</ExtendedData>` : "") +
    geom + "</Placemark>";
  const poly = l => `<Polygon><outerBoundaryIs><LinearRing><coordinates>${coords(l.getLatLngs()[0], true)}</coordinates></LinearRing></outerBoundaryIs></Polygon>`;
  const pt = l => `<Point><coordinates>${coords([l.getLatLng()])}</coordinates></Point>`;
  const body =
    `<Folder><name>Roads (Paths)</name>${F.road.map(l => pm(l, `<LineString><tessellate>1</tessellate><coordinates>${coords(l.getLatLngs())}</coordinates></LineString>`)).join("")}</Folder>` +
    // barrier lines: a folder of their own - read back as barriers, never as roads (geo.BARRIER_FOLDER)
    (F.barrier.length ? `<Folder><name>Barrier lines</name>${F.barrier.map(l => pm(l, `<LineString><tessellate>1</tessellate><coordinates>${coords(l.getLatLngs())}</coordinates></LineString>`,
      { kind: "barrier", type: l.props.type || "other", gap_m: l.props.gap_m ?? "1" })).join("")}</Folder>` : "") +
    (F.crossing.length ? `<Folder><name>Crossings</name>${F.crossing.map(l => pm(l, `<LineString><tessellate>1</tessellate><coordinates>${coords(l.getLatLngs())}</coordinates></LineString>`,
      { kind: "crossing", tol_m: l.props.tol_m ?? "", snap_m: l.props.snap_m ?? "" })).join("")}</Folder>` : "") +
    (F.zone_loop.length ? `<Folder><name>Zone loops</name>${F.zone_loop.map(l => pm(l, poly(l), { kind: "zone_loop", on_limit: l.props.on_limit || "" })).join("")}</Folder>` : "") +
    `<Folder><name>Project boundary</name>${F.boundary.map(l => pm(l, poly(l),
      String(l.props.population ?? "").trim() !== "" && !F.ward.some(w => parseFloat(w.props.population) > 0)
        ? { population: l.props.population } : null)).join("")}</Folder>` +
    `<Folder><name>Wards with population</name>${F.ward.map(l => pm(l, poly(l), l.props.population !== "" || l.props.ward_no ? { population: l.props.population ?? "", ward_no: l.props.ward_no ?? "" } : null)).join("")}</Folder>` +
    `<Folder><name>Spot levels (GL)</name>${F.spot.filter(l => l.props.gl !== "").map(l => {
      const g = Number(l.props.gl).toFixed(2); return pm(l, pt(l), { GL: g }, l.props.name || `GL ${g}`); }).join("")}</Folder>` +
    `<Folder><name>STP / outfall</name>${F.stp.map(l => pm(l, pt(l))).join("")}</Folder>` +
    (F.oht.length ? `<Folder><name>OHT / ESR</name>${F.oht.map(l => pm(l, pt(l), { existing: isExOht(l.props) ? "1" : "0", capacity_kl: l.props.capacity_kl ?? "",
      staging_m: l.props.staging_m ?? "", tubewells: l.props.tubewells ?? "", rebore: l.props.rebore ?? "", low_head: l.props.low_head === "new_oht" ? "new_oht" : "vfd" })).join("")}</Folder>` : "") +
    // bulk consumers: a folder of their own - never read as spot levels / STP (layout_cmd.BULK_FOLDER)
    (F.bulk.length ? `<Folder><name>Bulk consumers</name>${F.bulk.map(l => pm(l, pt(l), { kind: "bulk", kld: l.props.kld ?? "", peak: l.props.peak ?? "" })).join("")}</Folder>` : "") +
    // PRVs: a folder of their own - never read as spot levels / STP (layout_cmd.PRV_FOLDER)
    (F.prv.length ? `<Folder><name>PRVs</name>${F.prv.map(l => pm(l, pt(l), { kind: "prv", setting_m: l.props.setting_m ?? "" })).join("")}</Folder>` : "") +
    // new tube wells: a folder of their own - never read as spot levels / STP (layout_cmd.TW_FOLDER)
    (F.tw.length ? `<Folder><name>Tube wells</name>${F.tw.map(l => pm(l, pt(l), { kind: "tw", discharge_lpm: l.props.discharge_lpm ?? "" })).join("")}</Folder>` : "");
  const styles = '<Style id="road"><LineStyle><color>ff2f2fd3</color><width>3</width></LineStyle></Style>' +
    '<Style id="crossing"><LineStyle><color>ff52a100</color><width>4</width></LineStyle></Style>' +
    '<Style id="zone_loop"><LineStyle><color>ff5714ad</color><width>3</width></LineStyle><PolyStyle><fill>0</fill></PolyStyle></Style>' +
    '<Style id="barrier"><LineStyle><color>ff4f4737</color><width>5</width></LineStyle></Style>' +
    '<Style id="boundary"><LineStyle><color>ff0b86b8</color><width>2</width></LineStyle><PolyStyle><fill>0</fill></PolyStyle></Style>' +
    '<Style id="ward"><LineStyle><color>ff327d2e</color><width>1</width></LineStyle><PolyStyle><color>33327d2e</color></PolyStyle></Style>' +
    '<Style id="spot"><IconStyle><scale>0.6</scale></IconStyle></Style><Style id="stp"><IconStyle><scale>1.2</scale></IconStyle></Style>' +
    '<Style id="oht"><IconStyle><scale>1.3</scale></IconStyle></Style>';
  return `<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${xml($("pname").value)}</name>${styles}${body}</Document></kml>\n`;
}

function parseCoords(text) {
  return (text || "").trim().split(/\s+/).map(t => t.split(",").map(Number)).filter(a => a.length >= 2 && !isNaN(a[0]) && !isNaN(a[1]));
}
function num(v) { const m = String(v ?? "").match(/-?\d[\d,]*\.?\d*/); return m ? parseFloat(m[0].replace(/,/g, "")) : null; }
// onlyWards (a DXF network, user 30-Oct-2026): the KML's polygons only, each a ward - no roads, points, boundary
function fromKML(text, replace, onlyWards) {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.getElementsByTagName("parsererror").length) throw new Error("KML पढ़ा नहीं जा सका");
  if (replace) { drawn.clearLayers(); result.clearLayers(); zoneLayer.clearLayers(); designLayer.clearLayers(); select(null);
    $("zd").hidden = true; layoutData = null; tblReset(); $("files").innerHTML = ""; }
  const byTag = (el, tag) => Array.from(el.getElementsByTagNameNS("*", tag));
  const child = (el, tag) => Array.from(el.children).find(c => c.localName === tag);
  let n = { road: 0, boundary: 0, ward: 0, spot: 0, stp: 0, skipped: 0 };
  let hasBoundary = !!onlyWards;
  drawn.eachLayer(l => { if (l.kind === "boundary") hasBoundary = true; });
  const polys = [];
  for (const pmk of byTag(doc, "Placemark")) {
    const name = (child(pmk, "name")?.textContent || "").trim();
    let folder = "", el = pmk.parentElement;
    while (el) { if (el.localName === "Folder") { folder = (child(el, "name")?.textContent || ""); break; } el = el.parentElement; }
    const data = {};
    for (const d of byTag(pmk, "Data")) data[(d.getAttribute("name") || "").toLowerCase()] = byTag(d, "value")[0]?.textContent;
    for (const d of byTag(pmk, "SimpleData")) data[(d.getAttribute("name") || "").toLowerCase()] = d.textContent;
    const desc = child(pmk, "description")?.textContent || "";
    if (/<td/i.test(desc))                       // GIS exports (ArcGIS ...): the fields as a two-cell table
      for (const tr of new DOMParser().parseFromString(desc, "text/html").querySelectorAll("tr")) {
        const td = Array.from(tr.children).filter(c => c.localName === "td");
        if (td.length === 2 && !td[0].querySelector("table")) { const k = td[0].textContent.trim().toLowerCase(); if (k && !(k in data)) data[k] = td[1].textContent.trim(); }
      }
    const pop = ["population", "pop", "w_pop", "total_pop", "tot_pop", "jansankhya", "जनसंख्या"].map(k => data[k]).find(v => v != null && v !== "");
    const wname = data.w_name || data.ward_name || data.ward || "";
    const text = `${folder} ${name}`;
    for (const ls of onlyWards ? [] : byTag(pmk, "LineString")) {
      const c = parseCoords(byTag(ls, "coordinates")[0]?.textContent);
      if (c.length < 2) continue;
      if (folder === "Crossings" || data.kind === "crossing") {
        addFeature(L.polyline(c.map(a => [a[1], a[0]])), "crossing", { name, tol_m: data.tol_m ?? "", snap_m: data.snap_m ?? "" }); n.crossing = (n.crossing || 0) + 1; continue; }
      if (folder === "Barrier lines" || data.kind === "barrier") {
        addFeature(L.polyline(c.map(a => [a[1], a[0]])), "barrier", { name, type: data.type || "other", gap_m: data.gap_m ?? "1" }); n.barrier = (n.barrier || 0) + 1; continue; }
      addFeature(L.polyline(c.map(a => [a[1], a[0]])), "road", { name }); n.road++;
    }
    for (const pg of byTag(pmk, "Polygon")) {
      const ring = byTag(byTag(pg, "outerBoundaryIs")[0] || pg, "coordinates")[0];
      const c = parseCoords(ring?.textContent);
      if (folder === "Zone loops" || data.kind === "zone_loop") {          // a zone loop: no ward, no boundary
        if (c.length >= 3 && !onlyWards) { addFeature(L.polygon(c.map(a => [a[1], a[0]])), "zone_loop", { name, on_limit: data.on_limit || "" }); n.zone_loop = (n.zone_loop || 0) + 1; }
        continue; }
      // a polygon of (nearly) no area - all corners on one spot - is left out (it would count as a ward)
      const a2 = Math.abs(c.reduce((s_, a, i) => { const b = c[(i + 1) % c.length]; return s_ + a[0] * b[1] - b[0] * a[1]; }, 0)) / 2;
      if (c.length >= 3 && a2 > 1e-9) polys.push({ c, name: name || wname, text, pop: pop ?? null });
      else if (c.length >= 3) n.skipped++;
    }
    for (const p of onlyWards ? [] : byTag(pmk, "Point")) {
      const c = parseCoords(byTag(p, "coordinates")[0]?.textContent)[0];
      if (!c) continue;
      const ll = L.latLng(c[1], c[0]);
      if (folder === "Tube wells" || data.kind === "tw") {
        addFeature(L.marker(ll), "tw", { name, discharge_lpm: data.discharge_lpm ?? "" }); n.tw = (n.tw || 0) + 1; continue; }
      if (folder === "PRVs" || data.kind === "prv") {
        addFeature(L.marker(ll), "prv", { name, setting_m: data.setting_m ?? "" }); n.prv = (n.prv || 0) + 1; continue; }
      if (folder === "Bulk consumers" || data.kind === "bulk") {
        addFeature(L.marker(ll), "bulk", { name, kld: data.kld ?? "", peak: data.peak ?? "" }); n.bulk = (n.bulk || 0) + 1; continue; }
      if (/\bOHT\b|\bESR\b|टंकी/i.test(`${folder} ${name}`)) {
        const ex = data.existing !== undefined && data.existing !== "" ? data.existing : /^Ex-/i.test(name) ? "1"
          : (data.capacity_kl !== undefined && String(data.capacity_kl).trim() !== "" ? "1" : "0");
        addFeature(L.marker(ll), "oht", { name, existing: ex, capacity_kl: data.capacity_kl ?? "", staging_m: data.staging_m ?? "", tubewells: data.tubewells ?? "", rebore: data.rebore ?? "",
          low_head: data.low_head === "new_oht" ? "new_oht" : "vfd" });
        n.oht = (n.oht || 0) + 1; continue; }
      if (/stp|outfall|outlet|sps|ips|pump/i.test(name)) { addFeature(L.marker(ll), "stp", { name }); n.stp++; continue; }
      let gl = num(data.gl ?? data.level ?? data["ground level"] ?? data.rl);
      if (gl === null) gl = num(name);
      if (gl === null && c.length > 2 && Math.abs(c[2]) > 0.001) gl = c[2];
      if (gl !== null) { addFeature(L.marker(ll), "spot", { name, gl: gl.toFixed(2) }); n.spot++; } else n.skipped++;
    }
  }
  // polygons: population -> ward; 'boundary' in folder / name -> boundary; otherwise one is the boundary only when
  // it clearly is (see below), the rest wards
  const area = p => Math.abs(p.c.reduce((s, a, i) => { const b = p.c[(i + 1) % p.c.length]; return s + a[0] * b[1] - b[0] * a[1]; }, 0));
  let bnd = onlyWards ? null : polys.find(p => /boundary|सीमा/i.test(p.text) && (p.pop === null || /^\s*project boundary\b/i.test(p.text)));
  if (!bnd && !hasBoundary) {
    // no polygon called boundary: the one (without population) holding most of the roads - none if no polygon
    // holds at least half of them (then every polygon is a ward); without roads the largest
    const free = polys.filter(p => p.pop === null);
    const pts = []; drawn.eachLayer(l => { if (l.kind === "road") for (const ll of l.getLatLngs()) pts.push([ll.lng, ll.lat]); });
    const inRing = (pt, c) => { let ins = false;
      for (let i = 0, j = c.length - 1; i < c.length; j = i++)
        if ((c[i][1] > pt[1]) !== (c[j][1] > pt[1]) && pt[0] < (c[j][0] - c[i][0]) * (pt[1] - c[i][1]) / (c[j][1] - c[i][1]) + c[i][0]) ins = !ins;
      return ins; };
    if (pts.length && free.length) {
      const share = p => pts.filter(pt => inRing(pt, p.c)).length / pts.length;
      const best = free.reduce((a, b) => share(a) >= share(b) ? a : b);
      if (share(best) >= 0.5) bnd = best;
    } else if (free.length === 1 && polys.length === 1) bnd = free[0];
    else if (free.length) {
      // no roads: a polygon is the boundary only when it holds the middles of all the others - side by side
      // polygons (wards, each with its own boundary) are all wards
      const mid = p => { const xs = p.c.map(a => a[0]), ys = p.c.map(a => a[1]);
        return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2]; };
      const big = free.reduce((a, b) => area(a) >= area(b) ? a : b);
      if (polys.every(p => p === big || inRing(mid(p), big.c))) bnd = big;
    }
  }
  for (const p of polys) {
    const lls = p.c.map(a => [a[1], a[0]]);
    if (p === bnd) { drawn.eachLayer(l => { if (l.kind === "boundary") drawn.removeLayer(l); }); addFeature(L.polygon(lls), "boundary", { name: p.name || "Project boundary", population: p.pop !== null ? String(num(p.pop) ?? "") : "" }); n.boundary++; }
    else { addFeature(L.polygon(lls), "ward", { name: p.name, population: p.pop !== null ? String(num(p.pop) ?? "") : "" }); n.ward++; }
  }
  if (drawn.getLayers().length) map.fitBounds(drawn.getBounds(), { padding: [20, 20] });
  changed();
  return n;
}
