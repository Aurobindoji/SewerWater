"""The map UI as a desktop app (user request 30-Oct-2026): the start page (the launcher's: language, then sewer or
water) in a window of its own (pywebview: Edge WebView2 on Windows) - no browser, no address bar, no tabs. Only the
module chosen is started, in that same window (user decision 10-Nov-2026: the two apps fully independent); the other
starts only from its button in a module's page, in a second window. A window's close button (or Alt+F4) only
hides it - the app stays in the tray, its servers and the pages' work kept (user request 15-Nov-2026); the app ends
(and its servers) from the tray menu or the menu "App": Quit.

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

TITLE = "PravaahForge"                           # the app's name (user request 16-Nov-2026; was "Sewer & Water network design")
APP_ID = "Aurobindoji.SewerWater"                 # the app's name for the taskbar (the setup's shortcuts carry it too)
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


# ---------------------------------------------------------------------------------------------- the icon, the tray
def icon_path():
    """The app icon file (all its sizes): packed beside the program, or installer\\SewerWater.ico of the source."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(base, "SewerWater.ico"), os.path.join(base, "installer", "SewerWater.ico")):
        if os.path.isfile(p):
            return p
    return None


def own_taskbar_name():
    """The app's own identity on the taskbar (user 14-Nov-2026: the taskbar still showed the icon of before): its
    button takes the windows' icon, not one Windows kept for the program's path from an older version."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


# ---- the menus in one language and the pages' theme (user request 16-Nov-2026: Hindi or English, not both; dark when
# the pages are). The language is the one chosen last (the start page / a module page, launcher /api/ui); the menus
# take it, and the theme, each time they open.
MENU_TXT = {
    "hi": {"show": "खोलें", "open_master": "Master folder खोलें", "change_master": "Master folder बदलें…",
           "update": "Update देखें…", "about": "परिचय (About)", "quit": "बंद करें",
           "note": "App background में चल रहा है"},          # user 17-Nov-2026: only this
    "en": {"show": "Show", "open_master": "Open the master folder", "change_master": "Change the master folder…",
           "update": "Check for updates…", "about": "About", "quit": "Quit",
           "note": "The app is running in the background"},
}
APP_MENU = ("open_master", "change_master", "update", "about", "quit")     # the items of the menu "App", in order


def menu_look():
    """(lang, dark) of the pages now."""
    try:
        from launcher import about
        return about.look()
    except Exception:
        return "hi", False


class MenuLook:
    """Dark / light colours of a ToolStrip (menu bar, drop-down, the tray's menu) through its renderer's events - a
    renderer of pythonnet's own class does not load here. One per app; its handlers kept with it."""
    BG, HI, FG, LINE = (43, 45, 49), (70, 76, 86), (230, 232, 235), (70, 74, 80)

    def __init__(self):
        import System.Windows.Forms as WF
        from System.Drawing import Color, Pen, Point, Rectangle, SolidBrush
        c = lambda t: Color.FromArgb(*t)                     # noqa: E731
        bg, hi, fg, line = c(self.BG), c(self.HI), c(self.FG), c(self.LINE)
        self.light = WF.ToolStripProfessionalRenderer()
        r = self.dark = WF.ToolStripProfessionalRenderer()

        def back(s, e):
            e.Graphics.FillRectangle(SolidBrush(bg), e.AffectedBounds)

        def item(s, e):
            sel = (e.Item.Selected or e.Item.Pressed) and e.Item.Enabled
            e.Graphics.FillRectangle(SolidBrush(hi if sel else bg), Rectangle(Point(0, 0), e.Item.Size))

        def text(s, e):
            e.TextColor = fg

        def sep(s, e):
            y = e.Item.Height // 2
            e.Graphics.FillRectangle(SolidBrush(bg), Rectangle(Point(0, 0), e.Item.Size))
            e.Graphics.DrawLine(Pen(line), 4, y, e.Item.Width - 4, y)

        def border(s, e):
            if isinstance(e.ToolStrip, WF.ToolStripDropDown):
                e.Graphics.DrawRectangle(Pen(line), Rectangle(0, 0, e.ToolStrip.Width - 1, e.ToolStrip.Height - 1))

        def arrow(s, e):
            e.ArrowColor = fg
        self._keep = (back, item, text, sep, border, arrow)
        r.RenderToolStripBackground += back
        r.RenderImageMargin += back
        r.RenderMenuItemBackground += item
        r.RenderItemText += text
        r.RenderSeparator += sep
        r.RenderToolStripBorder += border
        r.RenderArrow += arrow

    def apply(self, strip, dark):
        """The colours on a strip and on each of its items - the text's own colour too (user 16-Nov-2026: the text
        looked dim; the renderer's TextColor event comes only after the text is drawn)."""
        from System.Drawing import Color
        rend = self.dark if dark else self.light
        if strip.Renderer is not rend:
            strip.Renderer = rend
        for it in list(strip.Items):
            if dark:
                it.ForeColor = Color.White
            else:
                it.ResetForeColor()


_LOOK = []


def menu_renderers():
    """The one MenuLook (made on the windows' thread when first needed)."""
    if not _LOOK:
        _LOOK.append(MenuLook())
    return _LOOK[0]


_TITLE_DARK = {}                                              # hwnd -> the title bar's last look


def title_bar(form, dark):
    """The window's title bar dark with the pages' theme (Windows 10 2004+ / 11: DWMWA_USE_IMMERSIVE_DARK_MODE, 20;
    older builds 19). Redrawn at once when it changes. Windows without it keep their own (light) bar."""
    try:
        import ctypes
        hwnd = int(form.Handle.ToInt64())
        if _TITLE_DARK.get(hwnd) == bool(dark):
            return
        v = ctypes.c_int(1 if dark else 0)
        dwm = ctypes.windll.dwmapi
        if any(dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), a, ctypes.byref(v), ctypes.sizeof(v)) == 0
               for a in (20, 19)):
            _TITLE_DARK[hwnd] = bool(dark)
            # SWP_FRAMECHANGED | NOMOVE | NOSIZE | NOZORDER | NOACTIVATE: the frame drawn again now
            ctypes.windll.user32.SetWindowPos(ctypes.c_void_p(hwnd), None, 0, 0, 0, 0, 0x20 | 0x2 | 0x1 | 0x4 | 0x10)
    except Exception:
        pass


