"""The water design of the map page (/api/w/water_design): pipe sizes and OHT stagings for 17 m, the OHTs moved
where no size helps, the stage-wise check, the PRVs, the rising mains of the new tube wells (restructure stage 2,
15-Nov-2026: out of ui_api.py)."""
import math
from . import hindi
from . import intze
from . import project as ui
from . import demand as dm
from . import design as wd
from . import dpr as wdpr
from .dpr import rising_main as wdpr_rm
from . import hydraulics as hy
from . import prv as wprv
from . import rising as wrising
from . import simulate as wsim
from .zone_lines import _mid_along
from .wards import _with_projection
from .results import _dpr_info, _excel, _keep, _keep_dpr, _keep_sim, edits_of
from .zoning_run import _barrier_check, _barrier_res, _loop_flags, _loop_res, _near_nodes, _node_lps, _unserved_note, _zones, _zoning_res


DESIGN_ROUNDS = 1200   # upsizing rounds of a design
FIRE_PASSES = 4        # designs more at most when the fire flow is designed for (its weakest junctions move)


MOVE_ROUNDS = 4        # designs at most: an OHT with a given staging gives up the nodes still below 17 m, again


def run_design(name, req):
    stem = ui.safe_name(name)
    bar, lines = {}, []
    req = _with_projection(req)
    for rnd in range(MOVE_ROUNDS):
        zz = _zones(stem, req, bar)
        out = _design_once(stem, req, *zz, lines)
        # the nodes an OHT with a given staging leaves below 17 m: to a new OHT (zoning again), not its own node
        res_h, ohts, crit, z, rh = out["res_h"], zz[3], zz[4], zz[5], out["rh"]
        add = {}
        for o in ohts:
            if o.get("low_head") != "new_oht":
                continue
            # only those no pipe size helps (not those the design ran out of rounds for)
            low = {n for n in out["hopeless"] if z["oz"].get(n) == o["name"] and n != o["node"]}
            if low - bar.get(o["name"], set()):
                add[o["name"]] = low
        if not add or rnd == MOVE_ROUNDS - 1:
            break
        for k, v in add.items():
            bar.setdefault(k, set()).update(v)
        lines.append(f"\n-- {', '.join(f'{k}: {len(v)} junctions below {rh:g} m' for k, v in add.items())}"
                     f" - given to a new OHT, zoning and design again")
    res = out["res"]
    res["projection"] = req.get("_proj")
    if bar:
        res["zoning_changed"] = True
        _keep(stem, "zoning", _zoning_res(stem, *zz), req)        # the zones shown: as designed
    for k, th in z.get("too_high", {}).items():
        th["stayed"] = sum(1 for n, kk in z["oz"].items() if kk == k and n in res_h["pressure"]
                           and res_h["pressure"][n] < rh - 1e-6)
        if th["to"]:
            res["checks"].append({"check": f"{k}: higher ground to new OHTs", "ok": True, "note": True,
                                  "ref": crit["residual_head_m"]["ref"],
                                  "detail": "its staging cannot give 17 m there - taken by " + ", ".join(sorted(th["to"])) +
                                            (f"; {th['stayed']} junctions on the way stay with it (below 17 m)"
                                             if th["stayed"] else "")})
    res.update(_barrier_res(stem, zz[1]))
    if _barrier_check(zz[1]):
        res["checks"].append(_barrier_check(zz[1]))
    res.update(_loop_res(zz[5], zz[2]))
    for f in _loop_flags(zz[5], zz[2]):
        res["checks"].append({"check": f["text"].split(":")[0], "ok": True, "note": True,
                              "ref": "user 27-Oct-2026: an area enclosed on the map is a zone of its own",
                              "detail": f["text"].split(":", 1)[1].strip(),
                              "check_hi": f["hi"].split(":")[0], "detail_hi": f["hi"].split(":", 1)[1].strip()})
    res["stages"] = _stages(req, out["hnet"], zz[2], ohts, z, crit, res, out["prvs"])
    if sim_on(req):                          # load cases and the 24 h run (user request 16-Nov-2026)
        _simulate(req, out, zz[2], z, crit, res)
    res["rising"] = _rising(stem, req, zz[2], z, ohts, res, crit)
    fire = sum(dm.daily_kl(v["pop"], crit, out["res"]["summary"]["population"])["fire"] for v in zz[2]["nodes"].values())
    res["checks"].append({"check": "fire demand", "ok": True, "note": True,
                          "ref": "user decision 30-Oct-2026; " + crit["fire_formula"]["ref"],
                          "detail": f"{fire:,.1f} KLD held in the OHTs (their capacity, DPR T1 storage) - not in the "
                                    f"network's peak flow (x {crit['peak_factor']['value']:g} on domestic + floating + bulk)",
                          "check_hi": "fire demand",
                          "detail_hi": f"{fire:,.1f} KLD टंकियों में रखा (उनकी क्षमता, DPR T1 storage) - network के peak "
                                       f"flow में नहीं (x {crit['peak_factor']['value']:g} केवल domestic + floating + bulk पर)"})
    # the bulk consumers (user 30-Oct-2026): for the checks and the DPR (T1, with the OZ each is in)
    res["bulk"] = [{"name": b["name"], "node": b["node"], "oz": z["oz"].get(b["node"]), "kld": b["kld"], "kl": b["kl"],
                    "peak": b["peak"], "dist_m": b["dist_m"]} for b in zz[2].get("bulk") or []]
    if res["bulk"]:
        s = ", ".join(f"{b['name']} {b['kld']:g} KLD x {b['peak']:g} at {b['node']} ({b['oz']})" for b in res["bulk"][:8])
        res["checks"].append({"check": "bulk consumers", "ok": True, "note": True,
                              "ref": "user 30-Oct-2026: KLD + distribution losses (CPHEEO Table 2.7 S.No.6), each at its "
                                     "own peak factor, the same at every stage",
                              "detail": s + (" ..." if len(res["bulk"]) > 8 else ""),
                              "check_hi": "bulk consumers", "detail_hi": s + (" ..." if len(res["bulk"]) > 8 else "")})
    try:
        res["files"] = {"excel": _excel(zz[0], stem, res, z, crit)}
    except Exception as e:                                         # the design stands without its Excel
        res["log"] += f"\nExcel not written: {type(e).__name__}: {e}"
    try:                       # what the Simulation tab runs on (17-Nov-2026)
        _keep_sim(zz[0], stem, _sim_pack(req, out, zz[2], z, crit, res))
    except Exception as e:                                         # the design stands without it
        res["log"] += f"\nSimulation data not kept: {type(e).__name__}: {e}"
    try:                       # the DPR's data only - its workbook on Export DPR (dpr_file; user 15-Nov-2026)
        _keep_dpr(zz[0], stem, _dpr_info(stem, res, z, crit, req, zz[2], zz[1]))
    except Exception as e:                                         # nor without its DPR
        res["log"] += f"\nDPR data not kept: {type(e).__name__}: {e}"
    # the Intze drawings: no longer with the DPR - one tank at a time by its button (user decision 10-Nov-2026)
    for c in res["checks"]:                                        # their Hindi for the page (30-Oct-2026)
        hindi.check_hi(c)
    _keep(stem, "design", res, req)
    return res


