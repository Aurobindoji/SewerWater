// The water map page (map.html), part 10 of 11: a DXF network: import, layers, GL, problems, selection, find, tools.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---------------------------------------------------------------- DXF network: import, show, correct
const netRenderer = L.canvas({ padding: 0.3, tolerance: 6 });
const netLayer = new L.FeatureGroup(), issueLayer = new L.FeatureGroup(), textLayer = new L.FeatureGroup(), selLayer = new L.FeatureGroup();
let mode = "kml", NET = null, nodeMk = {}, condLn = {}, netSel = null, tool = "select", pick = null, openGroup = null;
const TYPE_HI = {
  "label matched in pass 2 - CHECK": "Label - CHECK (नज़दीकी text, संख्या मेल नहीं खाती)",
  "label matched in pass 2 - low risk": "Label - pass 2, कम जोखिम",
  "GL matched in pass 2 - CHECK": "GL - CHECK (पड़ोसियों से 1 m से ज़्यादा अलग)",
  "GL matched in pass 2 - low risk": "GL - pass 2, कम जोखिम",
  "no drawing label (name generated)": "Drawing में label नहीं (नाम बनाया)",
  "label suggested (nearest unused label) - CHECK": "Label सुझाव से लगाया - CHECK",
  "no ground level": "GL नहीं", "GL spike (> 2 m from all neighbours)": "GL spike (सब पड़ोसियों से > 2 m)",
  "near-miss gap": "सिरों के बीच gap (जुड़े नहीं)", "T-joint": "T-joint (line दूसरी line पर खत्म)",
  "loop": "Loop", "part without an outfall": "Outfall के बिना हिस्सा", "very short conduit": "बहुत छोटा pipe",
  "conduit label used twice": "Pipe label दो बार", "label used twice in the drawing": "Junction label दो बार",
  "manhole on a continuous line - check": "लगातार line पर junction (line काटी गई)",
  "manholes overlap, not joined": "Junctions एक-दूसरे पर, pipe से जुड़े नहीं (लाल ✕)",
};
const OVERLAP = "manholes overlap, not joined";
const TYPE_ORDER = Object.keys(TYPE_HI);

function setMode(m) {
  mode = m;
  $("kmlsec").hidden = m !== "kml"; $("netsec").hidden = m !== "dxf";
  $(m === "dxf" ? "propslot_dxf" : "propslot_kml").appendChild($("propwrap"));   // the selected item's panel
  for (const b of ["kmlget", "kmlopen"]) {             // a drawing (KML) of its own only for a map project
    const e = $(b), off = m === "dxf";
    if (off && !e.disabled) { e.dataset.help = e.title;           // its own help (start.js) kept for later
      e.title = tr("DXF वाले project में नहीं - KML वाला project \"नया (सब हटाएँ)\" से शुरू करें",
                   "Not in a DXF project - start a KML project with \"New (clear all)\""); }
    else if (!off && e.disabled) e.title = e.dataset.help || "";
    e.disabled = off;
  }
  $("psave").title = m === "dxf" ? tr("सुधारा हुआ network (CSV) और बदलावों की सूची सहेजें - zoning / design के लिए ज़रूरी नहीं",
                                      "save the corrected network (CSV) and the list of changes - not needed for zoning / design")
                                 : tr("नक्शे की drawing (KML) सहेजें", "save the drawing of the map (KML)");
  // (water: the OHTs placed on a DXF network are drawn features - the drawing stays on the map)
  if (m === "dxf") { stopDraw(); if (editing) toggleEdit(false); drawn.addTo(map);
    netLayer.addTo(map); issueLayer.addTo(map); selLayer.addTo(map); warnLayer.addTo(map); }
  else { drawn.addTo(map); for (const g of [netLayer, issueLayer, textLayer, selLayer, warnLayer]) map.removeLayer(g); }
}

// its panel is on the Network tab (user 16-Nov-2026: pressed on the Project tab, nothing seemed to happen)
$("dxfopen").onclick = () => { if (window.uiTab) uiTab("network"); $("dxfpanel").hidden = false;
  // the panel just below the sticky bar (title, Simple / Advanced, tabs) - scrollIntoView put its file picker under
  // that bar (user report 18-Nov-2026)
  const side = $("side"), bar = $("uibar");
  side.scrollTop += $("dxfpanel").getBoundingClientRect().top - (bar ? bar.getBoundingClientRect().bottom : side.getBoundingClientRect().top) - 8;
  $("dxfpath").focus({ preventScroll: true }); };
