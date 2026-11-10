"""Intze OHT drawings of a water design: a NEW OHT of the last design (capacity = its required capacity, staging =
the design's) is designed by intze.py and drawn by intze_dwg.py into <output>/<project>/intze/ - DXF, PDF and the
design / BBS xlsx (user decisions 9-Nov-2026: the full package, inside water_app). One tank at a time, by its own
button on the page (user decision 10-Nov-2026: not all at once, not with the DPR).

Page inputs (req "intze"): zone, sbc (NET bearing capacity, kN/m2), soil (I / II / III), vb (m/s), fck, fckf
(foundation, staircase), fy, depth (founding, m) and "per":
"OHT-1=120, OHT-3=80" - the SBC of single OHTs (the soil test of each site). Existing OHTs are not drawn (only
repaired in the DPR).
"""
import json
import os
import re
import threading
import time

from . import intze
from . import intze_dwg
from . import server as ui

HERE = os.path.dirname(os.path.abspath(__file__))
_LOCK = threading.Lock()


def _num(v, lo, hi):
    try:
        x = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return x if lo <= x <= hi else None


def settings(req):
    """(options for intze.design, {OHT name: SBC}) from the page's inputs; anything empty / out of range = default."""
    q = (req or {}).get("intze") or {}
    o = {}
    z = str(q.get("zone") or "").strip().upper()
    if z in intze.ZONE_Z:
        o["zone"] = z
    s = str(q.get("soil") or "").strip().upper()
    if s in ("I", "II", "III"):
        o["soil_type"] = s
    for key, name, lo, hi in (("sbc", "sbc_kn_m2", 30, 1000), ("vb", "wind_vb", 33, 55),
                              ("depth", "founding_depth_m", 1.0, 6.0)):
        x = _num(q.get(key), lo, hi)
        if x is not None:
            o[name] = x
    for key, name, lo, hi in (("fck", "fck", 25, 40), ("fckf", "fck_found", 20, 40), ("fy", "fy", 415, 550)):
        x = _num(q.get(key), lo, hi)
        if x is not None:
            o[name] = int(x)
    per = {}
    for part in re.split(r"[,;\n]+", str(q.get("per") or "")):
        if "=" in part:
            k, v = part.split("=", 1)
            x = _num(v, 30, 1000)
            if k.strip() and x is not None:
                per[k.strip()] = x
    return o, per


def swd_of(kl):
    """CPHEEO Table 2.7 S.No.12 maximum side water depth, as the DPR's pump head (dpr_water.json swd)."""
    with open(os.path.join(HERE, "dpr_water.json"), encoding="utf-8") as fh:
        table = json.load(fh)["swd"]["value"]
    return next(d for c, d in table if c is None or (kl or 0) <= c)


def targets(design):
    """The new OHTs of a design result: (name, capacity KL, staging m)."""
    out = []
    for o in design.get("outlets") or []:
        if o.get("existing"):
            continue
        cap = o.get("required_kl") or o.get("capacity_kl")
        if cap and o.get("staging_m"):
            out.append((o["name"], float(cap), float(o["staging_m"])))
    return out


def _safe(name):
    return re.sub(r'[<>:"/\\|?*\s]+', "_", str(name)).strip("_") or "OHT"


def _last_design(stem):
    """(the project's folder, its last design result) - ValueError without one."""
    folder = os.path.join(ui.out_root(), stem)
    f = os.path.join(folder, f"{stem}_wdesign_ui.json")
    if not os.path.isfile(f):
        raise ValueError("इस project का design नहीं है - पहले Design चलाएँ (no design of this project yet)")
    with open(f, encoding="utf-8") as fh:
        return folder, json.load(fh), os.path.getmtime(f)


def tanks(stem):
    """The new OHTs of the project's last design with their drawings' state (user decision 10-Nov-2026: a Design
    button for each tank on the page, not all at once): {ok, folder, ohts: [{name, capacity_kl, staging_m, made:
    "dd-mm-yyyy hh:mm" or "", stale: drawn before the last design, files}]}."""
    stem = ui.safe_name(stem)
    folder, design, t_design = _last_design(stem)
    out = os.path.join(folder, "intze")
    rows = []
    for name, cap, stg in targets(design):
        st = f"{stem}_{_safe(name)}_intze"
        files = {k: st + ext for k, ext in (("dxf", ".dxf"), ("pdf", ".pdf"), ("calc", "_calc.pdf"), ("xlsx", "_design.xlsx"))
                 if os.path.isfile(os.path.join(out, st + ext))}
        t = os.path.getmtime(os.path.join(out, st + ".dxf")) if "dxf" in files else None
        rows.append({"name": name, "capacity_kl": cap, "staging_m": stg, "files": files,
                     "made": time.strftime("%d-%m-%Y %H:%M", time.localtime(t)) if t else "",
                     "stale": bool(t and t < t_design)})
    return {"ok": True, "folder": out, "ohts": rows}


def export_all(stem, req=None, pdf=True, design=None, only=None):
    """Draw the new OHTs of the project's last design (or of the design result given) - only the one named `only`
    when given (the page's button of each tank, 10-Nov-2026). Returns {ok, folder, ohts: [...], log}."""
    stem = ui.safe_name(stem)
    folder = os.path.join(ui.out_root(), stem)
    if design is None:
        folder, design, _ = _last_design(stem)
    if req is None or not (req or {}).get("intze"):
        req = dict(req or {}, intze=(design.get("req") or {}).get("intze") or (req or {}).get("intze"))
    opts, per = settings(req)
    todo = targets(design)
    if not todo:
        raise ValueError("design में कोई नई OHT नहीं (no new OHT in the design) - पुरानी टंकियों की drawing नहीं बनती")
    if only:
        todo = [t for t in todo if t[0] == only]
        if not todo:
            raise ValueError(f"{only}: आख़िरी design में ऐसी नई OHT नहीं (no such new OHT in the last design)")
    out = os.path.join(folder, "intze")
    rows, log = [], []
    meta_scheme = str((req or {}).get("scheme") or "").strip()
    with _LOCK:
        for name, cap, stg in todo:
            o = dict(opts)
            if name in per:
                o["sbc_kn_m2"] = per[name]
            try:
                res = intze.design(cap, stg, swd_of(cap), o)
                paths = intze_dwg.export(res, out, f"{stem}_{_safe(name)}_intze", {"name": name, "scheme": meta_scheme},
                                         pdf=pdf)
            except Exception as e:                      # one OHT that fails does not stop the others
                log.append(f"{name}: {type(e).__name__}: {e}")
                continue
            conc, steel = intze.quantities(res)
            g = res["geo"]
            rows.append({"name": name, "capacity_kl": cap, "staging_m": stg, "D_m": round(g["D"], 2),
                         "columns": f"{g['n_col']} x {g['dc'] * 1000:.0f}", "raft_m": round(2 * g["Ro"], 2),
                         "concrete_m3": round(sum(conc.values()), 1), "steel_t": round(sum(steel.values()) / 1000, 2),
                         "sbc": res["opt"]["sbc_kn_m2"], "warnings": res["warnings"],
                         "files": {k: os.path.basename(v) for k, v in paths.items()}})
    return {"ok": bool(rows), "folder": out, "ohts": rows, "log": "\n".join(log)}