STAGE_YEARS = {"init": 0, "mid": 15, "ult": 30}


def design_cases(req, crit):
    """The loads the design must pass besides the peak, when the page asks for it (crit "design_cases", user request
    16-Nov-2026): the 24 h run's busiest hour (draw-off pattern) when it is above the peak factor - the OHT at its
    lowest level then, as the design takes it."""
    if not (crit.get("design_cases") or {}).get("value"):
        return []
    top = max(crit["draw_off_pattern"]["value"])
    pf = crit["peak_factor"]["value"]
    if top <= pf + 1e-9:
        return []
    return [{"name": f"busiest hour (x {top:g})", "factor": top, "min_head": crit["residual_head_m"]["value"],
             "ref": crit["draw_off_pattern"]["ref"]}]


def fire_case(req, crit, res, z):
    """The fire flow of the page as a load to design for (constraint on, a flow and a head given): at each OZ's
    weakest junction of the design res, with the average demand."""
    if not (crit.get("design_cases") or {}).get("value"):
        return None
    q, m = _fire_inputs(req)
    if not q or m is None:
        return None
    weak = {}
    for n, p in res["pressure"].items():
        k = z["oz"].get(n)
        if k is not None and (k not in weak or p < res["pressure"][weak[k]]):
            weak[k] = n
    return {"name": f"fire flow {q:g} L/s", "factor": 1.0, "extra": {n: q for n in weak.values()}, "extra_lps": q,
            "min_head": m, "ref": wsim.FIRE_REF}


def sim_on(req):
    """Load cases and the 24 h simulation with the design: on unless switched off on the page."""
    return str((req or {}).get("simulate", "1")).strip().lower() not in ("", "0", "false", "off")


def _fire_inputs(req):
    """The page's fire flow (L/s; empty / 0 = no fire case) and the head to check at it (m; empty = shown only)."""
    def num(k, lo, hi, what):
        v = (req or {}).get(k)
        if v in (None, ""):
            return None
        try:
            x = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{what}: '{v}' अंक नहीं") from None
        if not lo <= x <= hi:
            raise ValueError(f"{what}: {x:g} ठीक नहीं - {lo:g} से {hi:g} तक")
        return x
    return num("fire_lps", 0, 500, "fire flow (L/s)"), num("fire_min_m", 0, 60, "fire के समय न्यूनतम दबाव (m)")


def _tanks(res, z, wnet, hnet, crit):
    """The OHTs for the 24 h run: [{name, kl, swd_m, fire_kl (one third of its OZ's fire demand), daily_kl}]."""
    S = wdpr.settings()
    swd = lambda kl: next(d for c, d in S["swd"] if c is None or (kl or 0) <= c)
    city = sum(v["pop"] for v in wnet["nodes"].values())
    tanks = []
    for o in res["outlets"]:
        kl = (o.get("capacity_kl") or 0) + (o.get("new_kl") or 0) or o.get("required_kl")   # both tanks together
        if not kl:
            continue
        mem = [n for n, k in z["oz"].items() if k == o["name"] and n in wnet["nodes"]]
        fire = sum(dm.daily_kl(wnet["nodes"][n]["pop"], crit, city)["fire"] for n in mem)
        daily = sum(hnet["nodes"][n].get("avg", 0.0) or 0.0 for n in mem if n in hnet["nodes"]) * 86.4
        tanks.append({"name": o["name"], "kl": float(kl), "swd_m": swd(kl), "fire_kl": fire / 3.0, "daily_kl": daily})
    return tanks


def _sim_pack(req, out, wnet, z, crit, res):
    """What the Simulation tab runs on, kept with the design (17-Nov-2026): the designed network (sizes, OHT heads,
    average demands), its PRVs, the OZ of each junction, the tanks, the criteria, the filling hours and the
    population stages as multiples of the design's average demand."""
    ult = next((st["avg_lps"] for st in res.get("stages") or [] if st["stage"] == "ult"), None) or         res["summary"].get("demand_avg_lps")
    stages = {st["stage"]: {"year": st.get("year"), "pop": st["pop"], "factor": round(st["avg_lps"] / ult, 4)}
              for st in res.get("stages") or [] if ult}
    fire_lps, fire_min = _fire_inputs(req)
    return {"hnet": out["hnet"], "prvs": out["prvs"], "oz": dict(z["oz"]), "crit": crit,
            "tanks": _tanks(res, z, wnet, out["hnet"], crit), "windows": crit["oht_inflow_hours"]["value"],
            "stages": stages, "fire_lps": fire_lps, "fire_min": fire_min,
            "peak_p": {n: round(p, 3) for n, p in out["res_h"]["pressure"].items()}}


