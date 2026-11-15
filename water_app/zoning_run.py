"""The water zoning of the map page (/api/w/water_zoning, /api/w/water_join_plan): the network as cut at the barrier
lines and zone loops, its population (wards / total / bulk consumers), the OHTs, the OZs and DMAs and their
checks (restructure stage 2, 15-Nov-2026: out of ui_api.py)."""
import collections
import csv
import math
import os
from . import barriers as wb
from . import geo as wgeo
from . import project as ui
from . import zone_geom as szoning
from . import demand as dm
from . import design as wd
from . import population as wpop
from . import zoning as wz
from .zone_lines import STRAIGHT_M, _mid_along, _zone_tri
from .wards import _factor, _has_conn, _proj_flags, _ward_flags, _ward_growth, _ward_pop, _ward_rest, _wards, _with_projection, ward_growth_of
from .results import _keep, edits_of


BULK_FAR_M = 200.0     # a bulk consumer farther than this from its junction: flagged


def _bulk(stem, req, wnet, crit):
    """Bulk / institutional consumers of the page (user request 30-Oct-2026: a hospital, industry, station ... -
    their demand is no population's): [{name, lat, lng, kld, peak}] -> each to the nearest junction with a pipe. On
    its node: bulk_raw (KLD as given), bulk_kl (+ distribution losses, CPHEEO Table 2.7 S.No.6 - user decision
    30-Oct-2026), bulk_peak_kl (bulk_kl x its own peak factor; none given: the network's). The same KLD at every stage
    (user decision 30-Oct-2026). Returns the rows for the flags / map / DPR."""
    raw = []
    for i, b in enumerate((req or {}).get("bulk") or [], 1):
        try:
            kld = float(str(b.get("kld")).replace(",", ""))
            lat, lng = float(b["lat"]), float(b["lng"])
        except (TypeError, ValueError, KeyError):
            continue
        if kld <= 0:
            continue
        try:
            pf = float(b.get("peak"))
        except (TypeError, ValueError):
            pf = None
        raw.append({"name": str(b.get("name") or "").strip() or f"Bulk {i}", "kld": kld, "lat": lat, "lng": lng,
                    "peak": pf if pf and 0 < pf <= 10 else None})
    if not raw:
        return []
    to_xy = ui.converters_for(stem)[1]
    piped = {n for p in wnet["pipes"].values() for n in (p["a"], p["b"])}
    cand = [(n, v["xy"]) for n, v in wnet["nodes"].items() if n in piped and v.get("xy")]
    if not cand:
        return []
    loss, pf0 = crit["distribution_losses"]["value"], crit["peak_factor"]["value"]
    out = []
    for b, xy in zip(raw, to_xy([[b["lat"], b["lng"]] for b in raw])):
        n, nxy = min(cand, key=lambda c: (math.dist(c[1], xy), str(c[0])))
        v = wnet["nodes"][n]
        pf = b["peak"] or pf0
        kl = b["kld"] * (1 + loss)
        v["bulk_raw"] = v.get("bulk_raw", 0.0) + b["kld"]
        v["bulk_kl"] = v.get("bulk_kl", 0.0) + kl
        v["bulk_peak_kl"] = v.get("bulk_peak_kl", 0.0) + kl * pf
        out.append(dict(b, peak=pf, peak_given=b["peak"] is not None, node=n, dist_m=round(math.dist(nxy, xy), 1),
                        kl=round(kl, 2)))
    return out


def _node_lps(v, crit, city, sc=1.0):
    """A junction's demand for the hydraulics (L/s, multiplied by the network's peak factor there): its population's
    (scaled to a stage) and its bulk consumers' at their own peak factor -> (that, the true average L/s). The fire
    demand is not in it - it is held in the OHT (zoning: OHT capacity; DPR T1: storage), not peaked in the network (user
    decision 30-Oct-2026), as the distribution demand of DPR T1 (M-O)."""
    d = dm.daily_kl(v["pop"] * sc, crit, city * sc)
    pop = dm.lps(d["domestic"] + d["floating"])
    return pop + dm.lps(v.get("bulk_peak_kl", 0.0)) / crit["peak_factor"]["value"], pop + dm.lps(v.get("bulk_kl", 0.0))


def _bulk_flags(rows, ll, xy):
    """The bulk consumers among the zoning's flags, and for the map each with the junction it is joined to."""
    if not rows:
        return [], []
    tot, kl = sum(b["kld"] for b in rows), sum(b["kl"] for b in rows)
    names = ", ".join(f"{b['name']} {b['kld']:g} KLD -> {b['node']}" for b in rows[:6]) + (" ..." if len(rows) > 6 else "")
    f = [{"zone": None, "level": "info",
          "text": f"{len(rows)} bulk consumer(s): {tot:,.1f} KLD, {kl:,.1f} KLD with distribution losses, each at its own "
                  f"peak factor, the same at every stage: {names}",
          "hi": f"{len(rows)} bulk consumer: {tot:,.1f} KLD, distribution losses सहित {kl:,.1f} KLD, हर एक अपने peak "
                f"factor पर, हर stage में वही: {names}"}]
    far = [b for b in rows if b["dist_m"] > BULK_FAR_M]
    if far:
        s = ", ".join(f"{b['name']} {b['dist_m']:,.0f} m" for b in far[:6])
        f.append({"zone": None, "level": "warn",
                  "text": f"bulk consumer(s) farther than {BULK_FAR_M:g} m from the nearest junction: {s} - a pipe to "
                          f"them is not in the network; move the point or draw the pipe",
                  "hi": f"सबसे पास के junction से {BULK_FAR_M:g} m से दूर bulk consumer: {s} - उन तक का pipe network में "
                        f"नहीं; बिंदु खिसकाएँ या pipe खींचें"})
    pts = [{"name": b["name"], "node": b["node"], "kld": b["kld"], "peak": b["peak"], "dist_m": b["dist_m"],
            "latlngs": [[b["lat"], b["lng"]], ll(xy[b["node"]])]} for b in rows if b["node"] in xy]
    return f, pts


