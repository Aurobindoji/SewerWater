"""The user's changes from the pipe / manhole tables (edits.apply): a given diameter / slope is designed as given (only
steepened for the minimum cover, broken rules flagged), a given manhole GL / outgoing invert is used; unknown labels
are left out."""
from sewer_app import edits, pipeline, zoning

from synthetic import INP, synth

quiet = lambda s: None                                                  # noqa: E731


def run(e):
    net, fixed, notes = edits.apply(synth(seed=1), e)
    return pipeline.run(net, INP, log=quiet, fixed_inv=fixed), notes


def test_free_design_unchanged_without_edits():
    a = pipeline.run(synth(seed=1), INP, log=quiet)["res"]
    b, notes = run({})
    assert not notes and all(abs(a[k]["dn"] - b["res"][k]["dn"]) < 1e-9 and a[k]["D"] == b["res"][k]["D"] for k in a)


def test_given_diameter_and_slope():
    free = pipeline.run(synth(seed=1), INP, log=quiet)["res"]
    lab = "C30"                                          # on the main sewer, well below its head
    big = next(z for z in pipeline.run(synth(seed=1), INP, log=quiet)["catalog"][2] if z["id_mm"] > free[lab]["D"] + 1)
    out, _ = run({"conduits": {lab: {"D": big["id_mm"], "slope": 1 / 2000}}})
    d = out["res"][lab]
    assert d["D"] == big["id_mm"] and abs(d["slope"] - 1 / 2000) < 1e-12 and d["gov"] == "given slope"
    assert any("flatter than Table 3.13" in f for f in d["flags"])
    only_d, _ = run({"conduits": {lab: {"D": big["id_mm"]}}})
    assert only_d["res"][lab]["D"] == big["id_mm"] and only_d["res"][lab]["gov"].startswith("given diameter")


def test_given_slope_steepened_for_cover():
    out, _ = run({"conduits": {"C0": {"slope": 1e-5}}})       # head sewer: 1 in 100000 would leave no cover
    d = out["res"]["C0"]
    assert d["slope"] > 1e-5 and "steepened" in d["gov"]
    assert d["depth_dn"] >= INP["start_depth"] - 1e-6


def test_given_gl_and_invert():
    free = pipeline.run(synth(seed=1), INP, log=quiet)
    inv = free["node_info"]["M20"]["invert"]
    out, _ = run({"manholes": {"M20": {"invert": inv - 0.5}, "M5": {"gl": 105.0}}})
    assert abs(out["node_info"]["M20"]["invert"] - (inv - 0.5)) < 1e-9
    assert out["ground"]["M5"] == 105.0
    high, _ = run({"manholes": {"M20": {"invert": inv + 0.5}}})          # above the incoming sewers: flagged
    assert any("given invert" in f for f in high["res"]["C20"]["flags"])


def test_unknown_labels_and_zoning():
    _, notes = run({"conduits": {"NOPE": {"D": 300}}, "manholes": {"XX": {"gl": 1}, "M1": {"gl": ""}}})
    assert notes == ["edit ignored: conduit NOPE not in the network", "edit ignored: manhole XX not in the network"]
    net, fixed, _ = edits.apply(synth(seed=1), {"conduits": {"C30": {"D": 600}}})
    z = zoning.run(net, INP, stp="OUT", log=quiet, given_only=True, only_given=True, fixed_inv=fixed)
    assert z["rank"][0]["res"]["C30"]["D"] == 600
