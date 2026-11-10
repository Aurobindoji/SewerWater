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
"""
import collections
import json
import math
import os

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


def check(net, res, crit, fixed=None):
    """Failing junctions (residual head) and pipes (velocity); notes for low velocity / high pressure."""
    rh, vmax, vmin = _val(crit, "residual_head_m"), _val(crit, "max_velocity_mps"), _val(crit, "min_velocity_mps")
    if fixed is None:
        fixed = {n for n, v in net["nodes"].items() if v.get("head") is not None}
    low = {n: p for n, p in res["pressure"].items() if n not in fixed and p < rh - 1e-6}
    fast = {p: v for p, v in res["velocity"].items() if v > vmax + 1e-9}
    slow = {p: v for p, v in res["velocity"].items() if 1e-9 < v < vmin}
    high = {n: p for n, p in res["pressure"].items() if n not in fixed and p > _val(crit, "residual_head_max_m") + 10}
    return low, fast, slow, high


def _path_pipe(net, res, start, adj, fixed=None):
    """From a low junction back towards the source, always to the neighbour with the higher head: (the pipe with the
    steepest head loss on that path that can still grow, the head of the source reached or None)."""
    best, bg, cur, seen = None, -1.0, start, {start}
    fixed = fixed if fixed is not None else {n for n, v in net["nodes"].items() if v.get("head") is not None}
    while cur not in fixed:
        up = [(res["head"].get(o, -1e9), pid, o) for pid, o in adj[cur] if o not in seen]
        if not up:
            break
        h, pid, o = max(up)
        if h <= res["head"][cur]:
            break
        if not net["pipes"][pid].get("fixed") and res["hl_per_km"][pid] > bg:
            best, bg = pid, res["hl_per_km"][pid]
        seen.add(o)
        cur = o
    return best, (cur if cur in fixed else None)


def _path_table(net, res, adj, fixed):
    """For every junction at once (what _path_pipe gives for one): following the neighbour with the higher head back
    to the source, (the steepest pipe on that way, the source reached or None) - nodes taken from the highest head
    down, each from its upstream neighbour's entry."""
    head = res["head"]
    hl = res["hl_per_km"]
    pipes = net["pipes"]
    out = {}
    for n in sorted(head, key=head.get, reverse=True):
        if n in fixed:
            out[n] = (None, n)
            continue
        best = None
        for pid, o in adj[n]:
            h = head.get(o)
            if h is not None and h > head[n] and (best is None or h > best[0]):
                best = (h, pid, o)
        if best is None:
            out[n] = (None, None)
            continue
        _, pid, o = best
        bp, src = out.get(o, (None, None))
        cand = pid if not pipes[pid].get("fixed") else None
        if bp is not None and (cand is None or hl[bp] >= hl[cand]):
            cand = bp
        out[n] = (cand, src)
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


def design(net, crit=None, pipes=None, economise=True, max_rounds=400, log=None, economise_seconds=120):
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

    model = hy.Model(net, minor_loss=minor, demand_factor=pf)        # built once; the sizes change in it

    def run(prev=None):
        return model.solve()                                          # from the last flows

    def set_size(pid, i):
        size[pid] = i
        net["pipes"][pid]["d_mm"], net["pipes"][pid]["C"] = cat[i]["id_mm"], cat[i]["C"]
        model.set_pipe(pid, cat[i]["id_mm"], cat[i]["C"])

    res = run()
    rounds, stuck, hopeless = 0, None, set()
    while rounds < max_rounds:
        rounds += 1
        low, fast, _, _ = check(net, res, crit, fixed_nodes)
        work = {n: p for n, p in low.items() if n not in hopeless}
        if not work and not fast:
            break
        grow = {pid for pid in fast if pid in size and size[pid] + 1 < len(cat)}     # too fast: one size up
        # junctions below the residual head: for the PER_SOURCE weakest of each source (OHT), the steepest pipe on
        # the way back to it one size up - all sources in the same round; a junction whose source is too low (static
        # head short) or whose whole way is at the largest size is set aside (no pipe helps: the OHT's staging is
        # reported short)
        done = collections.Counter()
        table = _path_table(net, res, adj, fixed_nodes) if work else {}
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
        if not grow:
            break
        for pid in grow:
            set_size(pid, size[pid] + 1)
        res = run(res)
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

        def ok(r):
            l2, f2, _, _ = check(net, r, crit, fixed_nodes)
            return not f2 and all(n in base_low and r["pressure"].get(n, -1e9) >= base_low[n] - 1e-3 for n in l2)
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
    vn = crit["min_velocity_mps"]
    checks.append({"check": f"velocity >= {vn['value']} m/s (flushing below)", "ref": vn["ref"], "ok": True, "note": True,
                   "detail": f"{len(slow)} pipes slower (mostly at the minimum diameter - scour valves)"})
    if high:
        checks.append({"check": f"residual head well above {crit['residual_head_max_m']['value']} m",
                       "ref": crit["residual_head_max_m"]["ref"], "ok": True, "note": True,
                       "detail": f"{len(high)} junctions above {crit['residual_head_max_m']['value'] + 10:g} m - consider PRV / smaller staging"})
    if res["unsupplied"]:
        checks.append({"check": "every junction connected to an OHT", "ref": "-", "ok": False,
                       "detail": f"{len(res['unsupplied'])} junctions without a path to an OHT"})
    return {"size": {p: cat[i] for p, i in size.items()}, "result": res, "checks": checks,
            "low": low, "fast": fast, "slow": slow, "missing_head_m": missing, "stuck_at": stuck,
            "hopeless": sorted(hopeless & set(low), key=str),
            "summary": {"pipes": len(net["pipes"]), "junctions": len(pr),
                        "min_pressure": round(min(pr), 2) if pr else None,
                        "max_pressure": round(max(pr), 2) if pr else None,
                        "length_by_size": {k: round(v, 1) for k, v in sorted(by_size.items(), key=lambda kv: kv[0])},
                        "peak_factor": pf, "rounds": rounds}}
