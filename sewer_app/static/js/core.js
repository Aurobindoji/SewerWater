// The sewer map page (map.html), part 1 of 9: the page's globals, its language, the loading cover and the main CPHEEO guidelines.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
"use strict";
const KIND = {
  road:     { name: "सड़क",        color: "#d32f2f" },
  boundary: { name: "Boundary",   color: "#b8860b" },
  ward:     { name: "वार्ड",        color: "#2e7d32" },
  spot:     { name: "Spot level", color: "#6a1b9a" },
  stp:      { name: "STP",        color: "#0d47a1" },
};
// a barrier line (highway, expressway, railway, canal - user 27-Oct-2026): no sewer crosses it; the zoning / design
// cut a sewer crossing it, both parts ending its gap_m (default 1 m) short of the line
KIND.barrier = { name: "रुकावट रेखा", color: "#37474f" };
// a zone loop (user 27-Oct-2026): the area it encloses is a zone of its own - the sewers crossing it stop there;
// its lowest manhole is its outlet (pumping station)
KIND.zone_loop = { name: "Zone लूप", color: "#ad1457" };
// the select tool's loop (user 30-Oct-2026): what it encloses is selected together, to be deleted at once
KIND.lasso = { name: "घेरा", color: "#f9a825" };
// a crossing (user 27-Oct-2026): where it crosses a barrier line / zone loop the sewers there go through; where none
// does, it is a new sewer itself, joined to the nearest manhole at each end
KIND.crossing = { name: "Crossing", color: "#00a152" };
const BARRIER_TYPES = [["highway", "Highway", "Highway"], ["expressway", "Expressway", "Expressway"],
  ["railway", "रेलवे लाइन", "Railway line"], ["canal", "नहर / नाला", "Canal / nala"], ["other", "अन्य", "Other"]];
const PIPE = "sewer";
const barrierType = t => { const x = BARRIER_TYPES.find(b => b[0] === t) || BARRIER_TYPES[4]; return EN ? x[2] : x[1]; };
const SNAP_PX = 12;
const $ = id => document.getElementById(id);
// the sewer module's own page (isolation of sewer and water, 21-Oct-2026: each module has its own copy, server and
// folders - a change here does not reach the other module)
const MODULE = "sewer";
// the open project and the unsaved drawing, remembered per module (a reload opens the module's own project)
const LS_LAST = "sewer_app_last";
const LS_DRAFT = "sewer_app_draft";

// tell the server this page is open (a second start of sewer_ui.bat then opens no new tab)
fetch("/api/ping").catch(() => { }); setInterval(() => fetch("/api/ping").catch(() => { }), 30000);

// ---------------------------------------------------------------- loading cover
// shown from the first moment of the page (in the HTML) until the last project is open again; and while a file /
// project loads. Nested loads keep it until the last one ends.
let LOADING = 1, loadT0 = Date.now();
function loading(on, text) {
  LOADING = Math.max(0, LOADING + (on ? 1 : -1));
  const el = document.getElementById("loading");
  if (LOADING) {
    if (on) { if (text) document.getElementById("loadtext").textContent = text; if (LOADING === 1) loadT0 = Date.now(); }
    el.classList.add("show");
  } else el.classList.remove("show");
}
async function withLoading(text, fn) { loading(true, text); try { return await fn(); } finally { loading(false); } }
document.addEventListener("keydown", e => {               // no keys reach the page under the cover
  if (e.key === "Escape" && document.getElementById("guide").classList.contains("show")) {
    hideGuide(); e.preventDefault(); e.stopImmediatePropagation(); return;
  }
  if (LOADING && !document.getElementById("modal").classList.contains("show")) { e.preventDefault(); e.stopImmediatePropagation(); }
}, true);
setInterval(() => { if (LOADING) document.getElementById("loadsub").textContent = Math.round((Date.now() - loadT0) / 1000) + " s"; }, 1000);
document.getElementById("loadtext").textContent = tr("लोड हो रहा है …", "Loading …");

