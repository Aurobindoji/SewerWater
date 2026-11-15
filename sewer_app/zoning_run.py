"""The sewer zoning of the map page (/api/zoning, /api/zoning_export): the options, why each zone is one, the barrier
lines, the export of an option (restructure stage 6, 15-Nov-2026: out of ui.py)."""
import collections
import json
import os
import time
from . import geo as sgeo
from .geo import inside, interior, ring_area
from .project import _ck, converters_for, has_network, is_dxf, net_rev, net_state, out_root, paths, project_net, safe_name, to_latlng
from .inputs import ZCACHE, bend_drop_on, criteria_for, design_inputs
from .results import _keep, _source


def export_zoning(name, req):
    """DXF + KML + Excel of one option of the project's last zoning, as the map shows it (zone_export)."""
    from . import zone_export
    stem = safe_name(name)
    folder, f_mh, f_co, _ = paths(stem)
    f = os.path.join(folder, f"{stem}_zoning_ui.json")
    if not os.path.isfile(f):
        return {"ok": False, "log": "पहले zoning चलाएँ"}
    with open(f, encoding="utf-8") as fh:
        z = json.load(fh)
    opt = next((o for o in z["options"] if o["option"] == req.get("option")), None)
    if opt is None:
        return {"ok": False, "log": f"option '{req.get('option')}' इस zoning में नहीं"}
    if "mains" not in opt:
        return {"ok": False, "log": "यह zoning ज़ोन-सीमाओं से पहले की है - \"Zoning options निकालें\" फिर से चलाएँ"}
    zq = z.get("req") or {}                          # the network the zoning was made on (its manholes at bends, spacing)
    from . import edits as ed
    net = design_net(stem, criteria_for(zq.get("max_depth"), zq.get("bend_drop"), zq.get("mh_spacing"),
                                        zq.get("bend_angle"), ed.clean(zq.get("edits"))["trunk"]),
                     barriers=zq.get("barriers"), loops=zq.get("loops"), crossings=zq.get("crossings"))
    to_ll, to_xy = converters_for(stem)
    q = z.get("req") or {}
    info = {"project": stem, "option": opt["option"], "zoning": z.get("time", ""),
            "STP manhole": q.get("stp") or "-",
            "design method": ("only the given outfalls / STP (sewer depth may grow)" if q.get("mode") == "given"
                              else "free (pumping station added where the sewer gets deeper than the limit)"),
            "max depth (m)": q.get("max_depth") or "design_criteria.json", "max zones from the ground slope": q.get("max_zones") or "-",
            "30 mm drop at a change of direction": "on (CPHEEO)" if bend_drop_on(q.get("bend_drop")) else "off (page)",
            "population": q.get("pop_total") or "-",
            "zones / sub-zones / PS": f"{len(opt['mains'])} / {len(opt.get('subs') or {})} / {opt['pumping']} "
                                      f"({opt['pumping_for_depth']} for depth)",
            "pipe cost (Rs lakh)": opt.get("pipe_lakh"), "total cost (Rs lakh, approx.)": opt.get("total_lakh"),
            "exported": time.strftime("%d-%m-%Y %H:%M")}
    base = os.path.join(folder, f"{stem}_zones_{opt['option']}_{time.strftime('%Y%m%d_%H%M')}")
    design_dxf = design_drawing_of(stem, opt["option"])
    if design_dxf:
        info["design drawing"] = os.path.basename(design_dxf)
    try:
        files = zone_export.export(opt, folder, base, to_ll, to_xy, net, info, design_dxf=design_dxf)
    except Exception as e:
        return {"ok": False, "log": f"{type(e).__name__}: {e}"}
    return {"ok": True, "files": files, "folder": folder, "design": os.path.basename(design_dxf) if design_dxf else None}


