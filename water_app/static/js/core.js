// The water map page (map.html), part 1 of 11: the page's globals, its language, the loading cover and the main CPHEEO guidelines.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
"use strict";
const KIND = {
  road:     { name: "सड़क",        color: "#d32f2f" },
  boundary: { name: "Boundary",   color: "#b8860b" },
  ward:     { name: "वार्ड",        color: "#2e7d32" },
  spot:     { name: "Spot level", color: "#6a1b9a" },
  stp:      { name: "STP",        color: "#0d47a1" },
};
KIND.oht = { name: "OHT / ESR", color: "#00838f" };
// a barrier line (highway, expressway, railway, canal - user 27-Oct-2026): no pipe crosses it; the zoning / design
// cut a pipe crossing it, both parts ending its gap_m (default 1 m) short of the line
KIND.barrier = { name: "रुकावट रेखा", color: "#37474f" };
// a zone loop (user 27-Oct-2026): the area it encloses is a zone of its own - its pipes crossing it closed there (valves);
// above / below the OZ limits the zoning asks (on_limit: keep / merge / split, kept with the loop)
const LOOP_MODES = [["", "पूछें", "Ask"], ["keep", "यही zone सीमा रखें", "Keep this zone boundary"],
  ["merge", "बगल वाले zone में merge", "Merge into the neighbouring zone"], ["split", "स्वतः नया zone बनाएँ", "Make new zones by itself"]];
KIND.zone_loop = { name: "Zone लूप", color: "#ad1457" };
// a ward's character and its growth - base / +15 / +30 years (Riverside water DPR p76, criteria.json ward_growth;
// user decision 6-Nov-2026)
// The names, densest first (user decision 9-Nov-2026): CPHEEO Manual on Water Supply 2024 Part A Annexure 2.7 p974's
// categories - low / medium / high / saturated, "the cores of the city" at saturation - with the Riverside DPR p76's
// word in brackets (its Proximal Developed / Core / Proximal Developing / Far-open, in that order of density); the
// old names of a saved project / map read as the new (charName; wards.char_name)
const CH = ["Saturated (Core)", "High (Proximal Developed)", "Medium (Proximal Developing)", "Low (Far-open)"];
const CH_OLD = { "Proximal Developed": CH[0], "Core": CH[1], "Proximal Developing": CH[2], "Far-open": CH[3] };
function charName(c) { c = String(c ?? "").trim(); return CH_OLD[c] || c; }
function charKeys(o) { const out = {}; for (const k in (o || {})) out[charName(k)] = o[k]; return out; }
const WARD_CHARS = [["", "— (page का गुणक)", "— (the page's factor)"]].concat(CH.map(c => [c, c, c]));
// Far-open: the balancing values of the example (technical.xlsx 'T' 465-478; user decision 7-Nov-2026); the page's
// ward table can change them all (WT.growth, yellow)
const WARD_GROWTH_DEF = { [CH[0]]: [1.02, 1.25, 1.50], [CH[1]]: [1.04, 1.40, 1.85],
  [CH[2]]: [1.06, 1.63, 2.45], [CH[3]]: [1.0932, 1.9183, 3.3282] };
