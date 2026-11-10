"""Sewer network as plain Python data - replaces the SewerGEMS model of the original scripts.

    net = read_extract_csv(manholes_csv, conduits_csv, outfalls=["O-1"])
    data, ground, xy = design_inputs(net)          # the shapes design.py / flows.py work on

Network dict:
    nodes     {label: {"ground": m or None, "xy": (x, y) or None, "gl_source": str}}
    conduits  [{"label", "start_node", "stop_node", "length_m", "vertices": [(x, y), ...]}]  (as drawn)
    outfalls  [labels]  - nodes where the sewer leaves the network (STP, pumping station, existing sewer)

The CSV files are those of dxf_extract.py (manholes: Label, X, Y, GL[, GL_source];
conduits: Label, From, To, Length_m, Vertices "x y;x y;...").
set_flow_direction is unchanged from the original scripts openflows_lib.py; parts_without_outfall and
duplicate_labels are the sewer_design.py checks, rewritten for this data.
"""
import collections
import csv
import math

from . import DesignError


def _num(s):
    s = (s or "").strip()
    return float(s) if s else None


def polyline_length(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def from_rows(mh_rows, co_rows, outfalls=()):
    """Network from dxf_extract rows (manholes: Label, X, Y, GL, GL_source; conduits: Label, From, To, Length_m,
    Vertices) - as read from its CSV files (strings) or straight from dxf_extract.extract (numbers)."""
    def num(v):
        return _num(v) if isinstance(v, str) or v is None else float(v)
    nodes = {}
    for r in mh_rows:
        try:
            xy = (float(r["X"]), float(r["Y"]))
        except (ValueError, KeyError, TypeError):
            xy = None
        nodes[str(r["Label"]).strip()] = {"ground": num(r.get("GL")), "xy": xy,
                                          "gl_source": str(r.get("GL_source") or "").strip()}
        if num(r.get("IL")) is not None:               # the drawing's invert level (sewer, 22-Oct-2026)
            nodes[str(r["Label"]).strip()]["invert_drawing"] = num(r.get("IL"))
    conduits = []
    for r in co_rows:
        pts = []
        for v in str(r.get("Vertices") or "").split(";"):
            p = v.split()
            if len(p) == 2:
                pts.append((float(p[0]), float(p[1])))
        L = num(r.get("Length_m"))
        if not L and len(pts) > 1:
            L = polyline_length(pts)
        conduits.append({"label": str(r["Label"]).strip(), "start_node": str(r["From"]).strip(),
                         "stop_node": str(r["To"]).strip(), "length_m": L, "vertices": pts})
    return {"nodes": nodes, "conduits": conduits, "outfalls": list(outfalls)}


def from_extract(ex, outfalls=()):
    """Network straight from dxf_extract.extract(...)."""
    return from_rows(ex["mh_rows"], ex["co_rows"], outfalls)


def write_csv(net, mh_csv, co_csv):
    """The network as the two dxf_extract CSV files (readable again with read_extract_csv / --csv)."""
    with open(mh_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Label", "X", "Y", "GL", "GL_source", "IL"])
        for n, v in net["nodes"].items():
            xy = v.get("xy") or (None, None)
            w.writerow([n, None if xy[0] is None else round(xy[0], 3), None if xy[1] is None else round(xy[1], 3),
                        None if v.get("ground") is None else round(v["ground"], 3), v.get("gl_source") or "",
                        None if v.get("invert_drawing") is None else round(v["invert_drawing"], 3)])
    with open(co_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Label", "From", "To", "Length_m", "Vertices"])
        for k in net["conduits"]:
            w.writerow([k["label"], k["start_node"], k["stop_node"], round(k["length_m"] or 0.0, 3),
                        ";".join(f"{p[0]:.3f} {p[1]:.3f}" for p in k.get("vertices") or [])])
    return mh_csv, co_csv


def read_extract_csv(mh_csv, co_csv, outfalls=()):
    with open(mh_csv, newline="", encoding="utf-8-sig") as fh:
        mh_rows = list(csv.DictReader(fh))
    with open(co_csv, newline="", encoding="utf-8-sig") as fh:
        co_rows = list(csv.DictReader(fh))
    return from_rows(mh_rows, co_rows, outfalls)


def set_flow_direction(conds, outfalls):
    """Sets k['to_outfall'] by walking the network outwards from the outfall labels."""
    adj = {}
    for k in conds:
        adj.setdefault(k["start_node"], []).append(k)
        adj.setdefault(k["stop_node"], []).append(k)
    seen, used, queue = set(outfalls), set(), list(outfalls)
    for k in conds:
        k["to_outfall"] = None
    while queue:
        nd = queue.pop(0)
        for k in adj.get(nd, []):
            if id(k) in used:
                continue
            other = k["start_node"] if k["stop_node"] == nd else k["stop_node"]
            if other in seen:
                continue                                 # loop edge: leave None
            used.add(id(k))
            k["to_outfall"] = (k["stop_node"] == nd)     # flows from 'other' towards nd
            seen.add(other)
            queue.append(other)


def duplicate_labels(net):
    """{"conduits": {label: n}, "nodes": {}} for labels used more than once (the design keys by label)."""
    cnt = collections.Counter(k["label"] for k in net["conduits"])
    return {"conduits": {k: n for k, n in cnt.items() if n > 1}, "nodes": {}}


def parts_without_outfall(net):
    """Connected parts of the network that hold no outfall: [sorted node labels of each part]."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for k in net["conduits"]:
        parent[find(k["start_node"])] = find(k["stop_node"])
    outs = set(net["outfalls"])
    groups = collections.defaultdict(list)
    for n in list(parent):
        groups[find(n)].append(n)
    bad = [sorted(g) for g in groups.values() if not (set(g) & outs)]
    bad.sort(key=len)
    return bad


def validate(net):
    """Problems that stop a design, as a list of text lines (empty = fine)."""
    out = []
    dup = duplicate_labels(net)["conduits"]
    if dup:
        out.append("conduit label used more than once: " + ", ".join(f"{k} x{n}" for k, n in sorted(dup.items())[:30]))
    unknown = sorted({n for k in net["conduits"] for n in (k["start_node"], k["stop_node"])} - set(net["nodes"]))
    if unknown:
        out.append("conduit end that is not a node: " + ", ".join(unknown[:30]))
    missing_out = [o for o in net["outfalls"] if o not in net["nodes"]]
    if missing_out:
        out.append("outfall that is not a node: " + ", ".join(missing_out))
    for g in parts_without_outfall(net):
        low = sorted((net["nodes"][n]["ground"], n) for n in g
                     if n in net["nodes"] and net["nodes"][n]["ground"] is not None)[:5]
        out.append(f"part with NO outfall ({len(g)} nodes: {', '.join(g[:8])}{' ...' if len(g) > 8 else ''})"
                   + (" - lowest ground: " + ", ".join(f"{n} ({v:.2f})" for v, n in low) if low else ""))
    return out


def design_inputs(net, check=True):
    """(data, ground, xy) in the shapes the design functions use. data = {"conduits": [...],
    "outfalls": [...]}; each conduit gets flow_lps 0, n None (catalog n is used) and to_outfall."""
    if check:
        bad = validate(net)
        if bad:
            raise DesignError("network problems:\n   " + "\n   ".join(bad))
    conds = [{"label": k["label"], "start_node": k["start_node"], "stop_node": k["stop_node"],
              "length_m": k["length_m"], "flow_lps": 0.0, "n": None,
              "up_invert_m": None, "dn_invert_m": None,
              "force_D": k.get("force_D"), "force_slope": k.get("force_slope")} for k in net["conduits"]]
    set_flow_direction(conds, net["outfalls"])
    ground = {n: v["ground"] for n, v in net["nodes"].items() if v["ground"] is not None}
    xy = {n: v["xy"] for n, v in net["nodes"].items() if v["xy"] is not None}
    return {"conduits": conds, "outfalls": list(net["outfalls"])}, ground, xy