// ---------------------------------------------------------------- main CPHEEO guidelines
// [Hindi, English, reference]; "UPJN:" in the reference = a UPJN rule, not CPHEEO. Values as used by the app
// (data/design_criteria.json), checked against the manuals.
// 50 points per module (user request 20-Oct-2026): 1-40 network design, 41-50 mechanical / electrical; a { sec } entry
// is a heading in the list (not numbered).
const GSEC_NET = { sec: ["नेटवर्क डिज़ाइन (1-40)", "Network design (1-40)"] };
const GSEC_ME = { sec: ["मैकेनिकल / इलेक्ट्रिकल (41-50)", "Mechanical / electrical (41-50)"] };
const GUIDE = {
  sewer: { hi: "मुख्य CPHEEO डिज़ाइन मानक - सीवर (gravity sewers)", en: "Main CPHEEO design guidelines - gravity sewers",
    src: "CPHEEO Manual on Sewerage and Sewage Treatment Systems, Part A (Engineering) - Chapters 2, 3, 4",
    note: ["पृष्ठ = manual का छपा पृष्ठ (अध्याय-पृष्ठ); यह सारांश है - DPR में मूल manual का हवाला दें",
           "Page = printed page of the manual (chapter-page). A summary - cite the manual itself in the DPR."],
    items: [
      GSEC_NET,
      ["<b>डिज़ाइन अवधि:</b> पारंपरिक sewers, pumping mains, pumping station (civil) 30 वर्ष; pumping machinery और STP 15 वर्ष",
       "<b>Design period:</b> conventional sewers, pumping mains and pumping stations (civil) 30 years; pumping machinery and STPs 15 years.", "Table 2.1, p2-9"],
      ["<b>आबादी:</b> master plan के land use और FSI से अंतिम घनत्व; वह न हो तो Table 3.1 के घनत्व",
       "<b>Population:</b> the ultimate densities from the master plan's land use and FSI; without one, the densities of Table 3.1.", "3.3, p3-2"],
      ["<b>Zoning:</b> बड़े शहरों में sewerage के zones, STPs बाहर की ओर फैले (radially outwards); विकेन्द्रीकृत sewerage केवल संस्थानों तक",
       "<b>Zoning:</b> in metropolitan cities, sewerage zones with STPs fanning out radially outwards; decentralised sewerage confined to institutions.", "2.9, p2-12"],
      ["<b>Peak factor (योगदान करने वाली आबादी):</b> 20,000 तक 3.0; 20,001-50,000: 2.5; 50,001-7,50,000: 2.25; उससे अधिक 2.0",
       "<b>Peak factor (contributory population):</b> up to 20,000: 3.0; 20,001-50,000: 2.5; 50,001-7,50,000: 2.25; above: 2.0.", "Table 3.2, p3-3"],
      ["<b>न्यूनतम प्रवाह:</b> औसत प्रवाह का 1/3 से 1/2",
       "<b>Minimum flow:</b> 1/3 to 1/2 of the average flow.", "3.5, p3-4"],
      ["<b>Infiltration:</b> 5,000-50,000 L/ha/दिन, 500-5,000 L/km/दिन, 250-500 L/manhole/दिन; पर डिज़ाइन sewage प्रवाह के 10% तक सीमित",
       "<b>Infiltration:</b> 5,000-50,000 L/ha/day, 500-5,000 L/km/day, 250-500 L/manhole/day; limited to 10% of the design sewage flow.", "Table 3.3, 3.6, p3-4"],
      ["<b>न्यूनतम व्यास:</b> base year में 1 लाख से अधिक आबादी वाले शहर 200 mm; 1 लाख से कम और पहाड़ी क्षेत्र 150 mm; घर का connection कम से कम 100 mm",
       "<b>Minimum diameter:</b> 200 mm for cities above 1 lakh base-year population; 150 mm below 1 lakh and in hilly areas; house connections at least 100 mm.", "3.14"],
      ["<b>वेग:</b> आरंभिक peak flow पर कम से कम 0.6 m/s, अंतिम peak flow पर कम से कम 0.8 m/s; अधिकतम 3 m/s",
       "<b>Velocity:</b> at least 0.6 m/s at the initial peak flow, at least 0.8 m/s at the ultimate peak flow; at most 3 m/s.", "Table 3.9, p3-26"],
      ["<b>प्रवाह की गहराई:</b> अंतिम peak flow पर व्यास के 0.8 (d/D ≤ 0.8) तक",
       "<b>Depth of flow:</b> at most 0.8 of the diameter (d/D ≤ 0.8) at the ultimate peak flow.", "3.15.5, p3-28"],
      ["<b>सूत्र:</b> gravity sewers के लिए Manning सूत्र, सामग्री के अनुसार स्थिर n",
       "<b>Formula:</b> Manning's formula for gravity sewers, a constant n by material.", "3.15.4, p3-27; Table 3.11, p3-29"],
      ["<b>न्यूनतम ढाल:</b> 150 mm 1:170; 200 mm 1:250; 250 mm 1:360; 300 mm 1:450; 375 mm 1:670; 450 mm 1:830; 525 mm व अधिक 1:1000",
       "<b>Minimum slopes:</b> 150 mm 1 in 170; 200 mm 1 in 250; 250 mm 1 in 360; 300 mm 1 in 450; 375 mm 1 in 670; 450 mm 1 in 830; 525 mm and above 1 in 1000.", "Table 3.13, p3-31"],
      ["<b>Layout के चरण:</b> (क) outlet / निपटान बिंदु चुनें, (ख) drainage घाटी / zone की सीमाएँ, (ग) trunk और main sewers घाटियों में, (घ) ज़रूरत हो तो pumping station",
       "<b>Layout steps:</b> (a) select the outlet / disposal point, (b) limits of the drainage valley / zonal boundaries, (c) trunk and main sewers in the valleys, (d) pumping stations if necessary.", "3.20.3, p3-41"],
      ["<b>Sub-zone और sewer की जगह:</b> sub-zone की सीमाएँ topography, लागत या व्यावहारिक कारणों से; sewers सड़क / ज़मीन के ढाल की दिशा में; sewer आमतौर पर सड़क के बीच, बहुत चौड़ी सड़क पर दोनों ओर",
       "<b>Sub-zones and sewer location:</b> sub-zone boundaries by topography, economy or other practical considerations; sewers slope with the street / ground; a sewer usually in the centre of the street, on each side in very wide streets.", "3.20.3, p3-41"],
      ["<b>न्यूनतम cover:</b> sanitary sewer की शुरुआत में 1 m",
       "<b>Minimum cover:</b> 1 m at the start of a sanitary sewer.", "3.20.3, p3-41"],
      ["<b>अधिकतम गहराई:</b> ज़मीन से 6 m से अधिक गहराई पर lift station (4.18) लगाकर sewage को 0.9 m cover तक उठाएँ; विशेष स्थिति (जैसे outfall) में अधिक गहराई का DPR में औचित्य",
       "<b>Maximum depth:</b> where depths exceed 6 m below GL, insert lift stations (4.18) lifting sewage to 0.9 m cover; deeper only where justified in the DPR (e.g. an outfall).", "Table 3.15 note, p3-46"],
      ["<b>चट्टानी / पहाड़ी, घनी बसावट:</b> blasting से बचें; सड़क के दोनों ओर उथले sewers या मौजूदा नाली के साथ जुड़वाँ नाली",
       "<b>Rocky / hilly, walled cities:</b> avoid blasting; shallow sewers on both sides of the road, or a twin of the existing drain.", "3.20.7, p3-46"],
      ["<b>Size नहीं घटे:</b> बड़े से छोटे व्यास में बदलाव नहीं; crowns लगातार; जाने वाले sewer का crown आने वाले के crown से ऊँचा नहीं",
       "<b>No reduction in size:</b> no transition from a larger to a smaller diameter; crowns kept continuous; the outgoing crown not higher than the incoming crown.", "3.17.1, p3-34"],
      ["<b>Manhole में drop:</b> size बदले बिना दिशा बदले तो आमतौर पर 30 mm drop; size बदले तो inlet और outlet के crown बराबर",
       "<b>Drop in a manhole:</b> usually 30 mm where the sewer changes direction without a change of size; with a change of size, the crowns of inlet and outlet at the same level.", "3.20.3, p3-42"],
      ["<b>Junction पर:</b> छोटे sewer का soffit (crown) बड़े sewer के soffit से नीचे न हो",
       "<b>At a junction:</b> the soffit (crown) of the smaller sewer not lower than that of the larger one.", "3.26, p3-54"],
      ["<b>Drop manhole:</b> दो sewers के स्तर में 600 mm से अधिक अंतर हो तो drop connection",
       "<b>Drop manhole:</b> a drop connection where the levels of two sewers differ by more than 600 mm.", "p3-53"],
      ["<b>Inverted siphon:</b> न्यूनतम प्रवाह पर 1.0 m/s का self-cleansing वेग",
       "<b>Inverted siphon:</b> a self-cleansing velocity of 1.0 m/s at the minimum flow.", "3.17.7"],
      ["<b>पेयजल से दूरी:</b> sewer पेयजल स्रोत / pipes के पास नहीं; टालना संभव न हो तो sleeve pipe या concrete में बंद",
       "<b>Away from water supplies:</b> sewers not near water supplies; where unavoidable, in sleeve pipes or encased in concrete.", "3.20.3, p3-42"],
      ["<b>ऊँचा भूजल / तटीय क्षेत्र:</b> stoneware या vitrified clay pipe नहीं; CI / DI या non-metallic pipe, ऊपर तैरने से बचाव सहित",
       "<b>High ground water / coastal areas:</b> no stoneware or vitrified clay pipes; CI / DI or non-metallic pipes, safeguarded against flotation.", "3.6, p3-4"],
      ["<b>Manhole कहाँ:</b> हर sewer मिलन पर, दिशा, ढाल या आकार बदलने पर, और नियमित दूरी पर",
       "<b>Manholes:</b> at every sewer junction, at every change of direction, slope or size, and at regular intervals.", "3.20.3, p3-41"],
      ["<b>Manhole की दूरी:</b> सार्वजनिक sewers में 30 m; बड़े trunk / outfall sewers में अधिक (Table 3.31 - pipe table के 'Trunk' कॉलम से चिह्नित करें)",
       "<b>Manhole spacing:</b> 30 m in public sewers; more in large trunk / outfall sewers (Table 3.31 - mark them in the 'Trunk' column of the pipe table).", "3.71.1, 3.71.2, Table 3.31, p3-126, p3-127"],
      ["<b>Manhole पहले:</b> manholes sewer से पहले, ठीक invert तक, pipes के लिए गोल openings छोड़कर बनें; इन्हीं से खाई में pipe का स्तर तय होता है",
       "<b>Manholes first:</b> manholes are built before the sewers, to the required invert with circular openings for the pipes; they then give the levels for laying the pipes in the trench.", "3.21, p3-46; 3.32 (f), p3-58"],
      ["<b>RCC manhole:</b> भीतर sulphide और बाहर sulphate से बचाव - high alumina cement, या sulphate resistant cement के साथ भीतर 25 mm high alumina cement की परत",
       "<b>RCC manholes:</b> against sulphide inside and sulphate outside - high alumina cement, or sulphate resistant cement with a 25 mm lining of high alumina cement inside.", "3.23, p3-46"],
      ["<b>Manhole का base slab:</b> 1 m गहराई तक 150 mm, 1-2 m तक 200 mm, अधिक पर 300 mm; उच्चतम भूजल पर खाली manhole की uplift जाँच",
       "<b>Manhole base slab:</b> 150 mm up to 1 m depth, 200 mm for 1-2 m, 300 mm deeper; checked for uplift of the empty manhole at the highest ground water.", "3.32 (d), p3-57"],
      ["<b>Manhole का जल-परीक्षण:</b> sewer के दोनों सिरे बंद कर पूरी ऊँचाई तक पानी भरें; 24 घंटे में 50 mm से अधिक गिरावट नहीं; खाली कर 24 घंटे भूजल के रिसाव की जाँच",
       "<b>Manhole water test:</b> both sewer ends closed and the manhole filled full height; a drop of not more than 50 mm in 24 hours; emptied and watched 24 hours for ground water leaking in.", "3.32 (m), (n), p3-58"],
      ["<b>Manhole cover:</b> 0.9 m से गहरे manhole में कम से कम 560 mm खुला व्यास; CI cover-frame IS 1726 के अनुसार; ऊपर सड़क के तैयार स्तर के बराबर",
       "<b>Manhole cover:</b> a clear opening of at least 560 mm for manholes deeper than 0.9 m; CI covers and frames to IS 1726; flush with the finished road level.", "3.34, p3-59; 3.32 (o), p3-58"],
      ["<b>Rungs (पायदान):</b> 90 cm से गहरे manhole में; दो पायदानों के बीच ऊर्ध्व दूरी 30 cm से अधिक नहीं",
       "<b>Rungs:</b> in manholes deeper than 90 cm; vertical distance between two rungs not more than 30 cm.", "3.35, p3-59"],
      ["<b>Terminal cleanout:</b> manhole का विकल्प नहीं; केवल उन branch sewers के अंत में जो कभी आगे न बढ़ें, और manhole से 50 m के भीतर",
       "<b>Terminal cleanouts:</b> never a substitute for a manhole; only at the ends of branch sewers that will never be extended, within 50 m of a manhole.", "3.31, p3-57"],
      ["<b>सफ़ाई मशीन से:</b> jet rodding / vacuum suction जैसी यांत्रिक सफ़ाई; manhole में मनुष्य का प्रवेश न हो (scraper manholes बंद)",
       "<b>Mechanised cleaning:</b> jet rodding / vacuum suction machines; no man entry into manholes (scraper manholes discontinued).", "p3-55; 3.35, p3-59"],
      ["<b>घर का connection:</b> crown के ऊपर कम से कम 90 cm मिट्टी; सार्वजनिक sewer का manhole crown पर ज़मीन से 100 cm नीचे शुरू हो",
       "<b>House connection:</b> at least 90 cm of earth over its crown; the public sewer's manhole starts at its crown 100 cm below ground.", "3.70, p3-124"],
      ["<b>Sewer बिछाना:</b> हर manhole के केन्द्र पर खूँटी, उस पर sight rail; pipe का ढाल boning rods से; खाई भरना शुरू होने तक sight rails न हटाएँ",
       "<b>Laying sewers:</b> a peg at the centre of every manhole with a sight rail over it; the pipe gradient by boning rods; sight rails kept until the refilling of the trench has started.", "3.56, p3-97"],
      ["<b>Sewer का जल-परीक्षण:</b> दो manholes के बीच; ऊपरी सिरे के invert से 2.5 m पानी का head; रिसाव 0.2 लीटर / mm व्यास / km / दिन से अधिक नहीं",
       "<b>Sewer water test:</b> between manholes; a head of 2.5 m above the invert at the upper end; leakage not more than 0.2 litres / mm dia. / km / day.", "3.61.1, p3-103"],
      ["<b>Pumping station की जगह:</b> इलाके के सबसे निचले बिंदु के पास; कभी न डूबे - plinth और wet well का ऊपरी स्तर 100 वर्ष की बाढ़ से 0.45 m ऊपर; चारों ओर ditch drain",
       "<b>Pumping station site:</b> near the lowest point of the area; never flooded - plinth and top of the wet well 0.45 m above the 1-in-100-year flood; a ditch drain all around.", "4.1.2, p4-1, p4-2"],
      ["<b>Suction स्तर:</b> आने वाले sewer के invert से 50-100 cm नीचे, ताकि sewer में गाद न रुके",
       "<b>Suction level:</b> 50-100 cm below the invert of the incoming sewer, so that sediments do not settle in the sewer.", "4.1.4, p4-3"],
      ["<b>Pumping main:</b> दबाव वाले प्रवाह के लिए Hazen-Williams सूत्र; turbulent प्रवाह ताकि ठोस न बैठें",
       "<b>Pumping main:</b> the Hazen-Williams formula for flow under pressure; turbulent flow so that solids do not settle.", "3.16, p3-32"],
      ["<b>Pumping main का वेग और HGL:</b> 0.6-2.4 m/s; 600 m से छोटे और 10 m से कम lift वाले mains में 1.8-2.7 m/s; HGL सबसे ऊँची ज़मीन / pipe के crown से कम से कम 1 m ऊपर",
       "<b>Pumping main velocity and HGL:</b> 0.6-2.4 m/s; 1.8-2.7 m/s for mains shorter than 600 m with a lift under 10 m; the HGL at least 1 m above the highest ground / crown of the main.", "4.20.3, p4-28; 4.1.5, p4-3"],
      GSEC_ME,
      ["<b>Pumps की संख्या:</b> छोटे station में 3 pumps - 1, 2 और 3 DWF; बड़े में 5 - दो ½ DWF, दो 1 DWF, एक 3 DWF (standby सहित); या DWF के गुणक में pumps और peak के लिए 100% standby",
       "<b>Number of pumps:</b> small stations 3 pumps - 1, 2 and 3 DWF; large ones 5 - two of ½ DWF, two of 1 DWF, one of 3 DWF (including standby); or pumps in multiples of DWF with 100% standby for the peak.", "4.5.4, p4-8"],
      ["<b>Pump का प्रकार:</b> suction lift लगभग 3-5 m हो तो horizontal foot-mounted centrifugal (स्थानीय मरम्मत आसान); जगह कम हो तो submersible; screw (Archimedean) pump की दक्षता केवल लगभग 25%",
       "<b>Type of pump:</b> horizontal foot-mounted centrifugal pumps for suction lifts of about 3-5 m (easy local repairs); submersibles where space is short; Archimedean screw pumps only about 25% efficient.", "4.5.5, p4-8"],
      ["<b>Pump का kW:</b> Q (L/s) × H (m) / 100.5 / pump efficiency; motor के लिए इसे 0.9 से भाग दें",
       "<b>Pump kW:</b> Q (L/s) × H (m) / 100.5 / pump efficiency; divided by 0.9 for the motor.", "4.20.2, p4-27"],
      ["<b>Wet well:</b> कम से कम दो (या दो खाने); आयतन V = T × Q / 4, T = 10-15 मिनट (एक pump cycle), एक घंटे में 6 से अधिक starts नहीं; submersible pump न्यूनतम स्तर पर पूरा डूबा",
       "<b>Wet well:</b> at least two (or two compartments); volume V = T × Q / 4 with T = 10-15 minutes (one pump cycle), not more than 6 starts an hour; submersibles fully submerged at the minimum level.", "4.1.2, p4-2; 4.6, p4-8; 4.6.6, p4-10"],
      ["<b>Gate, screen और grit:</b> wet well में sewer के प्रवेश पर penstock gate; यांत्रिक travelling screen ताकि मनुष्य को अंदर न जाना पड़े (बड़े station में coarse + fine); grit अलग well में हटाएँ",
       "<b>Gate, screens and grit:</b> a penstock gate where the sewer enters the wet well; a mechanised travelling screen so that no man enters (coarse + fine in large stations); grit removed in a separate well.", "4.2.1, 4.2.2, 4.2.4, p4-3, p4-4"],
      ["<b>स्वचालन और alarm:</b> ultrasonic / submersible level controller, high / low level alarm और backup float switch; PLC से pumps का क्रम से चलना / बंद होना; dry running और motor के तापमान पर alarm (4-20 mA signal)",
       "<b>Automation and alarms:</b> ultrasonic / submersible level controller, high / low level alarms and backup float switches; PLCs bring pumps in and out in sequence; alarms for dry running and motor temperature (4-20 mA signals).", "4.6.6, p4-11; 4.12.5, 4.14, p4-22"],
      ["<b>बिजली:</b> नज़दीकी substation से dedicated feeder; बड़े station में दो अलग substations से दो feeders (1 MLD DWF से छोटे में पास की line); standby DG, AMF panel से - mains 70-80% से नीचे गिरे तो अपने-आप चालू",
       "<b>Power:</b> a dedicated feeder from the nearby substation; two feeders from two substations for large stations (a nearby line for less than 1 MLD DWF); a standby DG with an AMF panel starting by itself when mains drops below 70-80%.", "4.1.6, p4-3; 4.13; 5.12.5.1, p5-138"],
      ["<b>विद्युत सुरक्षा:</b> सभी उपकरण insulated और earthed, switches non-sparking, खतरनाक जगहों पर explosion-proof; wet well में junction box नहीं, float cables ढके case में",
       "<b>Electrical safety:</b> all equipment insulated and earthed, non-sparking switches, explosion-proof in hazardous areas; no junction boxes in the wet well, float cables in a covered case.", "4.1.3 (8), p4-2; 4.6, p4-8"],
      ["<b>Control room और ventilation:</b> switch / control gear के लिए अलग हवादार कमरा, दो रास्ते, लगभग 4.5 m ऊँचा, लकड़ी नहीं; pump station में कम से कम 10 air changes / घंटा, positive pressure, filtered हवा; भारी उपकरण के लिए gantry",
       "<b>Control room and ventilation:</b> a dedicated ventilated room for switch / control gear with two exits, about 4.5 m high, no timber; at least 10 air changes per hour in the station, positive pressure, filtered air; gantries for heavy equipment.", "4.3, p4-5; 4.6.5, p4-9; 4.1.3 (10), p4-3"],
      ["<b>Surge और valves:</b> delivery head pipeline की क्षैतिज लंबाई के 25% से अधिक हो तो surge analysis; सब piping पर safety factor 1.5; soft starter और dashpot / spring-check NRV; DI / CI piping, stainless steel fasteners; check valve के पास air valve",
       "<b>Surge and valves:</b> a surge analysis where the delivery head exceeds 25% of the horizontal length of the main; a safety factor of 1.5 on all piping; soft starters and dashpot / spring-check NRVs; DI / CI piping, stainless steel fasteners; air valves close to the check valve.", "4.10, p4-20, p4-21; 4.11, 4.12.1, 4.16, p4-21, p4-23"],
    ] },
};
function showGuide() {
  const g = GUIDE.sewer;
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
  const O = { name: "water", port: 8766, page: "/water", win: "water_network_design", hi: "पेयजल", en: "Water" };
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
