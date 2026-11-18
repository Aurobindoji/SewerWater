"""The app's own name and version, its About page, and its updates from GitHub (user decisions 10-Nov-2026: an
About page; updates checked only from the menu, installed in one click - the setup downloaded, its SHA-256 matched
against the one GitHub gives, then run).

APP_VERSION is the one place of the version: build_setup.bat passes it to the setup (installer\\SewerWater.iss).
"""
import hashlib
import html
import json
import os
import re
import urllib.request

APP_NAME = "PravaahForge"                     # user request 16-Nov-2026 (was "Sewer & Water Network Design")
APP_VERSION = "0.9.34"
REPO = "Aurobindoji/SewerWater"
REPO_URL = f"https://github.com/{REPO}"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
UA = {"User-Agent": "SewerWater-app-updater", "Accept": "application/vnd.github+json"}


def version_tuple(v):
    """'v0.9.1' / '0.9.1 (beta)' -> (0, 9, 1); anything else -> ()."""
    m = re.match(r"\s*v?(\d+(?:\.\d+)*)", str(v or ""))
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def newer(a, b):
    """True when version a is newer than version b."""
    ta, tb = version_tuple(a), version_tuple(b)
    n = max(len(ta), len(tb))
    return ta + (0,) * (n - len(ta)) > tb + (0,) * (n - len(tb))


