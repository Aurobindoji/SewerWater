"""Gravity sewer design to CPHEEO rules: diameter, slope and inverts of every conduit, designed from
the heads of sewers down to the outfall (uniform flow, Manning, constant n).

From the original scripts sewer_design.py - the logic is unchanged; only the SewerGEMS-free parts are here:
orient, topo_order, design_conduit, deflection_deg, design_network, plan_for_fixed_outfalls,
pipe_cost, rate_ref, priced_cost, economise_sizes, max_depth, flushing (flush_water, plan_flushing,
slow_length, flushing_totals). sys.exit -> DesignError.

Input shapes (network.design_inputs):
    data   {"conduits": [{"label", "start_node", "stop_node", "length_m", "flow_lps", "n", "to_outfall",
                          "up_invert_m", "dn_invert_m"}]}
    ground {node: ground level m}      xy {node: (x, y)}
Result of design_network: (res, node_inv, node_info)
    res       {conduit: {"size", "D", "n", "up", "dn", "slope", "gov", "dd", "v", "q", "flags", "from", "to",
                         "rev", "length", "g_up", "g_dn", "depth_up", "depth_dn"}}
    node_inv  {node: invert m}
    node_info {node: {"ground", "invert", "depth", "drop", "max_in_drop", "outfall"}}
"""
import collections
import math

from . import DesignError
from .criteria import slope_row, val
from .hydraulics import slope_for_dd, slope_for_velocity, uniform_flow


# ---------------------------------------------------------------- network order
def orient(k):
    """Design direction = towards the outfall (from the topology, 'to_outfall').
    Only for loop edges / unconnected conduits: flow sign, then existing inverts."""
    t = k.get("to_outfall")
    if t is not None:
        rev = not t
    else:
        q = k["flow_lps"] or 0.0
        rev = q < 0 or (q == 0 and k.get("up_invert_m") is not None and k.get("dn_invert_m") is not None
                        and k["up_invert_m"] < k["dn_invert_m"])
    return (k["stop_node"], k["start_node"], True) if rev else (k["start_node"], k["stop_node"], False)


def topo_order(conds):
    """Upstream-first order of nodes; error on loops."""
    inc, out, nodes = {}, {}, set()
    for k in conds:
        a, b = k["_from"], k["_to"]
        nodes.update((a, b))
        out.setdefault(a, []).append(k)
        inc.setdefault(b, []).append(k)
    indeg = {n: len(inc.get(n, [])) for n in nodes}
    ready = collections.deque(sorted(n for n in nodes if indeg[n] == 0))
    order = []
    while ready:
        n = ready.popleft()
        order.append(n)
        for k in out.get(n, []):
            indeg[k["_to"]] -= 1
            if indeg[k["_to"]] == 0:
                ready.append(k["_to"])
    if len(order) != len(nodes):
        loop = sorted(n for n in nodes if indeg[n] > 0)
        raise DesignError(f"Network has a loop (or flow-direction conflict) at: {', '.join(loop[:20])}. "
                          f"A gravity sewer must be a tree - fix the layout or the flow directions.")
    return order, inc, out


# ---------------------------------------------------------------- design
def _given_conduit(k, up_cands, g_dn, R, sizes, n_model, min_d):
    """A conduit whose diameter and / or slope the user set (pipe table of the map page): the given size (nearest
    catalog ID) and slope are used as they are - the slope only steepened where the crown would come within the
    minimum cover of the d/s ground. The rules they break are flagged, not corrected."""
    q, L = abs(k["flow_lps"] or 0.0), k["length_m"] or 0.0
    fD, s_f = k.get("force_D"), k.get("force_slope")
    if not s_f:                                         # only the size given: the usual slope rules for that size
        sz = min(sizes, key=lambda z: abs(z["id_mm"] - float(fD)))
        d = design_conduit(dict(k, force_D=None), up_cands, g_dn, R, [sz], n_model, 0.0)
        if sz["id_mm"] < min_d - 0.5:
            d["flags"].append(f"given {sz['id_mm']:g} mm smaller than {min_d:g} mm (upstream sewer / minimum)")
        d["gov"] = "given diameter; " + d["gov"]
        return d
    flags = []
    if fD:
        sz = min(sizes, key=lambda z: abs(z["id_mm"] - float(fD)))
        if sz["id_mm"] < min_d - 0.5:
            flags.append(f"given {sz['id_mm']:g} mm smaller than {min_d:g} mm (upstream sewer / minimum)")
    else:                                               # only the slope given: the smallest size that carries it
        tried = [z for z in sizes if z["id_mm"] >= min_d - 0.5] or [sizes[-1]]
        sz = next((z for z in tried if slope_for_dd(q, z["id_mm"], z.get("manning_n") or n_model, R.ddmax) <= s_f),
                  tried[-1])
    D, n = sz["id_mm"], sz.get("manning_n") or n_model
    up = up_cands(D)
    s, gov = float(s_f), "given slope"
    s_cov = (up - (g_dn - R.cover - D / 1000.0)) / L if (g_dn is not None and L) else 0.0
    if s_cov > s:
        s, gov = s_cov, "given slope, steepened: pipe crown kept min cover below d/s ground"
    _, s_min = slope_row(R.slopes, D)
    if s_min and s < s_min * (1 - 1e-6):
        flags.append(f"slope 1 in {1 / s:.0f} flatter than Table 3.13 1 in {1 / s_min:.0f} (given)")
    dd, v = uniform_flow(q, D, s, n) if q else (None, None)
    if q and (dd is None or dd > R.ddmax + 1e-6):
        flags.append(f"d/D {'above 1 (surcharged)' if dd is None else f'{dd:.2f}'} > {R.ddmax} (given size / slope)")
    if q and R.vmin and v is not None and v < R.vmin:
        flags.append(f"velocity {v:.2f} < {R.vmin} m/s (given size / slope)")
    if R.vmax and v is not None and v > R.vmax:
        flags.append(f"velocity {v:.2f} > {R.vmax} m/s")
    if not q:
        flags.append("no flow")
    return {"size": sz, "D": D, "n": n, "up": up, "slope": s, "gov": gov, "dn": up - s * L,
            "dd": dd, "v": v, "q": q, "flags": flags}


