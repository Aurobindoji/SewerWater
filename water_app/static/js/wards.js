// The water map page (map.html), part 7 of 11: the population projection, the ward table, the town's wards and its census.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---- population projection (user request 30-Oct-2026, as the Elmwood 'T'): the base year and its population (popb)
// with the census of the town -> the population of the base year, +15 and +30 years by five methods (population.py),
// one adopted (default geometrical); then the +15 years population and the factor (+30 / base) follow from it and
// are not typed (the population on the junctions is the base year's).
let PJ = null, PJ_METHOD = "";
const PJ_COL = { arithmetical: "#2a78d6", incremental: "#eb6834", geometrical: "#1baf7a", decreasing: "#7e57c2", graph: "#eda100", semilog: "#e87ba4" };  // dataviz categorical, validated
const PJ_SHORT = { arithmetical: "Arith.", incremental: "Incr.", geometrical: "Geom.", decreasing: "Decr.", graph: "Graph", semilog: "Semi-log" };
// each method's tooltip (user 9-Nov-2026): for which town CPHEEO finds it suitable and its caution - CPHEEO Manual on
// Water Supply 2024 Part A, Annexure 2.8 (p977-980); short, to choose by
const PJ_TIP = {
  arithmetical: ["उपयुक्त: बड़ा, पुराना, बसा हुआ विकसित शहर - हर दशक लगभग बराबर बढ़त। ⚠ छोटे / नए / तेज़ बढ़ते शहर में कम अनुमान।",
                 "Suits: a large, old, well-settled developed town - about the same increase every decade. ⚠ Low for a small / new / fast-growing town."],
  incremental: ["उपयुक्त: सामान्य हालात का औसत आकार का शहर, जिसकी दशक-वार बढ़त लगातार बढ़ रही हो। ⚠ योजना / उद्योग से अचानक बढ़त नहीं पकड़ती; औसत incremental (Y) ऋणात्मक हो तो न अपनाएँ।",
                "Suits: an average-sized town in normal conditions whose decadal increase keeps rising. ⚠ Misses growth driven by schemes / industry; do not adopt if the average incremental (Y) is negative."],
  geometrical: ["उपयुक्त: नया, तेज़ी से बढ़ता शहर जिसमें फैलने की बहुत जगह हो (जैसे शुरुआती दशकों का नया औद्योगिक शहर)। ⚠ ज़्यादा (excessive) अनुमान - बड़े पुराने शहर में सोचकर अपनाएँ।",
                "Suits: a new, fast-growing town with much room to expand (e.g. a new industrial town in its first decades). ⚠ Excessive forecasts - adopt with care for a large old town."],
  decreasing: ["उपयुक्त: जिस शहर की दशक-वार वृद्धि दर लगातार घट रही हो (बड़ा, परिपक्व शहर)। ⚠ दर बढ़ रही हो (S धनात्मक) तो न अपनाएँ; census एक ही सीमा की हो।",
               "Suits: a town whose decadal growth rate keeps falling (a large, mature town). ⚠ Not if the rate is rising (S positive); the census should be of one boundary."],
  graph: ["उपयुक्त: census का रुझान सीधा (लगभग बराबर बढ़त) हो - least squares सीधी रेखा, CPHEEO के अनुसार अनुभव व judgment से। ⚠ बढ़ती दर वाले शहर में कम अनुमान।",
          "Suits: a census trend that is straight (about equal increases) - a least-squares line, by experience and judgment per CPHEEO. ⚠ Low for a town whose growth accelerates."],
  semilog: ["उपयुक्त: census ln-पैमाने पर सीधी हो (समान दर वाली बढ़त) - graphical विधि का रूप, geometrical जैसी। ⚠ geometrical की तरह ज़्यादा अनुमान दे सकती है।",
            "Suits: a census straight on a log scale (growth at a steady rate) - a form of the graphical method, like geometrical. ⚠ May over-forecast, as geometrical."] };
const PJ_TIP_ALL = ["CPHEEO 2.8.2.2: शहर के बढ़ने के ढंग से उपयुक्त विधि चुनें; अंतिम आबादी ULB, Town & Country Planning से मिलकर तय करे।",
                    "CPHEEO 2.8.2.2: choose the method by the town's growth pattern; the ULB fixes the final population with Town & Country Planning."];
