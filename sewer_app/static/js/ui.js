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
  if (th) th.value = UI.theme;
  uiTabsState();
}
async function uiLoad() {
  let p = null;
  try {
    const r = await fetch(UI_LAUNCHER, { signal: AbortSignal.timeout(1500) });
    if (r.ok) p = await r.json();
  } catch (e) { /* the module alone: this browser's own */ }
  if (!p || !p.ok) { try { p = JSON.parse(localStorage.getItem(UI_LS) || "null"); } catch (e) { p = null; } }
  if (p) { if (p.mode) UI.mode = p.mode; if (p.theme) UI.theme = p.theme; }
  uiApply();
}
async function uiSave() {
  try { localStorage.setItem(UI_LS, JSON.stringify({ mode: UI.mode, theme: UI.theme })); } catch (e) { }
  try { await fetch(`${UI_LAUNCHER}?mode=${UI.mode}&theme=${UI.theme}`, { signal: AbortSignal.timeout(1500) }); } catch (e) { }
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
    `<div class="uirow"><span class="seg" id="uimode">` +
    `<button type="button" data-m="simple" title="${tr("ज़रूरी खाने; बाकी CPHEEO / UPJN के default पर", "The essential fields; the rest at the CPHEEO / UPJN defaults")}">Simple</button>` +
    `<button type="button" data-m="advanced" title="${tr("सब खाने और विकल्प", "Every field and option")}">Advanced</button></span>` +
    `<select id="uitheme" title="${tr("रंग: हल्का / गहरा / Windows जैसा", "Colours: light / dark / as Windows")}">` +
    `<option value="system">🖥 ${tr("Windows जैसा", "System")}</option><option value="light">☀ ${tr("हल्का", "Light")}</option>` +
    `<option value="dark">🌙 ${tr("गहरा", "Dark")}</option></select></div>` +
    `<div class="hint uisimple">${tr("Simple: छिपे खाने CPHEEO / UPJN के default पर चलते हैं - बदलने के लिए Advanced।",
                                    "Simple: the hidden fields run at the CPHEEO / UPJN defaults - Advanced to change them.")}</div>` +
    `<div id="uitabs">` + keys.map((t, i) => `<button type="button" data-t="${t[0]}"><i>${i + 1}</i>${tr(t[1], t[2])}</button>`).join("") + `</div>`;
  if (sub) sub.after(bar); else side.prepend(bar);
  const empty = document.createElement("div");
  empty.id = "uiempty"; empty.className = "hint"; empty.hidden = true;
  empty.textContent = tr("इस चरण के खाने अभी नहीं - पहले Network / Layout बनाएँ (या project खोलें)।",
                         "Nothing for this step yet - make the network / layout first (or open a project).");
  bar.after(empty);
  bar.querySelector("#uimode").onclick = e => {
    const m = e.target.closest("button"); if (!m) return;
    UI.mode = m.dataset.m; uiApply(); uiSave();
  };
  bar.querySelector("#uitheme").onchange = e => { UI.theme = e.target.value; uiApply(); uiSave(); };
  bar.querySelector("#uitabs").onclick = e => { const b = e.target.closest("button"); if (b) uiTab(b.dataset.t); };
  let t0 = null;
  try { t0 = localStorage.getItem(uiTabKey); } catch (e) { }
  uiTab(keys.some(t => t[0] === t0) ? t0 : keys[0][0]);
  // a part shown / hidden by the page (a network opened, the zoning step reached ...): the tabs follow
  new MutationObserver(() => uiTabsState()).observe(side, { attributes: true, attributeFilter: ["hidden"], subtree: true });
  if (window.matchMedia) matchMedia("(prefers-color-scheme: dark)").addEventListener("change", uiTheme);
}
uiBuild();
setTimeout(() => { UI.settled = true; }, 5000);       // not while the page opens its project
uiApply();
uiLoad();
