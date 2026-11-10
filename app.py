"""The map UI as a desktop app (user request 30-Oct-2026): the start page (the launcher's: language, then sewer or
water) in a window of its own (pywebview: Edge WebView2 on Windows) - no browser, no address bar, no tabs. Only the
module chosen is started, in that same window (user decision 10-Nov-2026: the two apps fully independent); the other
starts only from its button in a module's page, in a second window. Closing every window ends the app (and its
servers).

    .venv\\Scripts\\pythonw app.py          (desktop.bat; packed: SewerWater.exe, its setup: installer\\SewerWater.iss)

All the data in one master folder the user chooses with Windows' folder dialog the first time (user request
30-Oct-2026), in sub-folders:
    <master>\\Sewer\\projects, Sewer\\output      the sewer module's (SEWER_APP_HOME)
    <master>\\Water\\projects, Water\\output      the water module's (WATER_APP_HOME)
    <master>\\App                                the window's own data (language, last project ...) and the log
Only where the master folder is, is kept outside it: %APPDATA%\\SewerWater\\config.json. Menu "App": open the master
folder, choose another one (the app then starts again on it).

The pages and the servers are the same as in the browser: a server already running on its port with this code is
used as it is; one with older code (or another program) on the port: the window says so instead of the app.
"""
import json
import os
import sys
import threading
import time
import urllib.request

import webview
from webview.menu import Menu, MenuAction

TITLE = "Sewer & Water network design"
START_URL = "http://127.0.0.1:8764/"              # the launcher's start page
CONFIG = os.environ.get("APP_CONFIG") or os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                                                      "SewerWater", "config.json")
SUBDIRS = {"sewer": "Sewer", "water": "Water", "app": "App"}
WINDOW = {"text_select": True, "zoomable": True,     # tables / logs copied; Ctrl + / - as in the browser
          "maximized": not os.environ.get("APP_DEBUG_PORT"),
          "minimized": bool(os.environ.get("APP_DEBUG_PORT"))}   # checks from outside: out of the user's way

# window.open of the pages (the start page opens the water page so): a window of the app, not a browser tab
OPEN_JS = """
if (!window.__appOpen) {
  window.__appOpen = true;
  window.open = function (url, name) {
    var u = new URL(url, location.href).href;
    if (window.pywebview && window.pywebview.api) window.pywebview.api.open_window(u, name || "");
    else location.href = u;
    return null;
  };
}
"""


# ---------------------------------------------------------------------------------------------- the master folder
def read_master():
    """The master folder of config.json, when it still exists; else None (the first run, or it was moved away)."""
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            m = json.load(fh).get("master")
        return m if m and os.path.isdir(m) else None
    except (OSError, ValueError):
        return None


def save_master(m):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump({"master": m}, fh, ensure_ascii=False, indent=1)


def use_master(m):
    """Its sub-folders made; the modules told where their data is (before they are imported: their paths are set
    when imported). Raises OSError when the folder cannot be written."""
    for s in SUBDIRS.values():
        os.makedirs(os.path.join(m, s), exist_ok=True)
    probe = os.path.join(m, SUBDIRS["app"], ".write_test")
    with open(probe, "w") as fh:
        fh.write("ok")
    os.remove(probe)
    os.environ["SEWER_APP_HOME"] = os.path.join(m, SUBDIRS["sewer"])
    os.environ["WATER_APP_HOME"] = os.path.join(m, SUBDIRS["water"])
    if getattr(sys, "frozen", False) or sys.stdout is None:     # the packed app (or pythonw) has no console: a log
        log = open(os.path.join(m, SUBDIRS["app"], "app.log"), "a", encoding="utf-8", buffering=1)
        log.write(f"\n--- {time.strftime('%d-%m-%Y %H:%M:%S')} ---\n")
        sys.stdout = sys.stderr = log


# ---------------------------------------------------------------------------------------------- the servers
def _version(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=2) as r:
            return json.loads(r.read()).get("version")
    except Exception:
        return None