function pjTip(m) { const t = PJ_TIP[m]; return t ? esc(`${EN ? t[1] : t[0]} (CPHEEO Annexure 2.8)`) : ""; }
function pjInputs() {
  return $("pjcensus").value.trim() && ($("popb").value || wtTotal() > 0) ? { base_pop: $("popb").value, census: $("pjcensus").value, method: PJ_METHOD } : null;
}
function pjLock(on) {                     // the fields the projection fills
  for (const id of ["popm", "wpopf"].concat(wtTotal() > 0 ? ["popb"] : [])) { $(id).readOnly = on; $(id).classList.toggle("locked", on); }
  if (!(wtTotal() > 0)) { $("popb").readOnly = false; $("popb").classList.remove("locked"); }
  $("wpopf").title = on ? tr("projection से: +30 वर्ष / आधार वर्ष", "from the projection: +30 years / base year") : "";
  popUi();
}
async function pjRun(quiet) {
  const p = pjInputs();
  if (!p) { PJ = null; $("pjout").innerHTML = ""; pjLock(false);
    if (!quiet) $("pjstatus").textContent = !$("pjcensus").value.trim()
      ? tr("Census का खाना खाली है - शहर (ULB) की census भरें, जैसे 1991 1139236, 2001 1374963, 2011 1636569 (धूसर लिखावट सिर्फ़ उदाहरण है)",
           "the census is empty - fill in the town's census, e.g. 1991 1139236, 2001 1374963, 2011 1636569 (the grey text is only an example)")
      : tr("आधार वर्ष की आबादी भरें, या ऊपर वार्ड तालिका", "fill in the base-year population, or the ward table above");
    return; }
  const r = await api("/api/projection", { base_year: $("byear").value, projection: p, ward_table: wtInputs() });
  if (!r.ok || !r.projection) { PJ = null; $("pjout").innerHTML = ""; pjLock(false); $("pjstatus").textContent = r.log || ""; return; }
  PJ = r.projection; PJ_METHOD = PJ.adopted; $("pjstatus").textContent = "";
  if (WT.rows.length) wtGrowthRender();     // Far-open balanced to this method (7-Nov-2026)
  if (PJ.wards) {                         // wards with a character: each by its factors, the others by the method
    $("popb").value = Math.round(PJ.wards.init); $("popm").value = Math.round(PJ.wards.mid);
    $("wpopf").value = PJ.ratio_from.ult.toFixed(4);
  } else if (PJ.from_year) {              // the wards' population of their year, grown from it (7-Nov-2026)
    $("popb").value = Math.round(PJ.base_pop); $("popm").value = Math.round(PJ.pop.mid);
    $("wpopf").value = PJ.ratio_from.ult.toFixed(4);
  } else {
    $("popm").value = Math.round(PJ.pop.mid * (+$("popb").value) / PJ.base_pop);
    $("wpopf").value = PJ.ratio.ult.toFixed(4);
  }
  pjLock(true);
  pjRender();
}
function pjRender() {
  const f = PJ, ms = Object.keys(f.by_method), y = f.years;
  const rows = ms.map(m => { const v = f.by_method[m];
    return `<tr${m === f.adopted ? ' style="font-weight:600"' : ""}><td title="${pjTip(m)}"><label style="min-width:0;cursor:pointer" title="${pjTip(m)}"><input type="radio" name="pjm" value="${m}"${m === f.adopted ? " checked" : ""}> ` +
      `<span class="k" style="background:${PJ_COL[m]};display:inline-block;width:10px;height:3px;vertical-align:middle"></span> ${esc(EN ? f.names[m][0] : f.names[m][1])}</label></td>` +
      `<td>${fmt(v.init)}</td><td>${fmt(v.mid)}</td><td>${fmt(v.ult)}</td><td>${(v.ult / v.init).toFixed(2)}</td></tr>`; }).join("");
  const g = f.growth;
  $("pjout").innerHTML = `<table class="wz"><tr><th title="${esc(EN ? PJ_TIP_ALL[1] : PJ_TIP_ALL[0])} ${tr("हर विधि पर mouse ले जाएँ: वह किस शहर के लिए उपयुक्त है।", "Hover a method: which town it suits.")}">${tr("विधि (चुनी = अपनाई)", "Method (chosen = adopted)")} ⓘ</th><th>${y.init}</th><th>${y.mid}</th><th>${y.ult}</th><th title="${tr("+30 वर्ष / आधार", "+30 years / base")}">×</th></tr>${rows}</table>` +
    `<div class="hint">X = ${fmt(f.X)} ${tr("प्रति दशक", "per decade")}, Y = ${f.Y == null ? "-" : fmt(f.Y)}, r = ${(f.r * 100).toFixed(2)} % ${tr("प्रति दशक", "per decade")}` +
    (f.S == null ? " " : `, S = ${f.S >= 0 ? "+" : ""}${(f.S * 100).toFixed(2)} % ${tr("प्रति दशक (वृद्धि दर का औसत बदलाव - घटती दर विधि)", "per decade (the rate's average change - decreasing rate method)")} `) +
    `(census ${f.census[0][0]}-${f.census[f.census.length - 1][0]}, ${g.length} ${tr("दशक-अंतराल", "intervals")}); ${tr("graph विधियाँ: census पर fitted सीधी रेखा", "graph methods: a straight line fitted to the census")}</div>` +
    (f.wards ? `<div class="hint"><b>${tr("Project (चरित्र सहित)", "Project (with the characters)")}: ${fmt(f.wards.init)} / ${fmt(f.wards.mid)} / ${fmt(f.wards.ult)}</b> - ` +
      tr(`${f.wards.rows.filter(r => r.char).length} वार्ड अपने चरित्र के गुणक से, बाकी चुनी विधि से (x ${f.ratio_from.ult.toFixed(4)} = आबादी गुणक)`,
         `${f.wards.rows.filter(r => r.char).length} ward(s) by their character's factors, the others by the adopted method (x ${f.ratio_from.ult.toFixed(4)} = the population factor)`) + `</div>` : "") +
    f.notes.map(n => `<div class="wflag warn">⚠ ${esc(EN ? n[1] : n[0])}</div>`).join("") +
    `<div style="display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start"><div style="flex:1 1 300px;max-width:340px">${pjChart()}</div>` +
    `<div style="flex:1 1 280px">${pjCompare()}</div></div>` +
    `<div class="hint">${tr("चित्र: census की आबादी (बिंदु) और हर विधि से उसी का projection; project की आबादी = आधार वर्ष की आबादी × उसी विधि का अनुपात (तालिका)",
                            "Chart: the census population (dots) and each method's projection of it; the project's population = the base-year population x that method's ratio (table)")}</div>`;
  document.querySelectorAll('#pjout input[name="pjm"]').forEach(b => b.onchange = () => { PJ_METHOD = b.value; pjRun(true); });
}
// beside the chart (user 9-Nov-2026): the town's population by each method - the last census, the base / +15 / +30
// years, the ratio to the last census and its yearly rate - the chart's figures side by side, the adopted in bold
function pjCompare() {
  const f = PJ, c = f.census[f.census.length - 1], y = f.years;
  const rows = Object.entries(f.town).map(([m, v]) => {
    const n = y.ult - c[0], rate = n > 0 && c[1] > 0 ? (Math.pow(v.ult / c[1], 1 / n) - 1) * 100 : null;
    return `<tr${m === f.adopted ? ' style="font-weight:700"' : ""}><td style="white-space:nowrap" title="${pjTip(m)}"><span style="background:${PJ_COL[m]};display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle"></span> ${esc(EN ? f.names[m][0] : f.names[m][1])}</td>` +
      `<td>${fmt(v.init)}</td><td>${fmt(v.mid)}</td><td>${fmt(v.ult)}</td><td>${(v.ult / c[1]).toFixed(3)}</td><td>${rate == null ? "-" : rate.toFixed(2) + " %"}</td></tr>`; }).join("");
  return `<div class="hint" style="margin-top:4px"><b>${tr("शहर की आबादी, हर विधि से", "The town's population by each method")}</b> (census ${c[0]}: ${fmt(c[1])})</div>` +
    `<table class="wz"><tr><th>${tr("विधि", "Method")}</th><th>${y.init}</th><th>${y.mid}</th><th>${y.ult}</th>` +
    `<th title="${tr(`${y.ult} ÷ census ${c[0]}`, `${y.ult} / census ${c[0]}`)}">× ${c[0]}</th><th title="${tr("सालाना बढ़त (चक्रवृद्धि)", "yearly growth (compound)")}">${tr("% / वर्ष", "% / year")}</th></tr>${rows}</table>`;
}
// the projection's chart: the census dots and each method's projection of the census population itself (the town -
// on one scale with the census; the project's own figures are in the table) from the last census to +30 years,
// labelled at its end; one y axis (population), the adopted line thicker
function pjChart() {
  const f = PJ, W = 300, H = 170, L = 46, R = 84, T = 8, Bt = 22, last = f.census[f.census.length - 1];
  const xs = [...f.census.map(c => c[0]), f.years.ult], x0 = Math.min(...xs), x1 = Math.max(...xs);
  const all = [...f.census.map(c => c[1]), ...Object.values(f.town).flatMap(v => [v.init, v.mid, v.ult])];
  const y1 = Math.max(...all) * 1.05, X = v => L + (v - x0) / (x1 - x0) * (W - L - R), Y = v => T + (1 - v / y1) * (H - T - Bt);
  const k = v => v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : v >= 1e3 ? Math.round(v / 1e3) + "k" : Math.round(v);
  let s = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:${W + 40}px;font:10px sans-serif;margin-top:4px" role="img" aria-label="${tr("आबादी projection", "population projection")}">`;
  for (const t of [0, .25, .5, .75, 1]) s += `<line x1="${L}" x2="${W - R}" y1="${Y(y1 * t)}" y2="${Y(y1 * t)}" style="stroke:var(--line)"/><text x="${L - 4}" y="${Y(y1 * t) + 3}" text-anchor="end" style="fill:var(--muted)">${k(y1 * t)}</text>`;
  for (const yr of [x0, f.years.init, x1]) s += `<text x="${X(yr)}" y="${H - 6}" text-anchor="${yr === x1 ? "end" : "middle"}" style="fill:var(--muted)">${yr}</text>`;
  s += `<polyline points="${f.census.map(c => `${X(c[0])},${Y(c[1])}`).join(" ")}" fill="none" style="stroke:var(--muted)" stroke-width="1.5" stroke-dasharray="3 3"/>`;
  for (const c of f.census) s += `<circle cx="${X(c[0])}" cy="${Y(c[1])}" r="3" style="fill:var(--muted)"><title>census ${c[0]}: ${fmt(c[1])}</title></circle>`;
  const ends = Object.entries(f.town).map(([m, v]) => [m, Y(v.ult)]).sort((a, b) => a[1] - b[1]);
  for (let i = 1; i < ends.length; i++) if (ends[i][1] - ends[i - 1][1] < 11) ends[i][1] = ends[i - 1][1] + 11;   // labels apart
  const ly = Object.fromEntries(ends);
  for (const [m, v] of Object.entries(f.town)) {
    const pts = [last, [f.years.init, v.init], [f.years.mid, v.mid], [f.years.ult, v.ult]];
    s += `<polyline points="${pts.map(p => `${X(p[0])},${Y(p[1])}`).join(" ")}" fill="none" stroke="${PJ_COL[m]}" stroke-width="${m === f.adopted ? 3 : 1.5}"/>`;
    for (const p of pts.slice(1)) s += `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="4" fill="${PJ_COL[m]}" style="stroke:var(--panel)" stroke-width="1.5"><title>${esc(f.names[m][0])} ${p[0]}: ${fmt(p[1])}</title></circle>`;
    s += `<text x="${X(f.years.ult) + 6}" y="${ly[m] + 3}" style="fill:var(--text)"${m === f.adopted ? ' font-weight="bold"' : ""}>${PJ_SHORT[m]} ${k(v.ult)}</text>`;
  }
  return s + "</svg>";
}
$("pjrun").onclick = () => pjRun(false);
// ---- the ward table (user decision 7-Nov-2026): the number of wards opens a row for each - its no. (the ward drawn on
// the map with the same Ward No. takes its population), name, population of the year given, % covered, households,
// area and the 2011 census (for the DPR); the covered total is the projection's population of that year
var WT = { year: 2025, rows: [], growth: JSON.parse(JSON.stringify(WARD_GROWTH_DEF)), dens: Object.assign({}, WARD_DENS_DEF),
           city: Object.assign({}, WARD_TOWN_DEF), sat: WARD_SAT_DEF };