def design_conduit(k, up_cands, g_dn, R, sizes, n_model, min_d):
    """Pick diameter and slope for one conduit. up_cands(D) -> upstream invert for diameter D. A diameter / slope the
    user gave (k['force_D'], k['force_slope']) is taken as given (_given_conduit)."""
    if k.get("force_D") or k.get("force_slope"):
        return _given_conduit(k, up_cands, g_dn, R, sizes, n_model, min_d)
    q, L = abs(k["flow_lps"] or 0.0), k["length_m"]
    flags = []
    tried = [s for s in sizes if s["id_mm"] >= min_d - 0.5]
    if not tried:
        tried = [sizes[-1]]
        flags.append(f"no catalog size >= {min_d:.0f} mm")
    pick = None
    for sz in tried:
        D = sz["id_mm"]
        n = sz.get("manning_n") or n_model
        up = up_cands(D)
        _, s_min = slope_row(R.slopes, D)
        s_min = s_min or 0.0
        s_cov = (up - (g_dn - R.cover - D / 1000.0)) / L if (g_dn is not None and L) else 0.0
        base = max(s_min, s_cov, 1e-6)
        s_dd = slope_for_dd(q, D, n, R.ddmax)
        if s_dd <= base or sz is tried[-1]:
            pick = (sz, D, n, up, s_min, s_cov, s_dd, base)
            if s_dd > base:
                flags.append(f"largest catalog size needs a steeper slope for d/D <= {R.ddmax}")
            break
    sz, D, n, up, s_min, s_cov, s_dd, base = pick
    L = L or 0.0
    s, gov = base, ("Table 3.13 min slope" if s_min >= s_cov else "ground falls: pipe crown kept min cover below d/s ground")
    if s_dd > s:
        s, gov = s_dd, f"d/D {R.ddmax}"
    dd, v = uniform_flow(q, D, s, n) if q else (None, None)
    if q and R.vmin and (v is None or v < R.vmin):
        # Steepen for self-cleansing velocity only when the velocity is actually REACHABLE within
        # the practical limits (d/s depth to invert <= max_depth_for_velocity_steepening_m and,
        # if set, slope <= max_slope_for_self_cleansing). If not reachable, the slope is NOT
        # steepened part way (that only deepens everything downstream without reaching the
        # velocity) - the base slope is kept and the conduit is flagged for flushing.
        s_v = slope_for_velocity(q, D, n, R.vmin + 0.002)   # small margin so the check is not 0.799
        lims, why = [], []
        if R.s_cap:
            lims.append(R.s_cap); why.append(f"slope 1 in {1 / R.s_cap:.0f}")
        if R.vel_depth and g_dn is not None and L:
            lims.append((up - (g_dn - R.vel_depth)) / L); why.append(f"d/s depth {R.vel_depth} m")
        s_lim = min(lims) if lims else float("inf")
        if s_v is not None and s_v <= s_lim:
            s, gov = max(s, s_v), f"self-cleansing {R.vmin} m/s"
            dd, v = uniform_flow(q, D, s, n)
        else:
            need = f"1 in {1 / s_v:.0f}" if s_v else "not reachable in this size"
            v_txt = f"{v:.2f} m/s" if v is not None else "velocity not computable"
            flags.append(f"self-cleansing velocity not reached: {v_txt} (needs {need}, beyond limit "
                         f"{' / '.join(why) or '-'}) - flushing needed")
    if not q:
        flags.append("no flow - Table 3.13 minimum slope adopted")
    if R.vmax and v is not None and v > R.vmax:
        flags.append(f"velocity {v:.2f} > {R.vmax} m/s")
    return {"size": sz, "D": D, "n": n, "up": up, "slope": s, "gov": gov, "dn": up - s * L,
            "dd": dd, "v": v, "q": q, "flags": flags}


