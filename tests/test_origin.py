"""The servers answer this computer's own pages only: a POST carrying the Origin of another site (a web page open
in the same browser, posting to 127.0.0.1 unseen) is refused; the app's pages (any local port) and programs, which
send no Origin, are served as before."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from sewer_app import ui
from water_app import server as wserver


@pytest.fixture(params=["sewer", "water"])
def base(request, tmp_path, monkeypatch):
    mod = ui if request.param == "sewer" else wserver
    monkeypatch.setattr(mod, "PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setattr(mod, "OUT_ROOT", str(tmp_path / "output"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path / "projects"
    srv.shutdown()
    srv.server_close()


def post(url, body, origin=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "text/plain", **({"Origin": origin} if origin else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.mark.parametrize("origin", ["https://example.com", "http://127.0.0.1.example.com:8765", "null"])
def test_post_of_another_site_is_refused(base, origin):
    url, projects = base
    code, res = post(url + "/api/save", {"name": "x", "kml": "<kml/>"}, origin)
    assert code == 403 and res["ok"] is False
    assert not (projects / "x.kml").exists()
    code, res = post(url + "/api/barriers_save", {"name": "x", "barriers": [1]}, origin)
    assert code == 403 and not (projects / "x.barriers.json").exists()


@pytest.mark.parametrize("origin", [None, "http://127.0.0.1:8765", "http://localhost:8766", "http://127.0.0.1:8764"])
def test_own_pages_and_programs_are_served(base, origin):
    url, projects = base
    code, res = post(url + "/api/save", {"name": "x", "kml": "<kml/>"}, origin)
    assert code == 200 and res["ok"] and (projects / "x.kml").exists()
    code, res = post(url + "/api/barriers_save", {"name": "x", "barriers": [1]}, origin)
    assert code == 200 and json.loads((projects / "x.barriers.json").read_text(encoding="utf-8")) == [1]
    with urllib.request.urlopen(url + "/api/barriers?name=x", timeout=30) as r:
        assert json.loads(r.read()) == {"ok": True, "barriers": [1]}


def test_unknown_call(base):
    url, _ = base
    assert post(url + "/api/nothing_save", {})[0] == 404
    assert post(url + "/api/nothing", {})[0] == 404