def style_window_menu(window):
    """The menu "App" of a window (pywebview's MenuStrip): its labels in the language now and its colours in the theme
    now - set when the window is shown, again whenever it is activated or the menu opened."""
    if os.name != "nt":
        return
    try:
        from System import Action
        import System.Windows.Forms as WF

        def find():
            form = window.native
            strip = next((c for c in form.Controls if isinstance(c, WF.MenuStrip)), None)
            top = strip.Items[0] if strip is not None and strip.Items.Count else None

            def restyle(*_):
                lang, dark = menu_look()
                title_bar(form, dark)
                if top is None:
                    return
                t, look = MENU_TXT[lang], menu_renderers()
                for k, it in zip(APP_MENU, list(top.DropDownItems)):
                    it.Text = t[k]
                look.apply(strip, dark)
                look.apply(top.DropDown, dark)
            restyle()
            keep = [restyle]
            if top is not None:
                strip.MenuActivate += restyle
                top.DropDownOpening += restyle
                # a click outside the open menu closes it (user 23-Nov-2026: a click on the page left it open - the
                # page's WebView2 is a window of another process, whose clicks the menu never sees): while it is
                # open, a mouse button down anywhere but on the menu or its bar closes it
                timer = WF.Timer()
                timer.Interval = 60
                no_button = getattr(WF.MouseButtons, "None")         # "None": a word of Python's

                def tick(*_):
                    dd = top.DropDown
                    if not dd.Visible:
                        timer.Stop()
                        return
                    if WF.Control.MouseButtons == no_button:
                        return
                    at = WF.Cursor.Position
                    if not dd.Bounds.Contains(at) and not strip.RectangleToScreen(strip.ClientRectangle).Contains(at):
                        top.HideDropDown()
                        timer.Stop()

                def opened(*_):
                    timer.Start()

                def closed(*_):
                    timer.Stop()
                timer.Tick += tick
                top.DropDownOpened += opened
                top.DropDownClosed += closed
                keep += [timer, tick, opened, closed]
            form.Activated += restyle
            window._menu_restyle = restyle                    # kept with the window
            window._menu_keep = keep                          # the handlers and the timer: not collected
        window.native.Invoke(Action(find))
    except Exception as e:                                    # the menu as pywebview made it
        print(f"menu look not set: {type(e).__name__}: {e}")


