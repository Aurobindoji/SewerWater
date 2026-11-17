"""The Simulation tab (user request 17-Nov-2026: "network design के बगल में simulation tab ... steady state analysis
(SSA) और extended period simulation (EPS)"): the network of the last design - its pipe sizes, OHT stagings and PRVs,
kept by design_run._sim_pack - solved again under a load chosen on the page, without designing again.

    info(stem)        what can be run: the stages, the default draw-off pattern and filling hours, the fire flow
    run(stem, req)    req["mode"] "ssa" | "eps"; the load:
        stage    "ult" (the design's, +30 years) | "mid" (+15) | "init" (base year) - the demand x that stage's share
        extra    [{node, lps}]  more draw-off at junctions (every hour in an EPS)
        ssa:  base "average" | "peak" | "night" | "hour" (hour 0-23 of the pattern) | "factor" (factor x average);
              fires [{node, lps}] at junctions, min_m the head to hold there (empty: shown only)
        eps:  hours 24 / 48 / 72, pattern (24 multiples of the average hourly demand; empty: the criteria's),
              inflow "5-12, 13-22" (the OHTs' filling hours; empty: the design's)
The answer has the junctions' and pipes' ids once ("nodes", "pipes") and their values in that order: SSA "P"
(residual head m), "H" (HGL m), "Q" (L/s, + from a to b), "V" (m/s), "HL" (m/km); EPS "P", "Q", "V" each a list per
hour, with the hour rows and the tanks of simulate.day.
"""
import math
import os
import time

from . import demand as dm
from . import project as ui
from . import simulate as wsim
from .results import sim_pack

STAGE_NAME = {"ult": "design (+30 years)", "mid": "+15 years", "init": "base year"}
WORST_N = 12


def _pack(stem):
    p = sim_pack(stem)
    if not p:
        raise ValueError("Simulation के लिए पहले Design चलाएँ (इस version में - पुराने design में simulation का data नहीं)")
    return p


def info(stem):
    p = _pack(ui.safe_name(stem))
    crit = p["crit"]
    f = os.path.join(ui.out_root(), ui.safe_name(stem), f"{ui.safe_name(stem)}_wsim.pkl")
    return {"ok": True, "stages": p["stages"], "pattern": list(crit["draw_off_pattern"]["value"]),
            "pattern_ref": crit["draw_off_pattern"]["ref"], "windows": p["windows"],
            "peak_factor": crit["peak_factor"]["value"], "fire_lps": p.get("fire_lps"), "fire_min": p.get("fire_min"),
            "tanks": [t["name"] for t in p["tanks"]], "residual_head_m": crit["residual_head_m"]["value"],
            "max_velocity_mps": crit["max_velocity_mps"]["value"], "min_velocity_mps": crit["min_velocity_mps"]["value"],
            "max_pressure_m": crit["max_pressure_m"]["value"] if "max_pressure_m" in crit else None,
            "made": time.strftime("%d-%m-%Y %H:%M", time.localtime(os.path.getmtime(f))) if os.path.isfile(f) else None}


def _num(v, lo, hi, what):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{what}: '{v}' अंक नहीं") from None
    if not (lo <= x <= hi) or math.isnan(x):
        raise ValueError(f"{what}: {x:g} - {lo:g} से {hi:g} के बीच हो")
    return x


def _stage(p, req):
    st = req.get("stage") or "ult"
    if st == "ult":
        return 1.0, STAGE_NAME["ult"]
    if st not in p["stages"]:
        raise ValueError("इस stage की आबादी design में नहीं दी गई (आबादी tab: base year / +15 वर्ष की आबादी भरकर Design)")
    return p["stages"][st]["factor"], STAGE_NAME[st]


def _extra(p, rows, what="अतिरिक्त load"):
    out = {}
    for r in rows or []:
        n = str(r.get("node") or "").strip()
        if not n:
            continue
        if n not in p["hnet"]["nodes"] or p["hnet"]["nodes"][n].get("head") is not None:
            raise ValueError(f"{what}: junction '{n}' design के network में नहीं")
        out[n] = out.get(n, 0.0) + _num(r.get("lps"), 0.0, 2000.0, f"{what} ({n}) L/s")
    return out


def _pattern(p, req):
    pat = req.get("pattern")
    if not pat:
        return list(p["crit"]["draw_off_pattern"]["value"]), None
    if len(pat) != 24:
        raise ValueError("Draw-off pattern में 24 घंटे के मान चाहिए")
    pat = [_num(x, 0.0, 10.0, f"pattern {h}-{h + 1} h") for h, x in enumerate(pat)]
    s = sum(pat)
    note = None if abs(s - 24.0) <= 0.05 else (f"pattern का जोड़ {s:.2f} (24 नहीं): दिन की माँग औसत का x {s / 24:.3f}; "
                                               f"टंकियों में भराई design जितनी - स्तर उसी से बदलेगा")
    return pat, note


