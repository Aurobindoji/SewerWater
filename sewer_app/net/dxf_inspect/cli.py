"""dxf_inspect: the drawing check from the command line (python -m sewer_app.net.dxf_inspect): console + Excel report."""
import os
import time
import argparse
import collections
from .kinds import INVERT_TAG, NOT_PIPE_NAME, OUTFALL_WORD, OUT_DIR, PIPE_NAME, UNITS
from .layers import inventory
from .levels import level_candidates, node_levels, text_summary
from .matching import labels_near_nodes, match_points, pipe_annotations
from .network import build_network, network_checks
from .reading import load
from .spatial import Grid


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Read-only DXF check for building a sewer model.")
    ap.add_argument("dxf")
    ap.add_argument("--pipe-layers", default="", help="comma separated; default: guessed from layer names")
    ap.add_argument("--mh-layers", default="", help="comma separated manhole symbol layers; default: best match")
    ap.add_argument("--level-layers", default="", help="comma separated ground-level text layers; default: guessed")
    ap.add_argument("--tol", type=float, default=0.5, help="snap tolerance for joining line ends (m), default 0.5")
    ap.add_argument("--level-radius", type=float, default=10.0, help="max distance node -> level text (m), default 10")
    a = ap.parse_args()
    path = os.path.abspath(a.dxf.strip('"'))
    t0 = time.time()
    doc, auditor = load(path)
    msp = doc.modelspace()
    hdr = doc.header
    ins = hdr.get("$INSUNITS", 0)
    layers, lines, texts, inserts, points = inventory(msp)
    print(f"File: {path}\nDXF {doc.dxfversion}, units {UNITS.get(ins, ins)}, entities read in {time.time() - t0:.1f} s; "
          f"audit: {len(auditor.errors)} error(s), {len(auditor.fixes)} fix(es)")
    allx = [p[0] for ln in lines for p in ln["pts"]] + [t["x"] for t in texts]
    ally = [p[1] for ln in lines for p in ln["pts"]] + [t["y"] for t in texts]
    if allx:
        w, h = max(allx) - min(allx), max(ally) - min(ally)
        big = max(abs(min(allx)), abs(max(allx)), abs(min(ally)), abs(max(ally)))
        print(f"Extent of data: {w:,.0f} x {h:,.0f} (drawing units); coordinates up to {big:,.0f} -> "
              + ("looks like projected metres (e.g. UTM)" if big > 100000 else "local / unknown coordinates"))

    # ---- layers
    lrows = []
    for lay, L in sorted(layers.items()):
        lrows.append({"layer": lay, "types": ", ".join(f"{k}:{v}" for k, v in L["types"].most_common()),
                      "entities": sum(L["types"].values()), "line_length": round(L["length"], 1),
                      "z_values": len(L["z"]), "z_range": (f"{min(L['z']):g} - {max(L['z']):g}" if L["z"] else ""),
                      "colour": L["color"].most_common(1)[0][0] if L["color"] else ""})
    print(f"\nLAYERS: {len(lrows)}")
    for r in sorted(lrows, key=lambda r: -r["line_length"])[:40]:
        print(f"   {r['layer'][:28]:<28} {r['entities']:>7}  length {r['line_length']:>11,.1f}  {r['types'][:70]}")

    # ---- texts
    trows = text_summary(texts)
    lvl_given = [s.strip() for s in a.level_layers.split(",") if s.strip()]
    lvl_cands = level_candidates(texts)
    print(f"\nTEXTS: {len(texts)} (incl. block attributes) on {len(trows)} layer(s)")
    for r in sorted(trows, key=lambda r: -r["numeric"])[:15]:
        print(f"   {r['layer'][:24]:<24} {r['n']:>6} texts; kinds {r['kinds'][:60] or '-'}; e.g. "
              f"{r['samples'][:60].replace(chr(10), ' ')}")
    print(f"   layers with level-like values (narrow band, > 10): "
          f"{', '.join(f'{k} ({len(v)})' for k, v in lvl_cands.items()) or 'none'}")

    # ---- blocks
    brows = collections.defaultdict(lambda: {"n": 0, "tags": collections.Counter(), "sample": ""})
    for b in inserts:
        k = (b["name"], b["layer"])
        brows[k]["n"] += 1
        for tg, v in b["attrs"].items():
            brows[k]["tags"][tg] += 1
            if not brows[k]["sample"]:
                brows[k]["sample"] = f"{tg}={v}"
    print(f"\nBLOCK REFERENCES: {len(inserts)}")
    for (nm, lay), v in sorted(brows.items(), key=lambda kv: -kv[1]["n"])[:20]:
        print(f"   {nm[:26]:<26} on {lay[:22]:<22} x{v['n']:<6} attributes: {', '.join(v['tags']) or '-'}")

    # ---- pipe layers
    linear = [r["layer"] for r in lrows if r["line_length"] > 0]
    pipe_layers = [s.strip() for s in a.pipe_layers.split(",") if s.strip()]
    guessed = not pipe_layers
    if not pipe_layers:
        pipe_layers = [l for l in linear if PIPE_NAME.search(l) and not NOT_PIPE_NAME.search(l)]
    pl = [ln for ln in lines if ln["layer"] in pipe_layers]
    print(f"\nPIPE LAYERS {'(guessed from names - check!)' if guessed else '(given)'}: {', '.join(pipe_layers) or 'NONE'}")
    net_rows = []
    per_layer = {}
    for lay in pipe_layers:
        ls = [ln for ln in lines if ln["layer"] == lay]
        nd, ed, _ = build_network(ls, a.tol)
        chk = network_checks(nd, ed, a.tol)
        per_layer[lay] = chk
        net_rows.append({"set": lay, **{k: (len(v) if isinstance(v, list) else v) for k, v in chk.items()
                                         if k not in ("part_sizes",)}, "part_sizes": str(chk["part_sizes"])})
    nodes, edges, _ = build_network(pl, a.tol)
    chk = network_checks(nodes, edges, a.tol) if edges else None
    if chk:
        net_rows.append({"set": "ALL PIPE LAYERS TOGETHER",
                         **{k: (len(v) if isinstance(v, list) else v) for k, v in chk.items() if k != "part_sizes"},
                         "part_sizes": str(chk["part_sizes"])})
        for lay, c in list(per_layer.items()) + [("ALL", chk)]:
            print(f"   {lay[:22]:<22} length {c['length']:>10,.1f} m, {c['edges']:>5} lines, {c['nodes']:>5} nodes, "
                  f"{c['parts']:>3} part(s), {c['loops']:>3} loop(s), {c['dead_ends']:>4} dead ends, "
                  f"{len(c['gaps']):>3} near-miss gaps, {len(c['tjoints']):>3} T-joints w/o node, "
                  f"crossings {c['crossings'] if c['crossings'] is not None else 'not checked'}, "
                  f"{len(c['long'])} lines > 30 m")

    # ---- manhole symbols
    cands, cand_layer = collections.defaultdict(list), {}
    for b in inserts:
        for k in (f"{b['layer']} / block {b['name']}", f"{b['layer']} (all blocks)"):
            cands[k].append(b)
            cand_layer[k] = b["layer"]
    for p in points:
        k = f"{p['layer']} / {p['kind']}"
        cands[k].append(p)
        cand_layer[k] = p["layer"]
    mh_given = [s.strip() for s in a.mh_layers.split(",") if s.strip()]
    mrows = []
    if edges:
        for k, pts in cands.items():
            lay = cand_layer[k]
            if mh_given and lay not in mh_given:
                continue
            hit, tot = match_points(nodes, pts, a.tol)
            if hit:
                mrows.append({"candidate": k, "layer": lay, "symbols": len(pts), "nodes_with_symbol": hit, "nodes": tot,
                              "share": round(hit / tot, 3) if tot else 0})
        mrows.sort(key=lambda r: -r["share"])
    print("\nMANHOLE SYMBOLS at network nodes:")
    for r in mrows[:8]:
        print(f"   {r['candidate'][:50]:<50} {r['nodes_with_symbol']:>5} of {r['nodes']} nodes ({r['share']:.0%}), "
              f"{r['symbols']} symbols in all")
    if not mrows:
        print("   none - no point / block / circle lies on the line ends (manholes would be created at line ends)")

    # ---- levels: the given layer(s), else the candidate layer that covers most nodes
    cover = []
    if edges:
        used_nodes = [n for n in nodes if n["deg"] > 0]
        for lay, vals in lvl_cands.items():
            g = Grid(max(a.level_radius, 1.0))
            for x, y, v in vals:
                g.add(x, y, v)
            hit = sum(1 for n in used_nodes if g.near(n["x"], n["y"], a.level_radius))
            cover.append((hit, lay))
        cover.sort(reverse=True)
    lvl_layers = lvl_given or ([cover[0][1]] if cover and cover[0][0] else [])
    print("\nLEVEL TEXT LAYERS by node coverage (within %g m): " % a.level_radius
          + (", ".join(f"{lay} {hit}" for hit, lay in cover) or "none") + f" -> using: {', '.join(lvl_layers) or 'none'}")
    lres, per_node, z_useful = (node_levels(nodes, texts, inserts, lvl_layers, a.level_radius)
                                if edges else ({"z": 0, "attr": 0, "text": 0, "none": 0}, {}, False))
    nn = sum(lres.values())
    mh_lay = set(mh_given) or ({mrows[0]["layer"]} if mrows else set())
    mh_labels = labels_near_nodes(nodes, texts, a.level_radius, mh_lay) if edges else {}
    if edges and mh_lay and not any(mh_labels.values()):
        mh_labels = labels_near_nodes(nodes, texts, a.level_radius)      # no IDs on the symbol layer
    n_lab = sum(1 for v in mh_labels.values() if v)
    dup = [k for k, c in collections.Counter(v for v in mh_labels.values() if v).items() if c > 1]
    print(f"MANHOLE LABELS (ID text within {a.level_radius:g} m): {n_lab} of {len(mh_labels)} nodes"
          + (f"; {len(dup)} label(s) used by more than one node, e.g. {', '.join(dup[:5])}" if dup else ""))
    ann = pipe_annotations(edges, texts, set(pipe_layers), 20.0) if edges else {}
    cnt = collections.Counter(k for v in ann.values() for k in v)
    ratios = sorted(e["len"] / v["length"] for e in edges for v in [ann.get(e["id"], {})]
                    if v.get("length") and v["length"] > 1 and e["len"] > 1)
    unit_ok = None
    if ratios:
        med = ratios[len(ratios) // 2]
        unit_ok = abs(med - 1.0) < 0.02
        print(f"PIPE TEXTS: label {cnt['id']}, diameter {cnt['dia']}, slope {cnt['slope_1in']}, length {cnt['length']} "
              f"of {len(edges)} lines; drawn / written length median {med:.3f} -> "
              + ("drawing units = METRES (confirmed)" if unit_ok else "units differ - check"))
    else:
        print(f"PIPE TEXTS: label {cnt['id']}, diameter {cnt['dia']}, slope {cnt['slope_1in']}, length {cnt['length']} "
              f"of {len(edges)} lines")
    print(f"\nGROUND LEVEL at network nodes ({nn} nodes): from Z {lres['z']}, from block attributes {lres['attr']}, "
          f"from text within {a.level_radius:g} m {lres['text']}, none {lres['none']}")
    vals = [v for s, v in per_node.values() if v is not None]
    if vals:
        print(f"   levels found: {min(vals):.3f} - {max(vals):.3f}")

    # ---- outfall
    orows = []
    used = [n for n in nodes if n["deg"] == 1]
    og = Grid(50.0)
    for n in used:
        og.add(n["x"], n["y"], n["id"])
    for t in texts:
        if OUTFALL_WORD.search(t["text"] or ""):
            h = og.near(t["x"], t["y"], 300.0)
            orows.append({"text": t["text"][:60], "layer": t["layer"], "x": round(t["x"], 2), "y": round(t["y"], 2),
                          "nearest_dead_end_m": round(h[0][0], 1) if h else None})
    print(f"\nOUTFALL hints (STP / outfall / SPS / IPS / existing sewer texts): {len(orows)}")
    for r in orows[:10]:
        print(f"   '{r['text']}' on {r['layer']} - nearest dead end of the pipes {r['nearest_dead_end_m']} m")

    # ---- checklist
    chkl = []

    def item(need, status, found, todo):
        chkl.append({"required": need, "status": status, "found": found, "to do": todo})
    if not pipe_layers or not edges:
        item("Network lines (sewer alignment)", "MISSING", "no pipe layer recognised",
             "give the layer(s) with --pipe-layers (see LAYERS above)")
    else:
        item("Network lines (sewer alignment)", "FOUND" if not guessed else "CHECK",
             f"{', '.join(pipe_layers)}: {chk['length']:,.0f} m, {chk['edges']} lines",
             "confirm these are the PROPOSED sewer lines (PIPE0/1/2 may be existing / proposed / water)" if guessed else "")
        ok = chk["parts"] == 1 and not chk["gaps"] and not chk["tjoints"]
        item("Connected network (one tree per outfall)", "FOUND" if ok and not chk["loops"] else "PARTIAL",
             f"{chk['parts']} part(s) {chk['part_sizes']}, {len(chk['gaps'])} near-miss gaps, "
             f"{len(chk['tjoints'])} T-joints without node, {chk['loops']} loop(s), crossings {chk['crossings']}",
             "join the gaps / break lines at T-joints in CAD, or use a larger --tol; a sewer must have no loops "
             "(each loop needs one line removed or split)" if not ok or chk["loops"] else "")
        best = mrows[0] if mrows else None
        item("Manhole positions", "FOUND" if best and best["share"] >= 0.9 else ("PARTIAL" if best else "MISSING"),
             f"best match {best['candidate']}: {best['share']:.0%} of nodes" if best else "no symbols on the nodes",
             "manholes can be created at every line end / junction (ModelBuilder 'create nodes'); "
             f"{len(chk['long'])} line(s) are longer than 30 m - the design adds manholes there")
        st = "FOUND" if lres["none"] == 0 else ("PARTIAL" if lres["none"] < nn else "MISSING")
        item("Ground level at every manhole", st,
             f"Z {lres['z']}, attributes {lres['attr']}, texts {lres['text']}, none {lres['none']} of {nn}",
             "" if st == "FOUND" else "give the level text layer (--level-layers), or a survey CSV (MH, GL), "
             "or a DEM / TIN for SewerGEMS TRex")
    if edges:
        item("Manhole labels (MH-...)", "FOUND" if n_lab >= 0.95 * len(mh_labels) else ("PARTIAL" if n_lab else "NOT GIVEN"),
             f"{n_lab} of {len(mh_labels)} nodes" + (f", {len(dup)} duplicate label(s)" if dup else ""),
             "" if n_lab else "names will be generated (MH-1, MH-2 ...)")
        item("Existing pipe data (diameter / slope) - for checking an existing design",
             "FOUND" if cnt["dia"] >= 0.95 * len(edges) else ("PARTIAL" if cnt["dia"] else "NOT GIVEN"),
             f"diameter {cnt['dia']}, slope {cnt['slope_1in']}, length {cnt['length']} of {len(edges)} lines",
             "inverts are not in the drawing: slopes alone fix inverts only relative to one known invert per line")
    item("Outfall location", "FOUND" if orows else "MISSING",
         f"{len(orows)} text hint(s)" if orows else "no STP / outfall text",
         "tell which dead end is the outfall (MH label or X, Y)")
    item("Outfall level fixed? (existing sewer / STP inlet)", "ASK", "not in a drawing", "answer in sewer_design.py --ask (question 3)")
    item("Population / sewage load", "ASK", "not in a drawing",
         "design population and per capita water supply - sewer_design.py --ask (questions 5-6)")
    inv_texts = sum(1 for t in texts if INVERT_TAG.match(t["text"] or ""))
    item("Invert levels (only for checking an EXISTING design)", "FOUND" if inv_texts else "NOT GIVEN",
         f"{inv_texts} IL text(s)", "not needed for a new design - the design fixes the inverts")
    units_found = ins == 6 or bool(edges and unit_ok)
    item("Drawing units = metres", "FOUND" if units_found else "CHECK",
         f"{UNITS.get(ins, str(ins))}" + (" ; written pipe lengths = drawn lengths" if edges and unit_ok else ""),
         "" if units_found else "lengths must be in metres - check a known distance in CAD")
    print("\n================ CHECKLIST ================")
    for c in chkl:
        print(f"   [{c['status']:<9}] {c['required']}: {c['found']}" + (f"\n               -> {c['to do']}" if c["to do"] else ""))

    # ---- Excel
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        print("(openpyxl not installed - Excel report skipped)")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(OUT_DIR, f"{stem}_dxf_inspect_{time.strftime('%Y%m%d_%H%M')}.xlsx")
    wb = Workbook()
    bold, head = Font(bold=True), PatternFill("solid", fgColor="D9E1F2")
    colours = {"FOUND": "C6EFCE", "PARTIAL": "FFEB9C", "CHECK": "FFEB9C", "ASK": "DDEBF7", "MISSING": "F8CBAD",
               "NOT GIVEN": "EDEDED"}

    def sheet(ws, rows, cols=None):
        if not rows:
            ws.append(["(none)"])
            return
        cols = cols or list(rows[0].keys())
        ws.append(cols)
        for c in ws[1]:
            c.font, c.fill = bold, head
        for r in rows:
            ws.append([r.get(c) for c in cols])
        for i, c in enumerate(cols, start=1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(60, max(12, len(c) + 2))
    ws = wb.active
    ws.title = "Checklist"
    sheet(ws, chkl)
    for r in range(2, ws.max_row + 1):
        st = ws.cell(r, 2).value
        if st in colours:
            ws.cell(r, 2).fill = PatternFill("solid", fgColor=colours[st])
    ws.append([])
    ws.append(["File", path])
    ws.append(["Options", f"tol {a.tol} m, level radius {a.level_radius} m, pipe layers {', '.join(pipe_layers)}"])
    sheet(wb.create_sheet("Layers"), sorted(lrows, key=lambda r: -r["line_length"]))
    sheet(wb.create_sheet("Texts by layer"), trows)
    sheet(wb.create_sheet("Blocks"), [{"block": k[0], "layer": k[1], "count": v["n"], "attribute tags": ", ".join(v["tags"]),
                                      "sample": v["sample"]} for k, v in brows.items()])
    sheet(wb.create_sheet("Network"), net_rows)
    sheet(wb.create_sheet("Manhole symbols"), mrows)
    ws = wb.create_sheet("Nodes")
    rows = []
    for n in nodes:
        if n["deg"] == 0:
            continue
        src, v = per_node.get(n["id"], (None, None))
        rows.append({"node": n["id"], "label": mh_labels.get(n["id"]), "x": round(n["x"], 3), "y": round(n["y"], 3),
                     "lines": n["deg"],
                     "type": "dead end" if n["deg"] == 1 else ("junction" if n["deg"] >= 3 else "through"),
                     "ground level": v, "level from": src})
    sheet(ws, rows)
    if edges:
        prow = []
        for e in edges:
            v = ann.get(e["id"], {})
            prow.append({"line": e["id"], "handle": e["handle"], "layer": e["layer"], "label": v.get("id"),
                         "from node": e["a"], "to node": e["b"],
                         "from MH": mh_labels.get(e["a"]), "to MH": mh_labels.get(e["b"]),
                         "drawn length": round(e["len"], 2), "written length": v.get("length"),
                         "dia (mm)": v.get("dia"), "slope 1 in": v.get("slope_1in")})
        sheet(wb.create_sheet("Pipes"), prow)
    if chk:
        ws = wb.create_sheet("Problems")
        prob = []
        for nid, other, d in chk["gaps"]:
            prob.append({"problem": "near-miss gap", "x": round(nodes[nid]["x"], 3), "y": round(nodes[nid]["y"], 3),
                         "detail": f"end {nid} is {d:.2f} m from node {other} (not joined)"})
        for nid, eid, d in chk["tjoints"]:
            prob.append({"problem": "T-joint without node", "x": round(nodes[nid]["x"], 3), "y": round(nodes[nid]["y"], 3),
                         "detail": f"end {nid} lies on line handle {edges[eid]['handle']} ({d:.2f} m) - break that line here"})
        for eid in chk["long"]:
            e = edges[eid]
            prob.append({"problem": "line longer than 30 m", "x": round(e["pts"][0][0], 3), "y": round(e["pts"][0][1], 3),
                         "detail": f"handle {e['handle']}, {e['len']:.1f} m (manholes will be added by the design)"})
        sheet(ws, prob)
    sheet(wb.create_sheet("Outfall hints"), orows)
    wb.save(out)
    print(f"\nExcel report: {out}  ({time.time() - t0:.0f} s)")