def deflection_deg(xy, a, b, c):
    """Change of direction (degrees) at node b for flow a -> b -> c; None if coordinates missing."""
    if not xy or a not in xy or b not in xy or c not in xy:
        return None
    (x1, y1), (x2, y2), (x3, y3) = xy[a], xy[b], xy[c]
    v1, v2 = (x2 - x1, y2 - y1), (x3 - x2, y3 - y2)
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if not n1 or not n2:
        return None
    cosang = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cosang))


class Plan:
    """Design order of a network: conduits oriented towards the outfall, nodes upstream-first.
    Built once and reused by every redesign of the same network (economise_sizes)."""

    def __init__(self, data):
        conds = [k for k in data["conduits"]]
        for k in conds:
            k["_from"], k["_to"], k["_rev"] = orient(k)
        self.order, self.inc, self.out = topo_order(conds)
        self.pos = {n: i for i, n in enumerate(self.order)}

    def downstream_nodes(self, nd):
        """nd and every node below it, in design (upstream-first) order."""
        seen, stack = {nd}, [nd]
        while stack:
            for k in self.out.get(stack.pop(), []):
                if k["_to"] not in seen:
                    seen.add(k["_to"])
                    stack.append(k["_to"])
        return sorted(seen, key=self.pos.__getitem__)


def _depth_flags(d, R):
    """Depth to invert at both ends of a designed conduit, and the depth flags (CPHEEO p205 / project limit)."""
    d["depth_up"] = d["g_up"] - d["up"] if d["g_up"] is not None else None
    d["depth_dn"] = d["g_dn"] - d["dn"] if d["g_dn"] is not None else None
    if R.max_depth is not None:
        for end, dep in (("u/s", d["depth_up"]), ("d/s", d["depth_dn"])):
            if dep is None or (dep <= R.max_depth and (R.lifts_allowed or R.max_depth_project is None
                                                       or dep <= R.max_depth_project + 1e-9)):
                continue                                 # (a project limit below CPHEEO's is flagged too)
            if R.lifts_allowed:
                d["flags"].append(f"{end} depth {dep:.2f} m > {R.max_depth} m - lift station needed")
            elif dep > R.max_depth_project + 1e-9:
                d["flags"].append(f"{end} depth {dep:.2f} m > project limit {R.max_depth_project:g} m - this part "
                                  f"needs its own zone + pumping station (no lift stations; zoning.py)")
            else:
                d["flags"].append(f"{end} depth {dep:.2f} m > CPHEEO {R.max_depth:g} m (p205) - accepted up to "
                                  f"{R.max_depth_project:g} m (project decision), justify in the DPR")


