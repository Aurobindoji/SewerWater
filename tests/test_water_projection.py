"""Population projection of the water module (user request 30-Oct-2026, as the Elmwood water estimate's sheet 'T'): the
base year and its population with the census of the town -> the base year, +15 and +30 years by five methods, one
adopted (default geometrical); the design's population (the junctions' base-year population) grown by its ratios,
the stage check from them; DPR sheet 'T' with live formulas."""
import openpyxl
import pytest

from test_dxf_extract import make_dxf
from test_water_ui import call, server  # noqa: F401  (the fixture)
from water_app import netedit
from water_app import population as P

# the Elmwood 'T': census 1951-2011 and the population known in 2025
CENSUS = "1951 376834, 1961 498567, 1971 672634, 1981 825717, 1991 1139236, 2001 1374963, 2011 1636569, 2025 2679842"


def test_the_methods_as_the_elmwood():
    f = P.project(2027, 125180, CENSUS)
    # T L55, P55, U55
    assert round(f["X"], 2) == 286418.57 and round(f["Y"], 2) == 103910.33 and round(f["r"] * 100, 2) == 28.74
    # the census projected from its last year 2025 to 2027 / 2042 / 2057: T M96, M101, M106 and K124, K129, K134
    a, i, g = (f["town"][m] for m in ("arithmetical", "incremental", "geometrical"))
    # (the Elmwood rounds X and Y to 2 decimals first, its 'Say' row 55: a cent apart at most)
    assert [a[t] for t in ("init", "mid", "ult")] == pytest.approx([2737125.71, 3166753.57, 3596381.42], abs=0.02)
    assert [i[t] for t in ("init", "mid", "ult")] == pytest.approx([2749594.95, 3405227.78, 4294658.84], abs=0.05)
    assert g["ult"] == pytest.approx(6014401.33, rel=1e-4)            # T L160 (its r rounded to 28.74 %)
    # the project (a part of the town): its base-year population x the census projection's ratio
    for m, v in f["by_method"].items():
        assert v["init"] == 125180 and v["ult"] == P.ceil5(125180 * f["town"][m]["ult"] / f["town"][m]["init"])
    assert f["adopted"] == "geometrical" and f["ratio"]["ult"] == pytest.approx(f["by_method"]["geometrical"]["ult"] / 125180)
    assert set(f["by_method"]) == set(P.METHODS)
    assert f["by_method"]["semilog"]["ult"] > f["by_method"]["graph"]["ult"]          # exponential above the line
    assert 160000 < f["by_method"]["arithmetical"]["ult"] < 170000                    # not + 3 x the town's 2.86 lakh
    assert P.project(2027, 125180, CENSUS, "arithmetical")["adopted"] == "arithmetical"
    # two census figures: no incremental; a census year after the base year, too few: refused
    two = P.project(2027, 1000, "2001 800, 2011 900")
    assert "incremental" not in two["by_method"] and any("three census" in n[1] for n in two["notes"])
    for bad in ("2011 900", "2001 800, 2031 900"):
        with pytest.raises(ValueError):
            P.project(2027, 1000, bad)


def test_decreasing_rate_as_the_cpheeo_example():
    """CPHEEO Manual on Water Supply 2024 Part A Annexure 2.8 (user request 9-Nov-2026): the decreasing rate of growth,
    Eq. 2.5 and its illustrative example p982-984 - S -1.40 % per decade, 2021 1,54,251, 2031 2,10,121; 2025 / 2040 /
    2055 by interpolation 1,75,000 / 2,75,000 / 4,23,000 (rounded there)."""
    c = "1971 27279, 1981 39068, 1991 68019, 2001 80625, 2011 112085"
    rows, *_ = P.growth(P.parse_census(c))
    assert P.decrease_s(rows) * 100 == pytest.approx(-1.40, abs=0.01)
    dec = lambda y: P.decreasing((2011, 112085), rows, y - 2011)
    assert dec(2021) == pytest.approx(154251, abs=5) and dec(2031) == pytest.approx(210121, abs=10)
    assert [dec(y) for y in (2025, 2040, 2055)] == pytest.approx([175000, 275000, 423000], rel=0.003)
    f = P.project(2025, 175000, c)
    assert "decreasing" in f["by_method"] and f["S"] == pytest.approx(P.decrease_s(rows))
    assert f["town"]["decreasing"]["init"] == pytest.approx(dec(2025)) and not any("decreasing" in n[1] for n in f["notes"])
    # a rate of growth rising (the Elmwood census with its 2025): noted as not this method's case; two census: none
    g = P.project(2027, 125180, CENSUS)
    assert g["S"] > 0 and any(n[1].startswith("decreasing rate: the decadal rate of growth is not falling") for n in g["notes"])
    assert "decreasing" not in P.project(2027, 1000, "2001 800, 2011 900")["by_method"]


