"""netedit: what the page gets - manholes, sewers, problems, suggestions."""
from sewer_app.net import repair
from .common import _UNDO
from .coords import converters
from .problems import issues
from .suggest import label_levels, suggestions
from .texts import _tuples


# ---------------------------------------------------------------- data for the page
def page_data(st, full=True, touched=None):
    """Everything the page draws: nodes, conduits (lat / lon), problems, totals. With full=False only the
    touched nodes / conduits (None = deleted)."""
    to_ll = converters(st)[0]
    net = st["net"]
    outs = set(net["outfalls"])

    def node(n):
        v = net["nodes"][n]
        p = to_ll([v["xy"]])[0] if v.get("xy") else None
        return {"latlng": p, "gl": v.get("ground"), "src": v.get("gl_source") or "", "out": n in outs,
                "il": v.get("invert_drawing")}

    def cond(k):
        pts = k.get("vertices") or [net["nodes"][n]["xy"] for n in (k["start_node"], k["stop_node"])
                                    if net["nodes"].get(n, {}).get("xy")]
        return {"id": k["id"], "label": k["label"], "from": k["start_node"], "to": k["stop_node"],
                "len": round(k["length_m"] or 0.0, 2), "pts": to_ll(pts)}
    iss = issues(st)
    ll = to_ll([[i["x"], i["y"]] if i.get("x") is not None else [0, 0] for i in iss])
    ilist = [[i["key"], i["type"], str(i["item"]), p[0] if i.get("x") is not None else None,
              p[1] if i.get("x") is not None else None, i.get("detail") or "", i["reviewed"], i["low"]]
             for i, p in zip(iss, ll)]
    parts = repair._parts(_tuples(net))
    summ = {"manholes": len(net["nodes"]), "conduits": len(net["conduits"]),
            "length": round(sum(k["length_m"] or 0 for k in net["conduits"]), 1),
            "parts": len(set(parts.values())), "outfalls": net["outfalls"],
            "no_gl": sum(1 for v in net["nodes"].values() if v.get("ground") is None), "edits": len(st["edits"]),
            "undo": len(_UNDO[st["stem"]])}
    sug = suggestions(st)
    sl = to_ll([s["lxy"] for s in sug.values()])
    out = {"ok": True, "kind": "dxf", "name": st["stem"], "issues": ilist, "summary": summ,
           "local": not st.get("epsg"), "epsg": st.get("epsg"), "dxf": st["dxf"],
           "suggest": {n: [s["label"], s["d"], s["gl"]["value"] if s["gl"] else None, p[0], p[1]]
                       for (n, s), p in zip(sug.items(), sl)},
           "label_levels": len(label_levels(st))}
    if full:
        # nodes in drawing order; lat / lon of all of them in one transform
        names = [n for n in net["nodes"] if net["nodes"][n].get("xy")]
        pts = to_ll([net["nodes"][n]["xy"] for n in names])
        out["nodes"] = {n: {"latlng": p, "gl": net["nodes"][n].get("ground"), "src": net["nodes"][n].get("gl_source") or "",
                            "out": n in outs, "il": net["nodes"][n].get("invert_drawing")} for n, p in zip(names, pts)}
        out["conduits"] = [cond(k) for k in net["conduits"]]
    else:
        tn, tc = touched
        out["nodes"] = {n: (node(n) if n in net["nodes"] else None) for n in tn}
        by_id = {k["id"]: k for k in net["conduits"]}
        out["conduits_upd"] = {str(i): (cond(by_id[i]) if i in by_id else None) for i in tc}
    return out