def start_servers(wait_s=15.0):
    """The launcher's server in a thread (no browser) - the modules' own servers start only when chosen (user decision
    10-Nov-2026); then wait until it answers. Returns the problems: [(name, port, version found)] - a port answered by
    older code or by nothing."""
    from launcher import server as launcher                      # imported here: after use_master
    ports = {"start page": (launcher.PORT, launcher.VERSION)}
    threading.Thread(target=launcher.serve, kwargs={"open_browser": False}, daemon=True).start()
    t0, seen = time.time(), {}
    while time.time() - t0 < wait_s:
        seen = {k: _version(p) for k, (p, _) in ports.items()}
        if all(seen[k] == v for k, (_, v) in ports.items()):
            return []
        time.sleep(0.2)
    return [(k, p, seen.get(k)) for k, (p, v) in ports.items() if seen.get(k) != v]


def problem_page(bad):
    rows = "".join(f"<li>{k}: port {p} - {'पुराना version / दूसरा program' if v else 'जवाब नहीं'}</li>" for k, p, v in bad)
    return ("<html><body style='font:15px sans-serif;margin:32px'><h3>App शुरू नहीं हुआ</h3><ul>" + rows + "</ul>"
            "<p>इन ports पर पहले से कोई server चल रहा है (जैसे sewer_ui.bat की काली window)। उसे बंद करें, फिर app "
            "दोबारा खोलें।</p><p style='color:#666'>A server is already running on these ports (e.g. the black window of "
            "sewer_ui.bat) - close it, then start the app again.</p></body></html>")


# the first run: the master folder chosen in Windows' folder dialog
FIRST_RUN = """<!doctype html><html><head><meta charset="utf-8"><style>
body{font:15px "Segoe UI",sans-serif;margin:0;background:#f5f7fa;color:#222}
.box{max-width:640px;margin:48px auto;background:#fff;border-radius:10px;padding:28px 32px;box-shadow:0 2px 10px #0002}
h2{margin:0 0 6px;color:#0d47a1} .en{color:#666;font-size:13px} code{background:#eef2f7;padding:1px 5px;border-radius:4px}
ul{margin:8px 0 14px} button{font:15px "Segoe UI",sans-serif;padding:8px 16px;border-radius:6px;border:1px solid #1565c0;
background:#fff;color:#1565c0;cursor:pointer;margin-right:8px} button.go{background:#1565c0;color:#fff}
button:disabled{opacity:.45;cursor:default} #path{margin:14px 0;padding:10px;background:#eef2f7;border-radius:6px;
min-height:20px;word-break:break-all} #err{color:#c62828;margin-top:8px}</style></head><body><div class="box">
<h2>Master folder चुनें</h2><div class="en">Choose the master folder</div>
<p>सारा data - projects, DXF, design के नतीजे, DPR - एक ही folder में रहेगा, उसके अंदर ये folders बनेंगे:</p>
<ul><li><code>Sewer\\projects</code>, <code>Sewer\\output</code> - sewer</li>
<li><code>Water\\projects</code>, <code>Water\\output</code> - पेयजल</li>
<li><code>App</code> - app की अपनी settings और log</li></ul>
<div class="en">All data (projects, DXF, results, DPR) stays in one folder, with the sub-folders above. A folder with
these sub-folders from before is used as it is. It can be changed later: menu App.</div>
<div id="path">अभी कोई folder नहीं चुना</div>
<button id="pick">📁 Folder चुनें…</button><button id="go" class="go" disabled>शुरू करें ▶</button>
<div id="err"></div></div><script>
let chosen = null;
const api = () => window.pywebview && window.pywebview.api;
document.getElementById("pick").onclick = async () => {
  const p = await api().choose_master();
  if (!p) return;
  chosen = p; document.getElementById("path").textContent = p; document.getElementById("go").disabled = false;
  document.getElementById("err").textContent = "";
};
document.getElementById("go").onclick = async () => {
  document.getElementById("go").disabled = true; document.getElementById("err").textContent = "शुरू हो रहा है …";
  const r = await api().begin(chosen);
  if (r) { document.getElementById("err").textContent = r; document.getElementById("go").disabled = false; }
};
</script></body></html>"""


