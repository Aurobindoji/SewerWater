"""One sewer design run without SewerGEMS - the population-mode path of the original scripts sewer_design.py main()
(--ask / --use-inputs): loads from the population, design flows, design (free or with fixed outfall
levels + pipe-cost economising), initial-stage velocities, flushing manholes.

    from sewer_app import network, pipeline
    net = network.read_extract_csv("oakdale_manholes.csv", "oakdale_conduits.csv", outfalls=["O-1"])
    out = pipeline.run(net, inputs)

inputs = the dict of inputs\\<model>_sewer_inputs.json in the original scripts (same keys):
    catalog, joint, fixed {outfall: invert}, trunk, pop_total, pop_dist (equal | length | csv), pop_csv,
    sewage_lpcd, infil_basis (none | km | manhole), infil_rate, peak ("table" or a number),
    pop_initial (optional), start_depth (optional)
    pop_mid, base_year (optional): the stage-wise check (stage_table) - population at +15 years, year of pop_initial
    pop_scale (optional): factor on the pop_csv populations (wards sharing out the forecast design population);
    forecast (optional): population.forecast of the page, kept for the DPR
Only pop_source "input" exists here (there is no model holding loads).

    data_grade (optional): "DPR" (default) or "PFR"
Only pop_source "input" exists here (there is no model holding loads).

Manhole spacing: new manholes are planned and the network is split there (net_split, made); the design
itself stays on the original conduits, as in sewer_design.py.

Data grade (user decision 12-Oct-2026): ground levels from a DEM or filled in by hand (mock / assumed) are good
for a PFR only, not for a DPR. A node whose gl_source names such a source (GL_PFR_SOURCES) makes the whole run
PFR, whatever the input says; the grade and the GL sources are in the result ("grade", "gl_sources") and are
printed on the report and the drawing.
"""
import collections
import copy

from . import DesignError, check, spacing
from .criteria import Rules, load_catalog, load_criteria, val
from .design import design_network, economise_sizes, plan_flushing, raise_to_fixed_outfalls
from .flows import average_flows, cut_heads, design_flows, distribute_population, share_cut_heads
from .hydraulics import uniform_flow
from .network import design_inputs

GL_PFR_SOURCES = ("dem", "mock", "assumed", "estimated", "google", "srtm", "pfr layout")
STAGE_POPS = {"pop_initial": "init", "pop_mid": "mid"}      # input key -> tag of the conduit's q_ / v_ / dd_ fields
STAGE_YEARS = {"init": 0, "mid": 15, "ult": 30}               # years from the base year, CPHEEO Table 2.1 (p2-9)


def stage_table(inp, res, flows, stage_flows, R, warnings, pop, avg):
    """One row per stage - base year, +15 years, +30 years (the design) - with its population, the average and peak
    flow at every outfall (pumping machinery and STP are designed for +15 years, sewers for +30: CPHEEO Table 2.1,
    p2-9; the outfall manhole's own population counted there too, at the peak factor of the sewer bringing the most)
    and the sewers below the self-cleansing velocity of that stage (Table 3.9, p3-26: 0.6 m/s at the initial
    peak, 0.8 m/s at the ultimate peak; the manual gives none for +15 years - shown against 0.6 m/s for information)."""
    y0 = inp.get("base_year")
    y0 = int(float(y0)) if y0 not in (None, "") else None
    pops = {"init": inp.get("pop_initial"), "mid": inp.get("pop_mid"), "ult": inp.get("pop_total")}
    fls = {"init": stage_flows.get("pop_initial"), "mid": stage_flows.get("pop_mid"), "ult": flows}
    ends = {r["to"] for r in flows.values()} - {r["from"] for r in flows.values()}
    tot_p = sum(pop.values())
    rows, prev = [], None
    for tag in ("init", "mid", "ult"):
        fl = fls[tag]
        if not fl or not pops[tag]:
            continue
        p = float(pops[tag])
        sc = p / tot_p if tot_p and tag != "ult" else 1.0
        if prev is not None and p < prev[1] - 0.5:
            warnings.append(f"stage population: {p:,.0f} at +{STAGE_YEARS[tag]} years is LESS than {prev[1]:,.0f} at "
                            f"+{STAGE_YEARS[prev[0]]} years - check the population forecast (CPHEEO 2.6, p2-9)")
        prev = (tag, p)
        if tag == "ult":
            v_of, lim, rule = (lambda d: d["v"]), R.vmin, "Table 3.9 p3-26 (ultimate peak)"
        else:
            v_of, lim = (lambda d, t=tag: d.get(f"v_{t}")), R.vmin_init
            rule = "Table 3.9 p3-26 (initial peak)" if tag == "init" else "information only (no limit in the manual)"
        slow = [d for d in res.values() if d["q"] and lim is not None and (v_of(d) is None or v_of(d) < lim - 1e-9)]
        vs = [v_of(d) for d in res.values() if d["q"] and v_of(d) is not None]
        dds = [d.get("dd" if tag == "ult" else f"dd_{tag}") for d in res.values()]
        outs = []
        for o in sorted(ends):
            rr = [r for r in fl.values() if r["to"] == o]
            a = sum(r["A"] for r in rr) + avg.get(o, 0.0) * sc
            pf = max(rr, key=lambda r: r["P"])["pf"]
            outs.append({"outfall": o, "pop": round(sum(r["P"] for r in rr) + pop.get(o, 0.0) * sc),
                         "avg_lps": round(a, 2), "avg_mld": round(a * 0.0864, 3),
                         "peak_lps": round(sum(r["Q"] for r in rr) + avg.get(o, 0.0) * sc * pf, 2)})
        rows.append({"stage": tag, "years": STAGE_YEARS[tag], "year": y0 + STAGE_YEARS[tag] if y0 else None,
                     "pop": round(p), "v_limit": lim, "v_rule": rule, "v_min": round(min(vs), 3) if vs else None,
                     "slow_n": len(slow), "slow_m": round(sum(d["length"] or 0.0 for d in slow), 1),
                     "dd_max": round(max(x for x in dds if x is not None), 3) if any(x is not None for x in dds) else None,
                     "outfalls": outs})
    return rows


