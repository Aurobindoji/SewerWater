"""python -m sewer_app design / zoning, end to end from a drawing (the small DXF of test_dxf_extract)."""
import glob
import json
import os

import openpyxl

from sewer_app.__main__ import main

from synthetic import INP
from test_dxf_extract import make_dxf


def test_design_and_zoning_from_dxf(tmp_path):
    dxf = str(tmp_path / "small.dxf")
    make_dxf(dxf)
    inp = str(tmp_path / "inputs.json")
    with open(inp, "w", encoding="utf-8") as fh:
        json.dump(dict(INP, pop_total=1500), fh)
    out = str(tmp_path / "out")
    common = ["--dxf", dxf, "--pipe-layers", "PIPE", "--mh-layers", "MH", "--level-layers", "GL",
              "--inputs", inp, "--out", out]
    main(["design"] + common + ["--outfall", "MH-5"])
    xl = [f for f in glob.glob(os.path.join(out, "small_sewer_design_*.xlsx")) if not f.endswith("_DPR.xlsx")]
    assert len(xl) == 1 and os.path.isfile(xl[0][:-5] + ".dxf") and os.path.isfile(xl[0][:-5] + "_DPR.xlsx")
    wb = openpyxl.load_workbook(xl[0], read_only=True)
    assert wb["Design"].max_row == 1 + 5                     # 5 conduits designed
    main(["zoning"] + common + ["--outfall", "MH-5", "--network-dxf", "best", "--ref-gl", "MH-5",
                                "--gl-bands", "0-0.5, 0.5+"])
    assert glob.glob(os.path.join(out, "small_zoning_*_costs.xlsx"))
    assert glob.glob(os.path.join(out, "small_zoning_*_GL_bands.png"))
    zx = [f for f in glob.glob(os.path.join(out, "small_zoning_*.xlsx")) if not f.endswith("_costs.xlsx")]
    rows = list(openpyxl.load_workbook(zx[0], read_only=True)["GL bands"].iter_rows(values_only=True))
    assert len(rows) == 1 + 3                                # below + 2 ranges
    main(["design"] + common + ["--outfall", "MH-5", "--zoning-option", "CURRENT"])
    assert glob.glob(os.path.join(out, "small_CURRENT_sewer_design_*.xlsx"))