$("dxfclose").onclick = () => { $("dxfpanel").hidden = true; };
// a DXF picked in the file dialog: uploaded as it is (the page cannot know its path), then its layers read
// in the desktop app (app.py): Windows' own file dialog - the DXF is read where it lies, not uploaded; in a browser
// the file is picked and uploaded (the page cannot know its path)
$("dxfpick").onclick = async () => {
  const app = window.pywebview && window.pywebview.api && window.pywebview.api.pick_file;
  if (!app) return $("dxffile").click();
  const p = await window.pywebview.api.pick_file("dxf");
  if (!p) return;
  $("dxfpath").value = p; $("dxfstatus").textContent = "";
  $("dxflayers").onclick();                              // the next step at once: its layers
};
$("dxffile").onchange = async e => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  $("dxfstatus").className = "status"; $("dxfstatus").textContent = tr(`${f.name} भेज रहे हैं …`, `Sending ${f.name} …`);
  let r = null;
  await withLoading(tr(`${f.name} (${(f.size / 1048576).toFixed(1)} MB) भेज रहे हैं …`, `Sending ${f.name} (${(f.size / 1048576).toFixed(1)} MB) …`), async () => {
    r = await fetch("/api/w/dxf_upload?file=" + encodeURIComponent(f.name),
      { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: f }).then(x => x.json()).catch(err => ({ ok: false, log: String(err) }));
  });
  if (!r.ok) { $("dxfstatus").className = "status err"; $("dxfstatus").textContent = r.log; return; }
  $("dxfpath").value = r.path; $("dxfstatus").textContent = "";
  $("dxflayers").onclick();                              // the next step at once: its layers
};
let LAYERS = null;
$("dxflayers").onclick = async () => {
  // the project's name from the file's name at once, and a project of that name asked about before the drawing is
  // read (user request 16-Nov-2026: no wait for the layers - only the name is compared)
  $("dxfname").value = $("dxfpath").value.trim().replace(/^"|"$/g, "").split(/[\\/]/).pop().replace(/\.[^.]*$/, "");
  const nameNote = (await dxfNameOk()) ? "" : $("dxfstatus").textContent;
  $("dxfstatus").className = "status"; $("dxfstatus").textContent = "Drawing पढ़ रहे हैं …";
  const r = await withLoading(tr("Drawing पढ़ रहे हैं …", "Reading the drawing …"), () => api("/api/dxf_layers", { path: $("dxfpath").value }));
  if (!r.ok) { $("dxfstatus").className = "status err"; $("dxfstatus").textContent = r.log; return; }
  LAYERS = r; $("dxfstatus").textContent = nameNote; $("dxfstatus").className = nameNote ? "status err" : "status";
  const rows = r.layers.filter(l => l.line_m > 0 || l.texts > 0 || l.blocks > 0 || l.circles > 0);
  const ck = (kind, lay) => `<input type="checkbox" data-k="${kind}" value="${esc(lay)}"${r.guess[kind === "gl" ? "level" : kind].includes(lay) && kind !== "gl" ? " checked" : ""}>`;
  $("laybox").innerHTML = `<table class="lay"><tr><th title="नक्शे पर देखें">👁</th><th>Layer</th><th title="lines की लंबाई (m)">Lines m</th><th>Texts</th><th title="N-12 / J-12 जैसे नाम">नाम</th><th title="81.25 जैसे स्तर">स्तर</th><th title="blocks / circles - junction के चिह्न">Symbols</th><th>Pipe</th><th title="junction / node: चिह्न या नाम की layer">Junction</th><th>GL</th></tr>` +
    rows.map(l => `<tr><td><button class="txtbtn lprev" data-l="${esc(l.layer)}" title="इस layer की lines / बिंदु नक्शे पर, अपने रंग में (कई layers एक साथ; दोबारा click = बंद)">👁</button></td><td title="${esc(l.layer)}">${esc(l.layer)}</td><td>${Math.round(l.line_m).toLocaleString("en-IN")}</td><td>${l.texts}</td><td>${l.ids}</td><td>${l.levels}</td><td>${(l.blocks || 0) + (l.circles || 0)}</td>
      <td>${l.line_m > 0 ? ck("pipe", l.layer) : ""}</td><td>${ck("mh", l.layer)}</td><td>${l.levels ? ck("gl", l.layer) : ""}</td></tr>`).join("") +
    `</table><div id="prevbox" class="hint"></div><div class="hint">${tr("Pipe = pipelines की layers; Junction = junction / node / valve के चिह्न या नाम की layers", "Pipe = layers of the pipelines; Junction = layers of junction / node / valve symbols or names")}; ` +
    tr(`GL खाली छोड़ें तो सबसे उपयुक्त layer अपने-आप (सुझाव: ${esc(r.guess.level.join(", ") || "-")}). 👁 से layers की lines, texts (पास zoom पर शब्द) और चिह्न (बिंदु) नक्शे पर देखकर पक्का करें - कई 👁 एक साथ, हर layer अपने रंग में; उसी 👁 पर दोबारा click = वह layer बंद। Pipe / Junction / GL में tick करते ही वह layer नक्शे पर, tick हटाते ही बंद। नाला, सड़क, भवन, घरों के नाम pipe / junction नहीं हैं`,
       `leave GL empty for the best layer automatically (suggested: ${esc(r.guess.level.join(", ") || "-")}). Check layers with 👁 - their lines, texts (words when zoomed in) and symbols (points) on the map, several at once, each in its own colour; the same 👁 again = that layer off. A tick under Pipe / Junction / GL shows that layer at once, untick hides it. Drains, roads, buildings, house names are no pipes / junctions`) + `</div>`;
  document.querySelectorAll("#laybox .lprev").forEach(b => b.onclick = () => previewLayer(b.dataset.l, b));
  document.querySelectorAll("#laybox input[data-k]").forEach(i => i.onchange = () => tickPreview(i.value));
  tickAll();                                                        // the suggested layers on the map at once
  if (!$("dxfname").value.trim()) $("dxfname").value = r.name;     // (set from the file's name before the reading)
  $("dxfopts").hidden = false;
};
// ---- layers of the drawing on the map (before choosing the layers): several at once, each in its own colour - its
// lines, and its texts / symbols as points with their text (user request 22-Oct-2026)
const prevLayer = L.layerGroup().addTo(map);
const PREV_COLOURS = ["#e53935", "#1e88e5", "#43a047", "#8e24aa", "#fb8c00", "#00897b", "#d81b60", "#6d4c41", "#3949ab", "#c0ca33"];
const PREV = new Map();                                      // layer -> {group, colour, info}
const prevBtn = layer => document.querySelector(`#laybox .lprev[data-l="${CSS.escape(layer)}"]`);
function prevBox() {
  if (!$("prevbox")) return;
  $("prevbox").innerHTML = !PREV.size ? "" : [...PREV].map(([layer, v]) =>
    `<div style="margin-top:4px"><span style="display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:middle;background:${v.colour}"></span> ${v.info}</div>`).join("") +
    (PREV.size > 1 ? `<div class="row" style="margin-top:4px"><button id="prevall">${tr("सब 👁 बंद करें", "Hide all 👁")}</button></div>` : "");
  if ($("prevall")) $("prevall").onclick = clearPreview;
}
function prevFit() {
  const all = []; PREV.forEach(v => v.group.eachLayer(l => all.push(l)));
  if (all.length) map.fitBounds(L.featureGroup(all).getBounds(), { padding: [30, 30], maxZoom: 19 });
}
function hidePreview(layer) {
  const v = PREV.get(layer); if (!v) return;
  prevLayer.removeLayer(v.group); PREV.delete(layer);
  const b = prevBtn(layer); if (b) { b.classList.remove("on"); b.style.background = b.style.borderColor = ""; }
}
function clearPreview() { [...PREV.keys()].forEach(hidePreview); prevLayer.clearLayers(); prevBox(); }
async function previewLayer(layer, btn, fit = true) {
  if (PREV.has(layer)) { hidePreview(layer); prevBox(); return; }       // the same 👁 again: that layer off
  const r = await withLoading(tr(`"${layer}" पढ़ रहे हैं …`, `Reading "${layer}" …`),
    () => api("/api/dxf_preview", { path: $("dxfpath").value, layer, epsg: $("dxfepsg").value }));
  if (!r.ok) { $("prevbox").textContent = r.log; return; }
  const used = new Set([...PREV.values()].map(v => v.colour));
  const colour = PREV_COLOURS.find(c => !used.has(c)) || PREV_COLOURS[PREV.size % PREV_COLOURS.length];
  const group = L.layerGroup().addTo(prevLayer);
  for (const ln of r.lines) L.polyline(ln, { color: colour, weight: 3, opacity: .9, renderer: netRenderer, interactive: false }).addTo(group);
  // a block / circle: a point filled in the layer's colour, white rim; a text: its words at its insertion point
  // (zoomed in, PREV_TEXT_ZOOM; further out a small point - user request 22-Oct-2026)
  const words = [], dots = [];
  for (const p of r.points) {
    if (p[3] !== "text") {
      L.circleMarker([p[0], p[1]], { radius: 4, color: "#fff", weight: 1.5, fillColor: colour, fillOpacity: 1, renderer: netRenderer })
        .bindTooltip(`${esc(p[2])} <span class="hint">(${esc(layer)}, ${esc(p[3])})</span>`, { direction: "top" }).addTo(group);
      continue;
    }
    words.push(L.marker([p[0], p[1]], { interactive: false, keyboard: false,
      icon: L.divIcon({ className: "prevtxt", html: `<div style="color:${colour}">${esc(p[2])}</div>`, iconSize: null, iconAnchor: [0, 11] }) }));
    dots.push(L.circleMarker([p[0], p[1]], { radius: 2.5, color: colour, weight: 1, fillColor: colour, fillOpacity: 1, renderer: netRenderer })
      .bindTooltip(`${esc(p[2])} <span class="hint">(${esc(layer)}, text)</span>`, { direction: "top" }));
  }
  const types = Object.entries(r.types).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join(", ");
  const info = `<b>${esc(layer)}</b>: ${esc(types)}` +
    (r.n_lines ? `<br>${tr("lines", "lines")}: ${r.n_lines}, ${fmt(r.line_m)} m, ${tr("औसत", "average")} ${fmt(r.avg_line_m, 1)} m ${tr("प्रति line", "per line")}` : "") +
    (r.samples.length ? `<br>${tr("texts जैसे", "texts like")}: ${r.samples.map(t => `<code>${esc(t)}</code>`).join(" ")}` : "") +
    (r.blocks.length ? `<br>${tr("blocks", "blocks")}: ${r.blocks.map(esc).join(", ")}` : "") +
    (r.truncated ? `<br>${tr("(बहुत अधिक - कुछ ही दिखाए)", "(too many - only some shown)")}` : "") +
    (r.local ? `<br>${tr("Local coordinates: नक्शे पर 0, 0 के पास (असली जगह नहीं)", "Local coordinates: shown around 0, 0 (not the real place)")}` : "");
  PREV.set(layer, { group, colour, info, words, dots, shown: null });
  btn.classList.add("on"); btn.style.background = btn.style.borderColor = colour;
  prevTexts(); if (fit) prevFit(); prevBox();
}
// a tick under Pipe / Junction / GL shows its layer on the map at once, the last tick of a layer taken off hides it - the
// chosen layers seen together before the import (user request 17-Nov-2026); the drawing is read once, so it is quick
const PREV_BUSY = new Set();
const ticked = layer => [...document.querySelectorAll("#laybox input[data-k]")].some(i => i.value === layer && i.checked);
async function tickPreview(layer, fit = !PREV.size) {
  if (PREV_BUSY.has(layer) || ticked(layer) === PREV.has(layer)) return;
  if (!ticked(layer)) { hidePreview(layer); prevBox(); return; }
  const btn = prevBtn(layer); if (!btn) return;
  PREV_BUSY.add(layer);
  try { await previewLayer(layer, btn, fit); } finally { PREV_BUSY.delete(layer); }
  if (!ticked(layer) && PREV.has(layer)) { hidePreview(layer); prevBox(); }   // ticked off while it was read
}
async function tickAll() {
  const lays = [...new Set([...document.querySelectorAll("#laybox input[data-k]:checked")].map(i => i.value))];
  for (const l of lays) await tickPreview(l, false);
  prevFit();
}
// the texts of the layers shown: their words from PREV_TEXT_ZOOM on, small points further out (too many to read there)
const PREV_TEXT_ZOOM = 17;
function prevTexts() {
  const want = map.getZoom() >= PREV_TEXT_ZOOM ? "words" : "dots";
  PREV.forEach(v => {
    if (v.shown === want) return;
    if (v.shown) v[v.shown].forEach(l => v.group.removeLayer(l));
    v[want].forEach(l => v.group.addLayer(l));
    v.shown = want;
  });
}
map.on("zoomend", prevTexts);
$("dxfclose").addEventListener("click", clearPreview);
$("dxfepsg").addEventListener("change", async () => {          // another EPSG: every layer shown read again
  const shown = [...PREV.keys()];
  clearPreview();
  for (const l of shown) { const b = prevBtn(l); if (b) await previewLayer(l, b); }
});
// ---- where the GL comes from (user request 22-Oct-2026): every layer with decimal texts ("78.25m") - how many, how many
// are the lengths of their pipes (left out), their range, how many junctions have one near - the best one ticked;
// the user confirms (or takes another, two, or none) and only then is the network extracted
// Z of the line ends too (user question 22-Oct-2026 'Z वाला विकल्प नहीं है?'): its own row - ticked, Z comes first (the
// texts where there is no Z: Z_MODE "first"); not ticked, the texts first and Z only where there is no text and it
// agrees with them ("auto"); nothing ticked: no GL from the drawing ("off")
let GL_NONE = false, Z_MODE = "auto";
async function glOptions(run) {
  const sel = k => Array.from(document.querySelectorAll(`#laybox input[data-k="${k}"]:checked`)).map(i => i.value);
  GL_NONE = false; Z_MODE = "auto";
  if (!sel("pipe").length) return run();                      // the import says what is missing
  const r = await withLoading(tr("GL के विकल्प खोज रहे हैं …", "Looking for the GL layers …"),
    () => api("/api/dxf_gl_options", { path: $("dxfpath").value, pipe_layers: sel("pipe"), mh_layers: sel("mh") }));
  if (!r.ok) { $("dxfstatus").className = "status err"; $("dxfstatus").textContent = r.log; return; }
  if (!r.options.length && !r.z.junctions) { GL_NONE = true; Z_MODE = "off"; return run(); }   // nothing to choose
  const f = v => v === null || v === undefined ? "-" : Number(v).toFixed(2);
  $("glbox").innerHTML = `<div class="box" style="margin-top:6px"><b>${tr("GL कहाँ से? - चुनकर पक्का करें", "Where does the GL come from? - tick and confirm")}</b>
    <div class="hint">${tr(`इन layers में GL जैसे (दशमलव वाले) texts हैं। सबसे उपयुक्त पहले से चुनी है - देखकर पक्का करें, दूसरी चुनें, या कोई नहीं। जो text अपने pipe की लंबाई के बराबर है (pipe के बीच में लिखा), वह GL नहीं माना जाता।`,
      `These layers have GL-like (decimal) texts. The most suitable one is ticked - check and confirm, take another, or none. A text equal to the length of its pipe (written along its middle) is no GL.`)}</div>
    <table class="lay"><tr><th></th><th>Layer</th><th>${tr("Texts", "Texts")}</th><th title="${tr("pipe की लंबाई के बराबर - GL नहीं माने जाएँगे", "equal to the length of their pipe - not taken as GL")}">${tr("लंबाई", "Lengths")}</th>
      <th>${tr("दायरा (median)", "range (median)")}</th><th title="${tr("10 m के भीतर इस layer का GL text", "a GL text of this layer within 10 m")}">${tr("Junctions के पास", "near junctions")}</th><th>${tr("उदाहरण", "samples")}</th><th>👁</th></tr>` +
    r.options.map(o => `<tr><td><input type="checkbox" data-gl="${esc(o.layer)}"${r.guess.includes(o.layer) ? " checked" : ""}></td>
      <td>${esc(o.layer)}${o.level_like ? "" : ` <span class="hint">(${tr("GL जैसा नहीं", "not like GL")})</span>`}</td><td>${o.texts}</td>
      <td>${o.lengths ? `<span style="color:#c62828" title="${tr("ये GL नहीं माने जाएँगे", "these are not taken as GL")}">⚠ ${o.lengths}</span>` : "-"}</td>
      <td>${o.min === null ? "-" : `${f(o.min)} - ${f(o.max)} (${f(o.median)})`}</td><td>${o.near} / ${r.junctions}</td>
      <td>${o.samples.map(t => `<code>${esc(t)}</code>`).join(" ")}</td>
      <td><button class="txtbtn" data-glprev="${esc(o.layer)}" title="${tr("इस layer के texts नक्शे पर", "this layer's texts on the map")}">👁</button></td></tr>`).join("") +
    (r.z.junctions ? `<tr><td><input type="checkbox" id="glz"${r.z_guess ? " checked" : ""}></td>
      <td title="${tr("Pipe lines के सिरों की Z (3D drawing)", "Z of the pipe lines' ends (a 3D drawing)")}">${tr("Z (lines की ऊँचाई)", "Z (height of the lines)")}${r.z.ground_like ? "" : ` <span class="hint">(${tr("GL जैसा नहीं", "not like GL")})</span>`}</td>
      <td>-</td><td>-</td><td>${f(r.z.min)} - ${f(r.z.max)} (${f(r.z.median)})</td><td>${r.z.junctions} / ${r.junctions}</td>
      <td>${tr(`${r.z.distinct} अलग मान`, `${r.z.distinct} different values`)}` +
      (r.z.distinct < Math.max(5, 0.1 * r.z.junctions) ? ` <span style="color:#c62828">⚠ ${tr("बहुत कम - पूरी lines की elevation लगती है, ज़मीन नहीं", "too few - the elevation of whole lines, not the ground")}</span>` : "") +
      (r.z.text_diff !== null ? `; ${tr("texts से", "from the texts")} ${f(r.z.text_diff)} m` +
        (r.z.text_diff > 1 ? ` <span style="color:#c62828">⚠</span>` : "") : "") + `</td><td></td></tr>` : "") +
    `</table><div class="row" style="margin-top:6px"><button id="glok" class="primary">${tr("पक्का करें - network निकालें", "Confirm - extract the network")}</button>
      <button id="glcancel">${tr("रद्द", "Cancel")}</button></div>
    <div class="hint">${tr("Z चुनें तो GL पहले lines की Z से (texts वहाँ जहाँ Z नहीं); सिर्फ़ layer चुनें तो पहले texts से, और Z केवल वहाँ जहाँ text नहीं और Z texts से मेल खाए (1 m)। कुछ न चुनें तो GL drawing से नहीं - बाद में तालिका से भरें या \"अपने-आप सुधार\" pipes के साथ भरेगा।",
      "Z ticked: the GL from the lines' Z first (the texts where there is no Z); only layers ticked: from the texts first, Z only where there is no text and it agrees with the texts (1 m). Nothing ticked: no GL from the drawing - fill it in the table later, or the auto repair fills it along the pipes.")}</div></div>`;
  $("glbox").hidden = false;
  $("glbox").scrollIntoView({ block: "nearest" });
  $("glbox").querySelectorAll("[data-glprev]").forEach(b => b.onclick = () => {
    const lb = prevBtn(b.dataset.glprev); if (lb) previewLayer(b.dataset.glprev, lb); });
  $("glcancel").onclick = () => { $("glbox").hidden = true; };
  $("glok").onclick = () => {
    const chosen = [...$("glbox").querySelectorAll("[data-gl]:checked")].map(i => i.dataset.gl);
    document.querySelectorAll('#laybox input[data-k="gl"]').forEach(i => { i.checked = chosen.includes(i.value); });
    const z = $("glz") && $("glz").checked;
    GL_NONE = !chosen.length;
    Z_MODE = z ? "first" : (chosen.length ? "auto" : "off");
    $("glbox").hidden = true;
    run();
  };
}
// a project of this name already there (user request 16-Nov-2026): the import would replace it without a word -
// asked as soon as a DXF is chosen (before its layers are read), not again at the import; Cancel suggests a free name.
async function dxfNameOk() {
    const stem = s => (s || "").trim().replace(/[^\p{L}\p{N}\p{M}_-]+/gu, " ").trim().replace(/\s+/g, "_").slice(0, 80) || "project";
    let have = null;
    try { const p = await api("/api/projects"); have = (p.projects || []).find(x => x.name === stem($("dxfname").value)); } catch (e) { }
    if (have && !confirm(have.kind === "dxf"
        ? tr(`"${have.name}" नाम का project पहले से है। यह DXF उसी पर खुलेगा: उसके network के सारे सुधार (junction मिलाना, pipe जोड़ना, GL ...) हट जाएँगे और zoning / design दोबारा करनी होगी (टंकियाँ, वार्ड जैसी रखी चीज़ें बची रहेंगी)।\n\nOK = उसी पर खोलें, Cancel = रुकें और नया नाम दें`,
             `A project "${have.name}" is already there. This DXF would open over it: all the corrections of its network (merged junctions, joined pipes, GL ...) go and the zoning / design must be made again (the tanks, wards and other placed items stay).\n\nOK = open over it, Cancel = stop and give a new name`)
        : tr(`"${have.name}" नाम का नक्शे वाला (KML) project पहले से है। इसी नाम से DXF project बनाने पर दोनों एक-दूसरे में उलझेंगे।\n\nOK = फिर भी आगे बढ़ें, Cancel = रुकें और नया नाम दें`,
             `A map (KML) project "${have.name}" is already there. A DXF project of the same name would get mixed up with it.\n\nOK = go on anyway, Cancel = stop and give a new name`))) {
      let k = 2; const base = stem($("dxfname").value);
      const names = new Set(((await api("/api/projects").catch(() => ({}))).projects || []).map(x => x.name));
      while (names.has(`${base}_${k}`)) k++;
      $("dxfname").value = `${base}_${k}`; $("dxfname").focus(); $("dxfname").select();
      $("dxfstatus").className = "status err";
      $("dxfstatus").textContent = tr(`नया नाम सुझाया: ${base}_${k} - चाहें तो बदलें`, `A new name suggested: ${base}_${k} - change it if you like`);
      return false;
    }
    return true;
}
$("dxfimport").onclick = async () => {
  const sel = k => Array.from(document.querySelectorAll(`#laybox input[data-k="${k}"]:checked`)).map(i => i.value);
  if (!sel("pipe").length) { $("dxfstatus").className = "status err"; $("dxfstatus").textContent = "कम से कम एक Pipe layer चुनें।"; return; }
  if (mode === "kml" && dirty && drawn.getLayers().length && !confirm("नक्शे पर खींचा बिना सहेजा काम हट जाएगा। आगे बढ़ें?")) return;
  $("dxfimport").disabled = true; $("dxfstatus").className = "status"; $("dxfstatus").textContent = "Network निकाल रहे हैं … (बड़ी drawing में लगभग 1 मिनट)";
  loading(true, tr("Network निकाल रहे हैं … (बड़ी drawing में लगभग 1 मिनट)", "Extracting the network … (about 1 minute for a big drawing)"));
  try {
    const r = await api("/api/dxf_import", { name: $("dxfname").value, path: $("dxfpath").value, pipe_layers: sel("pipe"),
      node_prefix: $("dnpre").value.trim(), pipe_prefix: $("dppre").value.trim(),
      mh_layers: sel("mh"), level_layers: sel("gl").length ? sel("gl") : (GL_NONE ? ["(no GL layer)"] : []), z_mode: Z_MODE, epsg: $("dxfepsg").value,
      joints_only: $("djoints").checked });
    $("log").hidden = !r.log; $("log").textContent = r.log || "";
    if (!r.ok) { $("dxfstatus").className = "status err"; $("dxfstatus").textContent = "Network नहीं निकला - नीचे का संदेश देखें।"; return; }
    $("dxfpanel").hidden = true; $("dxfstatus").textContent = ""; clearPreview(); clearNetPrev(); $("glbox").hidden = true;
    showNet(r, true); refreshList(); await loadDxfOhts(r.name);
    status(`DXF network: ${r.summary.manholes} junctions, ${r.summary.conduits} pipes - गड़बड़ियाँ नीचे`, "ok");
  } finally { $("dxfimport").disabled = false; loading(false); }
};