var CW = null;                            // the town's list of wards chosen (city_wards.py): {city, year, rows} or null
// Far-open balanced by the projection (wards.far_open_balance): {factors, total, target} or null
function pjFar() { try { return (PJ && PJ.far_open) || null; } catch (e) { return null; } }   // var / functions: used before this line runs
// the columns: key, title, width, input type ("char": the character's select; "ro": shown only - the KML's area share)
const WT_COLS = [["no", () => "Ward No.", 58, "text"], ["name", () => tr("नाम", "Name"), 110, "text"],
  ["char", () => tr("चरित्र", "Character"), 112, "char"],
  ["pop", () => tr("आबादी", "Population"), 80, "number"], ["cov", () => "% covered", 56, "number"],
  ["kcov", () => tr("KML क्षेत्रफल-%", "KML area %"), 52, "ro"],
  ["hh", () => "Households", 74, "number"], ["area", () => tr("क्षेत्रफल ha", "Area ha"), 86, "number"],
  ["census", () => tr("Census 2011 (वैकल्पिक)", "Census 2011 (optional)"), 74, "number"]];
const WT_TIPS = { char: () => tr("वार्ड का चरित्र (Riverside DPR p76): उसकी आबादी x नीचे के उसी चरित्र के गुणक (आधार / +15 / +30); — = चुनी projection विधि का अनुपात",
                                 "the ward's character (Riverside DPR p76): its population x that character's factors below (base / +15 / +30); — = the adopted projection's ratio"),
  cov: () => tr("project में आने वाला हिस्सा, आबादी के हिसाब से (technical.xlsx T1 जैसे); खाली = 100 %", "the share in the project, by population (as technical.xlsx T1); empty = 100 %"),
  census: () => tr("सिर्फ़ DPR की तालिका (T16) में दिखता है; design / projection में नहीं लगता - खाली छोड़ सकते हैं", "shown only in the DPR's table (T16); not used in the design / projection - may be left empty"),
  area: () => tr("CPHEEO 2.8.1.24 (iii): equivalent area = residential × 1 + public × 0.25 + उद्योग / कृषि × 0.1 + सड़क / जल × 0 - उपलब्ध हो तो यही भरें (density इसी पर)",
                  "CPHEEO 2.8.1.24 (iii): equivalent area = residential x 1 + public x 0.25 + industry / agriculture x 0.1 + roads / water x 0 - give it where known (the density on it)"),
  kcov: () => tr("KML से: वार्ड के क्षेत्रफल का zone में हिस्सा - सिर्फ़ जाँच के लिए, design में नहीं", "from the KML: the share of the ward's area in the zone - only a check, not used in the design") };
