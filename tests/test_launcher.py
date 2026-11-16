"""The launcher (user decision 10-Nov-2026): one start page; only the module chosen starts, the other only when its
button asks; loading the launcher loads neither module."""
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

from launcher import server as L


@pytest.fixture()
def launcher():
    srv = L.Server(("127.0.0.1", 0), L.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def get(url, origin=None):
    req = urllib.request.Request(url, headers={"Origin": origin} if origin else {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8"), dict(r.headers)


def test_loading_the_launcher_loads_no_module():
    code = ("import sys, launcher.server; "
            "print(sorted(k for k in sys.modules if k.split('.')[0] in ('sewer_app', 'water_app')))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]"


def test_start_page_and_open(launcher, monkeypatch):
    page, _ = get(launcher + "/")
    assert "Choose language" in page and "/api/open?module=" in page
    assert '<h1 class="brand">PravaahForge</h1>' in page                # the app's name the title (16-Nov-2026)
    with pytest.raises(urllib.error.HTTPError) as e:
        get(launcher + "/api/open?module=other")
    assert e.value.code == 400
    started = []                                         # the module's server: only the one asked for, once
    monkeypatch.setattr(L, "_STARTED", {})
    monkeypatch.setattr(L, "_start", lambda name: started.append(name) or f"v-{name}")
    monkeypatch.setattr(L, "_version", lambda port: {8765: "v-sewer", 8766: "v-water"}[port])
    body, head = get(launcher + "/api/open?module=water", origin="http://127.0.0.1:8765")
    assert json.loads(body) == {"ok": True, "url": "http://127.0.0.1:8766/water"}
    assert head.get("Access-Control-Allow-Origin") == "http://127.0.0.1:8765"      # the sewer page's button
    get(launcher + "/api/open?module=water")
    assert started == ["water"]
    _, head = get(launcher + "/api/version", origin="http://example.com")
    assert "Access-Control-Allow-Origin" not in head


def test_a_port_held_by_older_code(monkeypatch):
    monkeypatch.setattr(L, "_STARTED", {})
    monkeypatch.setattr(L, "_start", lambda name: "new")
    monkeypatch.setattr(L, "_version", lambda port: "old")
    ok, why = L.open_module("sewer", wait_s=0.5)
    assert not ok and "8765" in why


def test_the_pages_look_is_shared(launcher, monkeypatch, tmp_path):
    """Theme, mode and language (user request 16-Nov-2026): kept by the launcher for every page; unknown values
    ignored."""
    monkeypatch.setattr(L, "UI_FILE", str(tmp_path / "ui.json"))
    body, _ = get(launcher + "/api/ui")
    assert json.loads(body) == {"ok": True, "mode": "advanced", "theme": "system", "lang": "hi"}
    body, head = get(launcher + "/api/ui?theme=dark&mode=simple", origin="http://127.0.0.1:8766")
    assert json.loads(body)["theme"] == "dark" and head.get("Access-Control-Allow-Origin") == "http://127.0.0.1:8766"
    get(launcher + "/api/ui?theme=purple&mode=x&lang=fr")
    get(launcher + "/api/ui?lang=en")
    body, _ = get(launcher + "/api/ui")
    assert json.loads(body) == {"ok": True, "mode": "simple", "theme": "dark", "lang": "en"}
    assert json.load(open(tmp_path / "ui.json")) == {"mode": "simple", "theme": "dark", "lang": "en"}
    # About in that one language and theme (the desktop app's About too); ?lang= for the browser's
    from launcher import about
    page = about.about_html()
    assert 'data-theme="dark"' in page and "Credits" in page and "श्रेय" not in page
    body, _ = get(launcher + "/about?lang=hi")
    assert "श्रेय" in body and "Credits" not in body
