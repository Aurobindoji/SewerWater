"""WATER MODULE COPY of sewer_app/__main__.py (cmd_layout only) (isolation of sewer and water, user request 21-Oct-2026): changes here do not\nreach the sewer module, nor the reverse. Water rules are written in directly (a water main network keeps its loops\nand has no outfalls)."""
import argparse
import os
import sys
import time

from . import HOME

OUT_ROOT = os.path.join(HOME, "output")
BULK_FOLDER = "Bulk consumers"      # the map page's folder of bulk consumers (user 30-Oct-2026): no level, no STP
PRV_FOLDER = "PRVs"                 # the map page's folder of pressure reducing valves (user 30-Oct-2026): the same
TW_FOLDER = "Tube wells"            # the map page's folder of new tube wells (user 31-Oct-2026): the same


def _bulk_pt(f):
    """A point of the page that is no spot level / STP: a bulk consumer, a PRV or a new tube well."""
    return f.get("folder") in (BULK_FOLDER, PRV_FOLDER, TW_FOLDER) or \
        str((f.get("data") or {}).get("kind") or "") in ("bulk", "prv", "tw")


def cmd_layout(argv):
    import csv
    import math
    import re
    from . import cad, dxf_inspect as di, geo, layout, network
    ap = argparse.ArgumentParser(prog="python -m water_app layout")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--roads-kml", help="KML / KMZ with the road centrelines (LineStrings)")
    src.add_argument("--roads-dxf", help="DXF / DWG with road centrelines")
    ap.add_argument("--road-layers", help="with --roads-dxf: road centreline layers, comma separated")
    ap.add_argument("--boundary-kml", help="KML / KMZ: the largest polygon is the project boundary")
    ap.add_argument("--boundary-all", action="store_true",
                    help="with --boundary-kml: ALL its polygons together are the boundary (e.g. the wards)")
    ap.add_argument("--boundary-layer", help="with --roads-dxf: layer of the boundary (largest closed polyline)")
    ap.add_argument("--population-kml", help="KML / KMZ polygons with a population value (ExtendedData / description)")
    ap.add_argument("--population-field", default="population", help="name of the population value in the KML")
    lv = ap.add_mutually_exclusive_group()
    lv.add_argument("--levels-dxf", help="DXF / DWG with spot levels (texts on --level-layers, or points with Z)")
    lv.add_argument("--levels-kml", help="KML / KMZ points with a ground level: ExtendedData 'GL' / 'level', else a "
                                         "number in the name (e.g. 'GL 80.25'), else a non-zero altitude")
    lv.add_argument("--dem", help="DEM GeoTIFF")
    lv.add_argument("--flat-gl", type=float, help="one assumed ground level for every manhole (rough PFR only)")
    ap.add_argument("--level-layers", default="", help="with --levels-dxf: layers of the level texts")
    ap.add_argument("--epsg", type=int, help="projected system of the drawings (default: UTM zone of the KML)")
    ap.add_argument("--snap", type=float, default=1.0, help="road ends this close are joined (m)")
    ap.add_argument("--spacing", type=float, default=30.0, help="largest manhole spacing along a road (m)")
    ap.add_argument("--min-dangle-m", type=float, default=0.0, help="drop road ends shorter than this (m)")
    ap.add_argument("--node-prefix", default="MH-", help="names of the nodes (water: J-)")
    ap.add_argument("--pipe-prefix", default="CO-", help="names of the pipes (water: P-)")
    ap.add_argument("--no-bend-nodes", action="store_true",
                    help="no node at the bends of a road (water mains follow the road; a sewer needs a manhole there)")
    ap.add_argument("--out", help="output folder")
    a = ap.parse_args(argv)
    t0 = time.time()
    epsg = a.epsg

    def kml_xy(coords):
        nonlocal epsg
        if epsg is None:
            epsg = geo.utm_epsg(coords[0][0], coords[0][1])
        return geo.to_xy(coords, epsg)
    if a.roads_kml:
        k = geo.read_kml(a.roads_kml)
        lines = [kml_xy(f["coords"]) for f in k["lines"] if len(f["coords"]) >= 2]
        stem = os.path.splitext(os.path.basename(a.roads_kml))[0]
    else:
        if not a.road_layers:
            sys.exit("--roads-dxf needs --road-layers")
        doc, _ = di.load(os.path.abspath(a.roads_dxf))
        _, ln_all, _, _, _ = di.inventory(doc.modelspace())
        lays = {x.strip() for x in a.road_layers.split(",")}
        lines = [[p[:2] for p in ln["pts"]] for ln in ln_all if ln["layer"] in lays]
        stem = os.path.splitext(os.path.basename(a.roads_dxf))[0]
        if a.boundary_layer:
            closed = [ln for ln in ln_all if ln["layer"] == a.boundary_layer and len(ln["pts"]) >= 3]
            a.boundary_poly = max(([p[:2] for p in ln["pts"]] for ln in closed),
                                  key=lambda P: abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(P, P[1:] + P[:1]))),
                                  default=None)
    boundary = getattr(a, "boundary_poly", None)
    if a.boundary_kml:
        polys = [kml_xy(f["coords"]) for f in geo.read_kml(a.boundary_kml)["polygons"] if len(f["coords"]) >= 3]
        if a.boundary_all and polys:
            boundary = polys                                        # several polygons (wards) together
        else:
            boundary = max(polys, key=lambda P: abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(P, P[1:] + P[:1]))),
                           default=None)
    multi = bool(boundary) and isinstance(boundary[0][0], (list, tuple))
    print(f"Roads: {len(lines)} lines" + ((f", boundary = {len(boundary)} wards together" if multi
                                            else f", boundary {len(boundary)} points") if boundary else ", no boundary")
          + (f", EPSG {epsg}" if epsg else ""))
    if not lines:
        sys.exit("कोई सड़क नहीं मिली (KML में LineString / Path)")
    nodes, edges = layout.road_graph(lines, snap=a.snap, max_spacing=a.spacing, boundary=boundary,
                                     bend_nodes=not a.no_bend_nodes,
                                     min_dangle_m=a.min_dangle_m)
    if not edges and boundary:
        allb = [p for pg in boundary for p in pg] if multi else boundary
        bx = [p[0] for p in allb]
        by = [p[1] for p in allb]
        cx, cy = (min(bx) + max(bx)) / 2, (min(by) + max(by)) / 2
        d = min(math.dist((cx, cy), p) for ln in lines for p in ln) / 1000.0
        sys.exit(f"Project boundary के भीतर कोई सड़क नहीं - boundary का polygon सड़कों से लगभग {d:.1f} km दूर है। "
                 f"सही polygon को boundary बनाएँ या boundary हटाएँ।")
    if not edges:
        sys.exit("सड़कों से कोई sewer नहीं बना")
    if a.dem:
        gl_fn, gls = layout.gl_from_raster(a.dem, epsg), f"DEM {os.path.basename(a.dem)}"
    elif a.levels_dxf:
        doc, _ = di.load(os.path.abspath(a.levels_dxf))
        _, ln_all, texts, inserts, points = di.inventory(doc.modelspace())
        lays = {x.strip() for x in a.level_layers.split(",") if x.strip()}
        spots = [(t["x"], t["y"], v) for t in texts if (not lays or t["layer"] in lays)
                 for kd, v in di.classify(t["text"]) if kd == "level"]
        spots += [(q["x"], q["y"], q["z"]) for q in list(points) + list(inserts)
                  if (not lays or q["layer"] in lays) and abs(q.get("z") or 0.0) > 0.001]
        if len(spots) < 3:
            sys.exit("fewer than 3 spot levels found - give --level-layers")
        gl_fn, gls = layout.gl_from_spots(spots), f"{len(spots)} spot levels of {os.path.basename(a.levels_dxf)} (TIN)"
    elif a.levels_kml:
        spots = []
        for f in geo.read_kml(a.levels_kml)["points"]:
            if not f["coords"]:
                continue
            if re.search(r"\bOHT\b|\bESR\b|टंकी", f"{f.get('folder') or ''} {f.get('name') or ''}", re.I) or _bulk_pt(f):
                continue                                  # an OHT / bulk consumer of the water module (no level)
            v = next((geo.number(val) for key, val in f["data"].items()
                      if key and key.lower() in ("gl", "level", "ground level", "rl")), None)
            if v is None:
                v = geo.number(f["name"])
            if v is None and len(f["coords"][0]) > 2 and abs(f["coords"][0][2]) > 0.001:
                v = f["coords"][0][2]
            if v is not None:
                x, y = kml_xy(f["coords"])[0]
                spots.append((x, y, v))
        if len(spots) < 3:
            sys.exit(f"{len(spots)} spot level(s) with a value found in {a.levels_kml} - at least 3 are needed")
        gl_fn, gls = layout.gl_from_spots(spots), f"{len(spots)} spot levels of {os.path.basename(a.levels_kml)} (TIN)"
    elif a.flat_gl is not None:
        gl_fn, gls = (lambda x, y: a.flat_gl), f"assumed flat {a.flat_gl:g} m"
    else:
        gl_fn, gls = None, "none"
    net = layout.make_network(nodes, edges, gl_fn, gls, node_prefix=a.node_prefix, pipe_prefix=a.pipe_prefix)
    # named KML points (STP, outfall, pumping station ...) -> the manhole nearest to each, for --outfall / --stp
    marks = []
    for path in {x for x in (a.roads_kml, a.boundary_kml, a.population_kml) if x}:
        for f in geo.read_kml(path)["points"]:
            nm = (f["name"] or "").strip()
            if f["coords"] and re.search(r"stp|outfall|outlet|sps|ips|pump", nm, re.I) and not _bulk_pt(f):
                xy = kml_xy(f["coords"])[0]
                mh = layout.nearest_node(net, xy)
                marks.append((nm, mh, math.dist(net["nodes"][mh]["xy"], xy)))
    folder = a.out or os.path.join(OUT_ROOT, stem)
    os.makedirs(folder, exist_ok=True)
    f_mh, f_co = network.write_csv(net, os.path.join(folder, f"{stem}_layout_manholes.csv"),
                                   os.path.join(folder, f"{stem}_layout_conduits.csv"))
    f_pop = None
    if a.population_kml:
        polys = []
        for f in geo.read_kml(a.population_kml)["polygons"]:
            low = {key.lower(): val for key, val in f["data"].items() if key}
            v = next((geo.number(low[key]) for key in (a.population_field.lower(),) + geo.POP_KEYS
                      if low.get(key) not in (None, "")), None)
            if v is not None and len(f["coords"]) >= 3:
                polys.append((kml_xy(f["coords"]), v))
        pop, rows = layout.population_by_polygons(net, polys)
        f_pop = os.path.join(folder, f"{stem}_layout_population.csv")
        with open(f_pop, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Manhole", "Population"])
            for n_, p_ in pop.items():
                w.writerow([n_, round(p_, 2)])
        for r in rows:
            print(f"   polygon {r['polygon']}: population {r['population']:,.0f} -> {r['manholes inside']} manholes")
    dnodes = {n: {"xy": v["xy"], "gl": v["ground"], "il": None, "outfall": False} for n, v in net["nodes"].items()}
    dconds = [{"label": k["label"], "pts": k["vertices"], "D": None, "slope": None, "length": k["length_m"],
               "start": k["start_node"], "stop": k["stop_node"], "dir": None} for k in net["conduits"]]
    cad.write_dxf(os.path.join(folder, f"{stem}_layout.dxf"), dnodes, dconds, cad.default_text_height(net))
    print(f"Layout (PFR): {len(net['nodes'])} manholes, {len(net['conduits'])} sewers, "
          f"{sum(k['length_m'] for k in net['conduits']):,.0f} m; GL: {gls}")
    for nm, mh, d in marks:
        print(f"   point '{nm}' -> nearest manhole {mh} ({d:.0f} m away) - use it as --outfall / --stp {mh}")
    print(f"\nNetwork: {f_mh}\n         {f_co}" + (f"\nPopulation: {f_pop}  (inputs: \"pop_dist\": \"csv\", "
                                                   f"\"pop_csv\": this file)" if f_pop else "")
          + f"\nPlan   : {os.path.join(folder, stem + '_layout.dxf')}\nNext   : python -m sewer_app zoning --csv "
          f"MANHOLES CONDUITS --inputs ...   ({time.time() - t0:.0f} s)")
