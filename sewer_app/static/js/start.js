// The sewer map page (map.html), part 9 of 9: long work, the left panel, the start of the page and the tooltips.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---------------------------------------------------------------- long work: animation, no interruption, message at the end
let BUSY = null;
$("u_url").addEventListener("input", () => {           // no {z}: a WMS - its layer names wanted
  const u = $("u_url").value.trim(); $("u_wmsrow").hidden = !u || /\{z\}/i.test(u) || /\/MapServer\/?$/i.test(u);
});
$("urlmodal").querySelectorAll("a.ex").forEach(a => a.onclick = () => {
  $("u_name").value = a.dataset.n; $("u_url").value = a.dataset.u; $("u_maxz").value = a.dataset.z; $("u_kind").value = "base";
  $("u_url").dispatchEvent(new Event("input"));
});
$("u_close").onclick = () => $("urlmodal").classList.remove("show");
$("u_add").onclick = () => {
  const d = { name: $("u_name").value.trim(), url: $("u_url").value.trim(), layers: $("u_layers").value.trim(),
              kind: $("u_kind").value, op: $("u_op").value, maxz: $("u_maxz").value };
  if (!/^https?:\/\//i.test(d.url)) return notify(tr("URL ठीक नहीं", "URL not valid"), tr("URL http:// या https:// से शुरू होना चाहिए।", "The URL must start with http:// or https://."), "err");
  const xyz = /\{z\}/i.test(d.url) || /\/MapServer\/?$/i.test(d.url);
  if (!xyz && !d.layers) return notify(tr("WMS layer नहीं", "No WMS layer"), tr("URL में {z}/{x}/{y} नहीं है, इसलिए यह WMS माना गया - उसके layer के नाम भरें (QGIS में WMS जोड़ते समय दिखते हैं)।",
    "The URL has no {z}/{x}/{y}, so it is taken as a WMS - give its layer names (QGIS shows them when adding the WMS)."), "err");
  if (!xyz && /[?&]request=getcapabilities/i.test(d.url)) d.url = d.url.split("?")[0];
  d.name = d.name || (xyz ? d.url.replace(/^https?:\/\//, "").split("/")[0] : d.layers);
  addUrlMap(d, true); saveUrlMaps(); listUrlMaps();
  $("u_name").value = ""; $("u_url").value = ""; $("u_layers").value = ""; $("u_wmsrow").hidden = true;
  status(tr(`नक्शा जोड़ा: ${d.name} (परतों की सूची में भी)`, `Map added: ${d.name} (also in the layers list)`), "ok");
};
function notify(title, msg, kind) {                 // a message in the middle of the page, closed with OK
  return new Promise(res => {
    $("mtitle").textContent = title; $("mtitle").className = kind || "ok"; $("mmsg").textContent = msg || "";
    $("modal").classList.add("show"); $("mok").focus();
    $("mok").onclick = () => { $("modal").classList.remove("show"); res(); };
  });
}
document.addEventListener("keydown", e => {
  if ($("modal").classList.contains("show") && (e.key === "Enter" || e.key === "Escape")) { e.preventDefault(); $("mok").click(); }
}, true);
function busyText() { if (BUSY) $("busytext").textContent = `${BUSY.label} … ${Math.round((Date.now() - BUSY.t0) / 1000)} s`; }
function beforeUnload(e) { e.preventDefault(); e.returnValue = ""; }
// fn = the original handler; result() -> [title, message, kind] read from the page when it has finished
async function longTask(label, fn, result, opts) {
  if (BUSY) {
    if (BUSY.nest) { BUSY.label = label; busyText(); return fn(); }          // a step of the running work
    return notify("काम चल रहा है", tr(`अभी "${BUSY.label}" चल रहा है (${Math.round((Date.now() - BUSY.t0) / 1000)} s से)। `,
      `Still working: "${T(BUSY.label)}" (for ${Math.round((Date.now() - BUSY.t0) / 1000)} s). `) +
      "उसके पूरा होने तक रुकें - बीच में दूसरा काम शुरू करने से उसका नतीजा गड़बड़ा सकता है।", "warn");
  }
  BUSY = { label, t0: Date.now(), nest: !!(opts && opts.nest) };
  $("busybar").classList.add("show"); busyText();
  const tick = setInterval(busyText, 1000);
  window.addEventListener("beforeunload", beforeUnload);
  const t0 = BUSY.t0;
  try { await fn(); }
  catch (e) { $("log").hidden = false; $("log").textContent = String(e); }
  finally {
    clearInterval(tick); $("busybar").classList.remove("show");
    window.removeEventListener("beforeunload", beforeUnload);
    BUSY = null;
  }
  const [title, msg, kind] = result();
  await notify(title, `${msg}\n\n(${Math.round((Date.now() - t0) / 1000)} s)`, kind);
}
// while work runs, the other buttons of the panel only warn (the view buttons and the map stay free)
document.addEventListener("click", e => {
  if (!BUSY) return;
  const b = e.target.closest("#side button, #side select");
  if (!b || b.closest("#viewseg") || b.id === "mok") return;
  e.stopPropagation(); e.preventDefault();
  notify("काम चल रहा है", tr(`अभी "${BUSY.label}" चल रहा है (${Math.round((Date.now() - BUSY.t0) / 1000)} s से)। पूरा होने तक रुकें - `,
    `Still working: "${T(BUSY.label)}" (for ${Math.round((Date.now() - BUSY.t0) / 1000)} s). Wait until it has finished - `) +
    "बीच में दूसरा काम शुरू करने से उसका नतीजा गड़बड़ा सकता है। नक्शा देख सकते हैं।", "warn");
}, true);

const isErr = id => /err/.test($(id).className);
{
  const run0 = $("run").onclick;
  $("run").onclick = () => longTask("Layout बन रहा है", run0, () => isErr("status")
    ? ["Layout नहीं बना", $("status").textContent + "\n" + ($("log").textContent || "").slice(-600), "err"]
    : ["Layout बन गया", $("status").textContent, "ok"]);
  const dxf0 = $("dxfimport").onclick;
  // no GL layer ticked: the layers the GL could come from first, the user ticks one and confirms (glOptions)
  $("dxfimport").onclick = async () => { if (await dxfNameOk()) glOptions(dxfRun); };   // sewer: the GL / IL box every time
  const dxfRun = () => longTask("DXF से network निकाल रहे हैं", dxf0, () => (isErr("dxfstatus") || !NET)
    ? ["Network नहीं निकला", $("dxfstatus").textContent + "\n" + ($("log").textContent || "").slice(-600), "err"]
    : ["Network निकल आया", `${NET.summary.manholes} manholes, ${NET.summary.conduits} sewers, ${(NET.summary.length / 1000).toFixed(2)} km\n` +
       `${NET.issues.filter(i => !i[6] && !i[7]).length} गड़बड़ियाँ (CHECK) जाँचने को - बाईं ओर समूहों में।`, "ok"]);
  const z0 = $("zrun").onclick;
  $("zrun").onclick = () => {
    const given = $("zmode").value === "given";
    return longTask(given ? "Zones (केवल दिए outfalls)" : "Zoning चल रही है", z0, () => {
      if (isErr("zstatus")) return ["Zoning नहीं हुई", $("zstatus").textContent + "\n" + ($("log").textContent || "").slice(-600), "err"];
      return ["Zoning पूरी", $("zstatus").textContent + "\n" + (given ? tr("अब \"Design (केवल दिए outfalls)\" दबाएँ।", "Now press \"Design (given outfalls only)\".")
        : tr("किसी पंक्ति पर click = नक्शे पर zones; option चुनकर \"Design\" दबाएँ।",
             "Click a row = its zones on the map; choose an option and press \"Design\".")), "ok"];
    });
  };
  const d0 = runDesign;
  runDesign = o => longTask(`Option ${o.option} का design`, () => d0(o), () => isErr("dstatus") || !designData
    ? ["Design नहीं हुआ", $("dstatus").textContent + "\n" + ($("log").textContent || "").slice(-600), "err"]
    : ["Design पूरा", designMsg(), "ok"]);
}
function designMsg() {
  const s = designData.summary;
  return `Option ${s.option} (${s.grade}): ${s.sewers} sewers, ${(s.length / 1000).toFixed(2)} km, सबसे गहरा ${s.max_depth} m\n` +
    `Pipe लागत ₹ ${lakh(s.pipe_lakh)} लाख; outfalls ${s.outfalls.join(", ")}\n` +
    (designData.warnings.length ? `${designData.warnings.length} चेतावनी - बाईं ओर देखें\n` : "") +
    `Files: ${Object.values(designData.files).map(f => f.split(/[\\/]/).pop()).join(", ")}`;
}

// ---------------------------------------------------------------- the left panel: drag its edge to resize
(function splitter() {
  const side = $("side"), bar = $("splitter"), MIN = 300, DEF = 360;
  const clamp = w => Math.max(MIN, Math.min(w, Math.round(window.innerWidth * 0.75)));
  const setW = w => { side.style.width = clamp(w) + "px"; map.invalidateSize(); };
  try { const w = parseInt(localStorage.getItem("sewer_app_side_w")); if (w) setW(w); } catch (e) { }
  let start = null;
  bar.addEventListener("pointerdown", e => {
    start = { x: e.clientX, w: side.getBoundingClientRect().width };
    try { bar.setPointerCapture(e.pointerId); } catch (err) { }
    bar.classList.add("drag"); document.body.classList.add("resizing");
  });
  bar.addEventListener("pointermove", e => { if (start) setW(start.w + e.clientX - start.x); });
  const end = () => {
    if (!start) return;
    start = null; bar.classList.remove("drag"); document.body.classList.remove("resizing");
    try { localStorage.setItem("sewer_app_side_w", parseInt(side.style.width)); } catch (e) { }
  };
  bar.addEventListener("pointerup", end); bar.addEventListener("pointercancel", end);
  bar.addEventListener("dblclick", () => { setW(DEF); try { localStorage.removeItem("sewer_app_side_w"); } catch (e) { } });
  window.addEventListener("resize", () => { if (side.style.width) setW(parseInt(side.style.width)); });
})();

// ---------------------------------------------------------------- start
(async function restore() {
  await guideReady;                                     // the guidelines first (opened from the start page)
  let last = null;
  try { last = JSON.parse(localStorage.getItem(LS_LAST) || "null"); } catch (e) { }
  if (last && last.name) $("loadtext").textContent = tr(`"${last.name}" खुल रहा है …`, `Opening "${last.name}" …`);
  if (last && last.kind === "dxf" && last.name) {          // a DXF network was open: open it again
    summary(); refreshList(); loadCatalogs();
    await loadNet(last.name); if (NET) $("plist").value = last.name;
    return;
  }
  if (last && last.kind === "kml" && last.name) {          // a project drawn on the map: again with its results
    summary(); loadCatalogs();
    const r = await api("/api/project?name=" + encodeURIComponent(last.name)).catch(() => null);
    let d = null; try { d = JSON.parse(localStorage.getItem(LS_DRAFT) || "null"); } catch (e) { }
    const draft = d && d.name === last.name && d.kml ? d.kml : null;
    if (!r || !r.ok || r.kind === "dxf") { remember(null); if (draft) fromKML(draft, true); summary(); refreshList(); return; }
    await refreshList(); $("plist").value = last.name;
    // changes drawn after the last save come back too (marked unsaved)
    await openKml(last.name, draft && draft !== r.kml ? draft : r.kml, !!(draft && draft !== r.kml));
    return;
  }
  try {
    const d = JSON.parse(localStorage.getItem(LS_DRAFT) || "null");
    if (d && d.kml) { const n = fromKML(d.kml, true); $("pname").value = d.name || "new_project";
      if (n.road + n.ward + n.spot + n.boundary + n.stp) status("पिछला बिना सहेजा काम वापस लाया गया।"); }
  } catch (e) { }
  dirty = false;
  summary();
  await refreshList();
  loadCatalogs();
})().catch(e => status(String(e), "err")).finally(() => loading(false));

// ---- a tooltip on every button / option (user request 20-Oct-2026): what it does, shown on mouse over. Where the page
// already gives one it stays (several follow the state, e.g. Save, Zoning, Design); the row's label gets it too when
// the row has that one option. Watched: the left panel, the table and the message boxes (not the map's markers).
const TIPS = [
  // project
  ["#pname", "Project का नाम - project और उसके नतीजे (output\\<नाम>) इसी नाम से सहेजे जाते हैं",
             "Project name - the project and its results (output\\<name>) are saved under it"],
  ["#plist", "पहले सहेजे projects; '(DXF)' = DXF drawing से पढ़ा network", "Saved projects; '(DXF)' = a network read from a DXF drawing"],
  ["#popen", "चुना project खोलें - drawing / network और पिछली zoning व design वापस आते हैं",
             "Open the chosen project - its drawing / network and its last zoning and design come back"],
  ["#psave", "Project सहेजें", "Save the project"],
  ["#kmlget", "नक्शे पर खींची drawing (सड़कें, boundary, वार्ड + population, spot levels, STP) KML file में download - Google Earth में खुलती है; layout, zoning, design इसमें नहीं (उनके लिए Export)। DXF network में बंद",
              "Download the drawing made on the map (roads, boundary, wards + population, spot levels, STP) as a KML file - opens in Google Earth; no layout, zoning or design (Export for those). Off for a DXF network"],
  ["#kmlopen", "KML / KMZ file (जैसे Google Earth से) खोलें - उसकी सड़कें, boundary, वार्ड, spot levels, STP नक्शे पर आ जाते हैं",
               "Open a KML / KMZ file (e.g. from Google Earth) - its roads, boundary, wards, spot levels, STP come onto the map"],
  ["#dxfopen", "DXF drawing से network पढ़ें: layers चुनकर manholes, sewers / pipes, labels और GL",
               "Read the network from a DXF drawing: choose its layers for manholes, sewers / pipes, labels and GL"],
  ["#pnew", "नया project: नक्शे से सब हटाएँ (सहेजा हुआ project नहीं मिटता)", "New project: clear the map (a saved project is not deleted)"],
  // DXF panel
  ["#dxfpath", "DXF file का पूरा path - Explorer में file पर Shift + right-click → \"Copy as path\"",
               "Full path of the DXF file - in Explorer: Shift + right-click on the file → \"Copy as path\""],
  ["#dxflayers", "DXF की layers पढ़ें - फिर चुनें कि कौन-सी layers sewers / pipes, manholes और levels की हैं",
                 "Read the layers of the DXF - then choose which are the sewers / pipes, manholes and levels"],
  ["#dxfclose", "यह panel बंद करें", "Close this panel"],
  ["#dxfname", "नए project का नाम", "Name of the new project"],
  ["#dxfepsg", "Drawing के coordinates किस UTM zone के हैं: स्प्रिंगफ़ील्ड / पूर्वी UP 44N, पश्चिमी UP 43N; Local = नक्शे के बिना, केवल drawing",
               "UTM zone of the drawing's coordinates: Springfield / eastern UP 44N, western UP 43N; Local = no map, drawing only"],
  ["#dxfimport", "चुनी layers से network बनाएँ: manholes, sewers, labels, GL - गड़बड़ियाँ नीचे की सूची में",
                 "Make the network from the chosen layers: manholes, sewers, labels, GL - the problems in the list below"],
  // DXF network tools
  ["#ntools [data-t=select]", "चुनें: manhole / sewer पर click करके उसका ब्योरा देखें और बदलें (Delete = हटाएँ)",
                              "Select: click a manhole / sewer to see and change it (Delete = remove)"],
  ["#ntools [data-t=connect]", "दो manholes पर बारी-बारी click करके उनके बीच नया sewer / pipe जोड़ें",
                               "Click two manholes one after the other to join them with a new sewer / pipe"],
  ["#ntools [data-t=merge]", "दो manholes पर बारी-बारी click करके उन्हें एक manhole में मिलाएँ",
                             "Click two manholes one after the other to merge them into one"],
  ["#ntools [data-t=split]", "Sewer / pipe पर जहाँ click करें वहाँ नया manhole डालकर उसे दो में तोड़ें",
                             "Click on a sewer / pipe to put a new manhole there and cut it in two"],
  ["#ntools [data-t=move]", "Manhole को खींचकर नई जगह रखें - उसके sewers साथ चलते हैं",
                            "Drag a manhole to a new place - its sewers follow"],
  ["#placell", "Network की असली जगह का lat, lng - Google Maps में जगह पर right-click से copy करें",
               "lat, lng of the network's real place - right-click the place in Google Maps to copy it"],
  ["#nundo", "पिछला बदलाव वापस लें (20 तक)", "Undo the last change (up to 20)"],
  ["#ntexts", "पास zoom (19 या अधिक) पर drawing के अपने texts नक्शे पर - केवल Layout view में",
              "The drawing's own texts on the map when zoomed in (19 or more) - layout view only"],
  ["#showrev", "जाँची हुई (✔) गड़बड़ियाँ भी सूची और नक्शे पर दिखाएँ", "Show the problems already checked (✔) too, in the list and on the map"],
  // drawing tools
  [".tools [data-kind=road]", "सड़क की centreline खींचें - हर click एक बिंदु; आखिरी बिंदु पर दोबारा click, Enter या right-click से पूरा। Layout इन्हीं सड़कों पर बनता है",
                              "Draw a road centreline - every click a point; click the last point again, Enter or right-click to finish. The layout is made on these roads"],
  [".tools [data-kind=boundary]", "Project की सीमा (polygon) खींचें - layout इसके अंदर बनता है", "Draw the project boundary (polygon) - the layout is made inside it"],
  [".tools [data-kind=ward]", "वार्ड का polygon खींचें और उसकी population भरें - population उसके manholes में sewer की लंबाई से बँटती है",
                              "Draw a ward polygon and give its population - it is spread over its manholes by sewer length"],
  [".tools [data-kind=spot]", "Spot level (GL) का बिंदु रखें - manholes का GL इन बिंदुओं से (TIN) निकलता है",
                              "Place a spot level (GL) - the manholes' GL comes from these points (TIN)"],
  [".tools [data-kind=stp]", "STP / outfall की जगह रखें - उसके सबसे पास का manhole \"STP manhole\" बनता है",
                             "Place the STP / outfall - its nearest manhole becomes the \"STP manhole\""],
  ["#editbtn", "खींची वस्तुएँ (सड़क, polygon, बिंदु) बदलें या हटाएँ", "Change or remove the drawn items (roads, polygons, points)"],
  ["#dfinish", "खींचना पूरा करें (Enter)", "Finish drawing (Enter)"],
  ["#dundo", "पिछला बिंदु हटाएँ (Ctrl+Z)", "Remove the last point (Ctrl+Z)"],
  ["#dcancel", "खींचना रोकें - यह वस्तु नहीं बनेगी (Esc)", "Stop drawing - this item is not made (Esc)"],
  ["#esave", "किए बदलाव रखें (Enter)", "Keep the changes (Enter)"],
  ["#ecancel", "बदलाव रद्द करें (Esc)", "Cancel the changes (Esc)"],
  // layout
  ["#glmode", "Manholes का GL कहाँ से: खींचे spot levels से (TIN), सब जगह एक ही GL (केवल मोटा अनुमान), या खाली (बाद में भरें)",
              "Where the manholes' GL comes from: the spot levels drawn (TIN), one GL everywhere (a rough guess only), or none (fill in later)"],
  ["#flatgl", "सब manholes का एक ही GL (m) - केवल मोटा अनुमान", "One GL (m) for every manhole - a rough guess only"],
  ["#spacing", "Layout में सड़क पर manholes की अधिकतम दूरी (m) - CPHEEO 3.71.1 (p3-126): 30 m; हर चौराहे, सिरे और मोड़ पर भी manhole",
               "In the layout, the largest distance (m) between manholes along a road - CPHEEO 3.71.1 (p3-126): 30 m; a manhole also at every junction, end and bend"],
  ["#snapm", "सड़क का सिरा दूसरी सड़क से इतनी दूरी (m) के भीतर हो तो उससे जोड़ दिया जाता है",
             "A road end within this distance (m) of another road is joined to it"],
  ["#run", "खींची सड़कों से sewer layout बनाएँ: manholes, sewers, GL, population (PFR)", "Make the sewer layout from the roads drawn: manholes, sewers, GL, population (PFR)"],
  ["#showres", "बना layout नक्शे पर दिखाएँ / छिपाएँ", "Show / hide the layout on the map"],
  // zoning and design
  ["#catalog", "Pipe की सूची (sizes, internal dia, Manning n, दरें) - data/sewer_catalog.json से",
               "The pipe catalog (sizes, internal diameter, Manning n, rates) - from data/sewer_catalog.json"],
  ["#joint", "Joint का प्रकार - catalog में उसके हिसाब से Manning n", "Joint type - the catalog's Manning n for it"],
  ["#lpcd", "प्रति व्यक्ति sewage (L / दिन) = पानी की आपूर्ति × return factor (जैसे 135 × 0.8 = 108)",
            "Sewage per person (L / day) = water supply × return factor (e.g. 135 × 0.8 = 108)"],
  ["#sdepth", "शुरुआती (सबसे ऊपरी) manhole पर invert तक गहराई (m) - इससे pipe के ऊपर की मिट्टी (cover) तय होती है",
              "Depth to invert (m) at a starting (top) manhole - it sets the earth cover over the pipe"],
  ["#stp", "STP का manhole label - नक्शे पर STP रखा हो तो अपने-आप भरता है", "Label of the STP's manhole - filled in by itself when the STP is placed on the map"],
  ["#zmode", "स्वतंत्र: ज़मीन की ढलान से zoning के कई options, गहराई-सीमा पर अपने-आप pumping station; केवल दिए outfalls: सिर्फ़ चिह्नित outfalls / STP पर, कोई pumping station नहीं",
             "Free: several zoning options from the ground slope, a pumping station where the depth limit is passed; given outfalls only: only the marked outfalls / STP, no pumping station"],
  ["#poptot", "कुल design population (+30 वर्ष) - वार्डों में population न हो तो यही manholes में sewer की लंबाई से बँटती है",
              "Total design population (+30 years) - without ward populations it is spread over the manholes by sewer length"],
  ["#viewseg [data-v=layout]", "Layout / network दिखाएँ", "Show the layout / network"],
  ["#viewseg [data-v=zones]", "चुने option के zones, sub-zones और उनकी सीमाएँ दिखाएँ", "Show the chosen option's zones, sub-zones and their boundaries"],
  ["#viewseg [data-v=design]", "Design का नतीजा दिखाएँ: size, गहराई, नए manholes, flow की दिशा", "Show the design: sizes, depths, new manholes, flow direction"],
  ["#zexport", "चुने option के zones / sub-zones: DXF (उस option का ताज़ा design हो तो उसकी drawing सहित), KML (Google Earth) और Excel",
               "The chosen option's zones / sub-zones: DXF (with the drawing of its design when there is a current one), KML (Google Earth) and Excel"],
  ["#optbox button[data-d]", "इस option का design: sizes, गहराई, report (Excel), plan और L-section DXF",
                             "Design this option: sizes, depths, report (Excel), plan and L-section DXF"],
  // the pipe / manhole table
  ["#tbltabs button", "तालिका बदलें: conduits / manholes", "Switch table: conduits / manholes"],
  ["#tblq", "Label या manhole से पंक्तियाँ खोजें", "Find rows by label or manhole"],
  ["#tblfail", "केवल वे पंक्तियाँ जिनकी कोई जाँच पूरी नहीं होती", "Only the rows with a check not met"],
  // the selected item (drawing / DXF network)
  ["#f_name", "इस वस्तु का नाम", "Name of this item"],
  ["#f_pop", "इस वार्ड / क्षेत्र की population", "Population of this ward / area"],
  ["#f_gl", "इस बिंदु का GL (m)", "GL (m) of this point"],
  ["#f_kind", "यह polygon boundary ↔ वार्ड में बदलें", "Turn this polygon from boundary to ward or back"],
  ["#f_del", "चुनी वस्तु हटाएँ (Delete)", "Remove the selected item (Delete)"],
  ["#n_label", "Manhole का नाम बदलें (Enter)", "Rename the manhole (Enter)"],
  ["#n_gl", "Manhole का GL (m) बदलें (Enter)", "Change the manhole's GL (m) (Enter)"],
  ["#n_out", "इसे outfall मानें: STP / मौजूदा sewer / pumping station - zoning में यहाँ से बाहर", "Make it an outfall: STP / existing sewer / pumping station - an outlet for the zoning"],
  ["#n_sug", "सुझाया drawing label (और GL) इस manhole पर लगाएँ", "Give this manhole the drawing label (and GL) suggested"],
  ["#n_del", "यह manhole और इसके sewers हटाएँ", "Remove this manhole and its sewers"],
  ["#props button[data-go]", "इस manhole पर जाएँ", "Go to this manhole"],
  ["#c_del", "यह sewer हटाएँ", "Remove this sewer"],
  ["#props input[data-rk]", "जाँच ली - सूची में ✔ (grey) हो जाती है", "Checked - it turns ✔ (grey) in the list"],
  ["#sugall", "हर बिना label वाले manhole को पास का बचा हुआ drawing label (और GL) लगाएँ - Undo से वापस", "Give every manhole without a label the nearest unused drawing label (and GL) - Undo takes it back"],
  // message boxes
  ["#mok", "यह संदेश बंद करें (Enter)", "Close this message (Enter)"],
  ["#gclose", "Guidelines बंद करें", "Close the guidelines"],
  ["#u_name", "इस नक्शे का नाम (सूची में दिखेगा)", "Name of this map (shown in the list)"],
  ["#u_url", "Tiles का URL: XYZ ({z}/{x}/{y}), ArcGIS …/MapServer, या WMS", "URL of the tiles: XYZ ({z}/{x}/{y}), ArcGIS …/MapServer, or WMS"],
  ["#u_layers", "WMS की layers के नाम, comma से अलग", "Names of the WMS layers, comma separated"],
  ["#u_kind", "आधार नक्शा (OSM / Satellite की जगह) या ऊपर की परत (overlay)", "A base map (instead of OSM / Satellite) or a layer on top (overlay)"],
  ["#u_op", "पारदर्शिता: 1 = पूरा दिखे, 0.1 = लगभग पारदर्शी", "Opacity: 1 = fully shown, 0.1 = nearly transparent"],
  ["#u_maxz", "इस zoom तक tiles लें; इससे आगे वही tiles बड़ी करके", "Tiles up to this zoom; beyond it the same tiles enlarged"],
  ["#u_add", "यह नक्शा जोड़ें", "Add this map"],
  ["#u_close", "बंद करें", "Close"],
];
function applyTips(root) {
  if (!root || root.nodeType !== 1) return;
  for (const [sel, hi, en] of TIPS) {
    const els = root.matches(sel) ? [root] : [];
    els.push(...root.querySelectorAll(sel));
    for (const el of els) {
      if (el.title) continue;
      const t = typeof hi === "function" ? hi() : tr(hi, en);
      el.title = t;
      // the row's label (one option in the row): the same tooltip on the name in front of it
      const row = el.closest(".row"), lab = row && row.querySelector(":scope > label");
      if (lab && !lab.title && !lab.contains(el) && row.querySelectorAll("input, select").length === 1) lab.title = t;
    }
  }
}
for (const id of ["side", "tbl", "modal", "urlmodal", "loading", "guide"]) {
  const box = $(id); if (!box) continue;
  applyTips(box);
  new MutationObserver(ms => { for (const m of ms) for (const n of m.addedNodes) applyTips(n); }).observe(box, { childList: true, subtree: true });
}
