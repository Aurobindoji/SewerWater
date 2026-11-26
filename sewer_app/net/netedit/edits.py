"""netedit: the user's corrections from the page, each logged, one undo step a list."""
import json
import math
import re
import time
from sewer_app.core.spacing import label_namer
from .common import GL_TYPES, LABEL_TYPES, SUGGESTED, USER_GL, _UNDO
from .coords import converters
from .files import store
from .problems import _connected, _key
from .suggest import label_levels, suggestions


def _apply_suggestion(st, n, s, tn, tc):
    nodes = st["net"]["nodes"]
    if s["label"] in nodes:
        raise ValueError(f"'{s['label']}' नाम का manhole पहले से है")
    _apply1(st, {"op": "rename", "mh": n, "to": s["label"]}, tn, tc)
    st["edits"][-1]["change"] = "label (suggested)"
    st["edits"][-1]["detail"] += f" (drawing label {s['d']:.1f} m from the symbol)"
    v = nodes[s["label"]]
    det = f"{s['d']:.1f} m from the symbol"
    guessed = v.get("ground") is None or "interpolated" in (v.get("gl_source") or "")
    if s.get("gl") and guessed:                       # the drawing's level beats a level interpolated by repair
        old = v.get("ground")
        v["ground"] = s["gl"]["value"]
        v["gl_source"] = "text next to the suggested label - check"
        _log(st, "GL (suggested)", s["label"], f"{'-' if old is None else f'{old} (interpolated)'} -> {v['ground']}")
        det += f"; GL {v['ground']} (text next to the label)"
    st["ex_issues"].append({"type": SUGGESTED, "item": s["label"], "x": v["xy"][0], "y": v["xy"][1], "detail": det})


