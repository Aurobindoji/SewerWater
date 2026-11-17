"""Pipe sizes of a water distribution network to CPHEEO (criteria.json), with the app's own solver (hydraulics.py).

    res = design(net)              net as for hydraulics.solve; nodal "demand" = AVERAGE demand (L/s)
    res["size"][pipe] -> catalogue entry, res["result"] = hydraulics at peak, res["checks"], res["summary"]

1. All the pipes to be designed start at the smallest catalogue size (CPHEEO minimum 100 mm, Table 2.7 S.No.8).
2. The network is run at the PEAK demand = average x peak factor 2.5 (Table 2.7 S.No.7(b) p172).
3. UPSIZE until everything passes: a pipe faster than 3 m/s (6.6(ii) p400) goes one size up; while a junction has
   less than the residual head 17 m (Table 2.7 S.No.10 p173), the path from it back to the source is followed
   (always to the neighbour with the higher head) and the pipe on it with the steepest head loss goes one size up.
4. ECONOMISE (economise=True): each pipe, the slowest first, is tried one size down and kept there only if every
   check still passes - pipe cost saved.
If the source itself is too low (staging), no pipe size helps: the design stops and says how much head is missing.
A pipe with "fixed": True (an existing pipe to be kept) is never resized.

Constraints of the page (user request 16-Nov-2026), each only when given:
    pipes            the catalogue the design may use (allowed_pipes: smallest / largest nominal, HDPE up to a size)
    crit "max_hl_distribution_m_per_km"   a pipe with a steeper head loss at the peak goes one size up, as a fast one
    crit "max_pressure_m"                 the junctions above it reported (instead of residual_head_max + 10)
    cases            other loads the design must also pass: [{"name", "factor" (x the AVERAGE), "extra": {node: L/s},
                     "min_head": m}] - each solved with the same sizes; a junction below its min_head there gets the
                     pipes on its way back to the source upsized, as at the peak; economising keeps them passing.
"""
import collections
import json
import math
import os

import numpy as np

from . import hydraulics as hy

HERE = os.path.dirname(os.path.abspath(__file__))
PER_SOURCE = 8              # upsizing: the weakest junctions of each OHT whose path gets a bigger pipe in one round


def load_criteria(path=None):
    with open(path or os.path.join(HERE, "criteria.json"), encoding="utf-8") as fh:
        return {k: v for k, v in json.load(fh).items() if not k.startswith("_")}


def load_pipes(path=None):
    with open(path or os.path.join(HERE, "pipes.json"), encoding="utf-8") as fh:
        return json.load(fh)["sizes"]


def _val(crit, key):
    return crit[key]["value"]


def _where(d, test):
    """The items of a {key: float} dict whose value passes test (on a numpy array) - in the dict's order, the values as
    they are (17-Nov-2026: the dict comprehensions of check() were a tenth of a large design's time)."""
    vals = np.fromiter(d.values(), dtype=float, count=len(d))
    keys = list(d)
    return {keys[i]: d[keys[i]] for i in np.flatnonzero(test(vals)).tolist()}


def check(net, res, crit, fixed=None):
    """Failing junctions (residual head) and pipes (velocity); notes for low velocity / high pressure."""
    rh, vmax, vmin = _val(crit, "residual_head_m"), _val(crit, "max_velocity_mps"), _val(crit, "min_velocity_mps")
    if fixed is None:
        fixed = {n for n, v in net["nodes"].items() if v.get("head") is not None}
    pres, vel = res["pressure"], res["velocity"]
    low = {n: p for n, p in _where(pres, lambda a: a < rh - 1e-6).items() if n not in fixed}
    fast = _where(vel, lambda a: a > vmax + 1e-9)
    if "max_hl_distribution_m_per_km" in crit:            # too steep: one size up, as too fast (a constraint)
        g = _val(crit, "max_hl_distribution_m_per_km")
        fast.update({p: vel[p] for p in _where(res["hl_per_km"], lambda a: a > g + 1e-9) if p not in fast})
    slow = _where(vel, lambda a: (a > 1e-9) & (a < vmin))
    top = high_limit(crit)
    high = {n: p for n, p in _where(pres, lambda a: a > top).items() if n not in fixed}
    return low, fast, slow, high


