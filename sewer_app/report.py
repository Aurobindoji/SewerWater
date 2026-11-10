"""Excel design report of a pipeline.run result.

From the original scripts sewer_design.py write_report / cost_sheet / slice_quantities / trench_slices / deep_manholes,
with the same sheets and columns, minus what only existed with SewerGEMS: model file names, scenario,
solver velocity / d/D columns of sheet 'Check', the lift-station option sheets (project decision: no lift
stations) and the PNG map of deep manholes (the plan DXF shows them).

    from sewer_app import report
    report.write_report(out, "output/oakdale_B_sewer_design.xlsx", source="oakdale_manholes.csv + ...")
"""
import json
import math
import os
import re
import time

from . import DATA_DIR
from .criteria import Rules
from .design import flushing_totals, priced_cost, rate_ref, slow_length

DEPTH_BANDS = [1.5, 3.0, 4.5, 6.0]     # report only (earthwork depth classes), m
SEWER_RATES_FILE = os.path.join(DATA_DIR, "sewer_sor_rates.json")


def r(x, k=3):
    return None if x is None else round(x, k)


def load_sewer_rates(path=None):
    """sewer_sor_rates.json (SOR sewer items with codes) or None when the file is absent."""
    path = path or SEWER_RATES_FILE
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def nominal_mm(d):
    """Nominal size (mm) of a designed conduit: the number in the catalog 'nominal', else the ID."""
    m = re.search(r"(\d+(?:\.\d+)?)", str(d["size"].get("nominal") or ""))
    return int(round(float(m.group(1)))) if m else int(round(d["D"]))


def trench_slices(rule, D_mm, depth):
    """Trench slices for one conduit: list of (width m, thickness m), top slice first.
    rule type 'stepped' (Riverside DPR): n = ceil(depth / slice); top width = D + bottom_add +
    step x (n-1), each lower slice 'step' narrower, bottom slice D + bottom_add; the last slice is the
    remaining depth. rule {'a_m', 'b'}: one width a + b x D for the whole depth. None if not set."""
    if not isinstance(rule, dict) or depth is None or depth <= 0:
        return None
    D = D_mm / 1000.0
    if rule.get("type") == "stepped":
        sl, add, step = float(rule.get("slice_m", 1.5)), float(rule["bottom_add_m"]), float(rule["step_m"])
        n = max(1, math.ceil(depth / sl - 1e-9))
        out = []
        for k in range(n):
            th = min(sl, depth - k * sl)
            out.append((D + add + step * (n - 1 - k), th))
        return out
    if rule.get("a_m") is not None:
        W = float(rule["a_m"]) + float(rule.get("b", 0.0)) * D
        sl = 1.5
        return [(W, min(sl, depth - k * sl)) for k in range(max(1, math.ceil(depth / sl - 1e-9)))]
    return None


def slice_quantities(res, sr):
    """Per conduit: depth used, length in each SOR depth band (laying), trench volume in each 1.5 m
    slice below GL (excavation), top trench width (road cutting) and timbering area.
    depth_basis 'average' (default, DPR practice): one depth = mean of u/s and d/s depth to invert;
    'profile': depth varies linearly along the conduit (400-step integration; one width per step)."""
    bands = sr["depth_bands_m"]["value"]
    rule = (sr.get("trench_width_m") or {}).get("value")
    trule = (sr.get("timbering_rule") or {}).get("value")
    basis = ((sr.get("depth_basis") or {}).get("value") or "average").lower()
    rows = []
    for lab, d in res.items():
        L, d0, d1 = d["length"] or 0.0, d["depth_up"], d["depth_dn"]
        if d0 is None or d1 is None or not L:
            continue
        nb = len(bands)
        lens, vols, top_w, timb = [0.0] * nb, [0.0] * nb, None, None
        steps = [((d0 + d1) / 2.0, L)] if basis == "average" else \
                [(d0 + (d1 - d0) * (k + 0.5) / 400, L / 400) for k in range(400)]
        have_v = False
        for dep, dl in steps:
            j = next((i for i, b in enumerate(bands) if dep <= b + 1e-9), nb - 1)
            lens[j] += dl
            sls = trench_slices(rule, d["D"], dep)
            if sls:
                have_v = True
                top_w = max(top_w or 0.0, sls[0][0])
                for k, (w, th) in enumerate(sls):
                    vols[min(k, nb - 1)] += w * th * dl
            if isinstance(trule, dict) and trule.get("upto_depth_m"):
                # timbered only where the trench is deeper than min_depth_m (project decision); then from
                # GL down to min(depth, upto_depth_m), as in the DPR formula
                tmin = float(trule.get("min_depth_m") or 0.0)
                timb = (timb or 0.0) + (min(dep, float(trule["upto_depth_m"])) * dl if dep > tmin + 1e-9 else 0.0)
        dep_used = (d0 + d1) / 2.0 if basis == "average" else None
        rows.append({"label": lab, "nom": nominal_mm(d), "D": d["D"], "L": L, "d0": d0, "d1": d1,
                     "dep": dep_used, "W": top_w, "lens": lens, "vols": vols if have_v else None,
                     "timb": timb, "too_deep": max(d0, d1) > bands[-1] + 1e-9})
    return rows


