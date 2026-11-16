// The sewer app's full guide (user request 16-Nov-2026): step by step how to design with the app - per tab the order
// of work, then every field: what to give, why, where it comes from, its default and its reference (CPHEEO Manual on
// Sewerage and Sewage Treatment Systems 2013 Part A, printed pages "p3-26" = chapter-page; UPJN = U.P. Jal Nigam rule
// / practice; Reference DPR = the DPRs the app follows, their names mocked; App = a decision of the project where the
// manual gives no figure). Rendered by guide.html (/guide); the tour's steps (tour.js) at the end.
{   // helpers kept in this block: the map page loads this file too (the tour)
const F = (hi, en, what, why, from, def, ref) => ({ hi, en, what, why, from, def, ref, adv: false });
const A = (...a) => Object.assign(F(...a), { adv: true });
const T = (hi, en) => ({ hi, en });

var GUIDE_DOC = {
  module: "sewer",
  title: T("सीवर network design - पूरी मार्गदर्शिका", "Sewer network design - the full guide"),
  sub: T("नक्शे या DXF से sewer network, आबादी, zoning options (pumping stations), हर sewer का design, drawings और DPR - चरण-दर-चरण",
         "From a map or a DXF to the sewer network, population, zoning options (pumping stations), every sewer's design, drawings and the DPR - step by step"),
  refnote: T("Ref: \"p3-26\" = CPHEEO Manual on Sewerage and Sewage Treatment Systems (2013) Part A का छपा पृष्ठ (अध्याय-पृष्ठ); UPJN = उत्तर प्रदेश जल निगम का नियम / practice; Reference DPR = वे DPR जिनके format पर app बना (नाम काल्पनिक); App = जहाँ manual कोई अंक नहीं देता वहाँ का project-निर्णय।",
             "Ref: \"p3-26\" = printed page (chapter-page) of the CPHEEO Manual on Sewerage and Sewage Treatment Systems (2013) Part A; UPJN = a U.P. Jal Nigam rule / practice; Reference DPR = the DPRs the app follows (names mocked); App = a project decision where the manual gives no figure."),
  chapters: [
    { id: "start", title: T("शुरू करने से पहले", "Before you start"),
      text: [
        T("App एक design सहायक है: हर नतीजा tender / निर्माण से पहले योग्य engineer से जँचवाएँ।", "The app is a design aid: have a qualified engineer check every result before tender / construction."),
        T("काम का क्रम ऊपर के tabs जैसा है: 1 Project → 2 Network → 3 आबादी → 4 Zoning → 5 Network Design → 6 Outputs। जो चरण अभी नहीं पहुँचा, उसका tab धुँधला रहता है।",
          "The order of work is that of the tabs at the top: 1 Project → 2 Network → 3 Population → 4 Zoning → 5 Network Design → 6 Outputs. A step not reached yet has a dimmed tab."),
        T("Simple / Advanced: Simple में सिर्फ़ ज़रूरी खाने, बाकी CPHEEO / project के default पर (इस guide में \"Advanced\" लिखे खाने)।",
          "Simple / Advanced: Simple shows the essential fields, the rest at the CPHEEO / project defaults (fields marked \"Advanced\" in this guide)."),
      ],
      need: [
        T("सड़कों का नक्शा (KML) या मौजूदा sewer network की DXF (sewer layers, manhole / GL texts)।", "The roads (KML) or a DXF of the existing sewer network (sewer layers, manhole / GL texts)."),
        T("ज़मीन का स्तर (GL): total station के spot levels या DXF के GL - sewer की ढाल और गहराई इन्हीं पर।", "Ground levels (GL): total station spot levels or the DXF's GLs - the sewers' slope and depth rest on them."),
        T("आबादी: वार्ड-वार (नगर निकाय), census (projection के लिए)।", "Population: ward by ward (ULB), census (for the projection)."),
        T("STP / outfall की जगह और उसका स्तर; नदी / नाला, रेल, highway (रुकावटें)।", "The STP / outfall site and its level; rivers / drains, railway, highways (barriers)."),
      ] },

    { id: "project", title: T("1. Project", "1. Project"),
      steps: [
        T("\"नाम\" में project का नाम लिखें और \"सहेजें\"; पहले से बना हो तो सूची से \"खोलें\"।", "Type the project's name in \"Name\" and \"Save\"; an existing one: \"Open\" from the list."),
        T("Google Earth का नक्शा: \"KML/KMZ खोलें…\"; मौजूदा network की drawing: \"DXF network…\"।", "A Google Earth map: \"Open KML/KMZ…\"; a drawing of the existing network: \"DXF network…\"."),
      ],
      fields: [
        F("नाम", "Name", T("Project का नाम", "The project's name"), T("उसी नाम से project और output folder", "The project and its output folder by this name"), T("आप", "You"), "new_project", "App"),
        F("KML/KMZ खोलें…", "Open KML/KMZ…", T("सड़कें, boundary, वार्ड (आबादी), spot levels, STP", "Roads, boundary, wards (population), spot levels, STP"), T("नक्शा हाथ से खींचने की जगह", "Instead of drawing by hand"), T("Google Earth / survey", "Google Earth / survey"), "-", "App; samples\\sample_area.kml"),
        F("DXF network…", "DXF network…", T("मौजूदा sewer network की drawing", "A drawing of the existing sewer network"), T("बने / survey किए network पर design", "To design on a network already drawn / surveyed"), T("Consultant की DXF", "The consultant's DXF"), "-", "App"),
      ] },

    { id: "network", title: T("2. Network - नक्शा, DXF, जाँच, Layout", "2. Network - map, DXF, checks, layout"),
      steps: [
        T("(A) नक्शे पर: सड़कें (centreline), Project boundary, वार्ड + population, Spot level (GL), STP / outfall खींचें → \"Layout बनाएँ\": सड़कों के साथ sewers और manholes।",
          "(A) On the map: draw the roads (centreline), project boundary, wards + population, spot levels (GL), STP / outfall → \"Make layout\": sewers and manholes along the roads."),
        T("(B) DXF: \"📂 चुनें…\" → \"Layers पढ़ें\" → sewer / manhole / GL layers → Coordinates → \"Network निकालें\" → गड़बड़ियाँ सुधारें (या \"अपने-आप सुधार\")।",
          "(B) DXF: \"📂 Choose…\" → \"Read layers\" → sewer / manhole / GL layers → coordinates → \"Extract network\" → correct the problems (or \"Auto repair\")."),
        T("रुकावट रेखा (नदी, रेल, highway), crossing, zone लूप से zoning को दिशा दें।", "Guide the zoning by barrier lines (river, railway, highway), crossings and zone loops."),
      ],
      fields: [
        F("सड़क (centreline)", "Road (centreline)", T("हर सड़क की बीच-रेखा", "Every road's centre line"), T("Sewers सड़कों के साथ", "The sewers follow the roads"), T("Satellite / survey", "Satellite / survey"), "-", "App"),
        F("वार्ड + population", "Ward + population", T("वार्ड का घेरा और आबादी", "A ward's outline and population"), T("आबादी उसके manholes पर - sewage का प्रवाह", "Its population on its manholes - the sewage flow"), T("नगर निकाय", "ULB"), "-", "CPHEEO 3.3 p3-2"),
        F("Spot level (GL)", "Spot level (GL)", T("ज़मीन का स्तर (m)", "Ground level (m)"), T("हर manhole का GL - sewer की ढाल, cover और गहराई", "Every manhole's GL - the sewers' slope, cover and depth"), T("Total station", "Total station"), "-", "CPHEEO 3.70 p3-124 (cover)"),
        F("STP / outfall", "STP / outfall", T("STP या outfall का बिंदु", "The STP or outfall point"), T("सब sewers का अंतिम सिरा", "Where all the sewers end"), T("DPR / नगर निकाय", "DPR / ULB"), "-", "App"),
        F("रुकावट रेखा / Crossing / Zone लूप", "Barrier / crossing / zone loop", T("कोई sewer पार नहीं करता / पार की अनुमति / घेरा एक zone", "No sewer crosses / a crossing allowed / an enclosed zone"),
          T("Zones प्राकृतिक सीमाओं पर", "Zones on natural limits"), T("नक्शा", "The map"), "-", "App"),
        F("GL कहाँ से", "GL from", T("Spot levels (TIN), समतल GL, या बाद में", "Spot levels (TIN), a flat GL, or later"), T("समतल GL सिर्फ़ मोटा अनुमान", "A flat GL is a rough estimate only"), T("Survey", "Survey"), "Spot levels", "App"),
        F("Manhole दूरी (m)", "Manhole spacing (m)", T("Layout में manholes की दूरी", "The manholes' spacing in the layout"), T("घरों के connection - CPHEEO 30 m", "House connections - CPHEEO 30 m"), "-", "30", "CPHEEO 3.71.1 p3-126"),
        F("सिरे जोड़ें (m)", "Join ends (m)", T("इतने पास के सिरे एक manhole", "Ends this close become one manhole"), T("खींचने की छोटी चूक", "Small slips of drawing"), "-", "1", "App"),
      ],
      mistakes: [
        T("STP / outfall न हो तो हर हिस्से का सबसे नीचा manhole outlet बनता है।", "Without an STP / outfall each part's lowest manhole becomes its outlet."),
      ] },

    { id: "pop", title: T("3. आबादी - stages और forecast", "3. Population - stages and forecast"),
      text: [
        T("Sewers, pumping mains और pumping station (civil) 30 वर्ष (+30) के लिए; pumping machinery और STP 15 वर्ष (+15) के लिए - CPHEEO Table 2.1 p2-9।",
          "Sewers, pumping mains and pumping stations (civil) for 30 years (+30); pumping machinery and the STP for 15 years (+15) - CPHEEO Table 2.1 p2-9."),
      ],
      fields: [
        F("Population (कुल)", "Population (total)", T("Design (अंतिम वर्ष) की कुल आबादी", "The design (ultimate) year's total"), T("वार्ड न हों तो manholes पर बँटती है", "Spread over the manholes when there are no wards"), T("DPR", "DPR"), "-", "CPHEEO 3.3 p3-2"),
        A("Stage: आधार वर्ष", "Stage: base year", T("Design का आधार वर्ष", "The design's base year"), T("+15 / +30 वर्ष इसी से", "+15 / +30 years from it"), T("DPR का वर्ष", "The DPR's year"), "2027", "CPHEEO Table 2.1 p2-9"),
        A("आधार वर्ष की आबादी", "Base-year population", T("पूरे project की आबादी (floating के बिना)", "The whole project's population (without floating)"), T("+15 / +30 और floating इसी से", "+15 / +30 and floating from it"), T("नगर निकाय / census", "ULB / census"), T("वार्ड हों तो खाली", "empty with wards"), "CPHEEO 3.3"),
        A("Census आबादी (वर्ष आबादी)", "Census (year population)", T("दशक-वार census", "Census by decade"), T("Arithmetical, incremental, geometrical increase", "Arithmetical, incremental, geometrical increase"), T("Census of India", "Census of India"), T("खाली = 28.74 % प्रति दशक", "empty = 28.74 % per decade"), "CPHEEO Annexure; Reference DPR"),
        A("Forecast का तरीका", "Forecast method", T("+15 / +30 का तरीका", "The +15 / +30 method"), "-", "-", "Geometrical", "Reference DPR"),
        A("Floating आबादी (%)", "Floating population (%)", T("Floating / institutional, आबादी का %", "Floating / institutional, % of the population"), T("45 / (sewage ÷ 0.8) के बराबर आबादी जुड़ती है", "Adds a population of 45 / (sewage ÷ 0.8)"), T("Survey; reference", "Survey; reference"), "10 %", "Reference DPR; CPHEEO Annexure 2.8: 1-3 %"),
      ] },

    { id: "zoning", title: T("4. Zoning - settings और options", "4. Zoning - settings and options"),
      text: [
        T("App network को zones में बाँटने के कई options देता है: zones, pumping stations (PS), गहराई, pipe लागत, कुल अनुमानित लागत (PS, O&M, rising main; STP सब में बराबर, इसलिए नहीं)। ★ GIVEN = सिर्फ़ दिए outfalls पर; ⚠ = project की गहराई-सीमा से गहरा।",
          "The app offers several options for the zones: zones, pumping stations (PS), depth, pipe cost, total estimated cost (PS, O&M, rising main; the STP is the same in all, so not in it). ★ GIVEN = the given outfalls only; ⚠ = deeper than the project's depth limit."),
      ],
      steps: [
        T("Pipe catalog, joint, sewage, start depth, STP manhole भरें; \"Zoning options निकालें\"।", "Give the pipe catalog, joint, sewage, start depth, STP manhole; \"Zoning options\"."),
        T("तालिका की पंक्ति पर click = वह option नक्शे पर; चुनें और \"Network Design\" tab।", "Click a row = that option on the map; choose one and go to \"Network Design\"."),
        T("\"⇩ Export: DXF + KML + Excel\": चुने option के zones / sub-zones।", "\"⇩ Export: DXF + KML + Excel\": the chosen option's zones / sub-zones."),
      ],
      fields: [
        F("Pipe catalog / Joint", "Pipe catalog / joint", T("Pipes की सूची (sizes, internal dia, Manning n, rates) और joint", "The pipe list (sizes, internal dia, Manning n, rates) and the joint"), T("Diameter, Manning n, लागत", "Diameter, Manning n, cost"), "data/sewer_catalog.json", "ss", "CPHEEO Table 3.11 p3-29"),
        A("Sewage (L/व्यक्ति/दिन)", "Sewage (L/person/day)", T("जल आपूर्ति x return factor (135 x 0.8 = 108)", "Water supply x return factor (135 x 0.8 = 108)"), T("Sewage का प्रवाह", "The sewage flow"), T("जल आपूर्ति का मान", "The water supply rate"), "108", "CPHEEO 3.5 p3-3 (कम से कम 100)"),
        A("Start depth (m)", "Start depth (m)", T("सबसे ऊपरी manhole पर invert तक गहराई", "Depth to invert at the top manhole"), T("Cover - घर का connection और भार", "Cover - house connections and loads"), "-", "0.7", "CPHEEO 3.70 p3-124"),
        F("STP manhole", "STP manhole", T("STP का manhole (नक्शे के STP से अपने-आप)", "The STP's manhole (from the map's STP by itself)"), T("जहाँ सब sewers पहुँचें", "Where all the sewers arrive"), T("नक्शा", "The map"), "-", "App"),
        A("Design का तरीका", "Design mode", T("स्वतंत्र (गहराई पर PS अपने-आप) / केवल दिए outfalls पर", "Free (PS by depth) / only the given outfalls"), T("Pumping stations कहाँ", "Where the pumping stations go"), "-", T("स्वतंत्र", "free"), "App"),
        A("अधिकतम गहराई (m)", "Maximum depth (m)", T("इससे गहरे sewer से पहले pumping station", "A pumping station before a sewer deeper than this"), T("खुदाई की लागत और सुरक्षा", "Excavation cost and safety"), T("Project निर्णय", "Project decision"), "10", "CPHEEO Table 3.15 note p3-46 (6 m); 10 m App"),
        A("मोड़ पर 30 mm drop", "30 mm drop at bends", T("एक ही size का sewer 10° से अधिक मुड़े तो", "Same-size sewer turning more than 10°"), T("Manhole में head loss", "The head loss in the manhole"), "-", T("चालू", "on"), "CPHEEO 3.20.3 p3-42"),
        A("Manholes की अधिकतम दूरी (m)", "Maximum manhole spacing (m)", T("घरों के connection वाले sewers में", "In sewers with house connections"), T("House sewer 3-15 m; सफ़ाई", "House sewers 3-15 m; cleaning"), "-", "30", "CPHEEO 3.71.1 p3-126"),
        A("मोड़ पर manhole (°)", "Manhole at bends (°)", T("इतने ° या अधिक के मोड़ पर नया manhole", "A new manhole at a bend of this or more"), T("मोड़ पर सफ़ाई", "Cleaning at bends"), "-", "20", "CPHEEO 3.71 p3-125; कोण App"),
        A("ज़मीन की ढलान से अधिकतम zones", "Maximum zones by the ground", T("पहले इतने zones तक के options", "Options up to this many zones first"), T("Options की संख्या", "The number of options"), "-", "8", "App"),
      ],
      results: [
        T("Options तालिका: zones, PS, अधिकतम गहराई, pipe लागत, कुल लागत; पंक्ति पर click = नक्शे पर (हर zone का रंग, STP / PS, कटे sewers dashed)। GL band map: reference GL से ऊँचाई के रंग।",
          "Options table: zones, PS, maximum depth, pipe cost, total cost; click a row = on the map (each zone's colour, STP / PS, cut sewers dashed). GL band map: height above the reference GL in colours."),
      ] },

    { id: "design", title: T("5. Network Design - हर sewer", "5. Network Design - every sewer"),
      text: [
        T("चुना option: हर sewer का diameter, ढाल, invert, गहराई - Manning (स्थिर n), आरंभिक peak पर ≥ 0.6 m/s, अंतिम peak पर ≥ 0.8 m/s, अधिकतम 3 m/s, d/D ≤ 0.8, peak factor (Table 3.2), infiltration, न्यूनतम ढाल (Table 3.13), size downstream में कम नहीं, crowns लगातार; फिर pipe sizes घटाने वाला pass।",
          "The chosen option: each sewer's diameter, slope, invert, depth - Manning (constant n), ≥ 0.6 m/s at the initial peak, ≥ 0.8 m/s at the ultimate peak, 3 m/s at most, d/D ≤ 0.8, peak factor (Table 3.2), infiltration, minimum slopes (Table 3.13), no smaller size downstream, crowns matched; then a pass making pipes smaller."),
      ],
      steps: [
        T("\"Design\" दबाएँ; नतीजे और जाँचें पढ़ें।", "Press \"Design\"; read the results and checks."),
        T("\"☷ Pipe / manhole तालिका\": size / invert बदलकर \"बदलाव के साथ design दोबारा\"।", "\"☷ Pipe / manhole table\": change a size / invert and \"design again with the changes\"."),
      ],
      fields: [F("Design", "Design", T("चुने zoning option का design", "The design of the chosen zoning option"), T("Report, DPR, plan और L-section", "The report, DPR, plan and L-section"), "-", "-",
        "CPHEEO Table 3.2, 3.9, 3.13 p3-3-p3-31; 3.15.5, 3.17.1, 3.20.3")],
      results: [
        T("नक्शे पर sewers diameter के रंग में; tooltip में size, slope, Q, v, गहराई, flags। Files: design report, DPR (47 sheets), plan DXF, L-section DXF - Outputs tab में।",
          "Sewers coloured by diameter on the map; the tooltip gives size, slope, Q, v, depth, flags. Files: design report, DPR (47 sheets), plan DXF, L-section DXF - in the Outputs tab."),
      ],
      mistakes: [
        T("बहुत गहरे sewers: अधिकतम गहराई / design का तरीका देखें - स्वतंत्र तरीका PS जोड़ता है।", "Very deep sewers: see the maximum depth / design mode - the free mode adds pumping stations."),
      ] },

    { id: "out", title: T("6. Outputs - सब files एक जगह", "6. Outputs - every file in one place"),
      text: [
        T("Outputs tab: project के output folder का रास्ता और \"📁 Folder खोलें\"; हर output (layout, zoning options की files, चुने option का export, design report, DPR, plan, L-section) - \"बनाएँ / फिर बनाएँ\" या \"चरण पर जाएँ\", आख़िरी file, \"खोलें\", 📁; पुरानी files नीचे।",
          "The Outputs tab: the project's output folder (path, \"📁 Open the folder\"); each output (layout, the zoning options' files, the chosen option's export, design report, DPR, plan, L-section) - \"Make / make again\" or \"Go to the step\", the newest file, \"Open\", 📁; the older files below."),
        T("Sewer DPR (47 sheets): project, coverage, certificate, Form J, abstracts, O&M, economics, BOQ, manholes, hydraulic statement, house connections, pumping station (E&M, wet well, screen, rising main), HT / LT, SOR - UPJN SOR 2025-26।",
          "The sewer DPR (47 sheets): project, coverage, certificate, Form J, abstracts, O&M, economics, BOQ, manholes, hydraulic statement, house connections, pumping station (E&M, wet well, screen, rising main), HT / LT, SOR - UPJN SOR 2025-26."),
      ] },
  ],
};

// the tour (tour.js): what each part of the page is for, in order; sel = the element shown, tab = the tab opened first
var TOUR_STEPS = [
  { sel: "#title", hi: ["सीवर network design", "नक्शे या DXF से sewer network, zoning options, हर sewer का design, drawings और DPR - CPHEEO के अनुसार। \"छोड़ें\" से कभी भी बंद।"],
    en: ["Sewer network design", "From a map or DXF to the sewer network, zoning options, every sewer's design, drawings and the DPR - to CPHEEO. \"Skip\" closes it any time."] },
  { sel: "#uimode", hi: ["Simple / Advanced", "Simple: सिर्फ़ ज़रूरी खाने, बाकी default पर। Advanced: सब विकल्प।"], en: ["Simple / Advanced", "Simple: the essential fields, the rest at the defaults. Advanced: every option."] },
  { sel: "#uitheme", hi: ["रंग", "हल्का, गहरा या Windows जैसा।"], en: ["Colours", "Light, dark or as Windows."] },
  { sel: "#uitabs", hi: ["काम के चरण", "Project → Network → आबादी → Zoning → Network Design → Outputs।"], en: ["The steps of the work", "Project → Network → Population → Zoning → Network Design → Outputs."] },
  { sel: "#pname", tab: "project", hi: ["Project", "नाम, सहेजें / खोलें, KML / DXF लाएँ।"], en: ["Project", "Name, save / open, bring a KML / DXF."] },
  { sel: "#kmlsec .tools", tab: "network", hi: ["नक्शे पर खींचें", "सड़कें, boundary, वार्ड, spot levels, STP; फिर \"Layout बनाएँ\"।"], en: ["Draw on the map", "Roads, boundary, wards, spot levels, STP; then \"Make layout\"."] },
  { sel: "#poptot", tab: "pop", hi: ["आबादी", "कुल आबादी या वार्डों से; Advanced में stages और forecast।"], en: ["Population", "The total or from the wards; stages and forecast in Advanced."] },
  { sel: "#zrun", tab: "zoning", hi: ["Zoning options", "Zones और pumping stations के विकल्प, उनकी लागत; एक चुनें।"], en: ["Zoning options", "Options of zones and pumping stations, their cost; choose one."] },
  { sel: "#drun", tab: "design", hi: ["Network Design", "हर sewer का size, ढाल, गहराई; report, DPR, plan, L-section।"], en: ["Network Design", "Each sewer's size, slope, depth; report, DPR, plan, L-section."] },
  { sel: "#outlist", tab: "out", hi: ["Outputs", "सब files एक जगह: बनाएँ, खोलें, folder में देखें।"], en: ["Outputs", "Every file in one place: make, open, show in its folder."] },
  { sel: "#uihelp", hi: ["मदद", "❓ = इस चरण की पूरी मार्गदर्शिका; ▶ = यह tour फिर; 📘 CPHEEO = मुख्य मानक।"], en: ["Help", "❓ = this step's full guide; ▶ = this tour again; 📘 CPHEEO = the main norms."] },
];
}