def high_limit(crit):
    """The residual head above which a junction is reported (and a PRV suggested): the page's maximum pressure, else
    residual_head_max + 10 (31 m)."""
    if "max_pressure_m" in crit:
        return _val(crit, "max_pressure_m")
    return _val(crit, "residual_head_max_m") + 10


def allowed_pipes(crit, cat=None):
    """The catalogue within the page's size limits (crit "pipe_sizes": {dmin, dmax, hdpe_max} nominal mm, each
    optional): HDPE only up to hdpe_max, the rest of the sizes as they are. Never empty: the smallest left."""
    cat = cat or load_pipes()
    lim = (crit.get("pipe_sizes") or {}).get("value") or {}
    out = [s for s in cat
           if (lim.get("dmin") is None or s["nominal"] >= lim["dmin"]) and (lim.get("dmax") is None or s["nominal"] <= lim["dmax"])
           and not (lim.get("hdpe_max") is not None and "HDPE" in s["name"].upper() and s["nominal"] > lim["hdpe_max"])]
    return out or cat[-1:]


class _Paths:
    """The upstream path table of the upsizing rounds, with numpy (17-Nov-2026: the Python loop was a fifth of a
    12,000-junction design): the network's arrays built once, then per result each junction's upstream neighbour (the highest head above its own, the first
    in adj on a tie) and, by pointer doubling up those links, the steepest growable pipe on the way (the upstream one
    on a tie) and the source reached - the same answer as the plain loop in tests/test_water_paths.py."""

    def __init__(self, net, adj, fixed):
        self.ids = list(adj)
        self.ix = ix = {n: i for i, n in enumerate(self.ids)}
        self.pids = list(net["pipes"])
        px = {p: i for i, p in enumerate(self.pids)}
        en, eo, ep = [], [], []
        for n, lst in adj.items():
            for pid, o in lst:
                en.append(ix[n])
                eo.append(ix[o])
                ep.append(px[pid])
        self.en, self.eo, self.ep = (np.array(v, dtype=np.int64) for v in (en, eo, ep))
        self.isfixed = np.array([n in fixed for n in self.ids], dtype=bool)
        self.nans = [np.nan] * len(self.ids)
        self.growable = np.array([not net["pipes"][p].get("fixed") for p in self.pids], dtype=bool)

    def table(self, res, want):
        head, hl = res["head"], res["hl_per_km"]
        nn = len(self.ids)
        hn = np.fromiter(map(head.get, self.ids, self.nans), dtype=float, count=nn)
        hlp = np.fromiter(map(hl.__getitem__, self.pids), dtype=float, count=len(self.pids))
        hlo, hhi = hn[self.en], hn[self.eo]
        ok = (hhi > hlo) & ~self.isfixed[self.en]             # NaN compares False: no head, no link
        e = np.flatnonzero(ok)
        order = e[np.lexsort((-hhi[e], self.en[e]))]          # by junction, then highest head; stable: adj order
        first = order[np.r_[True, self.en[order][1:] != self.en[order][:-1]]] if len(order) else order
        anc = np.arange(nn)
        bp = np.full(nn, -1, dtype=np.int64)
        bv = np.full(nn, -np.inf)
        own = self.en[first]
        anc[own] = self.eo[first]
        g = self.growable[self.ep[first]]
        bp[own[g]] = self.ep[first][g]
        bv[own[g]] = hlp[self.ep[first][g]]
        while True:                                           # each node's segment doubles towards its root
            up = anc[anc]
            if np.array_equal(up, anc):
                break
            ubp, ubv = bp[anc], bv[anc]
            take = (ubp >= 0) & ((bp < 0) | (ubv >= bv))
            bp = np.where(take, ubp, bp)
            bv = np.where(take, ubv, bv)
            anc = up
        out = {}
        for n in want:
            i = self.ix.get(n)
            if i is not None and n in head:
                out[n] = (self.pids[bp[i]] if bp[i] >= 0 else None, self.ids[anc[i]] if self.isfixed[anc[i]] else None)
        return out


