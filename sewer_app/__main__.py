"""sewer_app from the command line.

    python -m sewer_app inspect  DRAWING.dxf [dxf_inspect options]
    python -m sewer_app layout   (--roads-kml ROADS.kml | --roads-dxf DRAWING.dxf --road-layers RD1,RD2)
                                 [--boundary-kml B.kml | --boundary-layer LAYER] [--population-kml P.kml]
                                 [--levels-dxf D.dxf --level-layers L | --levels-kml L.kml | --dem DEM.tif |
                                  --flat-gl 80.0] [--out DIR]
    python -m sewer_app ui       [--port 8765] [--no-browser]    map in the browser: draw roads, boundary, wards,
                                 spot levels, STP -> KML (projects\\<name>.kml) -> layout
    python -m sewer_app check    (--dxf DRAWING.dxf --pipe-layers L1,L2 | --csv MANHOLES.csv CONDUITS.csv)
                                 [--outfall O-1 ...] [--join-gap-m 1.0] [--tjoint-m 0.5] [--out DIR]
    python -m sewer_app extract  DRAWING.dxf --pipe-layers PIPE0,PIPE1 [dxf_extract options]
    python -m sewer_app zoning   (--dxf DRAWING.dxf --pipe-layers L1,L2 | --csv MANHOLES.csv CONDUITS.csv)
                                 --inputs INPUTS.json [--outfall O-1 ...] [--stp LABEL] [--max-zones 8] [--out DIR]
    python -m sewer_app design   (--dxf DRAWING.dxf --pipe-layers L1,L2 | --csv MANHOLES.csv CONDUITS.csv)
                                 --inputs INPUTS.json --outfall O-1 [--outfall O-2 ...] [--fixed O-1=142.03]
                                 [--source-dxf DRAWING.dxf] [--data-grade PFR] [--out DIR]

INPUTS.json = the answers file of the original scripts sewer_design.py --ask (inputs\\<model>_sewer_inputs.json): catalog,
joint, pop_total, pop_dist, sewage_lpcd, infil_basis, infil_rate, peak, pop_initial, start_depth, fixed, trunk;
optional data_grade ("DPR" / "PFR"). --fixed adds / overrides fixed outfall levels.

design writes into --out (default sewer_app\\output\\<stem>\\):
    <stem>_sewer_design_<time>[_PFR].xlsx    design report (Summary, Cost, Design, Manholes, ..., Check)
    <stem>_sewer_design_<time>[_PFR].dxf     plan drawing (pipes, manholes incl. the new 30 m ones, texts)
    <stem>_sewer_design_<time>[_PFR]_Lsection.dxf   L-section of the main trunk to every outfall
    <stem>_sewer_design_<time>[_PFR]_new_manholes.csv
zoning writes <stem>_zoning_<time>.xlsx, _costs.xlsx, maps (PNG) and DXFs.
layout (PFR) writes the sewer network along the roads as <stem>_layout_manholes.csv / _conduits.csv (+ _population.csv
with --population-kml) and a plan DXF; then: zoning / design --csv ... (the run is a PFR).
check writes <stem>_check_<time>.xlsx (issues, repairs, parts), _markers.dxf (one layer per kind of problem - XREF it
on the drawing) and the repaired network as <stem>_repaired_manholes.csv / _conduits.csv (use with --csv).
--repair (zoning, design): the automatic repairs of check (joins short gaps, splits T-joints, cuts loops, fills
missing GL along the sewer) are made before the run.
A DWG is read through the ODA File Converter when it is installed; otherwise give the DXF.
"""
import argparse
import json
import os
import sys
import time

from . import HOME, DesignError

OUT_ROOT = os.path.join(HOME, "output")


def load_network(a, log):
    """(network, stem, source text, extract result or None) from --dxf (extracted now) or --csv; with --repair the
    automatic repairs are made."""
    net, stem, src, ex = _read_network(a, log)
    if getattr(a, "repair", False):
        from . import repair
        net, rlog = repair.repair(net, ex, a.outfall, join_gap_m=a.join_gap_m, tjoint_m=a.tjoint_m)
        import collections
        log("Repairs: " + (", ".join(f"{k} {v}" for k, v in collections.Counter(r["repair"] for r in rlog).most_common())
                           or "none needed"))
    return net, stem, src, ex