// ---- the whole network of the ticked layers on the map, nothing saved (user request 18-Nov-2026): what the import would
// make - the largest part blue, other parts orange, open ends red - with the counts; a tick changed afterwards marks it
// as old (it is not made again by itself: a big drawing takes a while)
// the drawing's problems (dxf_extract's English texts, by their start) in Hindi on a Hindi page
const PROB_HI = [
  [/^no junction label in the drawing/, () => "Drawing में junction का नाम नहीं (नाम बनाया गया)"],
  [/^junction label used by more than one junction/, () => "एक ही नाम कई junctions पर"],
  [/^no GL$/, () => "GL नहीं"],
  [/^near-miss gap/, () => "सिरे पास-पास, पर जुड़े नहीं"],
  [/^line ends on another line without a node/, () => "Line दूसरी line पर ख़त्म, वहाँ junction नहीं"],
  [/^junction on a continuous line/, () => "लगातार line पर junction - line वहाँ काटी गई (CAD में जाँचें)"],
  [/^GL matched in pass 2 - within 1 m/, () => "GL दूसरे दौर में मिला - पड़ोसियों से 1 m के भीतर (कम जोखिम)"],
  [/^GL matched in pass 2 \(nearest free text\)/, () => "GL दूसरे दौर में मिला (सबसे पास का text) - CAD में जाँचें"],
  [/^label matched in pass 2 - number fits/, () => "नाम दूसरे दौर में मिला - पड़ोसी से मेल (कम जोखिम)"],
  [/^label matched in pass 2 \(nearest free text\)/, () => "नाम दूसरे दौर में मिला (सबसे पास का text) - CAD में जाँचें"],
  [/^level far from the drawing's other levels/, () => "Level बाकी levels से बहुत दूर - नहीं लिया (टाइपिंग की गलती?)"],
  [/^(\d+) line\(s\) drawn twice/, m => `${m[1]} lines दो बार खींची थीं - एक-एक रखी`],
  [/^(\d+) separate parts/, m => `${m[1]} अलग टुकड़े`],
];
const probText = k => { for (const [re, f] of PROB_HI) { const m = k.match(re); if (m) return tr(f(m), k); } return k; };
const netPrev = L.layerGroup().addTo(map);
const netPrevJn = L.layerGroup();                 // the junctions that are no open end: only zoomed in (PREV_TEXT_ZOOM)
const netPrevZoom = () => { const on = netPrev.getLayers().length && map.getZoom() >= PREV_TEXT_ZOOM;
  if (on && !map.hasLayer(netPrevJn)) netPrevJn.addTo(map); else if (!on && map.hasLayer(netPrevJn)) map.removeLayer(netPrevJn); };
map.on("zoomend", netPrevZoom);
function clearNetPrev() { netPrev.clearLayers(); netPrevJn.clearLayers(); netPrevZoom(); $("netprevbox").hidden = true; $("netprevbox").innerHTML = ""; }
$("dxfclose").addEventListener("click", clearNetPrev);
$("laybox").addEventListener("change", e => {
  if (e.target.dataset.k && !$("netprevbox").hidden && !$("netprevold")) $("netprevbox").insertAdjacentHTML("afterbegin",
    `<div id="netprevold" class="warn">${tr("Layers बदलीं - यह पुराना network है; \"Network देखें\" फिर दबाएँ", "The layers changed - this is the old network; press \"Show network\" again")}</div>`);
});
$("dxfnetprev").onclick = async () => {
  const sel = k => Array.from(document.querySelectorAll(`#laybox input[data-k="${k}"]:checked`)).map(i => i.value);
  if (!sel("pipe").length) { $("dxfstatus").className = "status err"; $("dxfstatus").textContent = tr("कम से कम एक Pipe layer चुनें।", "Tick at least one Pipe layer."); return; }
  const r = await withLoading(tr("Network बना रहे हैं (सहेजा नहीं जाएगा) …", "Making the network (not saved) …"),
    () => api("/api/dxf_netpreview", { path: $("dxfpath").value, pipe_layers: sel("pipe"), mh_layers: sel("mh"), level_layers: sel("gl"),
      epsg: $("dxfepsg").value, joints_only: $("djoints").checked, node_prefix: $("dnpre").value.trim(), pipe_prefix: $("dppre").value.trim() }));
  if (!r.ok) { $("dxfstatus").className = "status err"; $("dxfstatus").textContent = r.log; return; }
  $("dxfstatus").textContent = "";
  clearPreview();                         // the layers' own 👁 look shown no more: its red would read as open ends
  netPrev.clearLayers(); netPrevJn.clearLayers();
  for (const [part, pts] of r.pipes)
    L.polyline(pts, { color: part === 1 ? "#1565c0" : "#ef6c00", weight: part === 1 ? 3 : 4, opacity: .9, renderer: netRenderer, interactive: false }).addTo(netPrev);
  for (const [lat, lon, name, gl, deg] of r.nodes) {
    const end = deg === 1;
    L.circleMarker([lat, lon], { radius: end ? 4 : 2.5, color: end ? "#fff" : "#37474f", weight: end ? 1.5 : 1,
      fillColor: end ? "#d32f2f" : "#37474f", fillOpacity: 1, renderer: netRenderer })
      .bindTooltip(`${esc(name)} - ${deg} pipe${deg === 1 ? "" : "s"}, GL ${gl === null || gl === undefined ? "-" : fmt(gl, 2)}`, { direction: "top" }).addTo(end ? netPrev : netPrevJn);
  }
  const s = r.summary, bad = (v, t) => v ? `<b style="color:var(--danger)">${t}</b>` : t;
  const probs = Object.entries(r.problems).sort((a, b) => b[1] - a[1]);
  $("netprevbox").innerHTML = `<div class="box" style="margin-top:6px"><b>${tr("Network का पूर्वावलोकन (सहेजा नहीं)", "Network preview (not saved)")}</b><br>` +
    `${s.junctions.toLocaleString("en-IN")} junctions, ${s.pipes.toLocaleString("en-IN")} pipes, ${fmt(s.length / 1000, 2)} km; ` +
    bad(s.parts > 1, tr(`${s.parts} अलग टुकड़े`, `${s.parts} separate parts`)) + ` (<span style="color:#1565c0">■</span> ${tr("सबसे बड़ा", "largest")}, <span style="color:#ef6c00">■</span> ${tr("बाकी", "others")}); ` +
    `<span style="color:#d32f2f">●</span> ${tr(`${s.ends} खुले सिरे (बाकी junctions पास zoom पर)`, `${s.ends} open ends (the other junctions when zoomed in)`)}; ` + bad(s.no_gl, tr(`${s.no_gl} बिना GL`, `${s.no_gl} without GL`)) +
    (probs.length ? `<details style="margin-top:4px"><summary style="cursor:pointer">${tr("Drawing की गड़बड़ियाँ", "problems of the drawing")}: ${probs.reduce((a, p) => a + p[1], 0).toLocaleString("en-IN")}</summary>` +
      probs.map(([k, v]) => `<div>${/^\d/.test(k) && v === 1 ? "" : `${v.toLocaleString("en-IN")} x `}${esc(probText(k))}</div>`).join("") + `</details>` : "") +
    `<div class="row" style="margin-top:4px"><button id="netprevclear">${tr("हटाएँ", "Remove")}</button>` +
    `<span class="hint" style="min-width:0">${tr("ठीक लगे तो \"Network निकालें\"; नहीं तो layers बदलकर फिर देखें", "fine: \"Extract network\"; else change the layers and look again")}</span></div></div>`;
  $("netprevbox").hidden = false;
  $("netprevclear").onclick = clearNetPrev;
  const b = L.featureGroup(netPrev.getLayers()).getBounds();
  if (b.isValid()) map.fitBounds(b, { padding: [30, 30], maxZoom: 19 });
  netPrevZoom();
};

// a survey drawing's roads as the map's own layout (user request 17-Nov-2026): the layers ticked as Pipe are the road
// centrelines, those ticked as GL the levels (none: the drawing's own level layers and survey points); they come onto
// the map as a KML project (roads + GL points), the layout is then made as for a KML
$("dxfroads").onclick = async () => {
  const sel = k => Array.from(document.querySelectorAll(`#laybox input[data-k="${k}"]:checked`)).map(i => i.value);
  const err = m => { $("dxfstatus").className = "status err"; $("dxfstatus").textContent = m; };
  if (!sel("pipe").length) return err(tr("सड़क-केंद्र रेखा (centre line) की layer को Pipe column में चुनें।", "Tick the road centreline layer in the Pipe column."));
  if ($("dxfepsg").value === "local") return err(tr("सड़कों से layout नक्शे पर बनता है - Coordinates में UTM चुनें।", "The road layout is made on the map - choose a UTM system under Coordinates."));
  if (dirty && drawn.getLayers().length && !confirm("नक्शे पर खींचा बिना सहेजा काम हट जाएगा। आगे बढ़ें?")) return;
  const r = await withLoading(tr("सड़कें और GL पढ़ रहे हैं …", "Reading the roads and levels …"),
    () => api("/api/dxf_roads", { path: $("dxfpath").value, road_layers: sel("pipe"), level_layers: sel("gl"), epsg: $("dxfepsg").value }));
  if (!r.ok) return err(r.log);
  $("dxfpanel").hidden = true; $("dxfstatus").textContent = ""; clearPreview(); clearNetPrev(); $("glbox").hidden = true;
  await openKml(`${$("dxfname").value.trim() || "roads"}_roads`, r.kml, true);
  if ($("glmode")) $("glmode").value = "spots";
  status(tr(`Drawing से ${r.roads} सड़कें और ${r.spots} GL बिंदु नक्शे पर` + (r.far ? ` (${r.far} दूर के level छोड़े)` : "") +
            " - अब boundary / टंकियाँ जोड़ें, 'सहेजें' दबाएँ और Layout बनाएँ (GL: spot levels)",
            `${r.roads} roads and ${r.spots} GL points of the drawing on the map` + (r.far ? ` (${r.far} far levels left out)` : "") +
            " - now add the boundary / tanks, press Save and make the layout (GL: spot levels)"), "ok");
};

function remember(name, kind) {        // the project open now: opened again after a page reload (F5)
  try { if (name) localStorage.setItem(LS_LAST, JSON.stringify({ name, kind })); else localStorage.removeItem(LS_LAST); } catch (e) { }
}
// the OHTs of a DXF network's project (water): kept on the server, a moment after each change
let ohtSaveT = null;
function saveDxfOhts() {
  clearTimeout(ohtSaveT);
  const name = NET && NET.name;
  ohtSaveT = setTimeout(() => {
    const ohts = [], barriers = [], loops = [], crossings = [], wards = [], bulk = [], prv = [], tw = [];
    drawn.eachLayer(l => { if (l.kind === "oht") { const ll = l.getLatLng(); ohts.push({ latlng: [ll.lat, ll.lng], props: l.props }); }
      if (l.kind === "bulk") { const ll = l.getLatLng(); bulk.push({ latlng: [ll.lat, ll.lng], props: l.props }); }
      if (l.kind === "prv") { const ll = l.getLatLng(); prv.push({ latlng: [ll.lat, ll.lng], props: l.props }); }
      if (l.kind === "tw") { const ll = l.getLatLng(); tw.push({ latlng: [ll.lat, ll.lng], props: l.props }); }
      if (l.kind === "barrier") barriers.push({ latlngs: l.getLatLngs().map(ll => [ll.lat, ll.lng]), props: l.props });
      if (l.kind === "zone_loop") loops.push({ latlngs: l.getLatLngs()[0].map(ll => [ll.lat, ll.lng]), props: l.props });
      if (l.kind === "ward") wards.push({ latlngs: l.getLatLngs()[0].map(ll => [ll.lat, ll.lng]), props: l.props });
      if (l.kind === "crossing") crossings.push({ latlngs: l.getLatLngs().map(ll => [ll.lat, ll.lng]), props: l.props }); });
    if (name) { api("/api/ohts_save", { name, ohts }).catch(() => { }); api("/api/barriers_save", { name, barriers }).catch(() => { });
      api("/api/loops_save", { name, loops }).catch(() => { });
      api("/api/crossings_save", { name, crossings }).catch(() => { });
      api("/api/wards_save", { name, wards }).catch(() => { });
      api("/api/bulk_save", { name, bulk }).catch(() => { });
      api("/api/prv_save", { name, prv }).catch(() => { });
      api("/api/tw_save", { name, tw }).catch(() => { }); }
  }, 400);
}
async function loadDxfOhts(name) {
  const r = await api("/api/ohts?name=" + encodeURIComponent(name)).catch(() => null);
  for (const o of (r && r.ohts) || []) addFeature(L.marker(o.latlng), "oht", o.props);
  const b = await api("/api/barriers?name=" + encodeURIComponent(name)).catch(() => null);
  for (const x of (b && b.barriers) || []) addFeature(L.polyline(x.latlngs), "barrier", x.props);
  const lo = await api("/api/loops?name=" + encodeURIComponent(name)).catch(() => null);
  for (const x of (lo && lo.loops) || []) addFeature(L.polygon(x.latlngs), "zone_loop", x.props);
  const xs = await api("/api/crossings?name=" + encodeURIComponent(name)).catch(() => null);
  for (const x of (xs && xs.crossings) || []) addFeature(L.polyline(x.latlngs), "crossing", x.props);
  const wd = await api("/api/wards?name=" + encodeURIComponent(name)).catch(() => null);
  for (const x of (wd && wd.wards) || []) addFeature(L.polygon(x.latlngs), "ward", Object.assign({}, x.props, x.props && x.props.character ? { character: charName(x.props.character) } : {}));
  const bk = await api("/api/bulk?name=" + encodeURIComponent(name)).catch(() => null);
  for (const x of (bk && bk.bulk) || []) addFeature(L.marker(x.latlng), "bulk", x.props);
  const pv = await api("/api/prv?name=" + encodeURIComponent(name)).catch(() => null);
  for (const x of (pv && pv.prv) || []) addFeature(L.marker(x.latlng), "prv", x.props);
  const tv = await api("/api/tw?name=" + encodeURIComponent(name)).catch(() => null);
  for (const x of (tv && tv.tw) || []) addFeature(L.marker(x.latlng), "tw", x.props);
  popUi();
}
async function loadNet(name) {
  status("DXF network खुल रहा है …");
  const r = await api("/api/net?name=" + encodeURIComponent(name));
  if (!r.ok) { remember(null); return status(r.log, "err"); }
  showNet(r, true);
  await loadDxfOhts(name);
  status(tr(`खोला: ${r.summary.manholes} junctions, ${r.summary.conduits} pipes (DXF)`, `Opened: ${r.summary.manholes} junctions, ${r.summary.conduits} pipes (DXF)`), "ok");
  // water: the saved network's zoning / design again - only when it is the network as it is now
  const w = await api("/api/water_last?name=" + encodeURIComponent(name));
  if (!w.ok || !w.network_saved) return;
  layoutReady({ marks: [], population: 0, conduits: netConds() });
  await restoreWater(name);
}

function showNet(r, fit) {
  drawn.clearLayers(); result.clearLayers(); zoneLayer.clearLayers(); designLayer.clearLayers(); select(null);
  $("zd").hidden = true; layoutData = null; tblReset(); $("files").innerHTML = "";
  setMode("dxf");
  $("pname").value = r.name;
  remember(r.name, "dxf");
  NET = { nodes: r.nodes, conds: {}, issues: r.issues, summary: r.summary, local: r.local, name: r.name, suggest: r.suggest || {},
    labelLevels: r.label_levels || 0 };
  for (const c of r.conduits) NET.conds[c.id] = c;
  if (r.local) [gmap, osm, sat, ...urlMaps.map(m => m.layer)].forEach(l => map.removeLayer(l));   // local coordinates: no web map under it
  netLayer.clearLayers(); nodeMk = {}; condLn = {};
  for (const id in NET.conds) drawCond(NET.conds[id]);
  for (const n in NET.nodes) drawNode(n);
  netSelect(null); renderIssues(); netSummary();
  if (fit && netLayer.getLayers().length) map.fitBounds(netLayer.getBounds(), { padding: [20, 20] });
  netReady();
}
// a DXF network on the map: zoning / design work on it as it is - saved or not (user decision 19-Oct-2026)
const netConds = () => Object.values(NET.conds).map(c => ({ label: c.label, pts: c.pts }));
function netReady() { layoutReady({ conduits: netConds(), marks: [], population: 0 }); }
// the network changed: the zoning / design shown were of the network before - cleared, to be run again
function netChanged() {
  const had = !!(wZoning || wDesign);
  layoutReady(Object.assign({ marks: [], population: 0 }, layoutData || {}, { conduits: netConds() }));
  wZoning = null; wDesign = null; zoneLayer.clearLayers(); $("wzbox").innerHTML = ""; $("wdbox").innerHTML = "";
  if (had) {
    const msg = tr("Network बदला - zoning / design फिर चलाएँ (सहेजना ज़रूरी नहीं)", "network changed - run zoning / design again (no need to save)");
    $("wstatus").className = "status"; $("wstatus").textContent = msg;
  }
}
function nodeStyle(n) {
  const v = NET.nodes[n];
  let fill = "#fff", color = "#37474f", r = 3.5;
  if (v.gl === null || v.gl === undefined) fill = "#e53935";
  else if (/user/.test(v.src)) fill = "#43a047";
  else if (/interpolated/.test(v.src)) fill = "#fb8c00";
  if (v.out) { color = "#0d47a1"; r = 7; fill = "#90caf9"; }
  return { radius: r, color, weight: v.out ? 3 : 1, fillColor: fill, fillOpacity: 1, renderer: netRenderer };
}
function drawNode(n) {
  if (nodeMk[n]) { netLayer.removeLayer(nodeMk[n]); delete nodeMk[n]; }
  const v = NET.nodes[n]; if (!v || !v.latlng) return;
  const m = L.circleMarker(v.latlng, nodeStyle(n)).on("click", ev => { L.DomEvent.stopPropagation(ev); netClick("node", n, ev.latlng); });
  m.bindTooltip(() => `${esc(n)}<br>GL ${v.gl ?? "-"}`, { direction: "top" });
  nodeMk[n] = m.addTo(netLayer);
}
function drawCond(c) {
  if (condLn[c.id]) { netLayer.removeLayer(condLn[c.id]); delete condLn[c.id]; }
  // a pipe without service connections (feeder / transmission main - user 30-Oct-2026): blue, dashed; a pipe the page
  // joined an isolated piece with by itself (user 30-Oct-2026): purple
  const ln = L.polyline(c.pts, c.nc ? { color: c.aj ? JOIN_COL : "#0277bd", weight: 3, opacity: .9, dashArray: "8 5", renderer: netRenderer }
                                    : { color: c.aj ? JOIN_COL : "#546e7a", weight: c.aj ? 3.5 : 2.5, opacity: .9, renderer: netRenderer })
    .on("click", ev => { L.DomEvent.stopPropagation(ev); netClick("cond", c.id, ev.latlng); });
  condLn[c.id] = ln.addTo(netLayer);
  ln.bringToBack();
}
// the prefix most of a network's names have (user request 30-Oct-2026: rename them to another at once)
// The letters before the first number (16-Nov-2026: of MH-3-441 it took "MH-3-", so only zone 3 was renamed and lost
// its zone); a name with letters after them (J-G12) keeps them in its prefix.
function mainPrefix(labels) {
  const c = {};
  for (const x of labels) {
    const m = /^([A-Za-z]+[-_ /]?)\d/.exec(String(x)) || /^(.*?)(\d+)$/.exec(String(x));
    if (m && m[1]) c[m[1]] = (c[m[1]] || 0) + 1;
  }
  return Object.keys(c).sort((a, b) => c[b] - c[a])[0] || "";
}
function prefixFill() {
  const n = mainPrefix(Object.keys(NET.nodes)), p = mainPrefix(Object.values(NET.conds).map(c => c.label));
  for (const [id, v] of [["rnpre", n], ["rppre", p]]) { const el = $(id); el.dataset.cur = v; if (document.activeElement !== el) el.value = v; }
}
$("rnbtn").onclick = () => {
  const ops = [], say = [];
  for (const [id, kind, labels, what] of [["rnpre", "node", Object.keys(NET.nodes), JN_], ["rppre", "pipe", Object.values(NET.conds).map(c => c.label), PP_]]) {
    const from = $(id).dataset.cur || "", to = $(id).value.trim();
    if (!from || !to || to === from) continue;
    const n = labels.filter(x => x.startsWith(from) && /\d/.test(x.charAt(from.length))).length;
    ops.push({ op: "rename_prefix", kind, from, to }); say.push(`${n} ${what}: ${from}… → ${to}…`);
  }
  if (!ops.length) { $("nstatus").className = "status"; $("nstatus").textContent = tr("कोई prefix नहीं बदला", "no prefix changed"); return; }
  if (!confirm(tr(`ये नाम बदलें?\n${say.join("\n")}\n\n(संख्या वही रहेगी; Undo से एक बार में वापस। Zoning / Design फिर चलाने होंगे।)`,
                  `Rename these?\n${say.join("\n")}\n\n(the numbers stay; Undo brings them back at once. Run Zoning / Design again.)`))) return;
  netEdit(ops, null);
};
// every junction / pipe named afresh by the app (user request 17-Nov-2026): <prefix>1, 2, 3 ... from each new tank of
// the last zoning, along its zone's pipes; the old names kept and shown on the cards. The tables' changes follow.
$("rnall").onclick = async () => {
  const np = $("rnpre").value.trim() || "J-", pp = $("rppre").value.trim() || "P-";
  if (!confirm(tr(`सब junctions को ${np}1, ${np}2 … और सब pipes को ${pp}1, ${pp}2 … नए नाम दें?\n\nनंबर आख़िरी Zoning की हर टंकी से शुरू होकर उसी क्षेत्र की pipes के साथ-साथ बढ़ेंगे (पहले OHT-1 का क्षेत्र, फिर OHT-2 …)। पुराने नाम junction / pipe के card में और save पर अलग CSV में रहेंगे। Undo से एक बार में वापस। उसके बाद Zoning / Design फिर चलाएँ।`,
                  `Give every junction a new name ${np}1, ${np}2 ... and every pipe ${pp}1, ${pp}2 ...?\n\nThe numbers start at each tank of the last zoning and run along its zone's pipes (OHT-1's zone first, then OHT-2 ...). The old names stay on the junction / pipe cards and in a CSV of their own when saved. Undo takes it back at once. Run Zoning / Design again after it.`))) return;
  $("nstatus").className = "status"; $("nstatus").textContent = tr("नए नाम दिए जा रहे हैं …", "naming ...");
  const r = await api("/api/net_renumber", { name: NET.name, node_prefix: np, pipe_prefix: pp, pipes: true });
  if (!r.ok) { $("nstatus").className = "status err"; $("nstatus").textContent = r.log; return; }
  if (typeof WEDITS === "object" && r.renamed) {                 // the tables' changes go with the names
    const re = (o, m) => { const out = {}; for (const [k, v] of Object.entries(o || {})) out[m[k] || k] = v; return out; };
    WEDITS.junctions = re(WEDITS.junctions, r.renamed.nodes); WEDITS.pipes = re(WEDITS.pipes, r.renamed.pipes);
  }
  applyNet(r, null);
  $("nstatus").className = "status ok";
  $("nstatus").textContent = tr(`नए नाम: ${Object.keys(r.renamed.nodes).length} junctions, ${Object.keys(r.renamed.pipes).length} pipes - ${r.tanks} टंकियों से। अब Zoning / Design फिर चलाएँ।`,
                                `New names: ${Object.keys(r.renamed.nodes).length} junctions, ${Object.keys(r.renamed.pipes).length} pipes - from ${r.tanks} tanks. Now run Zoning / Design again.`);
};
function netSummary() {
  prefixFill();
  const nl = NET.labelLevels || 0;
  $("nlabgl").hidden = !nl; $("nlabgl").textContent = `Drawing के GL लगाएँ (${nl})`;
  const s = NET.summary, open = NET.issues.filter(i => !i[6] && !i[7]).length;
  $("netsum").innerHTML = [["Junctions", s.manholes.toLocaleString("en-IN")], ["Pipes", `${s.conduits.toLocaleString("en-IN")} (${(s.length / 1000).toFixed(2)} km)`],
    // (no "Outfalls" row: a sewer's - a water network is fed from its OHTs, user 30-Oct-2026)
    ["हिस्से (parts)", s.parts], ["GL नहीं", s.no_gl], ["खुली गड़बड़ियाँ (CHECK)", open], ["बदलाव", s.edits]]
    .map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join("");
  $("nundo").disabled = !s.undo;
}

// ---- problems: groups by type, list of the open one, markers on the map
function renderIssues() {
  const showRev = $("showrev").checked;
  const by = {};
  for (const i of NET.issues) (by[i[1]] = by[i[1]] || []).push(i);
  const types = Object.keys(by).sort((a, b) => {
    const la = by[a][0][7], lb = by[b][0][7];
    return (la - lb) || ((TYPE_ORDER.indexOf(a) + 99) % 99 - (TYPE_ORDER.indexOf(b) + 99) % 99);
  });
  $("groups").innerHTML = types.map(t => {
    const all = by[t], open = all.filter(i => !i[6]).length, low = all[0][7];
    const nsug = t === "no drawing label (name generated)" ? all.filter(i => NET.suggest[i[2]]).length : 0;
    const sugTxt = n => { const g = NET.suggest[n]; return g ? ` → <b>${esc(g[0])}</b> <span class="hint">(${g[1]} m${g[2] !== null ? `, GL ${g[2]}` : ""})</span>` : ""; };
    const body = openGroup === t ? (nsug ? `<div class="row"><button id="sugall" class="primary">सब सुझाव लागू करें (${nsug})</button>
      <span class="hint">पास का बचा drawing label (और उसके पास का GL); हर एक बाद में "CHECK" में जाँचें</span></div>` : "") +
      `<div class="ilist">${all.filter(i => showRev || !i[6]).slice(0, 400).map(i =>
      `<div data-key="${esc(i[0])}" class="${i[6] ? "rv" : ""}">${esc(i[2])}${sugTxt(i[2])}${i[5] ? ` - <span class="hint">${esc(i[5])}</span>` : ""}</div>`).join("") ||
      '<div class="hint">सब जाँच लिए गए</div>'}${all.length > 400 ? '<div class="hint">पहले 400 दिखाए</div>' : ""}</div>` : "";
    return `<div class="grp${openGroup === t ? " open" : ""}${low ? " low" : ""}${!open ? " done" : ""}" data-t="${esc(t)}"><span>${esc(TYPE_HI[t] || t)}</span><span class="n">${open}/${all.length}</span></div>${body}`;
  }).join("") || '<div class="hint">कोई गड़बड़ी नहीं</div>';
  document.querySelectorAll("#groups .grp").forEach(g => g.onclick = () => { openGroup = openGroup === g.dataset.t ? null : g.dataset.t; renderIssues(); });
  document.querySelectorAll("#groups .ilist div[data-key]").forEach(d => d.onclick = () => gotoIssue(NET.issues.find(i => i[0] === d.dataset.key)));
  if ($("sugall")) $("sugall").onclick = () => {
    const n = Object.keys(NET.suggest).length;
    if (confirm(`${n} junctions को पास का बचा drawing label (और जहाँ GL नहीं, वहाँ उसके पास का GL) लगाएँ? Undo से वापस ले सकते हैं; हर एक "Label सुझाव से लगाया - CHECK" में जाँचने को रहेगा।`))
      netEdit([{ op: "apply_suggestions" }], null);
  };
  issueLayer.clearLayers();
  if (openGroup && by[openGroup])
    for (const i of by[openGroup]) if (i[3] !== null && (showRev || !i[6]))
      L.circleMarker([i[3], i[4]], { radius: 10, color: i[6] ? "#9e9e9e" : i[7] ? "#ff9800" : "#d50000", weight: 2, fill: false, renderer: netRenderer, interactive: false }).addTo(issueLayer);
  if (openGroup === "no drawing label (name generated)")
    for (const [n, g] of Object.entries(NET.suggest)) if (NET.nodes[n])
      L.polyline([NET.nodes[n].latlng, [g[3], g[4]]], { color: "#ef6c00", weight: 2, dashArray: "4 4", renderer: netRenderer, interactive: false }).addTo(issueLayer);
  // manholes on top of each other with no sewer between them (user request 20-Oct-2026): always a red cross - such a
  // place can split the network in two without showing on the map (a loop cut head left at its manhole)
  const nCut = (by[OVERLAP] || []).filter(i => /loop cut head/.test(i[5])).length;
  $("nrejoin").hidden = !nCut;
  $("nrejoin").textContent = tr(`कटे loops फिर जोड़ें (${nCut})`, `Join cut loops back (${nCut})`);
  warnLayer.clearLayers();
  for (const i of by[OVERLAP] || []) if (i[3] !== null && (showRev || !i[6]))
    L.marker([i[3], i[4]], { icon: L.divIcon({ className: "ovx" + (i[6] ? " rev" : ""), html: "✕", iconSize: [22, 22] }), zIndexOffset: 1000 })
      .bindTooltip(`<b>${esc(i[2])}</b><br>${esc(TYPE_HI[OVERLAP])}<br>${esc(i[5])}`).on("click", () => { if (curView !== "layout") setView("layout"); gotoIssue(i); }).addTo(warnLayer);
}
$("showrev").onchange = renderIssues;
function gotoIssue(i) {
  if (!i) return;
  if (i[3] !== null) map.setView([i[3], i[4]], Math.max(map.getZoom(), 19));
  const item = i[1] === OVERLAP ? i[2].split(" - ")[0] : i[2];
  if (NET.nodes[item]) netSelect({ kind: "node", id: item });
  else { const c = Object.values(NET.conds).find(c => c.label === item); if (c) netSelect({ kind: "cond", id: c.id }); }
}

// ---- selection and the panel of the selected manhole / sewer
function netSelect(sel) {
  netSel = sel; selLayer.clearLayers();
  const box = $("props");
  if (sel && sel.kind === "many") {
    for (const id of sel.conds.concat(sel.also)) { const c = NET.conds[id]; if (c) L.polyline(c.pts, { color: "#ffd600", weight: 6, opacity: .8, renderer: netRenderer, interactive: false }).addTo(selLayer); }
    for (const n of sel.nodes) { const v = NET.nodes[n]; if (v) L.circleMarker(v.latlng, { radius: 7, color: "#ffd600", weight: 3, fill: false, renderer: netRenderer, interactive: false }).addTo(selLayer); }
    box.className = "";
    box.innerHTML = `<b>${tr("घेरे में चुने गए", "Selected by the loop")}</b>
      <div class="hint">${sel.nodes.length} ${JN_}, ${sel.conds.length} ${PP_}${sel.also.length ? tr(` + ${sel.also.length} ${PP_} जो घेरे के बाहर जाते हैं (उनका ${JN_} हटने से वे भी हटेंगे)`,
        ` + ${sel.also.length} ${PP_}(s) leaving the loop (they go with their ${JN_})`) : ""}</div>
      <div class="row"><button class="danger" id="m_del">${tr("सब हटाएँ (Delete)", "Delete all (Delete)")}</button></div>
      <div class="hint">${tr("Undo (Ctrl+Z) से सब एक बार में वापस आते हैं।", "Undo (Ctrl+Z) brings them all back at once.")}</div>
      <div class="row" title="${esc(NOCONN_TIP())}"><span class="hint" style="min-width:0">${tr(`घेरे के ${sel.conds.length} ${PP_}:`, `the ${sel.conds.length} ${PP_}(s) in the loop:`)}</span>
        <button id="m_nc1">${tr("बिना कनेक्शन", "no connections")}</button><button id="m_nc0">${tr("कनेक्शन वाले", "with connections")}</button></div>`;
    $("m_del").onclick = () => deleteMany(sel);
    $("m_nc1").onclick = () => setNoConn(sel.conds, true, sel);
    $("m_nc0").onclick = () => setNoConn(sel.conds, false, sel);
    return;
  }
  if (!sel) { box.className = "empty"; box.innerHTML = "नक्शे पर किसी junction / pipe पर click करें।"; return; }
  box.className = "";
  if (sel.kind === "node") {
    const n = sel.id, v = NET.nodes[n]; if (!v) return netSelect(null);
    L.circleMarker(v.latlng, { radius: 11, color: "#ffd600", weight: 4, fill: false, renderer: netRenderer, interactive: false }).addTo(selLayer);
    const mine = NET.issues.filter(i => i[2] === n || i[2].split(" - ").includes(n));
    const deg = Object.values(NET.conds).filter(c => c.from === n || c.to === n);
    box.innerHTML = `<b>Junction</b> <span class="hint">${deg.length} pipe: ${deg.map(c => esc(c.label)).join(", ")}</span>
      <div class="row"><label>नाम</label><input type="text" id="n_label" value="${esc(n)}"></div>
      <div class="row"><label>GL (m)</label><input type="number" id="n_gl" step="0.01" value="${v.gl ?? ""}"></div>
      <div class="hint">GL का स्रोत: ${esc(v.src || "-")}</div>
      ${v.old ? `<div class="hint">${tr("पुराना नाम (drawing)", "Old name (drawing)")}: <b>${esc(v.old)}</b></div>` : ""}
      ${NET.suggest[n] ? `<div class="row"><span>सुझाव: <b>${esc(NET.suggest[n][0])}</b> <span class="hint">(${NET.suggest[n][1]} m दूर लिखा${NET.suggest[n][2] !== null ? `, GL ${NET.suggest[n][2]}` : ""})</span></span>
        <button id="n_sug" class="primary">लागू करें</button></div>` : ""}
      ${mine.map(i => `<div class="row"><label style="min-width:0"><input type="checkbox" data-rk="${esc(i[0])}"${i[6] ? " checked" : ""}> जाँच लिया: ${esc(TYPE_HI[i[1]] || i[1])}${i[5] ? ` <span class="hint">(${esc(i[5])})</span>` : ""}</label></div>`).join("")}
      <div class="hint" style="margin-top:6px">पास के drawing texts (click = उपयोग करें):</div><div id="n_txt" class="hint">…</div>
      <div class="row"><button class="danger" id="n_del">Junction हटाएँ (उसके pipes सहित)</button></div>`;
    const setLabel = () => { const to = $("n_label").value.trim(); if (to && to !== n) netEdit([{ op: "rename", mh: n, to }], to); };
    $("n_label").onkeydown = e => { if (e.key === "Enter") setLabel(); };
    $("n_label").onchange = setLabel;
    const setGl = () => { const g = $("n_gl").value; if (String(g) !== String(v.gl ?? "")) netEdit([{ op: "set_gl", mh: n, gl: g }], n); };
    $("n_gl").onkeydown = e => { if (e.key === "Enter") setGl(); };
    $("n_gl").onchange = setGl;
    if ($("n_sug")) $("n_sug").onclick = () => netEdit([{ op: "apply_suggestions", mh: n }], NET.suggest[n][0]);
    document.querySelectorAll("#props input[data-rk]").forEach(c => c.onchange = () => netEdit([{ op: "review", key: c.dataset.rk, ok: c.checked }], n));
    $("n_del").onclick = () => { if (confirm(tr(`${n} और उसके ${deg.length} pipe हटाएँ?`, `Delete ${n} and its ${deg.length} pipe(s)?`))) netEdit([{ op: "delete_mh", mh: n }], null); };
    nearTexts(n, v.latlng);
  } else {
    const c = NET.conds[sel.id]; if (!c) return netSelect(null);
    L.polyline(c.pts, { color: "#ffd600", weight: 7, opacity: .8, renderer: netRenderer, interactive: false }).addTo(selLayer);
    box.innerHTML = `<b>Pipe ${esc(c.label)}</b> <span class="hint">${esc(c.from)} → ${esc(c.to)}, ${c.len.toFixed(2)} m</span>
      ${c.old ? `<div class="hint">${tr("पुराना नाम", "Old name")}: <b>${esc(c.old)}</b></div>` : ""}
      <div class="row"><button data-go="${esc(c.from)}">${esc(c.from)}</button><button data-go="${esc(c.to)}">${esc(c.to)}</button>
      <button class="danger" id="c_del">Pipe हटाएँ</button></div>
      ${c.aj ? `<div class="hint" style="color:${JOIN_COL}">🔗 ${tr("अलग टुकड़ा जोड़ने के लिए अपने-आप बना सीधा pipe - असली सड़क का रास्ता देखकर ठीक करें (हटाकर हाथ से खींचें)",
        "a straight pipe made by itself to join an isolated piece - check it against the real road (delete it and draw by hand)")}</div>` : ""}
      <div class="row" title="${esc(NOCONN_TIP())}"><label style="min-width:0"><input type="checkbox" id="c_nc"${c.nc ? " checked" : ""}> ${tr("बिना कनेक्शन (feeder / transmission main)", "no service connections (feeder / transmission main)")}</label></div>
      <div class="hint">बीच में junction चाहिए: "Pipe तोड़ें" चुनकर pipe पर उस जगह click करें।</div>`;
    $("c_nc").onchange = () => setNoConn([c.id], $("c_nc").checked, sel);
    document.querySelectorAll("#props button[data-go]").forEach(b => b.onclick = () => { const v = NET.nodes[b.dataset.go]; if (v) { map.panTo(v.latlng); netSelect({ kind: "node", id: b.dataset.go }); } });
    $("c_del").onclick = () => netEdit([{ op: "delete_conduit", id: c.id }], null);
  }
}
function netStats() {
  if (!NET._stats) {
    const g = Object.values(NET.nodes).map(v => v.gl).filter(x => x !== null && x !== undefined).sort((a, b) => a - b);
    const pc = {};
    for (const n of Object.keys(NET.nodes)) { const m = /^([A-Za-z]{1,8})\s*[-_ /]/.exec(n); if (m) pc[m[1].toUpperCase()] = (pc[m[1].toUpperCase()] || 0) + 1; }
    const tot = Object.values(pc).reduce((a, b) => a + b, 0);
    NET._stats = { medGl: g.length ? g[Math.floor(g.length / 2)] : null,
      prefixes: new Set(Object.entries(pc).filter(([, c]) => c >= 0.05 * tot).map(([p]) => p)) };
  }
  return NET._stats;
}
async function nearTexts(n, ll) {
  const d = 0.00025;          // ~25 m
  const r = await api(`/api/net_texts?name=${encodeURIComponent(NET.name)}&s=${ll[0] - d}&w=${ll[1] - d}&n=${ll[0] + d}&e=${ll[1] + d}`);
  const box = $("n_txt"); if (!box || !netSel || netSel.id !== n) return;
  if (!r.ok || !r.texts.length) { box.textContent = "कोई नहीं"; return; }
  const dist = t => map.distance(ll, [t[0], t[1]]);
  const items = r.texts.map(t => ({ t, d: dist(t) })).sort((a, b) => a.d - b.d).slice(0, 14);
  const { medGl, prefixes } = netStats();
  box.innerHTML = items.map(({ t, d }) => {
    // a ground level: a decimal number near the network's usual GL (not a pipe length / depth); a name: the
    // manholes' own prefix (MH-...), not a pipe label (P-...)
    const lv0 = /^\s*(?:GL|RL|G\.L\.?)?\s*[:=\-]?\s*(\d{1,4}\.\d{1,3})\s*m?\s*$/i.exec(t[2]);
    const lv = lv0 && medGl !== null && Math.abs(parseFloat(lv0[1]) - medGl) <= 20 ? lv0 : null;
    const idm = /^\s*([A-Za-z]{1,8})\s*[-_ /]\s*\d+[A-Za-z]?\s*$/.exec(t[2]);
    const id = idm && prefixes.has(idm[1].toUpperCase());
    const act = lv ? `data-gl="${lv[1]}"` : id ? `data-lb="${esc(t[2].trim())}"` : "";
    return `<button class="txtbtn" ${act} title="${esc(t[3])}, ${d.toFixed(1)} m"${act ? "" : " disabled"}>${esc(t[2])} <span class="hint">${d.toFixed(0)} m</span></button>`;
  }).join("");
  box.querySelectorAll("button[data-gl]").forEach(b => b.onclick = () => netEdit([{ op: "set_gl", mh: n, gl: b.dataset.gl }], n));
  box.querySelectorAll("button[data-lb]").forEach(b => b.onclick = () => netEdit([{ op: "rename", mh: n, to: b.dataset.lb }], b.dataset.lb));
}

// ---- find on the map (user request 30-Oct-2026): a junction / pipe / OHT / OZ / DMA or a drawn feature by
// its name, in every view; Ctrl+F with the mouse over the map opens it (over the panel: the browser's own find)
const findLayer = L.layerGroup().addTo(map);
function findExtra(add) {                        // the water module's own: zones, DMAs, a design's junctions
  for (const z of (wZoning && wZoning.zones) || []) add(z.name, "OZ / OHT", z.latlng);
  for (const d of (wZoning && wZoning.dmas) || []) if (d.label) add(d.name, "DMA", d.label);
  for (const r of [wZoning, wDesign]) for (const c of (r && r.cut_parts) || []) add(c.label, PP_, null, c.pts);
  for (const n of (wDesign && wDesign.nodes) || []) if (n.latlng) add(n.label, JN_, n.latlng);
}
function findItems() {
  const out = [], seen = new Set();
  const add = (name, kind, ll, pts) => {
    if (!name || (!ll && !(pts && pts.length))) return;
    const k = kind + "|" + name; if (seen.has(k)) return; seen.add(k);
    out.push({ name: String(name), kind, ll, pts });
  };
  if (mode === "dxf" && NET) {
    for (const [n, v] of Object.entries(NET.nodes)) add(n, JN_, v.latlng);
    for (const c of Object.values(NET.conds)) add(c.label, PP_, null, c.pts);
  } else if (layoutData) {
    for (const m of layoutData.manholes || []) add(m.label, JN_, m.latlng);
    for (const c of layoutData.conduits || []) add(c.label, PP_, null, c.pts);
  }
  findExtra(add);
  drawn.eachLayer(l => {
    const nm = l.props && l.props.name, kn = KIND[l.kind] ? KIND[l.kind].name : l.kind;
    if (!nm) return;
    if (l.getLatLng) { const q = l.getLatLng(); add(nm, kn, [q.lat, q.lng]); }
    else { const a = l.getLatLngs(); add(nm, kn, null, (Array.isArray(a[0]) ? a[0] : a).map(q => [q.lat, q.lng])); }
  });
  return out;
}
function findShow(it) {
  findLayer.clearLayers();
  let at = it.ll;
  if (it.pts && it.pts.length > 1) {
    const ln = L.polyline(it.pts, { color: "#ffd600", weight: 10, opacity: .8, interactive: false }).addTo(findLayer);
    map.fitBounds(ln.getBounds(), { maxZoom: 19, padding: [80, 80] });
    at = at || it.pts[Math.floor(it.pts.length / 2)];
  } else {
    at = at || it.pts[0];
    map.setView(at, Math.max(map.getZoom(), 19));
    L.circleMarker(at, { radius: 16, color: "#ffd600", weight: 5, fill: false, interactive: false }).addTo(findLayer);
  }
  L.popup({ autoPan: false, offset: [0, -8] }).setLatLng(at).setContent(`<b>${esc(it.name)}</b> <span class="hint">${esc(it.kind)}</span>`).openOn(map);
}
L.Control.Find = L.Control.extend({ options: { position: "topleft" }, onAdd() {
  const d = L.DomUtil.create("div", "leaflet-bar findbox");
  d.innerHTML = `<input type="text" id="findq" autocomplete="off" placeholder="${tr("नक्शे पर खोजें: नाम…", "Find on the map: name…")}"
    title="${tr("Junction, pipe, OHT, zone या खींची चीज़ का नाम (या उसका हिस्सा) - Enter / click से वहाँ पहुँचें; नक्शे पर mouse हो तो Ctrl+F", "Name (or part) of a junction, pipe, OHT, zone or drawn feature - Enter / click goes there; Ctrl+F with the mouse over the map")}"><div id="findres"></div>`;
  L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
  return d;
} });
new L.Control.Find().addTo(map);
{
  let hits = [], cur = 0, overMap = false;
  const box = $("findres"), q = $("findq");
  const draw = () => {
    box.innerHTML = hits.map((h, i) => `<div data-i="${i}" class="${i === cur ? "on" : ""}"><b>${esc(h.name)}</b> <span class="hint">${esc(h.kind)}</span></div>`).join("")
      + (q.value.trim() && !hits.length ? `<div class="hint">${tr("कुछ नहीं मिला", "nothing found")}</div>` : "");
  };
  q.addEventListener("input", () => {
    const t = q.value.trim().toLowerCase(); cur = 0;
    if (!t) { hits = []; return draw(); }
    const rank = h => { const n = h.name.toLowerCase(); return n === t ? 0 : n.startsWith(t) ? 1 : n.includes(t) ? 2 : 9; };
    hits = findItems().map(h => [rank(h), h]).filter(x => x[0] < 9)
      .sort((a, b) => a[0] - b[0] || a[1].name.length - b[1].name.length || a[1].name.localeCompare(b[1].name)).slice(0, 15).map(x => x[1]);
    draw();
  });
  const go = i => { if (!hits[i]) return; findShow(hits[i]); box.innerHTML = ""; };
  q.addEventListener("keydown", e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); cur = (cur + (e.key === "ArrowDown" ? 1 : hits.length - 1)) % Math.max(hits.length, 1); draw(); }
    else if (e.key === "Enter") { e.preventDefault(); go(cur); }
    else if (e.key === "Escape") { q.value = ""; hits = []; draw(); findLayer.clearLayers(); q.blur(); }
  });
  box.addEventListener("click", e => { const r = e.target.closest("[data-i]"); if (r) go(+r.dataset.i); });
  const c = map.getContainer();
  c.addEventListener("mouseenter", () => overMap = true);
  c.addEventListener("mouseleave", () => overMap = false);
  document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && (e.key || "").toLowerCase() === "f" && overMap) { e.preventDefault(); q.focus(); q.select(); }
  }, true);
}