class Api:
    """What the pages may ask of the app (window.pywebview.api)."""

    def __init__(self):
        self._windows = {}
        self._main = None                                         # the first window (first run, then the start page)
        self._master = None
        self._last_dir = None                                     # the file dialog opens where the last file was

    def open_window(self, url, name=""):
        """A page's window.open: one window per name (a module: 'sewer_network_design' / 'water_network_design');
        one open already is only brought forward - not loaded again, its work stays (10-Nov-2026)."""
        w = self._windows.get(name)
        if w is not None and w in webview.windows:
            w.restore()
            w.show()
            return
        title = "Water supply network design" if "/water" in url else "Sewer network design" if "/sewer" in url else TITLE
        w = webview.create_window(title, url, js_api=self, min_size=(900, 600), **WINDOW)
        w.events.loaded += lambda: w.evaluate_js(OPEN_JS)
        if name:
            self._windows[name] = w

    def module_opened(self, module):
        """The start page opened a module in the main window: the window's title, and the window known by the module's
        name - the other module's button then brings it forward instead of opening a second one."""
        if self._main is None:
            return
        self._main.set_title("Water supply network design" if module == "water" else "Sewer network design")
        self._windows[f"{module}_network_design"] = self._main

    def pick_file(self, kind="dxf"):
        """Windows' own file dialog (step 2 of the desktop app, user request 30-Oct-2026): the path of the file as it is -
        a DXF is read where it lies, not uploaded first. None when cancelled."""
        types = {"dxf": ("DXF drawing (*.dxf)", "All files (*.*)"),
                 "kml": ("KML / KMZ (*.kml;*.kmz)", "All files (*.*)")}.get(kind, ("All files (*.*)",))
        w = webview.active_window() or webview.windows[0]
        r = w.create_file_dialog(webview.FileDialog.OPEN, directory=self._last_dir or "", file_types=types)
        if not r:
            return None
        self._last_dir = os.path.dirname(r[0])
        return r[0]

    def choose_master(self):
        """Windows' folder dialog for the master folder; None when cancelled."""
        w = webview.active_window() or self._main
        r = w.create_file_dialog(webview.FileDialog.FOLDER, directory=self._master or "")
        return (r[0] if isinstance(r, (list, tuple)) else r) if r else None

    def begin(self, m):
        """The first run: the master folder chosen - kept, its sub-folders made, the servers started, the start page
        in this window. Returns a message when it cannot be (shown on the page)."""
        try:
            use_master(m)
        except OSError as e:
            return f"इस folder में लिखा नहीं जा सकता ({e}) - दूसरा folder चुनें / cannot write to this folder: choose another"
        save_master(m)
        self._master = m
        bad = start_servers()
        if bad:
            self._main.load_html(problem_page(bad))
        else:
            self._main.load_url(START_URL)
        return None

    # the menu "App"
    def open_master(self):
        if self._master:
            os.startfile(self._master)

    def change_master(self):
        """Another master folder: kept for the next start (the servers of this run keep their folder)."""
        m = self.choose_master()
        if not m or m == self._master:
            return
        try:
            for s in SUBDIRS.values():
                os.makedirs(os.path.join(m, s), exist_ok=True)
        except OSError as e:
            (webview.active_window() or self._main).evaluate_js(f"alert({json.dumps(f'Folder नहीं बना: {e}')})")
            return
        save_master(m)
        msg = (f"नया master folder: {m}\n\nApp बंद करके दोबारा खोलें - तब वही folder इस्तेमाल होगा।\n"
               f"New master folder: {m} - close the app and start it again to use it.")
        (webview.active_window() or self._main).evaluate_js(f"alert({json.dumps(msg)})")

    # the menu "App": About, and the updates (user decisions 10-Nov-2026: checked only from the menu, installed in
    # one click - downloaded, its SHA-256 matched against GitHub's, the app closed, the setup run, the app reopened)
    def _one_window(self, key, title, **kw):
        w = self._windows.get(key)
        if w is not None and w in webview.windows:
            w.restore()
            w.show()
            return w
        w = webview.create_window(title, js_api=self, width=680, height=620, min_size=(520, 420), **kw)
        self._windows[key] = w
        return w

    def show_about(self):
        from launcher import about
        self._one_window("about", "About - " + about.APP_NAME, html=about.about_html(self._master, desktop=True))

    def show_update(self):
        self._one_window("update", "Update - " + TITLE, html=UPDATE_PAGE)

    def check_update(self):
        from launcher import about
        r = about.check()
        r["frozen"] = bool(getattr(sys, "frozen", False))      # from source (not the setup): git pull, no install
        return r

    def start_update(self):
        """The newest setup downloaded in a thread (update_progress tells how far), checked against GitHub's SHA-256."""
        from launcher import about
        self._dl = {"done": 0, "size": 0, "path": None, "error": None}

        def run():
            try:
                r = about.check()
                if not r.get("ok") or not r.get("newer"):
                    raise ValueError(r.get("log") or "कोई नया version नहीं / no newer version")
                folder = os.path.join(os.environ.get("TEMP") or os.path.expanduser("~"), "SewerWater_update")
                self._dl["path"] = about.download(r["setup"], folder,
                                                  progress=lambda d, s: self._dl.update(done=d, size=s))
            except Exception as e:
                self._dl["error"] = str(e) or type(e).__name__
        threading.Thread(target=run, daemon=True).start()
        return True

    def update_progress(self):
        return dict(getattr(self, "_dl", None) or {})

    def run_update(self):
        """The checked setup run quietly for this user (it closes the app's files, installs, and starts the app again -
        installer\\SewerWater.iss); this app closes itself at once."""
        import subprocess
        p = (getattr(self, "_dl", None) or {}).get("path")
        if not p or not os.path.isfile(p):
            return "setup नहीं मिला / setup not found"
        subprocess.Popen([p, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/SP-"],
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                         close_fds=True)
        threading.Timer(0.5, lambda: [w.destroy() for w in list(webview.windows)]).start()
        return None


# the update window (menu App -> Check for updates)
UPDATE_PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
body{font:15px "Segoe UI","Nirmala UI",sans-serif;margin:0;background:#f5f7fa;color:#222}
.box{max-width:600px;margin:28px auto;background:#fff;border-radius:10px;padding:22px 28px;box-shadow:0 2px 10px #0002}
h2{margin:0 0 10px;color:#0d47a1} .hint{color:#666;font-size:13px} .ok{color:#2e7d32} .err{color:#c62828}
pre{white-space:pre-wrap;background:#f3f5f8;border-radius:6px;padding:10px;max-height:220px;overflow:auto;font:13px Consolas,monospace}
button{font:15px "Segoe UI",sans-serif;padding:8px 16px;border-radius:6px;border:1px solid #1565c0;background:#1565c0;
color:#fff;cursor:pointer;margin-top:8px} button:disabled{opacity:.45;cursor:default}
progress{width:100%;height:16px;margin-top:10px}</style></head><body><div class="box">
<h2>Update देखें / Check for updates</h2><div id="st">GitHub पर देख रहे हैं … / Checking GitHub …</div>
<div id="more"></div></div><script>
const api = () => window.pywebview.api;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
async function go() {
  const r = await api().check_update();
  if (!r.ok) { $("st").innerHTML = `<span class="err">${esc(r.log)}</span>`; return; }
  if (!r.newer) {
    $("st").innerHTML = `<span class="ok">✔ नया version यही है: ${esc(r.current)} / You have the newest version: ${esc(r.current)}</span>`;
    return;
  }
  const mb = r.setup ? (r.setup.size / 1048576).toFixed(1) + " MB" : "";
  $("st").innerHTML = `नया version <b>${esc(r.latest)}</b> उपलब्ध है (अभी ${esc(r.current)}) / Version <b>${esc(r.latest)}</b> is available (you have ${esc(r.current)})`;
  let h = `<pre>${esc(r.notes || "")}</pre>`;
  if (!r.frozen) h += `<div class="hint">App source से चल रहा है - update: git pull / The app runs from source: update with git pull.</div>`;
  else if (!r.setup) h += `<div class="err">इस release में setup नहीं / this release has no setup</div>`;
  else h += `<div class="hint">App बंद होकर setup चलेगा और नया version अपने-आप खुलेगा - पहले सब काम सहेज लें। ${esc(r.setup.name)}, ${mb}; SHA-256 GitHub से मिलाया जाएगा.<br>
The app closes, the setup runs and the new version opens by itself - save your work first.</div>
<button id="inst">Download और install / Download and install</button><progress id="pg" value="0" max="1" hidden></progress><div id="msg"></div>`;
  $("more").innerHTML = h;
  if ($("inst")) $("inst").onclick = install;
}
async function install() {
  if (!confirm("सब काम सहेज लिया? App बंद होकर update होगा। / Is all your work saved? The app will close and update.")) return;
  $("inst").disabled = true; $("pg").hidden = false; $("msg").textContent = "Download हो रहा है … / Downloading …";
  await api().start_update();
  const t = setInterval(async () => {
    const p = await api().update_progress();
    if (p.size) $("pg").value = p.done / p.size;
    if (p.error) { clearInterval(t); $("msg").innerHTML = `<span class="err">${esc(p.error)}</span>`; $("inst").disabled = false; return; }
    if (p.path) {
      clearInterval(t);
      $("msg").innerHTML = `<span class="ok">✔ SHA-256 मिला - setup चल रहा है, app बंद हो रहा है … / SHA-256 matched - the setup runs, the app closes …</span>`;
      const e = await api().run_update();
      if (e) { $("msg").innerHTML = `<span class="err">${esc(e)}</span>`; $("inst").disabled = false; }
    }
  }, 400);
}
let began = false;
const begin = () => { if (!began) { began = true; go(); } };
window.addEventListener("pywebviewready", begin);
if (window.pywebview && window.pywebview.api) begin();
</script></body></html>"""


def main():
    webview.settings["ALLOW_DOWNLOADS"] = True                   # the pages' CSV / KML / DXF downloads
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True    # manuals, maps outside the app
    if os.environ.get("APP_DEBUG_PORT"):                         # checks from outside: the pages over CDP
        webview.settings["REMOTE_DEBUGGING_PORT"] = int(os.environ["APP_DEBUG_PORT"])
    api = Api()
    m = read_master()
    storage = None
    if m is not None:
        try:
            use_master(m)
        except OSError:
            m = None                                             # not writable any more: chosen again
    if m is None:                                                # the first run: the master folder first
        api._main = webview.create_window(TITLE + " - master folder", html=FIRST_RUN, js_api=api, width=760,
                                         height=600, min_size=(600, 480), **dict(WINDOW, maximized=False))
    else:
        api._master, storage = m, os.path.join(m, SUBDIRS["app"], "webview")
        bad = start_servers()
        if bad:
            api._main = webview.create_window(TITLE, html=problem_page(bad), width=640, height=360)
        else:
            api._main = webview.create_window(TITLE, START_URL, js_api=api, min_size=(900, 600), **WINDOW)
    api._main.events.loaded += lambda: api._main.evaluate_js(OPEN_JS)
    menu = [Menu("App", [MenuAction("Master folder खोलें / Open the master folder", api.open_master),
                         MenuAction("Master folder बदलें… / Change the master folder…", api.change_master),
                         MenuAction("Update देखें… / Check for updates…", api.show_update),
                         MenuAction("About", api.show_about)])]
    webview.start(private_mode=False, storage_path=storage, menu=menu)   # localStorage kept (in <master>\App)
    sys.exit(0)                                                # every window closed: the servers end with the app


if __name__ == "__main__":
    main()
