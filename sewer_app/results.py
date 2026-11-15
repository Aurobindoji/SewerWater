"""The results of a sewer project kept on disk: the last zoning / design and the network they were made on (restructure
stage 6, 15-Nov-2026: out of ui.py)."""
import json
import os
import time
from .project import has_network, is_dxf, net_rev, net_state, network_current, out_root, paths, proj_dir
from .inputs import FIELDS


def _keep(stem, kind, res, req):
    """The page's last zoning / design result, kept with the project (output\\<stem>\\<stem>_<kind>_ui.json) so that
    it is shown again when the project is opened (page reload, app restart)."""
    folder = os.path.join(out_root(), stem)
    os.makedirs(folder, exist_ok=True)
    keep = dict(res, req={k: req.get(k) for k in FIELDS + ("option",)}, time=time.strftime("%d-%m-%Y %H:%M"),
                net_rev=net_rev(stem))
    with open(os.path.join(folder, f"{stem}_{kind}_ui.json"), "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, separators=(",", ":"))
    if kind == "zoning":                                # a new zoning: the design of the old one is not shown again
        try:
            os.remove(os.path.join(folder, f"{stem}_design_ui.json"))
        except OSError:
            pass


def last_results(stem):
    """What the page shows again on opening a project: {network_saved (= a network to zone), network_current,
    zoning, design} - a zoning / design made from another state of the network than the one now is 'stale'."""
    folder, f_mh, _, _ = paths(stem)
    out = {"ok": True, "network_saved": has_network(stem), "network_current": True}
    if not out["network_saved"]:
        return out
    rev = net_rev(stem)
    for kind in ("zoning", "design"):
        f = os.path.join(folder, f"{stem}_{kind}_ui.json")
        if os.path.isfile(f):
            with open(f, encoding="utf-8") as fh:
                r = json.load(fh)
            if r.get("net_rev") is not None:
                r["stale"] = r["net_rev"] != rev
            else:                                   # kept before net_rev: the saved files' time, as before
                r["stale"] = (not os.path.isfile(f_mh) or os.path.getmtime(f) < os.path.getmtime(f_mh)
                              or not network_current(stem))
            out[kind] = r
    return out


def _source(stem):
    if is_dxf(stem):
        st = net_state(stem)
        return f"{st['dxf']} (corrected on the map: {len(st['edits'])} change(s), list in {stem}_network_edits.csv)"
    return os.path.join(proj_dir(), stem + ".kml")