def _design_node(nd, plan, res, node_inv, node_info, ground, R, sizes, min_d_map, xy, lifts):
    """Design the conduits leaving node nd (their upstream sewers must be in res already) and fill
    node_inv / node_info of nd. res, node_inv, node_info are updated in place."""
    ins = [res[k["label"]] for k in plan.inc.get(nd, [])]
    g_up = ground.get(nd)
    fixed = getattr(R, "fixed_inv", {}).get(nd)          # outgoing invert given by the user (manhole table)
    for k in plan.out.get(nd, []):
        min_d = max([R.dmin] + ([d["D"] for d in ins] if R.no_reduce else [])
                    + [(min_d_map or {}).get(k["label"], 0)])
        need = {}

        def up_cands(D, ins=ins, g_up=g_up, to=k["_to"], nd=nd, need=need):
            """The highest upstream invert the cover / incoming sewers allow for diameter D - or the invert the
            user gave (that limit kept in need['max'] to flag it)."""
            c = []
            if g_up is not None:
                c.append(g_up - R.cover - D / 1000.0)
                if nd in lifts and fixed is None:
                    return c[0]                     # lift station: restart at minimum cover
            for d in ins:
                c.append(d["dn"] + d["D"] / 1000.0 - D / 1000.0)        # crown matching
                if abs(d["D"] - D) < 0.5:
                    # p201: drop (30 mm) where the sewer changes direction without change of
                    # size. Direction from the node coordinates; without coordinates the
                    # drop is given at junctions (2+ incoming sewers) only.
                    ang = deflection_deg(xy, d["from"], nd, to)
                    turned = (ang > R.straight_tol) if ang is not None else (len(ins) > 1)
                    if turned:
                        c.append(d["dn"] - R.drop_same)
            if fixed is not None:
                need["max"] = min(c) if c else None
                return float(fixed)
            if not c:
                raise DesignError(f"Node {nd}: no ground level and no incoming sewer - "
                                  f"cannot fix the upstream invert.")
            return min(c)
        d = design_conduit(k, up_cands, ground.get(k["_to"]), R, sizes, k["n"] or 0.013, min_d)
        if fixed is not None and need.get("max") is not None and float(fixed) > need["max"] + 1e-6:
            d["flags"].append(f"given invert {float(fixed):.3f} m is above {need['max']:.3f} m - the highest the "
                              f"cover / incoming sewers (crown matching) allow")
        d.update({"label": k["label"], "from": nd, "to": k["_to"], "rev": k["_rev"],
                  "length": k["length_m"], "g_up": g_up, "g_dn": ground.get(k["_to"])})
        _depth_flags(d, R)
        res[k["label"]] = d
    outs = [res[k["label"]] for k in plan.out.get(nd, [])]
    inv = min(d["up"] for d in outs) if outs else (min(d["dn"] for d in ins) if ins else None)
    node_inv[nd] = inv
    drops = [(d["label"], d["dn"] - inv) for d in ins if inv is not None]
    big = [(lab, h) for lab, h in drops if R.drop_mh is not None and h > R.drop_mh + 1e-6]
    node_info[nd] = {"ground": g_up, "invert": inv,
                     "depth": (g_up - inv) if (g_up is not None and inv is not None) else None,
                     "drop": "; ".join(f"{lab} drop {h:.2f} m" for lab, h in big),
                     "max_in_drop": max((h for _, h in drops), default=None),
                     "outfall": not outs}


def design_network(data, ground, R, sizes, min_d_map=None, xy=None, lifts=None, plan=None):
    """lifts = set of node labels treated as LIFT STATIONS (option study only): the sewer leaving such
    a node restarts at ground - cover - D, ignoring the levels of the incoming sewers (the sewage
    is pumped up). Everything else as the normal gravity design.
    plan = Plan(data) when the caller already has it (the orientation is the same every time)."""
    lifts = lifts or set()
    plan = plan or Plan(data)
    res, node_inv, node_info = {}, {}, {}
    for nd in plan.order:
        _design_node(nd, plan, res, node_inv, node_info, ground, R, sizes, min_d_map, xy, lifts)
    return res, node_inv, node_info


def redesign_below(start, label, plan, ground, R, sizes, min_d_map, xy=None, lifts=None):
    """The design start = (res, node_inv, node_info) again after min_d_map changed for conduit `label`
    ONLY: the conduit and everything downstream of it are designed again, the rest is kept - a sewer
    depends only on the sewers above it. Same result as design_network(..., min_d_map) for the whole
    network, at a fraction of the work. `start` is not changed (new dicts are returned)."""
    res, node_inv, node_info = dict(start[0]), dict(start[1]), dict(start[2])
    for nd in plan.downstream_nodes(start[0][label]["from"]):
        _design_node(nd, plan, res, node_inv, node_info, ground, R, sizes, min_d_map, xy, lifts or set())
    return res, node_inv, node_info