def _noconn_note(net):
    """The pipes left out when the population is spread: {"pipes", "m", "crossings"} or None."""
    nc = [c for c in net["conduits"] if not _has_conn(c)]
    if not nc:
        return None
    return {"pipes": len(nc), "m": round(sum(c["length_m"] or 0.0 for c in nc)),
            "crossings": sum(1 for c in nc if c.get("crossing") and not c.get("no_conn"))}


def _noconn_flags(note):
    if not note:
        return []
    x = f" ({note['crossings']} along crossing lines)" if note["crossings"] else ""
    xh = f" ({note['crossings']} crossing रेखाओं पर)" if note["crossings"] else ""
    return [{"zone": None, "level": "info",
             "text": f"{note['pipes']:,} pipes ({note['m']:,} m) without service connections{x}: no population put on "
                     f"them - the water still flows through them",
             "hi": f"{note['pipes']:,} pipes ({note['m']:,} m) बिना कनेक्शन{xh}: उन पर आबादी नहीं बाँटी - पानी उनसे होकर "
                   f"बहता है"}]


def _load(stem, req=None):
    """The project's network (the layout, or the DXF network as it is now on the map - saved or not) and its
    population per node: of the wards (layout; on a DXF network the wards drawn on the map, net["ward_note"]), else
    the total given on the page spread by pipe length (half of each pipe to each of its ends)."""
    folder, f_mh, f_co, f_pop = ui.paths(stem)
    if not ui.has_network(stem):
        raise ValueError("पहले Layout बनाएँ" if not ui.is_dxf(stem) else "पहले DXF network खोलें")
    net = cut_net(stem, req)
    pop = {}
    if os.path.isfile(f_pop):
        with open(f_pop, encoding="utf-8") as fh:
            pop = {r["Manhole"]: float(r["Population"]) for r in csv.DictReader(fh)}
    wards = _wards(stem, req) if ui.is_dxf(stem) and sum(pop.values()) <= 0 else []
    spread = sum(pop.values()) <= 0           # spread here (wards / total), not given per junction by the layout
    if spread:
        net["noconn_note"] = _noconn_note(net)
    if wards:
        pop, net["ward_note"] = _ward_pop(net, wards)
        _ward_rest(net, pop, wards, req)
        return folder, net, pop
    tot = float((req or {}).get("pop_total") or 0)
    if spread and tot > 0:
        share = collections.defaultdict(float)
        for c in filter(_has_conn, net["conduits"]):
            share[c["start_node"]] += c["length_m"] / 2
            share[c["stop_node"]] += c["length_m"] / 2
        L = sum(share.values()) or 1.0
        pop = {n: tot * v / L for n, v in share.items()}
    return folder, net, pop


def _loop_name(lp, i):
    return str((lp or {}).get("name") or "").strip() or f"Zone loop {i}"


def cut_net(stem, req):
    """The project's network with its pipes cut at the barrier lines of the page (barriers.py, user 27-Oct-2026),
    except where a crossing line of the page lets them through; a crossing where no pipe crosses: a new pipe along it.
    net["barriers"] / net["barrier_cuts"] / net["crossings"] tell which; net["cross_points"]: where the crossing lines
    cross the barriers and the zone loops (for _loops)."""
    req = req or {}
    net = ui.project_net(stem)
    if not req.get("barriers") and not req.get("crossings"):
        return dict(net, barriers=[], barrier_cuts=[], crossings=[], cross_points=[])
    to_xy = ui.converters_for(stem)[1]
    bars = wb.clean(req.get("barriers"), to_xy)
    crs = wb.clean_crossings(req.get("crossings"), to_xy)
    rings = []
    for i, lp in enumerate(req.get("loops") or [], 1):
        ring = [[float(p[0]), float(p[1])] for p in (lp or {}).get("latlngs") or []
                if isinstance(p, (list, tuple)) and len(p) >= 2]
        if len(ring) >= 3 and crs:
            rings.append(wb.ring_line(_loop_name(lp, i), to_xy(ring)))
    pts = wb.crossing_points(crs, bars + rings)
    net, made = wb.add_crossing_pipes(net, crs, bars + rings, pts)
    net, cuts = wb.cut(net, bars, pts)
    return dict(net, barriers=bars, barrier_cuts=cuts, crossings=made, cross_points=pts)


def _barrier_res(stem, net):
    """The barriers and their cuts for the page: lines, the points where pipes were cut and the parts of the cut pipes
    (the page has the network's pipes as they were, not these)."""
    ll = ui.to_latlng(stem)
    parts = {lab for c in net.get("barrier_cuts", []) for lab in c["parts"]}
    parts |= {m["pipe"] for m in net.get("crossings", []) if m["pipe"]}           # new pipes along crossing lines
    return {"barriers": [{"name": b["name"], "type": b["type"], "latlngs": b["latlngs"]} for b in net.get("barriers", [])],
            "cuts": [{"pipe": c["pipe"], "barrier": c["barrier"], "latlng": ll(c["xy"])} for c in net.get("barrier_cuts", [])],
            "cut_parts": [{"label": c["label"], "pts": [ll(p) for p in c["vertices"]]}
                          for c in net["conduits"] if c["label"] in parts],
            "crossings": net.get("crossings", [])}


def _barrier_check(net):
    """A note among the checks: the barrier lines and the pipes cut at them (none crosses but at a crossing)."""
    if not net.get("barriers") and not net.get("crossings"):
        return None
    return {"check": "barrier lines: no pipe crosses", "ok": True, "note": True,
            "ref": "user 27-Oct-2026: highway / expressway / railway lines drawn on the map",
            "detail": "; ".join(x for x in (wb.summary(net["barriers"], net["barrier_cuts"]),
                                            ("crossings: " + wb.crossing_summary(net["crossings"]))
                                            if net.get("crossings") else "") if x)}


LOOP_MODES = ("keep", "merge", "split")