// ---- tools
const JN_ = "junction", PP_ = "pipe";
const HINT = { lasso: "घेरा खींचें: हर click एक कोना, Enter / right-click से पूरा - अंदर का सब एक साथ चुना जाएगा (Esc = रद्द)।",
  select: "किसी junction / pipe पर click करें। Delete = चुनी वस्तु हटाएँ।",
  connect: "पहले junction पर click, फिर दूसरे पर - उनके बीच सीधा pipe बनेगा।",
  merge: "पहले वह junction जो रहेगा, फिर वह जो उसमें मिलेगा (gap वाले दो सिरे)।",
  split: "Pipe पर उस जगह click करें जहाँ नया junction चाहिए।",
  move: "पहले junction पर click, फिर नक्शे पर नई जगह।",
  place: "पूरा network: पहले drawing का कोई junction / बिंदु, फिर नक्शे पर उसकी असली जगह click करें - पूरा network उतना खिसकेगा (लंबाई / स्तर वही)। दूर हो तो नीचे lat, lng लिखें।" };
// select by a loop (user 30-Oct-2026): the junctions inside it and the pipes with both ends inside
function inRing(ll, ring) {
  let c = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i], b = ring[j];
    if ((a.lat > ll[0]) !== (b.lat > ll[0]) && ll[1] < a.lng + (ll[0] - a.lat) * (b.lng - a.lng) / (b.lat - a.lat)) c = !c;
  }
  return c;
}
function lassoSelect(ring) {
  const nodes = Object.entries(NET.nodes).filter(([, v]) => v.latlng && inRing(v.latlng, ring)).map(([n]) => n);
  const inside = new Set(nodes);
  const conds = Object.values(NET.conds).filter(c => inside.has(c.from) && inside.has(c.to)).map(c => c.id);
  const also = Object.values(NET.conds).filter(c => inside.has(c.from) !== inside.has(c.to)).map(c => c.id);
  netSelect(nodes.length || conds.length ? { kind: "many", nodes, conds, also } : null);
  if (!nodes.length) $("nhint").textContent = tr(`घेरे में कोई ${JN_} नहीं`, `no ${JN_} inside the loop`);
}
// pipes without service connections (user request 30-Oct-2026): no population is put on them when it is spread by
// pipe length (the total or the wards); the water still flows through them. One undo step; the selection stays.
const NOCONN_TIP = () => tr("Feeder / transmission main, खाली ज़मीन या highway के साथ का pipe: इस पर कोई घर नहीं जुड़ता, इसलिए आबादी (कुल या वार्ड की) इस पर नहीं बाँटी जाती। पानी इससे होकर बहता है और design में इसका size बनता है। नक्शे पर नीली टूटी रेखा।",
  "A feeder / transmission main, a pipe across open land or along a highway: no house is joined to it, so no population (total or by ward) is put on it. The water flows through it and the design sizes it. Blue dashed on the map.");
