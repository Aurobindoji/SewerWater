"""Final CPHEEO check of the designed sewer, on the network AFTER the manhole-spacing split.

check_sewer is the original scripts design_check.check_sewer with the SewerGEMS-only parts left out: there is no solver
here, so velocity and d/D are always judged on uniform flow (Manning, constant n - the project decision
'check_basis: uniform'), and Q/Qfull surcharge and HGL-above-rim (solver results) are not checked.
final_check_records builds its input from the design: each split piece takes the diameter, n and design flow
of the conduit it came from, and its inverts on the designed grade.
"""
from .criteria import slope_row, table_rows, val
from .hydraulics import uniform_flow

DEPTH_LIMIT_KEY = "max_depth_to_invert_m"        # design_criteria.json -> sewer (p205, 6 m below GL)


def depth_limit(c):
    """Maximum sewer depth from the 'sewer' criteria: (key, value, short page) or (None, None, None)."""
    import re
    item = c.get(DEPTH_LIMIT_KEY)
    v = item.get("value") if isinstance(item, dict) else None
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
        page = str(item.get("page", "") or "")
        page = re.split(r" - |, |; ", page)[0].replace("CPHEEO_sewer_manual_all ", "")
        return DEPTH_LIMIT_KEY, float(v), page
    return None, None, None


def final_check_records(net_split, made, res, flows, node_info, new_mh):
    """{"conduits": [...], "manholes": [...], "outfalls": [...]} in the shape check_sewer reads, for every
    conduit of the split network (design direction: slope > 0 downhill, to_outfall True)."""
    piece_of = {p["label"]: (lab, p) for lab, pcs in made.items() if pcs for p in pcs}
    new_by = {m["label"]: m for m in new_mh or []}
    ground = {n: v.get("ground") for n, v in net_split["nodes"].items()}
    conds = []
    for k in net_split["conduits"]:
        lab = k["label"]
        if lab in piece_of:
            parent, p = piece_of[lab]
            d = res[parent]
            if d["rev"]:                                 # piece drawn against the flow
                a, b, up, dn = p["stop"], p["start"], p["dn"], p["up"]
            else:
                a, b, up, dn = p["start"], p["stop"], p["up"], p["dn"]
            L = p["length"]
        else:
            parent, d = lab, res[lab]
            a, b, up, dn, L = d["from"], d["to"], d["up"], d["dn"], d["length"]
        D = d["D"]
        covers = [g - inv - D / 1000.0 for g, inv in ((ground.get(a), up), (ground.get(b), dn)) if g is not None]
        conds.append({"label": lab, "parent": parent, "from": a, "to": b, "diameter_mm": D, "n": d["n"],
                      "length_m": L, "slope": (up - dn) / L if L else None, "to_outfall": True,
                      "flow_lps": flows[parent]["Q"] if flows and parent in flows else d["q"],
                      "q_by_qfull": None, "cover_min_m": min(covers) if covers else None,
                      "up_invert_m": up, "dn_invert_m": dn})
    mhs = []
    for n, info in node_info.items():
        mhs.append({"label": n, "ground_m": info.get("ground"), "rim_m": None, "invert_m": info.get("invert"),
                    "hgl_m": None})
    for m in new_mh or []:
        if m.get("in_model"):
            mhs.append({"label": m["label"], "ground_m": m["ground"], "rim_m": None, "invert_m": m["invert"],
                        "hgl_m": None})
    return {"conduits": conds, "manholes": mhs, "outfalls": list(net_split["outfalls"])}