def plan_for_fixed_outfalls(data, ground, R, sizes, fixed, log, xy=None):
    """Outfall levels cannot change (fixed = {outfall label: invert}). Finds per-conduit minimum
    diameters so that no designed outfall invert falls below its fixed level, enlarging only the
    conduits on paths that need it. Larger pipes have flatter Table 3.13 minimum slopes, so long
    flat paths lose less fall. For each head of sewer draining to a failing outfall, the fall
    available (ground - cover - fixed invert - margin) is spread over its path length; each
    conduit gets the smallest catalog size whose minimum slope fits the tightest path through it.
    The margin of each failing outfall is raised in 0.05 m steps until it works (least
    enlargement). Returns (min_d_map, (res, node_inv, node_info), report lines)."""
    res, inv, info = design_network(data, ground, R, sizes, None, xy)
    short = {o: f for o, f in fixed.items()
             if info.get(o, {}).get("invert") is not None and info[o]["invert"] < f - 0.001}
    lines = [f"{o}: designed {info[o]['invert']:.3f} m vs fixed {f:.3f} m - "
             + ("needs enlargement" if o in short else "OK as designed")
             for o, f in fixed.items() if info.get(o, {}).get("invert") is not None]
    for ln in lines:
        log("   " + ln)
    if not short:
        return {}, (res, inv, info), lines

    par = {d["from"]: (d["to"], d["length"], lab) for lab, d in res.items()}
    heads = set(par) - {d["to"] for d in res.values()}
    paths = []                                   # (head, outfall, [conduit labels], length)
    for h in heads:
        n, path, L = h, [], 0.0
        while n in par:
            n, l, lab = par[n]
            path.append(lab)
            L += l
        if n in short and ground.get(h) is not None and L:
            paths.append((h, n, path, L))

    def sizes_for(margins):
        allow = {}
        for h, o, path, L in paths:
            s_ok = (ground[h] - R.cover - short[o] - margins[o]) / L
            for lab in path:
                allow[lab] = min(allow.get(lab, 1.0), s_ok)
        mmap = {}
        for lab, s_ok in allow.items():
            pick = sizes[-1]["id_mm"]
            for sz in sizes:
                if sz["id_mm"] < R.dmin - 0.5:
                    continue
                _, smin = slope_row(R.slopes, sz["id_mm"])
                if smin is not None and smin <= s_ok:
                    pick = sz["id_mm"]
                    break
            mmap[lab] = pick
        return mmap

    # Scan the margin upwards in small steps and keep the FIRST one that works (least
    # enlargement). Not a bisection: the outfall invert is not monotonic in the margin
    # (bigger pipes also mean bigger crown-matching drops and deeper starts).
    outs = sorted({o for _, o, _, _ in paths})
    blind = sorted(set(short) - set(outs))
    if blind:
        lines.append(f"no head of sewer with a ground level drains to: {', '.join(blind)} "
                     f"- pipes cannot be sized for the fixed level there")
        log("   " + lines[-1])
    if not outs:
        return {}, (res, inv, info), lines
    margin = {o: 0.0 for o in outs}
    done = {o: False for o in outs}
    best, step, limit = None, 0.05, 5.0
    while not all(done.values()) and max(margin.values(), default=limit) <= limit:
        mm = sizes_for(margin)
        r = design_network(data, ground, R, sizes, mm, xy)
        for o in outs:
            if not done[o] and r[2][o]["invert"] >= short[o] - 0.001:
                done[o] = True
        best = (mm, r)
        for o in outs:
            if not done[o]:
                margin[o] += step
    still = [o for o in outs if not done[o]]
    if still:
        lines.append(f"no catalog sizes reach the fixed level at: {', '.join(still)} "
                     f"- pumping (lift station) is unavoidable there")
        log("   " + lines[-1])
    hi_m = margin
    mmap, r = best
    for o in outs:
        lines.append(f"{o}: after enlargement designed invert {r[2][o]['invert']:.3f} m "
                     f"(fixed {short[o]:.3f} m), margin used {hi_m[o]:.2f} m")
        log("   " + lines[-1])
    return mmap, r, lines


def critical_path(outfall, res, plan, ground, R):
    """Conduits (outfall first, going upstream) of the path that fixes the outfall invert. At the outfall:
    the incoming sewer with the lowest invert. At a manhole: the incoming sewer that fixes the invert of
    the sewer leaving it - by crown matching that is the LOWEST CROWN (invert + diameter), or invert - drop
    for the same size; not simply the lowest invert (a 200 mm branch can hold a 600 mm main down by
    0.4 m). The path stops where the minimum cover at the manhole fixes the outgoing sewer (raising the
    sewers above would not help) or at a head of sewer."""
    path, n, seen, d_out = [], outfall, set(), None
    while n not in seen:
        seen.add(n)
        ins = [res[k["label"]] for k in plan.inc.get(n, [])]
        if not ins:
            break
        if d_out is None:
            d = min(ins, key=lambda x: (x["dn"], x["label"]))
        else:
            D = d_out["D"] / 1000.0

            def cand(x):
                c = x["dn"] + x["D"] / 1000.0 - D
                if abs(x["D"] - d_out["D"]) < 0.5:
                    c = min(c, x["dn"] - R.drop_same)
                return c
            d = min(ins, key=lambda x: (cand(x), x["label"]))
            g = ground.get(n)
            if g is not None and g - R.cover - D <= cand(d) + 1e-9:
                break                                   # minimum cover fixes the sewer leaving n
        path.append(d["label"])
        n, d_out = d["from"], d
    return path