async function setNoConn(ids, on, sel) {
  if (!ids.length) return;
  await netEdit([{ op: "set_noconn", ids, value: on }], null);
  if (sel && (sel.kind === "many" || NET.conds[sel.id])) netSelect(sel);
  $("nstatus").className = "status ok";
  $("nstatus").textContent = tr(`${ids.length} ${PP_}: ${on ? "बिना कनेक्शन" : "कनेक्शन वाले"} - Zoning दोबारा चलाएँ`,
                                `${ids.length} ${PP_}(s): ${on ? "no connections" : "with connections"} - run the zoning again`);
}
function deleteMany(sel) {
  const n = sel.nodes.length, m = sel.conds.length + sel.also.length;
  if (!confirm(tr(`${n} ${JN_} और ${m} ${PP_} हटाएँ? (Undo से एक बार में वापस)`, `Delete ${n} ${JN_}(s) and ${m} ${PP_}(s)? (Undo brings them all back)`))) return;
  // the pipes first, then the junctions (each with the pipes still joined to it): one undo step
  netEdit(sel.conds.map(id => ({ op: "delete_conduit", id })).concat(sel.nodes.map(mh => ({ op: "delete_mh", mh }))), null);
}
function setTool(t) {
  if (t === "lasso") {
    if (mode === "dxf" && !map.hasLayer(netLayer)) setView("layout");
    tool = "lasso"; pick = null; netSelect(null);
    document.querySelectorAll("#ntools button").forEach(b => b.classList.toggle("on", b.dataset.t === t));
    document.body.classList.add("netpick");
    $("nhint").textContent = HINT.lasso;
    return startDraw("lasso");
  }
  if (activeKind === "lasso") stopDraw();
  // the tools work on the network's manholes: they are on the map only in the "Layout" view (not Zones / Design)
  if (mode === "dxf" && !map.hasLayer(netLayer)) setView("layout");
  tool = t; pick = null; selLayer.clearLayers(); placeFrom = null;
  document.querySelectorAll("#ntools button").forEach(b => b.classList.toggle("on", b.dataset.t === t));
  // with a tool other than "select" a click on a red cross goes through to the manhole / map under it
  document.body.classList.toggle("netpick", t !== "select");
  $("placerow").hidden = t !== "place";
  if (t === "place") hasBase() || gmap.addTo(map);       // a local drawing: the map to find its place on
  $("nhint").textContent = HINT[t];
  uiToolHint("net", t === "select" ? null : toolName(`#ntools button[data-t="${t}"]`), $("nhint").textContent, false);
}
document.querySelectorAll("#ntools button").forEach(b => b.onclick = () => setTool(b.dataset.t));
const SAME_SPOT_M = 1.0;                 // as repair.OVERLAP_M: junctions this close are "on the same spot"
function netClick(kind, id, latlng) {
  if (tool === "lasso") return;                          // drawing the loop: the clicks are its corners
  if (tool === "select") return netSelect({ kind, id });
  if (tool === "place") return placeClick(kind === "node" && NET.nodes[id] ? L.latLng(NET.nodes[id].latlng) : latlng, kind === "node" ? id : null);
  if (tool === "split") { if (kind === "cond") netEdit([{ op: "split", id, latlng: [latlng.lat, latlng.lng] }], null, true); return; }
  if (kind !== "node") return;
  if (!pick) { pick = id; netSelect({ kind: "node", id }); $("nhint").textContent = tr(`${id} चुना - अब ${tool === "move" ? "नक्शे पर नई जगह" : "दूसरा junction"} पर click करें (Esc = रद्द)`,
    `${id} selected - now click ${tool === "move" ? "its new place on the map" : "the second junction"} (Esc = cancel)`); return; }
  if (pick === id) {
    // two manholes on (nearly) the same spot: a click there gives the top one again - take the other one there
    const p = L.latLng(NET.nodes[pick].latlng);
    const other = Object.entries(NET.nodes).filter(([n, v]) => n !== pick && v.latlng && p.distanceTo(L.latLng(v.latlng)) <= SAME_SPOT_M)
      .sort((a, b) => p.distanceTo(L.latLng(a[1].latlng)) - p.distanceTo(L.latLng(b[1].latlng)))[0];
    if (!other) return;
    id = other[0];
  }
  if (tool === "connect") netEdit([{ op: "connect", a: pick, b: id }], id);
  if (tool === "merge") {
    // a manhole and its loop cut head <manhole>-C<n>: the manhole keeps its name, whichever was clicked first
    let keep = pick, drop = id;
    if (keep.startsWith(drop + "-C") && /^\d+$/.test(keep.slice(drop.length + 2))) [keep, drop] = [drop, keep];
    if (confirm(tr(`${drop} को ${keep} में मिलाएँ? (${drop} हटेगा, उसके pipes ${keep} से जुड़ेंगे)`,
                   `Merge ${drop} into ${keep}? (${drop} is removed, its pipes are joined to ${keep})`))) netEdit([{ op: "merge", keep, drop }], keep);
  }
  pick = null; $("nhint").textContent = HINT[tool];
}
map.on("click", ev => {
  if (mode !== "dxf") return;
  if (tool === "place") return placeClick(ev.latlng, null);
  if (tool === "move" && pick) { netEdit([{ op: "move", mh: pick, latlng: [ev.latlng.lat, ev.latlng.lng] }], pick); pick = null; $("nhint").textContent = HINT.move; return; }
  if (tool === "select") netSelect(null);
});
document.addEventListener("keydown", e => {
  if (mode !== "dxf") return;
  const typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName);
  if (e.key === "Delete" && netSel && !typing) {
    if (netSel.kind === "many") deleteMany(netSel);
    else if (netSel.kind === "cond") netEdit([{ op: "delete_conduit", id: netSel.id }], null);
    else if (confirm(tr(`${netSel.id} और उसके pipes हटाएँ?`, `Delete ${netSel.id} and its pipes?`))) netEdit([{ op: "delete_mh", mh: netSel.id }], null);
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "z" && !typing) { e.preventDefault(); $("nundo").onclick(); }
});

