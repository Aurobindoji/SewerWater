// The page's tour (user request 16-Nov-2026, as an Android app shows on its first start): the page dimmed, one part
// lit at a time with a few lines beside it - Back / Next / Skip, arrow keys and Esc; shown once on the first visit
// (before the CPHEEO guidelines then), again from "▶ Tour". Its steps: TOUR_STEPS (js/guide_data.js) - sel = the
// element lit, tab = the tab opened first; a step whose element is not on the page (a DXF network has no drawing
// tools ...) is passed over. Same file in both modules.
const TOUR_KEY = "sw_tour_done_" + location.pathname;
let TOUR = null;

function tourEls() {
  if (document.getElementById("tourlit")) return;
  const lit = document.createElement("div");
  lit.id = "tourlit";
  const card = document.createElement("div");
  card.id = "tourcard";
  card.setAttribute("role", "dialog");
  card.innerHTML = `<div class="tc-n"></div><h3></h3><p></p><div class="tc-act">` +
    `<button type="button" data-a="skip">${tr("छोड़ें", "Skip")}</button><span></span>` +
    `<button type="button" data-a="back">← ${tr("पीछे", "Back")}</button>` +
    `<button type="button" data-a="next" class="primary">${tr("आगे", "Next")} →</button></div>`;
  card.onclick = e => { const b = e.target.closest("button"); if (b) tourGo(b.dataset.a); };
  const block = document.createElement("div");            // the page under the tour takes no clicks
  block.id = "tourblock";
  for (const k of ["t", "b", "l", "r"]) {                  // four dark bands around the lit part
    const d = document.createElement("div");
    d.className = "tourdim"; d.dataset.k = k;
    block.append(d);
  }
  document.body.append(block, lit, card);
}
function tourShown(el) {
  for (let x = el; x && x !== document.body; x = x.parentElement) if (x.hidden || getComputedStyle(x).display === "none") return false;
  return !!el;
}
function tourShow(i, dir = 1) {
  const S = TOUR_STEPS;
  while (i >= 0 && i < S.length) {
    const s = S[i];
    if (s.tab && window.uiTab && document.querySelector(`#uitabs button[data-t="${s.tab}"]`)) uiTab(s.tab);
    const el = document.querySelector(s.sel);
    if (el && tourShown(el)) break;
    i += dir;
  }
  if (i < 0 || i >= S.length) return tourEnd();
  TOUR = i;
  const s = S[i], el = document.querySelector(s.sel);
  el.scrollIntoView({ block: "nearest", inline: "nearest" });
  const r = el.getBoundingClientRect(), pad = 6;
  const lit = document.getElementById("tourlit"), card = document.getElementById("tourcard");
  const L = r.left - pad, Tp = r.top - pad, W = r.width + 2 * pad, Hh = Math.min(r.height, innerHeight - 40) + 2 * pad;
  Object.assign(lit.style, { left: L + "px", top: Tp + "px", width: W + "px", height: Hh + "px" });
  const px = v => Math.max(0, v) + "px";
  const box = { t: [0, 0, innerWidth, Tp], b: [0, Tp + Hh, innerWidth, innerHeight - Tp - Hh], l: [0, Tp, L, Hh],
                r: [L + W, Tp, innerWidth - L - W, Hh] };
  for (const d of document.querySelectorAll("#tourblock .tourdim")) {
    const [x, y, w, h] = box[d.dataset.k];
    Object.assign(d.style, { left: px(x), top: px(y), width: px(w), height: px(h) });
  }
  const [h, p] = EN ? s.en : s.hi;
  card.querySelector("h3").textContent = h;
  card.querySelector("p").textContent = p;
  card.querySelector(".tc-n").textContent = `${i + 1} / ${S.length}`;
  card.querySelector('[data-a="back"]').disabled = i === 0;
  card.querySelector('[data-a="next"]').textContent = i === S.length - 1 ? tr("समाप्त ✓", "Done ✓") : tr("आगे →", "Next →");
  // the card beside the lit part: right of it, else below, else above, kept on the screen
  const cw = Math.min(330, innerWidth - 24), ch = card.offsetHeight || 170;
  let x = r.right + 14, y = r.top;
  if (x + cw > innerWidth - 12) { x = Math.max(12, Math.min(r.left, innerWidth - cw - 12)); y = r.bottom + 14; }
  if (y + ch > innerHeight - 12) y = Math.max(12, r.top - ch - 14);
  Object.assign(card.style, { left: x + "px", top: Math.max(12, Math.min(y, innerHeight - ch - 12)) + "px", width: cw + "px" });
  card.querySelector('[data-a="next"]').focus();
}
function tourGo(a) {
  if (a === "skip") return tourEnd();
  if (a === "back") return tourShow(TOUR - 1, -1);
  if (TOUR >= TOUR_STEPS.length - 1) return tourEnd();
  tourShow(TOUR + 1, 1);
}
function tourKeys(e) {
  if (TOUR === null) return;
  if (e.key === "Escape") { e.preventDefault(); tourEnd(); }
  else if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); tourGo("next"); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); tourGo("back"); }
}
function tourStart() {
  if (typeof TOUR_STEPS === "undefined" || !TOUR_STEPS.length) return;
  tourEls();
  document.body.classList.add("touring");
  document.addEventListener("keydown", tourKeys, true);
  addEventListener("resize", tourReflow);
  tourShow(0, 1);
}
function tourReflow() { if (TOUR !== null) tourShow(TOUR, 1); }
function tourEnd() {
  TOUR = null;
  document.body.classList.remove("touring");
  document.removeEventListener("keydown", tourKeys, true);
  removeEventListener("resize", tourReflow);
  try { localStorage.setItem(TOUR_KEY, "1"); } catch (e) { }
  if (window.uiTab) uiTab("project");
}
window.tourStart = tourStart;
// the first visit: the tour once the page has opened (its loading cover gone); the CPHEEO guidelines window that the
// start page opens is closed for it (the tour's last step points to it)
(() => {
  let done = false;
  try { done = !!localStorage.getItem(TOUR_KEY); } catch (e) { done = true; }
  if (done) return;
  const t0 = Date.now();
  const wait = setInterval(() => {
    const busy = document.getElementById("loading") && document.getElementById("loading").classList.contains("show");
    if (busy && Date.now() - t0 < 30000) return;
    clearInterval(wait);
    const g = document.getElementById("guide");
    if (g && g.classList.contains("show") && window.hideGuide) hideGuide();
    tourStart();
  }, 400);
})();