class Tray:
    """The app's icon in the notification area (user request 14-Nov-2026) while the app runs: a double click brings
    its windows forward; the menu: show, the master folder, updates, About, quit. Made with Windows Forms' own
    NotifyIcon (the library of the app's windows - nothing more to install), on the windows' thread.

    A kept window (the start page / a module's) closed by the user is only hidden (user request 15-Nov-2026) - not when
    Windows shuts down or the user logs off (the app would hold that up), nor when the app quits. Without the tray
    icon the windows close as before (else a hidden app could not be reached)."""

    def __init__(self, api, icon):
        self.api, self.icon, self.ni = api, icon, None
        self.quitting = False
        self._told = False                                   # the "still running" notice: once a run

    def attach(self, window):
        """Called when the first window is shown."""
        if self.ni is not None or not self.icon or os.name != "nt":
            return
        try:
            from System import Action
            window.native.Invoke(Action(self._make))
        except Exception as e:                               # no tray icon: the app works without it
            print(f"tray icon not made: {type(e).__name__}: {e}")

    def keep(self, window):
        """The window hidden when the user closes it (called when it is shown: it has its form then)."""
        if os.name != "nt":
            return
        try:
            from System import Action

            def add():
                window.native.FormClosing += self._on_closing
            window.native.Invoke(Action(add))
        except Exception as e:
            print(f"close-to-tray not set: {type(e).__name__}: {e}")

    def _on_closing(self, sender, args):
        # after pywebview's own handler (added first); on the windows' thread
        import System.Windows.Forms as WF
        if self.ni is None or self.quitting or args.Cancel or args.CloseReason != WF.CloseReason.UserClosing:
            return
        args.Cancel = True
        sender.Hide()
        if not self._told:
            self._told = True
            self.ni.ShowBalloonTip(4000, TITLE, MENU_TXT[menu_look()[0]]["note"], WF.ToolTipIcon.Info)

    def _make(self):
        import System.Windows.Forms as WF
        from System.Drawing import Icon
        ni = WF.NotifyIcon()
        ni.Icon = Icon(self.icon)
        ni.Text = TITLE
        menu = WF.ContextMenuStrip()
        items = []
        for key, fn in (("show", self.show), ("open_master", self.api.open_master), ("update", self.api.show_update),
                        ("about", self.api.show_about), (None, None), ("quit", self.quit)):
            if key is None:
                menu.Items.Add(WF.ToolStripSeparator())
                continue
            item = menu.Items.Add(key)
            item.Click += self._handler(fn)
            items.append((key, item))

        def restyle(*_):                                     # the language and theme now, each time it opens
            lang, dark = menu_look()
            for k, it in items:
                it.Text = MENU_TXT[lang][k]
            menu_renderers().apply(menu, dark)
        restyle()
        menu.Opening += restyle
        self._restyle = restyle                              # kept while the app runs
        ni.ContextMenuStrip = menu
        ni.DoubleClick += self._handler(self.show)
        ni.Visible = True
        self.ni, self._menu = ni, menu                       # kept: not collected while the app runs
        print("tray icon on")

    @staticmethod
    def _handler(fn):
        # off the windows' thread: the windows are asked from another thread, as the menu "App" does
        return lambda sender, e: threading.Thread(target=fn, daemon=True).start()

    @staticmethod
    def show():
        for w in list(webview.windows):
            try:
                w.restore()
                w.show()
            except Exception:
                pass

    def quit(self):
        self.quitting = True                                 # the windows then really close
        for w in list(webview.windows):
            w.destroy()

    def close(self):
        """The icon taken away with the app (else it stays until the mouse passes over it)."""
        if self.ni is not None:
            try:
                self.ni.Visible = False
                self.ni.Dispose()
            except Exception:
                pass
            self.ni = None


# ---------------------------------------------------------------------------------------------- the servers
def _version(port, timeout=2):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=timeout) as r:
            return json.loads(r.read()).get("version")
    except Exception:
        return None


_INSTANCE = []                                    # the app's named mutex, held while it runs


def another_app_running():
    """True when another copy of the app runs - its named mutex is there. Instant (user 16-Nov-2026: asking the
    launcher's port when nothing listens took Windows 2 s at every start). The mutex is made here and held."""
    if os.name != "nt":
        return True                                  # elsewhere: ask the port (show_running_app)
    try:
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        h = k32.CreateMutexW(None, False, "Local\\Aurobindoji.SewerWater.app")
        running = ctypes.get_last_error() == 183     # ERROR_ALREADY_EXISTS
        _INSTANCE.append(h)
        return running
    except Exception:
        return True


def show_running_app():
    """The app already running (user 16-Nov-2026: started again while hidden in the tray, two icons): asked to bring
    its windows forward - True when it did, and this second start then ends. An app of before 0.9.22 has no such call:
    False, the start goes on as before. Asked only when another copy runs (another_app_running): no wait otherwise."""
    if not another_app_running():
        return False
    try:
        with urllib.request.urlopen(START_URL + "api/app_show", timeout=2) as r:
            return bool(json.loads(r.read().decode("utf-8")).get("shown"))
    except Exception:
        return False