// ---- server round trips
function applyNet(r, keepSel, selectNew) {
  if (r.conduits) { showNet(r, false); }
  else {
    for (const [n, v] of Object.entries(r.nodes || {})) { if (v) NET.nodes[n] = v; else delete NET.nodes[n]; drawNode(n); }
    for (const [id, c] of Object.entries(r.conduits_upd || {})) {
      if (c) { NET.conds[id] = c; drawCond(c); } else { delete NET.conds[id]; if (condLn[id]) { netLayer.removeLayer(condLn[id]); delete condLn[id]; } }
    }
    NET.issues = r.issues; NET.summary = r.summary; NET.suggest = r.suggest || {}; NET.labelLevels = r.label_levels || 0;
    if (selectNew) { const nn = Object.keys(r.nodes || {}).find(n => r.nodes[n] && !NET._before.has(n)); if (nn) keepSel = nn; }
    renderIssues(); netSummary();
  }
  if (keepSel && NET.nodes[keepSel]) netSelect({ kind: "node", id: keepSel }); else netSelect(null);
  netChanged();                                                // zoning / design: of the network as it is now
}
async function netEdit(ops, keepSel, selectNew) {
  NET._before = new Set(Object.keys(NET.nodes));
  const r = await api("/api/net_edit", { name: NET.name, ops });
  if (!r.ok) { $("nstatus").className = "status err"; $("nstatus").textContent = r.log; return; }
  $("nstatus").className = "status"; $("nstatus").textContent = "";
  applyNet(r, keepSel, selectNew);
}
$("nundo").onclick = async () => {
  const r = await api("/api/net_undo", { name: NET.name });
  if (!r.ok) { $("nstatus").className = "status err"; $("nstatus").textContent = r.log; return; }
  applyNet(r, netSel && netSel.kind === "node" ? netSel.id : null);
  $("nstatus").className = "status ok"; $("nstatus").textContent = "पिछला बदलाव वापस लिया।";
};
$("nrepair").onclick = async () => {
  // a water main network keeps its loops
  if (!confirm(tr("अपने-आप सुधार: 1 m तक के gaps जोड़ना, T-joint पर line तोड़ना, खाली GL pipe के साथ interpolate करना, और एक ही जगह पड़े junctions (लाल ✕) को एक में मिलाना (पेयजल में loops नहीं काटे जाते)। Undo से वापस ले सकते हैं। करें?",
         "Auto repair: join gaps up to 1 m, cut lines at T-joints, interpolate missing GL along the pipes, and merge the junctions on the same spot (red ✕) into one (a water network keeps its loops). Undo takes it back. Go on?"))) return;
  $("nstatus").className = "status"; $("nstatus").textContent = "सुधार हो रहा है …";
  const r = await api("/api/net_repair", { name: NET.name, loops: false });
  if (!r.ok) { $("nstatus").className = "status err"; $("nstatus").textContent = r.log; return; }
  applyNet(r, null);
  $("nstatus").className = "status ok"; $("nstatus").textContent = r.log;
};
// junctions only where pipes join (user request 14-Nov-2026): the junctions between two pipes taken out
$("njoints").onclick = async () => {
  if (!confirm(tr("जिन junctions पर केवल दो pipes मिलती हैं वे हट जाएँगे और उनकी दोनों pipes एक हो जाएँगी (रास्ता और लंबाई वही)। उन junctions के GL फिर design में नहीं देखे जाएँगे। सिरे, pipe joints और OHT / tube well / bulk consumer वाले junctions रहेंगे। Undo से वापस ले सकते हैं। आगे बढ़ें?",
                  "The junctions where only two pipes meet will be removed and their two pipes made one (same route and length). The ground levels of those junctions are then not looked at in the design. Ends, pipe joints and the junctions of an OHT / tube well / bulk consumer stay. Undo takes it back. Go on?"))) return;
  $("nstatus").className = "status"; $("nstatus").textContent = tr("Junctions हटा रहे हैं …", "Removing junctions …");
  const r = await api("/api/net_joints", { name: NET.name });
  if (!r.ok) { $("nstatus").className = "status err"; $("nstatus").textContent = r.log; return; }
  applyNet(r, null);
  $("nstatus").className = "status ok";
  $("nstatus").textContent = r.removed
    ? tr(`${r.removed} junctions हटे (दो pipes के बीच वाले) - अब ${r.summary.manholes} junctions, ${r.summary.conduits} pipes। Zoning और Design दोबारा चलाएँ।`,
         `${r.removed} junctions removed (those between two pipes) - now ${r.summary.manholes} junctions, ${r.summary.conduits} pipes. Run Zoning and Design again.`)
    : tr("दो pipes के बीच वाला कोई junction नहीं मिला।", "No junction between two pipes found.");
};
// the loop cut heads (<junction>-C<n>, from an earlier auto repair) merged back - a water network's loops are wanted
$("nrejoin").onclick = () => {
  const n = NET.issues.filter(i => i[1] === OVERLAP && /loop cut head/.test(i[5])).length;
  if (confirm(tr(`${n} कटे loops फिर जोड़ें? हर <junction>-C1 / -C2 … अपने junction में मिल जाएगा (Undo से वापस ले सकते हैं)`,
                 `Join ${n} cut loops back? Every <junction>-C1 / -C2 … is merged into its junction (Undo takes it back)`)))
    netEdit([{ op: "rejoin_cuts" }], null);
};
$("nrepair").title = tr("1 m तक के gaps जोड़ना, T-joint पर तोड़ना, खाली GL pipe के साथ भरना, एक ही जगह पड़े junctions (लाल ✕) मिलाना - पेयजल में loops नहीं काटे जाते",
                                                 "Join gaps up to 1 m, cut at T-joints, fill missing GL along the pipes, merge the junctions on the same spot (red ✕) - a water network keeps its loops");