def design_drawing_of(stem, option):
    """The plan DXF of the project's last design when it is of this zoning option and of the network as it is now
    (not stale) - the zone export draws the zones into it; None otherwise."""
    f = os.path.join(out_root(), stem, f"{stem}_design_ui.json")
    if not os.path.isfile(f):
        return None
    with open(f, encoding="utf-8") as fh:
        d = json.load(fh)
    path = (d.get("files") or {}).get("plan_dxf")
    if (d.get("summary") or {}).get("option") != option or d.get("net_rev") != net_rev(stem):
        return None
    if not path or not os.path.isfile(path):
        return None
    return path


LOOP_GAP_M = 0.5        # a sewer crossing a zone loop stops this short of it, on both sides


def design_net(stem, crit, log=None, barriers=None, loops=None, crossings=None):
    """The project's network for zoning and design: as it is now on the map (project_net), its sewers cut at the
    barrier lines of the page (barriers.py, user 27-Oct-2026: no sewer crosses a highway / railway ...) and at the
    zone loops (an area enclosed on the map is a zone of its own, user 27-Oct-2026: the sewers crossing the loop stop
    LOOP_GAP_M short of it; its lowest manhole is its outlet - a pumping station, or the STP when inside), with the
    manholes at bends and for the spacing put in (spacing.presplit - user decision 20-Oct-2026: every manhole in the
    design). A crossing line of the page lets the sewers through a barrier / loop where it crosses it, or is a new
    sewer itself where none crosses there (barriers.add_crossing_pipes). net["barriers"] / net["barrier_cuts"] tell
    which were cut, net["crossings"] what each crossing did, net["zone_loops"] the loops: name, manholes, outlet."""
    from . import barriers as sb, spacing
    net = project_net(stem)
    to_xy = converters_for(stem)[1]
    bars = sb.clean(barriers, to_xy) if barriers else []
    crs = sb.clean_crossings(crossings, to_xy) if crossings else []
    rings = []
    for i, lp in enumerate(loops or [], 1):
        ring = [[float(q[0]), float(q[1])] for q in (lp or {}).get("latlngs") or [] if isinstance(q, (list, tuple)) and len(q) >= 2]
        if len(ring) < 3:
            continue
        name = str(lp.get("name") or "").strip() or f"Zone loop {i}"
        rings.append((name, sb.clean([{"name": f"loop:{name}", "type": "other", "gap_m": LOOP_GAP_M,
                                       "latlngs": ring + ring[:1]}], to_xy)))
    pts = sb.crossing_points(crs, bars + [ln[0] for _, ln in rings])
    net, made = sb.add_crossing_pipes(net, crs, bars + [ln[0] for _, ln in rings], pts)
    net, cuts = sb.cut(net, bars, pts)
    if log and bars:
        log("barrier lines: " + sb.summary(bars, cuts) + " (a dead end); a side so cut off drains to an outlet of its "
            "own")
    if log and made:
        log("crossings: " + sb.crossing_summary(made))
    zl = []
    for name, line in rings:
        net, lc = sb.cut(net, line, pts)
        cuts += lc
        xy = [tuple(q) for q in line[0]["xy"]]
        taken = {n for x in zl for n in x["manholes"]}
        inside = {n for n, v in net["nodes"].items() if n not in taken and v.get("xy") and sgeo.inside(v["xy"], xy)}
        low = [n for n in inside if net["nodes"][n].get("ground") is not None]
        out = min(low, key=lambda n: (net["nodes"][n]["ground"], str(n))) if low else None
        zl.append({"name": name, "manholes": inside, "outlet": out, "cut": len(lc), "ring": xy})
        if log:
            log(f"zone loop {name}: {len(inside)} manholes, outlet {out or '-'}"
                + (f" (GL {net['nodes'][out]['ground']:.2f}, the lowest inside)" if out else " (no manhole inside)")
                + f"; {len(lc)} sewers cut at it, ending {LOOP_GAP_M:g} m short on both sides")
    net, rows = spacing.presplit(net, crit)
    net.update(barriers=bars, barrier_cuts=cuts, zone_loops=zl, crossings=made)
    if log and rows:
        nb = sum(1 for r in rows if r["why"].startswith("bend"))
        sp = crit["sewer"]
        log(f"new manholes before zoning / design: {len(rows)} - {nb} at bends of "
            f"{sp['bend_manhole_min_angle_deg']['value']} deg or more (CPHEEO 3.71), {len(rows) - nb} for the spacing "
            f"of {sp['max_manhole_spacing_m']['value']:g} m (3.71.1); ground there INTERPOLATED along the sewer")
    return net