def start_servers(wait_s=15.0):
    """The launcher's server in a thread (no browser) - the modules' own servers start only when chosen (user decision
    10-Nov-2026); then wait until it answers. Returns the problems: [(name, port, version found)] - a port answered by
    older code or by nothing."""
    from launcher import server as launcher                      # imported here: after use_master
    ports = {"start page": (launcher.PORT, launcher.VERSION)}
    threading.Thread(target=launcher.serve, kwargs={"open_browser": False}, daemon=True).start()
    t0, seen = time.time(), {}
    while time.time() - t0 < wait_s:
        seen = {k: _version(p, timeout=0.5) for k, (p, _) in ports.items()}   # short: not Windows' 2 s
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
        self._tray = None                                         # its quit closes the hidden windows too

    def restyle(self):
        """A page changed the theme: every window's title bar and menu in it now (on the windows' thread)."""
        if os.name != "nt":
            return
        from System import Action
        for w in list(webview.windows):
            fn = getattr(w, "_menu_restyle", None)
            if fn is not None:
                try:
                    w.native.BeginInvoke(Action(fn))
                except Exception:
                    pass

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
        w.events.shown += lambda: style_window_menu(w)
        if self._tray is not None:
            w.events.shown += lambda: self._tray.keep(w)
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
            if kw.get("html"):                                # its page again: the language / theme now
                w.load_html(kw["html"])
                w.set_title(title)
            w.restore()
            w.show()
            return w
        w = webview.create_window(title, js_api=self, width=680, height=620, min_size=(520, 420), **kw)
        w.events.shown += lambda: style_window_menu(w)
        self._windows[key] = w
        return w

    def show_about(self):
        from launcher import about
        self._one_window("about", "About - " + about.APP_NAME, html=about.about_html(self._master, desktop=True))

    def show_update(self):
        from launcher import about
        lang = about.look()[0]
        self._one_window("update", about.UPDATE_TXT[lang]["title"] + " - " + TITLE, html=about.update_html())

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
                    raise ValueError(r.get("log") or about.msg("no_newer"))
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
            from launcher import about
            return about.msg("no_file")
        subprocess.Popen([p, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/SP-"],
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                         close_fds=True)
        threading.Timer(0.5, self.quit).start()
        return None

    def quit(self):
        """The app ended: every window closed (hidden ones too), the servers with it."""
        if self._tray is not None:
            self._tray.quit()
        else:
            for w in list(webview.windows):
                w.destroy()


def main():
    webview.settings["ALLOW_DOWNLOADS"] = True                   # the pages' CSV / KML / DXF downloads
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True    # manuals, maps outside the app
    if os.environ.get("APP_DEBUG_PORT"):                         # checks from outside: the pages over CDP
        webview.settings["REMOTE_DEBUGGING_PORT"] = int(os.environ["APP_DEBUG_PORT"])
    own_taskbar_name()
    if show_running_app():                                     # the app runs already (perhaps hidden in the tray)
        sys.exit(0)
    api = Api()
    icon = icon_path()
    tray = Tray(api, icon)
    api._tray = tray
    m = read_master()
    storage, bad = None, []
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
        if not bad:                                          # a second start of the app shows this one's windows
            from launcher import server as launcher
            launcher.APP_HOOKS["show"] = Tray.show
        if bad:
            api._main = webview.create_window(TITLE, html=problem_page(bad), width=640, height=360)
        else:
            api._main = webview.create_window(TITLE, START_URL, js_api=api, min_size=(900, 600), **WINDOW)
    api._main.events.loaded += lambda: api._main.evaluate_js(OPEN_JS)
    api._main.events.shown += lambda: tray.attach(api._main)
    if not bad:                                                  # the problem page closes: nothing runs to keep
        api._main.events.shown += lambda: tray.keep(api._main)
    api._main.events.shown += lambda: style_window_menu(api._main)
    t = MENU_TXT[menu_look()[0]]                               # relabelled when opened (style_window_menu)
    fns = {"open_master": api.open_master, "change_master": api.change_master, "update": api.show_update,
           "about": api.show_about, "quit": api.quit}
    menu = [Menu("App", [MenuAction(t[k], fns[k]) for k in APP_MENU])]
    try:                                                       # localStorage kept (in <master>\App); the windows'
        webview.start(private_mode=False, storage_path=storage, menu=menu, icon=icon)   # icon: the file, every size
    finally:
        tray.close()
    sys.exit(0)                                                # every window closed: the servers end with the app


if __name__ == "__main__":
    main()
