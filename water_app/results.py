"""The results of a project kept on disk: the last zoning / design (with the network they were made on), the DPR
written on Export DPR from the data the design keeps, the rate xlsx, the design's Excel report and the technical
statement's data (restructure stage 2, 15-Nov-2026: out of ui_api.py)."""
import collections
import json
import os
import pickle
import time
from . import project as ui
from . import design as wd
from . import dpr as wdpr
from .wards import _town_list, ward_table


def _keep(stem, kind, res, req):
    folder = os.path.join(ui.out_root(), stem)
    os.makedirs(folder, exist_ok=True)
    keep = dict(res, req={k: req.get(k) for k in ("ohts", "pop_factor", "persons_per_connection", "floating_pct", "oht_inflow", "near_m", "tw_standby", "sug",
                                                  "pop_total", "edits", "barriers", "loops", "crossings", "wards", "bulk",
                                                  "projection", "ward_table", "load_by", "peak", "simulate", "fire_lps", "cons",
                                                  "fire_min_m")
                          + ui.STAGE_KEYS},
                time=time.strftime("%d-%m-%Y %H:%M"), net_rev=ui.net_rev(stem))
    with open(os.path.join(folder, f"{stem}_w{kind}_ui.json"), "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, separators=(",", ":"))
    if kind == "zoning":
        for f in (f"{stem}_wdesign_ui.json", f"{stem}_wdesign_dpr.pkl"):
            try:
                os.remove(os.path.join(folder, f))
            except OSError:
                pass


def dpr_file(stem, open_it=True):
    """The DPR workbook of the project's last design - written here, on the Export DPR button, from the data the design
    kept (_keep_dpr; user 15-Nov-2026: not with every design), once per design (a second click opens the same file) -
    and opened in its program (Excel) on this PC when asked. Raises ValueError when there is no design."""
    from . import rates
    r = last_results(stem).get("design") or {}
    path = (r.get("files") or {}).get("dpr")
    stamp = rates.stamp()                       # rates imported / reset since that DPR: written again with them
    if not path or not os.path.isfile(path) or (r.get("files") or {}).get("dpr_rates", "") != stamp:
        folder = os.path.join(ui.out_root(), stem)
        try:
            with open(_dpr_data(folder, stem), "rb") as fh:
                info = pickle.load(fh)
        except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ImportError):
            raise ValueError("DPR का data नहीं मिला - पहले Design चलाएँ / no DPR data: run the Design first") from None
        path = _dpr(folder, stem, info)
        f = os.path.join(folder, f"{stem}_wdesign_ui.json")            # the design remembers its DPR
        with open(f, encoding="utf-8") as fh:
            keep = json.load(fh)
        keep.setdefault("files", {}).update(dpr=path, dpr_rates=stamp)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(keep, fh, ensure_ascii=False, separators=(",", ":"))
    if open_it and hasattr(os, "startfile"):
        try:
            os.startfile(path)
        except OSError:
            open_it = False                             # no program for .xlsx: the path is told
    return {"ok": True, "path": path, "folder": os.path.dirname(path), "opened": bool(open_it),
            "time": r.get("time"), "stale": bool(r.get("stale"))}


def rate_export(stem, open_it=True):
    """Export rate xlsx (user decisions 15-Nov-2026): the SOR and the UPJN rates the DPR takes, the user's imported
    ones in place, in the project's folder; yellow = the rates the DPR of the project's last design uses (no design:
    none yellow, told). Opened in Excel when asked."""
    from . import rates
    folder = os.path.join(ui.out_root(), stem)
    use, note = None, ""
    try:
        with open(_dpr_data(folder, stem), "rb") as fh:
            info = pickle.load(fh)
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ImportError):
        info = None
    if info is not None:
        from .dpr.usage import used
        use = used(info)
        r = last_results(stem).get("design") or {}
        note = f"Design {r.get('time') or ''} ({stem})"
    else:
        note = "इस project का Design नहीं - कोई पीला नहीं / no design of this project: none yellow"
    out = rates.export_xlsx(os.path.join(folder, f"{stem}_rates_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"), use, note)
    if open_it and hasattr(os, "startfile"):
        try:
            os.startfile(out["path"])
        except OSError:
            open_it = False
    return dict(out, ok=True, folder=folder, opened=bool(open_it), design=info is not None, status=rates.status())