def _loop_pieces(wnet, lp, small, keep_out):
    """A loop drawn across roads leaves bits of them cut off from its main part (user report 27-Oct-2026: 7 OZs of
    8 - 193 people beside one of 34,546): a piece inside the loop not joined to its main part along the pipes inside
    goes out of the loop, to the neighbouring OZ, when smaller than one DMA; a piece outside joined only to the loop
    (small, no OHT given in it) comes into it. small(population) -> True below one DMA; keep_out: nodes of the OHTs
    given (never moved). Changes lp["nodes"]; returns (pieces out, their population, pieces in, their population)."""
    nodes, pipes = wnet["nodes"], wnet["pipes"]
    adj = collections.defaultdict(list)
    for p in pipes.values():
        adj[p["a"]].append(p["b"])
        adj[p["b"]].append(p["a"])
    pop = lambda ns: sum(float(nodes[n].get("pop") or 0.0) for n in ns)
    ins = lp["nodes"]
    comps, seen = [], set()                               # the pieces inside, along the pipes inside
    for n0 in sorted(ins, key=str):
        if n0 in seen:
            continue
        comp, st = set(), [n0]
        seen.add(n0)
        while st:
            u = st.pop()
            comp.add(u)
            for v in adj[u]:
                if v in ins and v not in seen:
                    seen.add(v)
                    st.append(v)
        comps.append(comp)
    out_n = out_p = in_n = in_p = 0
    if comps:
        main = max(comps, key=lambda c: (pop(c), len(c)))
        for c in comps:
            if c is not main and small(pop(c)) and not c & keep_out:
                ins -= c
                out_n, out_p = out_n + 1, out_p + pop(c)
    big, seen = set(), set()                              # the pieces outside joined to the loop
    for u in sorted(ins, key=str):
        for o in adj[u]:
            if o in ins or o in seen or o in big:
                continue
            comp, st, P, large = {o}, [o], pop([o]), False
            while st and not large:
                x = st.pop()
                for v in adj[x]:
                    if v in ins or v in comp:
                        continue
                    if v in big:
                        large = True
                        break
                    comp.add(v)
                    st.append(v)
                    P += float(nodes[v].get("pop") or 0.0)
                    if not small(P):
                        large = True
                        break
            if large or comp & keep_out:
                big |= comp
            else:
                seen |= comp
                ins |= comp
                in_n, in_p = in_n + 1, in_p + P
    return out_n, out_p, in_n, in_p


def _loops(stem, req, wnet, crit=None, keep_out=frozenset(), net=None):
    """The zone loops of the page ([{name, latlngs: ring, on_limit}], user request 27-Oct-2026) for zoning.plan: the
    junctions inside each (a junction inside two: the first loop's) and the pipes crossing its boundary - closed
    there, valves (user decision 27-Oct-2026). on_limit (what to do above / below the OZ limits, the user's answer
    kept with the loop): keep / merge / split; not answered yet: keep, and the page asks."""
    raw = (req or {}).get("loops") or []
    if not raw:
        return []
    to_xy = ui.converters_for(stem)[1]
    out, taken = [], set()
    for i, lp in enumerate(raw, 1):
        ring = [[float(p[0]), float(p[1])] for p in (lp or {}).get("latlngs") or []
                if isinstance(p, (list, tuple)) and len(p) >= 2]
        if len(ring) < 3:
            continue
        xy = [tuple(p) for p in to_xy(ring)]
        nodes = {n for n, v in wnet["nodes"].items() if n not in taken and v.get("xy") and wgeo.inside(v["xy"], xy)}
        mode = str(lp.get("on_limit") or "")
        x = {"name": _loop_name(lp, i), "latlngs": ring, "xy": xy, "nodes": nodes, "through": [],
             "mode": mode if mode in LOOP_MODES else "keep", "answered": mode in LOOP_MODES, "pieces": None}
        if crit:
            ppc, dmin = crit["persons_per_connection"]["value"], crit["dma_min_connections"]["value"]
            x["pieces"] = _loop_pieces(wnet, x, lambda P: P / ppc < dmin, set(keep_out) | taken)
        taken |= x["nodes"]
        out.append(x)
    pts = (net or {}).get("cross_points") or []
    geo = {c["label"]: c for c in (net or {}).get("conduits", [])} if pts else {}
    for lp in out:
        lp["boundary"] = sorted((pid for pid, p in wnet["pipes"].items() if (p["a"] in lp["nodes"]) != (p["b"] in lp["nodes"])),
                                key=str)
        if pts:                                          # a crossing line there: the pipe stays open (user 27-Oct-2026)
            ring = wb.ring_line(lp["name"], lp["xy"])
            for pid in lp["boundary"]:
                poly = wb._poly(geo[pid], net["nodes"]) if pid in geo else []
                if any(wb.through(pts, ring["name"], h) for h in wb._cross(poly, ring["xy"])):
                    lp["through"].append(pid)
            lp["boundary"] = [pid for pid in lp["boundary"] if pid not in lp["through"]]
        for pid in lp["boundary"]:
            wnet["pipes"][pid]["closed"] = True
    return out


def _loop_res(z, wnet):
    """The zone loops for the page: each with its OZs and sizes; those over / under the OZ limits whose answer is not
    given yet: to be asked (keep / merge / split)."""
    by = {lp["name"]: lp for lp in wnet.get("loops", [])}
    loops = [dict(x, latlngs=by[x["name"]]["latlngs"], answered=by[x["name"]]["answered"]) for x in z.get("loops", [])]
    return {"loops": loops, "loop_ask": [x for x in loops if not x["answered"] and (x["over"] or x["under"])]}


def _note_hi(x):
    """A zone loop's note (zoning.plan) in Hindi, for the page."""
    n = x.get("note") or ""
    if n.startswith("its pipes inside"):
        return f"भीतर के pipes {len(x['zones'])} अलग टुकड़ों में - हर एक का OZ; एक बनाने के लिए उन्हें जोड़ें"
    return {"an OHT given inside the loop: not merged": "लूप के भीतर OHT दी गई है: merge नहीं किया",
            "no neighbouring OZ joined to it by a pipe: not merged": "कोई पड़ोसी OZ pipe से नहीं जुड़ा: merge नहीं किया"}.get(n, n)


