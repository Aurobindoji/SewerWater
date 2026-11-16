"""The designed network under other loads (user request 16-Nov-2026: "water load विकल्प और simulation").

Load cases - the network as designed (pipe sizes, OHT stagings, PRVs) solved again at:
    average      the average demand (x 1)
    night        the lowest hour of the draw-off pattern (criteria "draw_off_pattern": x 0.05) - the highest pressures
    fire         the average demand + a fire flow (L/s, given on the page) at the weakest junction of each OZ (the
                 lowest residual head at the peak), each OZ at once (the OZs are apart: closed pipes); the head there
                 checked against a minimum when one is given. CPHEEO p138 gives no hydrant flow nor head: the fire
                 engines boost the pressure, one third of the OZ's fire demand is kept in its OHT.
    cs = cases(hnet, crit, prvs, peak_p, oz_of, fire_lps=None, fire_min_m=None)

24 h simulation (extended period, hour by hour) - each OHT's water level and the network's pressures:
    the demand of the hour = average x the draw-off pattern (criteria; as the OHT's mass balance, demand.mass_balance);
    an OHT is filled in its filling hours (criteria "oht_inflow_hours" / the page) at its OZ's daily demand / those
    hours, and gives what its outlet carries; its water above the fire third (CPHEEO p138: the supply outlet just above
    it) from 0 (the design's head: ground + staging) up to its capacity, the tank taken as a cylinder of the side water
    depth; at 0 h it holds what the mass balance needs never to run dry (its largest deficit) and half of any room
    beyond the mass balance's swing (start_kl), at most full.
    A full tank takes no more (overflow / the pumps stop), an empty one gives no more (the hour's shortage).
    d = day(hnet, crit, tanks, prvs, windows)     tanks: [{name, node, kl, swd_m, fire_kl, daily_kl}]
"""
from . import demand as dm
from . import hydraulics as hy
from . import prv as wprv

SHORT_KL = 0.05     # KL: a shortage less than this is rounding (a tank sized by the mass balance touches 0 %)
# below this share of its usable water in the day an OHT has no margin: a warning (user decision 16-Nov-2026, after
# the WaterGEMS EPS comparison: tanks sized exactly by the mass balance closed for a moment at 12:59 there)
MARGIN_PCT = 5.0
FIRE_REF = ("CPHEEO 2.8.2.5(iv) p138: fire demand 100 sqrt(P) m3/d, one third of an OZ's in its OHT, the pressure "
            "boosted by the fire engines - no hydrant flow / head given; flow and head given on the page")


def _net(hnet, use_avg=True, extra=None):
    """A copy of the network for a run: each junction's demand its average (L/s) - the peak demand of the design is
    average x peak factor - plus extra {node: L/s}."""
    nodes = {}
    for n, v in hnet["nodes"].items():
        d = dict(v)
        if v.get("head") is None and use_avg:
            d["demand"] = v.get("avg", v.get("demand")) or 0.0
        if extra and n in extra:
            d["demand"] = (d.get("demand") or 0.0) + extra[n]
        nodes[n] = d
    return {"nodes": nodes, "pipes": hnet["pipes"]}


def _summary(r, hnet, crit, fixed):
    rh = crit["residual_head_m"]["value"]
    pr = {n: x for n, x in r["pressure"].items() if n not in fixed}
    live = {lab: v for lab, v in r["velocity"].items() if not hnet["pipes"][lab].get("closed")}
    lo = min(pr, key=pr.get) if pr else None
    hi = max(pr, key=pr.get) if pr else None
    top = crit["max_pressure_m"]["value"] if "max_pressure_m" in crit else None
    return {"min_p": round(pr[lo], 2) if lo else None, "min_at": lo, "max_p": round(pr[hi], 2) if hi else None,
            "max_at": hi, "low_n": sum(1 for x in pr.values() if x < rh - 1e-6),
            "high_n": sum(1 for x in pr.values() if x > top + 1e-6) if top is not None else 0,
            "v_max": round(max(live.values()), 3) if live else None}


def cases(hnet, crit, prvs, peak_p, oz_of, fire_lps=None, fire_min_m=None):
    """[{case, factor, demand_lps, min_p, min_at, max_p, max_at, low_n, v_max}] and the fire rows
    [{oz, node, fire_lps, p, p_peak, ok}] (none without a fire flow)."""
    minor = crit["minor_loss_factor"]["value"]
    pf = crit["peak_factor"]["value"]
    night = min(crit["draw_off_pattern"]["value"])
    fixed = {n for n, v in hnet["nodes"].items() if v.get("head") is not None}
    avg = sum(v.get("avg", v.get("demand")) or 0.0 for n, v in hnet["nodes"].items() if n not in fixed)
    rows = []
    for case, f in (("peak", pf), ("average", 1.0), ("night", night)):
        r = hy.solve(_net(hnet), minor_loss=minor, demand_factor=f)
        wprv.shift(r, prvs)
        rows.append(dict(case=case, factor=f, demand_lps=round(avg * f, 2), **_summary(r, hnet, crit, fixed)))
    fires = []
    if fire_lps and fire_lps > 0:
        weak = {}                                         # each OZ's weakest junction at the peak
        for n, p in peak_p.items():
            k = oz_of.get(n)
            if k is not None and n not in fixed and (k not in weak or p < peak_p[weak[k]]):
                weak[k] = n
        r = hy.solve(_net(hnet, extra={n: fire_lps for n in weak.values()}), minor_loss=minor)
        wprv.shift(r, prvs)
        rows.append(dict(case="fire", factor=1.0, demand_lps=round(avg + fire_lps * len(weak), 2),
                         **_summary(r, hnet, crit, fixed)))
        for k in sorted(weak, key=str):
            n = weak[k]
            p = r["pressure"].get(n)
            fires.append({"oz": k, "node": n, "fire_lps": fire_lps, "p": round(p, 2) if p is not None else None,
                          "p_peak": round(peak_p[n], 2),
                          "ok": None if fire_min_m is None or p is None else p >= fire_min_m - 1e-6})
    return rows, fires