def last_results(stem):
    """As the sewer server's last_results: network_saved = there is a network to zone; a result of another state of the
    network than the one now is 'stale'."""
    folder, f_mh, _, _ = ui.paths(stem)
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


def _dpr_info(stem, res, z, crit, req, wnet=None, net=None):
    """What the DPR workbook (format of the Elmwood estimate, dpr.py, user decision 26-Oct-2026) needs from a design -
    kept with the design (_keep_dpr), the workbook written only on Export DPR (dpr_file, user 15-Nov-2026)."""
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
    return info


def _dpr_data(folder, stem):
    return os.path.join(folder, f"{stem}_wdesign_dpr.pkl")


def _keep_dpr(folder, stem, info):
    with open(_dpr_data(folder, stem), "wb") as fh:
        pickle.dump(info, fh, protocol=pickle.HIGHEST_PROTOCOL)


def _dpr(folder, stem, info):
    """The DPR workbook next to the design report; the Project texts of the previous DPR of the project are kept."""
    prev = wdpr.previous_dpr(folder, stem)
    path = os.path.join(folder, f"{stem}_water_design_{time.strftime('%Y%m%d_%H%M%S')}_DPR.xlsx")
    return wdpr.write_dpr(info, path, previous=prev)


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
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter
    wb = Workbook(write_only=True)          # streamed to the file (17-Nov-2026: a 12,000-pipe design, a tenth faster)

    def sheet(title):
        w = wb.create_sheet(title)
        for k in range(1, 20):
            w.column_dimensions[get_column_letter(k)].width = 16
        return w
    ws = sheet("Summary")
    a1 = WriteOnlyCell(ws, "Water distribution network design (PFR) - " + stem)
    a1.font = Font(bold=True, size=13)
    ws.append([a1])
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
    ws2 = sheet("Zones")
    ws2.append(["OZ (OHT)", "OHT", "population", "connections", "demand KLD", "OHT capacity KL (existing)",
                "required KL (max 33 % / mass balance)", "staging m", "staging", "VFD pump head m", "VFD pump kW", "CWR KL", "tube wells",
                "tube wells new (+15 years)", "standby tube wells (CPHEEO 5.7.5 / the page's table)", "rebored tube wells",
                "DMAs", "GL min", "GL max"])
    for x in z["zones"]:
        o = next((o for o in res["outlets"] if o["name"] == x["name"]), {})
        ws2.append([x["name"], "proposed (new)" if o.get("proposed") else "existing" if x["existing"] else "new",
                    x["population"], x["connections"], x["demand_kld"], x["capacity_kl"], x["required_kl"],
                    o.get("staging_m"), "found by the design" if o.get("staging_auto") else "given",
                    o.get("vfd_head_m"), o.get("vfd_kw"), x["cwr_kl"],
                    x["tubewells"], x.get("tubewells_new"), x.get("tubewells_standby"), x.get("rebore"),
                    x.get("dma_count"), x["elev_min"], x["elev_max"]])
    ws3 = sheet("DMAs")
    ws3.append(["DMA", "OZ", "population", "connections", "inlet pipe"])
    for d in z["dmas"]:
        ws3.append([d["name"], d["zone"], d["population"], d["connections"], d["inlet_pipe"] or "(at the OHT)"])
    ws4 = sheet("Pipes")
    ws4.append(["pipe", "from", "to", "length m", "size", "internal dia mm", "closed", "peak flow L/s", "velocity m/s",
                "head loss m/km", "OZ", "DMA"])
    for p in res["pipes"]:
        ws4.append([p["label"], p["from"], p["to"], p["length"], p["size"], p["id_mm"], "yes" if p["closed"] else "",
                    p["flow"], p["v"], p["hl_km"], p["oz"], p["dma"]])
    ws5 = sheet("Nodes")
    ws5.append(["node", "GL m", "HGL m", "residual head m", "peak demand L/s", "OZ", "DMA"])
    for n in res["nodes"]:
        ws5.append([n["label"], n["gl"], n["head"], n["p"], n["q"], n["oz"], n["dma"]])
    if res.get("stages"):
        ws6 = sheet("Stages")
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
    path = os.path.join(folder, f"{stem}_water_design_{time.strftime('%Y%m%d_%H%M')}.xlsx")
    wb.save(path)
    return path