def _loop_flags(z, wnet=None):
    """A line for each zone loop among the flags: its OZs, size, boundary valves and the small pieces it gave to /
    took from its neighbours."""
    out = []
    pieces = {lp["name"]: lp.get("pieces") for lp in (wnet or {}).get("loops", [])}
    thru = {lp["name"]: f"; open at crossings: {', '.join(map(str, lp['through']))}"
            for lp in (wnet or {}).get("loops", []) if lp.get("through")}
    for x in z.get("loops", []):
        pc = pieces.get(x["name"]) or (0, 0, 0, 0)
        moved = "".join([f"; {pc[0]} small piece(s) inside not joined to its main part along the pipes inside "
                         f"({pc[1]:,.0f} people) left to the neighbouring OZs" if pc[0] else "",
                         f"; {pc[2]} small piece(s) outside joined only to it ({pc[3]:,.0f} people) taken in"
                         if pc[2] else ""])
        what = {"keep": "kept as drawn", "split": "new OZs within it as needed",
                "merge": f"merged into {x['merged_into']}" if x.get("merged_into") else "to merge"}[x["mode"]]
        lim = (f" - above the OZ limit of {x['max_population']:,.0f}" if x["over"] else
               f" - below one DMA ({x['min_connections']:g} connections)" if x["under"] else "")
        what_hi = {"keep": "जैसा खींचा वैसा रखा", "split": "भीतर ज़रूरत भर नए OZ",
                   "merge": f"{x['merged_into']} में merge" if x.get("merged_into") else "merge होना है"}[x["mode"]]
        lim_hi = (f" - OZ की सीमा {x['max_population']:,.0f} से अधिक" if x["over"] else
                  f" - एक DMA ({x['min_connections']:g} कनेक्शन) से कम" if x["under"] else "")
        moved_hi = "".join([f"; भीतर के {pc[0]} छोटे टुकड़े जो मुख्य हिस्से से नहीं जुड़े ({pc[1]:,.0f} लोग) पड़ोसी OZ को"
                            if pc[0] else "",
                            f"; बाहर के {pc[2]} छोटे टुकड़े जो केवल इससे जुड़े थे ({pc[3]:,.0f} लोग) इसमें लिए" if pc[2] else ""])
        lp_ = next((lp for lp in (wnet or {}).get("loops", []) if lp["name"] == x["name"]), {})
        thru_hi = f"; crossings पर खुले: {', '.join(map(str, lp_['through']))}" if lp_.get("through") else ""
        out.append({"zone": None, "level": "info",
                    "text": f"zone loop {x['name']}: population {x['population']:,}, {x['connections']:,} connections"
                            f"{lim}; {what}: {', '.join(x['zones']) or '-'}; {x['boundary_pipes']} pipes closed at its "
                            f"boundary (valves)" + moved + thru.get(x["name"], "")
                            + (f" ({x['note']})" if x.get("note") else ""),
                    "hi": f"zone लूप {x['name']}: आबादी {x['population']:,}, {x['connections']:,} कनेक्शन{lim_hi}; "
                          f"{what_hi}: {', '.join(x['zones']) or '-'}; सीमा पर {x['boundary_pipes']} pipes बंद (valves)"
                          + moved_hi + thru_hi
                          + (f" ({_note_hi(x)})" if x.get("note") else "")})
    return out


def _ohts(stem, net, req):
    """The OHTs of the page snapped to the nearest node of the layout."""
    rows = req.get("ohts") or []
    if not rows:
        return []                                           # none placed: zoning proposes them all
    _, to_xy = ui.converters_for(stem)
    xy = {n: v["xy"] for n, v in net["nodes"].items() if v.get("xy")}
    out, seen = [], set()
    for i, o in enumerate(rows, 1):
        name = str(o.get("name") or f"OHT-{i}").strip() or f"OHT-{i}"
        if name in seen:
            name = f"{name}-{i}"
        seen.add(name)
        p = to_xy([[float(o["lat"]), float(o["lng"])]])[0]
        node = min(xy, key=lambda n: (xy[n][0] - p[0]) ** 2 + (xy[n][1] - p[1]) ** 2)
        cap = o.get("capacity_kl")
        st = o.get("staging_m")
        ex = o.get("existing")
        existing = ex in ("1", 1, True) or (ex in (None, "") and cap not in (None, ""))
        if existing and cap in (None, ""):
            raise ValueError(f"{name}: पुरानी टंकी की क्षमता (KL) भरें")
        if existing and st in (None, ""):
            raise ValueError(f"{name}: पुरानी टंकी की staging (m) भरें")
        if not existing:
            cap = None                                       # a new tank: sized from its OZ's demand
        # an existing tank too low for 17 m: a VFD pump at its outlet (CPHEEO Table 2.7 S.No.10), or its higher
        # ground to a new OHT
        low_head = ("new_oht" if str(o.get("low_head") or "") == "new_oht" else "vfd") if existing else None
        out.append({"name": name, "node": node, "dist_m": round(math.dist(xy[node], p), 1),
                    "capacity_kl": float(cap) if cap not in (None, "") else None,
                    "staging_m": float(st) if st not in (None, "") else None,
                    "tubewells": int(float(o.get("tubewells") or 0)), "rebore": int(float(o.get("rebore") or 0)),
                    "latlng": [float(o["lat"]), float(o["lng"])],
                    "low_head": low_head})
    return out


def standby_table(rows):
    """The page's standby table for the tube wells: [[working up to, standby], ...] - whole numbers, the working
    rising row by row; more working than the last row: the last row's standby."""
    tab = []
    for r in rows or []:
        try:
            u, s = (float(str(x).strip()) for x in r)
        except (TypeError, ValueError):
            raise ValueError(f"standby tube wells: '{r}' - दो अंक दें (working तक, standby)")
        if u != int(u) or s != int(s) or u < 1 or s < 0 or s > 20:
            raise ValueError(f"standby tube wells: {u:g} / {s:g} - working 1 या अधिक, standby 0-20, पूरे अंक")
        if tab and u <= tab[-1][0]:
            raise ValueError("standby tube wells: 'working तक' हर पंक्ति में पिछली से अधिक हो")
        tab.append([int(u), int(s)])
    if not tab:
        raise ValueError("standby tube wells: कम से कम एक पंक्ति दें")
    return tab