$("nlabgl").onclick = () => {
  if (confirm(`${NET.labelLevels} junctions का GL अभी खाली है या अनुमान से भरा है, पर drawing में उनके नाम के पास GL लिखा है। वह GL लगाएँ? (Undo से वापस ले सकते हैं)`))
    netEdit([{ op: "gl_from_labels" }], netSel && netSel.kind === "node" ? netSel.id : null);
};
// ---- the whole network to its place on the map (a drawing without / with wrong geo-reference)
let placeFrom = null;
function placeClick(ll, id) {
  if (!placeFrom) {
    placeFrom = ll; selLayer.clearLayers();
    L.circleMarker(ll, { radius: 9, color: "#d500f9", weight: 3, fill: false, interactive: false }).addTo(selLayer);
    $("nhint").textContent = tr(`${id || "बिंदु"} चुना - अब नक्शे पर उसकी असली जगह click करें (या नीचे lat, lng; Esc = रद्द)`,
      `${id || "Point"} picked - now click its real place on the map (or type lat, lng below; Esc = cancel)`);
    return;
  }
  doPlace(placeFrom, ll);
}
async function doPlace(frm, to) {
  const ohts = []; drawn.eachLayer(l => { if (l.kind === "oht") ohts.push(l); });
  const r = await withLoading(tr("Network खिसका रहे हैं …", "Moving the network …"), () =>
    api("/api/net_place", { name: NET.name, from: [frm.lat, frm.lng], to: [to.lat, to.lng], points: ohts.map(l => { const p = l.getLatLng(); return [p.lat, p.lng]; }) }));
  placeFrom = null; selLayer.clearLayers(); $("nhint").textContent = HINT.place;
  if (!r.ok) return status(r.log, "err");
  showNet(r, false); setTool("place");
  ohts.forEach((l, i) => { l.setLatLng(r.points[i]); drawn.addLayer(l); });   // the OHTs placed on it go with it
  if (ohts.length) changed();
  hasBase() || gmap.addTo(map);
  map.panTo(to);
  status(tr("Network खिसकाया - पूरा मिलाने को फिर एक बिंदु चुनकर उसकी जगह click करें; ↶ Undo से वापस। Zoning / design के लिए फिर सहेजें।",
    "Network moved - pick a point again and click its place to fine-tune; ↶ Undo to go back. Save again for zoning / design."), "ok");
}
$("placego").onclick = () => {
  const m = $("placell").value.match(/(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)/);
  if (!m) return notify(tr("lat, lng नहीं पढ़ा", "No lat, lng"), tr("जैसे: 25.2833, 82.9871 (Google Maps में जगह पर right-click करके coordinates copy करें)",
    "e.g. 25.2833, 82.9871 (right-click the place in Google Maps to copy its coordinates)"), "err");
  const to = L.latLng(+m[1], +m[2]);
  doPlace(placeFrom || netLayer.getBounds().getCenter(), to);
};

