"""The town's wards as an xlsx (user decisions 9-Nov-2026): exported in the format of the user's 'WARDWISE POPULATION
AND AREA' table, imported back (or the user's own table of those columns), kept by town for every project."""
import io

import openpyxl
import pytest

from water_app import city_wards as cw
from water_app import server as wserver


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(wserver, "PROJECTS", str(tmp_path / "projects"))
    return tmp_path


ROWS = [{"no": "1", "name": "Riverside", "pop": 37040, "hh": 4645, "area": 132.0, "census": 17204,
         "char": "Proximal Developing"},
        {"no": "3", "name": "Ashford", "pop": 41898, "hh": 5966, "area": 356.58, "census": 22096, "char": "Far-open"},
        {"no": "21", "name": "Camden", "pop": 33285, "hh": 4049, "area": None, "census": None, "char": ""}]
NOCHAR = [dict(r, char="") for r in ROWS]          # the export has no character to choose: the app's by the criteria


def test_export_then_import(home):
    data = cw.export_xlsx("Springfield City Council", 2025, ROWS)
    ws = openpyxl.load_workbook(io.BytesIO(data)).active
    assert ws["A1"].value == "WARDWISE POPULATION AND AREA" and ws["E3"].value == "population in Year 2025"
    assert (ws["E4"].value, ws["F4"].value) == ("Total", "house hold")
    assert ws["D5"].value == "Riverside" and ws["I5"].value == '=IFERROR(ROUND(E5/G5,2),"")'
    # no column to choose the character (user 9-Nov-2026): J by the criteria, the app by the density and criteria
    assert ws["J3"].value == "Character by the density criteria" and not ws.data_validations.dataValidation
    d = cw.import_xlsx(data, "x.xlsx")
    assert d["city"] == "Springfield City Council" and d["year"] == 2025 and d["notes"] == []
    assert d["rows"] == NOCHAR
    keep = cw.save(d, "x.xlsx")
    assert cw.cities() == [{"city": "Springfield City Council", "year": 2025, "n": 3, "file": "x.xlsx",
                            "imported": keep["imported"]}]
    assert cw.load("Springfield City Council")["rows"] == NOCHAR
    assert (home / "cities" / "Springfield_City_Council.json").is_file()
    # all in English (user 9-Nov-2026), EXTRA empty rows below for more wards, J the character by the criteria; beside
    # it (L-M) the criteria of the character (the density above which) and the town's census by decade - read back
    assert all(ord(ch) < 128 for row in ws.iter_rows(values_only=True) for v in row for ch in str(v or ""))
    assert ws.max_row == cw.FIRST + len(ROWS) + cw.EXTRA - 1 and ws["D8"].value is None and ws["I8"].value
    assert ws["J5"].value.startswith('=IF(I5="","",IF(I5>$M$5,"Saturated (Core)",IF(I5>$M$6,"High (Proximal Developed)"')
    assert ws["K5"].value is None and ws.column_dimensions["L"].width >= len(cw.CEN_TITLE) * 0.75
    assert [ws.cell(r, 12).value for r in range(3, 9)] == [cw.CRIT_TITLE, "Character of Ward"] + list(cw.CHARS)
    assert [ws.cell(r, 13).value for r in range(5, 9)] == [585, 310, 170, "the rest"]
    assert ws["L11"].value == cw.CEN_TITLE and [ws.cell(r, 12).value for r in range(13, 20)] == list(range(1951, 2012, 10))
    data2 = cw.export_xlsx("Springfield", 2025, ROWS, dens={"Core": 300},
                           census=[[1991, 1030863], [2001, 1203961], [2011, 1198491]])
    d2 = cw.import_xlsx(data2, "v.xlsx")
    # the characters by CPHEEO's categories with the DPR's word (9-Nov-2026): an old name ("Core") read as its new one
    assert d2["dens"] == {"Saturated (Core)": 585, "High (Proximal Developed)": 300, "Medium (Proximal Developing)": 170}
    assert d2["census"] == [[1991, 1030863], [2001, 1203961], [2011, 1198491]] and d2["rows"] == NOCHAR
    assert cw.save(d2, "v.xlsx")["census"] == d2["census"] and cw.load("Springfield")["dens"]["High (Proximal Developed)"] == 300
    # an empty list to begin with: BLANK rows, the town in each
    ws = openpyxl.load_workbook(io.BytesIO(cw.export_xlsx("Springfield", 2025, None))).active
    assert ws.max_row == cw.FIRST + cw.BLANK - 1 and ws["B5"].value == "Springfield"
    # no town given (the page's table to begin with): the file's name, not the header's "Name of ULB"
    d = cw.import_xlsx(cw.export_xlsx("", 2025, ROWS[:1]), "springfield_wards.xlsx")
    assert d["city"] == "springfield_wards" and [w["name"] for w in d["rows"]] == ["Riverside"]
    # the town's kept list again, also written to cities\
    r = cw.export_b64({"city": "Springfield City Council"})
    assert r["file"] == "Springfield_City_Council_wards.xlsx" and (home / "cities" / r["file"]).is_file()
    assert cw.export_b64({"city": "town_wards", "rows": ROWS})["file"] == "town_wards.xlsx"    # "wards" once


def test_the_users_own_table():
    """As the user's table: the town's name merged down the rows, a total row, text numbers, a character in other
    letters, an unknown one."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "WARDWISE POPULATION AND AREA"
    for c, t in zip("ABCDEGHIJ", ("Sl. No", "Name of ULB", "No of ward", "name of ward", "population\nin Year 2025",
                                  "Eq.area\n( IN HECTARE )", "Census Population 2011", "Population Density in Year",
                                  "Character of Ward")):
        ws[f"{c}2"] = t
    ws.merge_cells("E2:F2")
    ws["E3"], ws["F3"] = "Total", "house hold"
    data = [(1, "Springfield City Council", 1, "Riverside", "37,040", 4645, 132, 17204, 280.61, "Proximal\nDeveloping"),
            (2, None, 2, "Sikraul", 34247, 5001, 158.76, 18521, 215.72, "FAR OPEN"),
            (3, None, 3, "Ashford", 41898, 5966, 356.58, 22096, 117.5, "Outer")]
    for i, row in enumerate(data):
        for j, v in enumerate(row):
            ws.cell(4 + i, j + 1, v)
    ws.merge_cells("B4:B6")
    ws["A7"], ws["E7"] = "Total", 113185
    buf = io.BytesIO()
    wb.save(buf)
    d = cw.import_xlsx(buf.getvalue(), "wards.xlsx")
    assert d["city"] == "Springfield City Council" and d["year"] == 2025
    assert [(w["no"], w["name"], w["pop"], w["char"]) for w in d["rows"]] == [
        ("1", "Riverside", 37040, "Medium (Proximal Developing)"), ("2", "Sikraul", 34247, "Low (Far-open)"),
        ("3", "Ashford", 41898, "")]
    # the names: the new ones, CPHEEO's alone, the old ones (the DPR's order of density)
    assert [cw._char(x) for x in ("Saturated (Core)", "saturated", "HIGH", "Core", "Proximal Developed")] == [
        "Saturated (Core)", "Saturated (Core)", "High (Proximal Developed)", "High (Proximal Developed)", "Saturated (Core)"]
    assert d["rows"][0]["area"] == 132 and d["rows"][0]["hh"] == 4645
    assert len(d["notes"]) == 1 and "Outer" in d["notes"][0][1]