# ---------------------------------------------------------------- edits
def _plen(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _snapshot(st):
    _UNDO[st["stem"]].append(json.dumps({"net": st["net"], "reviewed": st["reviewed"], "ex_issues": st["ex_issues"],
                                         "edits": st["edits"], "next_id": st["next_id"], "epsg": st.get("epsg"),
                                         "shift": st.get("shift"), "origin": st.get("origin")}, separators=(",", ":")))


def place(st, frm, to, points=()):
    """The whole network moved on the map: the drawing's point now shown at frm (lat, lon) goes to `to` - a shift in
    metres (a drawing in local coordinates: placed in the UTM zone of `to`). Lengths and levels unchanged. One undo
    step. Returns `points` (lat, lon - e.g. OHTs placed on the network) moved with it."""
    from sewer_app.core import geo
    to_xy = converters(st)[1]
    raw = to_xy([frm])[0]
    pts = to_xy(list(points))
    _snapshot(st)
    epsg = st.get("epsg") or geo.utm_epsg(to[1], to[0])
    st["epsg"], st["shift"] = int(epsg), [0.0, 0.0]
    t = converters(st)[1]([to])[0]                     # the place in the EPSG's metres
    st["shift"] = [round(t[0] - raw[0], 3), round(t[1] - raw[1], 3)]
    _log(st, "placed on the map", "network", f"EPSG {st['epsg']}, drawing shifted {st['shift'][0]:+.1f} m E, "
                                             f"{st['shift'][1]:+.1f} m N")
    store(st)
    return converters(st)[0](pts)


def undo(st):
    if not _UNDO[st["stem"]]:
        raise ValueError("पीछे जाने को कुछ नहीं")
    st.update(json.loads(_UNDO[st["stem"]].pop()))
    store(st)


def _log(st, op, item, detail=""):
    st["edits"].append({"time": time.strftime("%d-%m-%Y %H:%M:%S"), "change": op, "item": item, "detail": detail})


def _review(st, mh, types):
    rev = set(st["reviewed"])
    for i in st["ex_issues"]:
        if i["type"] in types and str(i["item"]) == mh:
            rev.add(_key(i))
    st["reviewed"] = sorted(rev)


def apply(st, ops):
    """Corrections from the page, in order; one undo step for the whole list. Returns (touched node labels,
    touched conduit ids). Raises ValueError (nothing changed) when an operation is not possible."""
    _snapshot(st)
    tn, tc = set(), set()
    try:
        for op in ops:
            _apply1(st, op, tn, tc)
    except Exception:
        st.update(json.loads(_UNDO[st["stem"]].pop()))           # back to the state before this list
        raise
    store(st)
    return tn, tc


def _ctx(st, *want):
    """What an operation of _apply1 works on, by name: net, nodes, conds (the sewers), by_id, need_mh(n) (the manhole or
    ValueError), attached(n) (its pipes)."""
    net = st["net"]
    nodes, conds = net["nodes"], net["conduits"]

    def need_mh(n):
        if n not in nodes:
            raise ValueError(f"manhole '{n}' नहीं है")
        return nodes[n]

    def attached(n):
        return [k for k in conds if n in (k["start_node"], k["stop_node"])]

    have = {"net": net, "nodes": nodes, "conds": conds, "need_mh": need_mh, "attached": attached}
    if "by_id" in want:
        have["by_id"] = {k["id"]: k for k in conds}
    got = tuple(have[w] for w in want)
    return got[0] if len(got) == 1 else got


def _op_set_gl(st, op, tn, tc):
    need_mh = _ctx(st, "need_mh")
    mh = op["mh"]
    v = need_mh(mh)
    old = v.get("ground")
    g = op.get("gl")
    v["ground"] = None if g in (None, "") else round(float(g), 3)
    v["gl_source"] = USER_GL if v["ground"] is not None else ""
    _review(st, mh, GL_TYPES)
    _log(st, "GL", mh, f"{old if old is not None else '-'} -> {v['ground'] if v['ground'] is not None else '-'}")
    tn.add(mh)


def _op_rename_prefix(st, op, tn, tc):
    # the names of a network imported before, to another prefix at once (user request 30-Oct-2026): every
    # junction (kind "node") / pipe ("pipe") label <from><digit>... -> <to><digit>...; a new name already taken
    # by another: nothing changes
    net, nodes, conds = _ctx(st, "net", "nodes", "conds")
    old, new, what = str(op.get("from") or ""), str(op.get("to") or "").strip(), op.get("kind")
    if what not in ("node", "pipe") or not old or not new or new == old:
        return
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_/-]{0,7}", new):
        raise ValueError(f"prefix '{new}' नहीं चलेगा: अक्षर से शुरू, 8 तक अक्षर / अंक / - _ /")
    rx = re.compile(re.escape(old) + r"(?=\d)")
    labels = list(nodes) if what == "node" else [k["label"] for k in conds]
    ren = {x: new + x[len(old):] for x in labels if rx.match(x)}
    if not ren:
        raise ValueError(f"'{old}' से शुरू होने वाला कोई नाम नहीं")
    clash = (set(ren.values()) & (set(labels) - set(ren))) or (len(set(ren.values())) < len(ren))
    if clash:
        raise ValueError(f"नए नामों में से कुछ पहले से हैं (जैसे {sorted(set(ren.values()) & set(labels))[:3]}) - कुछ नहीं बदला")
    if what == "node":
        net["nodes"] = {ren.get(n, n): v for n, v in nodes.items()}
        for k in conds:
            k["start_node"], k["stop_node"] = ren.get(k["start_node"], k["start_node"]), ren.get(k["stop_node"], k["stop_node"])
        net["outfalls"] = [ren.get(o, o) for o in net["outfalls"]]
        tn.update(ren)
        tn.update(ren.values())
        tc.update(k["id"] for k in conds)
    else:
        for k in conds:
            if k["label"] in ren:
                k["label"] = ren[k["label"]]
                tc.add(k["id"])
    # the drawing's problems and the ones marked as checked: by the new names
    ks = {}
    for i in st["ex_issues"]:
        parts = [x.strip() for x in str(i["item"]).split(" - ")]
        item = " - ".join(ren.get(x, x) for x in parts)
        if item != str(i["item"]):
            ks[_key(i)] = f"{i['type']}|{item}"
            i["item"] = item
    st["reviewed"] = [ks.get(r, r) for r in st["reviewed"]]
    pre = dict(st.get("prefix") or {})
    if new == {"node": "MH-", "pipe": "CO-"}[what]:
        pre.pop(what, None)
    else:
        pre[what] = new
    st["prefix"] = pre
    _log(st, "names", f"{old}* -> {new}*", f"{len(ren)} {'junction' if what == 'node' else 'pipe'} names")


def _op_rename(st, op, tn, tc):
    net, nodes, need_mh, attached = _ctx(st, "net", "nodes", "need_mh", "attached")
    old, new = op["mh"], str(op["to"]).strip()
    need_mh(old)
    if not new or new == old:
        return
    if new in nodes:
        raise ValueError(f"'{new}' नाम का manhole पहले से है")
    nodes[new] = nodes.pop(old)
    for k in attached(old):
        for end in ("start_node", "stop_node"):
            if k[end] == old:
                k[end] = new
        tc.add(k["id"])
    net["outfalls"] = [new if o == old else o for o in net["outfalls"]]
    for i in st["ex_issues"]:
        if i["type"] == "near-miss gap":
            i["item"] = " - ".join(new if p.strip() == old else p.strip() for p in str(i["item"]).split(" - "))
        elif str(i["item"]) == old:
            i["item"] = new
    st["reviewed"] = [r.replace(f"|{old}", f"|{new}") if r.endswith(f"|{old}") else r for r in st["reviewed"]]
    _review(st, new, LABEL_TYPES)
    _log(st, "label", old, f"-> {new}")
    tn.update([old, new])