def _crit(req):
    crit = wd.load_criteria()
    ppc = req.get("persons_per_connection")
    if ppc not in (None, ""):
        crit["persons_per_connection"] = dict(crit["persons_per_connection"], value=float(ppc),
                                              ref=f"given on the page ({crit['persons_per_connection']['ref']})")
    fl = req.get("floating_pct")                  # 10 % by default, editable per project (user decision 11-Nov-2026)
    if fl not in (None, ""):
        try:
            v = float(str(fl).replace("%", "").strip())
        except ValueError:
            raise ValueError(f"floating: '{fl}' अंक नहीं - प्रतिशत दें, जैसे 10")
        if not 0.0 <= v <= 50.0:
            raise ValueError(f"floating: {v:g} % ठीक नहीं - 0 से 50 % तक दें")
        if abs(v / 100.0 - crit["floating_share"]["value"]) > 1e-12:
            crit["floating_share"] = {"value": v / 100.0,
                                      "ref": "given on the page (default 10 %: " + crit["floating_share"]["ref"]
                                             + "; CPHEEO Annexure 2.8: 1-3 % without figures)"}
    sb = req.get("tw_standby") or {}             # the tube wells' standby table of the page (user decision 15-Nov-2026)
    if sb.get("on"):
        tab = standby_table(sb.get("rows"))
        crit["standby_tubewells"] = {"value": tab, "ref": "given on the page: " + ", ".join(
            f"up to {u} working + {s} standby" for u, s in tab) + " (CPHEEO 5.7.5 p245-246: 1 W + 1 S, 2 W + 1 S, "
            "3-5 W + 2 S, 6-10 W + 3 S)"}
    win = req.get("oht_inflow")
    if win not in (None, ""):
        crit["oht_inflow_hours"] = dict(crit["oht_inflow_hours"], value=dm.parse_windows(win),
                                        ref=f"given on the page: {win} ({crit['oht_inflow_hours']['ref']})")
    # separate pieces of the drawing within this: a gap warned of (barriers.NEAR_M; page: editable, 7-Nov-2026)
    crit["near_gap_m"] = {"value": wb._num(req.get("near_m"), wb.NEAR_M, 1.0, 1000.0),
                          "ref": "pieces of the drawing joined by no pipe this close: warned of (page)"}
    if req.get("ward_table"):                     # the character factors of the page's ward table (7-Nov-2026)
        G = ward_growth_of(req["ward_table"])
        if G != crit["ward_growth"]["value"]:
            crit["ward_growth"] = {"value": G, "ref": "given on the page (ward table); " + crit["ward_growth"]["ref"]}
    return crit


def _pieces(wnet, nodes):
    """Number of connected pieces among these nodes (along the layout's pipes)."""
    nodes = set(nodes)
    adj = {n: [] for n in nodes}
    for p in wnet["pipes"].values():
        if p["a"] in nodes and p["b"] in nodes:
            adj[p["a"]].append(p["b"])
            adj[p["b"]].append(p["a"])
    seen, k = set(), 0
    for n in nodes:
        if n in seen:
            continue
        k += 1
        stack = [n]
        seen.add(n)
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    return k


def _unserved_note(wnet, nodes, hi=False):
    k = _pieces(wnet, nodes)
    if hi:
        return (f"{len(nodes)} junctions ({k} सड़क-टुकड़ों पर) किसी OHT के pipes से नहीं जुड़े - उन्हें नक्शे पर सड़कों से "
                f"जोड़ें (✎ / उनसे एक सड़क; या Zoning में '🔗 मुख्य network से जोड़ें') या वहाँ OHT रखें; नक्शे पर धूसर बिंदीदार घेरे")
    return (f"{len(nodes)} nodes on {k} road piece(s) joined to no OHT's pipes - join them to the roads on the map "
            f"(✎ / a road from them; or 'Join to the main network' in the Zoning) or place an OHT there; shown on the map as grey dashed circles")


def _near_nodes(stem, wnet, pts):
    """The junction nearest to each [{lat, lng}] of the page (the network's metres)."""
    to_xy = ui.converters_for(stem)[1]
    xy = {n: v["xy"] for n, v in wnet["nodes"].items()}
    out = []
    for p in pts or []:
        try:
            q = to_xy([[float(p["lat"]), float(p["lng"])]])[0]
        except (KeyError, TypeError, ValueError):
            continue
        if xy:
            out.append(min(xy, key=lambda n: math.dist(xy[n], q)))
    return out


def _removed_ohts(stem, req, wnet):
    """The proposed OHTs the user took away (user decision 15-Nov-2026): True for all ("सभी सुझाई OHT हटाएँ"), else
    the junctions at the sites taken away one by one."""
    s = (req or {}).get("sug") or {}
    if s.get("oht_off_all"):
        return True
    return _near_nodes(stem, wnet, s.get("oht_off"))