def _worst(nodes, Plo, Phi, pipes, V):
    """The WORST_N lowest heads (of Plo), highest (of Phi) and fastest pipes (of V) - [[id, value], ...]."""
    lo = [(x, n) for n, x in zip(nodes, Plo) if x == x]
    hi = [(x, n) for n, x in zip(nodes, Phi) if x == x]
    pv = [(x, k) for k, x in zip(pipes, V) if not k.endswith(" outlet")]
    return {"low": [[n, x] for x, n in sorted(lo)[:WORST_N]],
            "high": [[n, x] for x, n in sorted(hi, reverse=True)[:WORST_N]],
            "fast": [[k, x] for x, k in sorted(pv, reverse=True)[:WORST_N]]}


def run(stem, req):
    stem = ui.safe_name(stem)
    p = _pack(stem)
    mode = req.get("mode") or "ssa"
    if mode == "eps":
        return _eps(p, req)
    if mode == "ssa":
        return _ssa(p, req)
    raise ValueError(f"mode '{mode}' नहीं")


def _ssa(p, req):
    crit, hnet = p["crit"], p["hnet"]
    sf, sname = _stage(p, req)
    pattern, _ = _pattern(p, req)
    base = req.get("base") or "average"
    if base == "peak":
        f, what = crit["peak_factor"]["value"], f"peak (x {crit['peak_factor']['value']:g})"
    elif base == "night":
        f, what = min(pattern), f"night - the lowest hour (x {min(pattern):g})"
    elif base == "hour":
        h = int(_num(req.get("hour", 8), 0, 23, "घंटा"))
        f, what = pattern[h], f"{h:02d}:00-{h + 1:02d}:00 (x {pattern[h]:g})"
    elif base == "factor":
        f = _num(req.get("factor", 1.0), 0.0, 10.0, "गुणक")
        what = f"x {f:g} of the average"
    elif base == "average":
        f, what = 1.0, "average (x 1)"
    else:
        raise ValueError(f"load '{base}' नहीं")
    extra = _extra(p, req.get("extra"))
    fires = _extra(p, req.get("fires"), "fire")
    allx = dict(extra)
    for n, q in fires.items():
        allx[n] = allx.get(n, 0.0) + q
    t0 = time.time()
    r, summ = wsim.ssa(hnet, crit, p["prvs"], factor=f * sf, extra=allx)
    fixed = {n for n, v in hnet["nodes"].items() if v.get("head") is not None}
    nodes = [n for n in hnet["nodes"] if n not in fixed]
    pipes = list(hnet["pipes"])
    P = [round(r["pressure"].get(n, float("nan")), 2) for n in nodes]
    V = [round(r["velocity"].get(k, 0.0), 3) for k in pipes]
    fmin = req.get("min_m")
    fmin = None if fmin in (None, "") else _num(fmin, 0.0, 100.0, "fire पर न्यूनतम दबाव m")
    fire_rows = [{"node": n, "lps": q, "p": round(r["pressure"].get(n, float("nan")), 2),
                  "p_peak": p["peak_p"].get(n), "ok": None if fmin is None else r["pressure"].get(n, -1e9) >= fmin - 1e-6}
                 for n, q in fires.items()]
    demand = sum((v.get("avg", v.get("demand")) or 0.0) for n, v in hnet["nodes"].items() if n not in fixed)
    return {"ok": True, "mode": "ssa", "load": what, "stage": sname, "factor": round(f * sf, 4),
            "demand_lps": round(demand * f * sf + sum(allx.values()), 2), "extra_lps": round(sum(extra.values()), 2),
            "fires": fire_rows, "summary": summ, "nodes": nodes, "pipes": pipes, "P": P,
            "H": [round(r["head"].get(n, float("nan")), 2) for n in nodes],
            "Q": [round(r["flow"].get(k, 0.0), 2) for k in pipes], "V": V,
            "HL": [round(r["hl_per_km"].get(k, 0.0), 2) for k in pipes],
            "closed": [k for k in pipes if hnet["pipes"][k].get("closed")],
            "oz": {n: p["oz"].get(n) for n in nodes}, "worst": _worst(nodes, P, P, pipes, V),
            "tank_heads": {n: round(hnet["nodes"][n]["head"], 2) for n in fixed},
            "iterations": r.get("iterations"), "seconds": round(time.time() - t0, 2)}


def _eps(p, req):
    crit, hnet = p["crit"], p["hnet"]
    sf, sname = _stage(p, req)
    pattern, note = _pattern(p, req)
    hours = int(_num(req.get("hours", 24), 24, 72, "अवधि (घंटे)"))
    if hours % 24:
        raise ValueError("अवधि 24, 48 या 72 घंटे")
    win = req.get("inflow")
    win = dm.parse_windows(win) if win not in (None, "") else p["windows"]
    extra = _extra(p, req.get("extra"))
    t0 = time.time()
    d = wsim.day(hnet, crit, p["tanks"], p["prvs"], win, pattern=pattern, hours=hours, factor=sf, extra=extra,
                 detail=True)
    return dict(d, ok=True, mode="eps", stage=sname, factor=sf, n_hours=hours, note=note,
                extra_lps=round(sum(extra.values()), 2), closed=[k for k in d["pipes"] if hnet["pipes"][k].get("closed")],
                oz={n: p["oz"].get(n) for n in d["nodes"]},
                worst=_worst(d["nodes"], [min(c) for c in zip(*d["P"])], [max(c) for c in zip(*d["P"])], d["pipes"],
                             [max(c) for c in zip(*d["V"])]),
                seconds=round(time.time() - t0, 2))
