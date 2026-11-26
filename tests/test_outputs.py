"""The Outputs tab (user request 16-Nov-2026): a project's output files listed and opened from the page, both modules;
nothing outside the project's output folder."""
import os
import time

import pytest

from sewer_app.data import project as sproject
from water_app.data import project as wproject


@pytest.mark.parametrize("mod", [wproject, sproject])
def test_outputs_listed_and_opened(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "OUT_ROOT", str(tmp_path))
    folder = tmp_path / "p1"
    (folder / "intze").mkdir(parents=True)
    for f, age in (("p1_design_20261116_1200.dxf", 30), ("p1_water_design_20261116_1201.xlsx", 20),
                   ("intze/Prop-OHT-1.pdf", 10), ("p1_wdesign_ui.json", 0), ("~$p1_DPR.xlsx", 0)):
        p = folder / f
        p.write_text("x")
        t = time.time() - age
        os.utime(p, (t, t))
    r = mod.output_files("p1")
    assert r["ok"] and r["folder"] == str(folder)
    assert [f["file"] for f in r["files"]] == ["intze/Prop-OHT-1.pdf", "p1_water_design_20261116_1201.xlsx",
                                               "p1_design_20261116_1200.dxf"]        # newest first; no json, no Excel lock
    assert mod.output_files("none")["files"] == []
    opened, shown = [], []
    monkeypatch.setattr(os, "startfile", opened.append, raising=False)
    monkeypatch.setattr("subprocess.Popen", lambda args: shown.append(args))
    mod.open_output("p1", "intze/Prop-OHT-1.pdf")
    mod.open_output("p1", "p1_design_20261116_1200.dxf", folder=True)
    mod.open_output("p1", "", folder=True)
    assert opened == [os.path.realpath(folder / "intze" / "Prop-OHT-1.pdf"), os.path.realpath(folder)]
    assert shown == [["explorer", "/select,", os.path.realpath(folder / "p1_design_20261116_1200.dxf")]]
    (tmp_path / "secret.xlsx").write_text("x")
    for bad in ("../secret.xlsx", "..\\secret.xlsx", "missing.dxf", str(tmp_path / "secret.xlsx")):
        with pytest.raises(ValueError):
            mod.open_output("p1", bad)
