"""Export / Import rate xlsx of the water DPR (rates.py, user decisions 15-Nov-2026): the SOR and the UPJN rates by
size, the rates the project's last design's DPR uses yellow; an imported xlsx changes the rates of every project's
DPR (kept in the master folder), 'मूल rates वापस' goes back to the app's own."""
import io
import os

import openpyxl
import pytest

from test_water_dpr import design  # noqa: F401  (the fixture)
from water_app.data import rates
from water_app.run import results
@pytest.fixture
def mine(tmp_path, monkeypatch):
    monkeypatch.setattr(rates, "USER_FILE", str(tmp_path / "home" / "rates" / "water_rates.json"))
    return rates.USER_FILE


def yellow(c):
    return (c.fill.start_color.rgb or "").endswith(rates.YELLOW) and c.fill.fill_type == "solid"


def test_export_import_reset(design, mine):  # noqa: F811
    d = design()
    old_dpr = d["files"]["dpr"]
    r = results.rate_export("wdpr", open_it=False)
    assert r["ok"] and r["design"] and os.path.isfile(r["path"]) and r["changed"] == 0
    assert r["sor_used"] > 5 and r["upjn_used"] > 0
    wb = openpyxl.load_workbook(r["path"])
    ws, wu = wb[rates.SOR_SHEET], wb[rates.UPJN_SHEET]
    h = rates.HEAD_ROW
    assert [ws.cell(h, j).value for j in (1, 4)] == ["Item No.", "Rate"]
    ys = [x for x in range(h + 1, ws.max_row + 1) if yellow(ws.cell(x, 4))]
    assert len(ys) == r["sor_used"]
    codes = {str(ws.cell(x, 1).value) for x in ys}
    # the yellow SOR items are those the DPR looks up (excavation_sor of dpr_water.json among them)
    assert str(wdpr_settings()["excavation_sor"]) in codes
    # the pipe sizes of the design yellow in pipe_supply, the others not
    sizes = {p["size"] for p in d["pipes"]}
    yu = {(wu.cell(x, 1).value, str(wu.cell(x, 3).value)) for x in range(h + 1, wu.max_row + 1) if yellow(wu.cell(x, 5))}
    assert {s for k, s in yu if k == "pipe_supply"} == sizes
    # change a used SOR rate and the supply rate of a used size, import
    x_sor = ys[0]
    code, sor0 = str(ws.cell(x_sor, 1).value), ws.cell(x_sor, 4).value
    ws.cell(x_sor, 4, round(sor0 * 1.1, 2))
    s0 = sorted(sizes)[0]
    x_up = next(x for x in range(h + 1, wu.max_row + 1) if wu.cell(x, 1).value == "pipe_supply" and wu.cell(x, 3).value == s0)
    up0 = wu.cell(x_up, 5).value
    wu.cell(x_up, 5, up0 + 100)
    buf = io.BytesIO()
    wb.save(buf)
    imp = rates.import_xlsx(buf.getvalue(), "my_rates.xlsx")
    assert imp["sor_changed"] == 1 and imp["upjn_changed"] == 1 and not imp["notes"]
    assert os.path.isfile(mine) and rates.status()["changed"] == 2
    # Export DPR again: a new workbook with the new rates (the old one was of the old rates)
    p2 = results.dpr_file("wdpr", open_it=False)["path"]
    assert p2 != old_dpr
    w2 = openpyxl.load_workbook(p2)
    sor = w2["R SOR 2025-26"]
    row = next(c.row for c in sor["A"] if str(c.value) == code)
    assert sor.cell(row, 4).value == pytest.approx(sor0 * 1.1, abs=0.01)
    d2 = [c.value for row in w2["D2 DS Estimate"].iter_rows() for c in row]
    assert up0 + 100 in d2 and up0 not in d2, (up0, s0)
    assert results.dpr_file("wdpr", open_it=False)["path"] == p2          # the same rates: the same file
    # the next export shows them, as the user's
    r2 = results.rate_export("wdpr", open_it=False)
    assert r2["changed"] == 2
    # back to the app's own
    assert rates.reset() and not os.path.isfile(mine) and rates.status()["changed"] == 0
    assert results.dpr_file("wdpr", open_it=False)["path"] != p2


def test_export_without_a_design_and_bad_files(tmp_path, monkeypatch, mine):
    from water_app.data import project as wproject
    monkeypatch.setattr(wproject, "OUT_ROOT", str(tmp_path / "o"))
    r = results.rate_export("none", open_it=False)
    assert r["ok"] and not r["design"] and r["sor_used"] == 0 and r["upjn_used"] == 0
    with pytest.raises(ValueError):
        rates.import_xlsx(b"not an xlsx")
    wb = openpyxl.Workbook()
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError):
        rates.import_xlsx(buf.getvalue())
    # an item the app does not have: left out and told; a rate that is not a number: refused
    wb = openpyxl.load_workbook(r["path"])
    ws = wb[rates.SOR_SHEET]
    x = ws.max_row + 1
    ws.cell(x, 1, 999999)
    ws.cell(x, 4, 5)
    buf = io.BytesIO()
    wb.save(buf)
    imp = rates.import_xlsx(buf.getvalue())
    assert imp["sor_changed"] == 0 and "999999" in imp["notes"][0][1]
    ws.cell(rates.HEAD_ROW + 3, 4, "abc")
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError):
        rates.import_xlsx(buf.getvalue())


def wdpr_settings():
    from water_app.out import dpr as wdpr
    return wdpr.settings()