def deep_manholes(res, node_info, R):
    """Manholes deeper than max_depth_to_invert_m (CPHEEO p205) and, for each, the manhole JUST UPSTREAM of
    it that is still within the limit. Returns (deep set, rows of transitions)."""
    if R.max_depth is None:
        return set(), []
    lim = R.max_depth + 1e-6
    deep = {nd for nd, n in node_info.items() if n.get("depth") is not None and n["depth"] > lim}
    rows = []
    for lab, d in res.items():
        a, b = d["from"], d["to"]
        if b in deep and a not in deep:
            na, nb_ = node_info.get(a, {}), node_info.get(b, {})
            rows.append({"before": a, "g_before": na.get("ground"), "inv_before": na.get("invert"),
                         "dep_before": na.get("depth"), "conduit": lab, "D": d["D"], "length": d["length"],
                         "deep": b, "g_deep": nb_.get("ground"), "dep_deep": nb_.get("depth"),
                         "q": d["q"]})
    return deep, rows


def cost_sheet(wb, agg, szof, labels, node_info, new_mh, flush, cat_name, cat_src, bold, head, res=None, sr=None):
    """Sheet 'Cost' (+ 'Qty sewer'). Part A = items with a sourced rate, as live Excel formulas:
      pipe supply   - quantity SUMIFS over sheet 'Design' (length by material and ID), catalog rate;
      laying/jointing RCC NP3 (SOR 3196-3214, by depth slice) - quantity SUMIF over sheet 'Qty sewer';
      excavation (SOR 3001-3006.ii, slice-wise) - only when trench_width_m is set in sewer_sor_rates.json.
    Part B = quantities known from the design whose rates / rules are NOT set yet - shown, not priced."""
    from openpyxl.styles import Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    ws = wb.create_sheet("Cost", 1)                     # right after Summary
    dsh = wb["Design"]
    hdr = {c.value: get_column_letter(c.column) for c in dsh[1]}
    cL, cID, cMat = hdr["Length (m)"], hdr["ID (mm)"], hdr["Material"]
    last = dsh.max_row
    yellow = PatternFill("solid", fgColor="FFF2CC")

    # ---- quantity sheet (conduit-wise slices)
    qrows, qcol = [], {}
    if sr and res:
        bands = sr["depth_bands_m"]["value"]
        blab = [f"{a:g}-{b:g}" for a, b in zip([0.0] + bands[:-1], bands)]
        qrows = slice_quantities(res, sr)
        qs = wb.create_sheet("Qty sewer")
        qh = (["Conduit", "Nominal (mm)", "ID (mm)", "Length (m)", "Depth to invert u/s (m)", "Depth to invert d/s (m)"]
              + [f"Length (m) at depth {x} m" for x in blab] + ["Top trench width (m)"]
              + [f"Excavation (cum) slice {x} m" for x in blab] + ["Depth used (m)", "Timbering area (sqm)"])
        qs.append(qh)
        for c in qs[1]:
            c.font, c.fill = bold, head
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for q in qrows:
            qs.append([q["label"], q["nom"], q["D"], round(q["L"], 3), round(q["d0"], 3), round(q["d1"], 3)]
                      + [round(x, 3) for x in q["lens"]] + [round(q["W"], 3) if q["W"] else None]
                      + ([round(x, 3) for x in q["vols"]] if q["vols"] else [None] * len(bands))
                      + [round(q["dep"], 3) if q["dep"] is not None else None,
                         round(q["timb"], 3) if q["timb"] is not None else None])
        qlast = qs.max_row
        nb = len(bands)
        for i in range(nb):
            qcol[("L", i)] = get_column_letter(7 + i)
            qcol[("V", i)] = get_column_letter(8 + nb + i)
        qcol["T"] = get_column_letter(9 + 2 * nb)
        qs.append([])
        qs.append(["Method", f"Depth per conduit: {(sr.get('depth_basis') or {}).get('note', '')}"])
        qs.append(["Trench", f"{(sr.get('trench_width_m') or {}).get('note', 'trench width rule not set')} "
                   f"Source: {(sr.get('trench_width_m') or {}).get('_source', '-')}"])
        qs.append(["Timbering", f"{(sr.get('timbering_rule') or {}).get('note', 'not set')}"])
        for ci, h in enumerate(qh, start=1):
            qs.column_dimensions[get_column_letter(ci)].width = max(11, min(len(h) + 2, 22))
        qs.freeze_panes = "B2"

    def title(text):
        ws.append([text])
        ws.cell(row=ws.max_row, column=1).font = bold

    title("COST - sewer network (items with a sourced rate are priced; the rest is quantity only)")
    ws.append(["Pipe rates", f"sewer_catalog.json set {cat_name}: {cat_src}"[:500]])
    ws.append(["SOR rates", (sr or {}).get("_source", "sewer_sor_rates.json not found - laying / excavation not priced")])
    ws.append([])
    title("A. Items with a sourced rate")
    ws.append(["Sl No", "Item", "Rate item", "Quantity calculation", "Unit", "Quantity", "Rate (Rs)", "Amount (Rs)"])
    for c in ws[ws.max_row]:
        c.font, c.fill = bold, head
        c.alignment = Alignment(wrap_text=True, vertical="top")
    first_amt, sl = ws.max_row + 1, 0

    def add(item, code, calc, unit, qf, rate, missing=False):
        nonlocal sl
        sl += 1
        rr = ws.max_row + 1
        ws.append([sl, item, code, calc, unit, qf, rate, f'=IF(G{rr}="","",ROUND(F{rr}*G{rr},0))'])
        if missing:
            ws.cell(row=rr, column=7).fill = yellow

    # pipe supply
    for key, L in sorted(agg.items(), key=lambda x: x[0][2]):
        mat, nom, D = key
        rt = szof[key].get("rate_rs_per_m")
        qf = (f'=ROUND(SUMIFS(Design!${cL}$2:${cL}${last},Design!${cID}$2:${cID}${last},{D:g},'
              f'Design!${cMat}$2:${cMat}${last},"{mat}"),2)')
        add(f"Supply of {mat} pipe, {nom} (ID {D:g} mm)", rate_ref(szof[key]) or ("" if rt else "NO RATE in catalog"),
            f"Sum of 'Length (m)' in sheet Design for ID {D:g} mm, material '{mat}' (= {L:.1f} m)", "m", qf,
            float(rt) if rt else None, missing=not rt)
    # laying & jointing by depth slice
    if qrows:
        lay = sr["laying_rcc_np3"]["by_nominal_mm"]
        for nom in sorted({q["nom"] for q in qrows}):
            for i, b in enumerate(blab):
                tot = sum(q["lens"][i] for q in qrows if q["nom"] == nom)
                if tot <= 0.0005:
                    continue
                spec = lay.get(str(nom))
                col = qcol[("L", i)]
                qf = f"=ROUND(SUMIF('Qty sewer'!$B$2:$B${qlast},{nom},'Qty sewer'!${col}$2:${col}${qlast}),2)"
                add(f"Carting, laying and jointing RCC NP3 sewer {nom} mm (rubber ring), invert depth {b} m",
                    spec["codes"][i] if spec else "NO SOR item for this size",
                    f"Sum of sheet 'Qty sewer' column 'Length (m) at depth {b} m' for nominal {nom} mm (= {tot:.1f} m)",
                    "m", qf, spec["rates"][i] if spec else None, missing=not spec)
        # excavation by slice (needs the trench width rule)
        if any(q["vols"] for q in qrows):
            ex = sr["excavation_ordinary_soil"]
            for i, b in enumerate(blab):
                tot = sum(q["vols"][i] for q in qrows if q["vols"])
                if tot <= 0.0005:
                    continue
                col = qcol[("V", i)]
                add(f"Excavation in ordinary soil incl. refilling, slice {b} m below GL", ex["codes"][i],
                    f"Sum of sheet 'Qty sewer' column 'Excavation (cum) slice {b} m' (= {tot:.1f} cum)", "cum",
                    f"=ROUND(SUM('Qty sewer'!${col}$2:${col}${qlast}),2)", ex["rates"][i])
        tr = (sr.get("timbering_rule") or {}).get("value")
        if isinstance(tr, dict) and any(q["timb"] for q in qrows):
            tcode = tr.get("code", "3041")
            tspec = next(((c_, r_) for key in ("timbering_open", "timbering_close")
                          for c_, r_ in zip(sr.get(key, {}).get("codes", []), sr.get(key, {}).get("rates", []))
                          if c_ == tcode), None)
            col = qcol["T"]
            tmin = tr.get("min_depth_m")
            add(f"{tr.get('type', '').capitalize()} timbering in trenches 0-{tr.get('upto_depth_m', 3):g} m"
                + (f" (only trenches deeper than {tmin:g} m)" if tmin else ""),
                tcode if tspec else f"{tcode} - not in sewer_sor_rates.json",
                f"Sum of sheet 'Qty sewer' column 'Timbering area (sqm)' = min(depth, {tr.get('upto_depth_m', 3):g}) "
                f"x length" + (f", trenches deeper than {tmin:g} m only" if tmin else "")
                + f" (= {sum(q['timb'] or 0 for q in qrows):.1f} sqm)", "sqm",
                f"=ROUND(SUM('Qty sewer'!${col}$2:${col}${qlast}),2)", tspec[1] if tspec else None, missing=not tspec)
    last_amt = ws.max_row
    tot_row = ws.max_row + 1
    ws.append(["", "Total A (Rs)", "", "", "", "", "", f"=SUM(H{first_amt}:H{last_amt})"])
    ws.append(["", "Total A (Rs lakh)", "", "", "", "", "", f"=ROUND(H{tot_row}/100000,2)"])
    for rr in (tot_row, tot_row + 1):
        ws.cell(row=rr, column=2).font = bold
        ws.cell(row=rr, column=8).font = bold
    ws.append(["", "Rates as in the SOR / catalog (no GST, labour cess, contingency or centage added here)."])
    ws.append([])

    title("B. Quantities computed by the design - rate or rule NOT set yet (not priced, not in the total)")
    ws.append(["Sl No", "Item", "Needs", "Quantity calculation", "Unit", "Quantity"])
    for c in ws[ws.max_row]:
        c.font, c.fill = bold, head
    sl = 0
    if not (qrows and any(q["vols"] for q in qrows)):
        sl += 1
        ws.append([sl, "Excavation GL to invert (SOR 3001-3006.ii, slice-wise)", "trench_width_m rule",
                   "set 'trench_width_m' in sewer_sor_rates.json; volumes then appear in sheet 'Qty sewer'", "cum", None])
    deps = [(n, i.get("depth")) for n, i in node_info.items() if not i.get("outfall")]
    deps += [(m["label"], m.get("depth")) for m in (new_mh or []) if m.get("in_model")]
    cnt = [0] * len(labels)
    for _, dp in deps:
        if dp is not None:
            cnt[next((i for i, b in enumerate(DEPTH_BANDS) if dp <= b), len(DEPTH_BANDS))] += 1
    for lab, n in zip(labels, cnt):
        if n:
            sl += 1
            ws.append([sl, f"Manhole, depth to invert {lab} m", "manhole rate (unit estimate by type/depth)",
                       "original manholes (sheet Manholes) + new manholes added for spacing (sheet New manholes)",
                       "No", n])
    sl += 1
    ws.append([sl, "of these: drop manholes (incoming drop > drop_manhole_threshold_m)", "drop arrangement rate",
               "sheet Manholes, column 'Drop manhole'", "No", sum(1 for i in node_info.values() if i.get("drop"))])
    sl += 1
    ws.append([sl, "of these: flushing manholes (CPHEEO 3.29, p215)", "flushing arrangement rate (e.g. butterfly valve)",
               "sheet Flushing", "No", len(flush or [])])
    if qrows and any(q["W"] for q in qrows):
        sl += 1
        ws.append([sl, "Road cutting and reinstatement - area = top trench width x length", "road type per conduit (survey)",
                   "sheet 'Qty sewer': 'Top trench width (m)' x 'Length (m)' (all conduits)", "sqm",
                   round(sum((q["W"] or 0) * q["L"] for q in qrows), 1)])
    else:
        sl += 1
        ws.append([sl, "Road cutting and reinstatement", "trench width rule + road type per conduit", "", "", None])
    for txt in ("Bedding (bedding_rule)", "Dewatering (SOR 3031 - quantity rule)", "House connections"):
        sl += 1
        ws.append([sl, txt, "project decision / survey", "", "", None])
    if not ((sr or {}).get("timbering_rule") or {}).get("value"):
        sl += 1
        ws.append([sl, "Timbering / shoring", "timbering_rule", "", "", None])
    deep = [q["label"] for q in qrows if q["too_deep"]]
    if deep:
        ws.append([])
        ws.append(["Note", f"{len(deep)} conduit(s) deeper than the last SOR slice ({bands[-1]:g} m) - counted in the "
                   f"last slice: {', '.join(deep[:15])}"])
    for col, w in zip("ABCDEFGH", (7, 52, 24, 70, 7, 13, 12, 16)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        for c in row:
            if c.column in (2, 3, 4):
                c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A7"
    return ws


def write_report(out, path, source="", sor_rates=None):
    """Excel report of a pipeline.run result `out` at `path`. source = text naming the input network.
    Also writes <path without .xlsx>_new_manholes.csv when new manholes were planned. Returns path."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    res, node_info, crit = out["res"], out["node_info"], out["criteria"]
    cat_name, cat_src, _ = out["catalog"]
    check, flows, pop, node_avg = out["check"], out["flows"], out["pop"], out["avg"]
    new_mh, flush, warnings = out.get("new_mh") or [], out.get("flush") or [], out.get("warnings") or []
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bold, head = Font(bold=True), PatternFill("solid", fgColor="D9E1F2")
    red = PatternFill("solid", fgColor="F8CBAD")
    wb = Workbook()

    def sheet(title, header, rows, flag_col=None, widths=None):
        sh = wb.create_sheet(title)
        sh.append(header)
        for c in sh[1]:
            c.font, c.fill = bold, head
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for row in rows:
            sh.append(row)
            if flag_col is not None and row[flag_col]:
                sh.cell(row=sh.max_row, column=flag_col + 1).fill = red
        for ci, h in enumerate(header, start=1):
            sh.column_dimensions[get_column_letter(ci)].width = (widths or {}).get(h, max(11, len(h) + 2))
        sh.freeze_panes = "B2"
        return sh

    n_in = sum(1 for m in new_mh if m.get("in_model"))
    ws = wb.active
    ws.title = "Summary"
    grade = out.get("grade") or "DPR"
    ws.append(["DATA GRADE", grade if grade == "DPR" else "PFR - NOT VALID FOR A DPR (ground levels from DEM / assumed "
               "data; survey levels needed)"])
    ws.cell(row=1, column=1).font = Font(bold=True)
    ws.cell(row=1, column=2).font = Font(bold=True)
    if grade != "DPR":
        ws.cell(row=1, column=2).fill = red
    ws.append(["Ground level sources", ", ".join(f"{k}: {v}" for k, v in sorted((out.get("gl_sources") or {}).items()))])
    for row in [("Input network", source),
                ("Design flow", "from the contributory population (peak factor + infiltration, sheet 'Flows')"),
                ("Hydraulics", "uniform flow, Manning, constant n (CPHEEO p187/p190)"),
                ("Pipe catalog", f"{cat_name} - {cat_src}"), ("Designed on", time.strftime("%d-%m-%Y %H:%M")),
                ("Program", "sewer_app (SewerGEMS not used)")]:
        ws.append(list(row))
    ws.append([])
    ws.append(["Design run"])
    for line in list(out.get("log") or []) + [f"fixed outfall: {ln}" for ln in out.get("plan_lines") or []]:
        ws.append(["", line])
    ws.append([])
    ws.append(["Conduits designed", len(res)])
    ws.append(["Conduits with design flags", sum(1 for d in res.values() if d["flags"])])
    ws.append(["Drop manholes", sum(1 for n in node_info.values() if n["drop"])])
    ws.append(["Conduits failing final CPHEEO check (after split)", sum(1 for k in check["conduits"] if k["issues"])])
    ws.append(["New manholes for spacing and at bends (sheet 'New manholes')", len(new_mh)])
    ws.append(["   of these added to the split network", n_in])
    total, tank, trips, freq = flushing_totals(flush, crit)
    ws.append(["Flushing manholes (p215, sheet 'Flushing')", len(flush)])
    sl_len, sl_n = slow_length(flush, res)
    ws.append(["   sewer below self-cleansing velocity (each conduit once)", f"{sl_n} conduits, {sl_len:.0f} m"])
    ws.append(["   water per flushing round (L, Table 3.16)", round(total)])
    ws.append(["   tanker trips per round", f"{trips} x {tank:g} L" if trips else "-"])
    ws.append(["   flushing frequency (per day)", freq if freq else "not set - project decision"])
    if freq and total:
        ws.append(["   water per day (L)", round(total * freq)])
        ws.append(["   tanker trips per day", f"{math.ceil(total * freq / tank)} x {tank:g} L" if tank else "-"])
    amt, miss = priced_cost(res)
    ws.append(["Pipe material cost (catalog rates, Rs lakh) - sheet 'Length by size'", round(amt / 1e5, 2),
               f"rates: {cat_src}"[:250],
               f"NO RATE in the catalog for {', '.join(miss)} - not included" if miss else
               "length x rate per size; pipe material only (no excavation, laying, manholes, road)"])
    ws.append([])
    ws.append(["Criterion", "Value", "Source (verify)", "Note"])
    for c in ws[ws.max_row]:
        c.font, c.fill = bold, head
    for key, item in crit["sewer"].items():
        if key.startswith("_"):
            continue
        v = item.get("value")
        ws.append([key, json.dumps(v) if isinstance(v, (dict, list)) else ("not set" if v is None else v),
                   item.get("page", ""), item.get("note", "")])
    if warnings:
        ws.append([])
        ws.append(["Warnings"])
        for w in warnings:
            ws.append(["", w])
    for col, w in zip("ABCD", (34, 40, 50, 90)):
        ws.column_dimensions[col].width = w

    order = list(res.values())
    sheet("Design", ["Conduit", "From MH", "To MH", "Length (m)", "Design flow (L/s)", "Material", "Nominal",
                     "ID (mm)", "Manning n", "Slope", "Slope 1 in", "Governed by", "U/S ground (m)", "U/S invert (m)",
                     "D/S ground (m)", "D/S invert (m)", "U/S depth to invert (m)", "D/S depth to invert (m)",
                     "Velocity uniform (m/s)", "d/D uniform", "Flags", "Pipe rate (Rs/m)", "Pipe cost (Rs)",
                     "Initial peak flow (L/s)", "Velocity at initial peak (m/s)", "d/D at initial peak",
                     "+15 years peak flow (L/s)", "Velocity at +15 years peak (m/s)", "d/D at +15 years peak"],
          [[d["label"], d["from"], d["to"], r(d["length"], 2), r(d["q"]), d["size"]["material"], d["size"]["nominal"],
            d["D"], d["n"], r(d["slope"], 6), round(1 / d["slope"]) if d["slope"] > 0 else None, d["gov"],
            r(d["g_up"]), r(d["up"]), r(d["g_dn"]), r(d["dn"]), r(d["depth_up"], 2), r(d["depth_dn"], 2),
            r(d["v"]), r(d["dd"]), "; ".join(d["flags"]), d["size"].get("rate_rs_per_m"),
            round((d["length"] or 0) * float(d["size"]["rate_rs_per_m"])) if d["size"].get("rate_rs_per_m") else None,
            r(d.get("q_init"), 4), r(d.get("v_init")), r(d.get("dd_init")),
            r(d.get("q_mid"), 4), r(d.get("v_mid")), r(d.get("dd_mid"))]
           for d in order], flag_col=20, widths={"Flags": 70, "Governed by": 24})
    if out.get("stages"):
        # stage-wise check (CPHEEO Table 2.1 p2-9: sewers +30 years, pumping machinery and STP +15 years)
        sheet("Stages", ["Stage", "Year", "Population", "Outfall", "Population at outfall", "Average sewage (L/s)",
                         "Average sewage (MLD)", "Peak flow (L/s)", "Lowest velocity (m/s)", "Velocity limit (m/s)",
                         "Sewers below it", "Their length (m)", "Highest d/D", "Rule"],
              [[{"init": "base year", "mid": "+15 years (pumps, STP)", "ult": "+30 years (sewers)"}[st["stage"]],
                st["year"], st["pop"], o["outfall"], o["pop"], o["avg_lps"], o["avg_mld"], o["peak_lps"],
                st["v_min"], st["v_limit"], st["slow_n"], st["slow_m"], st["dd_max"], st["v_rule"]]
               for st in out["stages"] for o in st["outfalls"]], widths={"Stage": 24, "Rule": 40})

    Rr = Rules(crit)
    deep, trans = deep_manholes(res, node_info, Rr)
    before = {t["before"] for t in trans}
    lim_txt = f"{Rr.max_depth:g} m" if Rr.max_depth is not None else ""
    ST_DEEP = (f"DEEPER than {lim_txt} (lift station needed, p205)" if Rr.lifts_allowed else
               f"DEEPER than {lim_txt} (CPHEEO p205; no lift stations - accepted up to {Rr.max_depth_project:g} m, "
               f"justify in DPR; deeper = new zone + pumping station)")
    ST_BEFORE = f"last manhole within {lim_txt} before the deep sewer"
    msh = sheet("Manholes", ["Node", "Ground (m)", "Invert (m)", "Depth to invert (m)", "Max incoming drop (m)",
                             "Outfall", "Drop manhole", "Flushing manhole", "Depth status"],
                [[nd, r(n.get("ground")), r(n.get("invert")), r(n.get("depth"), 2), r(n.get("max_in_drop"), 2),
                  "yes" if n.get("outfall") else "", n.get("drop", ""), "yes" if n.get("flushing") else "",
                  ST_DEEP if nd in deep else (ST_BEFORE if nd in before else "")]
                 for nd, n in node_info.items()], flag_col=6, widths={"Drop manhole": 50, "Depth status": 48})
    f_deep = PatternFill("solid", start_color="F87171")
    f_bef = PatternFill("solid", start_color="FDBA74")
    for row in msh.iter_rows(min_row=2):
        st_ = row[8].value
        if st_:
            fill = f_deep if st_ == ST_DEEP else f_bef
            for c_ in (row[0], row[3], row[8]):
                c_.fill = fill
    if trans:
        sheet("Deep sewer start", ["Last MH within limit", "Its ground (m)", "Its invert (m)", "Its depth (m)",
                                   "Conduit", "ID (mm)", "Length (m)", "Design flow (L/s)", "Next MH (too deep)",
                                   "Its ground (m)", "Its depth (m)"],
              [[t["before"], r(t["g_before"]), r(t["inv_before"]), r(t["dep_before"], 2), t["conduit"], t["D"],
                r(t["length"], 1), r(t["q"]), t["deep"], r(t["g_deep"]), r(t["dep_deep"], 2)]
               for t in sorted(trans, key=lambda t: -(t["dep_deep"] or 0))])

    if flush:
        sh = sheet("Flushing", ["Flushing MH", "Head of sewer", "Ground (m)", "Invert (m)", "Depth to invert (m)",
                                "First slow conduit", "ID (mm)", "Slope 1 in", "Design flow (L/s)",
                                "Velocity uniform (m/s)", "Why not self-cleansing",
                                "Table 3.16 column (mm)", "Table 3.16 row (1 in)", "Water per flush (L)",
                                "Slow run length below this MH (m)", "Conduits in run", "Run ends at", "Note"],
                   [[f_["manhole"], "yes" if f_["head_of_sewer"] else "no (below a junction)", r(f_["ground"]),
                     r(f_["invert"]), r(f_["depth"], 2), f_["conduit"], f_["D"],
                     round(1 / f_["slope"]) if f_["slope"] else None, r(f_["q"]), r(f_["v"]), f_["reason"],
                     f_["col"], f_["row"], f_["litres"], r(f_["run_len"], 1), f_["run_n"], f_["run_end"],
                     f_["note"]] for f_ in flush], flag_col=None,
                   widths={"Why not self-cleansing": 28, "Note": 60, "Head of sewer": 20})
        for i, f_ in enumerate(flush, start=2):          # red only where Table 3.16 does not cover it
            if f_.get("outside"):
                sh.cell(row=i, column=18).fill = red
        sh.append([])
        sh.append(["Total water per flushing round (L)", round(total)])
        sh.append(["Tanker trips per round", f"{trips} x {tank:g} L" if trips else "-"])
        sh.append(["Flushing frequency (per day)", freq if freq else "not set - project decision (no general rule "
                   "in the manual)"])
        if freq and total:
            sh.append(["Water per day (L)", round(total * freq)])
            sh.append(["Tanker trips per day", f"{math.ceil(total * freq / tank)} x {tank:g} L" if tank else "-"])
        sh.append(["Rule", "CPHEEO 3.29, p215 (3-56): flushing where self-cleansing velocity is not obtained, "
                   "especially at the top ends of branch sewers; flushing manholes generally at the head of a "
                   "sewer; water per flush from Table 3.16 (row = next flatter tabulated slope, safe side). "
                   "Suggested method: butterfly valve at the head sewer mouth + tanker of treated sewage from "
                   "the STP (about 6000 L, at least two manholes per trip); automatic systems not recommended."])

    agg, szof = {}, {}
    for d in order:
        key = (d["size"]["material"], d["size"]["nominal"], d["D"])
        agg[key] = agg.get(key, 0.0) + (d["length"] or 0)
        szof[key] = d["size"]
    ups = out.get("upsized") or []
    if ups:
        sheet("Upsized for fall", ["Conduit", "From MH", "To MH", "Length (m)", "Design flow (L/s)",
                                   "ID free design (mm)", "ID chosen (mm)", "Slope 1 in free", "Slope 1 in chosen",
                                   "Velocity free (m/s)", "Velocity chosen (m/s)", "Extra pipe cost (Rs)"],
              [[u["label"], u["from"], u["to"], r(u["length"], 1), r(u["q"]), u["D_free"], u["D"],
                round(1 / u["s_free"]) if u["s_free"] else None, round(1 / u["s"]) if u["s"] else None,
                r(u["v_free"]), r(u["v"]), round(u["extra_cost"])] for u in ups])

    lrows, tot = [], 0.0
    for key, L in sorted(agg.items(), key=lambda x: x[0][2]):
        m, nom, D = key
        rt = szof[key].get("rate_rs_per_m")
        a = round(L * float(rt)) if rt else None
        tot += a or 0
        lrows.append([m, nom, D, round(L, 1), rt, a, rate_ref(szof[key]) or ("" if rt else "NO RATE in catalog")])
    sh = sheet("Length by size", ["Material", "Nominal", "ID (mm)", "Length (m)", "Rate (Rs/m)", "Amount (Rs)",
                                  "Rate item"], lrows, widths={"Rate item": 30})
    sh.append(["Total", "", "", round(sum(agg.values()), 1), "", round(tot)])
    sh.append(["Rates from", f"sewer_catalog.json set {cat_name}: {cat_src}"])
    sh.append(["Covers", "pipe material only - no excavation, laying, jointing, manholes, road restoration"])

    labels = [f"0-{DEPTH_BANDS[0]}"] + [f"{a}-{b}" for a, b in zip(DEPTH_BANDS, DEPTH_BANDS[1:])] + [f">{DEPTH_BANDS[-1]}"]
    band = {}
    for d in order:
        deps = [x for x in (d["depth_up"], d["depth_dn"]) if x is not None]
        if not deps:
            continue
        avg = sum(deps) / len(deps)
        idx = next((i for i, b in enumerate(DEPTH_BANDS) if avg <= b), len(DEPTH_BANDS))
        key = (d["size"]["nominal"], d["D"])
        band.setdefault(key, [0.0] * len(labels))[idx] += d["length"] or 0
    sheet("Depth bands", ["Nominal", "ID (mm)"] + [f"Length (m), avg depth {x} m" for x in labels],
          [[nom, D] + [round(x, 1) for x in v] for (nom, D), v in sorted(band.items(), key=lambda x: x[0][1])])

    # ---- Cost: quantities by Excel formula from sheet 'Design', rate x quantity, totals
    cost_sheet(wb, agg, szof, labels, node_info, new_mh, flush, cat_name, cat_src, bold, head, res,
               sr=sor_rates if sor_rates is not None else load_sewer_rates())

    sheet("New manholes", ["New MH", "Why", "On conduit", "From MH", "To MH", "Chainage from u/s MH (m)",
                           "Spacing (m)", "Limit (m)", "X", "Y", "Ground (m)", "Ground source", "Invert (m)",
                           "Depth to invert (m)", "Cover (m)", "Pipe ID (mm)", "In split network"],
          [[m["label"], m.get("why", "spacing"), m["conduit"], m["from"], m["to"], r(m["chainage"], 2),
            r(m["spacing"], 2), m["limit"],
            r(m["x"], 3), r(m["y"], 3), r(m["ground"]), m.get("ground_src", ""), r(m["invert"]), r(m["depth"], 2),
            r(m["cover"], 2), m["D"], "yes" if m.get("in_model") else "no"]
           for m in new_mh], widths={"Ground source": 22})

    sheet("Flows", ["Conduit", "From MH", "To MH", "Contributory population", "Peak factor",
                    "Average sewage (L/s)", "Peak sewage (L/s)", "Upstream sewer length (m)",
                    "Upstream manholes", "Infiltration before limit (L/s)", "Infiltration used (L/s)",
                    "Design flow (L/s)"],
          [[lab, f["from"], f["to"], round(f["P"], 1), f["pf"], r(f["A"], 4), r(f["peak"], 4), r(f["L"], 1),
            f["N"], r(f["infil_raw"], 4), r(f["infil"], 4), r(f["Q"], 4)] for lab, f in flows.items()])
    sheet("Population", ["Manhole", "Population", "Average sewage (L/s)"],
          [[m, round(p, 2), r((node_avg or {}).get(m), 5)] for m, p in sorted((pop or {}).items())])
    sheet("Check", ["Conduit", "Dia (mm)", "Flow (L/s)", "Velocity uniform (m/s)", "d/D uniform", "Min cover (m)",
                    "Issues"],
          [[k["label"], r(k["diameter_mm"], 1), r(k["flow_lps"]), r(k.get("vel_uniform_mps")), r(k.get("dd_uniform")),
            r(k["cover_min_m"], 2), k["issues"]] for k in check["conduits"]],
          flag_col=6, widths={"Issues": 80})
    wb.save(path)
    if new_mh:
        import csv
        with open(path[:-5] + "_new_manholes.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Label", "X", "Y", "GroundElevation", "InvertElevation", "OnConduit", "Chainage_m", "InModel",
                        "Why"])
            for m in new_mh:
                w.writerow([m["label"], r(m["x"], 3), r(m["y"], 3), r(m["ground"]), r(m["invert"]),
                            m["conduit"], r(m["chainage"], 2), "yes" if m.get("in_model") else "no",
                            m.get("why", "spacing")])
    return path