def _op_outfall(st, op, tn, tc):
    net, need_mh = _ctx(st, "net", "need_mh")
    mh = op["mh"]
    need_mh(mh)
    on = bool(op.get("on"))
    net["outfalls"] = [o for o in net["outfalls"] if o != mh] + ([mh] if on else [])
    _log(st, "outfall", mh, "set" if on else "removed")
    tn.add(mh)


def _op_delete_conduit(st, op, tn, tc):
    conds, by_id = _ctx(st, "conds", "by_id")
    k = by_id.get(int(op["id"]))
    if k is None:
        raise ValueError("sewer नहीं मिला")
    conds.remove(k)
    _log(st, "sewer deleted", k["label"], f"{k['start_node']} - {k['stop_node']}, {k['length_m'] or 0:.1f} m")
    tc.add(k["id"])
    tn.update([k["start_node"], k["stop_node"]])


def _op_delete_mh(st, op, tn, tc):
    net, nodes, conds, need_mh, attached = _ctx(st, "net", "nodes", "conds", "need_mh", "attached")
    mh = op["mh"]
    need_mh(mh)
    gone = attached(mh)
    for k in gone:
        conds.remove(k)
        tc.add(k["id"])
        tn.update([k["start_node"], k["stop_node"]])
    del nodes[mh]
    net["outfalls"] = [o for o in net["outfalls"] if o != mh]
    _log(st, "manhole deleted", mh, f"with {len(gone)} sewer(s): {', '.join(k['label'] for k in gone)}")
    tn.add(mh)


def _op_connect(st, op, tn, tc):
    net, conds, need_mh = _ctx(st, "net", "conds", "need_mh")
    a, b = op["a"], op["b"]
    pa, pb = need_mh(a)["xy"], need_mh(b)["xy"]
    if a == b:
        raise ValueError("एक ही manhole")
    if _connected(net, a, b):
        raise ValueError(f"{a} और {b} पहले से जुड़े हैं")
    lab = str(op.get("label") or "").strip() or label_namer([k["label"] for k in conds], (st.get("prefix") or {}).get("pipe", "CO-"))()
    k = {"label": lab, "start_node": a, "stop_node": b, "length_m": round(math.dist(pa, pb), 3),
         "vertices": [list(pa), list(pb)], "id": st["next_id"]}
    st["next_id"] += 1
    conds.append(k)
    _log(st, "sewer added", lab, f"{a} - {b}, {k['length_m']:.1f} m (straight)")
    tc.add(k["id"])
    tn.update([a, b])


def _op_merge(st, op, tn, tc):
    net, nodes, conds, need_mh, attached = _ctx(st, "net", "nodes", "conds", "need_mh", "attached")
    keep, drop = op["keep"], op["drop"]
    vk, vd = need_mh(keep), need_mh(drop)
    if keep == drop:
        raise ValueError("एक ही manhole")
    for k in attached(drop):
        tc.add(k["id"])
        if keep in (k["start_node"], k["stop_node"]):
            conds.remove(k)                                  # the sewer between the two: gone
            continue
        for end, vi in (("start_node", 0), ("stop_node", -1)):
            if k[end] == drop:
                k[end] = keep
                if k["vertices"]:
                    k["vertices"][vi] = list(vk["xy"])
        k["length_m"] = round(_plen(k["vertices"]), 3) if len(k["vertices"]) > 1 else k["length_m"]
        tn.update([k["start_node"], k["stop_node"]])
    if vk.get("ground") is None and vd.get("ground") is not None:
        vk["ground"], vk["gl_source"] = vd["ground"], vd.get("gl_source") or ""
    if drop in net["outfalls"] and keep not in net["outfalls"]:
        net["outfalls"].append(keep)
    net["outfalls"] = [o for o in net["outfalls"] if o != drop]
    del nodes[drop]
    _log(st, "manholes merged", drop, f"into {keep} ({math.dist(vk['xy'], vd['xy']):.2f} m apart)")
    tn.update([keep, drop])