def _simulate(req, out, wnet, z, crit, res):
    """The designed network under the load cases and through a day (simulate.py): res["load_cases"], res["fires"],
    res["day"] and their checks."""
    hnet, prvs = out["hnet"], out["prvs"]
    fire_lps, fire_min = _fire_inputs(req)
    peak_p = out["res_h"]["pressure"]
    res["load_cases"], res["fires"] = wsim.cases(hnet, crit, prvs, peak_p, z["oz"], fire_lps, fire_min)
    night = next(c for c in res["load_cases"] if c["case"] == "night")
    if "max_pressure_m" in crit:                             # the page's maximum: checked at night (16-Nov-2026)
        pm = crit["max_pressure_m"]["value"]
        res["checks"].append({"check": f"night: residual head <= {pm:g} m", "ok": not night["high_n"],
                              "ref": crit["max_pressure_m"]["ref"],
                              "detail": (f"{night['high_n']} junctions above, up to {night['max_p']:g} m at {night['max_at']} - "
                                         f"at night the head is nearly the static one (the OHT's level - the ground): "
                                         f"smaller pipes do not lower it; PRVs (the PRV option suggests them above "
                                         f"{pm:g} m), a lower staging or another zoning do" if night["high_n"] else
                                         f"highest {night['max_p']:g} m"),
                              "check_hi": f"रात: दबाव <= {pm:g} m",
                              "detail_hi": (f"{night['high_n']} junctions ऊपर, {night['max_at']} पर {night['max_p']:g} m तक - "
                                            f"रात में दबाव लगभग static (OHT का स्तर - ज़मीन): छोटे pipes से नहीं घटता; PRV "
                                            f"(PRV का विकल्प {pm:g} m से ऊपर सुझाता है), कम staging या दूसरी zoning से घटता है"
                                            if night["high_n"] else f"सबसे अधिक {night['max_p']:g} m")})
    res["checks"].append({"check": "night (lowest hour)", "ok": True, "note": True, "ref": crit["draw_off_pattern"]["ref"],
                          "detail": f"x {night['factor']:g} of the average: residual head up to {night['max_p']:g} m "
                                    f"at {night['max_at']}",
                          "check_hi": "रात (सबसे कम घंटा)",
                          "detail_hi": f"औसत का x {night['factor']:g}: दबाव {night['max_p']:g} m तक ({night['max_at']} पर)"})
    if res["fires"]:
        bad = [f for f in res["fires"] if f["ok"] is False]
        txt = "; ".join(f"{f['oz']} {f['node']} {f['p']:g} m" for f in res["fires"][:8])
        res["checks"].append({"check": f"fire flow {fire_lps:g} L/s", "ok": not bad, "note": fire_min is None,
                              "ref": wsim.FIRE_REF,
                              "detail": (f"at each OZ's weakest junction with the average demand: {txt}" +
                                         (f" - {len(bad)} below {fire_min:g} m" if bad else
                                          f" - all {fire_min:g} m or more" if fire_min is not None else "")),
                              "check_hi": f"fire flow {fire_lps:g} L/s",
                              "detail_hi": (f"हर OZ के सबसे कमज़ोर junction पर, औसत माँग के साथ: {txt}" +
                                            (f" - {len(bad)} में {fire_min:g} m से कम" if bad else
                                             f" - सब {fire_min:g} m या अधिक" if fire_min is not None else ""))})
    tanks = _tanks(res, z, wnet, hnet, crit)
    if not tanks:
        return
    res["day"] = wsim.day(hnet, crit, tanks, prvs, crit["oht_inflow_hours"]["value"])
    rh = crit["residual_head_m"]["value"]
    dry = {k: t for k, t in res["day"]["tanks"].items() if t["empty_h"]}
    spill = {k: t for k, t in res["day"]["tanks"].items() if t["full_h"] and k not in dry}
    low_h = [r["h"] for r in res["day"]["hours"] if r["low_n"]]
    txt = "; ".join(f"{k} {', '.join(f'{h}-{h + 1} h' for h in t['empty_h'][:4])} ({t['short_kl']:g} KL short)"
                    for k, t in dry.items())
    sp = "; ".join(f"{k} {', '.join(f'{h}-{h + 1} h' for h in t['full_h'][:4])} ({t['spill_kl']:g} KL)"
                   for k, t in spill.items())
    lowest = ", ".join(f"{k} {t['min_pct']:g} %" for k, t in res["day"]["tanks"].items())
    res["checks"].append({"check": "24 h: OHT levels", "ok": not dry and not spill, "ref": crit["esr_capacity_share"]["ref"],
                          "detail": "; ".join(x for x in ((f"runs dry: {txt}" if dry else ""),
                                                          (f"full, the inflow not held (the next day short): {sp}"
                                                           if spill else "")) if x)
                                    or f"no OHT runs dry or over - lowest {lowest}",
                          "check_hi": "24 घंटे: OHT का स्तर",
                          "detail_hi": "; ".join(x for x in ((f"खाली होती है: {txt}" if dry else ""),
                                                             (f"भर जाती है, आया पानी नहीं समाता (अगले दिन कमी): {sp}"
                                                              if spill else "")) if x)
                                       or f"कोई OHT न खाली होती न छलकती - सबसे कम {lowest}"})
    thin = {k: t for k, t in res["day"]["tanks"].items() if k not in dry and t["min_pct"] < wsim.MARGIN_PCT}
    if thin:
        at = {k: min(range(24), key=lambda h: res["day"]["hours"][h]["tanks"][k]["full_pct"]) for k in thin}
        t_ = "; ".join(f"{k} {t['min_pct']:g} % at {at[k]:02d}:00" for k, t in thin.items())
        th_ = "; ".join(f"{k} {t['min_pct']:g} %, {at[k]:02d}:00 बजे" for k, t in thin.items())
        res["checks"].append({
            "check": "24 h: OHT margin", "ok": True, "warn": True, "ref": crit["esr_capacity_share"]["ref"],
            "detail": f"nearly empty in the day (below {wsim.MARGIN_PCT:g} % of the usable water): {t_} - the capacity is "
                      f"just the mass balance, with no margin; a little more draw-off or a late pump and it runs dry "
                      f"(WaterGEMS closes such a tank for that moment) - a larger capacity, longer filling hours or "
                      f"filling in the gap gives a margin",
            "check_hi": "24 घंटे: OHT में गुंजाइश",
            "detail_hi": f"दिन में लगभग खाली ({wsim.MARGIN_PCT:g} % उपयोग योग्य पानी से कम): {th_} - क्षमता ठीक mass "
                         f"balance जितनी, कोई गुंजाइश नहीं; थोड़ी अधिक खपत या pump देर से चले तो खाली हो जाएगी (WaterGEMS "
                         f"ऐसी टंकी को उस पल बंद कर देता है) - अधिक क्षमता, भरने के लंबे घंटे या बीच के अंतराल में भराई से "
                         f"गुंजाइश मिलती है"})
    res["checks"].append({"check": f"24 h: residual head {rh:g} m", "ok": not low_h, "ref": crit["residual_head_m"]["ref"],
                          "detail": (f"below in hours {', '.join(f'{h}-{h + 1}' for h in low_h[:8])}" if low_h else
                                     f"every hour - lowest {min(r['min_p'] for r in res['day']['hours']):g} m"),
                          "check_hi": f"24 घंटे: residual head {rh:g} m",
                          "detail_hi": (f"इन घंटों में कम: {', '.join(f'{h}-{h + 1}' for h in low_h[:8])}" if low_h else
                                        f"हर घंटे - सबसे कम {min(r['min_p'] for r in res['day']['hours']):g} m")})


def _stages(req, hnet, wnet, ohts, z, crit, res, prvs=()):
    """Stage-wise check (CPHEEO Table 2.7 S.No.1, p168: pipes and ESRs for the ultimate stage = base + 30 years,
    pumps for +15 years): the designed network (its pipe sizes and OHT stagings) run again at the demand of the base
    year and of +15 years - each junction's population scaled alike (no fire demand in the network: _node_lps); the
    PRVs hold the heads of their design (prv.shift).
    Lower demand: less head loss, so the residual head rises; the velocities fall (stagnation below 0.3 m/s, 6.6(i)
    p400). Returns [] when no stage population is given."""
    given = ui.stage_inputs(req)
    if not any(k in given for k in ("pop_initial", "pop_mid")):
        return []
    y0 = given.get("base_year")
    city = sum(v["pop"] for v in wnet["nodes"].values())
    rh, rmax = crit["residual_head_m"]["value"], crit["residual_head_max_m"]["value"]
    vmin, vmax = crit["min_velocity_mps"]["value"], crit["max_velocity_mps"]["value"]
    pf, minor = crit["peak_factor"]["value"], crit["minor_loss_factor"]["value"]
    fixed = {n for n, v in hnet["nodes"].items() if v.get("head") is not None}
    plen = {lab: p["length"] for lab, p in hnet["pipes"].items()}
    vbase = {}
    rows, prev = [], None
    for tag, p in (("init", given.get("pop_initial")), ("mid", given.get("pop_mid")), ("ult", city)):
        if not p:
            continue
        sc = p / city if city else 0.0
        net = {"nodes": {n: dict(v) for n, v in hnet["nodes"].items()}, "pipes": hnet["pipes"]}
        for n, v in wnet["nodes"].items():                  # bulk consumers: the same at every stage
            # a junction of a ward with a character: its own share of the stage (_ward_growth, 6-Nov-2026)
            s = v["stage"][tag] if tag != "ult" and "stage" in v else sc
            net["nodes"][n]["demand"], net["nodes"][n]["avg"] = _node_lps(v, crit, city, s)
        r = hy.solve(net, minor_loss=minor, demand_factor=pf)
        wprv.shift(r, prvs)
        pr = {n: x for n, x in r["pressure"].items() if n not in fixed}
        live = {lab: v for lab, v in r["velocity"].items() if not hnet["pipes"][lab].get("closed")
                and lab in wnet["pipes"]}
        slow = [lab for lab, v in live.items() if v < vmin]
        if tag == "init":
            vbase = live
        oz = []
        for o in ohts:
            ps = [x for n, x in pr.items() if z["oz"].get(n) == o["name"]]
            oz.append({"oht": o["name"], "flow_lps": round(r["flow"].get(f"{o['name']} outlet", 0.0), 2),
                       "lowest_p": round(min(ps), 2) if ps else None, "highest_p": round(max(ps), 2) if ps else None})
        avg = sum(v.get("avg", v.get("demand")) or 0.0 for v in net["nodes"].values())
        if prev is not None and p < prev - 0.5:
            res["checks"].append({"check": "stage population", "ok": False, "ref": crit["stages"]["ref"],
                                  "detail": f"{p:,.0f} at +{STAGE_YEARS[tag]} years is less than {prev:,.0f} before it"})
        prev = p
        rows.append({"stage": tag, "years": STAGE_YEARS[tag], "year": y0 + STAGE_YEARS[tag] if y0 else None,
                     "pop": round(p), "avg_lps": round(avg, 2), "avg_mld": round(avg * 0.0864, 3),
                     "peak_lps": round(avg * pf, 2),
                     "min_p": round(min(pr.values()), 2) if pr else None, "max_p": round(max(pr.values()), 2) if pr else None,
                     "low_n": sum(1 for x in pr.values() if x < rh - 1e-6),
                     "over_max_n": sum(1 for x in pr.values() if x > rmax + 1e-6),
                     "slow_n": len(slow), "slow_m": round(sum(plen.get(lab, 0.0) for lab in slow), 1),
                     "fast_n": sum(1 for v in live.values() if v > vmax + 1e-9),
                     "v_max": round(max(live.values()), 3) if live else None, "oz": oz})
    for pp in res["pipes"]:
        if pp["label"] in vbase:
            pp["v_init"] = round(vbase[pp["label"]], 3)
    return rows