def _zones(stem, req, bar=None):
    folder, net, pop = _load(stem, req)
    if sum(pop.values()) <= 0:
        raise ValueError("population नहीं है: वार्ड में population भरें (फिर Layout दोबारा) या कुल population दें")
    crit = _crit(req)
    f = _factor(req)
    ohts = _ohts(stem, net, req)
    wnet = {"nodes": {n: {"xy": v["xy"], "elev": v.get("ground"), "pop": pop.get(n, 0.0) * f}
                      for n, v in net["nodes"].items() if v.get("xy")},
            "pipes": {c["label"]: {"a": c["start_node"], "b": c["stop_node"], "length": c["length_m"]}
                      for c in net["conduits"]}}
    chars = _ward_growth(net.get("ward_note"), wnet, pop, crit, req)
    # the junction table's changes (GL, population after the factor): zoning and design both use them
    e = edits_of(req)
    wnet["notes"] = []
    for n, x in e["junctions"].items():
        if n not in wnet["nodes"]:
            wnet["notes"].append(f"edit ignored: junction {n} not in the network")
            continue
        if "gl" in x:
            wnet["nodes"][n]["elev"] = x["gl"]
        if "pop" in x:
            wnet["nodes"][n]["pop"] = x["pop"]
    wnet["notes"] += [f"edit ignored: pipe {p} not in the network" for p in e["pipes"] if p not in wnet["pipes"]]
    if net.get("barriers") or net.get("crossings"):
        wnet["notes"].append("barrier lines: " + _barrier_check(net)["detail"])
    # bulk / institutional consumers of the page: on their nearest junctions (user 30-Oct-2026)
    wnet["bulk"] = _bulk(stem, req, wnet, crit)
    if wnet["bulk"]:
        wnet["notes"].append(f"bulk consumers: {len(wnet['bulk'])}, {sum(b['kld'] for b in wnet['bulk']):,.1f} KLD")
    wn = net.get("ward_note")
    if wn:
        wnet["notes"].append(f"population from {wn['wards']} ward(s) on the map: {wn['population']:,} on {wn['junctions']:,} "
                             f"junctions; {len(wn['outside']):,} junctions in no ward (none there)")
    # a projection of the page: the base year and +15 years from its ratios, on the base-year population on the
    # junctions (req: the copy made by _with_projection)
    pj = req.get("_proj")
    if pj:
        s0 = sum(pop.values())
        if pj.get("from_year"):                # the wards' population of their year (7-Nov-2026): grown from it
            req["pop_initial"], req["pop_mid"] = s0 * pj["ratio_from"]["init"], s0 * pj["ratio_from"]["mid"]
        else:
            req["pop_initial"], req["pop_mid"] = s0, s0 * pj["ratio"]["mid"]
        wnet["proj_s0"] = s0
        wnet["notes"].append(wpop.summary(pj))
    if chars:                                  # wards with a character: the stages junction by junction
        for t, k in (("init", "pop_initial"), ("mid", "pop_mid")):
            req[k] = sum(v["pop"] * v["stage"][t] for v in wnet["nodes"].values())
        wnet["notes"].append(f"ward growth by character (Riverside water DPR p76): {chars} ward(s); base year "
                             f"{req['pop_initial']:,.0f}, +15 years {req['pop_mid']:,.0f}")
    # the +15 years population of the page (stage check), for the tube wells the zoning counts (CWR rule)
    mid, city = ui.stage_inputs(req).get("pop_mid"), sum(v["pop"] for v in wnet["nodes"].values())
    crit["stage_mid_share"] = {"value": mid / city if mid and city else 1.0,
                               "ref": "page: +15 वर्ष की आबादी / design population (not given: 1)"}
    # the zone loops of the page: the junctions inside, their boundary pipes closed (valves)
    wnet["loops"] = _loops(stem, req, wnet, crit, {o["node"] for o in ohts}, net)
    z = wz.plan(wnet, ohts, crit, bar=bar, loops=wnet["loops"], removed=_removed_ohts(stem, req, wnet))
    if not z["zones"]:
        raise ValueError("कोई OHT नहीं: सुझाई OHT हटाई गई हैं और नक्शे पर कोई OHT नहीं - नक्शे पर OHT रखें या "
                         "'सुझाई OHT वापस' दबाएँ / no OHT: place OHTs on the map or bring the suggested ones back")
    ll = ui.to_latlng(stem)
    for p in z["proposed"]:
        p.update(latlng=ll(wnet["nodes"][p["node"]]["xy"]), dist_m=0.0)
    return folder, net, wnet, ohts + z["proposed"], crit, z


def run_zoning(name, req):
    stem = ui.safe_name(name)
    req = _with_projection(req)
    zz = _zones(stem, req)
    res = _zoning_res(stem, *zz)
    res["projection"] = req.get("_proj")
    res["flags"] = _proj_flags(req.get("_proj"), zz[2].get("proj_s0")) + res["flags"]
    _keep(stem, "zoning", res, req)
    return res


# an isolated piece is joined by itself to the network the OHTs serve within this (page: editable) - 100 m until
# 7-Nov-2026, when the user asked to join the pieces farther than 50 m to the main network (network_utm: its 5 pieces
# 104-154 m and 2.8 km away, none joined at 100 m)
JOIN_MAX_M = 500.0


