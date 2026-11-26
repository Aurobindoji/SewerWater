"""Quantities and rates of a sewer by depth: the earthwork depth bands, the trench slices of a pipe and their quantities,
the SOR rates of sewer works (restructure stage 7, 15-Nov-2026: out of report.py, so that zoning need not import the
report)."""
import json
import math
import os
import re
from sewer_app import DATA_DIR


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