const WARD_GROWTH = JSON.parse(JSON.stringify(WARD_GROWTH_DEF));
// the character by the density of the table's year (persons / ha above): the example technical.xlsx 'T' X346 (585 / 310 /
// 170, the rest Far-open; user decision 7-Nov-2026: filled by itself, the user may change it - yellow)
const WARD_DENS_DEF = { [CH[0]]: 585, [CH[1]]: 310, [CH[2]]: 170, [CH[3]]: 0 };
// the whole town's population of the table's year by character - Far-open's factors balance them to the adopted
// projection (example technical.xlsx 'T' AD347:AG347, Springfield's 100 wards; criteria ward_town_population; user
// decision 7-Nov-2026); another town: its own (yellow)
const WARD_TOWN_DEF = { [CH[0]]: 698311, [CH[1]]: 673088, [CH[2]]: 720858, [CH[3]]: 587585 };
// the saturation density (persons / ha): the upper limit of a ward's future density - CPHEEO Water Manual Part A
// Annexure 2.7 p974; default the example's densest Springfield ward 1,710 x 1.10 (criteria ward_saturation_density;
// user decision 8-Nov-2026: a ward above it only warned of); another town: its own (yellow), blank = no check
const WARD_SAT_DEF = 1880;
// CPHEEO Annexure 2.7 p974: the developed core near saturation - Saturated (Core)'s design factor above this warned
// of (the app's reading of "very close to the present density": 10 %, as the saturation's default; wards.CORE_NEAR)
const WARD_CORE_NEAR = 1.10;
// CPHEEO Manual on Water Supply 2024 Part A: the clauses on the ward-wise population (user 8-Nov-2026), shown with
// the factors of the ward's character
const CPHEEO_WARD = [
  ["2.8.2.2 (p37)", "शहर की कुल आबादी (आधार / +15 / +30) Town & Country Planning से तय करके वार्ड-वार बाँटें - बढ़त के रुझान से, यानी हर वार्ड की तात्कालिक और अंतिम stage की density से (2.8.1.24 के अनुसार)",
   "the town's total (base / +15 / +30), settled with Town & Country Planning, distributed ward-wise by the trend of growth - each ward's density in the immediate and ultimate stage (as 2.8.1.24)"],
  ["2.8.1.24 (p34-35)", "शहर के सब वार्डों का GIS नक्शा; हर वार्ड का land use क्षेत्रफल; equivalent area = residential × 1 + public × 0.25 + उद्योग / कृषि × 0.1 + सड़क / जल × 0 - density इसी पर",
   "a GIS map of all the town's wards; each ward's land-use areas; equivalent area = residential x 1 + public x 0.25 + industry / agriculture x 0.1 + roads / water x 0 - the density on it"],
  ["Table 2.7 क्र. 3 (p72), 3.6.3.2 (p103)", "सिर्फ़ शहर की कुल आबादी नहीं, वार्ड-वार आबादी और भविष्य की density (equivalent area पर) DPR में; परियोजना के अलग हिस्सों की 5 / 10 / 15 / 20 / 30 वर्ष बाद की density",
   "not only the town's total: the ward-wise population and future density (on the equivalent area) in the DPR; the densities of the parts of the project area 5 / 10 / 15 / 20 / 30 years ahead"],
  ["Annexure 2.7 (p974)", "विकसित core की density लगभग saturation पर (जब तक FSI न बढ़े) - saturation density आज की density के बहुत पास; यह हर वार्ड की भविष्य की density की ऊपरी सीमा। core के पास के वार्ड दूर वालों से तेज़ बढ़ते हैं; नदी / रेल जैसे barrier के पार धीमे; जहाँ ज़मीन के दाम तेज़ बढ़ें वहाँ आबादी भी",
   "the developed core's density practically at saturation (unless the FSI is raised) - the saturation density very close to its present density, the upper limit of every ward's future density. Wards near the core grow faster than those away; beyond a barrier (water body, railway) slower; where land prices rise fast, faster"],
  ["Annexure 2.7 (p974-975)", "वार्डों की आज की density को 4 श्रेणियों में बाँटें - low / medium / high / saturated (उदाहरण के 23 वार्ड के कस्बे में 31 / 45 / 95 प्रति ha; सीमाएँ शहर के आकार से - बड़ा शहर, बड़ी सीमाएँ); हर श्रेणी की भविष्य की density मानें",
   "the wards' present densities in 4 classes - low / medium / high / saturated (the example town of 23 wards: 31 / 45 / 95 per ha; the limits by the town's size - larger town, larger limits); a future density for each class"],
  ["Annexure 2.7 (p975-976)", "दोहराते रहें जब तक सब वार्डों का जोड़ शहर की projection से मिल जाए; फिर तकनीकी / प्रशासनिक लोगों से चर्चा और नगर निकाय की स्वीकृति - उसके बाद ही design",
   "iterate till all the wards add up to the town's projection; then discussion with technocrats / bureaucrats and the local body's approval - only then the design"],
  ["Annexure 2.8 (p980)", "Final Forecast: क्षेत्र / zone में आबादी का बँटवारा उसके विकास और town planning नियमों से; अंतिम stage का बँटवारा pipe के व्यास के लिए, तात्कालिक का टंकियों के लिए",
   "Final Forecast: the population's spread over areas / zones by their development and town-planning rules; the ultimate stage's for the pipe sizes, the immediate's for the service tanks"]];
// the select tool's loop (user 30-Oct-2026): what it encloses is selected together, to be deleted at once
KIND.lasso = { name: "घेरा", color: "#f9a825" };
// a crossing (user 27-Oct-2026): where it crosses a barrier line / zone loop the pipes there go through; where none
// does, it is a new pipe itself, joined to the nearest junction at each end
KIND.crossing = { name: "Crossing", color: "#00a152" };
const BARRIER_TYPES = [["highway", "Highway", "Highway"], ["expressway", "Expressway", "Expressway"],
  ["railway", "रेलवे लाइन", "Railway line"], ["canal", "नहर / नाला", "Canal / nala"], ["other", "अन्य", "Other"]];
const PIPE = "pipe";
const barrierType = t => { const x = BARRIER_TYPES.find(b => b[0] === t) || BARRIER_TYPES[4]; return EN ? x[2] : x[1]; };
KIND.oht_ex = { name: "पुरानी टंकी", color: "#00838f" };
// a bulk / institutional consumer (user 30-Oct-2026): its KLD and peak factor, on the nearest junction
KIND.bulk = { name: "Bulk consumer", color: "#6d4c41" };
// a pressure reducing valve (user 30-Oct-2026): on the pipe nearest to it, the area beyond held lower (prv.py)
KIND.prv = { name: "PRV", color: "#ef6c00" };
// a new tube well (water phase 2, user 31-Oct-2026): its own rising main along the roads to its OZ's OHT (rising.py)
KIND.tw = { name: "नया tube well", color: "#00897b" };
KIND.oht_new = { name: "नई टंकी", color: "#00838f" };
// an OHT of the drawing is existing (Ex-OHT: capacity and staging given) or new (Prop-OHT); older projects: existing
// when a capacity is given
const isExOht = p => !!p && (p.existing === "1" || p.existing === true ||
  ((p.existing === undefined || p.existing === "") && p.capacity_kl !== undefined && String(p.capacity_kl).trim() !== ""));
