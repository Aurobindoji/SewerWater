"""The survey GL of a new manhole (bend / spacing, spacing.presplit) given in the manhole table (user request
21-Oct-2026): the names are fixed by the drawing, so the edit finds the same manhole in the next design and replaces
the GL interpolated along the sewer."""
from test_stages import call, kml, server  # noqa: F401  (the fixture)


def test_survey_gl_of_a_new_manhole(server):  # noqa: F811
    assert call(server + "/api/layout", {"name": "g", "kml": kml(), "spacing": 0})["ok"]
    cat = call(server + "/api/catalogs")["catalogs"][0]["name"]
    req = {"name": "g", "stp": "MH-17", "catalog": cat, "joint": "ss", "sewage_lpcd": 108, "start_depth": 0.7}
    opt = call(server + "/api/zoning", req)["options"][0]["option"]
    d = call(server + "/api/design", dict(req, option=opt))
    assert d["ok"], d["log"]
    new = {m["label"]: m for m in d["new_manholes"]}
    rows = {m["label"]: m for m in d["manholes"]}
    lab = next(n for n in new if n in rows)
    assert rows[lab]["new"] in ("spacing",) or rows[lab]["new"].startswith("bend")
    assert not new[lab]["gl_edited"] and all(not rows[n]["new"] for n in rows if n not in new)
    gl = round(new[lab]["gl"] + 0.75, 3)

    e = call(server + "/api/design", dict(req, option=opt, edits={"manholes": {lab: {"gl": gl}}}))
    assert e["ok"], e["log"]
    new2 = {m["label"]: m for m in e["new_manholes"]}
    rows2 = {m["label"]: m for m in e["manholes"]}
    assert new2[lab]["gl_edited"] and abs(new2[lab]["gl"] - gl) < 1e-6 and abs(rows2[lab]["gl"] - gl) < 1e-6
    assert rows2[lab]["edited"] and "edit ignored" not in e["log"]
    # the sewers at it take the survey level too
    at = [w for w in e["sewers"] if w["from"] == lab or w["to"] == lab]
    assert at and all(abs((w["gl_up"] if w["from"] == lab else w["gl_dn"]) - gl) < 1e-6 for w in at)