def start_share(crit, windows):
    """The least water an OHT holds at 0 h, in multiples of the average hourly demand: the mass balance's largest
    deficit (demand.mass_balance) - what it needs never to run dry."""
    return -dm.mass_balance(crit, windows)["deficit"]


def start_kl(use_kl, hourly_kl, crit, windows):
    """The water at 0 h (KL): the least it needs, and half of what the tank holds beyond the mass balance's swing
    (a margin, user 16-Nov-2026: as far from empty as from full), at most full."""
    mb = dm.mass_balance(crit, windows)
    swing = (mb["excess"] - mb["deficit"]) * hourly_kl
    return min(use_kl, -mb["deficit"] * hourly_kl + max(0.0, use_kl - swing) / 2.0)


def day(hnet, crit, tanks, prvs, windows=None):
    """The 24 h run (module text). Returns {"hours": [...], "tanks": {name: {...}}}; an hour's row: h, factor,
    demand_lps, min_p / min_at / max_p / low_n / v_max, and per tank level_m (above the design's lowest level),
    full_pct, in_kl, out_kl, spill_kl, short_kl."""
    win = windows or crit["oht_inflow_hours"]["value"]
    pattern = crit["draw_off_pattern"]["value"]
    minor = crit["minor_loss_factor"]["value"]
    on = [dm._on(win, h) for h in range(24)]
    hours_on = sum(on) or 1.0
    s0 = start_share(crit, win)
    net = _net(hnet)
    fixed = {n for n, v in net["nodes"].items() if v.get("head") is not None}
    model = hy.Model(net, minor, 1.0)
    base = model.dem.copy()
    st = {}
    for t in tanks:
        use = max(t["kl"] - t.get("fire_kl", 0.0), 0.0)        # above the fire third: what the supply draws
        area = t["kl"] / t["swd_m"] if t.get("swd_m") and t["kl"] > 0 else None
        hr = t["daily_kl"] / 24.0
        v0 = start_kl(use, hr, crit, win)
        st[t["name"]] = {"use_kl": use, "area_m2": area, "vol": v0, "low_head": net["nodes"][t["name"]]["head"],
                         "fire_m": (t.get("fire_kl", 0.0) / area) if area else 0.0, "hourly_kl": hr,
                         "empty_h": [], "full_h": [], "min_pct": 100.0, "spill_kl": 0.0, "short_kl": 0.0,
                         "start_pct": round(100.0 * v0 / use, 1) if use else None}
    rows = []
    for h in range(24):
        model.dem = base * pattern[h]
        for name, s in st.items():                             # the head of the hour: the water above the outlet
            lvl = (s["vol"] / s["area_m2"]) if s["area_m2"] else 0.0
            model.set_head(name, s["low_head"] + s["fire_m"] + lvl)
        r = model.solve()
        wprv.shift(r, prvs)
        row = dict(h=h, factor=pattern[h], demand_lps=round(float(base.sum()) * 1000.0 * pattern[h], 2),
                   **_summary(r, hnet, crit, fixed), tanks={})
        for t in tanks:
            s = st[t["name"]]
            lvl = (s["vol"] / s["area_m2"]) if s["area_m2"] else 0.0
            pct = 100.0 * s["vol"] / s["use_kl"] if s["use_kl"] else 0.0
            inflow = t["daily_kl"] * on[h] / hours_on
            out = max(r["flow"].get(f"{t['name']} outlet", 0.0), 0.0) * 3.6       # L/s over the hour -> KL
            v = s["vol"] + inflow - out
            spill = max(0.0, v - s["use_kl"])
            short = max(0.0, -v)
            s["vol"] = min(max(v, 0.0), s["use_kl"])
            s["spill_kl"] += spill
            s["short_kl"] += short
            s["min_pct"] = min(s["min_pct"], pct)
            if short > SHORT_KL:
                s["empty_h"].append(h)
            if spill > SHORT_KL:
                s["full_h"].append(h)
            row["tanks"][t["name"]] = {"level_m": round(s["fire_m"] + lvl, 2), "full_pct": round(pct, 1),
                                       "in_kl": round(inflow, 1), "out_kl": round(out, 1),
                                       "spill_kl": round(spill, 1), "short_kl": round(short, 1)}
        rows.append(row)
    out = {}
    for t in tanks:
        s = st[t["name"]]
        end = 100.0 * s["vol"] / s["use_kl"] if s["use_kl"] else None
        out[t["name"]] = {"kl": t["kl"], "fire_kl": round(t.get("fire_kl", 0.0), 1), "use_kl": round(s["use_kl"], 1),
                          "swd_m": t.get("swd_m"), "daily_kl": round(t["daily_kl"], 1),
                          "start_pct": s["start_pct"], "end_pct": round(end, 1) if end is not None else None,
                          "min_pct": round(s["min_pct"], 1), "empty_h": s["empty_h"], "full_h": s["full_h"],
                          "spill_kl": round(s["spill_kl"], 1), "short_kl": round(s["short_kl"], 1)}
    return {"hours": rows, "tanks": out, "start_share": round(s0, 3),
            "windows": win, "pattern": list(pattern)}
