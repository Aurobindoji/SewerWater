"""Trunk sewers marked on the page (user request 21-Oct-2026, CPHEEO 3.71.2 Table 3.31 p3-127): a sewer with no house
connections gets its manholes at 60 / 90 / 120 / 150 m by the designed diameter instead of 30 m - so it is not cut at
30 m before the design (spacing.presplit), and its pieces cut at bends are trunk too."""
from sewer_app import check, edits, spacing, ui
from sewer_app.criteria import load_criteria

from test_bends import net_of
from test_stages import call, kml, server  # noqa: F401  (the fixture)


def test_clean_and_pieces():
    e = edits.clean({"trunk": ["CO-2", "CO-1", "CO-2", " "], "conduits": {}})
    assert e["trunk"] == ["CO-1", "CO-2"] and edits.clean(None)["trunk"] == []
    net = {"conduits": [{"label": "CO-1"}, {"label": "CO-1-2", "piece_of": "CO-1"}, {"label": "CO-3"}]}
    assert edits.trunk_labels(net, ["CO-1"]) == ["CO-1", "CO-1-2"]


def test_trunk_not_cut_at_30_m():
    poly = [(0.0, 0.0), (20.0, 0.0), (20.0, 50.0)]                    # 20 m, a 90 deg bend, 50 m
    net = net_of([("CO-1", "MH-1", "MH-9", poly)], {"MH-1": 80.0, "MH-9": 79.3})
    assert [r["why"] for r in spacing.presplit(net, ui.criteria_for())[1]] == ["bend 90 deg", "spacing"]
    crit = ui.criteria_for(trunk=["CO-1"])
    assert crit["sewer"]["trunk_conduits"]["value"] == ["CO-1"]
    assert "marked in the map UI" in crit["sewer"]["trunk_conduits"]["note"]
    assert [r["why"] for r in spacing.presplit(net, crit)[1]] == ["bend 90 deg"]       # the bend only


def test_check_of_a_piece():
    """The final check: a piece of a trunk sewer is held to Table 3.31, not to 30 m."""
    crit = load_criteria()
    crit["sewer"]["trunk_conduits"]["value"] = ["CO-1"]
    rec = {"label": "CO-1-2", "parent": "CO-1", "diameter_mm": 300, "n": 0.013, "length_m": 55.0, "slope": 0.004,
           "to_outfall": True, "flow_lps": 20.0, "cover_min_m": 1.5}
    out = check.check_sewer({"conduits": [dict(rec)], "manholes": [], "outfalls": []}, crit, "ultimate")
    assert "manhole spacing" not in out["conduits"][0]["issues"]
    assert not any("not found" in w for w in out["warnings"])
    crit["sewer"]["trunk_conduits"]["value"] = []
    out = check.check_sewer({"conduits": [dict(rec)], "manholes": [], "outfalls": []}, crit, "ultimate")
    assert "manhole spacing 30 m" in out["conduits"][0]["issues"]


def test_trunk_from_the_page(server):  # noqa: F811
    assert call(server + "/api/layout", {"name": "t", "kml": kml(), "spacing": 0})["ok"]
    cat = call(server + "/api/catalogs")["catalogs"][0]["name"]
    req = {"name": "t", "stp": "MH-17", "catalog": cat, "joint": "ss", "sewage_lpcd": 108, "start_depth": 0.7}
    z = call(server + "/api/zoning", req)
    assert z["ok"], z["log"]
    opt = z["options"][0]["option"]
    d = call(server + "/api/design", dict(req, option=opt))
    assert d["ok"], d["log"]
    assert not any(w["trunk"] for w in d["sewers"])
    # the longest conduit of the network, cut into pieces at 30 m
    cut = max((w for w in d["sewers"] if w["orig"] != w["label"]), key=lambda w: w["length"])["orig"]
    pieces = [w for w in d["sewers"] if w["orig"] == cut]
    assert len(pieces) >= 2 and all(w["length"] <= 30.5 for w in pieces)

    t = call(server + "/api/design", dict(req, option=opt, edits={"trunk": [cut]}))
    assert t["ok"], t["log"]
    mine = [w for w in t["sewers"] if w["orig"] == cut]
    assert mine and all(w["trunk"] for w in mine) and len(mine) < len(pieces)
    assert sum(1 for w in t["sewers"] if w["trunk"]) == len(mine)
    assert "trunk sewers (page, CPHEEO Table 3.31 spacing)" in t["log"]
    # its manholes by Table 3.31 (up to 600 mm: 60 m), planned after the design
    lim = {600: 60, 900: 90, 1200: 120, 1500: 150}
    for w in mine:
        cap = next(v for k, v in lim.items() if w["D"] <= k)
        for p in w["pieces"] or [w]:
            assert p["length"] <= cap + 0.5, (w["label"], p["length"])
    assert t["edits"]["trunk"] == [cut]
    assert call(server + "/api/last_results?name=t")["design"]["edits"]["trunk"] == [cut]