def data_grade(net, wanted="DPR"):
    """(grade, {GL source: number of nodes}, [nodes whose GL is good for a PFR only])."""
    srcs, pfr = collections.Counter(), []
    for n, v in net["nodes"].items():
        src = str(v.get("gl_source") or ("" if v.get("ground") is not None else "no GL")).strip() or "not stated"
        srcs[src] += 1
        if any(k in src.lower() for k in GL_PFR_SOURCES):
            pfr.append(n)
    grade = "PFR" if (str(wanted or "DPR").upper() == "PFR" or pfr) else "DPR"
    return grade, dict(srcs), pfr


def run(net, inp, crit=None, log=print, economise=True, split=True, fixed_inv=None):
    """fixed_inv = {manhole: outgoing invert} given by the user (edits.apply); a conduit's force_D / force_slope
    (edits.apply) are taken as given by the design."""
    crit = copy.deepcopy(crit or load_criteria())
    R = Rules(crit)
    R.fixed_inv = dict(fixed_inv or {})
    lines, warnings = [], []

    def note(s):
        lines.append(s)
        log(s)

    if inp.get("start_depth"):
        cov, manual = R.set_start_depth(inp["start_depth"])
        if abs(cov - manual) > 1e-6:
            # as sewer_design.py: the user's start depth replaces min_cover_m for this run (design and final check)
            mc = crit["sewer"].setdefault("min_cover_m", {})
            mc["value"] = cov
            mc["note"] = (f"PROJECT DECISION (user input): start depth to invert {float(inp['start_depth']):g} m "
                          f"-> earth cover over the crown {cov:.2f} m (manual value in design_criteria.json: "
                          f"{manual:g} m). " + str(mc.get("note") or ""))
            note(f"start depth to invert {float(inp['start_depth']):g} m (user) -> minimum earth cover over the "
                 f"crown {cov:.2f} m instead of {manual:g} m (design_criteria.json)")
            if cov < manual - 1e-6:
                warnings.append(f"cover {cov:.2f} m over the crown is LESS than min_cover_m {manual:g} m of "
                                f"design_criteria.json ({(mc.get('page') or '').split(' - ')[0]}) - user decision "
                                f"(start depth {float(inp['start_depth']):g} m); check house connections and "
                                f"protection under roads")
    crit["sewer"].setdefault("trunk_conduits", {})["value"] = list(inp.get("trunk") or [])
    cat_name, cat_src, sizes = load_catalog(inp.get("catalog"), inp.get("joint") or "ss")

    grade, gl_sources, pfr_nodes = data_grade(net, inp.get("data_grade"))
    if pfr_nodes and str(inp.get("data_grade") or "DPR").upper() != "PFR":
        warnings.append(f"data grade PFR (not DPR): {len(pfr_nodes)} ground level(s) from DEM / assumed data, e.g. "
                        f"{', '.join(pfr_nodes[:10])} - survey levels are needed for a DPR")
    note(f"data grade {grade}; GL sources: " + ", ".join(f"{k} {v}" for k, v in sorted(gl_sources.items())))
    n_interp = sum(1 for v in net["nodes"].values() if "interpolated along the sewer" in str(v.get("gl_source") or ""))
    if n_interp:
        warnings.append(f"{n_interp} ground level(s) of {len(net['nodes'])} were not in the drawing and were interpolated "
                        f"along the sewer (repair.fill_gl; oakdale test: error median 0.22 m, 90 % below 0.9 m) - depth "
                        f"and cover there are uncertain; take levels on site before a DPR")
    data, ground, xy = design_inputs(net)
    outfalls = set(net["outfalls"])
    manholes = [n for n in net["nodes"] if n not in outfalls]
    used = {k["start_node"] for k in data["conduits"]} | {k["stop_node"] for k in data["conduits"]}
    missing = sorted(used - set(ground))
    if missing:
        warnings.append(f"no ground level for: {', '.join(missing[:20])} (cover not controlled there)")
    fixed = {o: float(v) for o, v in (inp.get("fixed") or {}).items()}
    unknown = [o for o in fixed if o not in outfalls]
    if unknown:
        raise DesignError(f"fixed outfall level for a node that is not an outfall: {', '.join(unknown)}")

    # ---- loads and design flows
    lpcd = inp.get("sewage_lpcd")
    if not lpcd:
        raise DesignError("sewage_lpcd (water supply x return factor) is not given")
    pop = distribute_population(inp["pop_total"], inp.get("pop_dist") or "equal", data, manholes,
                                inp.get("pop_csv"))
    if (inp.get("pop_dist") or "equal") == "csv" and inp.get("pop_scale"):
        # the file's (wards') population shares out the design population (population forecast, ui.design_inputs)
        pop = {m: p * float(inp["pop_scale"]) for m, p in pop.items()}
        note(f"population file scaled x {float(inp['pop_scale']):.4f} to the design population {inp['pop_total']:,.0f}")
    if (inp.get("pop_dist") or "equal") == "csv":
        shared = share_cut_heads(pop, data, cut_heads(net["nodes"]))
        if shared:
            note(f"population file: {len(shared)} cut-end head manhole(s) given their share of their manhole's "
                 f"population by sewer length ({sum(r['population'] for r in shared):,.0f} persons moved, total "
                 f"unchanged): " + ", ".join(f"{r['head']} {r['population']:.0f}" for r in shared[:10]))
    avg = average_flows(pop, lpcd)
    if not sum(avg.values()):
        raise DesignError("No sewage load: the population / per capita sewage give zero flow.")
    infil = {"basis": inp.get("infil_basis", "none"), "rate": inp.get("infil_rate") or 0.0,
             "cap": val(crit["sewer"], "infiltration_max_fraction")}
    peak, rows = inp.get("peak", "table"), val(crit["sewer"], "peak_factor_by_population") or []
    mset = set(manholes)
    flows = design_flows(data, avg, pop, mset, peak, rows, infil)
    ddata = copy.deepcopy(data)
    for k in ddata["conduits"]:
        k["flow_lps"] = flows[k["label"]]["Q"] if k["label"] in flows else 0.0
    note(f"design flow from population: {sum(pop.values()):,.0f} persons, average {sum(avg.values()):.2f} L/s, "
         f"{len(manholes)} manholes, {len(data['conduits'])} conduits")
    # stages (CPHEEO Table 2.1, p2-9): the base-year and intermediate (+15 years) populations, spread as the design
    # population is (every manhole scaled alike); the peak factor of Table 3.2 from the stage's own population
    stage_flows = {}
    tot_p = sum(pop.values())
    for key in STAGE_POPS:
        if inp.get(key):
            sc = float(inp[key]) / tot_p if tot_p else 0.0
            stage_flows[key] = design_flows(data, {m: a * sc for m, a in avg.items()},
                                            {m: p * sc for m, p in pop.items()}, mset, peak, rows, infil)
    flows_init = stage_flows.get("pop_initial")

    # ---- design
    min_d_map, plan_lines = {}, []
    if fixed:
        min_d_map, start, plan_lines = raise_to_fixed_outfalls(ddata, ground, R, sizes, fixed, log, xy)
        if economise and min_d_map:
            min_d_map, start, eco = economise_sizes(ddata, ground, R, sizes, fixed, min_d_map, start, log, xy)
            plan_lines += eco
        res, node_inv, node_info = start
    else:
        res, node_inv, node_info = design_network(ddata, ground, R, sizes, None, xy)
    upsized = []
    if min_d_map:
        # conduits made larger than the flow needs, only to reach a fixed outfall level (sheet 'Upsized for fall')
        free = design_network(ddata, ground, R, sizes, None, xy)[0]
        rate = {z["id_mm"]: (z.get("rate_rs_per_m") or 0.0) for z in sizes}
        for lab, d in res.items():
            f = free[lab]
            if d["D"] > f["D"] + 0.5:
                upsized.append({"label": lab, "from": d["from"], "to": d["to"], "length": d["length"], "q": d["q"],
                                "D_free": f["D"], "D": d["D"], "s_free": f["slope"], "s": d["slope"],
                                "v_free": f["v"], "v": d["v"],
                                "extra_cost": (rate.get(d["D"], 0) - rate.get(f["D"], 0)) * (d["length"] or 0)})

    for key, tag in STAGE_POPS.items():
        fl = stage_flows.get(key)
        if not fl:
            continue
        for lab, d in res.items():
            fi = fl.get(lab)
            qi = fi["Q"] if fi else None
            ddi, vi = uniform_flow(qi, d["D"], d["slope"], d["n"]) if qi else (None, None)
            d[f"q_{tag}"], d[f"v_{tag}"], d[f"dd_{tag}"] = qi, vi, ddi
    stages = stage_table(inp, res, flows, stage_flows, R, warnings, pop, avg) if stage_flows else []
    flush = plan_flushing(res, node_info, R, crit)      # before the split: flushing MHs are original nodes

    # ---- manhole spacing (30 m, Table 3.31 for trunk sewers) and bends (3.71): new manholes, network split there
    new_mh = spacing.plan_new_manholes(res, crit, R, spacing.polylines(net), xy,
                                       checked={k["label"] for k in net["conduits"] if k.get("presplit")})
    spacing.assign_new_labels(manholes, new_mh)
    net_split, made = (spacing.split_network(net, res, new_mh) if (split and new_mh) else (net, {}))
    if new_mh:
        n_bend = sum(1 for m in new_mh if str(m.get("why", "")).startswith("bend"))
        note(f"new manholes: {len(new_mh)} on {len({m['conduit'] for m in new_mh})} conduit(s) - {n_bend} at bends "
             f"(CPHEEO 3.71), {len(new_mh) - n_bend} for the spacing"
             + ("" if split else " (listed only, network not split)")
             + " - ground at new manholes is INTERPOLATED, check on site / DEM")
        if n_bend and (val(crit["sewer"], "drop_same_size_mm") or 0) > 0:
            warnings.append(f"{n_bend} new manhole(s) at bends lie on the designed straight grade: the "
                            f"{val(crit['sewer'], 'drop_same_size_mm'):g} mm drop at a change of direction (CPHEEO 3.20.3) "
                            f"is NOT made there - up to {n_bend * val(crit['sewer'], 'drop_same_size_mm') / 1000:.2f} m "
                            f"of drops in all; add them in the L-section where needed")

    # ---- final CPHEEO check on the split network (uniform flow)
    check_data = check.check_sewer(check.final_check_records(net_split, made, res, flows, node_info, new_mh),
                                   crit, "ultimate")
    warnings += check_data.get("warnings", [])
    for o, f in fixed.items():
        inv = node_info.get(o, {}).get("invert")
        if inv is not None and inv < f - 0.001:
            warnings.append(f"outfall {o}: designed invert {inv:.3f} m is BELOW the fixed level {f:.3f} m - gravity "
                            f"connection not possible (pumping or re-grading needed)")

    return {"res": res, "node_inv": node_inv, "node_info": node_info, "flows": flows, "flows_init": flows_init,
            "flows_mid": stage_flows.get("pop_mid"), "stages": stages,
            "pop": pop, "avg": avg, "flush": flush, "fixed": fixed, "min_d_map": min_d_map,
            "new_mh": new_mh, "net_split": net_split, "made": made, "check": check_data,
            "upsized": upsized, "warnings": warnings, "grade": grade, "gl_sources": gl_sources,
            "plan_lines": plan_lines, "log": lines, "catalog": (cat_name, cat_src, sizes), "rules": R,
            "criteria": crit, "data": ddata, "ground": ground, "xy": xy}
