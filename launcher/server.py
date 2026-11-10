"""The start page and the starting of the modules (user decision 10-Nov-2026: one icon, choose at the start; the
module chosen alone is started; the other only from its button in a module's page).

    GET /                      the start page (language, then sewer / water)
    GET /api/open?module=...   starts that module's server (once) and answers {ok, url} when it answers with its own
                               version; {ok: false, log} when its port is held by older code or another program
    GET /api/version           this server's version (the desktop app's check)

Each module is imported only when it is first opened, so starting one never loads the other. Local use only; the
module pages (ports 8765 / 8766) may call /api/open (CORS), for their button of the other module.

    python -m launcher [--no-browser]      (start_ui.py, sewer_ui.bat; the desktop app runs it in a thread)
"""
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8764
HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
# module -> (its port, its page)
MODULES = {"sewer": (8765, "/sewer"), "water": (8766, "/water")}
ORIGINS = {f"http://{h}:{p}" for h in ("127.0.0.1", "localhost") for p in (PORT, 8765, 8766)}
_LOCK = threading.Lock()
_STARTED = {}                                   # module -> the version its server must answer with


def _code_version():
    h = hashlib.sha1()
    for d in (HERE, STATIC):
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if os.path.isfile(p) and f.endswith((".py", ".html")):
                with open(p, "rb") as fh:
                    h.update(fh.read())
    return h.hexdigest()[:12]


VERSION = _code_version()


def _version(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=2) as r:
            return json.loads(r.read()).get("version")
    except Exception:
        return None


def _start(name):
    """The module's server in a thread (imported here, only now); returns the version it must answer with."""
    if name == "sewer":
        from sewer_app import ui as mod
    else:
        from water_app import server as mod
    threading.Thread(target=mod.serve, kwargs={"open_browser": False}, daemon=True).start()
    return mod.VERSION


def open_module(name, wait_s=20.0):
    """Start the module once and wait until its port answers with its version -> (ok, url or the problem)."""
    port, page = MODULES[name]
    with _LOCK:
        if name not in _STARTED:
            _STARTED[name] = _start(name)
        want = _STARTED[name]
    t0, seen = time.time(), None
    while time.time() - t0 < wait_s:
        seen = _version(port)
        if seen == want:
            return True, f"http://127.0.0.1:{port}{page}"
        time.sleep(0.2)
    return False, (f"port {port}: " + ("पुराना version / दूसरा program - उसकी window बंद करके app फिर खोलें; an older "
                                       "version or another program holds it - close it and start the app again"
                                       if seen else "जवाब नहीं / no answer"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin") or ""
        if origin in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return self._send(403, {"ok": False, "log": "local use only"})
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            with open(os.path.join(STATIC, "start.html"), "rb") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")
        if u.path == "/about":                           # the About page (10-Nov-2026)
            from . import about
            return self._send(200, about.about_html().encode("utf-8"), "text/html; charset=utf-8")
        if u.path == "/api/version":
            from . import about
            return self._send(200, {"ok": True, "version": VERSION, "app_version": about.APP_VERSION, "pid": os.getpid()})
        if u.path == "/api/open":
            name = (parse_qs(u.query).get("module") or [""])[0]
            if name not in MODULES:
                return self._send(400, {"ok": False, "log": "module: sewer / water"})
            try:
                ok, r = open_module(name)
            except Exception as e:
                ok, r = False, f"{type(e).__name__}: {e}"
            return self._send(200, {"ok": True, "url": r} if ok else {"ok": False, "log": r})
        return self._send(404, {"ok": False})


class Server(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"       # as the modules' servers: a second start finds the port busy


def serve(port=PORT, open_browser=True):
    url = f"http://127.0.0.1:{port}/"
    try:
        srv = Server(("127.0.0.1", port), Handler)
    except OSError:
        print(f"Start page पहले से चल रहा है / already running: {url}")
        if open_browser:
            webbrowser.open(url)
        return None
    print(f"Start page: {url}   (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return srv


def main(argv):
    serve(open_browser="--no-browser" not in argv)


if __name__ == "__main__":
    main(sys.argv[1:])
