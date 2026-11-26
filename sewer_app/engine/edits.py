"""The user's changes from the pipe / manhole tables of the map page (user request 19-Oct-2026), applied to a network
before zoning and design:

    edits = {"conduits": {label: {"D": mm, "slope": fraction}}, "manholes": {label: {"gl": m, "invert": m}},
             "trunk": [conduit label, ...]}
    net2, fixed_inv, notes = edits.apply(net, edits)

D / slope go on the conduit as force_D / force_slope (design.design_conduit takes them as given); gl replaces the
manhole's ground level (zoning too); invert is the outgoing invert at that manhole (Rules.fixed_inv). A label that
is not in the network is left out and named in notes.

trunk (user request 21-Oct-2026): the sewers marked on the page as trunk / outfall sewers with no house connections -
labels of the network's own conduits (before the new manholes cut them into pieces). They are not divided at the 30 m
spacing before the design; their spacing is that of CPHEEO Table 3.31 by the designed diameter (60 / 90 / 120 / 150 m,
p3-127) - see trunk_labels.
"""
import copy

GL_EDIT = "edited in the pipe / manhole table (user)"


def _num(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def clean(edits):
    """Only the known fields with a number; empty entries dropped; trunk: the labels, sorted."""
    out = {"conduits": {}, "manholes": {}, "trunk": sorted({str(x) for x in (edits or {}).get("trunk") or [] if str(x).strip()})}
    for kind, keys in (("conduits", ("D", "slope")), ("manholes", ("gl", "invert"))):
        for lab, e in ((edits or {}).get(kind) or {}).items():
            e2 = {k: _num((e or {}).get(k)) for k in keys}
            e2 = {k: v for k, v in e2.items() if v is not None and (k != "slope" or v > 0) and (k != "D" or v > 0)}
            if e2:
                out[kind][str(lab)] = e2
    return out


def trunk_labels(net, trunk):
    """The conduits of net that are trunk sewers: those marked, and the pieces cut from them (piece_of)."""
    t = {str(x) for x in trunk or []}
    return sorted(k["label"] for k in net["conduits"] if k["label"] in t or k.get("piece_of") in t)


def apply(net, edits):
    """(network with the edits, {manhole: invert}, notes)."""
    e = clean(edits)
    net2 = copy.deepcopy(net)
    notes = []
    by_label = {k["label"]: k for k in net2["conduits"]}
    for lab, x in e["conduits"].items():
        k = by_label.get(lab)
        if k is None:
            notes.append(f"edit ignored: conduit {lab} not in the network")
            continue
        k["force_D"], k["force_slope"] = x.get("D"), x.get("slope")
    fixed = {}
    for lab, x in e["manholes"].items():
        v = net2["nodes"].get(lab)
        if v is None:
            notes.append(f"edit ignored: manhole {lab} not in the network")
            continue
        if "gl" in x:
            v["ground"], v["gl_source"] = x["gl"], GL_EDIT
        if "invert" in x:
            fixed[lab] = x["invert"]
    return net2, fixed, notes
