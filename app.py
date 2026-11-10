"""The map UI as a desktop app (user request 30-Oct-2026): both servers as start_ui.py starts them, the start page in a
window of its own (pywebview: Edge WebView2 on Windows) - no browser, no address bar, no tabs. Choosing water opens the
water page in a second window, as the browser opened it in a tab of its own. Closing every window ends the app (and
its servers).

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
START_URL = "http://127.0.0.1:8765/"
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
    """Both servers in threads (as start_ui.py, no browser); then wait until each answers. Returns the problems:
    [(module, port, version found)] - a port answered by older code or by nothing."""
    from sewer_app import ui as sewer_ui                         # imported here: after use_master
    from water_app import server as water_server
    ports = {"sewer": (8765, sewer_ui.VERSION), "water": (water_server.PORT, water_server.VERSION)}
    threading.Thread(target=water_server.serve, kwargs={"open_browser": False}, daemon=True).start()
    threading.Thread(target=sewer_ui.serve, kwargs={"open_browser": False}, daemon=True).start()
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
        """A page's window.open: one window per name (the water page: 'water_network_design'), loaded again if open."""
        w = self._windows.get(name)
        if w is not None and w in webview.windows:
            w.load_url(url)
            w.restore()
            return
        title = "Water network design" if "/water" in url else TITLE
        w = webview.create_window(title, url, js_api=self, min_size=(900, 600), **WINDOW)
        w.events.loaded += lambda: w.evaluate_js(OPEN_JS)
        if name:
            self._windows[name] = w

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
                         MenuAction("Master folder बदलें… / Change the master folder…", api.change_master)])]
    webview.start(private_mode=False, storage_path=storage, menu=menu)   # localStorage kept (in <master>\App)
    sys.exit(0)                                                # every window closed: the servers end with the app


if __name__ == "__main__":
    main()
