"""netedit: the app's own names - junctions and pipes numbered from the tanks."""
import collections
import math
import re
from .edits import _log, _snapshot
from .files import store
from .problems import _key


MERGED = "junctions on the same spot merged"


def renumber_order(net, seeds):
    """The order of new names (user request 17-Nov-2026: "नई टंकी से शुरू"): for each zone in turn - seeds [(tank's
    junction, pipe labels of its zone)] - out from the tank along the zone's pipes, the straightest way on first, so
    the numbers run along a line; then the junctions no zone reached, top to bottom and left to right. Returns
    (junctions in order, pipe labels in order): a pipe in the order it was first walked, the rest (loops) by the
    places of their two ends."""
    nodes, conds = net["nodes"], net["conduits"]
    xy = {n: v.get("xy") for n, v in nodes.items()}
    rank, order, porder, pseen = {}, [], [], set()

    def num(n):
        if n not in rank:
            rank[n] = len(order)
            order.append(n)

    for root, labels in seeds:
        if root not in nodes:
            continue
        labels = set(labels)
        adj = collections.defaultdict(list)
        for k in conds:
            if k["label"] in labels:
                adj[k["start_node"]].append((k["stop_node"], k["label"]))
                adj[k["stop_node"]].append((k["start_node"], k["label"]))
        num(root)
        stack = [(root, None)]
        while stack:
            u, came = stack.pop()
            nxt = []
            for v, lab in adj[u]:
                if v in rank or lab in pseen:
                    continue
                turn = 0.0
                if came is not None and xy.get(came) and xy.get(u) and xy.get(v):
                    a = math.atan2(xy[u][1] - xy[came][1], xy[u][0] - xy[came][0])
                    b = math.atan2(xy[v][1] - xy[u][1], xy[v][0] - xy[u][0])
                    turn = abs((b - a + math.pi) % (2 * math.pi) - math.pi)
                nxt.append((turn, v, lab))
            for turn, v, lab in sorted(nxt):                     # the straightest way on first
                stack.append((u, came))                          # come back to u for its other branches
                stack.append((v, u))
                if v not in rank:
                    num(v)
                    pseen.add(lab)
                    porder.append(lab)
                break
    rest = sorted((n for n in nodes if n not in rank),
                  key=lambda n: (-(xy[n][1] if xy.get(n) else 0), xy[n][0] if xy.get(n) else 0, n))
    for n in rest:
        num(n)
    left = [k for k in conds if k["label"] not in pseen]
    left.sort(key=lambda k: tuple(sorted((rank.get(k["start_node"], 1e9), rank.get(k["stop_node"], 1e9)))))
    porder += [k["label"] for k in left]
    return order, porder


def _rename_all(st, nmap, pmap, tn, tc):
    """Junctions (nmap old -> new) and pipes (pmap) renamed everywhere in the working state: the network, its
    outfalls, the drawing's problems and the ones marked as checked."""
    net = st["net"]
    if nmap:
        net["nodes"] = {nmap.get(n, n): v for n, v in net["nodes"].items()}
        for k in net["conduits"]:
            k["start_node"], k["stop_node"] = nmap.get(k["start_node"], k["start_node"]), nmap.get(k["stop_node"], k["stop_node"])
        net["outfalls"] = [nmap.get(o, o) for o in net["outfalls"]]
        tn.update(nmap)
        tn.update(nmap.values())
        tc.update(k["id"] for k in net["conduits"])
    if pmap:
        for k in net["conduits"]:
            if k["label"] in pmap:
                k["label"] = pmap[k["label"]]
                tc.add(k["id"])
    ren = {**nmap, **pmap}
    ks = {}
    for i in st["ex_issues"]:
        parts = [x.strip() for x in str(i["item"]).split(" - ")]
        item = " - ".join(ren.get(x, x) for x in parts)
        if item != str(i["item"]):
            ks[_key(i)] = f"{i['type']}|{item}"
            i["item"] = item
    st["reviewed"] = [ks.get(r, r) for r in st["reviewed"]]


def renumber(st, seeds, node_prefix="J-", pipe_prefix="P-", pipes=True):
    """Every junction (and pipe) named afresh - <prefix>1, 2, 3 ... in renumber_order (user request 17-Nov-2026: the
    app's own names in place of the drawing's, starting at the new tank). The first name each had (the drawing's)
    is kept with it ("old") and shown on the map. One undo step, logged. Returns ({old: new} junctions, pipes)."""
    for p in (node_prefix, pipe_prefix):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_/-]{0,7}", p or ""):
            raise ValueError(f"prefix '{p}' नहीं चलेगा: अक्षर से शुरू, 8 तक अक्षर / अंक / - _ /")
    _snapshot(st)
    net = st["net"]
    order, porder = renumber_order(net, seeds)
    nmap = {n: f"{node_prefix}{i}" for i, n in enumerate(order, start=1)}
    pmap = {lab: f"{pipe_prefix}{i}" for i, lab in enumerate(porder, start=1)} if pipes else {}
    for n, v in net["nodes"].items():
        v.setdefault("old", n)
    for k in net["conduits"]:
        k.setdefault("old", k["label"])
    tn, tc = set(), set()
    _rename_all(st, {a: b for a, b in nmap.items() if a != b}, {a: b for a, b in pmap.items() if a != b}, tn, tc)
    pre = dict(st.get("prefix") or {})
    for what, new in (("node", node_prefix), ("pipe", pipe_prefix if pipes else None)):
        if new is None:
            continue
        if new == {"node": "J-", "pipe": "P-"}[what]:
            pre.pop(what, None)
        else:
            pre[what] = new
    st["prefix"] = pre
    seeded = sum(1 for r, _ in seeds if r in nmap)
    _log(st, "new names", f"{node_prefix}1 ... {node_prefix}{len(order)}" + (f", {pipe_prefix}1 ... {pipe_prefix}{len(porder)}" if pipes else ""),
         f"from {seeded} tank(s) along the pipes; the old names kept")
    store(st)
    return nmap, pmap