const SNAP_PX = 12;
const $ = id => document.getElementById(id);
// the water module's own page (isolation of sewer and water, 21-Oct-2026: each module has its own copy, server and
// folders - a change here does not reach the other module)
const MODULE = "water";
// the open project and the unsaved drawing, remembered per module (a reload opens the module's own project)
const LS_LAST = "water_app_last";
const LS_DRAFT = "water_app_draft";
{
  document.body.classList.add("water");
  document.title = "Water network design";
  $("title").textContent = "पेयजल network - नक्शे पर खींचें";
  $("spacing").value = 0;
}

// tell the server this page is open (a second start of sewer_ui.bat then opens no new tab)
fetch("/api/ping").catch(() => { }); setInterval(() => fetch("/api/ping").catch(() => { }), 30000);

// ---------------------------------------------------------------- loading cover
// shown from the first moment of the page (in the HTML) until the last project is open again; and while a file /
// project loads. Nested loads keep it until the last one ends.
let LOADING = 1, loadT0 = Date.now(), loadSlow = null;
function loading(on, text) {
  LOADING = Math.max(0, LOADING + (on ? 1 : -1));
  const el = document.getElementById("loading");
  if (LOADING) {
    if (on) { if (text) document.getElementById("loadtext").textContent = text; if (LOADING === 1) loadT0 = Date.now(); }
    el.classList.add("show");
    clearTimeout(loadSlow);
    loadSlow = setTimeout(() => { if (LOADING) el.classList.add("slow"); }, 20000);   // something hangs: a way out
  } else { el.classList.remove("show", "slow"); clearTimeout(loadSlow); }
}
async function withLoading(text, fn) { loading(true, text); try { return await fn(); } finally { loading(false); } }
document.addEventListener("keydown", e => {               // no keys reach the page under the cover
  if (e.key === "Escape" && document.getElementById("guide").classList.contains("show")) {
    hideGuide(); e.preventDefault(); e.stopImmediatePropagation(); return;
  }
  if (LOADING && !document.getElementById("modal").classList.contains("show")) { e.preventDefault(); e.stopImmediatePropagation(); }
}, true);
setInterval(() => { if (LOADING) document.getElementById("loadsub").textContent = Math.round((Date.now() - loadT0) / 1000) + " s"; }, 1000);
document.getElementById("loadskip").onclick = () => { LOADING = 1; loading(false); };
document.getElementById("loadtext").textContent = tr("लोड हो रहा है …", "Loading …");
document.getElementById("loadskip").textContent = tr("इंतज़ार न करें", "Don't wait");