def _read_network(a, log):
    from . import dxf_extract, network
    if a.dxf:
        path = os.path.abspath(a.dxf.strip('"'))
        if not a.pipe_layers:
            sys.exit("--dxf needs --pipe-layers (see: python -m sewer_app inspect DRAWING.dxf)")
        log(f"Reading {path} ...")
        ex = dxf_extract.extract(path, a.pipe_layers.split(","), (a.mh_layers or "").split(","),
                                 (a.level_layers or "").split(","), a.tol, a.level_radius)
        for ln in ex["summary"]:
            log("   " + ln)
        stem = os.path.splitext(os.path.basename(path))[0]
        return network.from_extract(ex, a.outfall), stem, path, ex
    mh, co = (os.path.abspath(p) for p in a.csv)
    for p in (mh, co):
        if not os.path.isfile(p):
            sys.exit(f"CSV not found: {p}")
    stem = os.path.splitext(os.path.basename(mh))[0].replace("_manholes", "")
    return network.read_extract_csv(mh, co, a.outfall), stem, f"{mh} + {co}", None


def load_inputs(a):
    with open(a.inputs, encoding="utf-8") as fh:
        inp = json.load(fh)
    fixed = dict(inp.get("fixed") or {})
    for f in a.fixed or []:
        lab, _, v = f.partition("=")
        fixed[lab.strip()] = float(v)
    inp["fixed"] = fixed
    if a.data_grade:
        inp["data_grade"] = a.data_grade
    return inp


def network_args(ap, inputs=True):
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dxf", help="drawing (DXF, or DWG with the ODA File Converter)")
    src.add_argument("--csv", nargs=2, metavar=("MANHOLES_CSV", "CONDUITS_CSV"), help="dxf_extract CSV files")
    ap.add_argument("--pipe-layers", help="with --dxf: pipe layers, comma separated")
    ap.add_argument("--mh-layers", default="", help="with --dxf: manhole symbol / label layers")
    ap.add_argument("--level-layers", default="", help="with --dxf: GL text layers (default: best match)")
    ap.add_argument("--tol", type=float, default=0.5)
    ap.add_argument("--level-radius", type=float, default=10.0)
    if inputs:
        ap.add_argument("--inputs", required=True, help="answers file (JSON)")
        ap.add_argument("--repair", action="store_true", help="make the automatic network repairs first (see check)")
    ap.add_argument("--join-gap-m", type=float, default=1.0, help="repair: join line ends at most this far apart (m)")
    ap.add_argument("--tjoint-m", type=float, default=0.5, help="repair: a line end this close to another line splits it")
    ap.add_argument("--outfall", action="append", default=[], help="outfall manhole label (repeatable)")
    ap.add_argument("--out", help="output folder")


