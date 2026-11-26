"""netedit: the network's problems (repair.check)."""
import collections
from sewer_app.net import repair
from .common import LOW, SUGGESTED
from .texts import _tuples


# ---------------------------------------------------------------- problems
def _key(i):
    return f"{i['type']}|{i['item']}"


def issues(st):
    """Problems now: [{key, type, item, x, y, detail, reviewed, low}]."""
    net = st["net"]
    nodes = net["nodes"]
    adj = collections.defaultdict(set)
    for k in net["conduits"]:
        adj[k["start_node"]].add(k["stop_node"])
        adj[k["stop_node"]].add(k["start_node"])
    out = []
    for i in st["ex_issues"]:
        parts = [p.strip() for p in str(i["item"]).split(" - ")] if i["type"] == "near-miss gap" else [str(i["item"])]
        if any(p not in nodes for p in parts if _looks_like_node(p, nodes, i)):
            continue                                            # its manhole was deleted / merged / renamed away
        if i["type"] == "near-miss gap" and len(parts) == 2 and _linked(adj, *parts):
            continue                                            # joined (directly or through a new manhole)
        out.append(dict(i))
    out += repair.check(_tuples(net), None, net["outfalls"], gravity=True)
    rev = set(st["reviewed"])
    for i in out:
        i["key"] = _key(i)
        i["reviewed"] = i["key"] in rev
        i["low"] = i["type"] in LOW
        if i.get("x") is None and str(i["item"]) in nodes and nodes[str(i["item"])].get("xy"):
            i["x"], i["y"] = nodes[str(i["item"])]["xy"]
    return out


NODE_ITEM = {"near-miss gap", "label matched in pass 2 - CHECK", "label matched in pass 2 - low risk",
             "GL matched in pass 2 - CHECK", "GL matched in pass 2 - low risk", "no drawing label (name generated)",
             "manhole on a continuous line - check", SUGGESTED}


def _looks_like_node(p, nodes, i):
    """The item of these problems is a manhole label (two for a gap) - a problem whose manhole is gone is dropped."""
    return i["type"] in NODE_ITEM


def _linked(adj, a, b, hops=3):
    """a and b joined by at most `hops` conduits (a gap closed by a sewer, maybe split by a new manhole)."""
    seen, front = {a}, {a}
    for _ in range(hops):
        front = {m for n in front for m in adj[n]} - seen
        if b in front:
            return True
        seen |= front
    return False


def _connected(net, a, b):
    return any({k["start_node"], k["stop_node"]} == {a, b} for k in net["conduits"])