def _rising(stem, req, wnet, z, ohts, res, crit):
    """The new tube wells and their rising mains (rising.py, water phase 2 - user decisions 31-Oct-2026): placed on
    the map (req tws) or suggested where the zoning needs more, each pumping to its OHT's top water level (staging of
    the design + side water depth, CPHEEO Table 2.7 S.No.12) through its own main along the roads; the economical
    size, the surge, a check line each. For the page (latlngs), the DPR (T3 friction, T7 / D5) and the DXF."""
    S = wdpr.settings()
    to_xy, ll = ui.converters_for(stem)[1], ui.to_latlng(stem)
    placed = []
    for i, t in enumerate(req.get("tws") or [], 1):
        try:
            placed.append({"name": str(t.get("name") or f"TW {i}"), "xy": to_xy([[float(t["lat"]), float(t["lng"])]])[0],
                           "discharge_lpm": t.get("discharge_lpm")})
        except (KeyError, TypeError, ValueError):
            continue
    swd = lambda kl: next(d for c, d in S["swd"] if c is None or (kl or 0) <= c)

    def _cone(o):              # a new OHT is an Intze tank: its cone below the wall's SWD (user 10-Nov-2026)
        kl = _fill(o)
        return intze.cone_depth(kl, swd(kl)) if kl and kl == o.get("new_kl") else 0.0

    def _fill(o):              # the tank the tube wells fill: the new one where there is one (as the DPR's T3)
        return o.get("new_kl") or o.get("capacity_kl") or o.get("required_kl")
    # an OZ with a CWR (more than 3 new tube wells, UPJN rule): its tube wells fill the CWR - a ground reservoir at the
    # OHT, the tube wells lifting to the ground level (Riverside water DPR p136-195: TW to CWR staging 0, depth of water
    # 0 - user decision 6-Nov-2026) - and its pumps the OHT (R3 'H P Calculation pp': the tube wells of its CWR zones
    # 37 m, of the others 64-72 m; DPR T3 C.5 / C.6)
    cwr = {zn["name"]: zn["cwr_kl"] for zn in z["zones"] if zn.get("cwr_kl")}
    top, gls = {}, {}
    for o in res["outlets"]:
        node = next((x["node"] for x in ohts if x["name"] == o["name"]), None)
        gl = wnet["nodes"].get(node, {}).get("elev")
        gls[o["name"]] = gl
        if gl is not None and o.get("staging_m") is not None:
            top[o["name"]] = gl + (S["pump"]["cwr_water_above_gl_m"] if o["name"] in cwr else
                                   o["staging_m"] + swd(_fill(o)) +
                                   _cone(o))
    need = {zn["name"]: int(zn.get("tubewells_new") or 0) + int(zn.get("tubewells_standby") or 0)
            for zn in z["zones"] if zn["name"] in top}          # standby tube wells too: each its own main
    if not placed and not any(need.values()):
        return None
    auto = {o["name"] for o in res["outlets"] if o.get("proposed")}     # the zoning's OHTs: their tube wells too
    sby = {zn["name"]: int(zn.get("tubewells_standby") or 0) for zn in z["zones"] if zn["name"] in top}
    # the OZs whose suggested tube wells the user took away (user decision 15-Nov-2026): all, or those of the OHT
    # sites given (an OZ found by its OHT's site: the zoning's names change when it runs again)
    sg = (req or {}).get("sug") or {}
    if sg.get("tw_off_all"):
        manual = set(top)
    else:
        manual = {z["oz"].get(n) for n in _near_nodes(stem, wnet, sg.get("tw_off"))} - {None}
    R = wrising.plan(wnet, z, [o for o in ohts if o["name"] in top], placed, crit, wd.load_pipes(), wdpr_rm.laid_rate(S),
                     top, need, below=_tw_below(S), auto=auto, standby=sby, manual=manual)
    r2 = lambda x, d=2: round(x, d) if isinstance(x, float) else x
    tws = []
    for t in R["tws"]:
        row = {k: r2(v) for k, v in t.items() if k not in ("path", "alts", "xy")}
        row["latlng"] = ll(t["xy"])
        if t.get("path"):
            row["path"] = [ll(wnet["nodes"][n]["xy"]) for n in t["path"]]
            if t["snap_m"] > 0.5:
                row["path"].insert(0, ll(t["xy"]))
            row["alts"] = [{k: r2(v, 3 if k in ("v", "hf") else 0 if k in ("pipe", "pumps", "energy", "total") else 2)
                            for k, v in a.items()} for a in t["alts"]]
        tws.append(row)
    out = {"tws": tws, "oz": {k: {kk: r2(vv) if not isinstance(vv, dict) else {s: round(L, 1) for s, L in vv.items()}
                                  for kk, vv in v.items()} for k, v in R["oz"].items()},
           "flags": R["flags"], "top": {k: round(v, 2) for k, v in top.items()}, "cwr": sorted(cwr),
           "dropped": [{"name": d["name"], "oz": d["oz"], "why": d["why"], "latlng": ll(d["xy"])} for d in R["dropped"]],
           "needed": [{"name": t["name"], "oz": t["oz"], "latlng": ll(t["xy"])} for t in R["needed"]],
           "short": R["short"], "manual": sorted(manual),
           "need": need,
           "gl": {k: round(v, 2) for k, v in gls.items() if v is not None}}           # each OHT's ground (DPR static head)
    done = [t for t in tws if t.get("size")]
    lack = {oz: s for oz, s in R["short"].items() if s["have"] < s["need"]}
    if lack:                                          # the user's tube wells too few (user decision 15-Nov-2026)
        v = lambda k: crit[k]["value"]
        one = v("tubewell_discharge_lpm") * v("tubewell_pumping_hours") * 60 / 1000.0      # KL a day, a new tube well
        mid = crit.get("stage_mid_share", {}).get("value", 1.0)
        en, hi = [], []
        for oz, s in sorted(lack.items()):
            zn = next(x for x in z["zones"] if x["name"] == oz)
            p_ = zn["population"] * mid
            kld = ((p_ * v("lpcd") + p_ * v("floating_share") * v("floating_lpcd")) / 1000.0 + (zn.get("bulk_kld") or 0.0)) \
                * v("pumping_main_factor")
            w, sb = int(zn.get("tubewells_new") or 0), int(zn.get("tubewells_standby") or 0)
            en.append(f"{oz}: +15 years demand {kld:,.0f} KLD needs {w} working + {sb} standby tube wells "
                      f"({one:,.0f} KL a day each), the map has {s['have']} - {s['need'] - s['have']} more")
            hi.append(f"{oz}: +15 वर्ष की माँग {kld:,.0f} KLD के लिए {w} चालू + {sb} standby tube wells चाहिए "
                      f"(हर एक {one:,.0f} KL/दिन), नक्शे पर {s['have']} - {s['need'] - s['have']} और चाहिए")
        res["checks"].append({
            "check": "tube wells for the demand", "ok": False, "ref": crit["tubewell_discharge_lpm"]["ref"],
            "detail": "; ".join(en) + " - the design is not complete (the sites suggested for them: on the map)",
            "check_hi": "माँग के लिए tube wells",
            "detail_hi": "; ".join(hi) + " - design अधूरा (उनकी सुझाई जगहें नक्शे पर)"})
    if done:
        L = sum(t["length_m"] for t in done)
        by = {}
        for t in done:
            by[t["size"]] = by.get(t["size"], 0.0) + t["length_m"]
        sz = ", ".join(f"{s} {m:,.0f} m" for s, m in sorted(by.items(), key=lambda kv: _size_order(kv[0])))
        npl = sum(1 for t in done if t["placed"])
        cw = sorted({t["oz"] for t in done if t["oz"] in cwr})
        cw_en = (f"; in {', '.join(cw)} (a CWR) to the CWR, its pumps to the OHT" if cw else "")
        cw_hi = (f"; {', '.join(cw)} में (CWR) CWR तक, उसके pumps OHT तक" if cw else "")
        res["checks"].append({
            "check": "rising mains", "ok": True, "note": True, "ref": crit["rising_main_economics"]["ref"],
            "detail": f"{len(done)} new tube wells ({npl} on the map, {len(done) - npl} suggested), each its own main "
                      f"along the roads to its OHT{cw_en}: {L:,.0f} m - {sz}; economical size, friction "
                      f"{max(t['hf_m'] for t in done):.2f} m at most",
            "check_hi": "rising mains",
            "detail_hi": f"{len(done)} नए tube wells ({npl} नक्शे पर, {len(done) - npl} सुझाए), हर एक की अपनी main सड़क के "
                         f"रास्ते OHT तक{cw_hi}: {L:,.0f} m - {sz}; economical size, घर्षण अधिकतम {max(t['hf_m'] for t in done):.2f} m"})
        if R["dropped"]:
            au = sorted({d["oz"] for d in R["dropped"] if d["why"] == "auto"})
            ex = sorted({d["oz"] for d in R["dropped"] if d["why"] == "extra"})
            res["checks"].append({
                "check": "tube wells of the map left out", "ok": True, "note": True,
                "ref": "user decision 15-Nov-2026: only as many tube wells as the OZ needs",
                "detail": f"{len(R['dropped'])} not taken"
                          + (f"; {', '.join(au)}: OHT proposed by the zoning - its tube wells suggested with it" if au else "")
                          + (f"; {', '.join(ex)}: more on the map than needed - the nearest to the OHT taken" if ex else ""),
                "check_hi": "नक्शे के tube wells छोड़े",
                "detail_hi": f"{len(R['dropped'])} नहीं लिए"
                             + (f"; {', '.join(au)}: OHT zoning ने proposed की - उसके tube wells भी उसी के साथ सुझाए" if au else "")
                             + (f"; {', '.join(ex)}: ज़रूरत से ज़्यादा - OHT के सबसे पास वाले लिए" if ex else "")})
        k9 = [t for t in done if t.get("cls") == "K9"]
        if k9:
            s = (f"{len(k9)} DI mains in K9: K-7's AOP 0.8 / MOP 1.25 MPa exceeded by the head / head + surge (" +
                 ", ".join(f"{t['name']} {t['head_m']:g} + {t['surge_m']:g} m" for t in k9[:4]) + (" ..." if len(k9) > 4 else "") + ")")
            res["checks"].append({"check": "rising main class", "ok": True, "note": True, "ref": crit["di_k9"]["ref"],
                                  "detail": s, "check_hi": "rising main की class",
                                  "detail_hi": f"{len(k9)} DI mains K9 में: K-7 की AOP 0.8 / MOP 1.25 MPa head / head + surge "
                                               f"से पार (DPR D5 में K9 की UPJN rate, M.193)"})
        bad = [t for t in done if not t["surge_ok"]]
        if bad:
            s = "; ".join((f"{t['name']} {t['size']}: head {t['head_m']:g} m > AOP {t['aop_m']:g} m" if t["head_m"] > t["aop_m"]
                           else f"{t['name']} {t['size']}: {t['head_m']:g} + surge {t['surge_m']:g} = {t['max_m']:g} m > MOP "
                                f"{t['rating_m']:g} m") for t in bad[:6]) + (f" ... ({len(bad)} mains)" if len(bad) > 6 else "")
            res["checks"].append({"check": "rising main surge", "ok": False, "ref": crit["surge"]["ref"],
                                  "detail": s + " - a higher pipe class, or surge protection (NRV + air vessel / surge "
                                                "anticipation valve, CPHEEO 6.16.10)",
                                  "check_hi": "rising main surge (water hammer)",
                                  "detail_hi": s + " - pipe की ऊँची class, या surge से बचाव (NRV + air vessel / surge "
                                                   "anticipation valve, CPHEEO 6.16.10)"})
    for f in R["flags"]:
        res["checks"].append({"check": "tube well site", "ok": False, "ref": crit["tubewell_spacing_m"]["ref"],
                              "detail": f, "check_hi": "tube well की जगह", "detail_hi": hindi.hi(f)})
    return out


