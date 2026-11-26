"""The original drawing's text height read once per version of the file (rewrite stage 7, 26-Nov-2026: the DXF
exports read the whole drawing again for it every time - 3/4 of their time on a large drawing). Each module's own
copy (water: net/cad.py, sewer: out/cad.py); the height itself as before."""
import os
import time

import ezdxf
import pytest

from sewer_app.out import cad as scad
from water_app.net import cad as wcad


def _drawing(path, h):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for i, x in enumerate((0, 30, 60), 1):
        msp.add_text(f"MH-{i}", dxfattribs={"insert": (x, 0), "height": h})
    msp.add_text("road", dxfattribs={"insert": (0, 9), "height": 5.0})
    doc.saveas(path)


@pytest.mark.parametrize("cad,pkg", [(wcad, "water_app.net.dxf_inspect"), (scad, "sewer_app.net.dxf_inspect")])
def test_read_once_per_version_of_the_drawing(cad, pkg, tmp_path, monkeypatch):
    import importlib
    di = importlib.import_module(pkg)
    src, keep = str(tmp_path / "net.dxf"), str(tmp_path / "out" / "h.json")
    _drawing(src, 0.8)
    reads = []
    real = di.load
    monkeypatch.setattr(di, "load", lambda p: reads.append(p) or real(p))
    cad._TEXT_H.clear()
    first = cad.source_text_height(src, keep)
    assert first == (0.8, 3, "manhole labels (MH-...)") and len(reads) == 1
    assert cad.source_text_height(src, keep) == first and len(reads) == 1          # remembered in this run
    cad._TEXT_H.clear()                                                            # the app started again
    assert cad.source_text_height(src, keep) == first and len(reads) == 1          # from the kept file
    time.sleep(0.05)
    _drawing(src, 1.2)                                                             # the drawing changed
    os.utime(src, ns=(time.time_ns(), time.time_ns()))
    assert cad.source_text_height(src, keep)[0] == 1.2 and len(reads) == 2
    with open(keep, "w", encoding="utf-8") as fh:                                  # a spoilt kept file: read again
        fh.write("{not json")
    cad._TEXT_H.clear()
    assert cad.source_text_height(src, keep)[0] == 1.2 and len(reads) == 3


def test_the_network_reading_fills_waters_height(tmp_path):
    """Water: importing the network (its drawing read) leaves the height ready for the DXF export."""
    from water_app.net import netedit
    src = str(tmp_path / "net.dxf")
    _drawing(src, 0.9)
    wcad._TEXT_H.clear()
    netedit._INV.clear()
    netedit.dxf_layers(src, water=True)
    assert wcad._TEXT_H[tuple(wcad._version(src))][0] == 0.9