def cmd_design(argv):
    from . import cad, dpr, lsection, pipeline, report
    ap = argparse.ArgumentParser(prog="python -m sewer_app design")
    network_args(ap)
    ap.add_argument("--fixed", action="append", help="fixed outfall level, e.g. O-1=142.03 (repeatable)")
    ap.add_argument("--data-grade", choices=("DPR", "PFR"))
    ap.add_argument("--source-dxf", help="original drawing: text height of the plan = its MH labels x 0.67")
    ap.add_argument("--text-height", type=float, help="text height of the plan drawing (m)")
    ap.add_argument("--zoning-option", help="design the network with this zoning option applied (CURRENT, T4 ...): "
                                            "its zone outlets become the outfalls, its cut conduits are disconnected")
    ap.add_argument("--stp", help="with --zoning-option: node where the STP is")
    ap.add_argument("--max-zones", type=int, default=8)
    ap.add_argument("--min-zone-m", type=float)
    ap.add_argument("--spike-gl", choices=("keep", "neighbour"), default="keep")
    a = ap.parse_args(argv)
    if not a.outfall and not a.zoning_option:
        sys.exit("give the outfall(s): --outfall LABEL, or a zoning option: --zoning-option NAME")
    t0 = time.time()
    inp = load_inputs(a)
    net, stem, src, _ = load_network(a, print)
    applied = []
    if a.zoning_option:
        from . import zoning
        print(f"Zoning (to apply option {a.zoning_option}) ...")
        z = zoning.run(net, inp, stp=a.stp, max_zones=a.max_zones, min_zone_m=a.min_zone_m, spike_gl=a.spike_gl,
                       log=lambda s: None)
        ev = next((e for e in z["rank"] if e["m"]["option"] == a.zoning_option), None)
        if ev is None:
            sys.exit(f"zoning option '{a.zoning_option}' not found - options: "
                     + ", ".join(e["m"]["option"] for e in z["rank"]))
        net, applied = zoning.apply_option(net, ev)
        m = ev["m"]
        print(f"   option {m['option']} (rank {m['rank']}): {m['zones']} zones, outlets {m['outlets']}; "
              f"{len(applied)} conduit(s) disconnected at one end")
        stem += f"_{a.zoning_option}"
    try:
        out = pipeline.run(net, inp)
    except DesignError as e:
        sys.exit(f"\n*** {e}")
    if applied:
        out["log"].insert(0, f"zoning option {a.zoning_option} applied: outfalls {', '.join(net['outfalls'])}; "
                             f"{len(applied)} cut conduit(s) disconnected at one end (new head manholes <MH>-C<n>): "
                             + "; ".join(f"{r['conduit']} from {r['disconnected from']}" for r in applied[:40])
                             + (" ..." if len(applied) > 40 else ""))
    folder = a.out or os.path.join(OUT_ROOT, stem)
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, f"{stem}_sewer_design_{time.strftime('%Y%m%d_%H%M')}"
                                + ("_PFR" if out["grade"] != "DPR" else ""))
    xl = report.write_report(out, base + ".xlsx", source=src)
    xl_dpr = dpr.write_dpr(out, base + "_DPR.xlsx", title=f"{stem.replace('_', ' ').upper()} SEWERAGE SCHEME", inp=inp)
    if a.text_height:
        h = a.text_height
    elif a.source_dxf or a.dxf:
        h = cad.source_text_height(os.path.abspath(a.source_dxf or a.dxf))[0] * 0.67
    else:
        h = None
    cnt = cad.design_drawing(out, base + ".dxf", text_height=h)
    ls = lsection.draw(out, base + "_Lsection.dxf")
    res = out["res"]
    print(f"\nDesigned {len(res)} conduits, {sum(d['length'] or 0 for d in res.values()):,.0f} m; "
          f"{len(out['new_mh'])} new manholes for spacing; data grade {out['grade']}")
    for ln in out["plan_lines"]:
        print("   " + ln)
    for w in out["warnings"]:
        print("WARNING: " + w)
    print(f"\nExcel: {xl}\nDPR  : {xl_dpr}\nDXF  : {base}.dxf  ({cnt['nodes']} manholes, {cnt['conduits']} pipes, text height "
          f"{cnt['text_height']:.2f} m)\nL-sec: {base}_Lsection.dxf  (main trunk to {ls['outfalls']} outfall(s), "
          f"{ls['sheets']} sheet(s), H 1:1000 V 1:100)\n({time.time() - t0:.0f} s)")


def cmd_zoning(argv):
    from . import zoning
    ap = argparse.ArgumentParser(prog="python -m sewer_app zoning")
    network_args(ap)
    ap.add_argument("--stp", help="node where the STP is (fixed outlet, no pumping station)")
    ap.add_argument("--max-zones", type=int, default=8)
    ap.add_argument("--min-zone-m", type=float)
    ap.add_argument("--spike-gl", choices=("keep", "neighbour"), default="keep")
    ap.add_argument("--network-dxf", choices=("all", "best", "none"), default="all")
    ap.add_argument("--ref-gl", help="GL band map: reference GL in m (80.0) or a manhole label whose GL it is "
                                     "(default: inputs 'gl_ref', else the lowest GL)")
    ap.add_argument("--gl-bands", help="GL band map: ranges in m above the reference, e.g. \"0-1.5, 1.5-3, 3-4.5, 4.5+\" "
                                       "(default: inputs 'gl_bands', else that)")
    ap.add_argument("--band-max-edge", type=float, help="GL band map: no colour where manholes are more than this "
                                                        "apart (m; default max(150, 5 x median conduit length))")
    ap.add_argument("--no-band-map", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    with open(a.inputs, encoding="utf-8") as fh:
        inp = json.load(fh)
    net, stem, src, _ = load_network(argparse.Namespace(**dict(vars(a), outfall=[])), print)
    net["outfalls"] = list(a.outfall)               # zoning: the given outfalls are only option 'CURRENT'
    z = zoning.run(net, inp, stp=a.stp, max_zones=a.max_zones, min_zone_m=a.min_zone_m, spike_gl=a.spike_gl,
                   band_max_edge=a.band_max_edge)
    folder = a.out or os.path.join(OUT_ROOT, stem)
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, f"{stem}_zoning_{time.strftime('%Y%m%d_%H%M')}")
    ref = a.ref_gl if a.ref_gl is not None else inp.get("gl_ref")
    if ref is not None and not (isinstance(ref, str) and ref in z["gl"]):
        try:
            ref = float(ref)
        except ValueError:
            sys.exit(f"--ref-gl: '{ref}' is neither a level (m) nor a manhole label of this network")
    try:
        f = zoning.write_outputs(z, base, source=src, network_dxf=a.network_dxf,
                                 source_dxf=os.path.abspath(a.dxf) if a.dxf else None, band_map_on=not a.no_band_map,
                                 gl_ref=ref, gl_bands=a.gl_bands or inp.get("gl_bands"))
    except ValueError as e:
        sys.exit(f"--gl-bands: {e}")
    print("\n================ ZONING OPTIONS (ranked: pumping stations, depth, pipe cost) ================")
    for ev in z["rank"]:
        m = ev["m"]
        print(f"{m['rank']:>2}. {m['option']:<8} zones {m['zones']:>3} | pumping stations {m['pumping stations']:>3} "
              f"({m['of these added for depth']} added for depth) | max depth {m['max depth (m)']} m | pipe Rs "
              f"{m['pipe cost (Rs lakh)']:,.2f} lakh")
    print(f"\nExcel: {f['xlsx']}\nCosts: {f['costs']}\nDXF  : {f['boundary_dxf']} + {len(f['network_dxf'])} network "
          f"drawing(s)\nMaps : {len(f['option_png']) + len(f['boundary_png']) + 1} PNG"
          + (f"\nGL band map: {f['band_png']}\n   {f['band_text']}" if f.get("band_png") else "")
          + f"\n({time.time() - t0:.0f} s)")