def _tw_below(S):
    """The pumping water level of a tube well under its ground (m): water level + seasonal variation + depression during
    pumping (Riverside water DPR 'Calculation of static head', user decision 6-Nov-2026)."""
    P = S["pump"]
    return P["water_below_gl_m"] + P["seasonal_m"] + P["depression_m"]


def _size_order(name):
    return (not name.startswith("HDPE"), int("".join(c for c in name if c.isdigit()) or 0))


def prv_on(req):
    """The page's PRV option (user 31-Oct-2026: an option, off by default - PRVs are not in the U.P. Jal Nigam DPRs)."""
    return str(req.get("use_prv") or "").strip().lower() in ("1", "true", "yes", "on")


def _pressure_summary(hnet, res_h, r, crit):
    """A solved network's pressures into the design's summary and its residual-head check (the first check);
    returns the junctions well above the upper limit of the residual head."""
    rh = crit["residual_head_m"]["value"]
    low, _, _, high = wd.check(hnet, res_h, crit)
    fixed_n = {n for n, v in hnet["nodes"].items() if v.get("head") is not None}
    pr = [p for n, p in res_h["pressure"].items() if n not in fixed_n]
    r["summary"]["min_pressure"] = round(min(pr), 2) if pr else None
    r["summary"]["max_pressure"] = round(max(pr), 2) if pr else None
    r["checks"][0].update(ok=not low, detail=(f"{len(low)} junctions below" if low else f"lowest {min(pr):.2f} m"))
    r["missing_head_m"] = round(max(rh - p for p in low.values()), 2) if low else None
    return high


