"""The water server's guards (rewrite stage 1, 26-Nov-2026): only this run's own page makes it do anything (its token),
only drawings are read on the page's word, only output files are opened, a project folder's .pkl is never read (it
could run code), and files are written whole or not at all."""
import json
import os
import pickle
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from water_app import project as wproject
from water_app import results, store
from water_app import server as wserver


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setattr(wproject, "PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setattr(wproject, "OUT_ROOT", str(tmp_path / "output"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wserver.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path
    srv.shutdown()
    srv.server_close()


def post(url, body, token):
    h = {"Content-Type": "application/json"}
    if token is not None:
        h[wserver.TOKEN_HEADER] = token
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.mark.parametrize("token", [None, "", "wrong", wserver.TOKEN[:-1]])
def test_a_post_without_the_runs_token_is_refused(base, token):
    url, tmp = base
    code, res = post(url + "/api/save", {"name": "x", "kml": "<kml/>"}, token)
    assert code == 403 and res["ok"] is False and res.get("token")
    assert not (tmp / "projects" / "x.kml").exists()
    code, _ = post(url + "/api/barriers_save", {"name": "x", "barriers": [1]}, token)
    assert code == 403 and not (tmp / "projects" / "x.barriers.json").exists()


def test_the_page_carries_the_token_and_with_it_a_post_is_served(base):
    url, tmp = base
    with urllib.request.urlopen(url + "/water", timeout=30) as r:
        page = r.read().decode("utf-8")
    assert f'content="{wserver.TOKEN}"' in page and "__APP_TOKEN__" not in page
    code, res = post(url + "/api/save", {"name": "x", "kml": "<kml/>"}, wserver.TOKEN)
    assert code == 200 and res["ok"] and (tmp / "projects" / "x.kml").read_text(encoding="utf-8") == "<kml/>"


def test_only_a_dxf_is_read_on_the_pages_word(base):
    url, tmp = base
    other = tmp / "secret.txt"
    other.write_text("not a drawing", encoding="utf-8")
    code, res = post(url + "/api/dxf_layers", {"path": str(other)}, wserver.TOKEN)
    assert code == 200 and res["ok"] is False and ".dxf" in res["log"]


def test_only_output_files_are_opened(tmp_path, monkeypatch):
    monkeypatch.setattr(wproject, "OUT_ROOT", str(tmp_path))
    opened = []
    monkeypatch.setattr(os, "startfile", lambda p, *a: opened.append(p), raising=False)
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "run.bat").write_text("echo", encoding="utf-8")
    (tmp_path / "p" / "p_design.xlsx").write_bytes(b"x")
    with pytest.raises(ValueError):
        wproject.open_output("p", "run.bat")
    with pytest.raises(ValueError):
        wproject.open_output("p", "../p/../../x.xlsx")
    assert not opened
    assert wproject.open_output("p", "p_design.xlsx")["ok"] and len(opened) == 1


class _Runs:
    """A pickle that would make a folder when read - as one of another computer's project folder could."""

    def __init__(self, path):
        self.path = path

    def __reduce__(self):
        return os.makedirs, (self.path,)


def test_a_pkl_in_the_project_folder_is_never_read(tmp_path, monkeypatch):
    monkeypatch.setattr(wproject, "OUT_ROOT", str(tmp_path))
    folder = tmp_path / "p"
    folder.mkdir()
    mark = tmp_path / "it_ran"
    for name in ("p_wdesign_dpr.pkl", "p_wsim.pkl"):
        with open(folder / name, "wb") as fh:
            pickle.dump(_Runs(str(mark)), fh)
    (folder / "p_wdesign_ui.json").write_text('{"files": {}}', encoding="utf-8")
    with pytest.raises(ValueError):
        results.dpr_file("p", open_it=False)
    assert results.sim_pack("p") is None
    assert not mark.exists()


def test_kept_data_reads_back_as_it_was_written(tmp_path):
    data = {"valves": {"OZ-1": {350: 2, 100: 7}}, "census": [(1991, 1200.5), (2001, 1500)], "__map__": [1],
            "nested": {"__tuple__": "a real key"}, "keys": {(1, "a"): None}, "text": "पानी", "none": None}
    p = tmp_path / "d" / "k.json"
    store.write_json(str(p), data, typed=True)
    back = store.read_json(str(p), typed=True)
    assert back == data and type(back["census"][0]) is tuple and 350 in back["valves"]["OZ-1"]
    assert back["nested"] == {"__tuple__": "a real key"}


def test_a_failed_write_leaves_the_old_file_and_no_part(tmp_path):
    p = tmp_path / "k.json"
    store.write_json(str(p), {"a": 1})
    with pytest.raises(TypeError):
        store.write_json(str(p), {"a": object()})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    assert [f.name for f in tmp_path.iterdir()] == ["k.json"]


def test_device_names_are_not_project_names():
    assert wproject.safe_name("con") == "_con" and wproject.safe_name("NUL") == "_NUL"
    assert wproject.safe_name("COM1") == "_COM1" and wproject.safe_name("console") == "console"
    assert wproject.safe_name("../../x") == "x"