// ---- the drawing's texts on the map when zoomed in
let textTimer = null;
map.on("moveend", () => { clearTimeout(textTimer); textTimer = setTimeout(drawTexts, 250); });
$("ntexts").onchange = drawTexts;
// only in the layout view, where the network is checked against its drawing - in the zones / design views the drawing's
// own texts (P-..., its sizes, flows, levels) would mix with the app's labels (user request 20-Oct-2026)
async function drawTexts() {
  textLayer.clearLayers();
  if (mode !== "dxf" || !NET || !$("ntexts").checked || map.getZoom() < 19 || curView !== "layout") { map.removeLayer(textLayer); return; }
  const b = map.getBounds();
  // the junction names / GLs the page writes itself (mhlabels) are not written a second time from the drawing
  const hide = $("mhlabels").checked ? 1 : 0;
  const r = await api(`/api/net_texts?name=${encodeURIComponent(NET.name)}&s=${b.getSouth()}&w=${b.getWest()}&n=${b.getNorth()}&e=${b.getEast()}&hide=${hide}`);
  if (!r.ok) return;
  for (const t of r.texts.slice(0, 1500))
    L.marker([t[0], t[1]], { icon: L.divIcon({ className: "dxftext", html: esc(t[2]), iconSize: null }), interactive: false, keyboard: false }).addTo(textLayer);
  textLayer.addTo(map);
}
