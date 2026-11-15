"""The sewer design of the map page (/api/design): the network of an option designed, its drawings, the stages and
the checks (restructure stage 6, 15-Nov-2026: out of ui.py)."""
import os
import time
from .project import has_network, paths, safe_name, to_latlng
from .inputs import criteria_for, design_inputs
from .results import _keep, _source
from .zoning_run import _zoning, barrier_res


def run_design(name, req):
    """Design of the project's layout with a zoning option applied (as 'python -m sewer_app design
    --zoning-option'): report Excel, plan DXF, L-section DXF; for the page every designed sewer with its size,
    slope, depths and velocity."""
    from . import cad, dpr, hindi, lsection, pipeline, report, zoning
    from . import DesignError
    from . import edits as ed
    stem = safe_name(name)
    folder, f_mh, _, _ = paths(stem)
    if not has_network(stem):
        return {"ok": False, "log": "पहले DXF network खोलें या Layout बनाएँ"}
    lines = []
    try:
        inp = design_inputs(stem, req)
        stp = (req.get("stp") or "").strip() or None
        z, net, _ = _zoning(stem, inp, stp, req.get("max_zones") or 8, lines.append, req.get("mode") or "auto",
                            req.get("max_depth"), req.get("bend_drop"), req.get("edits"), req.get("mh_spacing"),
                            req.get("bend_angle"), req.get("barriers"), req.get("loops"), req.get("crossings"))
        opt = req.get("option") or z["rank"][0]["m"]["option"]
        ev = next((e for e in z["rank"] if e["m"]["option"] == opt), None)
        if ev is None:
            return {"ok": False, "log": f"option '{opt}' नहीं मिला"}
        net2, applied = zoning.apply_option(net, ev)
        trunk = ed.clean(req.get("edits"))["trunk"]
        if trunk:                       # the trunk sewers and their pieces (pipeline takes them from the inputs)
            inp["trunk"] = ed.trunk_labels(net2, trunk)
        out = pipeline.run(net2, inp, crit=criteria_for(req.get("max_depth"), req.get("bend_drop"), req.get("mh_spacing"),
                                                       req.get("bend_angle"), trunk),
                           log=lines.append,
                           fixed_inv=net.get("_fixed_inv"))
        out["log"].insert(0, f"zoning option {opt} applied (map UI): outfalls {', '.join(net2['outfalls'])}; "
                             f"{len(applied)} cut conduit(s) disconnected at one end")
        if trunk:
            out["log"].insert(1, f"trunk sewers (page, CPHEEO Table 3.31 spacing): {len(trunk)} marked, "
                                 f"{len(inp['trunk'])} conduit(s) of the design")
        base = os.path.join(folder, f"{stem}_{opt}_sewer_design_{time.strftime('%Y%m%d_%H%M')}"
                                    + ("_PFR" if out["grade"] != "DPR" else ""))
        xl = report.write_report(out, base + ".xlsx", source=_source(stem))
        # the DPR sheets in the format of the Riverside estimate (user request 22-Oct-2026); its pumping stations as
        # in the zoning comparison: every zone outlet but the STP's (without an STP, the zone with the largest flow is
        # taken as reaching it by gravity)
        zr = [x for x in ev.get("zones") or [] if x["role"] == "pumping station"]
        if not stp and zr:
            grav = max(zr, key=lambda x: (x["design flow at outlet (L/s)"] or 0, x["zone outlet"]))
            zr = [x for x in zr if x is not grav]
        import glob
        prev = sorted(glob.glob(os.path.join(folder, f"{stem}_*_DPR.xlsx")), key=os.path.getmtime)
        xl_dpr = dpr.write_dpr(out, base + "_DPR.xlsx", title=f"{stem.replace('_', ' ').upper()} SEWERAGE SCHEME",
                               inp=inp, stations=[{"outfall": x["zone outlet"], "dist": x.get("straight distance to STP (m)")}
                                                  for x in zr if (x["design flow at outlet (L/s)"] or 0) > 0],
                               previous=prev[-1] if prev else None)    # the texts typed in its Project sheet are kept
        cad.design_drawing(out, base + ".dxf")
        lsection.draw(out, base + "_Lsection.dxf")
    except DesignError as e:
        return {"ok": False, "log": "\n".join(lines) + f"\n*** {e}"}
    except Exception as e:
        return {"ok": False, "log": "\n".join(lines) + f"\n{type(e).__name__}: {e}"}
    from .criteria import slope_row
    given = ed.clean(req.get("edits"))
    ll = to_latlng(stem)
    xy = out["xy"]
    res = out["res"]
    R = out["rules"]
    sewers = []
    # each sewer as drawn (with its bends, where the new manholes at bends lie), from its upstream manhole down
    verts = {k["label"]: k.get("vertices") or [] for k in net2["conduits"]}
    orig = {k["label"]: k.get("piece_of") or k["label"] for k in net2["conduits"]}   # the network's conduit of a piece
    trunk_set = set(inp.get("trunk") or [])
    gl_of = dict(out["ground"], **{m["label"]: m["ground"] for m in out["new_mh"]})

    def pieces_of(lab, d):
        """The conduits the new manholes (30 m spacing, bends) cut a designed sewer into - as in the plan DXF - from
        upstream down: label (the first keeps the sewer's), manholes, length, inverts, ground, depth, line."""
        made = (out.get("made") or {}).get(lab)
        if not made or len(made) < 2:
            return []
        out_ = []
        for p in (made[::-1] if d["rev"] else made):
            a_, b_, up, dn = (p["stop"], p["start"], p["dn"], p["up"]) if d["rev"] else (p["start"], p["stop"], p["up"], p["dn"])
            pts = [tuple(q) for q in p["vertices"]]
            pts = pts[::-1] if d["rev"] else pts
            g_a, g_b = gl_of.get(a_), gl_of.get(b_)
            out_.append({"label": p["label"], "from": a_, "to": b_, "length": p["length"], "il_up": up, "il_dn": dn,
                         "gl_up": g_a, "gl_dn": g_b, "depth_up": g_a - up if g_a is not None else None,
                         "depth_dn": g_b - dn if g_b is not None else None, "pts": [ll(q) for q in pts]})
        return out_

    for lab, d in res.items():
        a, b = xy.get(d["from"]), xy.get(d["to"])
        if not a or not b:
            continue
        line = [tuple(p) for p in verts.get(lab) or []]
        line = (line[::-1] if d["rev"] else line) if len(line) >= 2 else [a, b]
        line[0], line[-1] = a, b
        _, s_min = slope_row(R.slopes, d["D"])
        cov = [g - (il + d["D"] / 1000.0) if g is not None and il is not None else None
               for g, il in ((d["g_up"], d.get("up")), (d["g_dn"], d.get("dn")))]
        sewers.append({"label": lab, "pts": [ll(p) for p in line], "D": d["D"], "slope": d["slope"], "length": d["length"],
                       "q": d["q"], "v": d["v"], "depth_up": d["depth_up"], "depth_dn": d["depth_dn"],
                       "gl_up": d["g_up"], "gl_dn": d["g_dn"], "il_up": d.get("up"), "il_dn": d.get("dn"),
                       "from": d["from"], "to": d["to"], "flags": d.get("flags") or [],
                       "dd": d.get("dd"), "s_min": s_min, "cover_up": cov[0], "cover_dn": cov[1],
                       "edited": lab in given["conduits"], "checks": _sewer_checks(d, R, s_min, cov),
                       "pieces": pieces_of(lab, d), "orig": orig.get(lab, lab), "trunk": lab in trunk_set,
                       **{f"{x}_{t}": d.get(f"{x}_{t}") for t in ("init", "mid") for x in ("q", "v", "dd")}})
    manholes = []
    ins, outs_ = {}, {}
    for d in res.values():
        ins.setdefault(d["to"], []).append(d["label"])
        outs_.setdefault(d["from"], []).append(d["label"])
    for n, i in out["node_info"].items():
        if n not in xy:
            continue
        chk = []
        if i.get("depth") is not None and R.max_depth is not None and i["depth"] > R.max_depth + 1e-6:
            chk.append(f"depth > {R.max_depth:g} m (CPHEEO)")
        if i.get("depth") is not None and R.max_depth_project and i["depth"] > R.max_depth_project + 1e-6:
            chk.append(f"depth > {R.max_depth_project:g} m (project)")
        nv = net2["nodes"].get(n) or {}
        manholes.append({"label": n, "latlng": ll(xy[n]), "gl": i.get("ground"), "invert": i.get("invert"),
                         "new": "" if nv.get("cut_of") else nv.get("new_mh") or "",   # put in at a bend / for the spacing
                         "depth": i.get("depth"), "drop": i.get("drop") or "", "max_in_drop": i.get("max_in_drop"),
                         "outfall": bool(i.get("outfall")), "ins": ins.get(n, []), "outs": outs_.get(n, []),
                         "edited": n in given["manholes"], "checks": chk})
    # the new manholes of the drawing (30 m spacing, bends): on the page too, so that the map and the DXF agree
    # the new manholes: put in before the zoning (spacing.presplit - real manholes of the design) and those planned
    # after it (trunk sewers, Table 3.31)
    # (their GL interpolated along the sewer, or the survey level given in the manhole table - user request 21-Oct-2026)
    new_mh = [{"label": n, "latlng": ll(xy[n]), "why": v["new_mh"], "conduit": v.get("on_conduit"),
               "gl": out["node_info"].get(n, {}).get("ground"), "invert": out["node_info"].get(n, {}).get("invert"),
               "gl_edited": "gl" in given["manholes"].get(n, {}),
               "depth": out["node_info"].get(n, {}).get("depth")}
              for n, v in net2["nodes"].items() if v.get("new_mh") and not v.get("cut_of") and n in xy]
    new_mh += [{"label": m["label"], "latlng": ll((m["x"], m["y"])), "why": m.get("why", "spacing"), "conduit": m["conduit"],
                "gl": m["ground"], "invert": m["invert"], "depth": m["depth"]}
               for m in out["new_mh"] if m.get("x") is not None]
    by_d = {}
    for d in res.values():
        by_d[d["D"]] = by_d.get(d["D"], 0.0) + (d["length"] or 0.0)
    deps = [x for d in res.values() for x in (d["depth_up"], d["depth_dn"]) if x is not None]
    pipe = zoning.priced_cost(res)[0] / 1e5
    summary = {"option": opt, "sewers": len(res), "length": round(sum(d["length"] or 0 for d in res.values()), 1),
               "new_manholes": len(new_mh),
               "new_manholes_bend": sum(1 for m in new_mh if str(m.get("why", "")).startswith("bend")),
               "grade": out["grade"], "max_depth": round(max(deps), 2) if deps else None,
               "pipe_lakh": round(pipe, 2), "by_diameter": [[D, round(L, 1)] for D, L in sorted(by_d.items())],
               "outfalls": net2["outfalls"]}
    sizes = [{"id_mm": z["id_mm"], "nominal": z.get("nominal")} for z in out["catalog"][2]]
    from .population import summary as pop_summary
    res = {"ok": True, "summary": summary, "sewers": sewers, "manholes": manholes, "new_manholes": new_mh,
           "forecast": pop_summary(inp["forecast"]) if inp.get("forecast") else "",
           "sizes": sizes, "edits": given,
           "rules": {"vmin": R.vmin, "ddmax": R.ddmax, "cover": round(R.cover, 3), "max_depth": R.max_depth,
                     "max_depth_project": R.max_depth_project, "vmin_init": R.vmin_init},
           "stages": _stage_roles(out["stages"], ev),
           "warnings": out["warnings"], "plan_lines": out["plan_lines"], "log": "\n".join(out["log"]),
           "warnings_hi": [hindi.hi(w) for w in out["warnings"]],          # for the page (user 30-Oct-2026)
           "files": {"report": xl, "dpr": xl_dpr, "plan_dxf": base + ".dxf", "lsection_dxf": base + "_Lsection.dxf"}}
    res.update(barrier_res(net, ll))
    _keep(stem, "design", res, dict(req, option=opt, edits=given))
    return res


