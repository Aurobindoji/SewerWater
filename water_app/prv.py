"""Pressure reducing valves (PRV) of the water design (user request 30-Oct-2026: Prop-OHT-8 of network_utm had 154
junctions above 31 m on ground 13 m lower than its OZ's top - no pipe size helps, the pipes there are the minimum
HDPE 110 already and the flow is a few L/s).

A PRV is placed on the map and sits on the pipe nearest to it (within SNAP_M). The area it serves - the junctions
downstream of it - is what the OHTs reach only through that pipe (a bridge of the open network): its flows are set by
its own demand, so a PRV holding the head at the pipe's downstream junction lowers the head of the whole area by the
same amount and leaves the rest of the network as it was (exact for a bridge - no change to the solver). A PRV on a
pipe of a loop (the area fed by other pipes too) does nothing: reported, not applied.

Setting (user decision 30-Oct-2026): by itself the lowest that keeps 17 m at every junction of its area at the design
peak (+30 years), rounded up to 0.5 m - or the one given on the map. The same head is held at every stage.

Suggestions (user: the design suggests, the user places): where junctions are above 31 m (residual_head_max_m + 10,
the design's "consider PRV" note), greedily the bridge whose PRV brings the most of them to 31 m or less, again until
none does."""
import math

SNAP_M = 30.0          # a PRV on the map sits on a pipe within this
MAX_SUGGEST = 12       # suggestions at most
MIN_GAIN = 5           # a PRV is suggested for this many junctions above 31 m at least (not one per dead end)
ROOT = "\0root"


def _seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if not L2 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def snap(prvs, geo, to_xy, max_m=SNAP_M):
    """[(prv, pipe label or None, distance m)]: each PRV of the page ({name, lat, lng, setting_m}) on the pipe nearest
    to it (geo: label -> polyline in metres) - a suggested one is placed half way along its pipe."""
    out = []
    for p in prvs or []:
        try:
            xy = to_xy([[float(p["lat"]), float(p["lng"])]])[0]
        except (KeyError, TypeError, ValueError):
            out.append((p, None, None))
            continue
        best = min(((min(_seg(xy, a, b) for a, b in zip(pts, pts[1:])), lab) for lab, pts in geo.items() if len(pts) > 1),
                   default=(math.inf, None))
        out.append((p, best[1], round(best[0], 1)) if best[0] <= max_m else (p, None, round(best[0], 1)))
    return out


class Tree:
    """The open network (closed pipes left out) from the OHTs: a DFS from a root joined to every source, its bridges
    (a pipe the area beyond it is reached through only) and each node's place in the DFS order - the area beyond a
    bridge (u, v) is order[tin[v]:tout[v]]."""

    def __init__(self, hnet):
        adj = {}
        for lab, p in hnet["pipes"].items():
            if p.get("closed"):
                continue
            adj.setdefault(p["a"], []).append((p["b"], lab))
            adj.setdefault(p["b"], []).append((p["a"], lab))
        src = [n for n, v in hnet["nodes"].items() if v.get("head") is not None]
        adj[ROOT] = [(s, f"{ROOT}{s}") for s in src]
        self.tin, self.tout, self.low, self.order, self.parent = {}, {}, {}, [], {}
        t = 0
        self.tin[ROOT] = self.low[ROOT] = t
        st = [(ROOT, None, iter(adj[ROOT]))]
        while st:
            u, pe, it = st[-1]
            nxt = next(it, None)
            if nxt is None:
                st.pop()
                self.tout[u] = len(self.order)
                if st:
                    w = st[-1][0]
                    self.low[w] = min(self.low[w], self.low[u])
                continue
            v, lab = nxt
            if lab == pe:
                continue
            if v in self.tin:
                self.low[u] = min(self.low[u], self.tin[v])
                continue
            t += 1
            self.tin[v] = self.low[v] = t
            self.parent[v] = (u, lab)
            self.order.append(v)
            st.append((v, lab, iter(adj.get(v, ()))))
        self.pos = {n: i for i, n in enumerate(self.order)}       # tin is 1 + pos for every node but the root
        self.bridge = {lab: v for v, (u, lab) in self.parent.items() if u != ROOT and self.low[v] > self.tin[u]}

    def area(self, v):
        return self.order[self.pos[v]:self.tout[v]]


def _setting(p_down, p_min, rh):
    """The lowest PRV setting (residual head at its downstream junction) keeping rh in its area, up to 0.5 m."""
    return math.ceil((p_down - (p_min - rh)) * 2 - 1e-6) / 2