def test_zoning_and_design_on_a_projection(server):  # noqa: F811
    url, tmp = server
    src = str(tmp / "small.dxf")
    make_dxf(src)
    netedit._UNDO.clear()
    d = call(url + "/api/w/dxf_import", {"path": src, "name": "wpj", "pipe_layers": ["PIPE"], "mh_layers": ["MH"],
                                         "level_layers": ["GL"], "epsg": "local"})
    assert d["ok"]
    a = d["nodes"]["MH-1"]["latlng"]
    oht = {"name": "Prop-OHT-1", "lat": a[0], "lng": a[1], "existing": "0", "capacity_kl": "", "staging_m": ""}
    pj = {"base_pop": "1200", "census": "1991 800, 2001 950, 2011 1100", "method": ""}
    prev = call(url + "/api/w/projection", {"base_year": 2027, "projection": pj})
    assert prev["ok"] and prev["projection"]["adopted"] == "geometrical"
    f = prev["projection"]
    # the factor, the total and the stages of the page are not used: the projection's
    req = {"name": "wpj", "ohts": [oht], "pop_factor": 9, "pop_total": 99, "base_year": 2027, "pop_initial": 5,
           "pop_mid": 7, "projection": pj}
    z = call(url + "/api/w/water_zoning", req)
    assert z["ok"], z.get("log")
    assert z["population"] == pytest.approx(f["pop"]["ult"], abs=1) and z["projection"]["adopted"] == "geometrical"
    assert any(x["text"].startswith("population projection - Geometrical Increase Method") for x in z["flags"])
    w = call(url + "/api/w/water_design", req)
    assert w["ok"], w.get("log")
    st = {s["stage"]: s for s in w["stages"]}
    assert st["init"]["pop"] == pytest.approx(1200, abs=1) and st["mid"]["pop"] == pytest.approx(f["pop"]["mid"], abs=1)
    assert st["ult"]["pop"] == pytest.approx(f["pop"]["ult"], abs=1)
    # DPR sheet T: the census, X / Y / r, the five methods, the adopted
    wb = openpyxl.load_workbook(w["files"]["dpr"])
    # the technical statement starts with it, the example technical.xlsx's sheets after it, T10 OZ Demand later
    assert wb.sheetnames.index("T1 Population") == wb.sheetnames.index("Title - Technical") + 1
    assert wb.sheetnames.index("T1 Population") < wb.sheetnames.index("T10 OZ Demand")
    ws = wb["T1 Population"]
    vals = {c.value for row in ws.iter_rows() for c in row if c.value is not None}
    assert {"Geometrical Increase Method", "Semi Log Graph Method (straight line fitted)", "Adopted method"} <= vals
    formulas = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
    assert any(v.startswith("=$C$") and "*(1+$F$" in v for v in formulas)                     # Pc (1 + r)^n
    assert any(v.startswith("=CEILING($D$") and "/D" in v for v in formulas)                   # P0 x T / T(base)
    assert any(v.startswith("=SLOPE(G") for v in formulas) and any("=PRODUCT(F" in v for v in formulas)
    last = call(url + "/api/w/water_last?name=wpj")["design"]["req"]
    assert last["projection"]["census"] == pj["census"]
    # no census: as before (the factor and the total of the page)
    z0 = call(url + "/api/w/water_zoning", dict(req, projection={"base_pop": "1200", "census": ""}, pop_factor=2,
                                                 pop_total=500))
    assert z0["ok"] and z0["population"] == 1000 and z0["projection"] is None


def test_far_open_below_one_is_flagged():
    """Far-open's balancing factor below 1 (user decision 10-Nov-2026): flagged as 'below' - its own warning in place
    of 'low'; the example's ratios give back the example's Far-open (technical.xlsx T P470)."""
    from water_app import ui_api as U
    ch = U.WARD_CHARS
    city = dict(zip(ch, (698311, 673088, 720858, 587585)))
    growth = dict(zip(ch, ([1.02, 1.25, 1.50], [1.04, 1.40, 1.85], [1.06, 1.63, 2.45], [1.0932, 1.9183, 3.3282])))
    S = sum(city.values())
    ex = {t: sum(city[k] * growth[k][j] for k in ch) / S for j, t in enumerate(("init", "mid", "ult"))}
    fo = U.far_open_balance({"city": city, "growth": growth}, {"town_ratio_from": ex})
    assert fo["factors"] == pytest.approx([1.0932, 1.9183, 3.3282], abs=1e-4) and fo["below"] == []
    slow = dict(ex, ult=1.6023)                       # an incremental-like town: Far-open 0.40 at +30 years
    fo = U.far_open_balance({"city": city, "growth": growth}, {"town_ratio_from": slow})
    assert fo["below"] == ["ult"] and fo["factors"][2] == pytest.approx(0.40, abs=0.01)
    f = {"names": {"inc": ["Incremental", "Incremental"]}, "adopted": "inc", "years": {"init": 2027, "mid": 2042, "ult": 2057},
         "pop": {"init": 1, "mid": 2, "ult": 3}, "ratio": {"ult": 1.6}, "notes": [], "far_open": fo}
    texts = [x["text"] for x in U._proj_flags(f, None)]
    assert any("below 1 (ult 0.40" in t for t in texts) and not any("grows slower" in t for t in texts)