def zone_reasons(net, stp, max_depth):
    """Why each zone of a zoning option (user request 30-Oct-2026, as the water module's): a function of an outlet row
    of zoning.evaluate -> {"kind": stp / given / loop / depth / part / terrain, "barriers": the barrier lines its part
    of the network is cut off by, "loop", "isolated": its part joined to the rest by no sewer in the drawing,
    "max_depth"}."""
    adj = collections.defaultdict(set)
    for k in net["conduits"]:
        adj[k["start_node"]].add(k["stop_node"])
        adj[k["stop_node"]].add(k["start_node"])
    part, parts = {}, collections.defaultdict(set)              # the connected parts of the network
    for n0 in sorted(adj, key=str):
        if n0 in part:
            continue
        st = [n0]
        part[n0] = n0
        while st:
            u = st.pop()
            parts[n0].add(u)
            for v in adj[u]:
                if v not in part:
                    part[v] = n0
                    st.append(v)
    at = {}                                                     # a cut manhole -> the line it was cut at
    for c in net.get("barrier_cuts", []):
        at[f"{c['pipe']}-x1"] = at[f"{c['pipe']}-x2"] = c["barrier"]
    loop_out = {x["outlet"]: x["name"] for x in net.get("zone_loops", []) if x.get("outlet")}
    given = set(net.get("outfalls") or [])
    main = part.get(stp)

    def why(zr):
        o, w = zr["zone outlet"], str(zr.get("why this outlet") or "")
        ns = parts.get(part.get(o), set()) if part.get(o) != main else set()   # the STP's part: the main one
        cut = sorted({at[n] for n in ns if n in at})
        bars = [b for b in cut if not b.startswith("loop:")]
        loops = sorted({b[5:] for b in cut if b.startswith("loop:")})
        kind = ("stp" if zr.get("role", "").startswith("STP") else "depth" if w.startswith("added")
                else "loop" if o in loop_out else "given" if o in given else "part" if "no outlet" in w else "terrain")
        return {"kind": kind, "barriers": bars, "loop": loop_out.get(o) or (loops[0] if loops else None),
                "isolated": kind == "part" and not bars and not loops and part.get(o) != main,
                "max_depth": max_depth}
    return why


def barrier_res(net, ll):
    """The barrier lines and their cuts for the page: the lines, where sewers were cut, and the parts of the cut
    sewers before the new manholes (the page has the network's sewers as they were, not these)."""
    parts = {lab for c in net.get("barrier_cuts", []) for lab in c["parts"]}
    parts |= {m["pipe"] for m in net.get("crossings", []) if m["pipe"]}            # new sewers along crossing lines
    geo = {}
    for k in net["conduits"]:                       # a part the new manholes divided: its pieces, end to end
        lab = k.get("piece_of") or k["label"]
        if lab in parts:
            pts = [ll(p) for p in (k.get("vertices") or [net["nodes"][k["start_node"]]["xy"], net["nodes"][k["stop_node"]]["xy"]])]
            geo[lab] = geo.get(lab, []) + (pts[1:] if geo.get(lab) else pts)
    return {"zone_loops": [{"name": x["name"], "manholes": len(x["manholes"]), "outlet": x["outlet"]} for x in net.get("zone_loops", [])],
            "barriers": [{"name": b["name"], "type": b["type"], "latlngs": b["latlngs"]} for b in net.get("barriers", [])],
            "cuts": [{"pipe": c["pipe"], "barrier": c["barrier"], "latlng": ll(c["xy"])} for c in net.get("barrier_cuts", [])],
            "cut_parts": [{"label": lab, "pts": pts} for lab, pts in geo.items()],
            "crossings": net.get("crossings", [])}


