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

from sewer_app import HOME, DesignError
from sewer_app.run.layout_cmd import cmd_layout

OUT_ROOT = os.path.join(HOME, "output")


def load_network(a, log):
    """(network, stem, source text, extract result or None) from --dxf (extracted now) or --csv; with --repair the
    automatic repairs are made."""
    net, stem, src, ex = _read_network(a, log)
    if getattr(a, "repair", False):
        from sewer_app.net import repair
        net, rlog = repair.repair(net, ex, a.outfall, join_gap_m=a.join_gap_m, tjoint_m=a.tjoint_m)
        import collections
        log("Repairs: " + (", ".join(f"{k} {v}" for k, v in collections.Counter(r["repair"] for r in rlog).most_common())
                           or "none needed"))
    return net, stem, src, ex


def _read_network(a, log):
    from sewer_app.net import dxf_extract
    from sewer_app.core import network
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
    from sewer_app.out import cad, lsection, report
    from sewer_app.out.dpr import workbook as dpr
    from sewer_app.engine import pipeline
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
        from sewer_app.engine import zoning
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
    from sewer_app.engine import zoning
    from sewer_app.out import zoning_out
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
        f = zoning_out.write_outputs(z, base, source=src, network_dxf=a.network_dxf,
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


def cmd_check(argv):
    import collections
    from sewer_app.out import cad
    from sewer_app.core import network
    from sewer_app.net import repair
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
        from sewer_app.net import dxf_inspect
        sys.argv = ["dxf_inspect"] + rest
        dxf_inspect.main()
    elif cmd == "extract":
        from sewer_app.net import dxf_extract
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
        from sewer_app.web import server as ui
        ui.main(rest)
    else:
        sys.exit(f"unknown command '{cmd}' - inspect, extract, layout, check, zoning, design or ui")


if __name__ == "__main__":
    main()
