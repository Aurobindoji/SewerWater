"""The water module's calls of the map page (/api/w/water_zoning, /api/w/water_design, /api/w/water_last): zoning
(OZ per OHT, DMAs) and pipe design of the project's layout, the results kept with the project.

Existing OHTs are placed first (capacity, staging); zoning.plan gives each the area it can serve and PROPOSES new
OHTs for the rest (capacity 33 % of their OZ). An OHT without a staging (a proposed one, or a new one placed without)
gets it from the design: the pipes are designed with a trial staging (highest ground of its OZ - ground at the OHT +
17 m + a head loss allowance), then the staging is lowered to what the designed pipes need for 17 m at the weakest
node of its OZ (rounded up to 0.5 m) and the network is run again with it.

The layout is made by the same page / code as for sewers (server.run_layout, nodes only along the roads -
no node at the bends) into water_app\\output\\<project>\\; the OHTs come from the page: name, place, existing
capacity (KL; empty = new OHT, sized here), staging (m, lowest water level above ground) and tube wells.
"""
import collections
import csv
import json
import math
import os
import time

from . import barriers as wb
from . import geo as wgeo
from . import hindi
from . import server as ui
from . import zone_geom as szoning

from . import demand as dm
from . import design as wd
from . import dpr as wdpr
from . import dpr_rm as wdpr_rm
from . import hydraulics as hy
from . import population as wpop
from . import prv as wprv
from . import rising as wrising
from . import zoning as wz

BOUNDARY_GAP_M = 400.0         # zone boundaries drawn across open land up to this between points
STEP_M = 10.0                  # points along the pipes / the project boundary for drawing the zone boundaries: as
                               # near each other as two mains along one road lie (40 m let a zone's line cut the
                               # other zone's main between its points - user 14-Nov-2026)
ALONE_M = 60.0                 # a pipe with no other pipe this near beside it (open land) is drawn in a strip
STRIP_M = 20.0                 # ... this wide to each side: a zone reached by one pipe does not shrink to a point
STRAIGHT_M = 25.0              # a zone boundary is straightened: its points up to this far off a straight line go
                               # (user request 14-Nov-2026), where no point of the network changes its side by it


def _project_area(stem):
    """The project boundary polygon(s) in metres: the polygon called boundary, else the wards together (as the
    layout takes them); [] when there is none."""
    import re
    from . import geo
    f = os.path.join(ui.proj_dir(), stem + ".kml")
    if not os.path.isfile(f):                       # a network from a DXF: no boundary drawn
        return []
    k = geo.read_kml(f)
    polys = [f for f in k["polygons"] if len(f["coords"]) >= 3]
    bnd = [f for f in polys if re.search(r"boundary|सीमा", f"{f.get('folder') or ''} {f.get('name') or ''}", re.I)]
    _, to_xy = ui.converters_for(stem)
    return [[tuple(p) for p in to_xy([[c[1], c[0]] for c in f["coords"]])] for f in (bnd or polys)]