def apply(hnet, res, placed, crit, tree=None):
    """The PRVs placed (snap()) on the designed network: res (hydraulics.solve) shifted in their areas. Returns the
    rows for the page / DPR, upstream PRVs first; each active one keeps 'area' and 'h_set' for shift()."""
    rh = crit["residual_head_m"]["value"]
    tree = tree or Tree(hnet)
    rows = []
    for p, lab, dist in placed:
        row = {"name": str(p.get("name") or "PRV"), "pipe": lab, "snap_m": dist, "active": False,
               "auto": str(p.get("setting_m") or "").strip() == "", "given_m": p.get("setting_m")}
        rows.append(row)
        if lab is None:
            row["note"] = f"no pipe within {SNAP_M:g} m" + (f" (nearest {dist:g} m)" if dist not in (None, math.inf) else "")
            continue
        v = tree.bridge.get(lab)
        if v is None:
            row["note"] = ("a closed pipe (OZ / DMA boundary valve)" if hnet["pipes"].get(lab, {}).get("closed") else
                           "the area beyond is fed by other pipes too (a loop) - no effect; close them or add PRVs there")
            continue
        u = tree.parent[v][0]
        row.update(up=u, down=v, _tin=tree.tin[v])
    for row in sorted((r for r in rows if "down" in r), key=lambda r: r["_tin"]):
        v = row["down"]
        area = [n for n in tree.area(v) if n in res["pressure"]]
        pd = res["pressure"].get(v)
        if not area or pd is None:
            row["note"] = "no junction beyond it"
            continue
        pmin = min(res["pressure"][n] for n in area)
        try:
            p_set = float(row["given_m"]) if not row["auto"] else _setting(pd, pmin, rh)
        except (TypeError, ValueError):
            p_set, row["auto"] = _setting(pd, pmin, rh), True
        cut = pd - p_set
        before = max(res["pressure"][n] for n in area)
        row.update(nodes=len(area), setting_m=p_set, upstream_m=round(res["pressure"].get(row["up"], pd), 2),
                   max_before=round(before, 2))
        if cut <= 0.05:
            row["note"] = (f"not needed - its area's weakest junction has {pmin:.2f} m" if row["auto"] else
                           f"inactive - {pd:.2f} m reaches it, less than its setting")
            continue
        for n in area:
            res["pressure"][n] -= cut
            res["head"][n] -= cut
        low = sum(1 for n in area if res["pressure"][n] < rh - 1e-6)
        row.update(active=True, cut_m=round(cut, 2), h_set=hnet["nodes"][v]["elev"] + p_set, area=area,
                   min_after=round(min(res["pressure"][n] for n in area), 2),
                   max_after=round(max(res["pressure"][n] for n in area), 2), low=low)
        if low:
            row["note"] = f"its setting leaves {low} junctions below {rh:g} m"
    for r in rows:
        r.pop("_tin", None)
    return rows


def shift(res, rows):
    """A stage's solution with the PRVs holding their heads (rows: apply(), upstream first)."""
    for r in rows:
        if not r.get("active"):
            continue
        h = res["head"].get(r["down"])
        cut = (h - r["h_set"]) if h is not None else 0.0
        if cut <= 0:
            continue
        for n in r["area"]:
            if n in res["pressure"]:
                res["pressure"][n] -= cut
                res["head"][n] -= cut


def suggest(hnet, res, crit, taken=(), tree=None, limit=MAX_SUGGEST, min_gain=MIN_GAIN):
    """Pipes for a PRV where junctions are above residual_head_max_m + 10 (31 m): greedily the bridge bringing the
    most of them to 31 m or less (ties: the larger cut, then the smaller area), each with its setting by itself, while
    one brings min_gain of them down at least. res is not changed.
    ([{pipe, down, nodes, setting_m, cut_m, high_before, high_after, max_after}], junctions above 31 m left)"""
    rh = crit["residual_head_m"]["value"]
    top = crit["residual_head_max_m"]["value"] + 10
    tree = tree or Tree(hnet)
    p = {n: x for n, x in res["pressure"].items() if n in tree.pos and hnet["nodes"][n].get("head") is None}
    out, taken = [], set(taken)
    while len(out) < limit:
        high = [n for n, x in p.items() if x > top + 1e-6]
        if not high:
            break
        cand = {}
        for n in high:                                 # the bridges above a high junction
            v = n
            while v in tree.parent and tree.parent[v][0] != ROOT:
                lab = tree.parent[v][1]
                if tree.bridge.get(lab) == v and lab not in taken:
                    cand[lab] = v
                v = tree.parent[v][0]
        best = None
        for lab, v in cand.items():
            if v not in p:
                continue
            area = [n for n in tree.area(v) if n in p]
            pmin = min(p[n] for n in area)
            cut = p[v] - _setting(p[v], pmin, rh)
            if cut < 0.5:
                continue
            hb = sum(1 for n in area if p[n] > top + 1e-6)
            ha = sum(1 for n in area if p[n] - cut > top + 1e-6)
            key = (hb - ha, cut, -len(area))
            if hb - ha >= min_gain and (best is None or key > best[0]):
                best = (key, lab, v, area, cut, hb, ha)
        if best is None:
            break
        _, lab, v, area, cut, hb, ha = best
        for n in area:
            p[n] -= cut
        taken.add(lab)
        out.append({"pipe": lab, "down": v, "nodes": len(area), "setting_m": round(p[v], 2), "cut_m": round(cut, 2),
                    "high_before": hb, "high_after": ha, "max_after": round(max(p[n] for n in area), 2)})
    return out, sum(1 for x in p.values() if x > top + 1e-6)