def _zoning(stem, inp, stp, max_zones, log, mode="auto", max_depth=None, bend_drop=True, edits=None, mh_spacing=None,
            bend_angle=None, barriers=None, loops=None, crossings=None):
    """mode 'auto': all zoning options, pumping stations added where the sewer gets deeper than max_depth (the
    project limit; default design_criteria.json); 'given': only the outfalls marked on the map / the STP (option
    GIVEN), the sewer may get deeper than the project limit. bend_drop, mh_spacing, bend_angle: see criteria_for. edits: the pipe /
    manhole tables' changes (edits.py) - on the returned network (net['_fixed_inv'] = the given inverts)."""
    from . import edits as ed
    from . import zoning
    _, f_mh, f_co, _ = paths(stem)
    bend_drop = bend_drop_on(bend_drop)
    edits = ed.clean(edits)
    if not has_network(stem):
        raise ValueError("पहले DXF network खोलें या Layout बनाएँ")
    crit = criteria_for(max_depth, bend_drop, mh_spacing, bend_angle, edits["trunk"])
    # the base year stage does not change the zoning; the +15 years population does (the pumps are sized on its
    # flow - CPHEEO Table 2.1 p2-9, user decision 21-Oct-2026)
    zin = {k: v for k, v in inp.items() if k not in ("base_year", "pop_initial")}
    key = json.dumps([zin, stp, max_zones, mode, max_depth, bend_drop, edits, barriers or [], loops or [], crossings or [], net_rev(stem),
                      crit["sewer"]["max_manhole_spacing_m"]["value"],
                      crit["sewer"]["bend_manhole_min_angle_deg"]["value"]], sort_keys=True)
    hit = ZCACHE.get(_ck(stem))
    if hit and hit[0] == key:
        return hit[1], hit[2], False
    net = design_net(stem, crit, log, barriers, loops, crossings)   # a DXF network: as it is now on the map
    if stp and stp not in net["nodes"]:
        raise ValueError(f"STP manhole '{stp}' इस network में नहीं है")
    if edits["conduits"] or edits["manholes"]:
        net, fixed, notes = ed.apply(net, edits)
        net["_fixed_inv"] = fixed
        log(f"table edits: {len(edits['conduits'])} conduit(s), {len(edits['manholes'])} manhole(s)"
            + "".join(f"\n   {s}" for s in notes))
    outs = list(net_state(stem)["net"]["outfalls"]) if is_dxf(stem) else []   # outfalls marked on the map
    net["outfalls"] = sorted(set(outs + ([stp] if stp else [])))
    for lp in net.get("zone_loops", []):             # a zone loop: its own outlet, unless one is given inside it
        given = sorted(lp["manholes"] & set(net["outfalls"]))
        if given:
            lp["outlet"] = given[0]
            log(f"zone loop {lp['name']}: its outlet is {given[0]}, given inside it (STP / outfall)")
        elif lp["outlet"]:
            net["outfalls"] = sorted(set(net["outfalls"]) | {lp["outlet"]})
    if mode == "given" and not net["outfalls"]:
        raise ValueError("केवल दिए गए outfalls पर design के लिए नक्शे पर outfall चिह्नित करें या STP manhole भरें")
    if not bend_drop:
        log("30 mm drop at a change of direction: OFF (page) - same-size sewers keep their invert through a bend")
    z = zoning.run(net, inp, crit=crit, stp=stp or None, max_zones=int(max_zones or 8),
                   log=log, given_only=mode == "given", only_given=mode == "given", fixed_inv=net.get("_fixed_inv"))
    ZCACHE[_ck(stem)] = (key, z, net)
    return z, net, True


