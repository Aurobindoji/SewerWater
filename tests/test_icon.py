"""The app icon (user request 14-Nov-2026): one picture, its background transparent - the exe and the setup take
installer/SewerWater.ico, the start page shows it, and every page has it on its tab (each server its own copy:
the modules stay independent)."""
import io
import os
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
from PIL import Image

from launcher import server as L
from sewer_app import ui
from water_app import server as wserver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_icon_file_and_where_it_is_used():
    ico = Image.open(os.path.join(ROOT, "installer", "SewerWater.ico"))
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(ico.info["sizes"])
    big = ico.ico.getimage((256, 256)).convert("RGBA")
    a = big.getchannel("A")
    assert a.getpixel((0, 0)) == 0 and a.getpixel((255, 255)) == 0          # the corners: nothing (no white ground)
    assert a.getpixel((128, 128)) == 255
    with open(os.path.join(ROOT, "SewerWater.spec"), encoding="utf-8") as fh:
        assert 'icon="installer/SewerWater.ico"' in fh.read()
    with open(os.path.join(ROOT, "installer", "SewerWater.iss"), encoding="utf-8") as fh:
        assert "SetupIconFile=SewerWater.ico" in fh.read()


@pytest.mark.parametrize("handler", [L.Handler, ui.Handler, wserver.Handler])
def test_every_server_gives_the_icon_for_the_tab(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/favicon.ico", timeout=10) as r:
            assert r.headers.get_content_type() == "image/x-icon"
            assert (16, 16) in Image.open(io.BytesIO(r.read())).info["sizes"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_the_start_page_shows_it():
    srv = L.Server(("127.0.0.1", 0), L.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        with urllib.request.urlopen(base + "/", timeout=10) as r:
            assert 'src="/icon.png"' in r.read().decode("utf-8")
        with urllib.request.urlopen(base + "/icon.png", timeout=10) as r:
            assert Image.open(io.BytesIO(r.read())).mode == "RGBA"
    finally:
        srv.shutdown()
        srv.server_close()