function wtCov(r) { return (+r.pop || 0) * (r.cov === "" || r.cov == null ? 100 : +r.cov) / 100; }
function wtTotal() { return (WT ? WT.rows : []).reduce((a, r) => a + wtCov(r), 0); }
function wtRow(no) { return no === undefined || no === null || String(no).trim() === "" ? null : WT.rows.find(r => String(r.no).trim() === String(no).trim()) || null; }
function wtInputs() { return WT && WT.rows.length ? { year: WT.year, rows: WT.rows, growth: WT.growth, dens: WT.dens, city: WT.city, sat: WT.sat ?? "", citylist: WT.citylist || "" } : null; }
// the wards above the saturation density in the design year (wards.saturation_over): density x the character's design
// factor, a ward without one x the adopted ratio (once the projection is run)
function wtSatOver() {
  const s = +WT.sat || 0; if (!(s > 0)) return [];
  let ru = null; try { ru = PJ && PJ.ratio_from ? PJ.ratio_from.ult : null; } catch (e) { ru = null; }
  return WT.rows.map(r => {
    const p = +r.pop || 0, a = +r.area || 0, f = r.char ? (WARD_GROWTH[r.char] || [])[2] : ru;
    return p > 0 && a > 0 && f ? { r, d0: p / a, d: p / a * f } : null;
  }).filter(x => x && x.d > s);
}
// the saturation's cells of the growth table and its warning, in place (the next box clicked keeps its cursor)
function wtSatShow() {
  if (!$("wtsatwarn")) return;
  const s = +WT.sat || 0;
  const o = wtSatOver(), L = o.map(x => `${x.r.name || x.r.no} ${fmt(x.d0)} → ${fmt(x.d)}`).join(", ");
  // each value in a box (user 9-Nov-2026), red past the limit: the value itself above the saturation density (the
  // character's +30 factor below 1 - its population falling) or a ward of the character denser than it today
  document.querySelectorAll("#wtgrowth td[data-sx]").forEach(td => {
    const k = td.dataset.sx, f = (WARD_GROWTH[k] || [])[2];
    if (!(s > 0 && f)) { td.textContent = "-"; return; }
    const v = s / f, ws = o.filter(x => x.r.char === k), why = [];
    if (v > s) why.push(tr(`${fmt(v)} saturation ${fmt(s)} से ऊपर: +30 गुणक ${(+f).toFixed(4)} 1 से कम - इस चरित्र की आबादी design वर्ष में घट रही है`,
                           `${fmt(v)} above the saturation ${fmt(s)}: the +30 factor ${(+f).toFixed(4)} below 1 - this character's population falls by the design year`));
    if (ws.length) why.push(tr(`आज इससे घने वार्ड: ${ws.map(x => `${x.r.name || x.r.no} ${fmt(x.d0)}`).join(", ")} - design वर्ष में saturation पार`,
                               `wards denser than it today: ${ws.map(x => `${x.r.name || x.r.no} ${fmt(x.d0)}`).join(", ")} - past saturation in the design year`));
    const red = why.length > 0;
    td.innerHTML = `<span class="satbox${red ? " satred" : ""}" title="${esc(why.join("; ") || tr("सीमा में", "within the limit"))}">${fmt(v)}</span>`;
  });
  // CPHEEO's limits as warnings (8-Nov-2026): the core near saturation, the town's total, near-core growing faster
  const G = WARD_GROWTH, w = [], inf = [];
  if (G[CH[0]][2] > WARD_CORE_NEAR)
    w.push(tr(`${CH[0]} का +30 गुणक ${G[CH[0]][2]}: विकसित core की density लगभग saturation पर है (जब तक FSI न बढ़े) - गुणक 1 के पास रखें (CPHEEO Annexure 2.7 p974; ${WARD_CORE_NEAR} से ऊपर चेतावनी)`,
              `${CH[0]}'s +30 factor ${G[CH[0]][2]}: the developed core's density is practically at saturation (unless the FSI is raised) - keep the factor close to 1 (CPHEEO Annexure 2.7 p974; warned above ${WARD_CORE_NEAR})`));
  if (Object.keys(WARD_TOWN_DEF).some(k => WT.city[k] === "" || WT.city[k] == null))
    w.push(tr("पूरे शहर की चरित्र-वार आबादी अधूरी - Far-open balance नहीं, वार्डों का जोड़ शहर की projection से नहीं मिलेगा (CPHEEO Annexure 2.7 p976)",
              "the whole town's population by character incomplete - Far-open not balanced, the wards will not add up to the town's projection (CPHEEO Annexure 2.7 p976)"));
  if (G[CH[3]][2] > G[CH[2]][2])
    inf.push(tr(`${CH[3]} (+30 × ${(+G[CH[3]][2]).toFixed(2)}) ${CH[2]} (× ${G[CH[2]][2]}) से तेज़: CPHEEO (Annexure 2.7 p974) के अनुसार core के पास वाले वार्ड दूर वालों से तेज़ बढ़ते हैं - जाँचें कि बाहरी वार्डों में सचमुच नई बसावट / ज़मीन के बढ़ते दाम हैं, और barrier (नदी, रेल) के पार वाले धीमे रखें`,
                `${CH[3]} (+30 x ${(+G[CH[3]][2]).toFixed(2)}) faster than ${CH[2]} (x ${G[CH[2]][2]}): by CPHEEO (Annexure 2.7 p974) the wards near the core grow faster than those away - check that the outer wards really have new layouts / rising land prices, and keep those beyond a barrier (river, railway) slower`));
  if ($("wtcph")) $("wtcph").innerHTML = w.map(x => `<div class="wflag warn">⚠ ${esc(x)}</div>`).join("") +
    inf.map(x => `<div class="wflag">ℹ ${esc(x)}</div>`).join("") +
    `<div class="hint">${tr("CPHEEO Annexure 2.7 p976: वार्ड-वार भविष्य की आबादी / density नगर निकाय से स्वीकृत कराएँ, उसके बाद ही design।", "CPHEEO Annexure 2.7 p976: get the ward-wise future population / density approved by the local body, only then the design.")}</div>`;
  $("wtsatwarn").innerHTML = o.length ? `<div class="wflag warn">⚠ ${esc(tr(`Design वर्ष में saturation density ${fmt(s)} /ha से ऊपर: ${L} - इनके चरित्र के गुणक घटाएँ या क्षेत्रफल जाँचें (CPHEEO Annexure 2.7)`,
    `above the saturation density ${fmt(s)} /ha in the design year: ${L} - lower their character's factors or check the area (CPHEEO Annexure 2.7)`))}</div>` : "";
}
// the character by the density (WT.dens) of a row the user has not chosen one for (charby "user"); "" without pop / area
function wtDensChar(r) {
  const p = +r.pop || 0, a = +r.area || 0;
  if (!(p > 0 && a > 0)) return "";
  const d = p / a, D = WT.dens || WARD_DENS_DEF;
  for (const k of CH.slice(0, 3)) if (d > +D[k]) return k;
  return CH[3];
}
function wtAuto(r) { if (r.charby !== "user" && r.charby !== "city") r.char = wtDensChar(r); }
function wardChar(p) { const r = wtRow(p.ward_no); return r ? r.char || "" : charName(p.character); }
function wtSyncGrowth() {
  for (const k in WARD_GROWTH_DEF) WARD_GROWTH[k] = (WT.growth && WT.growth[k]) || WARD_GROWTH_DEF[k].slice();
  const fo = pjFar(); if (fo) WARD_GROWTH[CH[3]] = fo.factors.slice();
}
function wtCell(c, r, i) {
  if (c[3] === "char") return `<select data-i="${i}" data-k="char" style="width:${c[2]}px" title="${r.charby === "user" ? tr("आपका चुना", "chosen by you") : tr("density से अपने-आप", "by the density, by itself")}">${WARD_CHARS.map(x => `<option value="${x[0]}"${(r.char || "") === x[0] ? " selected" : ""}>${x[0] ? x[0] : "—"}</option>`).join("")}</select>`;
  if (c[3] === "ro") return `<span class="hint">${r[c[0]] === "" || r[c[0]] == null ? "-" : esc(r[c[0]]) + " %"}</span>`;
  // the name: with the town's list, a click / typing searches it (datalist), the ward chosen fills the row
  const ls = c[0] === "name" && CW ? ` list="cwl" title="${tr("click करके / लिखकर शहर की सूची में खोजें", "click / type to search the town's list")}"` : "";
  return `<input data-i="${i}" data-k="${c[0]}" type="${c[3]}" value="${esc(r[c[0]] ?? "")}" style="width:${c[2]}px"${ls}>`;
}
function wtRender() {
  wtSyncGrowth();
  if (!WT.rows.length) { $("wttable").innerHTML = ""; $("wtgrowth").innerHTML = ""; return; }
  WT.rows.forEach(wtAuto);
  const drawnNo = new Set(); drawn.eachLayer(l => { if (l.kind === "ward" && l.props.ward_no) drawnNo.add(String(l.props.ward_no).trim()); });
  const dupRows = new Set(CW ? cwDups().flat() : []);
  $("wttable").innerHTML = `<div style="overflow-x:auto"><table class="wz"><tr>${WT_COLS.map(c => `<th${WT_TIPS[c[0]] ? ` title="${WT_TIPS[c[0]]()}"` : ""}>${c[1]()}</th>`).join("")}<th title="${tr("आबादी x % covered", "population x % covered")}">${tr("Project में", "In project")}</th><th title="${tr("नक्शे पर इसी Ward No. की सीमा", "a boundary with this Ward No. on the map")}">${tr("नक्शा", "Map")}</th>` +
    (CW ? `<th title="${tr("शहर की सूची का वार्ड जिससे यह पंक्ति भरी (✔ नंबर + नाम / नाम से, ⚠ सिर्फ़ नंबर से - नाम अलग, जाँचें); बदलने के लिए नाम पर click करके खोजें", "the town's list's ward this row is filled from (✔ number + name / by name, ⚠ by number only - the names differ, check); to change it click the name and search")}">${tr("शहर की सूची", "Town's list")}</th>` : "") + `</tr>` +
    WT.rows.map((r, i) => `<tr>${WT_COLS.map(c => `<td>${wtCell(c, r, i)}</td>`).join("")}` +
      `<td id="wtc${i}">${fmt(wtCov(r))}</td><td>${drawnNo.has(String(r.no).trim()) ? "✔" : "-"}</td>${CW ? `<td>${cwCell(r, dupRows.has(r))}</td>` : ""}</tr>`).join("") +
    `<tr><td colspan="${WT_COLS.length}"><b>${tr("कुल", "Total")} (<span id="wtyr">${WT.year}</span>)</b></td><td><b id="wtsum">${fmt(wtTotal())}</b></td><td></td>${CW ? "<td></td>" : ""}</tr></table></div>` +
    `<div id="wtwarn"></div><div class="hint">${tr("नक्शे पर वार्ड की सीमा में यही Ward No. भरें: उसकी आबादी उसी के junctions पर; जिसकी सीमा नहीं (-) उसकी आबादी वार्डों से बाहर के junctions पर, pipe लंबाई से। नीचे census भरकर Projection निकालें: इसी वर्ष की आबादी से पाँचों विधियाँ; चरित्र वाले वार्ड उसके गुणक से।",
                            "Give the same Ward No. to the ward's boundary on the map: its population on its junctions; a ward with no boundary (-): on the junctions in no ward, by pipe length. Fill in the census below and run the projection: the five methods from this year's population; a ward with a character by its factors.")}</div>`;
  document.querySelectorAll("#wttable input, #wttable select").forEach(inp => inp.onchange = () => {
    const i = +inp.dataset.i;
    const r = WT.rows[i], k = inp.dataset.k;
    r[k] = inp.value.trim();
    if (k === "name" && CW) {                   // a ward picked from the town's list: "name [no]"
      const m = /^(.*) \[([^\]]+)\]$/.exec(r.name), w = m && CW.rows.find(x => String(x.no) === m[2] && x.name === m[1]);
      if (w) { r.name = w.name; cwFill(r, w, "user"); cwTotals(); wtRender(); wtChanged(); cwStatus(); return; }
    }
    if (k === "char") r.charby = "user";
    else if ((k === "pop" || k === "area") && r.charby !== "user") {     // the character follows the density
      wtAuto(r); const s = document.querySelector(`#wttable select[data-i="${i}"]`); if (s) s.value = r.char || "";
    }
    $("wtc" + i).textContent = fmt(wtCov(r)); $("wtsum").textContent = fmt(wtTotal());   // not re-drawn
    if (k === "char" || k === "pop" || k === "area") wtGrowthRender();
    wtWarn(); wtChanged(); });
  wtWarn(); wtGrowthRender();
}
// a ward the KML has partly outside the zone, its % covered left empty (= 100 %)
function wtWarn() {
  const open = WT.rows.filter(r => (r.cov === "" || r.cov == null) && r.kcov !== "" && r.kcov != null && +r.kcov < 99.5);
  const L = open.map(r => `${r.name || r.no} ${r.kcov} %`).join(", ");
  $("wtwarn").innerHTML = open.length ? `<div class="wflag warn">⚠ ${esc(tr(`% covered खाली (= 100 %) पर KML में zone के भीतर कम: ${L} - आबादी के हिसाब से % भरें`,
                                                                          `% covered empty (= 100 %) but the KML has less in the zone: ${L} - fill in the % by population`))}</div>` : "";
}
// "Factors to the projection" (user decision 10-Nov-2026): the four characters' growth (factor − 1) in the example's
// proportion (WARD_GROWTH_DEF: Riverside DPR p76, Far-open the example's balance, technical.xlsx T), one multiplier
// a stage, so the whole town's wards (WT.city) add up to the adopted projection: m = S (R − 1) / Σ P g; Far-open's
// balance then gives back its own 1 + m g -> {character: [init, mid, ult]} or the reason not (text)
function wtFitR() { try { return (PJ && PJ.town_ratio_from) || null; } catch (e) { return null; } }
function wtFit() {
  const R = wtFitR(), ks = Object.keys(WARD_TOWN_DEF);
  if (!R) return tr("पहले census भरकर projection निकालें", "run the projection with the census first");
  if (ks.some(k => WT.city[k] === "" || WT.city[k] == null || !(+WT.city[k] >= 0)))
    return tr("पूरे शहर की चरित्र-वार आबादी चारों भरें", "fill in the whole town's population of all four characters");
  const S = ks.reduce((a, k) => a + +WT.city[k], 0), out = {};
  ks.forEach(k => { out[k] = []; });
  for (const [j, t] of ["init", "mid", "ult"].entries()) {
    const den = ks.reduce((a, k) => a + +WT.city[k] * (WARD_GROWTH_DEF[k][j] - 1), 0);
    if (!(den > 0)) return tr("शहर की आबादी 0", "the town's population 0");
    const m = S * (R[t] - 1) / den;
    for (const k of ks) out[k].push(Math.round((1 + m * (WARD_GROWTH_DEF[k][j] - 1)) * 1e4) / 1e4);
  }
  if (ks.some(k => out[k].some(x => !(x > 0)))) return tr("शहर की projection आज से बहुत कम - गुणक 0 से नीचे, हाथ से भरें", "the town's projection far below today's - the factors below 0, fill them in by hand");
  return out;
}
function wtBelow(fo) { return ["init", "mid", "ult"].map((t, j) => fo.below.includes(t) ? `${[tr("आधार", "base"), "+15", "+30"][j]} = ${fo.factors[j].toFixed(4)}` : "").filter(Boolean).join(", "); }
// the factors of each character (Riverside DPR p76; example technical.xlsx 'T'): yellow, on the population of the
// table's year (= 1); shown with the table
function wtGrowthRender() {
  const used = new Set(WT.rows.map(r => r.char).filter(Boolean)), fo = pjFar();
  let err = ""; try { err = (PJ && PJ.far_open_error) || ""; } catch (e) { err = ""; }
  wtSyncGrowth();
  const fcell = (k, j) => fo && k === CH[3]
    ? `<td title="${tr("चुनी विधि से balance - अपने-आप", "balanced to the adopted method - by itself")}"><b>${fo.factors[j].toFixed(4)}</b></td>`
    : `<td><input data-g="${k}" data-j="${j}" type="number" step="0.0001" min="0.01" value="${WT.growth[k][j]}" style="width:66px;background:#fff9c4"></td>`;
  const tot = Object.keys(WARD_TOWN_DEF).reduce((a, k) => a + (+WT.city[k] || 0), 0);
  $("wtgrowth").innerHTML = `<details${used.size ? " open" : ""}><summary>${tr("वार्ड के चरित्र के गुणक", "Factors of the ward's character")} (${WT.year || ""} = 1; Riverside DPR p76)</summary>` +
    `<table class="wz"><tr><th>${tr("चरित्र", "Character")}</th><th title="${tr("वार्ड की density (आबादी ÷ ha) इससे ज़्यादा हो तो यह चरित्र; example technical.xlsx T", "the ward's density (population / ha) above this: this character; example technical.xlsx T")}">${tr("density >", "density >")} (/ha)</th><th>${tr("आधार वर्ष", "Base year")}</th><th>+15</th><th>+30</th><th title="${tr("इस चरित्र का जो वार्ड आज इस density (/ha) से घना है, वह Design वर्ष में saturation density पार करेगा = saturation ÷ +30 गुणक", "a ward of this character denser than this (/ha) today passes the saturation density in the design year = saturation / the +30 factor")}">${tr("saturation पार: density >", "passes saturation: density >")}</th><th>${tr("वार्ड", "Wards")}</th><th title="${tr("पूरे शहर के सब वार्डों की इस वर्ष की आबादी, चरित्र-वार - Far-open का गुणक इन्हीं से balance होता है (default: स्प्रिंगफ़ील्ड, example technical.xlsx T)", "the whole town's wards' population of this year by character - Far-open's factor balances them (default: Springfield, example technical.xlsx T)")}">${tr("पूरे शहर में आबादी", "Whole town's population")} ${WT.year || ""}</th></tr>` +
    Object.keys(WARD_GROWTH_DEF).map(k => `<tr><td>${k}</td><td>${k === CH[3] ? tr("बाकी", "the rest") : `<input data-d="${k}" type="number" step="1" min="0" value="${WT.dens[k]}" style="width:60px;background:#fff9c4">`}</td>` +
      `${[0, 1, 2].map(j => fcell(k, j)).join("")}<td data-sx="${k}">-</td>` +
      `<td>${WT.rows.filter(r => r.char === k).length || "-"}</td>` +
      `<td><input data-c="${k}" type="number" step="1" min="0" value="${WT.city[k] ?? ""}" style="width:90px;background:#fff9c4"></td></tr>`).join("") +
    (fo ? `<tr><td colspan="2"><b>${tr("शहर, चुनी विधि से", "The town, adopted method")}</b></td>${["init", "mid", "ult"].map(t => `<td>${fmt(fo.target[t])}</td>`).join("")}<td></td><td></td><td><b>${fmt(tot)}</b></td></tr>` : "") +
    `</table><div class="row"><button id="wtdensall" title="${tr("आपके बदले चरित्र भी density से फिर भरें", "fill the characters you changed too by the density again")}">↺ ${tr("सब चरित्र density से", "All characters by the density")}</button>` +
    (wtFitR() ? `<button id="wtfit" title="${tr("चारों चरित्रों की बढ़त (गुणक − 1) example (Riverside DPR p76, technical.xlsx T) के अनुपात में, हर stage पर एक गुणांक से - ताकि शहर के सब वार्डों का जोड़ चुनी विधि की projection के बराबर हो; geometrical जैसी तेज़ विधि पर example के गुणक, धीमी पर सब कम। पीले गुणक बदलते हैं (पहले पूछकर)",
      "the four characters' growth (factor − 1) in the example's proportion (Riverside DPR p76, technical.xlsx T), one multiplier a stage - so the town's wards add up to the adopted projection; a fast method like the geometrical: the example's factors, a slower one: all lower. Changes the yellow factors (asked first)")}">⇅ ${tr("गुणक projection से मिलाएँ", "Factors to the projection")}</button>` : "") + `</div>` +
    `<div class="row"><span title="${tr("CPHEEO Water Manual Part A, Annexure 2.7: विकसित core की density लगभग saturation पर है - saturation density उसकी आज की density के बहुत पास रखें; कोई वार्ड भविष्य में इससे घना नहीं। Default: स्प्रिंगफ़ील्ड का सबसे घना वार्ड 1,710 x 1.10 (example technical.xlsx T); दूसरे शहर में उसका। खाली = जाँच नहीं", "CPHEEO Water Manual Part A, Annexure 2.7: the developed core's density is practically at saturation - keep the saturation density very close to its present density; no ward denser than it in future. Default: Springfield's densest ward 1,710 x 1.10 (example technical.xlsx T); another town: its own. Empty = no check")}">${tr("Saturation density (/ha)", "Saturation density (/ha)")}</span>` +
    `<input id="wtsat" type="number" step="1" min="0" value="${WT.sat ?? ""}" style="width:70px;background:#fff9c4"><span class="hint">${tr("ऊपर जाने वाले वार्ड सिर्फ़ चेताए जाते हैं", "a ward above it is only warned of")}</span></div><div id="wtsatwarn"></div><div id="wtcph"></div>` +
    `<details><summary>${tr("CPHEEO के निर्देश (Manual on Water Supply 2024, Part A)", "CPHEEO's directions (Manual on Water Supply 2024, Part A)")}</summary><table class="wz">` +
    CPHEEO_WARD.map(c => `<tr><td style="white-space:nowrap"><b>${c[0]}</b></td><td>${tr(c[1], c[2])}</td></tr>`).join("") +
    `</table><div class="hint">${tr("ध्यान दें: density की सीमाएँ 585 / 310 / 170, चरित्रों के गुणक और saturation का default 1,880 CPHEEO के नहीं हैं - example (technical.xlsx T, Riverside DPR p76) के हैं; CPHEEO तरीका और सिद्धांत देता है, संख्याएँ शहर के हिसाब से तय करें।",
      "Note: the density limits 585 / 310 / 170, the characters' factors and the saturation's default 1,880 are not CPHEEO's - they are the example's (technical.xlsx T, Riverside DPR p76); CPHEEO gives the method and principles, the numbers are the town's.")}</div></details>` + (err ? `<div class="wflag warn">⚠ ${esc(err)} - ${tr("पीले Far-open गुणक लगे; \"गुणक projection से मिलाएँ\" दबाएँ", "the yellow Far-open factors used; press \"Factors to the projection\"")}</div>` : "") +
    (fo && fo.below && fo.below.length ? `<div class="wflag warn">⚠ ${tr(`Far-open का गुणक 1 से कम (${wtBelow(fo)}): उसके वार्डों की आबादी घटती दिखती है - बाकी चरित्रों के गुणक इस शहर की projection के लिए ज़्यादा; "गुणक projection से मिलाएँ" दबाएँ`,
      `Far-open's factor below 1 (${wtBelow(fo)}): its wards' population falls - the other characters' factors too high for this town's projection; press "Factors to the projection"`)}</div>`
    : fo && fo.low ? `<div class="wflag warn">⚠ ${tr("Far-open किसी घने चरित्र से धीमा बढ़ रहा है - इस शहर की बढ़त के लिए बाकी चरित्रों के गुणक ज़्यादा लगते हैं", "Far-open grows slower than a denser character - the other characters' factors seem high for this town's growth")}</div>` : "") +
    `<div class="hint">${fo
      ? tr("Far-open = (चुनी विधि से शहर − बाकी तीन चरित्रों की आबादी × उनके गुणक) ÷ Far-open की आबादी (example T P470): विधि बदलें तो यह बदलता है, ताकि शहर के सब वार्डों का जोड़ projection के बराबर रहे। पीले: बदले जा सकते हैं; शहर की आबादी default स्प्रिंगफ़ील्ड की (दूसरे शहर में उसकी भरें)।",
           "Far-open = (the town by the adopted method − the other three characters x their factors) / Far-open's population (example T P470): it changes with the method, so the town's wards add up to the projection. Yellow: can be changed; the town's population by default Springfield's (another town: its own).")
      : tr("पीले: बदले जा सकते हैं। Far-open: census भरकर projection निकालें तो चुनी विधि से अपने-आप balance; तब तक example वाला (1.0932 / 1.9183 / 3.3282)।",
           "Yellow: can be changed. Far-open: with the census and the projection, balanced to the adopted method by itself; till then the example's (1.0932 / 1.9183 / 3.3282).")}</div></details>`;
  document.querySelectorAll("#wtgrowth input[data-d]").forEach(inp => inp.onchange = () => {
    const v = +inp.value;
    if (v >= 0 && inp.value !== "") WT.dens[inp.dataset.d] = v; else inp.value = WT.dens[inp.dataset.d];
    wtRender(); wtChanged(); });
  $("wtdensall").onclick = () => { WT.rows.forEach(r => { delete r.charby; }); wtRender(); wtChanged(); };
  if ($("wtfit")) $("wtfit").onclick = () => {
    const F = wtFit();
    if (typeof F === "string") { alert(F); return; }
    const L = Object.keys(F).map(k => `${k}: ${F[k].map(x => x.toFixed(4)).join(" / ")}`).join("\n");
    if (!confirm(tr(`गुणक (आधार / +15 / +30) ये हो जाएँ? (Far-open फिर balance से)\n\n${L}`, `Set the factors (base / +15 / +30) to these? (Far-open then by the balance)\n\n${L}`))) return;
    for (const k of CH) WT.growth[k] = F[k].slice();
    wtSyncGrowth(); wtGrowthRender(); wtChanged(); };
  $("wtsat").onchange = () => {
    const v = $("wtsat").value.trim();
    if (v === "") WT.sat = ""; else if (+v > 0) WT.sat = +v; else $("wtsat").value = WT.sat ?? "";
    wtSatShow(); wtChanged(); };
  document.querySelectorAll("#wtgrowth input[data-c]").forEach(inp => inp.onchange = () => {
    const v = +inp.value;
    if (v >= 0 && inp.value !== "") WT.city[inp.dataset.c] = v; else inp.value = WT.city[inp.dataset.c] ?? "";
    wtSatShow(); wtChanged(); });
  document.querySelectorAll("#wtgrowth input[data-g]").forEach(inp => inp.onchange = () => {
    const v = +inp.value;
    if (v > 0) WT.growth[inp.dataset.g][+inp.dataset.j] = v; else inp.value = WT.growth[inp.dataset.g][+inp.dataset.j];
    wtSyncGrowth(); wtSatShow(); wtChanged(); });
  wtSatShow();
}
// the ward table from a KML of the ward boundaries (user decision 7-Nov-2026; wards.ward_kml_table): the rows
// (replacing the table's, asked), the wards on the map with their Ward No. (replacing the wards drawn, asked)
$("wtkml").onclick = () => $("wtkmlfile").click();
$("wtkmlfile").onchange = async e => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  loading(true, tr(`${f.name} पढ़ रहे हैं …`, `Reading ${f.name} …`));
  try {
    const r = await api("/api/ward_kml_table", { kml: await kmlText(f) });
    if (!r.ok) { $("wtkmlst").textContent = tr("KML नहीं पढ़ी: ", "KML not read: ") + (r.log || ""); return; }
    if (WT.rows.length && !confirm(tr(`तालिका के ${WT.rows.length} वार्ड इस KML के ${r.rows.length} वार्डों से बदलें?`,
                                      `Replace the table's ${WT.rows.length} wards with this KML's ${r.rows.length}?`))) return;
    WT.rows = r.rows.map(x => Object.assign({}, x, { pop: String(x.pop ?? ""), hh: String(x.hh ?? ""), area: String(x.area ?? "") }));
    $("wtn").value = WT.rows.length;
    if (CW) cwAutoAll();                     // the town's list: its population, HH, Eq. area, census, character
    const old = []; drawn.eachLayer(l => { if (l.kind === "ward") old.push(l); });
    if (!old.length || confirm(tr(`नक्शे के ${old.length} वार्ड इस KML की सीमाओं (Ward No. के साथ) से बदलें? (Cancel = नक्शा वैसा ही)`,
                                  `Replace the ${old.length} wards on the map with this KML's boundaries (with their Ward No.)? (Cancel = the map as it is)`))) {
      old.forEach(l => drawn.removeLayer(l));
      for (const w of r.wards) addFeature(L.polygon(w.latlngs), "ward", { name: w.name, ward_no: w.no, population: "", character: "" });
      changed();
    }
    wtRender(); wtChanged(); popUi(); cwStatus();
    $("wtkmlst").textContent = tr(`${f.name}: ${r.rows.length} वार्ड`, `${f.name}: ${r.rows.length} wards`) +
      (r.zone ? `; zone ${r.zone.name} ${fmt(r.zone.area_ha)} ha` : "") + (r.notes.length ? " - " + r.notes.map(n => EN ? n[1] : n[0]).join("; ") : "");
  } catch (err) { $("wtkmlst").textContent = tr("KML नहीं पढ़ी: ", "KML not read: ") + err.message; }
  finally { loading(false); }
};
// ---- the town's wards (user decisions 9-Nov-2026; city_wards.py): an xlsx of all the town's wards exported /
// imported, kept by town in the master folder; the table's wards matched to it - by Ward No. and name, by the name
// alone, else by the number alone (marked ⚠: the KML's numbers may be of an older delimitation) - and filled from
// it (the xlsx's over the KML's, a difference warned of); the area its Eq. area (the density on it, CPHEEO
// 2.8.1.24); the whole town's population by character its sums. A name clicked searches the list (datalist).
var CW_DIFF = [];                          // the KML's population replaced by a different one of the list
function cwKey(s) { return String(s || "").toLowerCase().replace(/[^a-z0-9ऀ-ॿ]/g, ""); }
function cwNo(s) { const t = String(s ?? "").trim(); return /^\d+$/.test(t) ? String(+t) : t.toLowerCase(); }
function cwChar(w) { return w.char || wtDensChar({ pop: w.pop, area: w.area }); }
function cwFind(r) {
  const byNo = CW.rows.filter(w => cwNo(w.no) === cwNo(r.no)), byName = CW.rows.filter(w => cwKey(w.name) === cwKey(r.name));
  const both = byNo.find(w => cwKey(w.name) === cwKey(r.name));
  if (both) return [both, "both"];
  if (byName.length === 1) return [byName[0], "name"];
  if (byNo.length === 1) return [byNo[0], "no"];
  return null;
}
function cwFill(r, w, how) {
  const p0 = +String(r.pop || "").replace(/,/g, "") || 0;
  if (how !== "user" && p0 > 0 && w.pop != null && Math.abs(p0 - w.pop) > 0.01 * w.pop) CW_DIFF.push(`${r.name || r.no} ${fmt(p0)} → ${fmt(w.pop)}`);
  r.cw = String(w.no); r.cwname = w.name; r.cwhow = how;
  for (const k of ["pop", "hh", "census", "area"]) if (w[k] != null && w[k] !== "") r[k] = String(w[k]);
  if (!r.name) r.name = w.name;
  if (w.char) { r.char = w.char; r.charby = "city"; } else { delete r.charby; wtAuto(r); }
}
function cwAutoAll() {
  CW_DIFF = [];
  for (const r of WT.rows) {
    const own = r.cw ? CW.rows.find(w => String(w.no) === r.cw && w.name === r.cwname) : null;
    const f = own ? [own, r.cwhow || "user"] : cwFind(r);
    if (f) cwFill(r, f[0], f[1]); else { delete r.cw; delete r.cwname; delete r.cwhow; }
  }
  cwTotals();
}
// the whole town's population of the table's year by character: the list's sums (a ward without a character by its
// density on the Eq. area; one with neither not counted - warned)
function cwTotals() {
  if (!CW) return;
  const s = {}; for (const k in WARD_TOWN_DEF) s[k] = 0;
  for (const w of CW.rows) { const c = cwChar(w); if (c && w.pop) s[c] += +w.pop; }
  WT.city = s;
}
// the town's list's wards linked from more than one row of the table (user decision 10-Nov-2026): their population
// counted twice - "no|name" -> the rows
function cwDups() {
  const m = new Map();
  for (const r of WT.rows) if (r.cw) { const k = `${r.cw}|${r.cwname || ""}`; m.set(k, (m.get(k) || []).concat([r])); }
  return [...m.values()].filter(x => x.length > 1);
}
function cwCell(r, dup) {
  if (!r.cw) return `<span class="wflag warn" style="padding:0 4px">${tr("नहीं मिला - नाम पर click करके खोजें", "not found - click the name to search")}</span>`;
  const t = `${esc(r.cw)} ${esc(r.cwname || "")}`;
  if (dup) return `<span class="wflag warn" style="padding:0 4px" title="${tr("सूची का यही वार्ड तालिका की दूसरी पंक्ति से भी जुड़ा है - आबादी दो बार गिनी जाएगी; ग़लत पंक्ति में नाम पर click करके सही वार्ड चुनें", "this ward of the list is linked from another row of the table too - its population counted twice; in the wrong row click the name and pick the right ward")}">⚠ ${t} ×2</span>`;
  return r.cwhow === "no" ? `<span class="wflag warn" style="padding:0 4px" title="${tr("सिर्फ़ Ward No. मिला, नाम अलग - सही वार्ड है तो ठीक, नहीं तो नाम पर click करके खोजें", "only the Ward No. matched, the name differs - fine if it is the right ward, else click the name to search")}">⚠ ${t}</span>` : `✔ ${t}`;
}
function cwStatus() {
  if (!CW) { $("cwst").innerHTML = ""; return; }
  const n = CW.rows.length, none = CW.rows.filter(w => !cwChar(w)).length, linked = WT.rows.filter(r => r.cw).length;
  const m = [tr(`${esc(CW.city)}: ${n} वार्ड${CW.year ? ` (${CW.year})` : ""}, ${CW.file ? esc(CW.file) + ", " : ""}import ${esc(CW.imported || "")}; तालिका के ${linked} / ${WT.rows.length} वार्ड इससे भरे; "पूरे शहर में आबादी" चरित्र-वार इसी के जोड़`,
                `${esc(CW.city)}: ${n} wards${CW.year ? ` (${CW.year})` : ""}, ${CW.file ? esc(CW.file) + ", " : ""}imported ${esc(CW.imported || "")}; ${linked} / ${WT.rows.length} of the table's wards filled from it; "whole town's population" by character its sums`)];
  const nc = (CW.census || []).length, dn = Object.keys(CW.dens || {}).length;
  if (nc || dn) m.push(tr(`<div>सूची में${dn ? " चरित्र की density सीमाएँ" : ""}${dn && nc ? " और" : ""}${nc ? ` पूरे शहर की census (${nc} दशक)` : ""} - चुनते / import करते समय नीचे भरी गईं</div>`,
                          `<div>The list has${dn ? " the character's density limits" : ""}${dn && nc ? " and" : ""}${nc ? ` the whole town's census (${nc} decades)` : ""} - filled in below when chosen / imported</div>`));
  const w = [];
  if (CW.year && WT.year && +CW.year !== +WT.year) w.push(tr(`सूची की आबादी ${CW.year} की, तालिका का वर्ष ${WT.year} - वर्ष मिलाएँ`, `the list's population is of ${CW.year}, the table's year ${WT.year} - make them one`));
  if (none) w.push(tr(`${none} वार्डों का न चरित्र न Eq. area - शहर के चरित्र-वार जोड़ में नहीं गिने`, `${none} ward(s) with neither a character nor an Eq. area - not in the town's sums by character`));
  const D = cwDups().map(g => `${g[0].cw} ${g[0].cwname || ""} ← ${g.map(r => `${r.no} ${r.name || ""}`.trim()).join(", ")}`);
  if (D.length) w.push(tr(`सूची का एक ही वार्ड तालिका की कई पंक्तियों से जुड़ा: ${D.join("; ")} - उसकी आबादी दो बार गिनी जाएगी; ग़लत पंक्ति में नाम पर click करके सही वार्ड चुनें`,
                          `one ward of the list linked from several rows of the table: ${D.join("; ")} - its population counted twice; in the wrong row click the name and pick the right ward`));
  if (CW_DIFF.length) w.push(tr(`KML की आबादी सूची से अलग, सूची की ली: ${CW_DIFF.join(", ")}`, `the KML's population differs from the list's, the list's taken: ${CW_DIFF.join(", ")}`));
  $("cwst").innerHTML = m.map(x => x.startsWith("<div>") ? x : `<div>${x}</div>`).join("") + w.map(x => `<div class="wflag warn">⚠ ${esc(x)}</div>`).join("");
}
function cwOptions() {
  $("cwl").innerHTML = CW ? CW.rows.map(w => `<option value="${esc(w.name)} [${esc(w.no)}]">${esc(w.no)} · ${w.pop != null ? fmt(w.pop) : "-"} · ${esc(cwChar(w) || "-")}</option>`).join("") : "";
}
async function cwList(sel) {
  try {
    const r = await api("/api/city_wards_list"); if (!r.ok) return;
    $("cwsel").innerHTML = `<option value="">${tr("— कोई नहीं —", "— none —")}</option>` +
      r.cities.map(c => `<option value="${esc(c.city)}">${esc(c.city)} (${c.n}${c.year ? ", " + c.year : ""})</option>`).join("");
    $("cwsel").value = sel || "";
  } catch (e) { /* page opened without the server */ }
}
// the list of a town (fill: the table's wards from it, else only for the search / sums - a saved project restored)
async function cwLoad(city, fill) {
  CW = null;
  if (city) { const r = await api("/api/city_wards?city=" + encodeURIComponent(city)); if (r.ok) CW = r; }
  WT.citylist = CW ? CW.city : "";
  if (CW && fill) {                        // the list's criteria of the character and the town's census (9-Nov-2026)
    if (CW.dens && Object.keys(CW.dens).length) WT.dens = Object.assign({}, WARD_DENS_DEF, CW.dens);
    if (CW.census && CW.census.length) pjcSet(CW.census.map(x => `${x[0]} ${x[1]}`).join(", "));
  }
  cwOptions();
  if (CW && fill) cwAutoAll(); else cwTotals();
  wtRender(); cwStatus();
  if (fill) wtChanged();
}
$("cwsel").onchange = () => cwLoad($("cwsel").value, true);
$("cwexp").onclick = async () => {
  loading(true, tr("xlsx बना रहे हैं …", "Making the xlsx …"));
  try {
    const r = await api("/api/city_wards_xlsx", { city: CW ? CW.city : "", year: WT.year, rows: CW ? null : WT.rows,
      dens: WT.dens, census: PJC.filter(x => String(x.y).trim()).map(x => [x.y, x.p]) });
    if (!r.ok) { $("cwst").textContent = r.log || ""; return; }
    const bin = atob(r.b64), u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([u8], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
    a.download = r.file; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    $("cwst").textContent = tr(`xlsx: ${r.path || r.file} - पूरे शहर के वार्ड भरकर "Import xlsx…" से import करें`, `xlsx: ${r.path || r.file} - fill in the whole town's wards and import it with "Import xlsx…"`);
  } catch (err) { $("cwst").textContent = err.message; }
  finally { loading(false); }
};
$("cwimp").onclick = () => $("cwfile").click();
$("cwfile").onchange = async e => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  loading(true, tr(`${f.name} पढ़ रहे हैं …`, `Reading ${f.name} …`));
  try {
    const u8 = new Uint8Array(await f.arrayBuffer());
    let bin = ""; for (let i = 0; i < u8.length; i += 0x8000) bin += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    const r = await api("/api/city_wards_import", { file: f.name, b64: btoa(bin) });
    if (!r.ok) { $("cwst").textContent = tr("xlsx नहीं पढ़ी: ", "xlsx not read: ") + (r.log || ""); return; }
    await cwList(r.city);
    await cwLoad(r.city, true);
    if (r.notes && r.notes.length) $("cwst").innerHTML += r.notes.map(n => `<div class="wflag warn">⚠ ${esc(EN ? n[1] : n[0])}</div>`).join("");
  } catch (err) { $("cwst").textContent = tr("xlsx नहीं पढ़ी: ", "xlsx not read: ") + err.message; }
  finally { loading(false); }
};
cwList("");
// ---- the census of the town (user 7-Nov-2026): a row of year and population for each decade (1951-2011 to begin),
// "+ decade" adds one; its pairs go to #pjcensus (hidden) as before. A change does not re-draw the rows.
var PJC = [];
function pjcFromText(s) {
  const nums = String(s || "").replace(/,/g, " ").split(/\s+/).filter(Boolean);
  const out = [];
  for (let i = 0; i + 1 < nums.length; i += 2) out.push({ y: nums[i], p: nums[i + 1] });
  return out;
}
function pjcText() { return PJC.filter(r => String(r.y).trim() && String(r.p).trim()).map(r => `${r.y} ${r.p}`).join(", "); }
function pjcRender() {
  if (!PJC.length) PJC = [1951, 1961, 1971, 1981, 1991, 2001, 2011].map(y => ({ y: String(y), p: "" }));
  $("pjcen").innerHTML = `<table class="wz"><tr><th>${tr("दशक (वर्ष)", "Decade (year)")}</th><th title="${tr("census में पूरे शहर (ULB) की कुल आबादी - वार्ड की आबादी ऊपर वार्ड तालिका में", "the whole town's (ULB) population in the census - the wards' are in the ward table above")}">${tr("पूरे शहर की आबादी", "Population of the whole town")}</th><th></th></tr>` +
    PJC.map((r, i) => `<tr><td><input data-i="${i}" data-k="y" type="number" value="${esc(r.y)}" style="width:70px"></td>` +
      `<td><input data-i="${i}" data-k="p" type="number" value="${esc(r.p)}" style="width:110px"></td>` +
      `<td><button data-x="${i}" title="${tr("यह पंक्ति हटाएँ", "remove this row")}">✕</button></td></tr>`).join("") +
    `</table><div class="row"><button id="pjcadd">+ ${tr("दशक", "decade")}</button></div>`;
  document.querySelectorAll("#pjcen input").forEach(inp => inp.onchange = () => {
    PJC[+inp.dataset.i][inp.dataset.k] = inp.value.trim(); pjcSync(); });
  document.querySelectorAll("#pjcen button[data-x]").forEach(b => b.onclick = () => { PJC.splice(+b.dataset.x, 1); pjcRender(); pjcSync(); });
  $("pjcadd").onclick = () => {
    const last = PJC.length ? +PJC[PJC.length - 1].y || 0 : 0;
    PJC.push({ y: last ? String(last + 10) : "", p: "" }); pjcRender();
  };
}
function pjcSync() { $("pjcensus").value = pjcText(); if (PJ || pjInputs()) pjRun(true); }
function pjcSet(s) { PJC = pjcFromText(s); pjcRender(); $("pjcensus").value = pjcText(); }
function wtChanged() { popUi(); if ($("pjcensus").value.trim() && wtTotal() > 0) pjRun(true); else if (!(wtTotal() > 0)) pjLock(!!PJ); }
$("wtn").onchange = () => {
  const n = Math.max(0, Math.min(300, Math.round(+$("wtn").value || 0)));
  while (WT.rows.length < n) WT.rows.push({ no: String(WT.rows.length + 1), name: "", char: "", pop: "", cov: "100", kcov: "", hh: "", area: "", census: "" });
  WT.rows.length = n; wtRender(); wtChanged();
};
$("wtyear").onchange = () => { WT.year = Math.round(+$("wtyear").value) || ""; if ($("wtyr")) $("wtyr").textContent = WT.year; wtChanged(); };
pjcRender();
$("pjcensus").onchange = $("popb").onchange = $("byear").onchange = () => { if (PJ || pjInputs()) pjRun(true); };
