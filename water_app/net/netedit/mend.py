"""netedit: automatic mending - same-spot junctions merged, through junctions removed, repair, the CSV save."""
import collections
import os
import time
from water_app.net import repair
from .edits import _apply1, _log, _snapshot
from .files import store
from .renumber import MERGED
from .texts import _net_json, _tuples


def merge_pairs(net):
    """[(keep, drop, distance m)] for the junctions on (nearly) the same spot with no pipe between them - the red
    crosses (repair.overlaps). A loop cut head <junction>-C<n> goes into its junction; else the one with more pipes
    stays, then the one with a GL, then the first name. Three or more on one spot all go into one."""
    t = _tuples(net)
    deg = collections.Counter(n for k in t["conduits"] for n in (k["start_node"], k["stop_node"]))
    rep = {}

    def top(n):
        while n in rep:
            n = rep[n]
        return n
    out = []
    for a, b, d in repair.overlaps(t):
        a, b = top(a), top(b)
        if a == b:
            continue
        cut = lambda h, o: h.startswith(o + "-C") and h[len(o) + 2:].isdigit()    # noqa: E731
        if cut(a, b):
            keep, drop = b, a
        elif cut(b, a):
            keep, drop = a, b
        else:
            keep, drop = sorted((a, b), key=lambda n: (-deg[n], net["nodes"][n].get("ground") is None, n))
        rep[drop] = keep
        deg[keep] += deg[drop]
        out.append((keep, drop, d))
    return out


THROUGH = "junctions between two pipes removed (junctions only where pipes join)"


def through_merge(net, keep=()):
    """Junctions only where pipes join (user request 14-Nov-2026, water only): a junction with exactly two pipes - a
    point along one line, as a drawing with a point every 30 m has them - goes; its two pipes become one, through
    its place (a vertex now), the lengths added, the first pipe's name kept. Junctions with one pipe (ends) and
    three or more (joints) stay, and so do those in `keep` (an OHT, a tube well, a bulk consumer stands there), a
    ring's last junction, and one whose going would lay a second pipe between the same two junctions. Pipes with and
    without house connections are not joined. Works on the network in place -> the junctions removed."""
    nodes, conds = net["nodes"], net["conduits"]
    keep = set(keep) | set(net.get("outfalls") or [])
    at = collections.defaultdict(list)                    # junction -> its pipes
    pairs = collections.Counter()
    for k in conds:
        at[k["start_node"]].append(k)
        at[k["stop_node"]].append(k)
        pairs[frozenset((k["start_node"], k["stop_node"]))] += 1
    gone, dead = [], set()
    for n in list(nodes):
        if n in keep or len(at[n]) != 2:
            continue
        a, b = at[n]
        if a is b or bool(a.get("no_conn")) != bool(b.get("no_conn")):
            continue
        far_a = a["stop_node"] if a["start_node"] == n else a["start_node"]
        far_b = b["stop_node"] if b["start_node"] == n else b["start_node"]
        if far_a == far_b or far_a == n or far_b == n or pairs[frozenset((far_a, far_b))]:
            continue
        va = [list(p) for p in a.get("vertices") or []]
        vb = [list(p) for p in b.get("vertices") or []]
        if a["start_node"] == n:                          # a: far_a -> n
            va.reverse()
        if b["stop_node"] == n:                           # b: n -> far_b
            vb.reverse()
        here = nodes[n].get("xy")
        if not va and here and nodes[far_a].get("xy"):
            va = [list(nodes[far_a]["xy"]), list(here)]
        if not vb and here and nodes[far_b].get("xy"):
            vb = [list(here), list(nodes[far_b]["xy"])]
        pairs[frozenset((far_a, n))] -= 1
        pairs[frozenset((far_b, n))] -= 1
        pairs[frozenset((far_a, far_b))] += 1
        a["start_node"], a["stop_node"] = far_a, far_b
        a["vertices"] = va + vb[1:] if va and vb else va + vb
        a["length_m"] = round(float(a["length_m"]) + float(b["length_m"]), 3)
        if a.get("auto_join") and not b.get("auto_join"):
            del a["auto_join"]
        at[far_b] = [a if k is b else k for k in at[far_b]]
        dead.add(id(b))
        del at[n], nodes[n]
        gone.append(n)
    if dead:
        conds[:] = [k for k in conds if id(k) not in dead]
    return gone