def _along(pts, step):
    """Points every `step` m along a polyline (its own vertices kept)."""
    out = [tuple(pts[0])]
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        n = max(1, int(L // step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(1, n + 1)]
    return out


def _mid_along(pts):
    """The point half way ALONG a pipe (it follows the bends of its road) - its valve is drawn there, on the pipe."""
    seg = [math.dist(pts[i - 1], pts[i]) for i in range(1, len(pts))]
    goal = sum(seg) / 2
    for i, L in enumerate(seg, 1):
        if goal <= L or i == len(seg):
            t = min(1.0, goal / L) if L else 0.0
            return (pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t)
        goal -= L
    return tuple(pts[0])


def _enclosed(neighbors, keep, inside):
    """The triangles left out for their length that the kept ones close in on every side (open land in the middle
    of the zones - user 14-Nov-2026: the zones' lines made an empty figure there): True for those. Open land that
    reaches the edge of all the points, or the outside of the project boundary, stays out."""
    import numpy as np
    n = len(keep)
    out = np.zeros(n, dtype=bool)                             # open land reached from outside
    stack = [i for i in range(n) if not keep[i] and (not inside[i] or (neighbors[i] < 0).any())]
    out[stack] = True
    while stack:
        i = stack.pop()
        for j in neighbors[i]:
            if j >= 0 and not keep[j] and not out[j]:
                out[j] = True
                stack.append(j)
    return ~keep & ~out & inside


def _zone_tri(stem, net):
    """Triangles for zone_regions, built once for OZs and DMAs: points along every pipe (each standing for the nearer
    end of its pipe - a pipe between two zones is cut half way, where its valve is drawn) and along the project
    boundary (each standing for the node of the nearest pipe point); triangles
    longer than BOUNDARY_GAP_M (unless the zones close them in - _enclosed) or with their middle outside the boundary
    dropped. Returns (tg, node of each point,
    (X, Y) of the points on the pipes - the ones a straightened boundary must not pass)."""
    import numpy as np
    from matplotlib.path import Path
    import matplotlib.tri as mtri
    pts, who = [], []
    way, of_pipe, way_of = [], [], []                         # the pipe's direction at each point; its pipe
    for c in net["conduits"]:
        vs = c.get("vertices") or [net["nodes"][c["start_node"]]["xy"], net["nodes"][c["stop_node"]]["xy"]]
        run = _along(vs, STEP_M)
        half, gone = sum(math.dist(a, b) for a, b in zip(run, run[1:])) / 2, 0.0
        for i, p in enumerate(run):
            a, b = run[max(0, i - 1)], run[min(len(run) - 1, i + 1)]
            L = math.dist(a, b)
            gone += math.dist(run[i - 1], p) if i else 0.0
            pts.append(p)
            who.append(c["start_node"] if gone <= half else c["stop_node"])
            way.append(((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-9 else None)
            of_pipe.append(len(way_of))
        way_of.append(c["label"])
    if len(pts) < 3:
        return None, [], None
    n_pipe = len(pts)
    # a pipe alone in open land: a point to each side of it, so its zone has a strip there, not a line of no width
    from scipy.spatial import cKDTree
    P1 = np.array(pts)
    near = cKDTree(P1).query_ball_point(P1, ALONE_M)
    pipe_of = np.array(of_pipe)
    for i in range(n_pipe):
        if way[i] is None:
            continue
        ux, uy = way[i]
        other = [j for j in near[i] if pipe_of[j] != pipe_of[i]]
        q = P1[other] - P1[i]
        if len(other) and np.any(np.abs(q[:, 0] * -uy + q[:, 1] * ux) > STRIP_M * 0.6):
            continue                                          # another pipe beside it
        for sgn in (1.0, -1.0):
            pts.append((pts[i][0] - sgn * uy * STRIP_M, pts[i][1] + sgn * ux * STRIP_M))
            who.append(who[i])
    area = _project_area(stem)
    P0 = np.array(pts)
    for ring in area:
        for p in _along(list(ring) + [ring[0]], STEP_M)[:-1]:
            pts.append(p)
            who.append(who[int(np.argmin((P0[:, 0] - p[0]) ** 2 + (P0[:, 1] - p[1]) ** 2))])
    X = np.array([p[0] for p in pts])
    Y = np.array([p[1] for p in pts])
    tri = mtri.Triangulation(X, Y)
    T = tri.triangles
    el = np.max(np.stack([np.hypot(X[T[:, i]] - X[T[:, j]], Y[T[:, i]] - Y[T[:, j]])
                          for i, j in ((0, 1), (1, 2), (2, 0))]), axis=0)
    keep = el <= BOUNDARY_GAP_M
    inside = np.ones(len(T), dtype=bool)
    if area:
        mid = np.column_stack([X[T].mean(axis=1), Y[T].mean(axis=1)])
        inside = np.zeros(len(T), dtype=bool)
        for ring in area:
            inside |= Path(np.array(ring)).contains_points(mid)
        keep &= inside
    keep |= _enclosed(tri.neighbors, keep, inside)
    ids = [f"p{i}" for i in range(len(pts))]
    return (ids, X, Y, T[keep]), who, (X[:n_pipe], Y[:n_pipe])


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


def _wards(stem, req):
    """The wards drawn on a DXF network (user request 30-Oct-2026: its population by ward, not spread evenly) in the
    project's metres: [{"name", "population", "xy"}]; a ring of fewer than 3 points is left out, a population not a
    number: 0."""
    raw = [w for w in (req or {}).get("wards") or [] if len((w or {}).get("latlngs") or []) >= 3]
    if not raw:
        return []
    to_xy = ui.converters_for(stem)[1]
    wt = ward_table(req)
    by_no = {r["no"]: r for r in (wt or {}).get("rows", [])}
    out = []
    for i, w in enumerate(raw, 1):
        try:
            p = max(float(str(w.get("population")).replace(",", "")), 0.0)
        except (TypeError, ValueError):
            p = 0.0
        ring = [[float(q[0]), float(q[1])] for q in w["latlngs"]]
        row = by_no.get(str(w.get("ward_no") or "").strip())
        d = {"name": str(w.get("name") or "").strip() or f"Ward {i}", "population": p,
             "character": char_name(w.get("character")), "xy": [tuple(q) for q in to_xy(ring)]}
        if row:                                    # the table's ward (user decision 7-Nov-2026): its covered population
            d.update(name=row["name"], population=row["covered"], table=row, character=row["char"])
        out.append(d)
    return out


def _has_conn(c):
    """A pipe with service connections: not one marked without them on the DXF network (a feeder / transmission main,
    user 30-Oct-2026), nor a new pipe along a crossing line - no population is put on those."""
    return not (c.get("no_conn") or c.get("crossing"))


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


def _ward_pop(net, wards):
    """Population per junction from the wards (layout.population_by_polygons: by half the pipe length at each
    junction inside a ward); a junction in no ward gets none (user decision 30-Oct-2026: 0 and a warning, the total
    given on the page not used). -> (pop, note for the flags)."""
    from . import layout as wl
    served = dict(net, conduits=[c for c in net["conduits"] if _has_conn(c)])
    pop, rows = wl.population_by_polygons(served, [(w["xy"], w["population"]) for w in wards])
    half = collections.defaultdict(float)
    for c in served["conduits"]:
        half[c["start_node"]] += (c["length_m"] or 0.0) / 2
        half[c["stop_node"]] += (c["length_m"] or 0.0) / 2
    out = sorted((n for n in half if n not in pop and (net["nodes"].get(n) or {}).get("xy")), key=str)
    of = {}                                    # junction -> its ward (the first drawn that holds it), for the growth
    for i, w in enumerate(wards):
        for n in pop:
            if n not in of and wl.inside(net["nodes"][n]["xy"], w["xy"]):
                of[n] = i
    note = {"wards": len(wards), "population": round(sum(pop.values())), "junctions": len(pop), "ward_of": of,
            "list": [{"name": w["name"], "population": w["population"], "character": w["character"],
                      "table": w.get("table")} for w in wards],
            "outside": out, "outside_m": round(sum(half[n] for n in out)),
            "empty": [w["name"] for w, r in zip(wards, rows) if not r["manholes inside"]],
            "no_pop": [w["name"] for w, r in zip(wards, rows) if r["manholes inside"] and w["population"] <= 0]}
    return pop, note


def _ward_flags(note, ll, xy):
    """The wards' lines among the zoning's flags, and the junctions in no ward for the map."""
    if not note:
        return [], []
    L = lambda a: ", ".join(a[:8]) + (" ..." if len(a) > 8 else "")
    f = [{"zone": None, "level": "info",
          "text": f"population from {note['wards']} ward(s) drawn on the map: {note['population']:,} on "
                  f"{note['junctions']:,} junctions (by the pipe length at each)",
          "hi": f"आबादी नक्शे पर खींचे {note['wards']} वार्डों से: {note['population']:,}, {note['junctions']:,} junctions पर "
                f"(हर junction पर pipe की लंबाई के अनुपात में)"}]
    if note["outside"]:
        f.append({"zone": None, "level": "warn",
                  "text": f"{len(note['outside']):,} junctions ({note['outside_m']:,} m of pipe) lie in no ward - no population "
                          f"there; draw / widen a ward over them if people live there (orange dots on the map)",
                  "hi": f"{len(note['outside']):,} junctions ({note['outside_m']:,} m pipe) किसी वार्ड में नहीं - वहाँ आबादी 0; "
                        f"वहाँ लोग रहते हों तो वार्ड खींचें / बढ़ाएँ (नक्शे पर नारंगी बिंदु)"})
    if note["empty"]:
        f.append({"zone": None, "level": "warn",
                  "text": f"ward(s) with no junction inside - their population not counted: {L(note['empty'])}",
                  "hi": f"जिन वार्डों में कोई junction नहीं - उनकी आबादी नहीं गिनी गई: {L(note['empty'])}"})
    if note["no_pop"]:
        f.append({"zone": None, "level": "warn",
                  "text": f"ward(s) without population - their junctions get none: {L(note['no_pop'])}",
                  "hi": f"जिन वार्डों में population नहीं भरी - उनके junctions पर आबादी 0: {L(note['no_pop'])}"})
    return f, [ll(xy[n]) for n in note["outside"] if n in xy]


def _load(stem, req=None):
    """The project's network (the layout, or the DXF network as it is now on the map - saved or not) and its
    population per node: of the wards (layout; on a DXF network the wards drawn on the map, net["ward_note"]), else
    the total given on the page spread by pipe length (half of each pipe to each of its ends)."""
    folder, f_mh, f_co, f_pop = ui._paths(stem)
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


def _ward_rest(net, pop, wards, req):
    """The wards of the table with no boundary on the map (user decision 7-Nov-2026): their covered population on the
    junctions in no ward, by the pipe length at each - all junctions when every one is in a ward (a warning)."""
    wt = ward_table(req)
    if not wt:
        return
    drawn = {w["table"]["no"] for w in wards if w.get("table")}
    rest = [r for r in wt["rows"] if r["no"] not in drawn]
    if not rest:
        return
    note = net["ward_note"]
    half = collections.defaultdict(float)
    for c in filter(_has_conn, net["conduits"]):
        half[c["start_node"]] += (c["length_m"] or 0.0) / 2
        half[c["stop_node"]] += (c["length_m"] or 0.0) / 2
    to = [n for n in note["outside"] if half.get(n)] or [n for n in half if (net["nodes"].get(n) or {}).get("xy")]
    L = sum(half[n] for n in to) or 1.0
    tot = sum(r["covered"] for r in rest)
    by_char = collections.defaultdict(float)       # the characters of these wards (7-Nov-2026): each junction's parts
    for r in rest:
        by_char[r["char"]] += r["covered"]
    parts = note.setdefault("rest_parts", {})
    for n in to:
        pop[n] = pop.get(n, 0.0) + tot * half[n] / L
        if any(by_char):
            parts[n] = {c: v * half[n] / L for c, v in by_char.items()}
    note["rest"] = {"wards": [r["no"] for r in rest], "population": round(tot), "on_outside": bool(note["outside"]),
                    "chars": sum(1 for r in rest if r["char"])}
    note["population"] = round(sum(pop.values()))
    if note["outside"]:
        note["outside"] = []                      # the junctions in no ward now have the table's other wards


def _ward_growth(wn, wnet, pop, crit, req):
    """Wards given a character on the map (user decision 6-Nov-2026, Riverside water DPR p76, criteria ward_growth):
    the population on their junctions is the present one, grown by the character's design-year factor in place of the
    factor of the page / projection; every junction gets its base-year and +15 years shares (node["stage"]) - the
    others the page's / projection's, when given, else 1. The ward table's wards without a boundary (7-Nov-2026) share
    junctions in no ward (wn["rest_parts"]: {junction: {character: population}}): such a junction mixes them. Returns
    the number of wards with a character (0: nothing done)."""
    G = crit["ward_growth"]["value"]
    wn = wn or {}
    chars = [w["character"] if w["character"] in G else "" for w in wn.get("list", [])]
    n_rest = (wn.get("rest") or {}).get("chars", 0)
    if not any(chars) and not n_rest:
        return 0
    rest = wn.get("rest_parts") or {}
    f = _factor(req)                               # wnet's population: the junction's x f (_zones)
    pj, given = req.get("_proj"), ui.stage_inputs(req)
    city = sum(v["pop"] for v in wnet["nodes"].values())
    if pj:
        uni = {t: pj["ratio"][t] / pj["ratio"]["ult"] for t in ("init", "mid")}
    else:
        uni = {t: (given[k] / city if given.get(k) and city else 1.0) for t, k in (("init", "pop_initial"),
                                                                                 ("mid", "pop_mid"))}
    for n, v in wnet["nodes"].items():
        p = pop.get(n, 0.0)
        parts = {c: q for c, q in (rest.get(n) or {}).items() if c in G or c == ""}
        i = wn.get("ward_of", {}).get(n)
        own = chars[i] if i is not None else ""
        parts[own] = parts.get(own, 0.0) + max(p - sum(parts.values()), 0.0)
        ult = sum(q * (G[c][2] if c else f) for c, q in parts.items())
        if not any(c and q > 0 for c, q in parts.items()) or ult <= 0:
            v["stage"] = dict(uni)
            continue
        v["pop"] = ult
        v["stage"] = {t: sum(q * (G[c][j] if c else f * uni[t]) for c, q in parts.items()) / ult
                      for j, t in ((0, "init"), (1, "mid"))}
    return sum(1 for c in chars if c) + n_rest


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
        nodes = {n for n, v in wnet["nodes"].items() if n not in taken and v.get("xy") and ui._inside(v["xy"], xy)}
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


def _factor(req):
    f = float(req.get("pop_factor") or 1.0)
    if not 0.1 <= f <= 10:
        raise ValueError("आबादी गुणक 0.1 से 10 के बीच दें")
    return f


def ward_table(req):
    """The wards of the page's table (user decision 7-Nov-2026: the user gives the number of wards, then each ward's
    number, name, population of a year he gives (e.g. 2025) and the share of it covered by the project; households,
    area and the 2011 census for the DPR): {"year", "rows": [{no, name, pop, cov (share 0-1), covered, hh, area,
    census, char, kcov}], "total" (the covered population of that year), "growth"} or None.
    char (user decision 7-Nov-2026): the ward's character - its population grows by the character's factors of the
    page (growth: {character: [base, middle, design]} on the population of the year, default criteria ward_growth =
    the Riverside DPR p76 / technical.xlsx 'T' values) in place of the projection's; "" = the projection's. kcov: the
    share of the ward's area in the zone (from a KML, only shown as a check - % covered is the user's)."""
    t = (req or {}).get("ward_table") or {}
    # a 0 is a number, not empty (9-Nov-2026: a character with no ward in the town - its 0 left Far-open unbalanced)
    num = lambda v, d=0.0: float(str(v).replace(",", "")) if str("" if v is None else v).strip() not in ("", "None") else d
    G = ward_growth_of(t)
    rows = []
    for i, r in enumerate(t.get("rows") or [], 1):
        try:
            pop, cov = max(num(r.get("pop")), 0.0), min(max(num(r.get("cov"), 100.0), 0.0), 100.0) / 100.0
        except ValueError:
            continue
        no = str(r.get("no") or "").strip() or str(i)
        rows.append({"no": no, "name": str(r.get("name") or "").strip() or f"Ward {no}", "pop": pop, "cov": cov,
                     "covered": pop * cov, "hh": num(r.get("hh"), None) if r.get("hh") not in (None, "") else None,
                     "area": num(r.get("area"), None) if r.get("area") not in (None, "") else None,
                     "census": num(r.get("census"), None) if r.get("census") not in (None, "") else None,
                     "char": char_name(r.get("char")) if char_name(r.get("char")) in G else "",
                     "kcov": num(r.get("kcov"), None) if r.get("kcov") not in (None, "") else None})
    if not rows or sum(r["covered"] for r in rows) <= 0:
        return None
    y = t.get("year")
    city, C0 = {}, wd.load_criteria().get("ward_town_population", {}).get("value", {})
    given = {char_name(k): v for k, v in t.get("city").items()} if isinstance(t.get("city"), dict) else {}
    for k in G:                                    # the whole town's population of the year by character (Far-open):
        try:                                       # the page's, else criteria (the example's Springfield)
            city[k] = num(given.get(k), None) if k in given else C0.get(k)
        except ValueError:
            city[k] = None
    sat = t.get("sat") if "sat" in t else wd.load_criteria().get("ward_saturation_density", {}).get("value")
    try:                                           # the saturation density (8-Nov-2026): the page's, blank = none
        sat = num(sat, None)
    except ValueError:
        sat = None
    gd, dens = {char_name(k): v for k, v in t["dens"].items()} if isinstance(t.get("dens"), dict) else {}, {}
    for k, v in WARD_DENS.items():                 # the character by the density (the page's; for the DPR's note)
        try:
            dens[k] = num(gd.get(k), v)
        except ValueError:
            dens[k] = v
    return {"year": int(y) if str(y or "").strip() else None, "rows": rows, "total": sum(r["covered"] for r in rows),
            "growth": G, "city": city, "sat": sat if sat and sat > 0 else None, "dens": dens}


# the characters of a ward, densest first (user decision 9-Nov-2026): CPHEEO Manual on Water Supply 2024 Part A
# Annexure 2.7 p974's categories - low / medium / high / saturated, "the cores of the city" at saturation - with the
# Riverside water DPR p76's word in brackets (its Proximal Developed / Core / Proximal Developing / Far-open, in that
# order of density); the old names of a saved project / list / map read as the new (char_name)
WARD_CHARS = ("Saturated (Core)", "High (Proximal Developed)", "Medium (Proximal Developing)", "Low (Far-open)")
OLD_CHARS = dict(zip(("Proximal Developed", "Core", "Proximal Developing", "Far-open"), WARD_CHARS))
CORE_CHAR = WARD_CHARS[0]


def char_name(c):
    """A ward character by its name now: an old one (before 9-Nov-2026) as its new one; "" for none."""
    c = str(c or "").strip()
    return OLD_CHARS.get(c, c)


# the character of a ward by its density of the table's year, persons / ha above (example technical.xlsx 'T' X346; the
# ranges not CPHEEO's - its Annexure 2.7 p974 chooses them by the town's size); the rest Low (Far-open)
WARD_DENS = {WARD_CHARS[0]: 585, WARD_CHARS[1]: 310, WARD_CHARS[2]: 170}
# CPHEEO Water Manual Part A Annexure 2.7 p974: the developed core's density has practically reached saturation -
# "very close to the present density"; its design factor above this warned of (the app's reading: 10 %, as the
# saturation density's default)
CORE_NEAR = 1.10


def saturation_over(wt, ratio):
    """The saturation density (CPHEEO Manual on Water Supply 2024 Part A, Annexure 2.7 p974; user decision 8-Nov-2026:
    only warned of): the developed core's present density, a little above, is the upper limit of every ward's future
    density. The table's wards with an area whose design-year density - the ward's population x its character's
    design factor, else the adopted ratio (ratio["ult"]) - is above it: [{no, name, char, d0, d}] (per ha)."""
    sat, out = (wt or {}).get("sat"), []
    if not sat:
        return out
    for r in wt["rows"]:
        a = r.get("area") or 0.0
        f = wt["growth"][r["char"]][2] if r["char"] else (ratio or {}).get("ult")
        if a <= 0 or r["pop"] <= 0 or not f:
            continue
        d0 = r["pop"] / a
        if d0 * f > sat:
            out.append({"no": r["no"], "name": r["name"], "char": r["char"], "d0": round(d0, 1), "d": round(d0 * f, 1)})
    return out


FAR_OPEN = WARD_CHARS[3]


def far_open_balance(wt, f):
    """The balancing factors of Far-open (user decision 7-Nov-2026; example technical.xlsx 'T' P470 = AD472 / AC473,
    Riverside water DPR p76): the whole town's population of the table's year by character (wt["city"], the page's;
    default the example's Springfield wards 6,98,311 / 6,73,088 / 7,20,858 / 5,87,585), grown by the adopted method
    (f["town_ratio_from"]) is the town of each stage; less the other characters x their factors, over Far-open's
    population: Far-open's factor - so the town's wards add up to the adopted projection in every stage.
    -> {"factors": [init, mid, ult], "city", "total", "target"} or {"error": text} or None (not given)."""
    P, R = (wt or {}).get("city") or {}, (f or {}).get("town_ratio_from")
    if not R or not P or any(v is None for v in P.values()):
        return None
    if any(v < 0 for v in P.values()) or not (P.get(FAR_OPEN) or 0) > 0:
        return {"error": "Far-open की शहर की आबादी 0 से अधिक दें"}
    S = sum(P.values())
    G = wt["growth"]
    out, target = [], {}
    for j, t in enumerate(("init", "mid", "ult")):
        target[t] = S * R[t]
        x = (target[t] - sum(P[k] * G[k][j] for k in P if k != FAR_OPEN)) / P[FAR_OPEN]
        if x <= 0:
            return {"error": f"Far-open का गुणक {x:.3f} ({t}) - बाकी चरित्रों के गुणक शहर की projection से ज़्यादा"}
        out.append(round(x, 6))
    # Far-open growing slower than a denser character: the fixed factors do not suit this town's growth
    low = out[2] < max(G[k][2] for k in P if k != FAR_OPEN)
    # Far-open below 1 (user decision 10-Nov-2026): its wards' population falling - the others' factors too high
    below = [t for t, x in zip(("init", "mid", "ult"), out) if x < 1]
    return {"factors": out, "city": P, "total": S, "target": target, "ratio": R, "low": low, "below": below}


def ward_growth_of(t):
    """The factors of each ward character (base / middle / design on the population of the ward table's year): the
    page's (t["growth"], yellow on the page, 7-Nov-2026) where given as three positive numbers, else criteria.json
    ward_growth."""
    G = {k: list(v) for k, v in wd.load_criteria()["ward_growth"]["value"].items()}
    for k, v in ((t or {}).get("growth") or {}).items():
        k = char_name(k)
        try:
            f = [float(str(x).replace(",", "")) for x in v]
        except (TypeError, ValueError):
            continue
        if k in G and len(f) == 3 and all(x > 0 for x in f):
            G[k] = f
    fo = (t or {}).get("_far_open")                # balanced by the projection (_with_projection, 7-Nov-2026)
    if fo and FAR_OPEN in G:
        G[FAR_OPEN] = list(fo)
    return G


def ward_stages(wt, ratio):
    """The wards of the table in the base / middle / design years: a ward with a character its covered population x
    the character's factors, the others x ratio ({init, mid, ult} from the table's year; None: those not counted).
    -> {"init", "mid", "ult", "rows": [{no, char, init, mid, ult}]}."""
    out = {"init": 0.0, "mid": 0.0, "ult": 0.0, "rows": []}
    for r in wt["rows"]:
        f = wt["growth"][r["char"]] if r["char"] else ([ratio[t] for t in ("init", "mid", "ult")] if ratio else None)
        x = {"no": r["no"], "char": r["char"]}
        for j, t in enumerate(("init", "mid", "ult")):
            x[t] = r["covered"] * f[j] if f else None
            out[t] += x[t] or 0.0
        out["rows"].append(x)
    return out


WARD_NO_KEYS = ("w_num", "ward_no", "ward no", "wardno", "w_no", "ward_num", "ward number")
WARD_NAME_KEYS = ("w_name", "ward_name", "ward name", "wardname")
WARD_HH_KEYS = ("w_hh", "hh", "households", "household", "house_hold")


def ward_kml_table(text):
    """The ward table from a KML of the ward boundaries (user decision 7-Nov-2026, e.g. 'MAPLEWOOD ZONE AND WARDS.kml'):
    a polygon with a ward number / ward name field is a ward, the others the zone. Each ward: its number, name, area
    (ha, of its boundary), the share of that area inside the zone (kcov, only a check: % covered stays the user's, by
    population as technical.xlsx T1) and, where the KML gives them above 0, population and households; its boundary
    (the largest part) for the map. -> {"rows", "wards": [{no, name, latlngs}], "zone": {name, area_ha} | None,
    "notes": [(hi, en)]}."""
    import numpy as np
    from matplotlib.path import Path
    k = wgeo.read_kml("wards.kml", text=text)
    low = lambda d: {str(a).strip().lower(): b for a, b in (d or {}).items() if a}
    pick = lambda d, keys: next((str(d[x]).strip() for x in keys if str(d.get(x) or "").strip()), "")
    polys = [p for p in k["polygons"] if len(p["coords"]) >= 3]
    if not polys:
        raise ValueError("KML में कोई polygon नहीं")
    c0 = polys[0]["coords"][0]
    epsg = wgeo.utm_epsg(c0[0], c0[1])
    wards, zone = collections.OrderedDict(), []
    for p in polys:
        d = low(p["data"])
        no, nm = pick(d, WARD_NO_KEYS), pick(d, WARD_NAME_KEYS)
        xy = np.array(wgeo.to_xy(p["coords"], epsg))
        a = abs(float(np.dot(xy[:-1, 0], xy[1:, 1]) - np.dot(xy[1:, 0], xy[:-1, 1])
                      + xy[-1, 0] * xy[0, 1] - xy[0, 0] * xy[-1, 1])) / 2
        if a < 1.0:                                # a ring of no area
            continue
        if not no and not nm:
            zone.append((p, xy, a))
            continue
        key = no or nm
        w = wards.setdefault(key, {"no": no, "name": nm or p["name"] or f"Ward {no}", "parts": [], "data": d})
        w["parts"].append((p, xy, a))
    if not wards:
        raise ValueError("KML में कोई वार्ड नहीं (ward number / name का field, जैसे W_NUM / W_Name)")
    zpaths = [Path(z[1]) for z in zone]
    num = lambda v: wgeo.number(v) if wgeo.number(v) and wgeo.number(v) > 0 else None
    rows, out_w, notes = [], [], []
    for i, (key, w) in enumerate(wards.items(), 1):
        area = sum(x[2] for x in w["parts"])
        kcov = None
        if zpaths:
            inside = total = 0
            for _, xy, a in w["parts"]:
                step = max(math.sqrt(a / 60000.0), 1.0)
                (x0, y0), (x1, y1) = xy.min(axis=0), xy.max(axis=0)
                gx, gy = np.meshgrid(np.arange(x0 + step / 2, x1, step), np.arange(y0 + step / 2, y1, step))
                pts = np.column_stack([gx.ravel(), gy.ravel()])
                pts = pts[Path(xy).contains_points(pts)]
                total += len(pts)
                hit = np.zeros(len(pts), bool)
                for zp in zpaths:
                    hit |= zp.contains_points(pts)
                inside += int(hit.sum())
            kcov = round(100.0 * inside / total, 1) if total else None
        pop, hh = num(w["data"].get("w_pop") or pick(w["data"], wgeo.POP_KEYS)), num(pick(w["data"], WARD_HH_KEYS))
        no = w["no"] or str(i)
        rows.append({"no": no, "name": w["name"], "pop": round(pop) if pop else "", "cov": "",
                     "hh": round(hh) if hh else "", "area": round(area / 1e4, 2), "census": "", "char": "",
                     "kcov": kcov if kcov is not None else ""})
        big = max(w["parts"], key=lambda x: x[2])[0]
        out_w.append({"no": no, "name": w["name"], "latlngs": [[c[1], c[0]] for c in big["coords"]]})
        if len(w["parts"]) > 1:
            notes.append((f"{w['name']}: {len(w['parts'])} हिस्से - नक्शे पर सबसे बड़ा, क्षेत्रफल सबका",
                          f"{w['name']}: {len(w['parts'])} parts - the largest on the map, the area of all"))
    if pop_given := [r for r in rows if r["pop"] != ""]:
        notes.append((f"KML की आबादी {len(pop_given)} वार्डों में भरी - उसका वर्ष जाँचें (तालिका का वर्ष "
                      f"ऊपर है), बाकी में भरें",
                      f"the KML's population filled in {len(pop_given)} ward(s) - check its year (the table's year "
                      f"is above), fill in the others"))
    if not zone:
        notes.append(("KML में zone का polygon (बिना ward number) नहीं - zone में क्षेत्रफल-% नहीं निकला",
                      "no zone polygon (one without a ward number) in the KML - no area share in the zone"))
    zi = {"name": " + ".join(z[0]["name"] or "zone" for z in zone),
          "area_ha": round(sum(z[2] for z in zone) / 1e4, 2)} if zone else None
    return {"rows": rows, "wards": out_w, "zone": zi, "notes": notes}


def projection_of(req):
    """The population projection of the page (population.py, user request 30-Oct-2026): req["projection"] =
    {base_pop, census, method} with req["base_year"]; None when no base-year population or census is given. With the
    ward table (user decision 7-Nov-2026) its covered population of its year, grown from that year."""
    p = (req or {}).get("projection") or {}
    wt = ward_table(req)
    if not str(p.get("census") or "").strip() or (p.get("base_pop") in (None, "") and not wt):
        return None
    if (req or {}).get("base_year") in (None, ""):
        raise ValueError("projection के लिए आधार वर्ष दें")
    if wt:
        if not wt["year"]:
            raise ValueError("वार्डों की आबादी का वर्ष दें (जैसे 2025)")
        f = wpop.project(req["base_year"], wt["total"], p["census"], p.get("method"), from_year=wt["year"])
        fo = far_open_balance(wt, f)               # Far-open by the adopted method (7-Nov-2026)
        if fo and "factors" in fo:
            wt["growth"][FAR_OPEN] = fo["factors"]
            f["far_open"] = fo
        elif fo:
            f["far_open_error"] = fo["error"]
        if wt["sat"]:                              # the saturation density (CPHEEO Annexure 2.7, 8-Nov-2026)
            f["saturation"] = {"value": wt["sat"], "over": saturation_over(wt, f["ratio_from"])}
        pd = wt["growth"].get(CORE_CHAR)
        if pd and pd[2] > CORE_NEAR:               # CPHEEO Annexure 2.7 p974: the core near saturation
            f["core_factor"] = pd[2]
        if any(r["char"] for r in wt["rows"]):     # wards with a character (7-Nov-2026): the project's own stages
            f["wards"] = ward_stages(wt, f["ratio_from"])
        return f
    return wpop.project(req["base_year"], float(str(p["base_pop"]).replace(",", "")), p["census"], p.get("method"))


def _with_projection(req):
    """With a projection: the population on the junctions (the wards / the total of the page) is the base year's -
    grown by the adopted method's +30 years ratio, in place of the factor of the page; the stage check's base year and
    +15 years from the same ratios (set in _zones, where the base-year population on the junctions is known)."""
    f = projection_of(req)
    if f is None:
        wt = ward_table(req)                        # the ward table, no census: its population x the page's factor
        return dict(req, pop_total=wt["total"]) if wt else req
    if f.get("from_year"):                          # the wards' population of their year: grown from it
        out = dict(req, pop_factor=f["ratio_from"]["ult"], pop_total=f["from_pop"], _proj=f)
        if f.get("far_open"):                       # the balanced Far-open: for every ward_table(req) after this
            out["ward_table"] = dict(req["ward_table"], _far_open=f["far_open"]["factors"])
    else:
        out = dict(req, pop_factor=f["ratio"]["ult"], pop_total=f["base_pop"], _proj=f)
    out.pop("pop_initial", None)
    out.pop("pop_mid", None)
    return out


def _proj_flags(f, s0):
    """The projection among the zoning's flags: the adopted method and its stages; a base-year population on the
    junctions (wards) not the one given."""
    if not f:
        return []
    nm = f["names"][f["adopted"]]
    st = ", ".join(f"{f['years'][t]} {f['pop'][t]:,.0f}" for t in ("init", "mid", "ult"))
    out = [{"zone": None, "level": "info",
            "text": f"population projection - {nm[0]}: {st} (x {f['ratio']['ult']:.3f} at +30 years)",
            "hi": f"आबादी projection - {nm[1]}: {st} (+30 वर्ष पर x {f['ratio']['ult']:.3f})"}]
    out += [{"zone": None, "level": "warn", "text": en, "hi": hi} for hi, en in f["notes"]]
    fo = f.get("far_open")
    if fo:
        x = " / ".join(f"{v:.4f}" for v in fo["factors"])
        out.append({"zone": None, "level": "info",
                    "text": f"Far-open balanced by {nm[0]}: x {x} (the town's wards {fo['total']:,.0f} add up to the projection)",
                    "hi": f"Far-open {nm[1]} से balance: x {x} (शहर के वार्ड {fo['total']:,.0f} का जोड़ projection के बराबर)"})
    if fo and fo.get("below"):                  # more particular than "low" (10-Nov-2026)
        x = ", ".join(f"{t} {v:.4f}" for t, v in zip(("init", "mid", "ult"), fo["factors"]) if t in fo["below"])
        out.append({"zone": None, "level": "warn",
                    "text": f"Far-open's factor below 1 ({x}): its wards' population falls - the other characters' "
                            "factors too high for this town's projection; 'Factors to the projection' on the page",
                    "hi": f"Far-open का गुणक 1 से कम ({x}): उसके वार्डों की आबादी घटती दिखती है - बाकी चरित्रों के "
                          "गुणक इस शहर की projection के लिए ज़्यादा; पन्ने पर 'गुणक projection से मिलाएँ'"})
    elif fo and fo.get("low"):
        out.append({"zone": None, "level": "warn",
                    "text": "Far-open grows slower than a denser character - the other characters' factors seem high for this town's growth",
                    "hi": "Far-open किसी घने चरित्र से धीमा बढ़ रहा है - इस शहर की बढ़त के लिए बाकी चरित्रों के गुणक ज़्यादा लगते हैं"})
    if f.get("far_open_error"):
        out.append({"zone": None, "level": "warn", "text": "Far-open not balanced: " + f["far_open_error"],
                    "hi": "Far-open balance नहीं हुआ: " + f["far_open_error"] + " - पन्ने वाले गुणक लगे"})
    sv = f.get("saturation")
    if sv and sv["over"]:                      # only warned (user decision 8-Nov-2026)
        L = ", ".join(f"{w['name']} {w['d0']:,.0f} -> {w['d']:,.0f}" for w in sv["over"])
        out.append({"zone": None, "level": "warn",
                    "text": f"ward(s) above the saturation density {sv['value']:,.0f} per ha in the design year (CPHEEO "
                            f"Water Manual Part A Annexure 2.7 p974): {L} - lower their character's factors, or check the area",
                    "hi": f"Design वर्ष में saturation density {sv['value']:,.0f} प्रति ha से ऊपर के वार्ड (CPHEEO Water "
                          f"Manual Part A Annexure 2.7 p974): {L} - उनके चरित्र के गुणक घटाएँ, या क्षेत्रफल जाँचें"})
    if f.get("core_factor"):
        cf = f["core_factor"]
        out.append({"zone": None, "level": "warn",
                    "text": f"{CORE_CHAR} x {cf:.2f} in the design year: the developed core's density has practically "
                            f"reached saturation unless the FSI is raised - keep its factor close to 1 (CPHEEO Water Manual "
                            f"Part A Annexure 2.7 p974; warned above {CORE_NEAR:.2f})",
                    "hi": f"{CORE_CHAR} x {cf:.2f} (Design वर्ष): विकसित core की density लगभग saturation पर है, जब तक "
                          f"FSI न बढ़े - इसका गुणक 1 के पास रखें (CPHEEO Water Manual Part A Annexure 2.7 p974; "
                          f"{CORE_NEAR:.2f} से ऊपर चेतावनी)"})
    if f.get("from_year"):                     # the wards' table: its population is the one spread
        return out
    if s0 and abs(s0 - f["base_pop"]) > 0.02 * f["base_pop"]:
        out.append({"zone": None, "level": "warn",
                    "text": f"the population on the junctions (wards) {s0:,.0f} is not the base-year population given "
                            f"{f['base_pop']:,.0f} - it is grown by the same ratio",
                    "hi": f"junctions (वार्डों) पर आबादी {s0:,.0f} है, दी गई आधार वर्ष की आबादी {f['base_pop']:,.0f} नहीं - "
                          f"उसी अनुपात से बढ़ाई गई"})
    return out


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


def _keep(stem, kind, res, req):
    folder = os.path.join(ui.out_root(), stem)
    os.makedirs(folder, exist_ok=True)
    keep = dict(res, req={k: req.get(k) for k in ("ohts", "pop_factor", "persons_per_connection", "floating_pct", "oht_inflow", "near_m",
                                                  "pop_total", "edits", "barriers", "loops", "crossings", "wards", "bulk",
                                                  "projection", "ward_table")
                          + ui.STAGE_KEYS},
                time=time.strftime("%d-%m-%Y %H:%M"), net_rev=ui.net_rev(stem))
    with open(os.path.join(folder, f"{stem}_w{kind}_ui.json"), "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, separators=(",", ":"))
    if kind == "zoning":
        try:
            os.remove(os.path.join(folder, f"{stem}_wdesign_ui.json"))
        except OSError:
            pass


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


def last_results(stem):
    """As the sewer server's last_results: network_saved = there is a network to zone; a result of another state of the
    network than the one now is 'stale'."""
    folder, f_mh, _, _ = ui._paths(stem)
    out = {"ok": True, "network_saved": ui.has_network(stem), "network_current": True}
    if not out["network_saved"]:
        return out
    rev = ui.net_rev(stem)
    for kind in ("zoning", "design"):
        f = os.path.join(folder, f"{stem}_w{kind}_ui.json")
        if os.path.isfile(f):
            with open(f, encoding="utf-8") as fh:
                r = json.load(fh)
            if r.get("net_rev") is not None:
                r["stale"] = r["net_rev"] != rev
            else:                                       # kept before net_rev: the saved files' time, as before
                r["stale"] = not os.path.isfile(f_mh) or os.path.getmtime(f) < os.path.getmtime(f_mh)
            out[kind] = r
    return out


def edits_of(req):
    """The pipe / junction tables' changes of the page (user request 19-Oct-2026), only known fields with a value:
    {"pipes": {label: {"size": pipes.json name}}, "junctions": {label: {"gl": m, "pop": persons}}}."""
    raw = (req or {}).get("edits") or {}
    names = {s["name"] for s in wd.load_pipes()}
    out = {"pipes": {}, "junctions": {}}
    for lab, x in (raw.get("pipes") or {}).items():
        if (x or {}).get("size") in names:
            out["pipes"][str(lab)] = {"size": x["size"]}
    for lab, x in (raw.get("junctions") or {}).items():
        y = {}
        for k in ("gl", "pop"):
            try:
                if (x or {}).get(k) not in (None, ""):
                    y[k] = float(x[k])
            except (TypeError, ValueError):
                pass
        if "pop" in y and y["pop"] < 0:
            del y["pop"]
        if y:
            out["junctions"][str(lab)] = y
    return out


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
    z = wz.plan(wnet, ohts, crit, bar=bar, loops=wnet["loops"])
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
            rings = sorted(r.get("rings", []), key=lambda q: -abs(ui._ring_area(q)))
            keep = [q for q in rings if len(q) >= 3]
            big = abs(ui._ring_area(keep[0])) if keep else 0
            keep = [q for q in keep if abs(ui._ring_area(q)) >= 0.01 * big]
            out[g] = {"rings": [[ll(p) for p in q] for q in keep],
                      "label": ll(ui._interior(keep[0])) if keep else None, "area_ha": round(r.get("area", 0.0) / 1e4, 2)}
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


DESIGN_ROUNDS = 1200   # upsizing rounds of a design
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
    try:
        res.setdefault("files", {})["dpr"] = _dpr(zz[0], stem, res, z, crit, req, zz[2], zz[1])
    except Exception as e:                                         # nor without its DPR
        res["log"] += f"\nDPR Excel not written: {type(e).__name__}: {e}"
    # the Intze drawings: no longer with the DPR - one tank at a time by its button (user decision 10-Nov-2026)
    for c in res["checks"]:                                        # their Hindi for the page (30-Oct-2026)
        hindi.check_hi(c)
    _keep(stem, "design", res, req)
    return res


STAGE_YEARS = {"init": 0, "mid": 15, "ult": 30}


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
        if o.get("existing") or not o.get("required_kl"):
            return 0.0
        from . import intze
        return intze.cone_depth(o["required_kl"], swd(o["required_kl"]))
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
                                   o["staging_m"] + swd(o.get("capacity_kl") or o.get("required_kl")) +
                                   _cone(o))
    need = {zn["name"]: int(zn.get("tubewells_new") or 0) + int(zn.get("tubewells_standby") or 0)
            for zn in z["zones"] if zn["name"] in top}          # standby tube wells too: each its own main
    if not placed and not any(need.values()):
        return None
    R = wrising.plan(wnet, z, [o for o in ohts if o["name"] in top], placed, crit, wd.load_pipes(), wdpr_rm.laid_rate(S),
                     top, need, below=_tw_below(S))
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
           "gl": {k: round(v, 2) for k, v in gls.items() if v is not None}}           # each OHT's ground (DPR static head)
    done = [t for t in tws if t.get("size")]
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
            auto[o["name"]] = o["_eff"] = o["staging_m"] = math.ceil(max(static + allow, 10.0) * 2) / 2
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
    r = wd.design(hnet, crit, log=lines.append, max_rounds=DESIGN_ROUNDS)
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
            need = math.ceil((o["_eff"] - (low - rh)) * 2) / 2
            if o["name"] in auto:
                o["staging_m"] = o["_eff"] = need
                staging_note[o["name"]] = {"trial": auto[o["name"]], "required": need}
            else:
                o["_vfd"] = max(0.0, need - o["staging_m"])
                o["_eff"] = o["staging_m"] + o["_vfd"]
            hnet["nodes"][o["name"]]["head"] = hnet["nodes"][o["name"]]["elev"] + o["_eff"]
        res_h = hy.solve(hnet, minor_loss=crit["minor_loss_factor"]["value"], demand_factor=crit["peak_factor"]["value"])
        r["result"] = res_h
        _pressure_summary(hnet, res_h, r, crit)
        for nm, v in staging_note.items():
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


def _dpr(folder, stem, res, z, crit, req, wnet=None, net=None):
    """The DPR workbook in the format of the Elmwood estimate (dpr.py, user decision 26-Oct-2026), next to the design
    report; the Project texts of the previous DPR of the project are kept."""
    info = wdpr.dpr_info(z["zones"], res["pipes"], res["outlets"], z["dmas"], z["closed_pipes"], ui.stage_inputs(req),
                         crit, stem)
    info["bulk"] = res.get("bulk") or []
    info["prvs"] = [p for p in res.get("prvs") or [] if p.get("active")]
    info["rising"] = res.get("rising")
    info["projection"] = res.get("projection")
    info["tech"] = _tech(res, z, req, wnet, net) if wnet else None
    wt = ward_table(req)                           # the wards of the page's table (7-Nov-2026), for the DPR
    if wt:
        drawn = {str(w.get("ward_no") or "").strip() for w in req.get("wards") or []}
        info["ward_table"] = dict(wt, rows=[dict(r, on_map=r["no"] in drawn) for r in wt["rows"]])
        info["town"] = _town_list(req, wt)
    prev = wdpr.previous_dpr(folder, stem)
    path = os.path.join(folder, f"{stem}_water_design_{time.strftime('%Y%m%d_%H%M')}_DPR.xlsx")
    return wdpr.write_dpr(info, path, previous=prev)


def _town_list(req, wt):
    """The town's list of wards chosen on the page (city_wards, user decisions 9-Nov-2026), for DPR T2 Town Wards:
    {city, year, rows: [{no, name, pop, hh, area, census, char}]} - each ward's character the list's, else by the
    density limits of the page on its Eq. area (as the page) - or None."""
    name = str(((req.get("ward_table") or {}).get("citylist")) or "").strip()
    if not name:
        return None
    from . import city_wards as cw
    try:
        d = cw.load(name)
    except (OSError, ValueError):
        return None
    D = sorted(((v, k) for k, v in (wt.get("dens") or WARD_DENS).items() if k in WARD_DENS), reverse=True)

    def char(w):
        c = char_name(w.get("char"))
        if c in WARD_CHARS:
            return c
        p, a = w.get("pop") or 0, w.get("area") or 0
        if p > 0 and a > 0:
            return next((k for v, k in D if p / a > v), FAR_OPEN)
        return ""
    return {"city": d["city"], "year": d.get("year"),
            "rows": [dict({k: w.get(k) for k in ("no", "name", "pop", "hh", "area", "census")}, char=char(w))
                     for w in d.get("rows") or []]}


def _tech(res, z, req, wnet, net):
    """What the technical statement of the Riverside water DPR shows beyond the OZ sums (dpr_tech.py, user decision
    6-Nov-2026): the population of every OZ, DMA and ward in the base / +15 / +30 years (a junction's own stage shares
    where its ward has a character, else the page's), the wards' parts in each OZ, the pipes and residual heads of each
    OZ."""
    given = ui.stage_inputs(req)
    nodes = wnet["nodes"]
    city = sum(v["pop"] for v in nodes.values()) or 1.0
    uni = {t: (given[k] / city if given.get(k) else 1.0) for t, k in (("init", "pop_initial"), ("mid", "pop_mid"))}
    sh = lambda v, t: v["stage"][t] if "stage" in v else uni[t]
    stage = lambda ns: {t: round(sum(nodes[n]["pop"] * (sh(nodes[n], t) if t != "ult" else 1.0) for n in ns))
                        for t in ("init", "mid", "ult")}
    by_oz, by_dma = collections.defaultdict(list), collections.defaultdict(list)
    for n in nodes:
        if z["oz"].get(n):
            by_oz[z["oz"][n]].append(n)
        if z["dma"].get(n):
            by_dma[z["dma"][n]].append(n)
    wn = (net or {}).get("ward_note") or {}
    wards = []
    for i, w in enumerate(wn.get("list") or []):
        ns = [n for n, k in wn["ward_of"].items() if k == i and n in nodes]
        parts = collections.defaultdict(list)
        for n in ns:
            parts[z["oz"].get(n)].append(n)
        wards.append(dict(w, junctions=len(ns), pop=stage(ns),
                          oz={k: stage(v) for k, v in parts.items() if k}))
    # the wards in each DMA (example technical.xlsx 'Tech3' DMA wise demand: ward no. and its contribution, user
    # 9-Nov-2026): the DMA's junctions by their ward, the share of that ward's design-year population; None = no ward
    wof = wn.get("ward_of") or {}
    dma_wards = {}
    for k, ns in by_dma.items():
        parts = collections.defaultdict(list)
        for n in ns:
            parts[wof.get(n)].append(n)
        if any(i is not None for i in parts):
            rows = []
            for i in sorted(parts, key=lambda i: (i is None, i or 0)):
                w = wards[i] if i is not None else None
                p = stage(parts[i])
                rows.append(dict(p, no=(str((w.get("table") or {}).get("no") or w["name"]) if w else None),
                                 share=(round(p["ult"] / w["pop"]["ult"], 4) if w and w["pop"]["ult"] else None)))
            dma_wards[k] = rows
    press = collections.defaultdict(list)
    for x in res["nodes"]:
        if x.get("p") is not None and x.get("oz"):
            press[x["oz"]].append((x["p"], x["label"]))
    ozp = {k: {"min": min(v), "max": max(v)} for k, v in press.items()}
    # a DMA's line size (its equipment, DPR p55): the valve size of its inlet pipe, the first one's the OHT outlet's
    vop = wdpr.settings()["valve_of_pipe"]
    size_of = {p["label"]: p.get("size") for p in res["pipes"]}
    out_size = {o["name"]: o.get("size") for o in res["outlets"]}
    line = lambda d: vop.get(size_of.get(d["inlet_pipe"]) if d.get("inlet_pipe") else out_size.get(d["zone"]))
    return {"oz": {k: stage(v) for k, v in by_oz.items()}, "dma": {k: stage(v) for k, v in by_dma.items()},
            "dmas": [dict({k: d[k] for k in ("name", "zone", "population", "connections")}, line_mm=line(d),
                          wards=dma_wards.get(d["name"]) or []) for d in z["dmas"]],
            "wards": wards, "press": ozp, "stages_given": bool(given.get("pop_initial") or given.get("pop_mid")),
            "own_stages": any("stage" in v for v in nodes.values()),          # wards with a character
            "pipes": [{k: p[k] for k in ("label", "length", "size", "id_mm", "flow", "v", "hl_km", "oz", "dma", "closed")}
                      for p in res["pipes"] if p.get("size")]}


def _excel(folder, stem, res, z, crit):
    """Design report: Summary / Checks, Zones, DMAs, Pipes, Nodes."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Water distribution network design (PFR) - " + stem])
    ws["A1"].font = Font(bold=True, size=13)
    s = res["summary"]
    for k, v in [("population (design)", s["population"]), ("average demand without fire (L/s)", s["demand_avg_lps"]),
                 ("peak factor", s["peak_factor"]), ("lowest residual head (m)", s["min_pressure"]),
                 ("highest residual head (m)", s["max_pressure"]), ("pipes closed at OZ/DMA boundaries", res["closed"])]:
        ws.append([k, v])
    ws.append([])
    ws.append(["length by size (m)"])
    for k, v in s["length_by_size"].items():
        ws.append([k, v])
    ws.append([])
    ws.append(["check", "result", "detail", "CPHEEO / UPJN reference"])
    for c in res["checks"]:
        ws.append([c["check"], "OK" if c["ok"] else ("note" if c.get("note") else "NOT MET"), c["detail"], c["ref"]])
    ws2 = wb.create_sheet("Zones")
    ws2.append(["OZ (OHT)", "OHT", "population", "connections", "demand KLD", "OHT capacity KL (existing)",
                "required KL (max 33 % / mass balance)", "staging m", "staging", "VFD pump head m", "VFD pump kW", "CWR KL", "tube wells",
                "tube wells new (+15 years)", "standby tube wells (CPHEEO 5.7.5)", "rebored tube wells",
                "DMAs", "GL min", "GL max"])
    for x in z["zones"]:
        o = next((o for o in res["outlets"] if o["name"] == x["name"]), {})
        ws2.append([x["name"], "proposed (new)" if o.get("proposed") else "existing" if x["existing"] else "new",
                    x["population"], x["connections"], x["demand_kld"], x["capacity_kl"], x["required_kl"],
                    o.get("staging_m"), "found by the design" if o.get("staging_auto") else "given",
                    o.get("vfd_head_m"), o.get("vfd_kw"), x["cwr_kl"],
                    x["tubewells"], x.get("tubewells_new"), x.get("tubewells_standby"), x.get("rebore"),
                    x.get("dma_count"), x["elev_min"], x["elev_max"]])
    ws3 = wb.create_sheet("DMAs")
    ws3.append(["DMA", "OZ", "population", "connections", "inlet pipe"])
    for d in z["dmas"]:
        ws3.append([d["name"], d["zone"], d["population"], d["connections"], d["inlet_pipe"] or "(at the OHT)"])
    ws4 = wb.create_sheet("Pipes")
    ws4.append(["pipe", "from", "to", "length m", "size", "internal dia mm", "closed", "peak flow L/s", "velocity m/s",
                "head loss m/km", "OZ", "DMA"])
    for p in res["pipes"]:
        ws4.append([p["label"], p["from"], p["to"], p["length"], p["size"], p["id_mm"], "yes" if p["closed"] else "",
                    p["flow"], p["v"], p["hl_km"], p["oz"], p["dma"]])
    ws5 = wb.create_sheet("Nodes")
    ws5.append(["node", "GL m", "HGL m", "residual head m", "peak demand L/s", "OZ", "DMA"])
    for n in res["nodes"]:
        ws5.append([n["label"], n["gl"], n["head"], n["p"], n["q"], n["oz"], n["dma"]])
    if res.get("stages"):
        ws6 = wb.create_sheet("Stages")
        ws6.append(["stage", "year", "population", "average demand L/s", "average demand MLD", "peak flow L/s",
                    "lowest residual head m", "highest residual head m", "junctions below 17 m",
                    "junctions above 21 m", "pipes below 0.3 m/s", "their length m", "pipes above 3 m/s",
                    "OHT", "OHT outlet flow L/s", "lowest head in OZ m", "highest head in OZ m"])
        name = {"init": "base year", "mid": "+15 years (pumps)", "ult": "+30 years (pipes, ESR)"}
        for st in res["stages"]:
            for o in st["oz"]:
                ws6.append([name[st["stage"]], st["year"], st["pop"], st["avg_lps"], st["avg_mld"], st["peak_lps"],
                            st["min_p"], st["max_p"], st["low_n"], st["over_max_n"], st["slow_n"], st["slow_m"],
                            st["fast_n"], o["oht"], o["flow_lps"], o["lowest_p"], o["highest_p"]])
        ws6.append([])
        ws6.append([crit["stages"]["ref"]])
    for w in wb.worksheets:
        for col in w.columns:
            w.column_dimensions[col[0].column_letter].width = 16
    path = os.path.join(folder, f"{stem}_water_design_{time.strftime('%Y%m%d_%H%M')}.xlsx")
    wb.save(path)
    return path