def latest(timeout=15):
    """The newest published release on GitHub -> {version, tag, url, notes, setup: {name, url, size, sha256} or None}.
    Raises OSError / ValueError when GitHub cannot be reached or answers oddly."""
    with urllib.request.urlopen(urllib.request.Request(LATEST_API, headers=UA), timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    tag = d.get("tag_name") or ""
    if not version_tuple(tag):
        raise ValueError(f"GitHub: no version in the release's tag {tag!r}")
    setup = None
    for a in d.get("assets") or []:
        if re.fullmatch(r"SewerWater_Setup_[\w.\-]+\.exe", a.get("name") or ""):
            dig = a.get("digest") or ""
            setup = {"name": a["name"], "url": a["browser_download_url"], "size": a.get("size") or 0,
                     "sha256": dig.split(":", 1)[1].lower() if dig.startswith("sha256:") else ""}
            break
    return {"version": tag.lstrip("v"), "tag": tag, "url": d.get("html_url") or REPO_URL,
            "notes": d.get("body") or "", "setup": setup}


# the updater's messages in one language (user request 16-Nov-2026, as the About page)
MSG = {
    "hi": {"no_answer": "GitHub से जवाब नहीं ({err}) - internet देखें।",
           "no_sha": "GitHub ने setup का SHA-256 नहीं दिया - update नहीं।",
           "sha_bad": "Download की file GitHub के SHA-256 से नहीं मिली - हटा दी, कुछ install नहीं हुआ।",
           "no_newer": "कोई नया version नहीं।", "no_file": "Setup नहीं मिला।"},
    "en": {"no_answer": "GitHub did not answer ({err}) - check the internet.",
           "no_sha": "GitHub gave no SHA-256 for the setup - no update.",
           "sha_bad": "The download does not match GitHub's SHA-256 - deleted, nothing installed.",
           "no_newer": "No newer version.", "no_file": "The setup was not found."},
}


def msg(key, lang=None, **kw):
    """One of the updater's messages in the pages' language (or lang)."""
    return MSG[look(lang, False)[0]][key].format(**kw)


def check(timeout=15, lang=None):
    """The menu's 'Check for updates' -> {ok, current, latest, newer, url, notes, setup} or {ok: False, log}."""
    try:
        r = latest(timeout)
    except Exception as e:
        return {"ok": False, "current": APP_VERSION, "log": msg("no_answer", lang, err=type(e).__name__)}
    return {"ok": True, "current": APP_VERSION, "latest": r["version"], "newer": newer(r["version"], APP_VERSION),
            "url": r["url"], "notes": r["notes"], "setup": r["setup"]}


def download(setup, folder, progress=None, timeout=60, lang=None):
    """The setup into folder, its SHA-256 matched against GitHub's -> the file's path. A file that does not match is
    deleted and ValueError raised (nothing is run)."""
    if not setup or not setup.get("url") or not re.fullmatch(r"[0-9a-f]{64}", setup.get("sha256") or ""):
        raise ValueError(msg("no_sha", lang))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, os.path.basename(setup["name"]))
    h, done = hashlib.sha256(), 0
    req = urllib.request.Request(setup["url"], headers={"User-Agent": UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(path + ".part", "wb") as fh:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            fh.write(b)
            h.update(b)
            done += len(b)
            if progress:
                progress(done, setup.get("size") or 0)
    if h.hexdigest() != setup["sha256"]:
        os.remove(path + ".part")
        raise ValueError(msg("sha_bad", lang))
    if os.path.exists(path):
        os.remove(path)
    os.rename(path + ".part", path)
    return path


def look(lang=None, dark=None):
    """(lang "hi" / "en", dark True / False): given, else the pages' choice (launcher.server.ui_prefs) - theme
    "system" = Windows' own app colours (AppsUseLightTheme)."""
    p = {}
    if lang not in ("hi", "en") or dark is None:
        try:
            from .server import ui_prefs
            p = ui_prefs()
        except Exception:
            p = {}
    if lang not in ("hi", "en"):
        lang = p.get("lang") if p.get("lang") in ("hi", "en") else "hi"
    if dark is None:
        theme = p.get("theme", "system")
        dark = theme == "dark" or (theme == "system" and windows_dark())
    return lang, bool(dark)


def windows_dark():
    """Windows set to dark app colours."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except Exception:
        return False


ABOUT_TXT = {
    "hi": {"sub": "सीवर और पेयजल network design, CPHEEO manuals के अनुसार।", "version": "Version",
           "licence": "Licence", "licence_v": "GNU GPL v3.0 या उसके बाद का", "source": "Source code",
           "master": "Master folder (data)", "credits": "श्रेय",
           "c1": "Aurobindoji - engineering की ज़रूरतें, design के निर्णय, संदर्भ data और जाँच।",
           "c2": "Claude (Anthropic) - Aurobindoji के साथ मिलकर लिखा, AI coding सहायक के रूप में।",
           "warn": "Beta: यह app design में सहायता के लिए है। Tender या निर्माण से पहले हर नतीजा योग्य engineer से "
                   "जँचवाएँ।",
           "upd_desktop": "Update: menu <b>App → Update देखें…</b>",
           "upd_web": "Update: desktop app का menu <b>App → Update देखें…</b>, या GitHub का "
                      "<a href=\"{url}/releases\" target=\"_blank\">Releases</a> पन्ना।",
           "free": "यह program GNU General Public License v3.0 (या उसके बाद के) के अंतर्गत free software है और इसकी "
                   "कोई WARRANTY नहीं है।"},
    "en": {"sub": "Sewerage and water supply network design to the CPHEEO manuals.", "version": "Version",
           "licence": "Licence", "licence_v": "GNU GPL v3.0 or later", "source": "Source code",
           "master": "Data folder / Master folder", "credits": "Credits",
           "c1": "Aurobindoji - the engineering requirements, design decisions, reference data and testing.",
           "c2": "Claude (Anthropic) - written together with Aurobindoji, as an AI coding assistant.",
           "warn": "Beta: the app is a design aid. A qualified engineer must check every result before it is used "
                   "for tender or construction.",
           "upd_desktop": "Update: menu <b>App → Check for updates…</b>",
           "upd_web": "Updates: the desktop app's menu <b>App → Check for updates…</b>, or the "
                      "<a href=\"{url}/releases\" target=\"_blank\">Releases</a> page.",
           "free": "This program is free software under the GNU General Public License v3.0 or later, and comes with "
                   "ABSOLUTELY NO WARRANTY."},
}


def about_html(master=None, desktop=False, lang=None, dark=None):
    """The About page (the desktop app's menu, the start page's link) in one language (user request 16-Nov-2026: Hindi
    or English, not both) and in the pages' theme."""
    lang, dark = look(lang, dark)
    t, e = ABOUT_TXT[lang], html.escape
    rows = [(t["version"], f"{APP_VERSION} (beta)"), (t["licence"], t["licence_v"]),
            (t["source"], f'<a href="{REPO_URL}" target="_blank">{REPO_URL}</a>')]
    if master:
        rows.append((t["master"], e(master)))
    tr = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
    upd = t["upd_desktop"] if desktop else t["upd_web"].format(url=REPO_URL)
    return f"""<!doctype html><html lang="{lang}" data-theme="{'dark' if dark else 'light'}"><head><meta charset="utf-8">
<title>About - {e(APP_NAME)}</title><style>
:root{{--bg:#f5f7fa;--card:#fff;--text:#222;--muted:#555;--head:#0d47a1;--link:#1565c0;--warnbg:#fff8e1;--warnline:#f9a825;
--shadow:#0002}}
:root[data-theme="dark"]{{--bg:#15171c;--card:#22262d;--text:#e3e5e8;--muted:#9ba1aa;--head:#8ab4ff;--link:#8ab4ff;
--warnbg:#3a3220;--warnline:#c9a227;--shadow:#0008;color-scheme:dark}}
body{{font:15px "Segoe UI","Nirmala UI",sans-serif;margin:0;background:var(--bg);color:var(--text)}}
.box{{max-width:620px;margin:32px auto;background:var(--card);border-radius:10px;padding:24px 30px;box-shadow:0 2px 10px var(--shadow)}}
h2{{margin:0 0 4px;color:var(--head)}} .sub{{color:var(--muted);margin-bottom:14px}} table{{border-collapse:collapse;margin:10px 0 14px}}
th{{text-align:left;padding:4px 14px 4px 0;color:var(--muted);font-weight:600;vertical-align:top}} td{{padding:4px 0;word-break:break-all}}
.hint{{color:var(--muted);font-size:13px}} .warn{{background:var(--warnbg);border-left:4px solid var(--warnline);padding:8px 12px;font-size:14px}}
a{{color:var(--link)}}</style></head><body><div class="box">
<h2>{e(APP_NAME)}</h2>
<div class="sub">{t["sub"]}</div>
<table>{tr}</table>
<p><b>{t["credits"]}</b><br>{t["c1"]}<br>{t["c2"]}</p>
<div class="warn">{t["warn"]}</div>
<p class="hint">{upd}</p>
<p class="hint">{t["free"]}</p></div></body></html>"""


# the update window (menu App -> Check for updates) in one language and the pages' theme (user request 16-Nov-2026,
# as the About page); {cur} / {new} / {name} / {size} filled in by its script
UPDATE_TXT = {
    "hi": {"title": "Update देखें", "checking": "GitHub पर देख रहे हैं …",
           "newest": "✔ नया version यही है: {cur}", "available": "नया version <b>{new}</b> उपलब्ध है (अभी {cur})",
           "source": "App source से चल रहा है - update के लिए git pull करें।",
           "no_setup": "इस release में setup नहीं है।",
           "how": "App बंद होकर setup चलेगा और नया version अपने-आप खुलेगा - पहले सब काम सहेज लें। "
                  "{name}, {size}; SHA-256 GitHub से मिलाया जाएगा।",
           "install": "Download और install", "confirm": "सब काम सहेज लिया? App बंद होकर update होगा।",
           "downloading": "Download हो रहा है …", "matched": "✔ SHA-256 मिला - setup चल रहा है, app बंद हो रहा है …"},
    "en": {"title": "Check for updates", "checking": "Checking GitHub …",
           "newest": "✔ You have the newest version: {cur}", "available": "Version <b>{new}</b> is available (you have {cur})",
           "source": "The app runs from source: update it with git pull.",
           "no_setup": "This release has no setup.",
           "how": "The app closes, the setup runs and the new version opens by itself - save your work first. "
                  "{name}, {size}; its SHA-256 is matched against GitHub's.",
           "install": "Download and install", "confirm": "Is all your work saved? The app will close and update.",
           "downloading": "Downloading …", "matched": "✔ SHA-256 matched - the setup runs, the app closes …"},
}


def update_html(lang=None, dark=None):
    """The update window's page: its texts in one language, its colours in the theme (the About page's)."""
    lang, dark = look(lang, dark)
    t = UPDATE_TXT[lang]
    return f"""<!doctype html><html lang="{lang}" data-theme="{'dark' if dark else 'light'}"><head><meta charset="utf-8">
<title>{html.escape(t["title"])} - {html.escape(APP_NAME)}</title><style>
:root{{--bg:#f5f7fa;--card:#fff;--text:#222;--muted:#666;--head:#0d47a1;--ok:#2e7d32;--err:#c62828;--pre:#f3f5f8;
--btn:#1565c0;--shadow:#0002}}
:root[data-theme="dark"]{{--bg:#15171c;--card:#22262d;--text:#e3e5e8;--muted:#9ba1aa;--head:#8ab4ff;--ok:#81c784;
--err:#ef9a9a;--pre:#1a1d22;--btn:#3d7be0;--shadow:#0008;color-scheme:dark}}
body{{font:15px "Segoe UI","Nirmala UI",sans-serif;margin:0;background:var(--bg);color:var(--text)}}
.box{{max-width:600px;margin:28px auto;background:var(--card);border-radius:10px;padding:22px 28px;box-shadow:0 2px 10px var(--shadow)}}
h2{{margin:0 0 10px;color:var(--head)}} .hint{{color:var(--muted);font-size:13px}} .ok{{color:var(--ok)}} .err{{color:var(--err)}}
pre{{white-space:pre-wrap;background:var(--pre);border-radius:6px;padding:10px;max-height:220px;overflow:auto;font:13px Consolas,monospace}}
button{{font:15px "Segoe UI",sans-serif;padding:8px 16px;border-radius:6px;border:1px solid var(--btn);background:var(--btn);
color:#fff;cursor:pointer;margin-top:8px}} button:disabled{{opacity:.45;cursor:default}}
progress{{width:100%;height:16px;margin-top:10px;accent-color:var(--btn)}}</style></head><body><div class="box">
<h2>{html.escape(t["title"])}</h2><div id="st">{html.escape(t["checking"])}</div>
<div id="more"></div></div><script>
const T = {json.dumps(t, ensure_ascii=False)};
const api = () => window.pywebview.api;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;"}}[c]));
const fill = (s, o) => s.replace(/\\{{(\\w+)\\}}/g, (m, k) => k in o ? o[k] : m);
async function go() {{
  const r = await api().check_update();
  if (!r.ok) {{ $("st").innerHTML = `<span class="err">${{esc(r.log)}}</span>`; return; }}
  if (!r.newer) {{ $("st").innerHTML = `<span class="ok">${{fill(esc(T.newest), {{cur: esc(r.current)}})}}</span>`; return; }}
  const mb = r.setup ? (r.setup.size / 1048576).toFixed(1) + " MB" : "";
  $("st").innerHTML = fill(T.available, {{new: esc(r.latest), cur: esc(r.current)}});
  let h = `<pre>${{esc(r.notes || "")}}</pre>`;
  if (!r.frozen) h += `<div class="hint">${{esc(T.source)}}</div>`;
  else if (!r.setup) h += `<div class="err">${{esc(T.no_setup)}}</div>`;
  else h += `<div class="hint">${{fill(esc(T.how), {{name: esc(r.setup.name), size: mb}})}}</div>
<button id="inst">${{esc(T.install)}}</button><progress id="pg" value="0" max="1" hidden></progress><div id="msg"></div>`;
  $("more").innerHTML = h;
  if ($("inst")) $("inst").onclick = install;
}}
async function install() {{
  if (!confirm(T.confirm)) return;
  $("inst").disabled = true; $("pg").hidden = false; $("msg").textContent = T.downloading;
  await api().start_update();
  const t = setInterval(async () => {{
    const p = await api().update_progress();
    if (p.size) $("pg").value = p.done / p.size;
    if (p.error) {{ clearInterval(t); $("msg").innerHTML = `<span class="err">${{esc(p.error)}}</span>`; $("inst").disabled = false; return; }}
    if (p.path) {{
      clearInterval(t);
      $("msg").innerHTML = `<span class="ok">${{esc(T.matched)}}</span>`;
      const e = await api().run_update();
      if (e) {{ $("msg").innerHTML = `<span class="err">${{esc(e)}}</span>`; $("inst").disabled = false; }}
    }}
  }}, 400);
}}
let began = false;
const begin = () => {{ if (!began) {{ began = true; go(); }} }};
window.addEventListener("pywebviewready", begin);
if (window.pywebview && window.pywebview.api) begin();
</script></body></html>"""