def joints_only(st, keep=()):
    """through_merge on the working network: one undo step, logged. Returns the number of junctions removed."""
    _snapshot(st)
    gone = through_merge(st["net"], keep)
    if gone:
        _log(st, THROUGH, f"{len(gone)} junctions", f"{len(st['net']['nodes'])} junctions, "
                                                   f"{len(st['net']['conduits'])} pipes left")
    store(st)
    return len(gone)


def auto_repair(st, join_gap_m=1.0, tjoint_m=0.5, loops=False, gl=True, merge=True):
    """repair.repair on the working network (one undo step); every repair is logged. Returns the repair rows.
    merge (user request 21-Oct-2026): then the junctions on the same spot with no pipe between them (red crosses) are
    merged - a water main network keeps its loops, so a loop cut head of an earlier repair goes back too."""
    _snapshot(st)
    net, rows = repair.repair(_tuples(st["net"]), {"problems": st["ex_problems"]}, st["net"]["outfalls"],
                              join_gap_m=join_gap_m, tjoint_m=tjoint_m, loops=loops, gl=gl)
    nj = _net_json(net)
    for k in nj["conduits"]:
        if "id" not in k:
            k["id"] = st["next_id"]
            st["next_id"] += 1
    st["net"] = nj
    for r in rows:
        _log(st, "auto: " + r["repair"], r["item"], str(r.get("detail") or ""))
    if merge:
        tn, tc = set(), set()
        for keep, drop, d in merge_pairs(st["net"]):
            _apply1(st, {"op": "merge", "keep": keep, "drop": drop}, tn, tc)       # logged as "manholes merged"
            rows.append({"repair": MERGED, "item": f"{drop} -> {keep}", "detail": f"{d:.2f} m apart"})
    store(st)
    return rows


def save_network(st):
    """The corrected network as CSV (manholes / conduits, as dxf_extract writes them - for zoning / design and
    --csv) and the list of the changes made (<stem>_network_edits.csv). Returns the paths."""
    import csv
    from water_app.core import network
    folder = os.path.join(st["_root"], st["stem"])
    os.makedirs(folder, exist_ok=True)
    paths = {"manholes": os.path.join(folder, f"{st['stem']}_network_manholes.csv"),
             "conduits": os.path.join(folder, f"{st['stem']}_network_conduits.csv"),
             "edits": os.path.join(folder, f"{st['stem']}_network_edits.csv")}
    if st.get("saved_edits") == len(st["edits"]) and all(os.path.isfile(f) for f in paths.values()):
        return dict(paths, unchanged=True)       # nothing changed: the files (and the zoning made from them) stay
    net = _tuples(st["net"])
    f_mh, f_co = network.write_csv(net, os.path.join(folder, f"{st['stem']}_network_manholes.csv"),
                                   os.path.join(folder, f"{st['stem']}_network_conduits.csv"))
    f_ed = os.path.join(folder, f"{st['stem']}_network_edits.csv")
    with open(f_ed, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Time", "Change", "Item", "Detail"])
        for e in st["edits"]:
            w.writerow([e["time"], e["change"], e["item"], e["detail"]])
    out = {"manholes": f_mh, "conduits": f_co, "edits": f_ed}
    # the drawing's names beside the app's (renumber, 17-Nov-2026): the drawing can still be read by them
    olds = [("junction", n, v["old"]) for n, v in st["net"]["nodes"].items() if v.get("old") and v["old"] != n] + \
           [("pipe", k["label"], k["old"]) for k in st["net"]["conduits"] if k.get("old") and k["old"] != k["label"]]
    if olds:
        f_old = os.path.join(folder, f"{st['stem']}_network_old_names.csv")
        with open(f_old, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["Kind", "Name", "Old name (drawing)"])
            w.writerows(olds)
        out["old_names"] = f_old
    st["saved"] = time.strftime("%d-%m-%Y %H:%M")
    st["saved_edits"] = len(st["edits"])          # changes after this: the CSV files are older than the network
    store(st)
    return out
