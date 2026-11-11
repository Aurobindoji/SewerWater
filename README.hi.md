# सीवर और पेयजल Network Design - उपयोग पुस्तिका (हिन्दी)

[English README](README.md)

यह app नगरों के **सीवर (sewerage)** और **पेयजल वितरण (water supply)** network की योजना और design CPHEEO
manuals के अनुसार करता है - नक्शे या CAD drawing से शुरू करके design report, DXF drawings और Excel में DPR
तक। SewerGEMS या WaterGEMS की ज़रूरत नहीं।

> **Beta (v0.9.4).** यह app design में सहायता के लिए है। Tender या निर्माण से पहले हर नतीजा योग्य engineer से
> जँचवाएँ - ख़ास तौर पर Intze टंकियों का structural design।

इस पुस्तिका में:

1. [Install और पहली बार शुरू करना](#1-install-और-पहली-बार-शुरू-करना)
2. [App की बनावट - दो स्वतंत्र apps](#2-app-की-बनावट---दो-स्वतंत्र-apps)
3. [दोनों apps में साझा चरण - project, नक्शा, DXF](#3-दोनों-apps-में-साझा-चरण)
4. [सीवर app - चरण-दर-चरण](#4-सीवर-app---चरण-दर-चरण)
5. [पेयजल app - चरण-दर-चरण](#5-पेयजल-app---चरण-दर-चरण)
6. [Output files और DPR](#6-output-files-और-dpr)
7. [मानक और स्रोत - कौन-सा मान कहाँ से](#7-मानक-और-स्रोत---कौन-सा-मान-कहाँ-से)
8. [Update, About, data folder](#8-update-about-data-folder)
9. [Source से चलाना (developers)](#9-source-से-चलाना)

---

## 1. Install और पहली बार शुरू करना

**ज़रूरी:** Windows 10 या 11 (64-bit); Microsoft Edge WebView2 (Windows 11 में पहले से; न हो तो setup उसे
internet से install करता है); नक्शे की पृष्ठभूमि (map tiles) के लिए internet - बाकी सब काम offline।

1. [Releases](../../releases) पन्ने से `SewerWater_Setup_0.9.4.exe` download करें।
2. उसे चलाएँ। Setup सिर्फ़ आपके user account के लिए install होता है - administrator की ज़रूरत नहीं।
3. Setup पर digital signature नहीं है; Windows SmartScreen रोके तो **More info → Run anyway**।
4. पहली बार खुलने पर **master folder** चुनें - सारा data इसी में रहता है (भाग 8)।
5. फिर start page: **भाषा** (हिन्दी / English), फिर **सीवर** या **पेयजल**।

Uninstall करने पर आपका data folder नहीं हटता।

## 2. App की बनावट - दो स्वतंत्र apps

- **Start page** (launcher): भाषा, फिर module। जो चुनें, सिर्फ़ वही module शुरू होकर उसी window में खुलता है।
- **सीवर app** और **पेयजल app** पूरी तरह अलग हैं - अपना code, अपना data folder, अपनी settings। एक को खोलने
  से दूसरा शुरू नहीं होता।
- हर app में ऊपर: **📘 CPHEEO** (मुख्य design मानकों का सारांश, पन्नों के हवाले सहित), **🌐 English / हिन्दी**
  (इसी पन्ने की भाषा बदलें) और **↗ पेयजल / ↗ सीवर** (दूसरा app अपनी window में खोलें - वह तभी शुरू होता है;
  पहले से खुला हो तो उसकी window आगे आ जाती है, उसका काम नहीं मिटता)।
- Menu **App**: master folder खोलें / बदलें, **Update देखें**, **About**।

## 3. दोनों apps में साझा चरण

### 3.1 Project
- **Project नाम** भरें → **सहेजें**: project `projects\<नाम>.kml` में Google Earth वाले format में सहेजा जाता है।
- **खोलें**: सहेजे हुए projects की सूची से। **KML download**: नक्शे की सब चीज़ें एक KML में।
- **KML/KMZ खोलें…**: Google Earth में बनी file - सड़कें (paths), boundary, वार्ड (polygons, आबादी सहित),
  spot levels, STP / OHT आदि अपने-अपने folder से पहचाने जाते हैं। उदाहरण: `samples\sample_area.kml`।
- **नया (सब हटाएँ)**: नक्शा खाली।

### 3.2 नक्शे पर खींचना
**खींचें** बटनों से: सड़कें (centreline), project **Boundary**, **वार्ड** (आबादी, Ward No.), **spot levels (GL)**;
सीवर में **STP**; पेयजल में **पुरानी टंकी / नई टंकी (OHT / ESR)**, **Bulk consumer**, **नया tube well**, **PRV**।
Zoning के औज़ार: **रुकावट रेखा** (नदी, रेल, highway - कोई pipe इसे पार नहीं करता), **Crossing** (रुकावट के
आर-पार जाने की अनुमति वाली जगह), **Zone लूप** (क्षेत्र को घेरकर एक zone बनाना)।

- **पूरा करें (Enter)**, **पिछला बिंदु हटाएँ (Ctrl+Z)**, **रोकें (Esc)**; किसी वस्तु पर click → **✎ बदलें / हटाएँ**।
- सड़क का सिरा दूसरी सड़क के 12 pixel के भीतर छोड़ें तो उस पर जुड़ जाता है।
- नक्शे की पृष्ठभूमि: Google Map (default), OSM, Esri satellite; अपनी WMS layer भी जोड़ सकते हैं।

### 3.3 DXF से network (मौजूदा drawing)
1. **DXF network…** → **📂 चुनें…** से DXF file।
2. **Layers पढ़ें**: pipe / manhole (या junction) layers सुझाए जाते हैं; GL खाली छोड़ें तो अपने-आप।
3. **Coordinates**: drawing का coordinate system (जैसे UTM 44N); नक्शे के बिना काम हो तो "Local"।
4. **Network निकालें**। गड़बड़ियाँ समूहों में दिखती हैं - label नहीं, GL नहीं, GL spike, gap, बिना outfall का हिस्सा
   आदि; पंक्ति पर click → उस जगह पर।
5. सुधार के औज़ार: नाम / GL बदलना, खिसकाना ("यहाँ रखें"), जोड़ना, तोड़ना, हटाना, **↶ Undo**, **अपने-आप सुधार**,
   **Drawing के GL लगाएँ** (पास लिखे GL texts से), पेयजल में **कटे loops फिर जोड़ें**। जिन manholes का label नहीं
   मिला, उनके लिए पास का label और GL सुझाया जाता है - **सब सुझाव लागू करें**।
6. हर बदलाव `output\<नाम>\<नाम>_network_edits.csv` में दर्ज होता है।

## 4. सीवर app - चरण-दर-चरण

### 4.1 Layout (सड़कों से network)
सड़कें, boundary, वार्ड (आबादी) और GL खींचकर / KML से लाकर **Layout बनाएँ**: सड़कों के साथ sewers और manholes
बनते हैं ("सिरे जोड़ें (m)" - इतने पास के सिरे जुड़ जाते हैं)। GL कहाँ से: drawing / KML के spot levels (TIN
interpolation) या समतल GL। वार्डों की आबादी उनके manholes पर बँटती है। हर layout **PFR** स्तर का है।

### 4.2 Zoning और design के inputs
- **Pipe catalog** और **Joint**, **Sewage (L/व्यक्ति/दिन)** (default 108; कम से कम 100 - CPHEEO 3.5),
  **Start depth (m)** (default 0.7), **STP manhole** (KML के STP बिंदु से अपने-आप), **ज़मीन की ढलान से अधिकतम
  zones**, **अधिकतम गहराई (m)** (इससे गहरे sewer से पहले pumping station; CPHEEO 6 m, project निर्णय 10 m)।
- **Manholes की अधिकतम दूरी (m)** (30 m - CPHEEO 3.71.1), **मोड़ पर manhole** (इतने ° या ज़्यादा के मोड़ पर नया
  manhole - manual कोई कोण नहीं देता), **मोड़ पर 30 mm drop** (एक ही size का sewer 10° से ज़्यादा मुड़े तो -
  CPHEEO 3.20.3)।
- **Population**: आधार वर्ष की आबादी, census आबादी (वर्ष आबादी), forecast का तरीका; stages - आधार वर्ष,
  +15, +30 वर्ष।

### 4.3 Zoning options निकालें
App network को zones में बाँटने के कई विकल्प देता है - zones, pumping stations (PS), गहराई, pipe लागत, कुल
अनुमानित लागत (PS, O&M, rising main अनुमानित; STP सब में बराबर, इसलिए नहीं)। पंक्ति पर click → zones नक्शे पर
(हर zone अलग रंग, STP / PS, कटे sewers dashed)। ★ GIVEN = सिर्फ़ दिए गए outfalls पर, गहराई के लिए कोई PS नहीं।
⚠ = project की गहराई-सीमा से गहरा। साथ में **GL band map** - reference GL से ऊपर की ऊँचाई के रंगीन ranges।

### 4.4 Design
चुना हुआ option **Design** होता है: हर sewer का diameter, ढाल, invert, गहराई - Manning (स्थिर n), न्यूनतम /
अधिकतम वेग, d/D ≤ 0.8, peak factor, infiltration, 30 m पर manholes, drops, fixed outfall level, और pipe sizes घटाने
वाला economise pass। नक्शे पर sewers diameter के रंग में; tooltip में size, slope, Q, v, गहराई, flags।
**☷ Pipe / manhole तालिका** में बदलाव करके **बदलाव के साथ design दोबारा**; **⇩ Export: DXF + KML + Excel**।

## 5. पेयजल app - चरण-दर-चरण

### 5.1 Network और टंकियाँ
सड़कें / KML / DXF से network (**Layout बनाएँ**), junctions पर GL। **पुरानी टंकी**: क्षमता और staging दोनों भरें;
**नई टंकी**: क्षमता अपने-आप (5.4), staging खाली छोड़ें तो design से। पुरानी टंकी की staging से 17 m residual head
न मिले तो विकल्प: **VFD pump** (CPHEEO Table 2.7 S.No.10 p173 - design उसका head और kW बताता है) या
**ऊँचा क्षेत्र नई टंकी को**। Tube wells: पुराने (चालू), rebore होने वाले, नए (आपस में और OHT से कम से कम 100 m)।

### 5.2 वार्ड-वार आबादी
- **📥 KML से वार्ड तालिका…**: वार्ड सीमाओं की KML/KMZ (Ward No., नाम, आबादी, HH)। तालिका में Ward No., नाम,
  चरित्र, आबादी (वर्ष), % covered (project में आने वाला हिस्सा), KML क्षेत्रफल-%, Households, क्षेत्रफल (ha),
  Census 2011।
- **शहर की वार्ड सूची**: **Export xlsx** → पूरे शहर के वार्ड भरें → **Import xlsx…**। सूची शहर-वार सहेजी जाती है
  (सब projects में काम आती है); तालिका के वार्ड उससे नंबर + नाम, नाम या नंबर से मिलाए जाते हैं। नाम पर click
  करके सूची में खोजें। एक ही सूची-वार्ड दो पंक्तियों से जुड़े तो चेतावनी (आबादी दो बार गिनी जाती)।
- **वार्ड का चरित्र** (density = आबादी ÷ ha से अपने-आप; बदला जा सकता है): Saturated (Core) > 585 /ha,
  High (Proximal Developed) > 310, Medium (Proximal Developing) > 170, बाकी Low (Far-open)। हर चरित्र की
  वृद्धि के गुणक (आधार / +15 / +30): Saturated 1.02 / 1.25 / 1.50, High 1.04 / 1.40 / 1.85, Medium 1.06 / 1.63 /
  2.45; **Far-open** का गुणक इस तरह balance होता है कि शहर के सब वार्डों का जोड़ चुनी projection के बराबर रहे।
  **⇅ गुणक projection से मिलाएँ**: चारों चरित्रों की वृद्धि reference अनुपात में, हर stage पर एक गुणांक से।
  Far-open का गुणक 1 से कम हो तो अलग चेतावनी।
- **Saturation density** (default 1,880 /ha): design वर्ष में इससे घने होने वाले वार्ड चेताए जाते हैं।

### 5.3 Population projection
**Census (projection)** में दशक-वार census भरें → **Projection निकालें**। छह विधियाँ (हर एक पर CPHEEO tooltip):
Arithmetical, Incremental, Geometrical (default), Decreasing rate of growth, Simple graph, Semi-log। Graph और
हर विधि से शहर की आबादी की तुलना। वार्ड तालिका हो तो उसके वर्ष की आबादी से आगे बढ़ाया जाता है।

### 5.4 Zoning (OZ / DMA)
**Zoning (OZ / DMA)**: हर टंकी का एक Operational Zone (OZ), उसके अंदर DMAs - आबादी, connections, ढलान की सीमाओं
से (भाग 7.2)। **सीमा पार हो तो**: पूछें / यही सीमा रखें / बगल के zone में merge / अपने-आप नया zone। नई टंकी
की क्षमता = OZ की दैनिक माँग (fire के बिना) का 33% या mass balance (जो अधिक) + fire demand का 1/3, 50 KL में
ऊपर गोल। **OHT भरने के घंटे** (default 5-12 और 13-22) से mass balance।

### 5.5 Design
**Design**: हर pipe का diameter, junctions पर residual head, वेग, head loss - अपना network solver (Hazen-Williams)।
तीनों stages (आधार, +15, +30) की जाँच; rising mains (economical size, surge), tube wells, CWR, pumps।
**PRV का विकल्प** (default बंद - U.P. जल निगम की DPRs में आम नहीं)। ☷ तालिका में बदलाव → **बदलाव के साथ design
दोबारा**; **Export DXF** (zoning + design)। Design के साथ DPR (Excel) भी बनती है।

### 5.6 Intze OHT drawings
**🏗 Intze OHT drawings (नई टंकियाँ)** panel: Seismic zone, Net SBC (kN/m²), मिट्टी का प्रकार, हवा की गति Vb,
नींव की गहराई, concrete / steel (M30 / M25 नींव-सीढ़ी, Fe500), टंकी-वार SBC (`Prop-OHT-1=120, …`)।
आख़िरी design की हर नई टंकी की पंक्ति पर **Design** बटन - **एक बार में एक टंकी**। हर टंकी के लिए: A1 sheets
(staging-foundation, container, सीढ़ी, BBS) DXF + PDF, design calculation PDF, design / BBS / quantities xlsx।
Drawings "⚠" दिखें तो वे आख़िरी design से पहले की हैं - फिर बनाएँ।

## 6. Output files और DPR

सब files `<master folder>\Sewer\output\<project>` या `...\Water\output\<project>` में; सब export English में।

- **सीवर**: zoning Excel, costs Excel, zone / GL band maps (PNG), design report Excel, plan DXF, L-section DXF,
  `<नाम>_inputs.json` (वही run दोबारा)। **सीवर DPR** (47 sheets): Project, Coverage, Certificate, Index, Form J,
  Abstracts, O&M, Economics, Income, Recurring expenses, Breakup, Bar chart, Tech, Population, BOQ, Manholes,
  Hydraulic design statement, house connections, pumping station (E&M, design data, inlet chamber, wet well,
  screen, BOQ, rising main), HT / LT, Plinth Area Rate, EM rates, SOR।
- **पेयजल**: design workbook (Summary, Zones, DMAs, Pipes, Nodes, Stages), DXF। **पेयजल DPR** (~120 sheets):
  front pages (Cover, Checklist, Certificate, Coverage, Index, Salient features), Financial (Form J, abstracts,
  breakup, 5 वर्ष O&M), Economics, **Technical statement** T1-T21 (Population व graphs, Town Wards, Ward
  Projection, Zone Population, DMA Demand, Zone Summary, OHT Details, DMA Pop & HH, Zone Households, OZ Demand,
  Mass Balance, Tube Wells, OZ Summary, हर OZ की T14 sheet, Rising Main, Ward Population, DMA Population, Water &
  Tube Wells, OHT Mass Balance, Static Head, Pipe Table), Distribution (D1-D6), Storage (S1-S4), Civil (C1-C6),
  E&M (E1-E9), Unit estimates (U01-U44), SOR 2025-26। सब formulas live - rate बदलें तो सब बदलता है।
- **Intze**: `output\<project>\intze\` में हर टंकी की `.dxf`, `.pdf`, `_calc.pdf`, `_design.xlsx`।

## 7. मानक और स्रोत - कौन-सा मान कहाँ से

**पन्नों की संख्या:** पेयजल में "p173" = CPHEEO Manual on Water Supply and Treatment (2024), Part A के PDF का
पन्ना; सीवर में "p3-26" = CPHEEO Manual on Sewerage and Sewage Treatment Systems (2013), Part A (Engineering) का
छपा पन्ना (अध्याय-पन्ना)। हर app में **📘 CPHEEO** बटन यही सारांश दिखाता है।

**स्रोतों के प्रकार:** **CPHEEO** = manual; **UPJN** = U.P. जल निगम का नियम / practice; **Reference DPR** =
जिन DPRs के format और practice पर app बना (इस पुस्तिका में उनके नाम काल्पनिक हैं: Elmwood DPR, Riverside DPR);
**App का निर्णय** = जहाँ manual कोई अंक नहीं देता, वहाँ project में लिया गया निर्णय या planning allowance।

### 7.1 सीवर - design के मान

| विषय | मान | स्रोत |
|---|---|---|
| Design अवधि | sewers, pumping mains, PS (civil) 30 वर्ष; machinery और STP 15 वर्ष | CPHEEO Table 2.1, p2-9 |
| आबादी | master plan के land use / FSI से; न हो तो Table 3.1 के घनत्व | CPHEEO 3.3, p3-2 |
| Sewage प्रवाह | कम से कम 100 L/व्यक्ति/दिन; जल आपूर्ति का 40-90% (return factor project के अनुसार) | CPHEEO 3.5, p3-3 |
| Peak factor | 20,000 तक 3.0; 50,000 तक 2.5; 7,50,000 तक 2.25; अधिक 2.0 | CPHEEO Table 3.2, p3-3 |
| न्यूनतम प्रवाह | औसत का 1/3 से 1/2 | CPHEEO p3-4 |
| Infiltration | 5,000-50,000 L/ha/दिन, 500-5,000 L/km/दिन, 250-500 L/manhole/दिन; design प्रवाह के 10% तक | CPHEEO Table 3.3, 3.6, p3-4 |
| Storm water | sanitary sewer में नहीं जोड़ा | CPHEEO p3-5 |
| न्यूनतम व्यास | 200 mm (1 लाख से अधिक आबादी); 150 mm छोटे / पहाड़ी | CPHEEO 3.14, p184 |
| वेग | आरंभिक peak पर ≥ 0.6 m/s, अंतिम peak पर ≥ 0.8 m/s, अधिकतम 3 m/s | CPHEEO Table 3.9, p3-26 |
| जाँच का आधार | uniform flow, Manning में स्थिर n | CPHEEO 3.15.5, p3-28; p3-31 |
| Manning n | सामग्री के अनुसार | CPHEEO Table 3.11, p3-29 |
| प्रवाह की गहराई | d/D ≤ 0.8 (अंतिम peak पर) | CPHEEO 3.15.5, p3-28 |
| न्यूनतम ढाल | 150 mm 1:170; 200 1:250; 250 1:360; 300 1:450; 375 1:670; 450 1:830; 525+ 1:1000 | CPHEEO Table 3.13, p3-31 |
| Size न घटे, crowns लगातार | downstream में छोटा व्यास नहीं | CPHEEO 3.17.1, p3-34 |
| Manhole में drop | size बदले बिना मोड़ पर 30 mm; size बदले तो crowns बराबर | CPHEEO 3.20.3, p3-42 |
| Drop manhole | स्तर-अंतर 600 mm से अधिक | CPHEEO 3.25, p3-53 |
| न्यूनतम cover | 1 m (घर का connection: crown पर 90 cm मिट्टी) | CPHEEO 3.70, p3-124 |
| अधिकतम गहराई | 6 m के बाद lift station; विशेष स्थिति में DPR में औचित्य | CPHEEO Table 3.15 note, p3-46 |
| Project की गहराई-सीमा | 10 m, lift stations नहीं | App का निर्णय (CPHEEO p3-46 note के अंतर्गत) |
| Manhole दूरी | 30 m; trunk sewers में 600 mm पर 60 m … 1500 mm पर 150 m | CPHEEO 3.71.1, Table 3.31, p3-126-127 |
| मोड़ पर manhole | default 20° या अधिक का मोड़ | CPHEEO 3.71, p3-125 (मोड़ पर manhole); कोण App का निर्णय |
| मोड़ पर 30 mm drop | 10° से अधिक मोड़ (drawing की हल्की टेढ़ नहीं गिनी जाती) | CPHEEO 3.20.3, p3-42; 10° App का निर्णय |
| Flushing | Table 3.16 के अनुसार पानी; tanker 6,000 L | CPHEEO 3.29, p3-56 |
| Terminal cleanout | manhole से 50 m के भीतर | CPHEEO 3.31, p3-57 |
| Pumping main | Hazen-Williams; 0.6-2.4 m/s; HGL ज़मीन से ≥ 1 m ऊपर | CPHEEO 3.16, 4.20.3, 4.1.5 |
| Pumping station | 3 या 5 pumps (DWF के गुणक), wet well T = 10-15 मिनट, kW = Q×H/100.5/η | CPHEEO 4.5.4, 4.6, 4.20.2 |
| Zoning में PS लागत | PFR स्तर का अनुमान, reference DPR के estimate से | Reference DPR; App का अनुमान, DPR नहीं |
| Rates | UPJN SOR 2025-26, pipe rates (UPJN rate document 2025-26) | UPJN |
| DPR का format | Reference DPR का sewer estimate और UPJN E&M estimate | Reference DPR / UPJN |

### 7.2 पेयजल - design के मान

| विषय | मान | स्रोत |
|---|---|---|
| Design अवधि | pipes और ESR अंतिम चरण (आधार + 30); machinery मध्य चरण (+15) | CPHEEO Table 2.7 S.No.1, p168 |
| प्रति व्यक्ति जल | 150 LPCD (10 लाख से बड़े शहर; छोटे 135) | CPHEEO Table 2.7 S.No.4, p169 |
| Floating population | 45 LPCD (स्नान सहित); हिस्सा आबादी का 10% (default - page पर "Floating आबादी (%)" में बदल सकते हैं) | CPHEEO S.No.5, p170; 10% Reference DPR |
| हानियाँ | वितरण में 10% (भूजल सीधे: कुल 11%) | CPHEEO Table 2.7 S.No.6, p171 |
| Peak factor | 2.5; ESR तक transmission 22 घंटे | CPHEEO Table 2.7 S.No.7, p172 |
| न्यूनतम व्यास | 100 mm (पुराने 80 mm रह सकते हैं) | CPHEEO Table 2.7 S.No.8, p172 |
| Residual head | 17-21 m (Class I-II शहर) | CPHEEO Table 2.7 S.No.10, p173 |
| कम staging वाली पुरानी ESR | OZ उसकी क्षमता जितना, outlet पर VFD pump | CPHEEO Table 2.7 S.No.10, p173 |
| ESR क्षमता | mass balance या OZ की माँग का 33% (जो अधिक) + fire का 1/3 | CPHEEO Table 2.7 S.No.12-13, p175-177 |
| ESR की SWD | 1 लाख L तक 3 m, 10 लाख L तक 4 m, अधिक 5 m | CPHEEO Table 2.7 S.No.12, p176 |
| Fire demand | 100√P m³/दिन (P हज़ार में) | CPHEEO Table 2.7 S.No.13, p176 |
| OZ | 50,000 आबादी या 10,000 connections तक; ज़मीन का ढाल 5 m तक | CPHEEO Table 2.7 S.No.18, 20, p180 |
| DMA | 500-3,000 connections; एक OZ में अधिकतम 4 | CPHEEO Table 2.7 S.No.21, p181 |
| Isolation segment | 50-250 connections | CPHEEO Table 2.7 S.No.30, p184 |
| वेग | 0.4-0.6 m/s उचित, 0.3 तक (न्यूनतम व्यास पर); अधिकतम 3 m/s | CPHEEO 6.6 (i), (ii), p400 |
| Head loss | Hazen-Williams: h = 10.68 (Q/C)^1.852 L / D^4.87; minor losses 10% | CPHEEO eq 6.4 p393; 6.6 (vi) p400 |
| Transmission | head loss gradient 10 m/km तक, वेग 2.5 m/s तक | CPHEEO 6.6 (v), Table 2.7 S.No.22, p182 |
| Rising main का size | pipe + pumps + बिजली की present-worth लागत सबसे कम; 0.6-2.0 m/s | CPHEEO 6.7, Annexure 6.1, p400-402, p1157 |
| Surge | h = c V / g, c = 1425 / √(1 + k d / E t) | CPHEEO 6.16.4, Table 6.9, p428 |
| DI pipe की मोटाई | K-7 / K-9 और AOP / MOP | IS 8329:2000 Table 2, Amendment 1 |
| Rising main सामग्री | DI | Reference DPR; App का निर्णय |
| CWR | एक ESR को 3 से अधिक **नए** tube wells भरें तो अनिवार्य; क्षमता ESR का 25% | UPJN नियम; CPHEEO 2.8.1.17, p127 |
| Standby pumps | 1 W + 1 S; 2 W + 1 S; 3-5 W + 2 S; 6-10 W + 3 S | CPHEEO 5.7.5, p350 |
| Tube well | नया 1,500 LPM, पुराना 1,200 LPM; 16 घंटे pumping; आपस में 100 m | Reference DPR / UPJN; 100 m App का निर्णय |
| OHT भराई / draw-off | 5-12 और 13-22 घंटे; घंटे-वार draw-off pattern | Reference DPR (mass balance) |
| व्यक्ति / connection | 6 (एक घर = एक connection) | Reference DPR |
| Pumping main की माँग | हानि के बिना माँग × 1.11 | Reference DPR |
| OHT क्षमता का गोलाई | 50 KL में ऊपर | Practice |
| Zoning में head loss | नई OHT की trial staging के लिए 1.5 m/km; पुरानी OHT 0.5 m/km | App का planning allowance (CPHEEO नहीं) |
| VFD pump की दक्षता | 0.65 | Practice (CPHEEO नहीं) |

### 7.3 आबादी - projection और वार्ड

| विषय | स्रोत |
|---|---|
| छह विधियाँ - arithmetical, incremental, geometrical, decreasing rate (Eq. 2.5), simple graph, semi-log | CPHEEO Annexure 2.8, p977-984 |
| वार्ड-वार आबादी, equivalent area (आवासीय 1, सार्वजनिक 0.25, उद्योग / कृषि 0.1, सड़क / जल 0) | CPHEEO 2.8.1.24, p131 |
| चरित्र (low / medium / high / saturated), core लगभग saturation पर, saturation density, आबादी नगर निकाय से स्वीकृत कराएँ | CPHEEO Annexure 2.7, p974-976 |
| density सीमाएँ 585 / 310 / 170, चरित्र के गुणक, saturation 1,880 /ha (सबसे घना वार्ड × 1.10) | Reference DPR (p76) - **ये अंक CPHEEO के नहीं**, शहर के अनुसार बदलें |
| Floating population 10% (default; दोनों apps के आबादी चरण में "Floating आबादी (%)" से बदलें) | Reference DPR (CPHEEO Annexure 2.8 आँकड़े न हों तो 1-3% सुझाता है) |

### 7.4 Intze OHT

| विषय | मान | स्रोत |
|---|---|---|
| पानी वाले members | working stress, crack width के लिए steel 130 N/mm² | IS 3370 (Part 2) |
| Staging, नींव, सीढ़ी | limit state | IS 456 |
| भूकंप | seismic zone (default III), मिट्टी का प्रकार | IS 1893 (Part 1, Part 2) |
| हवा | Vb (default 47 m/s) | IS 875 (Part 3) |
| Wall पर पानी | CPHEEO की अधिकतम SWD (3 / 4 / 5 m), नीचे cone | CPHEEO Table 2.7 S.No.12, p176 |
| आकार, annular raft, सीढ़ी, drawing की शैली | reference design (Brookfield Consultants) की practice | Reference design |
| Braces / raft के moments | reference design report के सूत्र | Reference design report |
| Net SBC | default 80 kN/m² (soil test आने तक) | Reference design; हर टंकी की अपनी भरें |

### 7.5 Rates और DPR
- **Rates**: U.P. जल निगम का Schedule of Rates 2025-26 (`R SOR 2025-26` / `sor` sheet) और UPJN का pipe rate
  document 2025-26 (DI / HDPE / RCC / DWC pipes)।
- **DPR का format**: reference DPRs (पेयजल के technical statement, unit estimates; सीवर का estimate) और UPJN
  E&M estimate का format। Cost index का मान reference DPR जैसा - अपने ज़िले का भरें।

## 8. Update, About, data folder

- **Master folder**: पहली बार चुना गया folder; उसमें `Sewer\projects`, `Sewer\output`, `Water\projects`,
  `Water\output`, `App` (settings, log)। Menu **App → Master folder खोलें / बदलें…**।
- **App → Update देखें…**: app सिर्फ़ तभी GitHub से नया version पूछता है। नया हो तो एक click में - setup download,
  उसका SHA-256 GitHub से मिलाना (न मिले तो file हटा दी जाती है, कुछ install नहीं होता), app बंद, setup चलकर
  update, app फिर खुलता है। पहले सब काम सहेज लें। Data folder वैसा ही रहता है।
- **App → About** (और start page पर नीचे "About"): version, licence (GNU GPL v3.0 या बाद का), source, credits।

## 9. Source से चलाना

Windows पर Python 3.10 या नया:

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

- `sewer_ui.bat` - वही app browser में (start page `http://127.0.0.1:8764`); `water_ui.bat` - सिर्फ़ पेयजल।
- `build_setup.bat` - setup बनाता है (PyInstaller + Inno Setup 6); version `launcher\about.py` से।
- `.venv\Scripts\python -m pytest` - tests।

---

Licence: GNU General Public License v3.0 or later ([LICENSE](LICENSE)) - बिना किसी warranty के।
Credits: Aurobindoji (engineering requirements, design के फ़ैसले, reference data, testing); Claude (Anthropic) -
Aurobindoji के साथ मिलकर लिखा, AI coding assistant के रूप में।