BOUNDARY_GAP_M = 300.0        # drawn zone boundaries span open land up to this (m) - one line round a zone


def run_zoning(name, req):
    """Zoning options of the project's layout (zoning.run + the same files as 'python -m sewer_app zoning'):
    for the page the ranked options with their costs, and for each option the zone of every sewer, the outlets
    (STP / pumping stations) and the cut sewers."""
    from . import zoning
    from .zoning import VSEP
    stem = safe_name(name)
    folder, f_mh, _, _ = paths(stem)
    if not has_network(stem):
        return {"ok": False, "log": "पहले DXF network खोलें या Layout बनाएँ"}
    lines = []
    try:
        inp = design_inputs(stem, req)
        if inp.get("forecast"):
            from .population import summary as pop_summary
            lines.append(pop_summary(inp["forecast"]))
        stp = (req.get("stp") or "").strip() or None
        z, net, fresh = _zoning(stem, inp, stp, req.get("max_zones") or 8, lines.append, req.get("mode") or "auto",
                                req.get("max_depth"), req.get("bend_drop"), req.get("edits"), req.get("mh_spacing"),
                                req.get("bend_angle"), req.get("barriers"), req.get("loops"), req.get("crossings"))
        base = os.path.join(folder, f"{stem}_zoning_{time.strftime('%Y%m%d_%H%M')}")
        f = zoning.write_outputs(z, base, source=_source(stem), network_dxf="best")
    except Exception as e:
        return {"ok": False, "log": "\n".join(lines) + f"\n{type(e).__name__}: {e}"}
    ll = to_latlng(stem)
    costs = z.get("option_costs") or {}
    why = zone_reasons(net, stp, criteria_for(req.get("max_depth"))["sewer"]["max_depth_project_m"]["value"])
    # boundaries to DRAW: triangles up to BOUNDARY_GAP_M long, so that a zone is enclosed by one line across
    # open land between its manholes (the zone areas of the tables keep the zoning's own, shorter limit)
    tg = zoning.triangulate(z["gl"], z["xy"], max(BOUNDARY_GAP_M, 2 * z["max_edge"]))

    def outer(reg):
        """Outer boundary rings only (in metres): a ring lying inside a larger ring of the same zone is a hole
        (no data) and would only clutter the boundary; a piece smaller than 1 % of the zone's largest (a manhole
        alone among another zone's) is not drawn."""
        rs = sorted((reg or {}).get("rings", []), key=lambda r: -abs(ring_area(r)))
        keep = []
        for r in rs:
            if len(r) >= 3 and not any(inside(r[0], k) for k in keep):
                keep.append(r)
        big = abs(ring_area(keep[0])) if keep else 0
        return [r for r in keep if abs(ring_area(r)) >= 0.01 * big]

    def rings(reg):
        return [[ll(p) for p in ring] for ring in outer(reg)]

    def ring_labels(reg):
        """A point inside each piece of a zone for its name (a zone can lie in several pieces where manholes are far
        apart); none for pieces smaller than 5 % of the largest."""
        keep = outer(reg)
        big = abs(ring_area(keep[0])) if keep else 0
        return [ll(interior(r)) if abs(ring_area(r)) >= 0.05 * big else None for r in keep]

    opts = []
    for ev in z["rank"]:
        m = ev["m"]
        c = costs.get(m["option"], {})
        # main zones = the zones from the slope of the ground (outlets of the option without the pumping stations
        # added for depth); sub-zones = the areas of the pumping stations added for depth, each inside a main zone
        outs = sorted(set(ev["zone"].values()))
        added = set(ev.get("pumps_added") or [])
        base_zone, _, _ = zoning.zones_from_outlets([o for o in outs if o not in added], z["adj"], z["E"], z["gl"], z["W"])
        parent = {o: base_zone.get(o, o) for o in outs}
        main_regs = zoning.zone_regions(tg, base_zone) if tg else {}
        mains = [{"outlet": o, "rings": rings(main_regs.get(o)), "ring_labels": ring_labels(main_regs.get(o)),
                  "label": ll(main_regs[o]["label"]) if main_regs.get(o, {}).get("label") else None}
                 for o in sorted(set(base_zone.values()))]
        # sub-zones: those of the pumping stations added for depth, and - in a main zone that has such - the rest of
        # the main zone (the area that reaches the main outlet itself)
        with_subs = {parent[o] for o in added}
        sub_regs = zoning.zone_regions(tg, ev["zone"]) if (tg and (added or with_subs)) else {}
        subs = {o: {"rings": rings(sub_regs.get(o)), "ring_labels": ring_labels(sub_regs.get(o)),
                    "label": ll(sub_regs[o]["label"]) if sub_regs.get(o, {}).get("label") else None}
                for o in outs if o in added or o in with_subs}
        opts.append({
            "option": m["option"], "rank": m["rank"], "zones": m["zones"], "pumping": m["pumping stations"],
            "pumping_for_depth": m["of these added for depth"], "max_depth": m["max depth (m)"],
            "deep_project": m["manholes deeper than project limit"], "deep_cpheeo": m["manholes deeper than CPHEEO limit"],
            "pipe_lakh": m["pipe cost (Rs lakh)"], "total_lakh": c.get("total_lakh"), "groups_lakh": c.get("groups_lakh", {}),
            "cuts": [r["conduit"] for r in ev["cuts"]],
            "conduit_zone": {lab: d["to"].split(VSEP)[0] if ev["zone"].get(d["to"].split(VSEP)[0]) is None
                             else ev["zone"][d["to"].split(VSEP)[0]] for lab, d in ev["res"].items()},
            "outlets": [{"manhole": zr["zone outlet"], "role": zr["role"], "why": zr["why this outlet"],
                         "latlng": ll(z["xy"][zr["zone outlet"]]) if zr["zone outlet"] in z["xy"] else None,
                         "flow_lps": zr["design flow at outlet (L/s)"], "depth": zr["outlet depth = wet well (m)"],
                         "manholes": zr["manholes"], "area_ha": zr.get("zone area (ha)"), "reason": why(zr)}
                        for zr in ev["zones"]],
            "mains": mains, "parent": parent, "subs": subs})
    files = {k: v for k, v in f.items() if isinstance(v, str)}
    # the network's conduits cut by the new manholes (spacing.presplit): piece -> the conduit drawn on the map
    piece_of = {k["label"]: k["piece_of"] for k in net["conduits"] if k.get("piece_of") and k["label"] != k["piece_of"]}
    from .population import summary as pop_summary
    res = {"ok": True, "options": opts, "log": "\n".join(lines), "files": files, "inputs": inp,
           "cached": not fresh, "stp": stp, "piece_of": piece_of,
           "forecast": pop_summary(inp["forecast"]) if inp.get("forecast") else ""}
    res.update(barrier_res(net, ll))
    # separate pieces of the drawing close to each other, joined by no sewer: a gap to join (user 30-Oct-2026), not
    # across a barrier line / zone loop (cut there on purpose)
    from . import barriers as sb
    gaps = sb.near_parts(net, net.get("barriers", []) + [{"xy": x["ring"]} for x in net.get("zone_loops", [])
                                                          if x.get("ring")], skip=sb.cut_ends(net.get("barrier_cuts")))
    res["near_gaps"] = [{"a": g["a"], "b": g["b"], "dist_m": g["dist_m"], "latlngs": [ll(p) for p in g["xy"]]}
                        for g in gaps]
    if gaps:
        res["log"] += "\n" + sb.near_summary(gaps, what="sewer")
    _keep(stem, "zoning", res, req)
    return res
