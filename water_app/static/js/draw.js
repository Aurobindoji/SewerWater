// The water map page (map.html), part 3 of 11: the features drawn on the map, the drawing tools and the summary of the drawing.
// Restructure stage 4 (15-Nov-2026): the page's one script split into files run in this order, sharing one global scope.
// ---------------------------------------------------------------- features
let selected = null;
function addFeature(layer, kind, props) {
  layer.kind = kind;
  layer.props = Object.assign({ name: "" }, props || {});
  if (layer.setStyle) layer.setStyle(style(kind));
  if (layer.setIcon) layer.setIcon(icon(kind, false, layer.props));
  layer.on("click", ev => { L.DomEvent.stopPropagation(ev); select(layer); });
  if (kind === "oht") layer.on("dragstart", () => { if (ohtPop) map.closePopup(ohtPop); })
    .on("dragend", () => { changed(); ohtTouched(); showProps(); if (selected === layer) ohtPopup(layer); });
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
    layer.bindTooltip(`${p.name || "वार्ड"}: ${p.population ? Number(p.population).toLocaleString("en-IN") : "population ?"}`,
      { sticky: true, direction: "right", offset: [22, 0] });
  else if (layer.kind === "road" && p.name) layer.bindTooltip(p.name, { sticky: true, direction: "right", offset: [22, 0] });
  else if (layer.kind === "tw")
    hoverCard(layer, () => ({ html: twCardHtml(layer.props.name, layer.props.discharge_lpm, true) + hcStale(),
      acts: [["✕", tr("नक्शे से हटाएँ", "remove from the map"), () => hcDelete(layer), "del"], ["✥ move", tr("खींचकर नई जगह", "drag to a new place"), () => hcMove(layer)]] }));
  else if (layer.kind === "prv")
    layer.bindTooltip(`${p.name || "PRV"}: setting ${p.setting_m ? `${p.setting_m} m` : tr("अपने-आप", "by itself")}`, { direction: "right", offset: [10, 0] });
  else if (layer.kind === "bulk")
    layer.bindTooltip(`${p.name || "Bulk"}: ${p.kld ? `${p.kld} KL/day` : tr("KL/day ?", "KL/day ?")}${p.peak ? `, peak ${p.peak}` : ""}`, { direction: "right", offset: [10, 0] });
  else if (layer.kind === "crossing")
    layer.bindTooltip(`${p.name || "Crossing"} - ${tr("यहाँ pipe आर-पार", "a pipe goes across here")}`, { sticky: true, direction: "right", offset: [22, 0] });
  else if (layer.kind === "zone_loop")
    layer.bindTooltip(`${p.name || "Zone"} - ${tr("घेरा क्षेत्र एक zone", "the area enclosed: one zone")}`, { sticky: true, direction: "right", offset: [22, 0] });
  else if (layer.kind === "barrier")
    layer.bindTooltip(`${p.name || ""} (${barrierType(p.type)}) - ${tr("कोई pipe पार नहीं करेगा", "no pipe crosses it")}`, { sticky: true, direction: "right", offset: [22, 0] });
  if (layer.kind === "oht" && layer.setIcon) layer.setIcon(icon("oht", layer === selected, p));     // the name on the marker
  if (layer.kind === "oht")
    hoverCard(layer, () => ({ html: ohtCardHtml(layer.props.name, true, layer.props) + hcStale(),
      acts: [["✕", tr("नक्शे से हटाएँ", "remove from the map"), () => hcDelete(layer), "del"], ["✥ move", tr("खींचकर नई जगह", "drag to a new place"), () => hcMove(layer)]] }));
}
function select(layer) {
  const reEdit = editing && layer && layer !== editTarget;       // editing: a click on another feature edits that one
  if (reEdit) toggleEdit(false);
  if (selected && drawn.hasLayer(selected)) {
    if (selected.setStyle) selected.setStyle(style(selected.kind));
    if (selected.setIcon) selected.setIcon(icon(selected.kind, false, selected.props));
  }
  if (selected && selected.kind === "oht" && selected.dragging) { selected.dragging.disable(); selected.setZIndexOffset(0); }
  if (ohtPop && map.hasLayer(ohtPop)) map.closePopup(ohtPop);
  selected = layer;
  if (layer) {
    if (layer.setStyle) layer.setStyle(style(layer.kind, true));
    if (layer.setIcon) layer.setIcon(icon(layer.kind, true, layer.props));
  }
  showProps();
  if (reEdit) toggleEdit(true);
  if (layer && layer.kind === "oht") {
    layer.setZIndexOffset(10000);                    // above the zoning / design markers of the same tank
    if (layer.dragging && !editing) layer.dragging.enable();
    ohtPopup(layer);
  }
}
// an OHT clicked on the map: its main data edited right beside it; the tank dragged to move it
let ohtPop = null;
function ohtPopup(layer) {
  const p = layer.props, ex = isExOht(p);
  const html = `<div class="ohtpop"><b>${esc(p.name)}</b> <span class="hint">${ex ? tr("पुरानी टंकी", "existing tank") : tr("नई टंकी", "new tank")}</span>
    ${ex ? `<div class="row"><label>${tr("क्षमता (KL)", "Capacity (KL)")}</label><input type="number" id="pp_cap" min="0" step="50" value="${esc(p.capacity_kl)}"></div>` : ""}
    <div class="row"><label>Staging (m)</label><input type="number" id="pp_stg" min="0" step="0.5" value="${esc(p.staging_m)}"${ex ? "" : ` placeholder="${tr("खाली: design से", "empty: from the design")}"`}></div>
    ${ex ? `<div class="row"><label>${tr("17 m न मिले तो", "If 17 m is not reached")}</label><select id="pp_lh">
      <option value="vfd"${p.low_head !== "new_oht" ? " selected" : ""}>${tr("VFD pump (मैनुअल)", "VFD pump (manual)")}</option>
      <option value="new_oht"${p.low_head === "new_oht" ? " selected" : ""}>${tr("ऊँचा क्षेत्र नई टंकी को", "Higher ground to a new tank")}</option></select></div>` : ""}
    <div class="hint">✥ ${tr("टंकी को पकड़कर खींचें - नई जगह पर छोड़ दें", "drag the tank to move it - drop it at its new place")}</div>
    <div class="warn">${tr("टंकी बदलने या खिसकाने पर Zoning और Design दोबारा चलाने पड़ सकते हैं।", "Changing or moving a tank may need Zoning and Design run again.")}</div></div>`;
  ohtPop = L.popup({ offset: [0, -12], closeOnClick: false, autoPanPadding: [20, 20], maxWidth: 300 })
    .setLatLng(layer.getLatLng()).setContent(html).openOn(map);
  const el = ohtPop.getElement();
  const bind = (id, key, side) => {
    const f = el.querySelector("#" + id); if (!f) return;
    f.addEventListener(f.tagName === "SELECT" ? "change" : "input", () => {
      p[key] = f.value; label(layer); changed(); ohtTouched();
      if ($(side)) $(side).value = f.value;          // the panel on the left shows the same
    });
  };
  bind("pp_cap", "capacity_kl", "f_cap"); bind("pp_stg", "staging_m", "f_stg"); bind("pp_lh", "low_head", "f_lowhead");
}
// a barrier line / zone loop drawn / changed / removed after zoning / design: they are of the lines as they were
function barrierTouched() {
  if (!(wZoning || wDesign) || !$("wstatus")) return;
  $("wstatus").className = "status err";
  $("wstatus").textContent = tr("Zoning औज़ार (रेखा / लूप) बदला गया - Zoning और Design दोबारा चलाएँ", "A zoning tool (line / loop) changed - run Zoning and Design again");
}
// a tank changed after zoning / design: they are of the tanks as they were
function ohtTouched() {
  if (!(wZoning || wDesign) || !$("wstatus")) return;
  $("wstatus").className = "status err";
  $("wstatus").textContent = tr("OHT बदली गई - Zoning और Design दोबारा चलाएँ", "An OHT changed - run Zoning and Design again");
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
  if (k === "spot" || k === "stp" || k === "oht" || k === "bulk" || k === "prv" || k === "tw") { const ll = selected.getLatLng(); info = `${ll.lat.toFixed(6)}, ${ll.lng.toFixed(6)}`; }
  box.className = "";
  const ohtEx = k === "oht" && isExOht(p);
  box.innerHTML = `<b style="color:${KIND[k].color}">${k === "oht" ? (ohtEx ? "पुरानी टंकी (Ex-OHT)" : "नई टंकी (Prop-OHT)") : KIND[k].name}</b> <span class="hint">${info}</span>
    <div class="row"><label>नाम</label><input type="text" id="f_name" value="${esc(p.name)}"></div>
    ${k === "ward" ? `<div class="row"><label title="${tr("वार्ड-वार आबादी की तालिका का Ward No. - उसकी आबादी x % covered इसी सीमा के junctions पर", "the Ward No. of the ward table - its population x % covered on this boundary's junctions")}">Ward No.</label><input type="text" id="f_wno" value="${esc(p.ward_no ?? "")}" style="width:70px"></div>
       ${wtRow(p.ward_no) ? `<div class="hint">${tr("तालिका से", "from the table")}: ${esc(wtRow(p.ward_no).name || "")} ${fmt(+wtRow(p.ward_no).pop || 0)} x ${wtRow(p.ward_no).cov === "" ? 100 : +wtRow(p.ward_no).cov}% = ${fmt(wtCov(wtRow(p.ward_no)))} (${WT.year})</div>` : ""}
       <div class="row"><label>Population</label><input type="number" id="f_pop" min="0" step="1" value="${esc(p.population)}"${wtRow(p.ward_no) ? " disabled" : ""}></div>
       <div class="row"><label title="${tr("वार्ड का चरित्र: उसकी वृद्धि (Riverside DPR p76) - आधार / +15 / +30 वर्ष; खाली = page / projection का एक ही गुणक", "the ward's character: its growth (Riverside DPR p76) - base / +15 / +30 years; empty = the one factor of the page / projection")}">${tr("चरित्र", "Character")}</label>
         <select id="f_wchar">${WARD_CHARS.map(c => `<option value="${c[0]}"${(wardChar(p) || "") === c[0] ? " selected" : ""}>${EN ? c[2] : c[1]}</option>`).join("")}</select></div>
       ${wardChar(p) ? `<div class="hint">${wtRow(p.ward_no) ? tr("तालिका का चरित्र; ", "the table's character; ") : ""}${tr("Population = " + (wtRow(p.ward_no) ? WT.year : "आज (वर्तमान)") + " की आबादी; design में x " + (WARD_GROWTH[wardChar(p)] || []).join(" / ") + " (आधार / +15 / +30 वर्ष)", "Population = the population of " + (wtRow(p.ward_no) ? WT.year : "today") + "; in the design x " + (WARD_GROWTH[wardChar(p)] || []).join(" / ") + " (base / +15 / +30 years)")}</div>` : ""}` : ""}
    ${k === "boundary" ? `<div class="row"><label>Population</label><input type="number" id="f_pop" min="0" step="1" value="${esc(p.population ?? "")}"></div>
       <div class="hint">पूरे क्षेत्र की population - तभी ली जाती है जब किसी वार्ड में population न भरी हो (वार्ड हों तो वार्ड-वार भरें)।</div>` : ""}
    ${k === "crossing" ? `<div class="row"><label title="${tr("रेखा / लूप को काटने की जगह से इतनी दूरी के भीतर का pipe नहीं कटता", "a pipe within this of where the line crosses is not cut")}">${tr("इतने में pipe आर-पार (m)", "Pipe through within (m)")}</label>
         <input type="number" id="f_xtol" min="0.5" max="100" step="0.5" value="${esc(p.tol_m ?? 10)}"></div>
       <div class="row"><label title="${tr("कोई pipe न हो तो नया pipe: उसके दोनों सिरे इतनी दूरी तक के सबसे पास वाले junction से जुड़ते हैं", "no pipe there: a new pipe, each end joined to the nearest junction within this")}">${tr("नया pipe: junction इतने तक (m)", "New pipe: junction within (m)")}</label>
         <input type="number" id="f_xsnap" min="1" max="1000" step="1" value="${esc(p.snap_m ?? 100)}"></div>
       <div class="hint">${tr(`जहाँ यह रेखा किसी रुकावट रेखा या zone लूप को काटती है, वहाँ ${esc(p.tol_m ?? 10)} m के भीतर का pipe नहीं कटता (लूप की सीमा पर valve बंद नहीं होता, दोनों zone जुड़ते हैं)। वहाँ कोई pipe न हो तो यही रेखा नया pipe बनती है, जिसके दोनों सिरे सबसे पास के junction (${esc(p.snap_m ?? 100)} m तक) से जुड़ते हैं। बदलने पर Zoning और Design दोबारा चलाएँ।`,
         `Where this line crosses a barrier line or a zone loop, the pipe within ${esc(p.tol_m ?? 10)} m there is not cut (no valve closed at the loop: the two zones join). Where no pipe crosses there, this line is a new pipe, its ends joined to the nearest junction (within ${esc(p.snap_m ?? 100)} m). After a change run Zoning and Design again.`)}</div>` : ""}
    ${k === "zone_loop" ? `<div class="row"><label title="${tr("घेरे क्षेत्र की आबादी OZ की सीमा (50,000 / 10,000 कनेक्शन) से अधिक या एक DMA (500 कनेक्शन) से कम हो तो", "when the area's population is above the OZ limit (50,000 / 10,000 connections) or below one DMA (500 connections)")}">${tr("सीमा पार हो तो", "Beyond the limits")}</label>
         <select id="f_onlimit">${LOOP_MODES.map(m => `<option value="${m[0]}"${(p.on_limit || "") === m[0] ? " selected" : ""}>${EN ? m[2] : m[1]}</option>`).join("")}</select></div>
       <div class="hint">${tr("घेरे क्षेत्र के junctions एक OZ (एक OHT) बनते हैं; सीमा पार करने वाले pipes सीमा पर valve से बंद। आबादी सीमा से बाहर हो तो Zoning पूछती है और आपका जवाब यहीं रहता है। बदलने पर Zoning और Design दोबारा चलाएँ।",
         "The junctions inside form one OZ (one OHT); the pipes crossing the loop are closed at it (valves). Beyond the population limits the Zoning asks, and your answer is kept here. After a change run Zoning and Design again.")}</div>` : ""}
    ${k === "barrier" ? `<div class="row"><label>${tr("प्रकार", "Type")}</label><select id="f_btype">${BARRIER_TYPES.map(b =>
         `<option value="${b[0]}"${(p.type || "other") === b[0] ? " selected" : ""}>${EN ? b[2] : b[1]}</option>`).join("")}</select></div>
       <div class="row"><label title="${tr(`रेखा को काटने वाला ${PIPE} रेखा से इतने मीटर पहले, दोनों ओर, बंद होता है`, `a ${PIPE} crossing the line ends this many metres short of it, on both sides`)}">${tr("रेखा से पहले बंद (m)", "Ends short of the line (m)")}</label>
         <input type="number" id="f_gap" min="0" max="100" step="0.5" value="${esc(p.gap_m ?? 1)}"></div>
       <div class="hint">${tr("कोई pipe इस रेखा को पार नहीं करेगा: Zoning / Design में काटने वाला pipe रेखा पर कटता है - दोनों हिस्से अपनी सड़क पर रहते हैं, रेखा से ऊपर दी दूरी (m) पहले बंद। कटकर अलग हुए हिस्से को अपनी OHT मिलती है (या वह किसी OHT से नहीं जुड़ा दिखता है)। बदलने पर Zoning और Design दोबारा चलाएँ।",
         "No pipe crosses this line: in Zoning / Design a pipe crossing it is cut there - both parts stay on their road, ending the distance above (m) short of the line. A part so cut off gets an OHT of its own (or shows as joined to no OHT). After a change run Zoning and Design again.")}</div>` : ""}
    ${k === "bulk" ? `<div class="row"><label title="${tr("दैनिक माँग, losses के बिना", "daily demand, without losses")}">${tr("माँग (KL/day)", "Demand (KL/day)")}</label><input type="number" id="f_kld" min="0" step="1" value="${esc(p.kld)}"></div>
       <div class="row"><label title="${tr("खाली = network का 2.5; अपनी sump हो तो 24 / भराई के घंटे (8 घंटे → 3.0), लगातार लेने पर 1.0", "empty = the network's 2.5; with a sump of its own 24 / filling hours (8 hours → 3.0), a steady draw 1.0")}">Peak factor</label><input type="number" id="f_peak" min="0.1" max="10" step="0.1" value="${esc(p.peak)}" placeholder="2.5"></div>
       <div class="hint">${tr("माँग सबसे पास के junction पर जुड़ती है (200 m से दूर हो तो चेतावनी), 10 % distribution losses सहित, हर stage में वही; zoning में OZ की माँग, OHT क्षमता और नलकूपों में, design में अपने peak factor पर, DPR T10 में अलग स्तंभ। बदलने पर Zoning और Design दोबारा चलाएँ।",
         "The demand joins the nearest junction (warned when farther than 200 m), with 10 % distribution losses, the same at every stage: in the OZ demand, OHT capacity and tube wells of the zoning, at its own peak factor in the design, a column of its own in DPR T10. After a change run Zoning and Design again.")}</div>` : ""}
    ${k === "tw" ? `<div class="row"><label title="${tr("पम्प का discharge; खाली = नए TW का 1500 LPM (Elmwood TW)", "the pump's discharge; empty = a new tube well's 1500 LPM (Elmwood TW)")}">Discharge (LPM)</label><input type="number" id="f_twq" min="100" step="100" value="${esc(p.discharge_lpm)}" placeholder="1500"></div>
       <div class="hint">${tr("अपने सबसे पास के junction के OZ का होता है; उसकी अपनी rising main सड़क के रास्ते उस OZ की OHT तक - economic size (CPHEEO 6.7, Annexure 6.1), surge जाँच; T14 के pumping head में उसका घर्षण; DPR में T15 / D5। बदलने पर Design दोबारा चलाएँ।",
         "Belongs to the OZ of its nearest junction; its own rising main along the roads to that OZ's OHT - economical size (CPHEEO 6.7, Annexure 6.1), surge check; its friction in the T14 pumping head; DPR T15 / D5. After a change run the Design again.")}</div>` : ""}
    ${k === "prv" ? `<div class="row"><label title="${tr("PRV के बाद का residual head (m); खाली = अपने-आप: सबसे कम जिससे आगे हर junction पर 17 m मिले", "the residual head after the PRV (m); empty = by itself: the lowest that keeps 17 m at every junction beyond it")}">Setting (m)</label><input type="number" id="f_prvset" min="0" step="0.5" value="${esc(p.setting_m)}" placeholder="${tr("अपने-आप", "auto")}"></div>
       <div class="hint">${tr("सबसे पास के pipe (30 m तक) पर बैठता है; जिस इलाके को सिर्फ़ उसी pipe से पानी मिलता है उसका दबाव घटता है (loop हो तो असर नहीं - Design में बताया जाता है)। Design के नतीजे और stage जाँच में लागू, DPR (D2) में पीली rate, DXF में W_PRV। बदलने पर Design दोबारा चलाएँ।",
         "Sits on the nearest pipe (within 30 m); lowers the pressure of the area fed only through that pipe (in a loop: no effect - the Design says so). In the design results and the stage check, the DPR (D2) at a yellow rate, the DXF on W_PRV. After a change run the Design again.")}</div>` : ""}
    ${k === "spot" ? `<div class="row"><label>GL (m)</label><input type="number" id="f_gl" step="0.01" value="${esc(p.gl)}"></div>
       <div class="hint">Google Earth में cursor की ऊँचाई (Elev) या survey का स्तर - PFR अनुमान।</div>` : ""}
    ${k === "oht" && ohtEx ? `<div class="row"><label title="मौजूदा टंकी की क्षमता">क्षमता (KL)</label><input type="number" id="f_cap" min="0" step="50" value="${esc(p.capacity_kl)}"></div>
       <div class="row"><label title="टंकी का निम्नतम जल-स्तर ज़मीन से कितना ऊपर (m)">Staging (m)</label><input type="number" id="f_stg" min="0" step="0.5" value="${esc(p.staging_m)}"></div>
       <div class="row"><label title="staging से 17 m residual head न मिले तो">17 m न मिले तो</label><select id="f_lowhead">
         <option value="vfd"${p.low_head !== "new_oht" ? " selected" : ""}>VFD pump (मैनुअल)</option>
         <option value="new_oht"${p.low_head === "new_oht" ? " selected" : ""}>ऊँचा क्षेत्र नई टंकी को</option></select></div>
       <div class="hint">पुरानी टंकी: क्षमता और staging दोनों भरें। Staging से 17 m न मिले तो CPHEEO (Table 2.7 S.No.10 p173): OZ टंकी की क्षमता जितना, outlet पर VFD pump - design उसका head और kW बताएगा; या ऊँची ज़मीन नई टंकी को।</div>` : ""}
    ${k === "oht" && !ohtEx ? `<div class="row"><label title="टंकी का निम्नतम जल-स्तर ज़मीन से कितना ऊपर (m)">Staging (m)</label><input type="number" id="f_stg" min="0" step="0.5" value="${esc(p.staging_m)}" placeholder="खाली: design से"></div>
       <div class="hint">नई टंकी: क्षमता = OZ की माँग (fire के बिना) का 33% या mass balance (जो अधिक हो) + fire demand का 1/3; staging खाली छोड़ें तो design से (17 m के लिए जितनी चाहिए)।</div>` : ""}
    ${k === "oht" ? `
       <div class="row"><label title="इस टंकी को भरने वाले मौजूदा नलकूप; CWR तब जब +15 वर्ष के नए नलकूप 3 से अधिक हों (जल निगम नियम; मौजूदा नलकूप पुराने structures से जुड़े रहते हैं)">पुराने नलकूप (चालू)</label><input type="number" id="f_tw" min="0" step="1" value="${esc(p.tubewells)}"></div>
       <div class="row"><label title="${tr("इस टंकी के पुराने नलकूप जिनका rebore होगा (ऊपर की संख्या में नहीं): पुराने नलकूप की तरह पानी देते हैं; DPR में boring, pumping plant, SCADA, girder pillar और पुराने pump house तक LT cable - नया pump house और नया बिजली connection नहीं", "existing tube wells of this tank to be rebored (not in the number above): they give as the existing ones; in the DPR their boring, pumping plant, SCADA, a girder pillar and the LT cable to the existing pump house - no new pump house, no new power connection")}">${tr("Rebore होने वाले नलकूप", "Tube wells to rebore")}</label><input type="number" id="f_rb" min="0" step="1" value="${esc(p.rebore ?? "")}"></div>` : ""}
    <div class="row">${k === "ward" ? '<button id="f_kind">Boundary बनाएँ</button>' : k === "boundary" ? '<button id="f_kind">वार्ड बनाएँ</button>'
      : k === "oht" ? `<button id="f_ohtkind">${ohtEx ? "नई टंकी बनाएँ" : "पुरानी टंकी बनाएँ"}</button>` : ""}
      <button class="danger" id="f_del">हटाएँ (Delete)</button></div>`;
  const bind = (id, key) => { const el = $(id); if (el) el.addEventListener("input", () => { p[key] = el.value; label(selected); changed(); }); };
  bind("f_name", "name"); bind("f_pop", "population"); bind("f_gl", "gl");
  if ($("f_wno")) $("f_wno").onchange = () => { p.ward_no = $("f_wno").value.trim(); changed(); showProps(); popUi(); };
  bind("f_cap", "capacity_kl"); bind("f_stg", "staging_m"); bind("f_tw", "tubewells"); bind("f_rb", "rebore"); bind("f_kld", "kld"); bind("f_peak", "peak"); bind("f_prvset", "setting_m"); bind("f_twq", "discharge_lpm");
  if ($("f_lowhead")) $("f_lowhead").onchange = () => { p.low_head = $("f_lowhead").value; changed(); };
  if ($("f_wchar")) $("f_wchar").onchange = () => {     // a ward of the table: its row's character (7-Nov-2026)
    const row = wtRow(p.ward_no);
    if (row) { row.char = $("f_wchar").value; wtRender(); wtChanged(); } else { p.character = $("f_wchar").value; changed(); }
    showProps(); };
  if ($("f_btype")) $("f_btype").onchange = () => { p.type = $("f_btype").value; label(selected); changed(); barrierTouched(); };
  if ($("f_onlimit")) $("f_onlimit").onchange = () => { p.on_limit = $("f_onlimit").value; changed(); barrierTouched(); };
  if ($("f_gap")) $("f_gap").onchange = () => { p.gap_m = $("f_gap").value; changed(); barrierTouched(); };
  // a crossing's own distances (user request 7-Nov-2026): the pipe going through within tol_m, a new pipe's ends within snap_m
  if ($("f_xtol")) $("f_xtol").onchange = () => { p.tol_m = $("f_xtol").value; changed(); barrierTouched(); showProps(); };
  if ($("f_xsnap")) $("f_xsnap").onchange = () => { p.snap_m = $("f_xsnap").value; changed(); barrierTouched(); showProps(); };
  $("f_del").onclick = () => removeSelected();
  if ($("f_ohtkind")) $("f_ohtkind").onclick = () => {  // existing <-> new; a default name follows (Ex-OHT-n / Prop-OHT-n)
    const toEx = !ohtEx;
    p.existing = toEx ? "1" : "0";
    if (!toEx) p.capacity_kl = "";
    if (/^(Ex|Prop)-OHT-\d+$/.test(p.name || "")) {
      let n = 1; drawn.eachLayer(l => { if (l.kind === "oht" && l !== selected && isExOht(l.props) === toEx) n++; });
      p.name = `${toEx ? "Ex" : "Prop"}-OHT-${n}`;
    }
    label(selected); showProps(); changed();
  };
  if ($("f_kind")) $("f_kind").onclick = () => {        // a polygon read as ward / boundary the wrong way round
    const to = k === "ward" ? "boundary" : "ward";
    if (to === "boundary") drawn.eachLayer(l => { if (l.kind === "boundary" && l !== selected) { l.kind = "ward"; l.props.population = l.props.population || ""; l.setStyle(style("ward")); label(l); } });
    selected.kind = to;
    if (to === "ward") selected.props.population = selected.props.population || "";
    selected.setStyle(style(to, true)); label(selected); showProps(); changed();
  };
  const focus = $(k === "spot" ? "f_gl" : k === "ward" ? "f_pop" : k === "oht" ? "f_stg" : k === "bulk" ? "f_kld" : "f_name");
  if (focus && (k === "spot" || k === "ward" || k === "oht" || k === "bulk") && (focus.value === "")) setTimeout(() => focus.focus(), 30);
}
function removeSelected() {
  if (!selected) return;
  if (editing) toggleEdit(false);
  if (selected.kind === "barrier" || selected.kind === "zone_loop" || selected.kind === "crossing") barrierTouched();
  drawn.removeLayer(selected); selected = null; showProps(); changed();
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
}
function stopDraw() {
  if (map.dragging._draggable) map.dragging._draggable.options.clickTolerance = map.options.clickTolerance || 3;
  if (activeHandler) activeHandler.disable();
  activeHandler = null; activeKind = null;
  document.querySelectorAll(".tools button[data-kind]").forEach(b => b.classList.remove("on"));
  $("drawbar").classList.remove("show");
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
  if (kind === "oht_ex" || kind === "oht_new") {          // an OHT: existing (Ex-OHT-n) or new (Prop-OHT-n)
    const ex = kind === "oht_ex";
    let n = 1; drawn.eachLayer(l => { if (l.kind === "oht" && isExOht(l.props) === ex) n++; });
    const layer = addFeature(e.layer, "oht", { name: `${ex ? "Ex" : "Prop"}-OHT-${n}`, existing: ex ? "1" : "0",
                                              capacity_kl: "", staging_m: "", tubewells: "" });
    select(layer); stopDraw(); changed();
    return;
  }
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
    : kind === "spot" ? { name: "", gl: "" } : kind === "stp" ? { name: "STP" } : kind === "bulk" ? { name: `Bulk ${n}`, kld: "", peak: "" } : kind === "prv" ? { name: `PRV ${n}`, setting_m: "" } : kind === "tw" ? { name: `TW ${n}`, discharge_lpm: "" }
    : kind === "oht" ? { name: `OHT-${n}`, capacity_kl: "", staging_m: "", tubewells: "" } : { name: "Project boundary", population: "" };
  const layer = addFeature(e.layer, kind, props);
  if (kind === "road") snapRoad(layer);
  select(layer);
  if (kind === "boundary" || kind === "stp" || kind === "oht" || kind === "bulk" || kind === "prv" || kind === "tw" || kind === "barrier" || kind === "zone_loop" || kind === "crossing") stopDraw();
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
  let barriers = 0, roadsL = 0, roads = 0, wards = 0, pop = 0, noPop = 0, spots = 0, noGl = 0, bArea = null, stp = 0, oht = 0, noStg = 0, bPop = 0;
  drawn.eachLayer(l => {
    if (l.kind === "road") { roads++; roadsL += lengthOf(l.getLatLngs()); }
    if (l.kind === "ward") { wards++; const v = parseFloat(l.props.population); if (v > 0) pop += v; else noPop++; }
    if (l.kind === "spot") { spots++; if (l.props.gl === "" || isNaN(parseFloat(l.props.gl))) noGl++; }
    if (l.kind === "boundary") { bArea = areaOf(l); bPop = parseFloat(l.props.population) || 0; }
    if (l.kind === "stp") stp++;
    if (l.kind === "barrier") barriers++;
    if (l.kind === "oht") { oht++; if (isExOht(l.props) && (String(l.props.staging_m ?? "").trim() === "" || String(l.props.capacity_kl ?? "").trim() === "")) noStg++; }
  });
  $("sum").innerHTML = [
    ["सड़कें", `${roads} (${(roadsL / 1000).toFixed(2)} km)`],
    ["Boundary", bArea ? `${(bArea / 1e4).toFixed(1)} ha` + (bPop ? `, population ${bPop.toLocaleString("en-IN")}${pop ? " " + tr("(नहीं ली जाएगी - वार्डों में है)", "(not used - the wards have it)") : ""}` : "") : tr("नहीं", "no")],
    ["वार्ड", `${wards}, population ${pop.toLocaleString("en-IN")}`],
    ["Spot levels", `${spots}`],
    ["OHT / ESR", `${oht}`],
    ...(barriers ? [[tr("रुकावट रेखाएँ", "Barrier lines"), `${barriers}`]] : []),
  ].map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join("");
  const w = [];
  if (!roads) w.push("कम से कम एक सड़क खींचें।");
  if (noPop && !(bPop && !pop)) w.push(`${noPop} वार्ड की population नहीं भरी।`);
  if (noGl) w.push(`${noGl} spot level का GL नहीं भरा (वे नहीं गिने जाएँगे)।`);
  if ($("glmode").value === "spots" && spots - noGl < 3) w.push("Spot levels से GL के लिए कम से कम 3 spot levels चाहिए।");
  if (!oht) w.push("कोई OHT नहीं - पुरानी टंकियाँ (क्षमता, staging के साथ) लगाएँ; बाकी क्षेत्र के लिए नई OHT zoning सुझाएगी।");
  if (noStg) w.push(`${noStg} पुरानी टंकी की क्षमता या staging नहीं भरी।`);
  $("checks").innerHTML = w.map(x => `<div class="warn">• ${x}</div>`).join("");
  return { roads, spots: spots - noGl };
}