def check_sewer(data, crit, stage):
    c = crit["sewer"]
    vmin = val(c, "min_velocity_ultimate_peak_mps" if stage == "ultimate" else "min_velocity_initial_peak_mps")
    vmax, ddmax = val(c, "max_velocity_mps"), val(c, "max_d_by_D")
    dmin, spacing = val(c, "min_diameter_mm"), val(c, "max_manhole_spacing_m")
    slope_rows, cover_min = table_rows(val(c, "min_slope_by_diameter")), val(c, "min_cover_m")
    trunk = {str(x) for x in (val(c, "trunk_conduits") or [])}
    trunk_rows = table_rows(val(c, "max_manhole_spacing_trunk_m"))
    basis = (val(c, "check_basis") or "uniform").lower()
    warnings, no_flow, no_slope_row, no_cover, no_uniform = [], [], [], [], []
    if basis != "uniform":
        warnings.append(f"check_basis '{basis}' needs a hydraulic solver - checked on uniform flow instead")
    tag = "uniform flow"

    for k in data["conduits"]:
        iss = []
        d, s, L = k["diameter_mm"], k["slope"], k["length_m"]
        t = k.get("to_outfall")
        if s is not None and (t is False or (t is None and k["flow_lps"] is not None and k["flow_lps"] < 0)):
            s = -s
        has_flow = k["flow_lps"] is not None and abs(k["flow_lps"]) > 0

        k["dd_uniform"], k["vel_uniform_mps"] = uniform_flow(k["flow_lps"], d, s, k["n"])
        v, dd = k["vel_uniform_mps"], k["dd_uniform"]
        if has_flow and v is None and s is not None and s > 0:
            no_uniform.append(k["label"])

        if has_flow and v is not None:
            if vmin is not None and v < vmin - 0.005:          # 5 mm/s tolerance (rounding)
                iss.append(f"velocity {v:.2f} < {vmin} m/s ({stage} peak, {tag})")
            if vmax is not None and v > vmax:
                iss.append(f"velocity {v:.2f} > {vmax} m/s ({tag})")
        elif not has_flow:
            no_flow.append(k["label"])
        if ddmax is not None and dd is not None and dd > ddmax:
            iss.append(f"d/D {dd:.2f} > {ddmax} ({tag})")
        if dmin is not None and d is not None and d < dmin - 0.5:
            iss.append(f"diameter {d:.0f} < {dmin} mm")

        # minimum slope (Table 3.13)
        row_d, row_s = slope_row(slope_rows, d)
        if slope_rows and d is not None and row_d is None:
            no_slope_row.append(k["label"])
        if s is not None and s <= 0:
            iss.append("zero/adverse slope")
        elif s is not None and row_s is not None and s < row_s - 1e-9:
            iss.append(f"slope 1 in {1 / s:.0f} flatter than 1 in {1 / row_s:.0f} (Table 3.13, {row_d:g} mm row)")

        # manhole spacing: 30 m with house connections; Table 3.31 for listed trunk conduits
        if (k["label"] in trunk or k.get("parent") in trunk) and trunk_rows:
            lim = next((sp for dm, sp in trunk_rows if d is not None and d <= dm + 0.5), None)
            why = "trunk, Table 3.31"
            if lim is None:
                warnings.append(f"{k['label']}: trunk diameter {d} mm is above Table 3.31 - spacing not checked")
        else:
            lim, why = spacing, "house connections"
        if lim is not None and L is not None and L > lim + 0.5:
            iss.append(f"length {L:.1f} m > manhole spacing {lim:g} m ({why})")

        if cover_min is not None:
            if k["cover_min_m"] is None:
                no_cover.append(k["label"])
            elif k["cover_min_m"] < cover_min - 0.005:         # 5 mm tolerance (rounding)
                iss.append(f"cover {k['cover_min_m']:.2f} < {cover_min} m")
        k["issues"] = "; ".join(iss)

    unknown = trunk - {k["label"] for k in data["conduits"]} - {k.get("parent") for k in data["conduits"]}
    if unknown:
        warnings.append(f"trunk_conduits not found in the network: {', '.join(sorted(unknown))}")
    if no_flow:
        warnings.append(f"{len(no_flow)} conduit(s) carry NO flow - velocity not checked "
                        f"(no self-cleansing): {', '.join(no_flow[:15])}{' ...' if len(no_flow) > 15 else ''}")
    if no_slope_row:
        warnings.append(f"{len(no_slope_row)} conduit(s) smaller than the first row of Table 3.13 - "
                        f"minimum slope not checked: {', '.join(no_slope_row[:15])}")
    if no_uniform:
        warnings.append(f"{len(no_uniform)} conduit(s) carry more than the pipe's maximum part-full "
                        f"capacity (Manning) - uniform-flow velocity/d/D not computed: {', '.join(no_uniform[:15])}")
    if no_cover:
        warnings.append(f"{len(no_cover)} conduit(s) without node ground level - cover not checked: "
                        f"{', '.join(no_cover[:15])}")
    data["warnings"] = warnings
    data["check_basis"] = "uniform"

    dkey, dlim, dpage = depth_limit(c)
    if dkey is None:
        warnings.append(f"maximum sewer depth NOT checked - key '{DEPTH_LIMIT_KEY}' not found in design_criteria.json 'sewer'")
    la = val(c, "lift_stations_allowed")
    lifts_ok = True if la is None else bool(la)
    plim = (val(c, "max_depth_project_m") or dlim) if not lifts_ok else None
    deep, deep_p = [], []
    for m in data["manholes"]:
        iss = []
        top = m["ground_m"] if m["ground_m"] is not None else m["rim_m"]
        depth = top - m["invert_m"] if (top is not None and m["invert_m"] is not None) else None
        m["depth_gl_m"] = depth
        if dlim is not None and depth is not None and depth > dlim + 0.005:     # 5 mm tolerance
            if lifts_ok:
                iss.append(f"depth {depth:.2f} m > {dlim:g} m (lift station needed{', ' + dpage if dpage else ''})")
            elif depth > plim + 0.005:
                iss.append(f"depth {depth:.2f} m > project limit {plim:g} m (no lift stations - needs its own zone "
                           f"+ pumping station)")
                deep_p.append(m["label"])
            else:
                iss.append(f"depth {depth:.2f} m > {dlim:g} m{' (' + dpage + ')' if dpage else ''} - accepted up to "
                           f"{plim:g} m (project decision), justify in the DPR")
            deep.append(m["label"])
        m["issues"] = "; ".join(iss)
    if deep:
        warnings.append(f"{len(deep)} manhole(s) deeper than {dlim:g} m "
                        + ("- lift / pumping station needed" if lifts_ok else
                           f"(CPHEEO) - no lift stations: accepted up to {plim:g} m, justify in the DPR")
                        + f" (key '{dkey}'): {', '.join(deep[:15])}{' ...' if len(deep) > 15 else ''}")
    if deep_p:
        warnings.append(f"{len(deep_p)} manhole(s) deeper than the project limit {plim:g} m - split into zones with "
                        f"pumping stations (zoning): {', '.join(deep_p[:15])}{' ...' if len(deep_p) > 15 else ''}")
    return data