def _down_min(net, res, adj, fixed):
    """For every junction the lowest residual head of the junctions fed through it (each junction hangs from its
    neighbour with the highest head) - the head a pipe into it may still lose."""
    head, pr = res["head"], res["pressure"]
    up = {}
    for n in head:
        if n in fixed:
            continue
        best = None
        for pid, o in adj[n]:
            h = head.get(o)
            if h is not None and h > head[n] and (best is None or h > best[0]):
                best = (h, o)
        if best is not None:
            up[n] = best[1]
    low = {n: pr.get(n, math.inf) for n in head if n not in fixed}
    for n in sorted(up, key=head.get):                   # from the lowest head up: children before parents
        o = up[n]
        if o in low and low[n] < low[o]:
            low[o] = low[n]
    return low


def design(net, crit=None, pipes=None, economise=True, max_rounds=400, log=None, economise_seconds=120, cases=None):
    crit = crit or load_criteria()
    cat = pipes or load_pipes()
    say = log or (lambda *_: None)
    minor, pf = _val(crit, "minor_loss_factor"), _val(crit, "peak_factor")
    dmin = _val(crit, "min_diameter_mm")
    first = next((i for i, s in enumerate(cat) if s["nominal"] >= dmin), 0)
    size = {}
    for pid, p in net["pipes"].items():
        if p.get("fixed"):
            continue
        size[pid] = first
        p["d_mm"], p["C"] = cat[first]["id_mm"], cat[first]["C"]
    adj = {n: [] for n in net["nodes"]}
    for pid, p in net["pipes"].items():
        if not p.get("closed"):
            adj[p["a"]].append((pid, p["b"]))
            adj[p["b"]].append((pid, p["a"]))

    fixed_nodes = {n for n, v in net["nodes"].items() if v.get("head") is not None}
    rh = _val(crit, "residual_head_m")
    paths = _Paths(net, adj, fixed_nodes)

    model = hy.Model(net, minor_loss=minor, demand_factor=pf)        # built once; the sizes change in it
    cases = list(cases or [])
    cmodels = []                                                      # the other loads: their own models, same sizes
    for c in cases:
        cn = {"nodes": {n: v if v.get("head") is not None else
                        dict(v, demand=(v.get("avg", v.get("demand")) or 0.0) * c.get("factor", 1.0)
                             + (c.get("extra") or {}).get(n, 0.0))
                        for n, v in net["nodes"].items()}, "pipes": net["pipes"]}
        cmodels.append(hy.Model(cn, minor_loss=minor, demand_factor=1.0))

    def run(prev=None):
        return model.solve()                                          # from the last flows

    def run_cases():
        return [m.solve() for m in cmodels]

    def case_low(c, r):
        return {n: p for n, p in r["pressure"].items() if n not in fixed_nodes and p < c["min_head"] - 1e-6}

    def set_size(pid, i):
        size[pid] = i
        net["pipes"][pid]["d_mm"], net["pipes"][pid]["C"] = cat[i]["id_mm"], cat[i]["C"]
        model.set_pipe(pid, cat[i]["id_mm"], cat[i]["C"])
        for m in cmodels:
            m.set_pipe(pid, cat[i]["id_mm"], cat[i]["C"])

    res = run()
    cres = run_cases()
    rounds, stuck, hopeless = 0, None, set()
    chopeless = [set() for _ in cases]
    while rounds < max_rounds:
        rounds += 1
        low, fast, _, _ = check(net, res, crit, fixed_nodes)
        work = {n: p for n, p in low.items() if n not in hopeless}
        cwork = [{n: p for n, p in case_low(c, r).items() if n not in ch} for c, r, ch in zip(cases, cres, chopeless)]
        if not work and not fast and not any(cwork):
            break
        grow = {pid for pid in fast if pid in size and size[pid] + 1 < len(cat)}     # too fast: one size up
        # junctions below the residual head: for the PER_SOURCE weakest of each source (OHT), the steepest pipe on
        # the way back to it one size up - all sources in the same round; a junction whose source is too low (static
        # head short) or whose whole way is at the largest size is set aside (no pipe helps: the OHT's staging is
        # reported short)
        done = collections.Counter()
        table = paths.table(res, work) if work else {}
        for n in sorted(work, key=work.get):
            pid, src = table.get(n, (None, None))
            h0 = net["nodes"][src]["head"] if src is not None else None
            if h0 is not None and h0 - float(net["nodes"][n].get("elev") or 0.0) < rh - 1e-6:
                hopeless.add(n)
                continue
            if pid is None or size.get(pid, len(cat)) + 1 >= len(cat):
                hopeless.add(n)
                continue
            if done[src] >= PER_SOURCE:
                continue
            done[src] += 1
            grow.add(pid)
        # the other loads: their weakest junctions' ways back to the source, in each load's own heads
        for c, r, cw, ch in zip(cases, cres, cwork, chopeless):
            if not cw:
                continue
            done = collections.Counter()
            table = paths.table(r, cw)
            for n in sorted(cw, key=cw.get):
                pid, src = table.get(n, (None, None))
                h0 = net["nodes"][src]["head"] if src is not None else None
                if h0 is not None and h0 - float(net["nodes"][n].get("elev") or 0.0) < c["min_head"] - 1e-6:
                    ch.add(n)
                    continue
                if pid is None or size.get(pid, len(cat)) + 1 >= len(cat):
                    ch.add(n)
                    continue
                if done[src] >= PER_SOURCE:
                    continue
                done[src] += 1
                grow.add(pid)
        if not grow:
            break
        for pid in grow:
            set_size(pid, size[pid] + 1)
        res = run(res)
        cres = run_cases()
    low, fast, slow, high = check(net, res, crit)
    stuck = min(low, key=low.get) if low else None
    say(f"upsize: {rounds} rounds, {len(low)} junctions below {rh} m ({len(hopeless & set(low))} no pipe size helps - "
        f"source too low), {len(fast)} pipes too fast")

    if economise and not fast:
        # one size down where every check still holds - in groups, a group that fails is split in two (and its
        # halves tried), a single pipe that fails keeps its size; junctions already below (no pipe helps them) may
        # not lose head
        import time as _t
        t_end = _t.time() + economise_seconds
        base_low = dict(low)
        cbase = [case_low(c, r) for c, r in zip(cases, cres)]

        def ok(r):
            l2, f2, _, _ = check(net, r, crit, fixed_nodes)
            if f2 or not all(n in base_low and r["pressure"].get(n, -1e9) >= base_low[n] - 1e-3 for n in l2):
                return False
            for c, m, b in zip(cases, cmodels, cbase):             # the other loads: no junction worse off there
                rc = m.solve()
                if not all(n in b and rc["pressure"].get(n, -1e9) >= b[n] - 1e-3 for n in case_low(c, rc)):
                    return False
            return True
        # a pipe whose head loss, one size smaller, would grow by more than the spare head at its downstream end
        # cannot go down (in a branch exactly so, in a loop nearly) - not tried; the others with the most room first
        def slack(pid):
            p, i = net["pipes"][pid], size[pid]
            ratio = (cat[i]["C"] / cat[i - 1]["C"]) ** 1.852 * (cat[i]["id_mm"] / cat[i - 1]["id_mm"]) ** 4.87
            h = res["hl_per_km"][pid] * p["length"] / 1000.0
            down = p["b"] if res["flow"][pid] >= 0 else p["a"]
            if down in fixed_nodes:
                return -1.0
            spare = dmin.get(down, 0.0) - rh
            if down in base_low:
                spare = 0.0
            return spare - h * (ratio - 1) - (0.0 if res["velocity"][pid] * ratio ** 0.5 <= _val(crit, "max_velocity_mps") else 1e9)
        dmin = _down_min(net, res, adj, fixed_nodes)
        cand = {p: slack(p) for p in size if size[p] > first}
        order = sorted((p for p, v in cand.items() if v > 0), key=lambda p: -cand[p])
        kept, stack, timed_out = 0, [order[i:i + 64] for i in range(0, len(order), 64)][::-1], False
        while stack:
            if _t.time() > t_end:
                timed_out = True
                break
            grp = stack.pop()
            for pid in grp:
                set_size(pid, size[pid] - 1)
            r2 = run(res)
            if ok(r2):
                res, kept = r2, kept + len(grp)
                continue
            for pid in grp:
                set_size(pid, size[pid] + 1)
            if len(grp) > 1:
                h = len(grp) // 2
                stack += [grp[h:], grp[:h]]
        res = run(res)
        cres = run_cases()
        low, fast, slow, high = check(net, res, crit)
        say(f"economise: {kept} pipes one size smaller" + (" (time limit reached - the rest kept their size)" if timed_out else ""))

    missing = None
    if low:
        # how much more head the source would need for the weakest junction
        missing = round(max(_val(crit, "residual_head_m") - p for p in low.values()), 2)
    by_size = {}
    for pid, p in net["pipes"].items():
        nm = cat[size[pid]]["name"] if pid in size else f"existing {p['d_mm']:g} mm"
        by_size[nm] = by_size.get(nm, 0.0) + p["length"]
    fixed = {n for n, v in net["nodes"].items() if v.get("head") is not None}
    pr = [p for n, p in res["pressure"].items() if n not in fixed]
    checks = []
    rh = crit["residual_head_m"]
    checks.append({"check": f"residual head >= {rh['value']} m", "ref": rh["ref"],
                   "ok": not low, "detail": f"{len(low)} junctions below" if low else f"lowest {min(pr):.2f} m" if pr else "-"})
    vm = crit["max_velocity_mps"]
    checks.append({"check": f"velocity <= {vm['value']} m/s", "ref": vm["ref"], "ok": not fast,
                   "detail": f"{len(fast)} pipes faster" if fast else f"highest {max(res['velocity'].values() or [0]):.2f} m/s"})
    if "max_hl_distribution_m_per_km" in crit:
        g = crit["max_hl_distribution_m_per_km"]
        steep = [p for p, h in res["hl_per_km"].items() if h > g["value"] + 1e-9]
        checks.append({"check": f"head loss <= {g['value']:g} m/km", "ref": g["ref"], "ok": not steep,
                       "detail": f"{len(steep)} pipes steeper" if steep else
                                 f"steepest {max(res['hl_per_km'].values() or [0]):.2f} m/km"})
    for c, r in zip(cases, cres):
        lc = case_low(c, r)
        pc = [p for n, p in r["pressure"].items() if n not in fixed_nodes]
        checks.append({"check": f"{c['name']}: residual head >= {c['min_head']:g} m (designed for)", "ref": c.get("ref", "-"),
                       "ok": not lc, "detail": f"{len(lc)} junctions below" if lc else f"lowest {min(pc):.2f} m" if pc else "-"})
    vn = crit["min_velocity_mps"]
    checks.append({"check": f"velocity >= {vn['value']} m/s (flushing below)", "ref": vn["ref"], "ok": True, "note": True,
                   "detail": f"{len(slow)} pipes slower (mostly at the minimum diameter - scour valves)"})
    if high and "max_pressure_m" not in crit:            # with a maximum of the page: checked at night (design_run)
        checks.append({"check": f"residual head well above {crit['residual_head_max_m']['value']} m",
                       "ref": crit["residual_head_max_m"]["ref"], "ok": True, "note": True,
                       "detail": f"{len(high)} junctions above {high_limit(crit):g} m - consider PRV / smaller staging"})
    if res["unsupplied"]:
        checks.append({"check": "every junction connected to an OHT", "ref": "-", "ok": False,
                       "detail": f"{len(res['unsupplied'])} junctions without a path to an OHT"})
    return {"size": {p: cat[i] for p, i in size.items()}, "result": res, "checks": checks,
            "low": low, "fast": fast, "slow": slow, "missing_head_m": missing, "stuck_at": stuck,
            "hopeless": sorted(hopeless & set(low), key=str),
            "cases": {c["name"]: {"result": r, "low": case_low(c, r), "min_head": c["min_head"]}
                      for c, r in zip(cases, cres)},
            "summary": {"pipes": len(net["pipes"]), "junctions": len(pr),
                        "min_pressure": round(min(pr), 2) if pr else None,
                        "max_pressure": round(max(pr), 2) if pr else None,
                        "length_by_size": {k: round(v, 1) for k, v in sorted(by_size.items(), key=lambda kv: kv[0])},
                        "peak_factor": pf, "rounds": rounds}}
