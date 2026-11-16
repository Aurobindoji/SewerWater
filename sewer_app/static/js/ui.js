// The map page's look (user request 16-Nov-2026): the sidebar in tabs (the work's steps), a Simple / Advanced switch
// (Simple: the essential fields only, the rest at the app's CPHEEO / UPJN presets when run) and a light / dark / system
// theme (dark: the map's tiles dimmed too). Mode and theme are kept by the start page's server (port 8764) for every
// page; a module run alone keeps them in this browser. Runs first of the page's scripts (needs i18n.js's tr only).
const UI_TABS = [["project", "Project", "Project"], ["network", "Network", "Network"], ["pop", "आबादी", "Population"],
  ["zoning", "Zoning", "Zoning"], ["design", "Network Design", "Network Design"], ["tank", "Tank Design", "Tank Design"],
  ["out", "Outputs", "Outputs"]];
const UI = { mode: "advanced", theme: "system", tab: "project" };
const UI_LAUNCHER = "http://127.0.0.1:8764/api/ui";
const UI_LS = "sw_ui";
const uiTabKey = "sw_tab_" + location.pathname;

function uiTheme() {
  const dark = UI.theme === "dark" || (UI.theme === "system" && window.matchMedia &&
                                       matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}
function uiApply() {
  uiTheme();
  document.body.classList.toggle("simple", UI.mode === "simple");
  for (const b of document.querySelectorAll("#uimode button")) b.classList.toggle("on", b.dataset.m === UI.mode);
  const th = document.getElementById("uitheme");
  if (th) {                                   // the icon of the look now; a click gives the other one
    const dark = document.documentElement.dataset.theme === "dark";
    th.textContent = dark ? "🌙" : "☀";
    th.title = dark ? tr("गहरा रंग - हल्के के लिए click", "Dark - click for light")
                    : tr("हल्का रंग - गहरे के लिए click", "Light - click for dark");
  }
  uiTabsState();
}
async function uiLoad() {
  let p = null;
  try {
    const lang = typeof LANG === "string" ? `?lang=${LANG}` : "";        // the desktop app's tray / menu follow it
    const r = await fetch(UI_LAUNCHER + lang, { signal: AbortSignal.timeout(1500) });
    if (r.ok) p = await r.json();
  } catch (e) { /* the module alone: this browser's own */ }
  if (!p || !p.ok) { try { p = JSON.parse(localStorage.getItem(UI_LS) || "null"); } catch (e) { p = null; } }
  if (p) { if (p.mode) UI.mode = p.mode; if (p.theme) UI.theme = p.theme; }
  uiApply();
}
async function uiSave() {
  try { localStorage.setItem(UI_LS, JSON.stringify({ mode: UI.mode, theme: UI.theme })); } catch (e) { }
  try { await fetch(`${UI_LAUNCHER}?mode=${UI.mode}&theme=${UI.theme}`, { signal: AbortSignal.timeout(1500) }); } catch (e) { }
  try { if (window.pywebview && window.pywebview.api && window.pywebview.api.restyle) window.pywebview.api.restyle(); } catch (e) { }   // the desktop app's title bars / menus
}
// Simple mode: the hidden fields go at the page's presets (the app's defaults), whatever they hold
function uiSimple(q, preset) { return UI.mode === "simple" ? Object.assign(q, JSON.parse(JSON.stringify(preset))) : q; }

// ---- the tabs: every part of the sidebar marked data-tab; the others of the chosen tab are hidden (CSS)
function uiHasContent(key) {
  for (const el of document.querySelectorAll(`#side [data-tab="${key}"]`)) {
    let x = el, shown = true;
    for (; x && x.id !== "side"; x = x.parentElement) if (x.hidden) { shown = false; break; }
    if (shown) return true;
  }
  return false;
}
function uiTabsState() {
  const bs = [...document.querySelectorAll("#uitabs button")];
  const cur = bs.findIndex(b => b.dataset.t === UI.tab);
  for (const [i, b] of bs.entries()) {
    const has = uiHasContent(b.dataset.t);
    if (has && UI.settled && b.classList.contains("dim") && i === cur + 1) b.classList.add("new");  // the next step just opened up
    b.classList.toggle("dim", !has);
    b.classList.toggle("on", b.dataset.t === UI.tab);
  }
  const e = document.getElementById("uiempty"), v = uiHasContent(UI.tab);
  if (e && e.hidden !== v) e.hidden = v;              // only a change: the observer below watches 'hidden'
}
function uiTab(key) {
  UI.tab = key;
  document.body.dataset.tab = key;
  const b = document.querySelector(`#uitabs button[data-t="${key}"]`);
  if (b) b.classList.remove("new");
  try { localStorage.setItem(uiTabKey, key); } catch (e) { }
  uiTabsState();
  document.getElementById("side").scrollTop = 0;
  document.dispatchEvent(new CustomEvent("uitab", { detail: key }));       // the Outputs tab reads its list then
}
function uiBuild() {
  const side = document.getElementById("side");
  const sub = side.querySelector(":scope > .sub");
  const keys = UI_TABS.filter(t => side.querySelector(`[data-tab="${t[0]}"]`));
  const bar = document.createElement("div");
  bar.id = "uibar";
  bar.innerHTML =
    `<div class="uirow" id="uitools"><span id="uihelp"><button type="button" id="uiguide" title="${tr("इस चरण की पूरी मार्गदर्शिका: हर खाना, क्यों, कहाँ से, CPHEEO / UPJN ref", "This step's full guide: every field, why, from where, CPHEEO / UPJN ref")}">❓ ${tr("मदद", "Help")}</button>` +
    `<button type="button" id="uitour" title="${tr("Page का tour फिर से", "The page's tour again")}">▶ Tour</button></span>` +
    `<span id="uilinks"></span><button type="button" id="uitheme"></button></div>` +
    `<div class="uirow"><span class="seg" id="uimode">` +
    `<button type="button" data-m="simple" title="${tr("ज़रूरी खाने; बाकी CPHEEO / UPJN के default पर", "The essential fields; the rest at the CPHEEO / UPJN defaults")}">Simple</button>` +
    `<button type="button" data-m="advanced" title="${tr("सब खाने और विकल्प", "Every field and option")}">Advanced</button></span>` +
    `</div>` +
    `<div class="hint uisimple">${tr("Simple: छिपे खाने CPHEEO / UPJN के default पर चलते हैं - बदलने के लिए Advanced।",
                                    "Simple: the hidden fields run at the CPHEEO / UPJN defaults - Advanced to change them.")}</div>` +
    `<div id="uitabs">` + keys.map((t, i) => `<button type="button" data-t="${t[0]}"><i>${i + 1}</i>${tr(t[1], t[2])}</button>`).join("") + `</div>`;
  if (sub) sub.after(bar); else side.prepend(bar);
  // user request 16-Nov-2026: help, tour, CPHEEO, the language and the other app close together on the title's line,
  // on its right, the theme an icon at the far right (on a narrow sidebar the group goes under the title, still right)
  const tools = bar.querySelector("#uitools");
  const head = document.getElementById("title");
  if (head && head.parentElement) { head.parentElement.classList.add("uihead"); head.parentElement.append(tools); }
  const links = tools.querySelector("#uilinks");
  for (const id of ["gopen", "langsw", "otherapp"]) {
    const a = document.getElementById(id);
    if (a) { const old = a.parentElement; links.append(a); if (old && !old.querySelector("a")) old.remove(); }
  }
  const empty = document.createElement("div");
  empty.id = "uiempty"; empty.className = "hint"; empty.hidden = true;
  empty.textContent = tr("इस चरण के खाने अभी नहीं - पहले Network / Layout बनाएँ (या project खोलें)।",
                         "Nothing for this step yet - make the network / layout first (or open a project).");
  bar.after(empty);
  bar.querySelector("#uimode").onclick = e => {
    const m = e.target.closest("button"); if (!m) return;
    UI.mode = m.dataset.m; uiApply(); uiSave();
  };
  tools.querySelector("#uitheme").onclick = () => {
    UI.theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; uiApply(); uiSave();
  };
  bar.querySelector("#uitabs").onclick = e => { const b = e.target.closest("button"); if (b) uiTab(b.dataset.t); };
  // the guide (guide.html, its chapter of the tab shown) in a window of its own; the tour (tour.js)
  tools.querySelector("#uiguide").onclick = () => window.open(`/guide?lang=${LANG}#${UI.tab}`, "sw_guide");
  tools.querySelector("#uitour").onclick = () => { if (window.tourStart) tourStart(); };
  let t0 = null;
  try { t0 = localStorage.getItem(uiTabKey); } catch (e) { }
  uiTab(keys.some(t => t[0] === t0) ? t0 : keys[0][0]);
  // a part shown / hidden by the page (a network opened, the zoning step reached ...): the tabs follow
  new MutationObserver(() => uiTabsState()).observe(side, { attributes: true, attributeFilter: ["hidden"], subtree: true });
  if (window.matchMedia) matchMedia("(prefers-color-scheme: dark)").addEventListener("change", uiTheme);
}
// ---- an active tool shown at the mouse (user request 16-Nov-2026: after pressing a tool button nothing told that it
// was on until the mouse reached the map): the cursor a cross wherever it is, and a note following it - the tool and
// what to do next (go to the map, click the place ...). Two slots: "draw" (a drawing tool, draw.js) and "net" (a
// network tool, dxfnet.js); the drawing one shown first. On the map a drawing tool has Leaflet.draw's own note at the
// mouse, so this one only off the map there.
const TOOLHINT = { draw: null, net: null, x: -1, y: -1, onMap: false };
{
  const st = document.createElement("style");
  st.textContent = `#toolfollow { position: fixed; z-index: 4000; pointer-events: none; max-width: 300px; padding: 5px 9px;
      border-radius: 6px; background: rgba(32, 33, 36, .92); color: #fff; font: 12px/1.4 system-ui, sans-serif;
      box-shadow: 0 2px 8px #0005; display: none; }
    #toolfollow b { color: #ffd54f; font-weight: 600; }
    #toolfollow .k { opacity: .75; font-size: 11px; }
    body.toolon #side, body.toolon #uibar { cursor: crosshair; }
    body.toolon .leaflet-container { cursor: crosshair; }`;
  document.head.appendChild(st);
}
function toolHintShow() {
  let el = document.getElementById("toolfollow");
  const h = TOOLHINT.draw || TOOLHINT.net;
  document.body.classList.toggle("toolon", !!h);
  if (!h) { if (el) el.style.display = "none"; return; }
  if (!el) { el = document.createElement("div"); el.id = "toolfollow"; document.body.appendChild(el); }
  if (el._h !== h) {
    el._h = h;
    el.innerHTML = `<b>${h.name.replace(/[<&]/g, c => (c === "<" ? "&lt;" : "&amp;"))}</b> ${tr("चालू", "on")}<br>` +
      `${h.what.replace(/[<&]/g, c => (c === "<" ? "&lt;" : "&amp;"))}<br><span class="k">${h.slot === "draw" ? tr("Esc या बटन दोबारा = बंद", "Esc or the button again = off") : tr("Esc या \"चुनें\" = बंद", "Esc or \"Select\" = off")}</span>`;
  }
  const hideHere = TOOLHINT.onMap && h === TOOLHINT.draw && h.ownOnMap;
  if (TOOLHINT.x < 0 || hideHere) { el.style.display = "none"; return; }
  el.style.display = "block";
  const w = el.offsetWidth, ht = el.offsetHeight;
  let x = TOOLHINT.x + 16, y = TOOLHINT.y + 18;
  if (x + w > innerWidth - 4) x = TOOLHINT.x - w - 12;
  if (y + ht > innerHeight - 4) y = TOOLHINT.y - ht - 12;
  el.style.left = Math.max(4, x) + "px"; el.style.top = Math.max(4, y) + "px";
}
// slot "draw" | "net"; name: the tool (its button's text); what: what to do now; ownOnMap: the map shows its own note
function uiToolHint(slot, name, what, ownOnMap) {
  TOOLHINT[slot] = name ? { slot, name, what, ownOnMap: !!ownOnMap } : null;
  toolHintShow();
}
document.addEventListener("pointermove", e => {
  TOOLHINT.x = e.clientX; TOOLHINT.y = e.clientY;
  TOOLHINT.onMap = !!(e.target.closest && e.target.closest(".leaflet-container"));
  if (TOOLHINT.draw || TOOLHINT.net) toolHintShow();
}, { passive: true });
document.addEventListener("pointerleave", () => { TOOLHINT.x = -1; toolHintShow(); });
// what a drawing tool asks for, by its kind
function toolWhat(kind) {
  const line = ["road", "barrier", "crossing"], area = ["boundary", "ward", "zone_loop", "lasso"];
  if (line.includes(kind)) return tr("नक्शे पर जाएँ: हर click एक बिंदु; आखिरी बिंदु पर दोबारा click, Enter या right-click से पूरा",
    "Go to the map: each click a point; click the last point again, Enter or right-click to finish");
  if (area.includes(kind)) return tr("नक्शे पर जाएँ और घेरा खींचें: हर click एक कोना; Enter या right-click से पूरा",
    "Go to the map and draw the area: each click a corner; Enter or right-click to finish");
  if (kind === "prv") return tr("नक्शे पर जाएँ और pipe के ऊपर उसकी जगह click करें", "Go to the map and click its place on the pipe");
  return tr("नक्शे पर जाएँ और उसकी जगह click करें", "Go to the map and click its place");
}
function toolName(sel) {
  const b = document.querySelector(sel);
  return b ? b.textContent.replace(/\s+/g, " ").trim() : "";
}

uiBuild();
setTimeout(() => { UI.settled = true; }, 5000);       // not while the page opens its project
uiApply();
uiLoad();
