"""A water main network keeps its loops (user report 20-Oct-2026): the network check does not call loops or parts
without an outfall problems there, the auto repair does not cut them, and the loop cut heads an earlier repair made
(<junction>-C<n> on the same spot, a red cross) are merged back in one step."""
import pytest

from water_app import netedit, repair

from test_dxf_extract import make_dxf


@pytest.fixture
def st(tmp_path):
    path = str(tmp_path / "small.dxf")
    make_dxf(path)
    netedit._UNDO.clear()
    return netedit.import_dxf(str(tmp_path / "out"), "small", path, ["PIPE"], ["MH"], ["GL"], None, log=lambda s: None)


def types(st):
    return {i["type"] for i in netedit.issues(st)}


def test_loops_kept_and_rejoined(st):
    netedit.apply(st, [{"op": "connect", "a": "MH-1", "b": "MH-3"}])            # a loop
    assert not {"loop", "part without an outfall"} & types(st)                   # a water network: neither a problem
    # an auto repair as a sewer's (before 20-Oct-2026) cuts the loop: a cut head on the same spot, a red cross
    netedit.auto_repair(st, loops=True, merge=False)
    heads = [n for n in st["net"]["nodes"] if "-C" in n]
    assert len(heads) == 1 and repair.OVERLAP in types(st)
    assert netedit.cut_pairs(st["net"]) == [(heads[0].split("-C")[0], heads[0])]
    # merged back: the loop is there again, no red cross
    netedit.apply(st, [{"op": "rejoin_cuts"}])
    assert not [n for n in st["net"]["nodes"] if "-C" in n] and repair.OVERLAP not in types(st)
    with pytest.raises(ValueError):                                              # nothing left to rejoin
        netedit.apply(st, [{"op": "rejoin_cuts"}])
    netedit.undo(st)                                                             # one undo step: the cut again
    assert [n for n in st["net"]["nodes"] if "-C" in n] == heads
    netedit.apply(st, [{"op": "rejoin_cuts"}])
    # the water network's auto repair keeps the loop
    netedit.auto_repair(st)                                                      # its default: no loop cut
    assert not [n for n in st["net"]["nodes"] if "-C" in n]


def test_auto_repair_merges_the_red_crosses(st):
    """User request 21-Oct-2026: the water module's auto repair merges the junctions on the same spot (red crosses)."""
    netedit.apply(st, [{"op": "connect", "a": "MH-1", "b": "MH-3"}])
    netedit.auto_repair(st, loops=True, merge=False)                            # an old repair: a loop cut head
    head = next(n for n in st["net"]["nodes"] if "-C" in n)
    # and a junction drawn twice: MH-6 moved onto MH-5 (no pipe between them)
    ll5 = netedit.page_data(st)["nodes"]["MH-5"]["latlng"]
    netedit.apply(st, [{"op": "move", "mh": "MH-6", "latlng": ll5}])
    assert len([i for i in netedit.issues(st) if i["type"] == repair.OVERLAP]) == 2
    keep6 = next(k for k, d, _ in netedit.merge_pairs(st["net"]) if "MH-6" in (k, d))
    deg = lambda n: sum(n in (k["start_node"], k["stop_node"]) for k in st["net"]["conduits"])   # noqa: E731
    assert keep6 == ("MH-5" if deg("MH-5") >= deg("MH-6") else "MH-6")
    rows = netedit.auto_repair(st)
    merged = [r for r in rows if r["repair"] == netedit.MERGED]
    assert len(merged) == 2 and f"{head} -> {head.split('-C')[0]}" in {r["item"] for r in merged}
    assert repair.OVERLAP not in types(st) and head not in st["net"]["nodes"]
    netedit.undo(st)                                                             # one undo step for all of it
    assert head in st["net"]["nodes"] and "MH-6" in st["net"]["nodes"]


def test_three_on_one_spot_go_into_one():
    net = {"nodes": {"J-1": {"xy": [0.0, 0.0], "ground": 80.0}, "J-1-C1": {"xy": [0.0, 0.0], "ground": 80.0},
                     "J-1-C2": {"xy": [0.2, 0.0], "ground": 80.0}, "J-2": {"xy": [30.0, 0.0], "ground": 80.0},
                     "J-3": {"xy": [0.0, 30.0], "ground": 80.0}},
           "conduits": [{"label": "P-1", "start_node": "J-1", "stop_node": "J-2", "length_m": 30.0, "vertices": []},
                        {"label": "P-2", "start_node": "J-1-C1", "stop_node": "J-3", "length_m": 30.0, "vertices": []}],
           "outfalls": []}
    pairs = netedit.merge_pairs(net)
    assert {d for _, d, _ in pairs} == {"J-1-C1", "J-1-C2"} and {k for k, _, _ in pairs} == {"J-1"}