def _after_prv(hnet, res_h, r, crit):
    """The design's summary and pressure checks again, its areas' heads lowered by the PRVs."""
    high = _pressure_summary(hnet, res_h, r, crit)
    name = f"residual head well above {crit['residual_head_max_m']['value']} m"
    r["checks"] = [c for c in r["checks"] if c["check"] != name]
    if high:
        r["checks"].insert(3, {"check": name, "ref": crit["residual_head_max_m"]["ref"], "ok": True, "note": True,
                               "detail": f"{len(high)} junctions above {crit['residual_head_max_m']['value'] + 10:g} m"
                                         f" - consider PRV / smaller staging"})


def _prv_res(res, prvs, sugg, geo, pipes, z, ll):
    """The PRVs and the suggested ones for the page, the DPR and the DXF: where (half way along its pipe), its pipe's
    size and flow, and a line in the checks each (English / Hindi). sugg: prv.suggest()."""
    sugg, left = sugg
    by = {p["label"]: p for p in pipes}
    at = lambda lab: ll(_mid_along(geo[lab])) if lab in geo and len(geo[lab]) > 1 else None
    res["prvs"] = []
    for p in prvs:
        pp = by.get(p.get("pipe")) or {}
        row = {k: v for k, v in p.items() if k not in ("area", "h_set")}
        row.update(latlng=at(p.get("pipe")), size=pp.get("size"), flow=pp.get("flow"), oz=z["oz"].get(p.get("down")),
                   dma=z["dma"].get(p.get("down")))
        res["prvs"].append(row)
        if row["active"]:
            s = (f"on {row['pipe']} ({row['size']}, {abs(row['flow'] or 0):g} L/s) towards {row['down']}: setting "
                 f"{row['setting_m']:g} m{' (by itself)' if row['auto'] else ''}, -{row['cut_m']:g} m on {row['nodes']} "
                 f"junctions, highest {row['max_before']:g} -> {row['max_after']:g} m")
            h = (f"{row['pipe']} पर ({row['size']}, {abs(row['flow'] or 0):g} L/s) {row['down']} की ओर: setting "
                 f"{row['setting_m']:g} m{' (अपने-आप)' if row['auto'] else ''}, {row['nodes']} junctions पर -{row['cut_m']:g} m, "
                 f"अधिकतम {row['max_before']:g} -> {row['max_after']:g} m")
            ok = not row.get("low")
            if row.get("low"):
                s += f"; {row['low']} junctions below 17 m - raise the setting"
                h += f"; {row['low']} junctions 17 m से कम - setting बढ़ाएँ"
        else:
            s = f"on {row['pipe'] or '-'}: " + (row.get("note") or "")
            h = f"{row['pipe'] or '-'} पर: " + hindi.hi(row.get("note") or "")
            ok = bool(row.get("pipe")) and "loop" not in (row.get("note") or "") and "closed" not in (row.get("note") or "")
        res["checks"].append({"check": f"PRV {row['name']}", "ok": ok, "note": ok, "ref": PRV_REF, "detail": s,
                              "check_hi": f"PRV {row['name']}", "detail_hi": h})
    res["prv_suggest"] = []
    for g in sugg:
        pp = by.get(g["pipe"]) or {}
        res["prv_suggest"].append(dict(g, latlng=at(g["pipe"]), size=pp.get("size"), flow=pp.get("flow"),
                                       oz=z["oz"].get(g["down"]), dma=z["dma"].get(g["down"])))
    res["prv_left"] = left
    if sugg or (left and prvs):
        s = "; ".join(f"{g['pipe']} ({g['nodes']} junctions, -{g['cut_m']:g} m, above 31 m {g['high_before']} -> "
                      f"{g['high_after']})" for g in sugg)
        h = "; ".join(f"{g['pipe']} ({g['nodes']} junctions, -{g['cut_m']:g} m, 31 m से ऊपर {g['high_before']} -> "
                      f"{g['high_after']})" for g in sugg)
        if sugg:
            s += " - place them on the map (Design view) and run the design again"
            h += " - नक्शे पर रखें (Design view) और design दोबारा चलाएँ"
        if left:
            s += (f"{'; ' if sugg else ''}{left} junctions above 31 m left on small branches (fewer than "
                  f"{wprv.MIN_GAIN} for one PRV) - a PRV by hand there if wanted")
            h += (f"{'; ' if sugg else ''}{left} junctions 31 m से ऊपर छोटी शाखाओं पर बचे (एक PRV पर "
                  f"{wprv.MIN_GAIN} से कम) - चाहें तो वहाँ हाथ से PRV रखें")
        res["checks"].append({"check": "PRV suggested", "ok": True, "note": True, "ref": PRV_REF, "detail": s,
                              "check_hi": "सुझाए PRV", "detail_hi": h})


PRV_REF = ("CPHEEO Table 2.7 S.No.10 p173: 17-21 m; user 30-Oct-2026: a PRV where junctions are above 31 m, its setting "
           "the lowest keeping 17 m beyond it")