def cmd_layout(argv):
    import csv
    import math
    import re
    from . import cad, dxf_inspect as di, geo, layout, network
    ap = argparse.ArgumentParser(prog="python -m sewer_app layout")
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
            if re.search(r"\bOHT\b|\bESR\b|टंकी", f"{f.get('folder') or ''} {f.get('name') or ''}", re.I):
                continue                                  # an OHT of the water module (its name is no level)
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
            if f["coords"] and re.search(r"stp|outfall|outlet|sps|ips|pump", nm, re.I):
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


def cmd_check(argv):
    import collections
    from . import cad, network, repair
    ap = argparse.ArgumentParser(prog="python -m sewer_app check")
    network_args(ap, inputs=False)
    a = ap.parse_args(argv)
    t0 = time.time()
    net, stem, src, ex = load_network(argparse.Namespace(**dict(vars(a), repair=False)), print)
    issues = repair.check(net, ex, a.outfall)
    fixed, log = repair.repair(net, ex, a.outfall, join_gap_m=a.join_gap_m, tjoint_m=a.tjoint_m)
    parts = repair.parts_report(fixed, a.outfall)
    folder = a.out or os.path.join(OUT_ROOT, stem)
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, f"{stem}_check_{time.strftime('%Y%m%d_%H%M')}")
    h = cad.default_text_height(net)
    repair.write_check(issues, log, base + ".xlsx", base + "_markers.dxf", parts=parts, text_h=h)
    f_mh, f_co = network.write_csv(fixed, os.path.join(folder, f"{stem}_repaired_manholes.csv"),
                                   os.path.join(folder, f"{stem}_repaired_conduits.csv"))
    print("\nProblems (nothing changed in the drawing):")
    for k, v in collections.Counter(i["type"] for i in issues).most_common():
        print(f"   {v:6}  {k}")
    print("Automatic repairs (in the repaired CSV):")
    for k, v in collections.Counter(r["repair"] for r in log).most_common():
        print(f"   {v:6}  {k}")
    for p_ in parts:
        print(f"   part {p_['part']}: {p_['manholes']} MH, {p_['sewer length (m)']:,.0f} m, outfalls {p_['outfalls']}, "
              f"lowest {p_['lowest manhole']} (GL {p_['its GL']})"
              + (f"; nearest: {p_['nearest other parts']}" if p_["nearest other parts"] else ""))
    print(f"\nExcel  : {base}.xlsx\nMarkers: {base}_markers.dxf  (XREF / INSERT on the drawing - same coordinates)\n"
          f"Repaired network: {f_mh}\n                  {f_co}   (use with --csv)\n({time.time() - t0:.0f} s)")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "inspect":
        from . import dxf_inspect
        sys.argv = ["dxf_inspect"] + rest
        dxf_inspect.main()
    elif cmd == "extract":
        from . import dxf_extract
        sys.argv = ["dxf_extract"] + rest
        dxf_extract.main()
    elif cmd == "layout":
        cmd_layout(rest)
    elif cmd == "check":
        cmd_check(rest)
    elif cmd == "design":
        cmd_design(rest)
    elif cmd == "zoning":
        cmd_zoning(rest)
    elif cmd == "ui":
        from . import ui
        ui.main(rest)
    else:
        sys.exit(f"unknown command '{cmd}' - inspect, extract, layout, check, zoning, design or ui")


if __name__ == "__main__":
    main()