// ---------------------------------------------------------------- main CPHEEO guidelines
// [Hindi, English, reference]; "UPJN:" in the reference = a UPJN rule, not CPHEEO. Values as used by the app
// (water_app/criteria.json, data/design_criteria.json), checked against the manuals.
// 50 points per module (user request 20-Oct-2026): 1-40 network design, 41-50 mechanical / electrical; a { sec } entry
// is a heading in the list (not numbered).
const GSEC_NET = { sec: ["नेटवर्क डिज़ाइन (1-40)", "Network design (1-40)"] };
const GSEC_ME = { sec: ["मैकेनिकल / इलेक्ट्रिकल (41-50)", "Mechanical / electrical (41-50)"] };
const GUIDE = {
  water: { hi: "मुख्य CPHEEO डिज़ाइन मानक - पेयजल वितरण", en: "Main CPHEEO design guidelines - water distribution",
    src: "CPHEEO Manual on Water Supply and Treatment Systems, Part A - Table 2.7 (planning & design norms), Chapters 5, 6",
    note: ["पृष्ठ = manual PDF का पृष्ठ; नारंगी = उत्तर प्रदेश जल निगम का नियम; यह सारांश है - DPR में मूल manual का हवाला दें",
           "Page = page of the manual's PDF. Orange = a UP Jal Nigam rule. A summary - cite the manual itself in the DPR."],
    items: [
      GSEC_NET,
      ["<b>डिज़ाइन अवधि:</b> वितरण pipes और ESR अंतिम चरण (base year + 30 वर्ष) के लिए; मध्य चरण 15 वर्ष",
       "<b>Design period:</b> distribution pipes and ESRs for the ultimate stage (base year + 30 years); intermediate stage 15 years.", "Table 2.7 S.No.1, p168"],
      ["<b>ज़मीन पहले से तय:</b> शहर के master plan में अगले 30 वर्ष या अधिक के लिए WTP, sump, ESR आदि की ज़मीन चिह्नित करें; न मिले तो पार्क / खेल मैदान जैसी जगह में",
       "<b>Land earmarked:</b> mark the land for WTPs, sumps, ESRs etc. in the city's master plan for the next 30 years or more; if none, in recreational land such as parks or stadiums.", "Table 2.7 S.No.2, p168"],
      ["<b>प्रति व्यक्ति जल:</b> 10 लाख या अधिक आबादी वाले शहर 150 LPCD, उससे छोटे 135 LPCD",
       "<b>Per capita supply:</b> 150 LPCD for cities of 10 lakh or more, 135 LPCD below.", "Table 2.7 S.No.4, p169"],
      ["<b>Floating population:</b> स्नान सुविधा सहित 45 LPCD, बिना 25 LPCD, केवल सार्वजनिक सुविधा 15 LPCD",
       "<b>Floating population:</b> 45 LPCD with bathing facilities, 25 without, 15 for public facilities only.", "Table 2.7 S.No.5, p170"],
      ["<b>डिज़ाइन आबादी:</b> वार्ड-वार अनुमान, GIS land use से equivalent area - आवासीय 100%, सार्वजनिक 25%, उद्योग / कृषि 10%",
       "<b>Design population:</b> ward by ward, by the equivalent area of the GIS land use - residential 100%, public 25%, industry / agriculture 10%.", "2.8.1.24, p131"],
      ["<b>हानियाँ:</b> वितरण में 10% से अधिक नहीं (भूजल सीधे वितरण में: कुल 11%)",
       "<b>Losses:</b> not more than 10% in distribution (ground water supplied directly: 11% in all).", "Table 2.7 S.No.6, p171"],
      ["<b>कुल हानियाँ 15% तक:</b> headwork से WTP तक 1%, WTP में 3%, WTP से ESR तक 1% (पहला और तीसरा मिलाकर 2%; 20 km से लंबे हों तो 1% प्रति 10 km), वितरण में 10%",
       "<b>Total losses up to 15%:</b> headwork to WTP 1%, in the WTP 3%, WTP to the ESRs 1% (the first and third together 2%; over 20 km, 1% per 10 km), distribution 10%.", "Table 2.7 S.No.6, p171"],
      ["<b>Peak factor:</b> शहरी वितरण network के लिए 2.5, आबादी चाहे जितनी हो (शहरी-ग्रामीण योजना के ग्रामीण भाग में 3); ESR तक transmission 22 घंटे के लिए",
       "<b>Peak factor:</b> 2.5 for an urban distribution network irrespective of population (3 in the rural part of urban-rural schemes); transmission up to the ESRs for 22 hours.", "Table 2.7 S.No.7, p172"],
      ["<b>अग्निशमन माँग:</b> 100√P m³/दिन (P हज़ार में)",
       "<b>Fire demand:</b> 100√P m³/day (P in thousands).", "Table 2.7 S.No.13, p176"],
      ["<b>ESR में अग्निशमन भंडार:</b> OZ की अग्निशमन आवश्यकता का एक-तिहाई टंकी में, सामान्य outlet उसके ऊपर रखें; तल में fire outlet; हर ESR पर दमकल की गाड़ियाँ भरने की व्यवस्था",
       "<b>Fire storage in the ESR:</b> one third of the OZ's fire requirement kept in the tank, the normal outlet just above it; a fire outlet at the bottom; filling of fire tenders at every ESR.", "Table 2.7 S.No.13, p176-177"],
      ["<b>न्यूनतम व्यास:</b> 100 mm (पुराने 80 mm pipe रह सकते हैं)",
       "<b>Minimum diameter:</b> 100 mm (existing 80 mm pipes may stay).", "Table 2.7 S.No.8, p172"],
      ["<b>पहाड़ी क्षेत्र:</b> नए primary pipe कम से कम 80 mm (पुराने 63 mm रह सकते हैं); संकरी गलियों के secondary pipe 32-63 mm",
       "<b>Hilly terrain:</b> new primary pipes at least 80 mm (existing 63 mm may stay); secondary pipes in narrow lanes 32-63 mm.", "Table 2.7 S.No.8, p172"],
      ["<b>Residual head (ferrule पर):</b> Class I और II शहरों में सबसे ऊँचे node पर 17-21 m, अन्य शहरों में 12-15 m",
       "<b>Residual head at the ferrule:</b> 17-21 m at the highest node for Class I and II cities, 12-15 m for others.", "Table 2.7 S.No.10, p173"],
      ["<b>पुरानी ESR की staging कम हो:</b> OZ उसकी क्षमता (अंतिम चरण की आबादी) जितना; outlet पर VFD pump, staging को suction head मानकर; टंकी सूखने पर pump बंद; critical node के sensor से नियंत्रण",
       "<b>Existing ESR with too little staging:</b> its OZ as large as its capacity serves (ultimate-stage population); a VFD pump at the outlet using the staging as suction head, stopping when the tank runs dry, run from a sensor at the critical node.", "Table 2.7 S.No.10, p173"],
      ["<b>ESR क्षमता:</b> संतुलन भंडार = mass balance या OZ की अंतिम चरण की दैनिक माँग (fire के बिना) का 33%, जो अधिक हो (कम से कम 33%); <b>+ अग्निशमन भंडार</b> = OZ की अग्निशमन माँग का एक-तिहाई",
       "<b>ESR capacity:</b> balancing storage = mass balance or 33% of the OZ's ultimate-stage daily demand (without fire), the larger (at least 33%); <b>+ fire storage</b> = one third of the OZ's fire demand.", "Table 2.7 S.No.12, p175; S.No.13, p176"],
      ["<b>ESR की पानी की अधिकतम गहराई (SWD):</b> 1 लाख लीटर तक 3 m; 10 लाख लीटर तक 4 m; उससे बड़ी 5 m",
       "<b>Maximum side water depth (SWD) of an ESR:</b> 3 m up to 1 lakh litres; 4 m up to 10 lakh litres; 5 m above.", "Table 2.7 S.No.12, p176"],
      ["<b>बौनी / छोटी टंकियाँ न जोड़ें:</b> कम staging वाली छोटी ESR से न्यूनतम residual pressure नहीं मिलता",
       "<b>No dwarf / small ESRs:</b> small tanks of low staging cannot give the minimum residual pressure.", "p98, p102"],
      ["<b>Pressure zones:</b> शहर को GIS contours से pressure zones में, फिर OZ में बाँटें; पुरानी टंकियों की सही सीमा तय करके बचे क्षेत्र में नई टंकियाँ",
       "<b>Pressure zones:</b> divide the city by GIS contours into pressure zones, then OZs; fix the optimum boundaries of the existing tanks first, plan new tanks in the area left over.", "2.8.1.9, p124; steps p140"],
      ["<b>Operational Zone (OZ):</b> हर service reservoir का एक OZ; मैदानी क्षेत्र में 50,000 आबादी या 10,000 connections तक (पहाड़ी 30,000 / 6,000; घनी आबादी में औचित्य सहित 75,000-1,00,000)",
       "<b>Operational zone (OZ):</b> one OZ per service reservoir; up to 50,000 population or 10,000 connections in plain areas (hilly 30,000 / 6,000; dense areas 75,000-1,00,000 with justification).", "Table 2.7 S.No.20, p180; 2.8.1.9, p124"],
      ["<b>OZ की सीमा:</b> सड़क, रेल लाइन, नाला जैसी प्राकृतिक सीमाओं और ढलान से; transmission / feeder mains ऐसे कि एक OZ में बड़ी रुकावट पर दूसरे OZ से आपूर्ति हो सके",
       "<b>OZ boundaries:</b> by natural features such as roads, railway lines and nallas, and the slope; transmission / feeder mains designed so that another OZ can make up a major disruption in one OZ.", "Table 2.7 S.No.18, p179-180"],
      ["<b>OZ में ज़मीन का ढाल:</b> गैर-पहाड़ी क्षेत्र में 5 m तक",
       "<b>Ground within an OZ:</b> up to 5 m difference in non-hilly areas.", "Table 2.7 S.No.18, p180"],
      ["<b>DMA:</b> मैदानी क्षेत्र में 500-3000 connections (पहाड़ी 300-1500); एक OZ में अधिकतम 4 DMA; हर DMA hydraulically अलग, एक inlet पर isolation valve, bulk meter और FCV",
       "<b>DMA:</b> 500-3000 connections in plain areas (hilly 300-1500); at most 4 DMAs per OZ; each DMA hydraulically discrete, one inlet with an isolation valve, bulk meter and FCV.", "Table 2.7 S.No.21, p181; 2.8.1.9, p124"],
      ["<b>DMA को पानी:</b> नई टंकी में हर DMA का अलग outlet; ESR से DMA तक के common feeder से कोई consumer connection नहीं",
       "<b>Feeding the DMAs:</b> a separate outlet from a new tank for each DMA; no consumer connections from the common feeder between the ESR and the DMAs.", "Table 2.7 S.No.21, p181-182"],
      ["<b>Isolation valves:</b> ऐसे लगाएँ कि मरम्मत के समय 50-250 connections (पहाड़ी में 50 तक) का हिस्सा ही बंद हो; इनसे sub-DMA भी बनते हैं",
       "<b>Isolation valves:</b> placed so that a repair shuts a segment of 50-250 connections only (up to 50 in hilly areas); they also form sub-DMAs.", "Table 2.7 S.No.30, p184"],
      ["<b>Control valves:</b> पहाड़ी शहरों और नीचे बसे DMA में PRV; हर DMA के inlet पर dual solenoid वाला FCV, peak hour माँग पर set",
       "<b>Control valves:</b> PRVs in hilly cities and low-lying DMAs; an FCV with dual solenoid at each DMA inlet, set for the peak-hour demand.", "Table 2.7 S.No.26, p183"],
      ["<b>Bulk meters:</b> headwork, WTP के inlet व outlet और हर DMA के प्रवेश पर; DMA के inlet पर न्यूनतम रात्रि प्रवाह से NRW पर नज़र",
       "<b>Bulk meters:</b> at the headwork, the WTP inlet and outlet and at the entry of every DMA; NRW watched by the minimum net night flow at the DMA inlet.", "Table 2.7 S.No.24, p182"],
      ["<b>वेग:</b> 0.4-0.6 m/s उचित (न्यूनतम व्यास के कारण 0.3 m/s तक, scour सहित); अधिकतम 3 m/s (filtered water)",
       "<b>Velocity:</b> 0.4-0.6 m/s recommended (down to 0.3 m/s where the minimum diameter forces it, with scouring); maximum 3 m/s for filtered water.", "6.6 (i), (ii), p400"],
      ["<b>Head loss:</b> Hazen-Williams सूत्र; minor losses friction का 10%",
       "<b>Head loss:</b> Hazen-Williams formula; minor losses 10% of friction.", "6.6 (vi), p400; Table 2.7 S.No.36, p187"],
      ["<b>Transmission mains:</b> head loss gradient 10 m/km तक (पहाड़ी में अधिक हो सकता है), पर वेग 2.5 m/s से अधिक नहीं; हर ESR को उसकी design मात्रा",
       "<b>Transmission mains:</b> head loss gradient up to 10 m/km (more in hilly areas), but velocity not above 2.5 m/s; every ESR gets just its design quantity.", "Table 2.7 S.No.22, p182"],
      ["<b>MBR / ZBR:</b> master balancing reservoir अंतिम माँग के 3 घंटे का; ग्रामीण zonal balancing reservoir अपने क्षेत्र की टंकियों की अंतिम माँग के 2 घंटे का",
       "<b>MBR / ZBR:</b> a master balancing reservoir for 3 hours of the ultimate demand; a rural zonal balancing reservoir for 2 hours of the ultimate demand of the tanks it commands.", "Table 2.7 S.No.29, p184"],
      ["<b>Hydraulic model:</b> GIS आधारित; पूरे शहर के केवल दो model - वितरण और raw / treated transmission; हर node को GIS से elevation और माँग ('whole to the part')",
       "<b>Hydraulic model:</b> GIS based; only two models for the city - distribution and raw / treated transmission; every node given its elevation and demand from GIS ('whole to the part').", "Table 2.7 S.No.17, p179"],
      ["<b>GIS mapping:</b> मौजूदा, प्रस्तावित और बने सभी ढाँचे का GIS नक्शा; वार्ड की सीमाएँ GIS से, माँग वार्ड-वार आबादी घनत्व से",
       "<b>GIS mapping:</b> all existing, proposed and executed infrastructure in GIS; ward boundaries from GIS for the demand by ward-wise population density.", "Table 2.7 S.No.14, p177"],
      ["<b>Survey:</b> सड़कों के साथ ज़मीन के स्तर total station से (GIS निर्देशांक सहित) और उनसे GIS contours; समतल शहर में 3D stereo satellite से; घर-घर consumer survey, meters geo-tagged",
       "<b>Survey:</b> ground levels along the roads by total station (with GIS coordinates) and GIS contours from them; 3D stereo satellite where the city is flat; door-to-door consumer survey, meters geo-tagged.", "Table 2.7 S.No.39, 40, p188"],
      ["<b>Pipe सामग्री:</b> pumping, transmission और DMA feeder mains preferably भीतरी lining वाले metallic pipes; non-metallic हों तो औचित्य सहित",
       "<b>Pipe material:</b> pumping, transmission and DMA feeder mains preferably metallic pipes with internal lining; non-metallic ones only with justification.", "Table 2.7 S.No.32, p185"],
      ["<b>Pipe बिछाना:</b> न्यूनतम cover 0.9 m (या pipe के BIS code से); 80 / 100 mm pipe से 25 mm से बड़ा connection नहीं; pumping, transmission और DMA feeder mains से कोई connection नहीं",
       "<b>Laying pipes:</b> minimum cover 0.9 m (or per the pipe's BIS code); no connection above 25 mm from an 80 / 100 mm pipe; no service connections from pumping, transmission or DMA feeder mains.", "Table 2.7 S.No.33, p186"],
      ["<b>6 m या चौड़ी सड़क:</b> pipeline सड़क के दोनों ओर, ताकि connection के लिए सड़क न काटनी पड़े",
       "<b>Roads 6 m wide or more:</b> pipelines on both sides, so that house connections need no road cutting.", "Table 2.7 S.No.34, p186"],
      ["<b>Public stand post नहीं:</b> नए stand post नहीं; पुराने हटाकर meter वाले घरेलू connection, OZ-वार समयबद्ध कार्यक्रम से",
       "<b>No public stand posts:</b> no new ones; existing ones replaced by metered house connections in an OZ-wise time-bound programme.", "Table 2.7 S.No.9, p173"],
      ["<b>घर की भूमिगत टंकी:</b> तीन मंज़िल तक के भवनों में प्रोत्साहित न करें; 24×7 आपूर्ति स्थिर होने पर मौजूदा टंकियाँ धीरे-धीरे हटाएँ",
       "<b>Consumer underground tanks:</b> not encouraged for buildings up to three storeys; existing ones removed gradually once 24×7 supply is stable.", "Table 2.7 S.No.35, p186-187"],
      ["<b>24×7 दबावयुक्त आपूर्ति:</b> 100% consumer metering और telescopic tariff; हर DMA का water audit",
       "<b>24×7 pressurised supply:</b> 100% consumer metering with a telescopic tariff; a water audit of every DMA.", "p108; Fig. 2.13, p155"],
      ["<b>CWR:</b> एक ESR को 3 से अधिक नलकूप भरें तो CWR अनिवार्य; CWR की क्षमता ESR का 25%",
       "<b>CWR:</b> mandatory when more than 3 tube wells fill one ESR; CWR capacity 25% of the ESR.", "UPJN: rule; CPHEEO 2.8.1.17, p127 (25%)"],
      GSEC_ME,
      ["<b>Pumping machinery की अवधि:</b> नलकूप, WTP, CWR और pumping machinery मध्य चरण (base year + 15 वर्ष) के लिए; ज़मीन अंतिम चरण के लिए रखें",
       "<b>Period for machinery:</b> tube wells, WTPs, CWRs and pumping machinery for the intermediate stage (base year + 15 years); land kept for the ultimate stage.", "Table 2.7 S.No.1, p168"],
      ["<b>Pumping station की जगह:</b> बाढ़ से मुक्त सूखी ज़मीन; pump / motor floor उच्चतम बाढ़ स्तर (HFL) से 1-2 m ऊपर; भारी वाहनों के लिए कम से कम 3 m चौड़ा रास्ता",
       "<b>Pumping station site:</b> dry land free from flooding; pump / motor floor 1-2 m above the high flood level (HFL); an approach at least 3 m clear for heavy vehicles.", "5.2.1, p307"],
      ["<b>बिजली:</b> dedicated independent feeder; 63 / 100 kVA या अधिक भार पर substation; headwork और WTP के लिए 11 kV express feeder अनिवार्य; independent feeder न हो तो diesel generator standby (50 BHP तक के pumps के लिए generator)",
       "<b>Power:</b> a dedicated independent feeder; a substation for a load of 63 / 100 kVA or more; an 11 kV express feeder mandatory for headworks and WTPs; a diesel generator as standby where there is no independent feeder (generators for pumps up to 50 BHP).", "5.2.2, p307; Table 2.7 S.No.38, p188"],
      ["<b>Pumps की संख्या:</b> एक working हो तो 1 + 1 standby; दो working हों तो 2 + 1 standby (बड़ी योजना 2 + 2); 25 MLD से छोटे में दो pumps औसत दैनिक प्रवाह के, या तीन pumps 50% के (2 working + 1 standby)",
       "<b>Number of pumps:</b> one working - 1 + 1 standby; two working - 2 + 1 standby (large schemes 2 + 2); below 25 MLD two pumps of the average daily discharge, or three of 50% each (2 working + 1 standby).", "5.7.5, p350"],
      ["<b>Pump का चयन:</b> specific speed 38-68 (SI), 80 से अधिक कभी नहीं; बड़े संयंत्र में 980 rpm (अपवाद में 1,480; 2,900 केवल borewell submersible में); VT pump में 5 stage तक (अपवाद 10); centrifugal pump preferably double suction horizontal split casing; open well, intake और sump में submersible pump से बचें",
       "<b>Pump selection:</b> specific speed 38-68 (SI), never above 80; 980 rpm for large installations (1,480 in exceptions; 2,900 only for borewell submersibles); VT pumps up to 5 stages (10 in exceptions); centrifugal pumps preferably double-suction horizontal split casing; avoid submersibles in open wells, intakes and sumps.", "5.11, p358"],
      ["<b>Motor rating:</b> pump bkW पर margin - 1.5 kW तक 50%; 1.5-3.7: 40%; 3.7-7.5: 30%; 7.5-15: 20%; 15-75: 15%; 75 kW से अधिक 10%; HWL पर अधिक प्रवाह में भी overload न हो",
       "<b>Motor rating:</b> margin over the pump bkW - up to 1.5 kW 50%; 1.5-3.7: 40%; 3.7-7.5: 30%; 7.5-15: 20%; 15-75: 15%; above 75 kW 10%; no overload even at the higher discharge with HWL.", "5.12, Table 5.6, p358-359"],
      ["<b>Energy efficient motors:</b> IE2 न्यूनतम अनिवार्य; भारत में उपलब्ध सबसे ऊँचे स्तर (IE3 / IE4) की motor चुनें (IS 12615)",
       "<b>Energy-efficient motors:</b> IE2 is the mandatory minimum; select the highest level available in India (IE3 / IE4) (IS 12615).", "5.20.2, 5.20.3, p370"],
      ["<b>प्रवाह नियंत्रण:</b> pump की गति बदलना (VFD) सबसे कुशल; valve से throttling में ऊर्जा व्यर्थ; अधिक static head वाले system में VFD सावधानी से (निर्माता से परामर्श)",
       "<b>Flow control:</b> changing the pump speed (VFD) is the most efficient; throttling with a valve wastes energy; VFDs with care where the static head is a large part of the total (consult the manufacturer).", "5.16.4, 5.16.5, p365-366"],
      ["<b>Valves और surge:</b> 300 mm या बड़े delivery valve पर electric actuator; header और surge device के बीच NRV / DPCV व isolation valve; ऊँचे बिंदुओं पर air valve, हर एक के साथ isolation valve; surge protection 6.12 / 6.16 के अनुसार",
       "<b>Valves and surge:</b> an electric actuator on delivery valves of 300 mm and above; an NRV / DPCV and an isolation valve between the header and the surge device; air valves at high points, each with an isolation valve; surge protection as in 6.12 / 6.16.", "5.2.9.6, 5.2.10, p318"],
      ["<b>Substation और panels:</b> switchboard के सामने कम से कम 915 mm (व्यवहार में लगभग 1.4 m), सिरों पर 750 mm का रास्ता; APFC panel; आपात के लिए DG set; lightning arresters; 1000 kVA या बड़े outdoor substation में circuit breaker भी",
       "<b>Substation and panels:</b> at least 915 mm clear in front of a switchboard (about 1.4 m in practice), a 750 mm passage at the ends; APFC panels; DG sets for emergencies; lightning arresters; circuit breakers too in outdoor substations of 1000 kVA and above.", "5.2.11, p318-319"],
    ] },

};
function showGuide() {
  const g = GUIDE.water;
  document.getElementById("gtitle").textContent = EN ? g.en : g.hi;
  document.getElementById("gsub").textContent = g.src;
  document.getElementById("gnote").textContent = EN ? g.note[1] : g.note[0];
  document.getElementById("gclose").textContent = EN ? "Close" : "बंद करें";
  document.getElementById("gx").title = EN ? "Close (Esc)" : "बंद करें (Esc)";
  document.getElementById("glist").innerHTML = g.items.map(it => it.sec ? `<li class="gsec">${EN ? it.sec[1] : it.sec[0]}</li>` : (([hi, en, ref]) =>
    `<li class="${/^UPJN/.test(ref) ? "upjn" : ""}"><span>${EN ? en : hi}</span><span class="ref">${ref.replace(/^UPJN: rule;/, "UPJN rule;")}</span></li>`)(it)).join("");
  document.getElementById("guide").classList.add("show");
  document.querySelector("#guide .gbody").scrollTop = 0;
  document.getElementById("gclose").focus();
}
// opened with the page: the last project is opened only after it is closed - reading a big project keeps the browser
// busy for seconds, and the guidelines would not scroll / close meanwhile
let guideWait = null, guideReady = Promise.resolve();
function hideGuide() {
  document.getElementById("guide").classList.remove("show");
  if (guideWait) { const go = guideWait; guideWait = null; setTimeout(go, 50); }    // the page repaints first
}
document.getElementById("gx").onclick = hideGuide;
document.getElementById("gclose").onclick = hideGuide;
document.getElementById("gopen").onclick = e => { e.preventDefault(); showGuide(); };
// the language on this page itself, and the other module beside it (user decision 10-Nov-2026: the two apps fully
// independent - the other one is started only now, by the launcher on port 8764, in a window / tab of its own;
// the launcher not running (this module started alone): opened if it already runs)
{
  const sw = document.getElementById("langsw");
  sw.textContent = EN ? "🌐 हिन्दी" : "🌐 English";
  sw.title = EN ? "पेज हिन्दी में" : "Page in English";
  sw.onclick = e => {
    e.preventDefault();
    const q = new URLSearchParams(location.search); q.set("lang", EN ? "hi" : "en"); q.delete("intro");
    location.href = location.pathname + "?" + q + location.hash;
  };
  const O = { name: "sewer", port: 8765, page: "/sewer", win: "sewer_network_design", hi: "सीवर", en: "Sewer" };
  const ob = document.getElementById("otherapp");
  ob.textContent = "↗ " + tr(O.hi, O.en);
  ob.title = tr(`${O.hi} app अपनी window में खोलें (वह तभी शुरू होता है)`, `Open the ${O.en} app in a window of its own (it starts only then)`);
  ob.onclick = async e => {
    e.preventDefault();
    // the browser: the window / tab opened at the click itself (a popup blocker lets it), its address set once the
    // other app answers; one open already is only brought forward (its work stays). The desktop app: after.
    const desk = !!(window.pywebview && window.pywebview.api);
    const w = desk ? null : window.open("", O.win);
    let ok = false, why = "";
    try {
      const r = await (await fetch(`http://127.0.0.1:8764/api/open?module=${O.name}`)).json();
      ok = !!r.ok; why = r.log || "";
    } catch (err) { why = ""; }
    if (!ok) {                                        // no launcher: the other module may run on its own already
      try { await fetch(`http://127.0.0.1:${O.port}/api/version`, { mode: "no-cors" }); ok = true; } catch (err) { ok = false; }
    }
    if (!ok) {
      if (w) { try { if (w.location.href === "about:blank") w.close(); } catch (err) { } }
      alert(tr(`${O.hi} app शुरू नहीं हो सका${why ? " - " + why : ""}। App को उसके icon / start page से खोलें।`,
               `The ${O.en} app could not be started${why ? " - " + why : ""}. Open the app from its icon / start page.`));
      return;
    }
    const url = `http://127.0.0.1:${O.port}${O.page}?lang=${LANG}`;
    if (!w) { window.open(url, O.win); return; }
    let blank = false;
    try { blank = w.location.href === "about:blank"; } catch (err) { blank = false; }   // the other app's own page: cross-origin
    if (blank) w.location.href = url;
    w.focus();
  };
}
{ // opened from the start page (language chosen): the guidelines first; not again on F5
  const q = new URLSearchParams(location.search);
  if (q.get("intro") === "1") {
    q.delete("intro");
    history.replaceState(null, "", location.pathname + (q.toString() ? "?" + q : "") + location.hash);
    guideReady = new Promise(res => { guideWait = res; });
    showGuide();
  }
}