def raise_to_fixed_outfalls(data, ground, R, sizes, fixed, log, xy=None, max_steps=2000):
    """Outfall levels that cannot change (fixed = {outfall: invert}, an existing sewer / STP inlet / IPS):
    pipes are enlarged step by step until the designed outfall invert reaches the fixed level.

    Why a STRETCH and not one pipe (user decision, 12-Oct-2026): a larger pipe has a flatter Table 3.13
    minimum slope (200 mm 1 in 250 -> 300 mm 1 in 450 saves 0.053 m per 30 m), but where it starts its invert
    drops by the difference in diameter (crown matching, p201: 0.10 m). One pipe alone therefore LOWERS the
    outfall; a long enough stretch raises it.

    Each step: on the critical path (the path that fixes the outfall invert) every manhole is a candidate
    'from here down to the outfall every pipe at least one catalog size larger than the pipe leaving here';
    the candidate with the most rise of the outfall per rupee of pipe cost is taken (rise without extra cost
    first). Repeated until the fixed level is reached or no candidate raises the outfall any more - then
    the HIGHEST design found is kept and the outfall is reported as needing pumping (the the original scripts
    plan_for_fixed_outfalls returned its last, most enlarged try there - 2600 mm pipes on a test network).
    Only moves that raise the outfall are taken, so the result is never below the free design.
    Objective = pipe cost from the catalog rates (pipe_cost), as economise_sizes.
    Returns (min_d_map, (res, node_inv, node_info), report lines)."""
    plan = Plan(data)
    cur = design_network(data, ground, R, sizes, {}, xy, plan=plan)
    mm, lines = {}, []
    ids = sorted(z["id_mm"] for z in sizes if z["id_mm"] >= R.dmin - 0.5)

    def note(s):
        lines.append(s)
        log("   " + s)

    for o, f in sorted(fixed.items()):
        inv0 = cur[2].get(o, {}).get("invert")
        if inv0 is None:
            note(f"{o}: no sewer reaches this outfall")
            continue
        if inv0 >= f - 0.001:
            note(f"{o}: designed {inv0:.3f} m vs fixed {f:.3f} m - OK as designed")
            continue
        note(f"{o}: designed {inv0:.3f} m vs fixed {f:.3f} m - needs enlargement")
        steps = 0
        while cur[2][o]["invert"] < f - 0.001 and steps < max_steps:
            res = cur[0]
            path = critical_path(o, res, plan, ground, R)
            inv, cost = cur[2][o]["invert"], pipe_cost(res, sizes)
            best, tried = None, set()
            for i, lab in enumerate(path):
                bigger = [x for x in ids if x > res[lab]["D"] + 0.5]
                if not bigger:
                    continue
                S = bigger[0]
                trial = dict(mm)
                for c in path[:i + 1]:                      # this conduit and the path below it
                    if res[c]["D"] < S - 0.5:
                        trial[c] = max(trial.get(c, 0), S)
                key = tuple(sorted(trial.items()))
                if trial == mm or key in tried:
                    continue
                tried.add(key)
                r = redesign_below(cur, lab, plan, ground, R, sizes, trial, xy)
                rise = r[2][o]["invert"] - inv
                if rise <= 1e-6:
                    continue
                extra = pipe_cost(r[0], sizes) - cost
                score = (1, rise) if extra <= 0 else (0, rise / extra)
                if best is None or score > best[0]:
                    best = (score, trial, r)
            if best is None:
                break
            mm, cur = best[1], best[2]
            steps += 1
        inv1 = cur[2][o]["invert"]
        n_big = sum(1 for d in cur[0].values() if d["label"] in mm)
        if inv1 >= f - 0.001:
            note(f"{o}: after enlargement designed invert {inv1:.3f} m (fixed {f:.3f} m) - {steps} step(s), "
                 f"{n_big} conduit(s) with a minimum size")
        else:
            note(f"{o}: NOT reachable by gravity with the catalog sizes - highest designed invert {inv1:.3f} m "
                 f"(fixed {f:.3f} m, {f - inv1:.3f} m short) after {steps} step(s): pumping is needed at this "
                 f"outfall (or a lower connection level)")
    return mm, cur, lines


# ---------------------------------------------------------------- cost
def pipe_cost(res, sizes):
    """Pipe cost (Rs) used as the OPTIMISATION objective: catalog rate per m x length; where a size has
    no rate its ID (mm) stands in, only so that larger pipes still count as dearer. For the REPORTED
    cost use priced_cost(), which leaves such sizes out and names them."""
    rate = {z["id_mm"]: (z.get("rate_rs_per_m") or z["id_mm"]) for z in sizes}
    return sum((d["length"] or 0) * rate.get(d["D"], d["D"]) for d in res.values())


def rate_ref(sz):
    """Short rate reference of one catalog size (item / SOR code if the catalog gives one)."""
    for k in ("rate_item", "item", "sor_item", "code", "rate_source"):
        if sz.get(k):
            return str(sz[k])
    return ""