def _stage_roles(stages, ev):
    """pipeline.stage_table with the role of each outfall in the zoning option (STP / pumping station)."""
    role = {zr["zone outlet"]: zr["role"] for zr in ev.get("zones") or []}
    for st in stages:
        for o in st["outfalls"]:
            o["role"] = role.get(o["outfall"], "outfall")
    return stages


def _sewer_checks(d, R, s_min, cov):
    """The manual rules a designed sewer breaks (pipe table of the page): velocity at the ultimate peak, Table 3.13
    slope, d/D, cover at both ends, depth (CPHEEO / project limit)."""
    out = []
    if d["q"] and R.vmin and (d["v"] is None or d["v"] < R.vmin - 1e-9):
        out.append(f"v < {R.vmin:g} m/s")
    if "v_init" in d and d["q"] and R.vmin_init and (d["v_init"] is None or d["v_init"] < R.vmin_init - 1e-9):
        out.append(f"v (base year) < {R.vmin_init:g} m/s")
    if s_min and d["slope"] < s_min * (1 - 1e-6):
        out.append("slope < Table 3.13")
    if d["q"] and (d.get("dd") is None or d["dd"] > R.ddmax + 1e-6):
        out.append(f"d/D > {R.ddmax:g}")
    if any(c is not None and c < R.cover - 0.005 for c in cov):
        out.append(f"cover < {R.cover:.2f} m")
    deps = [x for x in (d["depth_up"], d["depth_dn"]) if x is not None]
    if deps and R.max_depth is not None and max(deps) > R.max_depth + 1e-6:
        out.append(f"depth > {R.max_depth:g} m (CPHEEO)")
    if deps and R.max_depth_project and max(deps) > R.max_depth_project + 1e-6:
        out.append(f"depth > {R.max_depth_project:g} m (project)")
    return out