def join_plan(name, req):
    """The isolated pieces of a DXF network - the junctions the zoning leaves to no OHT - each to be joined by a new
    straight pipe (user request 30-Oct-2026, a preview first, joined on the user's word: netedit 'connect', one Undo):
    from its junction nearest to a junction of the served network, within max_m (JOIN_MAX_M), not across a barrier
    line or a zone loop's ring (user: on its own side - a piece cut off by a highway is not joined back across it),
    junction to junction (user: their GL known; not the ends a barrier cut made, they are not in the drawing). The
    shortest join first; a piece joined serves the pieces after it. A piece left: near_m = its straight distance to
    the nearest junction of the network (barriers not looked at) - to tell a piece just beyond max_m from one far away.
    {"joins": [{a, b, dist_m, latlngs, nodes, population}], "left": [{nodes, population, latlng, cut, near_m}],
     "max_m"}"""
    stem = ui.safe_name(name)
    if not ui.is_dxf(stem):
        raise ValueError("सिर्फ़ DXF network पर - KML layout में सड़क जोड़कर Layout दोबारा बनाएँ")
    try:
        max_m = min(max(float(req.get("join_max_m") or JOIN_MAX_M), 1.0), 5000.0)
    except (TypeError, ValueError):
        max_m = JOIN_MAX_M
    req = _with_projection(req)
    _, net, wnet, _, _, z = _zones(stem, req)
    nodes, un = wnet["nodes"], set(z["unserved"])
    ends = wb.cut_ends(net.get("barrier_cuts"))
    real = set(ui.project_net(stem)["nodes"]) - ends               # junctions of the drawing (netedit has them)
    adj = collections.defaultdict(set)
    for p in wnet["pipes"].values():
        adj[p["a"]].add(p["b"])
        adj[p["b"]].add(p["a"])
    pieces, seen = [], set()
    for n0 in sorted(un, key=str):
        if n0 in seen:
            continue
        comp, st = {n0}, [n0]
        seen.add(n0)
        while st:
            for v in adj[st.pop()]:
                if v in un and v not in seen:
                    seen.add(v)
                    comp.add(v)
                    st.append(v)
        pieces.append(comp)
    across = wb.blocker(list(net.get("barriers") or []) + [wb.ring_line(lp["name"], lp["xy"])
                                                           for lp in wnet.get("loops") or [] if lp.get("xy")])
    grid = collections.defaultdict(list)                           # the served junctions, in cells of max_m

    def add(ns):
        for n in ns:
            if n in real and nodes[n].get("xy"):
                x, y = nodes[n]["xy"]
                grid[(math.floor(x / max_m), math.floor(y / max_m))].append(n)

    def best(comp, only=None):
        """(distance, junction of the piece, served junction) of its shortest join; only: to these junctions."""
        cand = []
        for u in comp:
            if u not in real or not nodes[u].get("xy"):
                continue
            xu = nodes[u]["xy"]
            i, j = math.floor(xu[0] / max_m), math.floor(xu[1] / max_m)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for s in grid.get((i + di, j + dj), ()):
                        if only is None or s in only:
                            d = math.dist(xu, nodes[s]["xy"])
                            if d <= max_m:
                                cand.append((d, str(u), str(s), u, s))
        for d, _, _, u, s in sorted(cand):
            if not across(nodes[u]["xy"], nodes[s]["xy"]):
                return d, u, s
        return None

    add(n for n in nodes if n not in un)
    todo = {i: (c, best(c)) for i, c in enumerate(pieces)}
    ll = ui.to_latlng(stem)
    pop = lambda comp: round(sum(nodes[n].get("pop", 0.0) for n in comp), 1)
    joins = []
    while True:
        go = [(b, i) for i, (c, b) in todo.items() if b]
        if not go:
            break
        (d, u, s), i = min(go, key=lambda x: (x[0][0], x[1]))
        comp = todo.pop(i)[0]
        joins.append({"a": u, "b": s, "dist_m": round(d, 1), "latlngs": [ll(nodes[u]["xy"]), ll(nodes[s]["xy"])],
                      "nodes": len(comp), "population": pop(comp)})
        add(comp)
        for k, (c, b) in todo.items():                               # the piece just joined: nearer for some?
            nb = best(c, only=comp)
            if nb and (not b or nb[0] < b[0]):
                todo[k] = (c, nb)
    left = []
    srv = [p for ps in grid.values() for p in ps]                  # the network's junctions now (joined pieces too)
    for c, _ in todo.values():
        xy = [nodes[n]["xy"] for n in c if nodes[n].get("xy")]
        near = min((math.dist(p, nodes[s]["xy"]) for p in xy for s in srv), default=None)
        left.append({"nodes": len(c), "population": pop(c), "cut": bool(c & ends),
                     "near_m": round(near, 1) if near is not None else None,
                     "latlng": ll((sum(p[0] for p in xy) / len(xy), sum(p[1] for p in xy) / len(xy))) if xy else None})
    left.sort(key=lambda x: -x["nodes"])
    return {"joins": joins, "left": left, "max_m": max_m, "unserved": len(un), "pieces": len(pieces)}


def _why(net, wnet, z):
    """Why each OZ (user request 30-Oct-2026, a tooltip on the page): zoning.plan's reason, and for a proposed OZ
    whether its area is cut off by a barrier line (cut junctions in it) or by a zone loop's valves, or is a separate
    piece of the drawing joined to the rest by no pipe (isolation)."""
    at = {}                                                  # a cut junction -> the barrier it was cut at
    for c in net.get("barrier_cuts", []):
        at[f"{c['pipe']}-x1"] = at[f"{c['pipe']}-x2"] = c["barrier"]
    loop_of = {}                                             # a junction at a loop's closed boundary -> the loop
    for lp in wnet.get("loops", []):
        for pid in lp["boundary"]:
            p = wnet["pipes"][pid]
            loop_of[p["a"]] = loop_of[p["b"]] = lp["name"]
    mem = collections.defaultdict(list)
    for n, k in z["oz"].items():
        mem[k].append(n)
    piece = collections.defaultdict(list)                    # the OZs of one piece of the network
    for k, w in (z.get("why") or {}).items():
        if w["kind"] == "proposed":
            piece[w["piece"]] += mem.get(k, [])
    whys = (z.get("why") or {}).values()
    given = any(w["kind"] == "given" for w in whys)
    biggest = max((w["piece_nodes"] for w in whys if w["kind"] == "proposed"), default=0)
    out = {}
    for k, w in (z.get("why") or {}).items():
        w = dict(w)
        if w["kind"] == "proposed":
            ns = piece[w["piece"]]
            w["barriers"] = sorted({at[n] for n in ns if n in at})
            w["loops_closed"] = sorted({loop_of[n] for n in ns if n in loop_of} - {w.get("loop")})
            # no tank given: the largest piece is the network's main part, not one apart from it
            w["main"] = not given and w["piece_nodes"] == biggest
            w["isolated"] = not (w["next_to"] or w["barriers"] or w["loops_closed"] or w.get("loop") or w["main"])
            w["piece_zones"] = sorted((x for x, y in (z.get("why") or {}).items() if y.get("piece") == w["piece"]),
                                      key=str)
        out[k] = w
    return out


