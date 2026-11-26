"""dxf_inspect: ground-level and invert texts - numbers, their summary, each manhole's GL and IL."""
import re
import statistics
import collections
from .kinds import IL_MAX_DEPTH_M, IL_MIN_DEPTH_M, LEVEL_TAG, NUM, Z_TEXT_AGREE_M, classify
from .matching import match_to_nodes, pair_with_labels
from .spatial import Grid


def parse_number(s):
    """(prefix, number) from a label such as 'GL 82.350', 'IL=79.6', '82.350'; (None, None) if none."""
    s = (s or "").strip()
    k = classify(s)
    for kind, v in k:
        if kind in ("level", "invert", "dia", "slope_1in"):
            return kind.upper(), v
    if k and all(kind == "id" for kind, _ in k):
        return None, None
    m = NUM.search(s)
    if not m:
        return None, None
    try:
        v = float(m.group(0))
    except ValueError:
        return None, None
    prefix = s[:m.start()].strip(" :=-").upper()
    return prefix, v


def text_summary(texts):
    by = collections.defaultdict(list)
    for t in texts:
        by[t["layer"]].append(t)
    rows = []
    for lay, ts in sorted(by.items()):
        nums, prefixes, decs = [], collections.Counter(), 0
        kinds = collections.Counter(kd for t in ts for kd, _ in classify(t["text"]))
        for t in ts:
            pre, v = parse_number(t["text"])
            if v is None:
                continue
            nums.append(v)
            if pre:
                prefixes[pre[:8]] += 1
            if re.search(r"\d\.\d{2,3}\b", t["text"]):
                decs += 1
        nums.sort()
        med = nums[len(nums) // 2] if nums else None
        band = sum(1 for v in nums if med is not None and abs(v - med) <= 15) if nums else 0
        rows.append({"layer": lay, "n": len(ts), "numeric": len(nums), "decimal_2_3": decs,
                     "min": nums[0] if nums else None, "max": nums[-1] if nums else None, "median": med,
                     "within_15m_of_median": band, "prefixes": ", ".join(f"{k}({c})" for k, c in prefixes.most_common(5)),
                     "kinds": ", ".join(f"{k}:{c}" for k, c in kinds.most_common()),
                     "samples": " | ".join(t["text"][:25] for t in ts[:6])})
    return rows


def level_candidates(texts, min_n=5):
    """{layer: [(x, y, value), ...]} of level-like values (decimal numbers, 1-3 decimals) per layer,
    kept only when at least 80 % of them lie within 15 m of the layer median and the median is above
    10 (terrain levels, not pipe lengths or depths)."""
    by = collections.defaultdict(list)
    for t in texts:
        for kind, v in classify(t["text"]):
            if kind == "level":
                by[t["layer"]].append((t["x"], t["y"], v))
    out = {}
    for lay, vals in by.items():
        if len(vals) < min_n:
            continue
        vs = sorted(v for _, _, v in vals)
        med = vs[len(vs) // 2]
        if med > 10 and sum(1 for v in vs if abs(v - med) <= 15) >= 0.8 * len(vs):
            out[lay] = vals
    return out


def split_gl_il(nodes, texts, layers, radius):
    """SEWER (user request 22-Oct-2026: 'IL सदैव GL से कम'): texts of `layers` written without 'IL' (plain "84.12 m")
    near one manhole with two or more level values - name, GL, IL, depth at every manhole: the highest is its GL, the
    lower ones IL_MIN_DEPTH_M .. IL_MAX_DEPTH_M below it are its IL (a depth "3.64 m" is far lower: neither). Each
    text goes to its nearest manhole within radius. Only when the layer is drawn so - two values at at least half of
    its manholes (oakdale MH-: 251 of 7,183 manholes have a neighbour's GL text near too - no IL there). Returns the
    indexes of the IL texts."""
    g = Grid(max(radius, 1.0))
    for n in nodes:
        if n["deg"] > 0:
            g.add(n["x"], n["y"], n["id"])
    by = collections.defaultdict(list)
    for i, t in enumerate(texts):
        if t["layer"] not in layers:
            continue
        v = next((v for kind, v in classify(t["text"]) if kind == "level"), None)
        h = g.near(t["x"], t["y"], radius) if v is not None else None
        if h:
            by[h[0][3]].append((v, i))
    out = set()
    if sum(1 for vals in by.values() if len(vals) >= 2) < 0.5 * len(by):
        return out
    for vals in by.values():
        if len(vals) >= 2:
            top = max(v for v, _ in vals)
            out |= {i for v, i in vals if IL_MIN_DEPTH_M <= top - v <= IL_MAX_DEPTH_M}
    return out


def node_inverts(nodes, texts, il_layers, gl_layers, radius, gl_of, split=(), skip=()):
    """SEWER: the IL of each manhole from the drawing - the texts marked IL / INV on il_layers, the plain levels of an
    il_layer that is no GL layer, and the IL texts split_gl_il found - matched one to one to the manholes as the GLs
    (match_to_nodes). An IL not IL_MIN_DEPTH_M .. IL_MAX_DEPTH_M below the manhole's GL (gl_of) is not taken.
    skip: indexes of texts that are no level (the lengths of their pipes). Returns ({node: IL}, [(node, IL, GL) not
    taken])."""
    items = []
    for i, t in enumerate(texts):
        if i in skip or (t["layer"] not in il_layers and i not in split):
            continue
        for kind, v in classify(t["text"]):
            if kind == "invert" or (kind == "level" and (i in split or t["layer"] not in gl_layers)):
                items.append((t["x"], t["y"], v, t.get("h") or 0.0))
                break
    if not items:
        return {}, []
    got, _ = match_to_nodes(nodes, items, radius)
    il, bad = {}, []
    for nid, v in got.items():
        gl = gl_of.get(nid)
        if gl is None or IL_MIN_DEPTH_M <= gl - v <= IL_MAX_DEPTH_M:
            il[nid] = v
        else:
            bad.append((nid, v, gl))
    return il, bad


def node_levels(nodes, texts, inserts, level_layers, radius, anchors=None, pass2_labels=(), z_mode="auto"):
    """Ground level per node from (in this order - water and sewer, 22-Oct-2026): block attributes, the GL text paired with the
    manhole's label (anchors - see pair_with_labels) or the nearest numeric text, Z of line ends (only when Z agrees
    with the GL texts). z_mode (the user's choice on the page, 22-Oct-2026): "auto" as said; "first" - Z of the line
    ends before all else, whether it agrees or not (the texts where there is no Z); "off" - Z not at all."""
    used = [n for n in nodes if n["deg"] > 0]
    res = {"z": 0, "attr": 0, "text": 0, "none": 0}
    # Z
    zs = [z for n in used for z in n["z"]]
    z_useful = zs and (max(zs) - min(zs) > 0.01) and sum(1 for z in zs if abs(z) > 0.001) > 0.5 * len(zs)
    # attributes
    ag = Grid(max(radius, 1.0))
    for i, b in enumerate(inserts):
        for tag, val in b["attrs"].items():
            if LEVEL_TAG.match(tag):
                _, v = parse_number(val)
                if v is not None:
                    ag.add(b["x"], b["y"], v)
                    break
    items = [(t["x"], t["y"], v, t.get("h") or 0.0) for t in texts if t["layer"] in level_layers
             for kind, v in classify(t["text"]) if kind == "level"]
    paired, pidx, pinfo = pair_with_labels(items, anchors or {}, set(pass2_labels))
    rest = [it for k, it in enumerate(items) if k not in set(pidx.values())]
    free_nodes = [dict(n, deg=0) if n["id"] in paired else n for n in nodes]
    tmatch, tinfo = match_to_nodes(free_nodes, rest, radius) if rest else ({}, {})
    tinfo = dict(tinfo or {"pass2": set(), "pass2_n": 0, "pass1": 0, "matched": 0, "texts_unused": 0, "offsets": [],
                           "offset_samples": 0, "unused_offsets": []})
    # a GL paired with a label matched only in pass 2 is as uncertain as that label
    p2 = set(tinfo.get("pass2", set())) | {n for n in paired if n in set(pass2_labels)}
    tinfo.update({"texts": len(items), "paired": len(paired), "matched": tinfo.get("matched", 0) + len(paired),
                  "pass1": tinfo.get("pass1", 0) + sum(1 for n in paired if n not in p2), "pass2": p2,
                  "pass2_n": len(p2), **pinfo})
    tmatch = {**tmatch, **paired}
    # (user request 22-Oct-2026 - water, then sewer - chit5: every GL taken from the lines' Z - 74.533, -4.617, 26.8 - though the
    # node layer has its GL texts): the drawing's GL first - a block attribute, else the GL text - and Z of the line
    # ends only where there is none, and only when Z is the ground: at the nodes having both, Z within Z_TEXT_AGREE_M
    # of the GL text (median). A Z far from the texts (a polyline's elevation, not a level) is not used at all.
    zt = [abs(max(n["z"]) - tmatch[n["id"]]) for n in used
          if n["id"] in tmatch and any(abs(z) > 0.001 for z in n["z"])]
    z_off = statistics.median(zt) if zt else None
    if z_mode == "off":
        z_useful = False
    elif z_mode == "first":
        z_useful = any(abs(z) > 0.001 for z in zs)
    elif z_useful and z_off is not None and z_off > Z_TEXT_AGREE_M:
        z_useful = False
        tinfo["z_ignored"] = (f"Z of the lines not used: {statistics.median(zt):.2f} m from the GL texts (median of "
                              f"{len(zt)} nodes having both) - a line's elevation, not the ground")
    node_levels.info = tinfo
    per_node = {}
    for n in used:
        if z_mode == "first" and z_useful and any(abs(z) > 0.001 for z in n["z"]):
            per_node[n["id"]] = ("Z", max(n["z"]))
            res["z"] += 1
            continue
        h = ag.near(n["x"], n["y"], radius)
        if h:
            per_node[n["id"]] = ("attribute", h[0][3])
            res["attr"] += 1
            continue
        if n["id"] in tmatch:
            per_node[n["id"]] = ("text", tmatch[n["id"]])
            res["text"] += 1
            continue
        if z_useful and any(abs(z) > 0.001 for z in n["z"]):
            per_node[n["id"]] = ("Z", max(n["z"]))
            res["z"] += 1
            continue
        per_node[n["id"]] = (None, None)
        res["none"] += 1
    return res, per_node, bool(z_useful)
