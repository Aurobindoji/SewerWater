// The Outputs tab's list (user request 16-Nov-2026), the same in both modules; OUT_KINDS (files.js) are the module's
// own outputs: {hi, en, re (the file's path in the output folder), make (the id of the step's button that makes it),
// tab (the step's tab), note, all (every file of the kind, not only the newest)}.
let OUTS = null;
const outName = () => $("pname").value;
const outSize = b => b >= 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB";
function outRow(f, cls = "") {
  return `<div class="ofile ${cls}"><span class="oname" title="${esc(f.file)}">${esc(f.file.split("/").pop())}</span>` +
    `<span class="otime">${esc(f.time)} · ${outSize(f.size)}</span>` +
    `<button type="button" data-open="${esc(f.file)}" title="${tr("अपने program में खोलें (Excel, AutoCAD …)", "Open in its program (Excel, AutoCAD …)")}">${tr("खोलें", "Open")}</button>` +
    `<button type="button" data-folder="${esc(f.file)}" title="${tr("Explorer में folder खोलें, यह file चुनी हुई", "Open its folder in Explorer, the file selected")}">📁</button></div>`;
}
async function outRefresh() {
  const box = $("outlist");
  if (!box) return;
  if (!outName()) { box.innerHTML = ""; return; }
  try { OUTS = await api("/api/outputs?name=" + encodeURIComponent(outName())); } catch (e) { OUTS = null; }
  if (!OUTS || !OUTS.ok) { box.innerHTML = `<div class="hint">${tr("सूची नहीं मिली", "No list")}</div>`; return; }
  const used = new Set();
  let html = `<div class="hint ofolder">${tr("जगह", "Location")}: <code>${esc(OUTS.folder)}</code><br>` +
    `<button type="button" data-folder="" class="txtbtn">📁 ${tr("Folder खोलें", "Open the folder")}</button>` +
    `<button type="button" id="outre" class="txtbtn" title="${tr("सूची फिर से पढ़ें", "Read the list again")}">↻ ${tr("ताज़ा करें", "Refresh")}</button></div>`;
  for (const k of OUT_KINDS) {
    const fs = OUTS.files.filter(f => k.re.test(f.file));
    fs.forEach(f => used.add(f.file));
    if (!fs.length && !k.make && !k.tab) continue;
    const mk = k.make ? `<button type="button" class="primary" data-make="${k.make}">${fs.length ? tr("फिर बनाएँ", "Make again") : tr("बनाएँ", "Make")}</button>`
      : k.tab ? `<button type="button" data-goto="${k.tab}">${tr("चरण पर जाएँ", "Go to the step")}</button>` : "";
    const latest = k.all ? fs.slice(0, 12) : fs.slice(0, 1);
    html += `<div class="ocard"><div class="ohead"><b>${esc(tr(k.hi, k.en))}</b>${mk}</div>` +
      (k.note ? `<div class="hint" style="margin:0">${esc(tr(k.note[0], k.note[1]))}</div>` : "") +
      (latest.length ? latest.map(f => outRow(f)).join("") : `<div class="hint" style="margin:2px 0">${tr("अभी नहीं बनी", "not made yet")}</div>`) +
      (fs.length > latest.length ? `<details><summary class="hint">${tr(`पुरानी ${fs.length - latest.length}`, `${fs.length - latest.length} older`)}</summary>` +
        fs.slice(latest.length).map(f => outRow(f, "old")).join("") + `</details>` : "") + `</div>`;
  }
  const rest = OUTS.files.filter(f => !used.has(f.file));
  if (rest.length) html += `<details class="ocard"><summary><b>${tr(`बाकी files (${rest.length})`, `Other files (${rest.length})`)}</b></summary>` +
    rest.map(f => outRow(f)).join("") + `</details>`;
  box.innerHTML = html;
}
async function outOpen(file, folder) {
  try {
    const r = await api("/api/open_output", { name: outName(), file, folder });
    if (!r.ok) alert(r.log || tr("नहीं खुली", "not opened"));
  } catch (e) { alert(String(e)); }
}
document.addEventListener("click", e => {
  const b = e.target.closest("#outlist button");
  if (!b) return;
  if (b.id === "outre") return outRefresh();
  if (b.dataset.open !== undefined) return outOpen(b.dataset.open, false);
  if (b.dataset.folder !== undefined) return outOpen(b.dataset.folder, true);
  if (b.dataset.goto) return uiTab(b.dataset.goto);
  if (b.dataset.make) {                                  // the step's own button: its checks and messages stay there
    const m = $(b.dataset.make);
    if (!m || m.disabled) return alert(tr("पहले उस चरण को चलाएँ", "Run that step first"));
    m.click();
    for (const t of [1500, 5000, 15000, 40000]) setTimeout(outRefresh, t);
  }
});
document.addEventListener("uitab", e => { if (e.detail === "out") outRefresh(); });