def priced_cost(res):
    """(Rs priced from the catalog rates, [sizes without a rate]) - for reports only."""
    amt, missing = 0.0, set()
    for d in res.values():
        rt = d["size"].get("rate_rs_per_m")
        if rt:
            amt += (d["length"] or 0) * float(rt)
        else:
            missing.add(d["size"].get("nominal") or f"{d['D']:g} mm")
    return amt, sorted(missing)


def max_depth(res):
    return max((x for d in res.values() for x in (d["depth_up"], d["depth_dn"]) if x is not None), default=0.0)


def economise_sizes(data, ground, R, sizes, fixed, mmap, start, log, xy=None, max_trials=3000):
    """Cost optimisation after plan_for_fixed_outfalls: try each enlarged conduit one catalog size
    smaller (upstream conduits first, since a sewer may not be smaller than what flows into it);
    keep the change when every fixed outfall is still reached, the deepest point does not get
    deeper (or stays within max_depth_to_invert_m) and no 'no size large enough' flag appears.
    Objective = pipe cost from the catalog rates (excavation is not priced here - the depth
    rule keeps it from growing). Returns (min_d_map, (res, node_inv, node_info), report lines).

    sewer_app (12-Oct-2026): same trials and same result as the the original scripts version, but a trial redesigns
    only the conduit made smaller and what lies below it (redesign_below) instead of the whole network
    (oakdale_B, 7180 conduits: about 0.4 s -> a few ms per trial)."""
    res0 = start[0]
    best_cost, depth_cap = pipe_cost(res0, sizes), max(max_depth(res0), R.max_depth or 0.0)
    ids = [z["id_mm"] for z in sizes if z["id_mm"] >= R.dmin - 0.5]

    def ok(r):
        res_, _, info_ = r
        if any(info_.get(o, {}).get("invert") is None or info_[o]["invert"] < f - 0.001 for o, f in fixed.items()):
            return False
        if max_depth(res_) > depth_cap + 0.001:
            return False
        return not any("catalog size" in fl for d in res_.values() for fl in d["flags"])
    plan = Plan(data)

    par = {d["from"]: (d["to"], d["length"]) for d in res0.values()}

    def dist(n):
        L = 0.0
        while n in par:
            n, l = par[n]
            L += l
        return L
    order = sorted(mmap, key=lambda lab: -dist(res0[lab]["from"]) if lab in res0 else 0)
    best, trials, kept, improved = (dict(mmap), start), 0, 0, True
    while improved and trials < max_trials:
        improved = False
        for lab in order:
            cur = best[0].get(lab)
            if cur is None:
                continue
            smaller = [d for d in ids if d < cur - 0.5]
            trial = dict(best[0])
            if smaller:
                trial[lab] = smaller[-1]
            else:
                trial.pop(lab)
            r = redesign_below(best[1], lab, plan, ground, R, sizes, trial, xy)
            trials += 1
            c = pipe_cost(r[0], sizes)
            if ok(r) and c < best_cost - 1:
                best, best_cost, kept, improved = (trial, r), c, kept + 1, True
            if trials >= max_trials:
                break
    c0 = pipe_cost(res0, sizes)
    line = (f"cost optimisation: {trials} trials, {kept} size reductions kept; pipe cost "
            f"Rs {c0 / 1e5:.2f} lakh -> Rs {best_cost / 1e5:.2f} lakh")
    log("   " + line)
    return best[0], best[1], [line]


# ---------------------------------------------------------------- flushing (CPHEEO 3.29, p215)
def flush_water(table, D, s, flat_rule=None):
    """Table 3.16 (p215) quantity of water for ONE flush, litres, for internal diameter D (mm) and
    slope s. table = {"200": {"200": 2300, ...}, ...} (diameter -> {slope '1 in' -> litres}).
    Diameter column: largest tabulated size <= D (+5 % for internal diameters); below the first
    column the first is used. Slope row: the steepest tabulated slope that is NOT steeper than s
    (i.e. the next flatter row -> more water, safe side); flatter than the flattest row -> that row.
    flat_rule 'flattest_row' (project decision, flushing_flatter_slope_rule): a slope flatter than the
    flattest row takes that row without a warning (note says 'project decision').
    Returns (litres, column mm, row '1 in', note, outside) - litres None when D is above the table;
    outside = True when the value is NOT covered by the table or a project decision."""
    if not table or not D or not s or s <= 0:
        return None, None, None, "no Table 3.16 data / no slope", True
    cols = sorted(float(k) for k in table)
    fit = [c for c in cols if c <= D * 1.05]
    notes, outside = [], False
    if not fit:
        col = cols[0]
        notes.append(f"diameter {D:g} mm below Table 3.16 - {col:g} mm column used")
        outside = True
    else:
        col = fit[-1]
        if D > cols[-1] * 1.05:
            return None, None, None, f"diameter {D:g} mm above Table 3.16 ({cols[-1]:g} mm) - water not given", True
    rows = table[next(k for k in table if float(k) == col)]
    one_in = sorted(float(k) for k in rows)                 # e.g. [33, 50, 100, 130, 200]
    ok = [x for x in one_in if 1.0 / x <= s + 1e-12]        # tabulated slopes not steeper than s
    if ok:
        row = min(ok)                                       # steepest of them
    else:
        row = max(one_in)
        if flat_rule == "flattest_row":
            notes.append(f"slope 1 in {1 / s:.0f} flatter than Table 3.16 - 1 in {row:g} row used (project decision)")
        else:
            notes.append(f"slope 1 in {1 / s:.0f} flatter than Table 3.16 (1 in {row:g}) - that row used, "
                         f"more water may be needed")
            outside = True
    lit = rows[next(k for k in rows if float(k) == row)]
    return float(lit), col, row, "; ".join(notes), outside