def _zoning_res(stem, folder, net, wnet, ohts, crit, z):
    ll = ui.to_latlng(stem)
    xy = {n: v["xy"] for n, v in wnet["nodes"].items()}

    tg, who, on_pipes = _zone_tri(stem, net)

    def shown(regs):
        """The areas as the page draws them: rings (lat, lon; the small ones left out), a label point, the area."""
        out = {}
        for g, r in regs.items():
            rings = sorted(r.get("rings", []), key=lambda q: -abs(wgeo.ring_area(q)))
            keep = [q for q in rings if len(q) >= 3]
            big = abs(wgeo.ring_area(keep[0])) if keep else 0
            keep = [q for q in keep if abs(wgeo.ring_area(q)) >= 0.01 * big]
            out[g] = {"rings": [[ll(p) for p in q] for q in keep],
                      "label": ll(wgeo.interior(keep[0])) if keep else None, "area_ha": round(r.get("area", 0.0) / 1e4, 2)}
        return out

    def regions():
        """Boundaries of the OZs and of the DMAs: a pipe point belongs to its pipe's start node's OZ and DMA. The
        OZs are made of their DMAs' areas (a part of an OZ in no DMA: an area of its own), so a line of an OZ and
        of a DMA is the same line."""
        fine, parent = {}, {}
        for i, n in enumerate(who):
            o, d = z["oz"].get(n), z["dma"].get(n)
            if o is None and d is None:
                continue
            key = ("dma", d) if d is not None else ("oz", o)
            fine[f"p{i}"] = key
            if o is not None:
                parent[key] = o
        if not tg:
            return {}, {}
        small, large = szoning.zone_regions(tg, fine, straighten=STRAIGHT_M, guard=on_pipes, parent=parent)
        return shown(large), shown({k[1]: v for k, v in small.items() if k[0] == "dma"})

    def density(x, reg):
        """Area (ha, of the region drawn) and persons per ha of an OZ / DMA - to check the population as spread
        (user request 30-Oct-2026: a checking map)."""
        a = (reg or {}).get("area_ha") or 0.0
        return {"area_ha": a, "density": round(x["population"] / a, 1) if a > 0 else None}
    oz_regs, dma_regs = regions()
    pipe_zone = {lab: z["oz"].get(p["a"]) for lab, p in wnet["pipes"].items()}
    pipe_dma = {lab: z["dma"].get(p["a"]) if z["dma"].get(p["a"]) == z["dma"].get(p["b"]) else None
                for lab, p in wnet["pipes"].items()}
    by = {o["name"]: o for o in ohts}
    why = _why(net, wnet, z)
    zones = []
    for x in z["zones"]:
        o = by[x["name"]]
        zones.append(dict(x, staging_m=o["staging_m"], latlng=o["latlng"], node_dist_m=o["dist_m"],
                          proposed=bool(o.get("proposed")), why=why.get(x["name"]),
                          rings=oz_regs.get(x["name"], {}).get("rings", []),
                          label=oz_regs.get(x["name"], {}).get("label"), **density(x, oz_regs.get(x["name"]))))
    dmas = [dict(d, rings=dma_regs.get(d["name"], {}).get("rings", []), label=dma_regs.get(d["name"], {}).get("label"),
                 **density(d, dma_regs.get(d["name"]))) for d in z["dmas"]]
    closed = []
    geo = {c["label"]: c.get("vertices") for c in net["conduits"]}
    for lab in z["closed_pipes"]:
        p = wnet["pipes"][lab]
        closed.append({"pipe": lab, "latlng": ll(_mid_along(geo.get(lab) or [xy[p["a"]], xy[p["b"]]]))})
    if z["unserved"]:
        for f in z["flags"]:
            if f["text"].endswith("nodes have no pipe path to any OHT"):
                f["text"] = _unserved_note(wnet, z["unserved"])
                f["hi"] = _unserved_note(wnet, z["unserved"], hi=True)
    res = {"ok": True, "zones": zones, "dmas": dmas, "closed": closed, "pipe_zone": pipe_zone, "pipe_dma": pipe_dma,
           "unserved_pts": [ll(xy[n]) for n in z["unserved"]],
           # every junction with its population and bulk demand: the checking map of the page (user 30-Oct-2026)
           "node_load": [[str(n), *(round(c, 6) for c in ll(xy[n])), round(v["pop"], 1), round(v.get("bulk_raw", 0.0), 1)]
                         for n, v in wnet["nodes"].items() if n in xy],
           "proposed": [{"name": p["name"], "latlng": p["latlng"]} for p in z["proposed"]],
           "flags": z["flags"], "moved": z["moved"], "unserved": len(z["unserved"]),
           "refs": {k: crit[k]["ref"] for k in ("oz_max_population", "esr_capacity_share", "dma_max_connections",
                                                "cwr_when_tubewells_over", "persons_per_connection")},
           "population": round(sum(v["pop"] for v in wnet["nodes"].values()))}
    res.update(_barrier_res(stem, net))
    res.update(_loop_res(z, wnet))
    res["flags"] = res["flags"] + _loop_flags(z, wnet)
    if net.get("barriers") or net.get("crossings"):
        hi = "; ".join(x for x in (wb.summary_hi(net["barriers"], net["barrier_cuts"]),
                                   ("crossings: " + wb.crossing_summary_hi(net["crossings"])) if net.get("crossings") else "")
                       if x)
        res["flags"] = res["flags"] + [{"zone": None, "level": "info", "text": _barrier_check(net)["detail"], "hi": hi}]
    # the wards of a DXF network: the population they gave, the junctions in none of them (user 30-Oct-2026)
    wf, res["ward_out_pts"] = _ward_flags(net.get("ward_note"), ll, xy)
    bf, res["bulk_pts"] = _bulk_flags(wnet.get("bulk"), ll, xy)
    res["flags"] = wf + _noconn_flags(net.get("noconn_note")) + bf + res["flags"]
    # separate pieces of the drawing close to each other, joined by no pipe: a gap to join (user 30-Oct-2026)
    near = (crit.get("near_gap_m") or {}).get("value", wb.NEAR_M)
    gaps = wb.near_parts(net, net.get("barriers"), max_m=near, skip=wb.cut_ends(net.get("barrier_cuts")))
    res["near_gaps"] = [{"a": g["a"], "b": g["b"], "dist_m": g["dist_m"], "latlngs": [ll(p) for p in g["xy"]]}
                        for g in gaps]
    if gaps:
        res["flags"] = res["flags"] + [{"zone": None, "level": "warn", "text": wb.near_summary(gaps, near),
                                        "hi": wb.near_summary_hi(gaps, near)}]
    mb = dm.mass_balance(crit)
    res["storage"] = {"share": round(dm.storage_share(crit), 4), "mass_balance": round(mb["share"], 4),
                      "min_share": crit["esr_capacity_share"]["value"], "hours": mb["hours"],
                      "windows": crit["oht_inflow_hours"]["value"], "ref": crit["esr_capacity_share"]["ref"],
                      "fire_share": round(crit["fire_storage_share"]["value"], 4)}
    return res
