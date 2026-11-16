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
APP_VERSION = "0.9.22"
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


def check(timeout=15):
    """The menu's 'Check for updates' -> {ok, current, latest, newer, url, notes, setup} or {ok: False, log}."""
    try:
        r = latest(timeout)
    except Exception as e:
        return {"ok": False, "current": APP_VERSION,
                "log": f"GitHub से जवाब नहीं ({type(e).__name__}) - internet देखें / GitHub did not answer - check the internet"}
    return {"ok": True, "current": APP_VERSION, "latest": r["version"], "newer": newer(r["version"], APP_VERSION),
            "url": r["url"], "notes": r["notes"], "setup": r["setup"]}


def download(setup, folder, progress=None, timeout=60):
    """The setup into folder, its SHA-256 matched against GitHub's -> the file's path. A file that does not match is
    deleted and ValueError raised (nothing is run)."""
    if not setup or not setup.get("url") or not re.fullmatch(r"[0-9a-f]{64}", setup.get("sha256") or ""):
        raise ValueError("GitHub ने setup का SHA-256 नहीं दिया - update नहीं / GitHub gave no SHA-256: no update")
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
        raise ValueError("Download की file GitHub के SHA-256 से नहीं मिली - हटा दी, कुछ install नहीं हुआ / "
                         "the download does not match GitHub's SHA-256 - deleted, nothing installed")
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