def plan_flushing(res, node_info, R, crit):
    """Flushing manholes (CPHEEO 3.29, p215). A conduit is NOT self-cleansing when its uniform-flow
    velocity is below the minimum velocity (5 mm/s tolerance, as design_check) or it carries no flow.
    Each continuous run of such conduits gets ONE flushing manhole at its upstream end ('generally at
    the head of a sewer', p215). Water for one flush from Table 3.16 by the diameter and slope of the
    first conduit of the run. Returns a list of dicts, upstream-first."""
    c = crit["sewer"]
    table = val(c, "flushing_water_l")
    vmin = R.vmin
    if vmin is None:
        return []
    slow = {}
    for lab, d in res.items():
        if not d["q"]:
            slow[lab] = "no flow"
        elif d["v"] is None or d["v"] < vmin - 0.005:
            slow[lab] = f"velocity {d['v']:.2f} < {vmin} m/s" if d["v"] is not None else "velocity not computed"
        elif "q_init" in d and R.vmin_init is not None and (not d["q_init"] or d["v_init"] is None
                                                             or d["v_init"] < R.vmin_init - 0.005):
            slow[lab] = (f"initial peak velocity {d['v_init']:.2f} < {R.vmin_init} m/s" if d.get("v_init") is not None
                         else "no flow at the initial stage")
    inc, out = {}, {}
    for lab, d in res.items():
        inc.setdefault(d["to"], []).append(lab)
        out.setdefault(d["from"], []).append(lab)
    rows = []
    for lab, d in res.items():
        if lab not in slow or any(u in slow for u in inc.get(d["from"], [])):
            continue                                        # not the first conduit of a slow run
        run, L, cur = [], 0.0, lab
        while cur in slow and cur not in run:
            run.append(cur)
            L += res[cur]["length"] or 0.0
            nxt = out.get(res[cur]["to"], [])
            cur = nxt[0] if nxt else None
        lit, col, row, note, outside = flush_water(table, d["D"], d["slope"], val(c, "flushing_flatter_slope_rule"))
        ni = node_info.get(d["from"], {})
        rows.append({"manhole": d["from"], "ground": ni.get("ground"), "invert": ni.get("invert"),
                     "depth": ni.get("depth"), "head_of_sewer": not inc.get(d["from"]),
                     "conduit": lab, "D": d["D"], "slope": d["slope"], "q": d["q"], "v": d["v"],
                     "reason": slow[lab], "col": col, "row": row, "litres": lit, "note": note, "outside": outside,
                     "run_len": L, "run_n": len(run), "run_end": res[run[-1]]["to"], "run": run})
    for r_ in rows:
        node_info.setdefault(r_["manhole"], {})["flushing"] = True
    return rows


def slow_length(rows, res):
    """Length (m) of sewer below the self-cleansing velocity, each conduit counted ONCE (runs from
    different flushing manholes share the conduits below their junction)."""
    seen = {lab for r_ in rows for lab in r_.get("run", [])}
    return sum(res[lab]["length"] or 0.0 for lab in seen if lab in res), len(seen)


def flushing_totals(rows, crit):
    """(water per flushing round L, tanker capacity L, tanker trips per round, frequency per day)."""
    c = crit["sewer"]
    tank = val(c, "flushing_tanker_l")
    freq = val(c, "flushing_frequency_per_day")
    total = sum(r_["litres"] or 0.0 for r_ in rows)
    trips = math.ceil(total / tank) if (tank and total) else None
    return total, tank, trips, freq
