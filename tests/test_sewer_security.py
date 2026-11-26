"""The sewer server's guards (rewrite stage 2, 26-Nov-2026), as the water server's: only this run's own page makes it
do anything (its token), only drawings are read on the page's word, only output files are opened, the map libraries
come with the app, and files are written whole or not at all."""
import json
import os
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from sewer_app.data import project as sproject
from sewer_app.core import store
from sewer_app.web import server as ui


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setattr(sproject, "PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setattr(sproject, "OUT_ROOT", str(tmp_path / "output"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path
    srv.shutdown()
    srv.server_close()


def post(url, body, token):
    h = {"Content-Type": "application/json"}
    if token is not None:
        h[ui.TOKEN_HEADER] = token
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.mark.parametrize("token", [None, "", "wrong", ui.TOKEN[:-1]])
def test_a_post_without_the_runs_token_is_refused(base, token):
    url, tmp = base
    code, res = post(url + "/api/save", {"name": "x", "kml": "<kml/>"}, token)
    assert code == 403 and res["ok"] is False and res.get("token")
    assert not (tmp / "projects" / "x.kml").exists()
    code, _ = post(url + "/api/loops_save", {"name": "x", "loops": [1]}, token)
    assert code == 403 and not (tmp / "projects" / "x.loops.json").exists()


def test_the_page_carries_the_token_and_with_it_a_post_is_served(base):
    url, tmp = base
    with urllib.request.urlopen(url + "/sewer", timeout=30) as r:
        page = r.read().decode("utf-8")
    assert f'content="{ui.TOKEN}"' in page and "__APP_TOKEN__" not in page
    code, res = post(url + "/api/save", {"name": "x", "kml": "<kml/>"}, ui.TOKEN)
    assert code == 200 and res["ok"] and (tmp / "projects" / "x.kml").read_text(encoding="utf-8") == "<kml/>"


def test_the_map_libraries_come_with_the_app(base):
    url, _ = base
    with urllib.request.urlopen(url + "/sewer", timeout=30) as r:
        page = r.read().decode("utf-8")
    assert "unpkg.com" not in page and "://" not in "".join(re.findall(r'<(?:script|link)[^>]+>', page))
    for src in re.findall(r'(?:src|href)="(vendor/[^"]+)"', page) + ["vendor/leaflet/images/marker-icon.png",
                                                                       "vendor/leaflet-draw/images/spritesheet.svg"]:
        with urllib.request.urlopen(url + "/" + src, timeout=30) as r:
            assert r.status == 200 and len(r.read()) > 500, src


def test_only_a_dxf_is_read_on_the_pages_word(base):
    url, tmp = base
    other = tmp / "secret.txt"
    other.write_text("not a drawing", encoding="utf-8")
    code, res = post(url + "/api/dxf_layers", {"path": str(other)}, ui.TOKEN)
    assert code == 200 and res["ok"] is False and ".dxf" in res["log"]


def test_only_output_files_are_opened(tmp_path, monkeypatch):
    monkeypatch.setattr(sproject, "OUT_ROOT", str(tmp_path))
    opened = []
    monkeypatch.setattr(os, "startfile", lambda p, *a: opened.append(p), raising=False)
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "run.bat").write_text("echo", encoding="utf-8")
    (tmp_path / "p" / "p_design.xlsx").write_bytes(b"x")
    with pytest.raises(ValueError):
        sproject.open_output("p", "run.bat")
    with pytest.raises(ValueError):
        sproject.open_output("p", "../p/../../x.xlsx")
    assert not opened
    assert sproject.open_output("p", "p_design.xlsx")["ok"] and len(opened) == 1


def test_kept_data_reads_back_as_it_was_written(tmp_path):
    data = {"sizes": {200: 3}, "pair": (1, 2.5), "__map__": [1], "nested": {"__tuple__": "a real key"}, "t": "सीवर"}
    p = tmp_path / "d" / "k.json"
    store.write_json(str(p), data, typed=True)
    back = store.read_json(str(p), typed=True)
    assert back == data and type(back["pair"]) is tuple and 200 in back["sizes"]


def test_a_failed_write_leaves_the_old_file_and_no_part(tmp_path):
    p = tmp_path / "k.json"
    store.write_json(str(p), {"a": 1})
    with pytest.raises(TypeError):
        store.write_json(str(p), {"a": object()})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    assert [f.name for f in tmp_path.iterdir()] == ["k.json"]


def test_device_names_are_not_project_names():
    assert sproject.safe_name("con") == "_con" and sproject.safe_name("NUL") == "_NUL"
    assert sproject.safe_name("LPT1") == "_LPT1" and sproject.safe_name("console") == "console"


def test_the_page_runs_only_the_apps_own_scripts(base):
    """Rewrite stage 6: the map page's Content-Security-Policy lets only this app's script files run - a name from a
    drawing or a KML that slipped into the page's HTML (an onerror=, a <script>) is never run; the page itself has no
    inline script or handler attribute for the policy to break."""
    import re
    url, _ = base
    with urllib.request.urlopen(url + "/sewer", timeout=30) as r:
        csp = r.headers.get("Content-Security-Policy") or ""
        page = r.read().decode("utf-8")
    rules = dict((d.split(" ", 1) + [""])[:2] for d in (x.strip() for x in csp.split(";")) if d)
    assert rules.get("script-src") == "'self'" and rules.get("object-src") == "'none'" and "default-src" in rules
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", page)                 # no inline script
    assert not re.search(r"\son[a-z]+\s*=", page)                              # no handler attribute
    js = os.path.join(ui.STATIC, "js")
    for name in os.listdir(js):
        with open(os.path.join(js, name), encoding="utf-8") as fh:
            text = fh.read()
        assert not re.search(r"\beval\(|new Function\(", text), name
        assert not re.search(r"<[a-z][^>]*\son(click|change|input|load|error|mouse\w+|key\w+)=", text), name