def _op_split(st, op, tn, tc):
    nodes, conds, by_id = _ctx(st, "nodes", "conds", "by_id")
    k = by_id.get(int(op["id"]))
    if k is None:
        raise ValueError("sewer नहीं मिला")
    p = converters(st)[1]([op["latlng"]])[0]
    P = k["vertices"] if len(k["vertices"]) > 1 else [nodes[k["start_node"]]["xy"], nodes[k["stop_node"]]["xy"]]
    best = None
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if not L2 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        q = [a[0] + t * dx, a[1] + t * dy]
        d = math.dist(p, q)
        if best is None or d < best[0]:
            best = (d, i, q)
    _, i, q = best
    first, second = [list(x) for x in P[:i + 1]] + [q], [q] + [list(x) for x in P[i + 1:]]
    if _plen(first) < 0.05 or _plen(second) < 0.05:
        raise ValueError("sewer के सिरे पर नहीं तोड़ सकते - वहाँ manhole पहले से है")
    mh = str(op.get("label") or "").strip() or label_namer(list(nodes), (st.get("prefix") or {}).get("node", "MH-"))()
    if mh in nodes:
        raise ValueError(f"'{mh}' नाम का manhole पहले से है")
    nodes[mh] = {"xy": [round(q[0], 3), round(q[1], 3)], "ground": None, "gl_source": ""}
    lab2 = label_namer([c["label"] for c in conds], (st.get("prefix") or {}).get("pipe", "CO-"))()
    tot = k["length_m"] or _plen(P)
    f1 = _plen(first) / (_plen(P) or 1.0)
    k2 = {"label": lab2, "start_node": mh, "stop_node": k["stop_node"], "length_m": round(tot * (1 - f1), 3),
          "vertices": second, "id": st["next_id"]}
    st["next_id"] += 1
    k["stop_node"], k["vertices"], k["length_m"] = mh, first, round(tot * f1, 3)
    conds.append(k2)
    _log(st, "sewer split", k["label"], f"new manhole {mh} (no GL yet); second part {lab2}")
    tc.update([k["id"], k2["id"]])
    tn.update([mh, k["start_node"], k2["stop_node"]])


def _op_move(st, op, tn, tc):
    need_mh, attached = _ctx(st, "need_mh", "attached")
    mh = op["mh"]
    v = need_mh(mh)
    p = converters(st)[1]([op["latlng"]])[0]
    old = v["xy"]
    v["xy"] = p
    for k in attached(mh):
        for end, vi in (("start_node", 0), ("stop_node", -1)):
            if k[end] == mh and k["vertices"]:
                k["vertices"][vi] = list(p)
        if len(k["vertices"]) > 1:
            k["length_m"] = round(_plen(k["vertices"]), 3)
        tc.add(k["id"])
    _log(st, "manhole moved", mh, f"{math.dist(old, p):.2f} m" if old else "")
    tn.add(mh)


def _op_gl_from_labels(st, op, tn, tc):
    nodes = _ctx(st, "nodes")
    for n, (g, d) in label_levels(st).items():
        v = nodes[n]
        old = v.get("ground")
        v["ground"] = g
        v["gl_source"] = "text next to the manhole's label - check"
        _log(st, "GL (drawing, next to the label)", n,
             f"{'-' if old is None else f'{old} (interpolated)'} -> {g} (label {d:.1f} m from the symbol)")
        tn.add(n)


def _op_apply_suggestions(st, op, tn, tc):
    nodes = _ctx(st, "nodes")
    sug = suggestions(st)
    want = op.get("mh")
    todo = [(n, s) for n, s in sug.items() if want is None or n in (want if isinstance(want, list) else [want])]
    if want is not None and not todo:
        raise ValueError("इस manhole के लिए सुझाव नहीं")
    for n, s in todo:
        if s["label"] in nodes:
            continue                                         # taken meanwhile (only possible in a list)
        _apply_suggestion(st, n, s, tn, tc)


def _op_review(st, op, tn, tc):
    rev = set(st["reviewed"])
    (rev.add if op.get("ok", True) else rev.discard)(op["key"])
    st["reviewed"] = sorted(rev)
    _log(st, "checked" if op.get("ok", True) else "check undone", op["key"])


_OPS = {
    "set_gl": _op_set_gl,
    "rename_prefix": _op_rename_prefix,
    "rename": _op_rename,
    "outfall": _op_outfall,
    "delete_conduit": _op_delete_conduit,
    "delete_mh": _op_delete_mh,
    "connect": _op_connect,
    "merge": _op_merge,
    "split": _op_split,
    "move": _op_move,
    "gl_from_labels": _op_gl_from_labels,
    "apply_suggestions": _op_apply_suggestions,
    "review": _op_review,
}


def _apply1(st, op, tn, tc):
    """One correction of the page (17-Nov-2026: the operations' long if/elif chain split into the _op_* functions)."""
    f = _OPS.get(op.get("op"))
    if f is None:
        raise ValueError(f"unknown change '{op.get('op')}'")
    f(st, op, tn, tc)