def _design_once(stem, req, folder, net, wnet, ohts, crit, z, lines):
    if not ohts:
        raise ValueError("कोई OHT नहीं - Layout / आबादी देखें")
    rh = crit["residual_head_m"]["value"]
    smax = crit["max_staging_m"]["value"] if "max_staging_m" in crit else math.inf     # a constraint of the page
    auto, vfd = {}, {}            # OHT -> trial staging (none given) / trial head of an existing one with a VFD
    for o in ohts:
        if o["staging_m"] is not None and o.get("low_head") != "vfd":
            continue
        mem = [n for n, k in z["oz"].items() if k == o["name"]]
        top = max((wnet["nodes"][n]["elev"] for n in mem if wnet["nodes"][n].get("elev") is not None), default=None)
        gl = wnet["nodes"][o["node"]].get("elev")
        far = max((z["dist"].get(n, 0.0) for n in mem), default=0.0) / 1000.0
        allow = min(10.0, max(2.0, crit["zoning_head_loss_m_per_km"]["value"] * far))   # head loss to the farthest node
        static = (top - gl if top is not None and gl is not None else 0.0) + rh
        if o["staging_m"] is None:
            auto[o["name"]] = o["_eff"] = o["staging_m"] = min(math.ceil(max(static + allow, 10.0) * 2) / 2, smax)
        else:
            # its staging, when the ground allows 17 m (the pipes are sized for it); else a trial with a pump
            # (a small allowance: the pipes rather than the pump take the head loss - the pump as small as it can be)
            allow_v = min(10.0, max(1.0, crit["existing_oht_head_loss_m_per_km"]["value"] * far))
            vfd[o["name"]] = o["_eff"] = (o["staging_m"] if static <= o["staging_m"]
                                          else math.ceil((static + allow_v) * 2) / 2)
    no_gl = [n for n, v in wnet["nodes"].items() if v.get("elev") is None]
    if no_gl:
        raise ValueError(f"{len(no_gl)} nodes का GL नहीं है - Layout में GL (spot levels / समतल GL) दें")
    city = sum(v["pop"] for v in wnet["nodes"].values())
    hnet = {"nodes": {}, "pipes": {}}
    for n, v in wnet["nodes"].items():
        q, avg = _node_lps(v, crit, city)
        hnet["nodes"][n] = {"elev": v["elev"], "demand": q, "avg": avg}
    for lab, p in wnet["pipes"].items():
        hnet["pipes"][lab] = dict(p, closed=lab in set(z["closed_pipes"]))
    # the pipe table's sizes: kept as given (the design never resizes a fixed pipe)
    edits = edits_of(req)
    cat = {s["name"]: s for s in wd.load_pipes()}
    given = {}
    for lab, x in edits["pipes"].items():
        if lab in hnet["pipes"]:
            s = given[lab] = cat[x["size"]]
            hnet["pipes"][lab].update(fixed=True, d_mm=s["id_mm"], C=s["C"])
    for s_ in [x for x in wnet.get("notes", []) if x not in lines]:
        lines.append(s_)
    for o in ohts:                                    # the OHT: a fixed head at its lowest water level, a short main
        src = f"{o['name']}"
        gl = wnet["nodes"][o["node"]]["elev"]
        hnet["nodes"][src] = {"elev": gl, "head": gl + o.get("_eff", o["staging_m"])}
        hnet["pipes"][f"{o['name']} outlet"] = {"a": src, "b": o["node"], "length": 20.0}
    allowed = wd.allowed_pipes(crit)                     # the page's size limits (16-Nov-2026)
    cases = design_cases(req, crit)
    r = wd.design(hnet, crit, pipes=allowed, log=lines.append, max_rounds=DESIGN_ROUNDS, cases=cases)
    # the fire flow at each OZ's weakest junction of the design: designed again with it too; the weakest move as the
    # pipes change - each new set a load of its own, until they no longer move (at most FIRE_PASSES designs more)
    fires, covered = [], set()
    for k in range(FIRE_PASSES):
        fire = fire_case(req, crit, r["result"], z)
        if not fire:
            break
        new = {n: q for n, q in fire["extra"].items() if n not in covered}
        if not new:
            break
        covered |= set(new)
        fires.append(dict(fire, extra=new, name=fire["name"] + (f" (set {k + 1})" if k else "")))
        lines.append(f"\n-- fire flow {fire['extra_lps']:g} L/s at {', '.join(sorted(new))}: design again with it")
        r = wd.design(hnet, crit, pipes=allowed, log=lines.append, max_rounds=DESIGN_ROUNDS, cases=cases + fires)
    res_h = r["result"]
    staging_note = {}
    if auto or vfd:
        # each OHT without a staging: lowered to what the designed pipes need (17 m at its OZ's weakest node); an
        # existing one with a VFD: its staging, the pump adding what is still missing
        for o in ohts:
            if o["name"] not in auto and o["name"] not in vfd:
                continue
            ps = [res_h["pressure"][n] for n, k in z["oz"].items() if k == o["name"] and n in res_h["pressure"]]
            low = min(ps) if ps else rh
            spare = low - rh
            for c in r.get("cases", {}).values():          # the other loads designed for: their spare head too
                pc = [c["result"]["pressure"][n] for n, k in z["oz"].items() if k == o["name"] and n in c["result"]["pressure"]]
                if pc:
                    spare = min(spare, min(pc) - c["min_head"])
            need = math.ceil((o["_eff"] - spare) * 2) / 2
            if o["name"] in auto:
                want = need
                need = min(need, smax)
                o["staging_m"] = o["_eff"] = need
                staging_note[o["name"]] = {"trial": auto[o["name"]], "required": need, "wanted": want}
            else:
                o["_vfd"] = max(0.0, need - o["staging_m"])
                o["_eff"] = o["staging_m"] + o["_vfd"]
            hnet["nodes"][o["name"]]["head"] = hnet["nodes"][o["name"]]["elev"] + o["_eff"]
        res_h = hy.solve(hnet, minor_loss=crit["minor_loss_factor"]["value"], demand_factor=crit["peak_factor"]["value"])
        r["result"] = res_h
        _pressure_summary(hnet, res_h, r, crit)
        for nm, v in staging_note.items():
            if v["wanted"] > smax + 1e-9:
                r["checks"].append({"check": f"{nm}: staging limit {smax:g} m", "ok": False,
                                    "ref": crit["max_staging_m"]["ref"],
                                    "detail": f"it would need {v['wanted']:g} m - kept at {smax:g} m: junctions stay below "
                                              f"17 m (larger pipes cannot help) - another site (higher ground), a booster "
                                              f"or a higher limit",
                                    "check_hi": f"{nm}: staging की सीमा {smax:g} m",
                                    "detail_hi": f"{v['wanted']:g} m चाहिए - {smax:g} m पर रखा: कुछ junctions 17 m से नीचे रहेंगे "
                                                 f"- दूसरी जगह (ऊँची ज़मीन), booster या सीमा बढ़ाएँ"})
            if v["required"] > 30:
                r["checks"].append({"check": f"{nm}: staging {v['required']:g} m", "ok": True, "note": True,
                                    "ref": crit["residual_head_m"]["ref"],
                                    "detail": "more than 30 m - consider another site (higher ground) or a booster"})
    # the PRVs placed on the map (prv.py, user 30-Oct-2026): their areas' heads lowered; where junctions are still
    # above 31 m, PRVs suggested
    geo = {c["label"]: [tuple(p) for p in c.get("vertices") or []] or
           [tuple(wnet["nodes"][c[k]]["xy"]) for k in ("start_node", "stop_node") if c[k] in wnet["nodes"]]
           for c in net["conduits"] if c["label"] in hnet["pipes"]}
    # PRVs are an option of the page, off by default (user 31-Oct-2026: no U.P. Jal Nigam DPR has them)
    use_prv = prv_on(req)
    tree = wprv.Tree(hnet)
    prvs = wprv.apply(hnet, res_h, wprv.snap(req.get("prvs"), geo, ui.converters_for(stem)[1]), crit, tree) \
        if use_prv else []
    if any(p["active"] for p in prvs):
        _after_prv(hnet, res_h, r, crit)
    sugg = wprv.suggest(hnet, res_h, crit, {p["pipe"] for p in prvs if p.get("pipe")}, tree) if use_prv else ([], 0)
    ll = ui.to_latlng(stem)
    xy = {n: v["xy"] for n, v in wnet["nodes"].items()}
    vmax, vmin = crit["max_velocity_mps"]["value"], crit["min_velocity_mps"]["value"]
    pipes = []
    for c in net["conduits"]:
        lab = c["label"]
        s = given.get(lab) or r["size"].get(lab)
        v_ = res_h["velocity"].get(lab, 0.0)
        closed = hnet["pipes"][lab].get("closed", False)
        chk = [] if closed else ([f"v > {vmax:g} m/s"] if v_ > vmax + 1e-9 else []) + \
            ([f"v < {vmin:g} m/s (note)"] if 1e-9 < v_ < vmin else [])
        pipes.append({"label": lab, "from": c["start_node"], "to": c["stop_node"], "length": round(c["length_m"], 1),
                      "size": s["name"] if s else None, "nominal": s["nominal"] if s else None,
                      "id_mm": s["id_mm"] if s else None, "closed": closed,
                      "flow": round(res_h["flow"].get(lab, 0.0), 3), "v": round(v_, 3),
                      "hl_km": round(res_h["hl_per_km"].get(lab, 0.0), 2), "oz": z["oz"].get(c["start_node"]),
                      "dma": z["dma"].get(c["start_node"]), "edited": lab in given, "checks": chk})
    nodes = []
    for n, v in wnet["nodes"].items():
        nodes.append({"label": n, "latlng": ll(xy[n]), "gl": v["elev"], "head": round(res_h["head"].get(n, float("nan")), 3)
                      if n in res_h["head"] else None, "p": round(res_h["pressure"][n], 2) if n in res_h["pressure"] else None,
                      "q": round(hnet["nodes"][n]["demand"] * crit["peak_factor"]["value"], 4), "oz": z["oz"].get(n),
                      "dma": z["dma"].get(n), "pop": round(v.get("pop") or 0.0, 1), "edited": n in edits["junctions"],
                      "checks": [f"residual head < {rh:g} m"] if n in res_h["pressure"] and res_h["pressure"][n] < rh - 1e-6
                      else []})
    outlets = []
    for o in ohts:
        lab = f"{o['name']} outlet"
        s = r["size"].get(lab)
        lowest = min((res_h["pressure"][n] for n in wnet["nodes"] if z["oz"].get(n) == o["name"] and n in res_h["pressure"]),
                     default=None)
        zr = next((x for x in z["zones"] if x["name"] == o["name"]), {})
        q = res_h["flow"].get(lab, 0.0)
        pump = o.get("_vfd") or None
        outlets.append({"low_head": o.get("low_head"), "vfd_head_m": pump,
                        "vfd_kw": round(9.81 * q / 1000.0 * pump / crit["vfd_efficiency"]["value"], 1) if pump else None,"name": o["name"], "latlng": o["latlng"], "staging_m": o["staging_m"],
                        "staging_auto": o["name"] in staging_note, "proposed": bool(o.get("proposed")),
                        "existing": o.get("capacity_kl") is not None, "capacity_kl": o.get("capacity_kl"),
                        "required_kl": zr.get("required_kl"), "cwr_kl": zr.get("cwr_kl"),
                        # the new OHT of the OZ: its need, or the shortfall beside a short existing one (24-Nov-2026)
                        "new_kl": intze.new_kl(zr.get("required_kl"), o.get("capacity_kl"),
                                               crit["oht_capacity_round_kl"]["value"]) or None,
                        "population": zr.get("population"), "dmas": zr.get("dma_count"),
                        "flow": round(res_h["flow"].get(lab, 0.0), 2), "size": s["name"] if s else None,
                        "lowest_p": round(lowest, 2) if lowest is not None else None,
                        # an OHT whose (given) staging cannot give 17 m in its OZ: how much more head it needs
                        "short_m": round(rh - lowest, 2) if lowest is not None and lowest < rh - 1e-6 else None})
    lows = [n for n in wnet["nodes"] if n in res_h["pressure"] and res_h["pressure"][n] < rh - 1e-6]
    if lows:
        by_oz = {}
        for n in lows:
            by_oz[z["oz"].get(n)] = by_oz.get(z["oz"].get(n), 0) + 1
        hope = set(r.get("hopeless", []))
        why = []
        for o in outlets:
            if o["name"] in by_oz:
                nh = sum(1 for n in lows if z["oz"].get(n) == o["name"] and n in hope)
                why.append(f"{o['name']}: {by_oz[o['name']]} junctions" +
                           (f", its staging {o['staging_m']:g} m is {o['short_m']:g} m short" if o["short_m"] else "") +
                           (f" - no pipe size helps {nh} of them (on the way to lower ground)" if nh else "") +
                           (f" - {by_oz[o['name']] - nh} not reached in {DESIGN_ROUNDS} rounds of upsizing"
                            if by_oz[o["name"]] - nh else ""))
        r["checks"][0]["detail"] = f"{len(lows)} junctions below - " + "; ".join(why)
    for o in outlets:
        if o["vfd_head_m"]:
            r["checks"].append({"check": f"{o['name']}: VFD pump at the outlet", "ok": True, "note": True,
                                "ref": crit["residual_head_m"]["ref"].split(":")[0] + " S.No.10 p173 (existing ESRs)",
                                "detail": f"+{o['vfd_head_m']:g} m at {o['flow']:g} L/s (peak), about {o['vfd_kw']:g} kW "
                                          f"(efficiency {crit['vfd_efficiency']['value']:g}) - its staging "
                                          f"{o['staging_m']:g} m cannot give 17 m; the OZ stays what its capacity "
                                          f"serves, the pump takes the staging as suction head, stops when the tank "
                                          f"runs dry, bypass inlet-outlet, run from a sensor at the critical node"})
    for c in r["checks"]:
        if c["check"] == "every junction connected to an OHT":
            c["detail"] = _unserved_note(wnet, res_h["unsupplied"])
    summ = r["summary"]
    summ["missing_head_m"] = r["missing_head_m"]
    summ["demand_avg_lps"] = round(sum(v.get("avg", v.get("demand")) or 0.0 for v in hnet["nodes"].values()), 2)
    summ["population"] = round(city)
    res = {"ok": True, "pipes": pipes, "nodes": nodes, "sizes": list(cat), "edits": edits, "outlets": outlets,
           "checks": r["checks"], "summary": summ,
           "unsupplied_pts": [ll(xy[n]) for n in res_h["unsupplied"] if n in xy],
           "log": "\n".join(lines), "closed": len(z["closed_pipes"])}
    _prv_res(res, prvs, sugg, geo, pipes, z, ll)
    res["prv_option"] = use_prv
    if not use_prv and req.get("prvs"):
        n = len(req["prvs"])
        res["checks"].append({"check": "PRV", "ok": True, "note": True, "ref": PRV_REF,
                              "detail": f"{n} PRVs on the map not used - the PRV option of the page is off",
                              "check_hi": "PRV", "detail_hi": f"नक्शे के {n} PRV उपयोग नहीं हुए - page पर PRV का विकल्प बंद है"})
    return {"res": res, "res_h": res_h, "staging_note": staging_note, "rh": rh, "hnet": hnet, "prvs": prvs,
            "hopeless": {n for n in r.get("hopeless", []) if res_h["pressure"].get(n, rh) < rh - 0.005}}
