"""netedit: automatic mending (repair) and the CSV save for zoning / design."""
import os
import time
from sewer_app.net import repair
from .edits import _log, _snapshot
from .files import store
from .texts import _net_json, _tuples


def auto_repair(st, join_gap_m=1.0, tjoint_m=0.5, loops=True, gl=True):
    """repair.repair on the working network (one undo step); every repair is logged. Returns the repair rows."""
    _snapshot(st)
    net, rows = repair.repair(_tuples(st["net"]), {"problems": st["ex_problems"]}, st["net"]["outfalls"],
                              join_gap_m=join_gap_m, tjoint_m=tjoint_m, loops=loops, gl=gl)
    nj = _net_json(net)
    for k in nj["conduits"]:
        if "id" not in k:
            k["id"] = st["next_id"]
            st["next_id"] += 1
    st["net"] = nj
    for r in rows:
        _log(st, "auto: " + r["repair"], r["item"], str(r.get("detail") or ""))
    store(st)
    return rows


def save_network(st):
    """The corrected network as CSV (manholes / conduits, as dxf_extract writes them - for zoning / design and
    --csv) and the list of the changes made (<stem>_network_edits.csv). Returns the paths."""
    import csv
    from sewer_app.core import network
    folder = os.path.join(st["_root"], st["stem"])
    os.makedirs(folder, exist_ok=True)
    paths = {"manholes": os.path.join(folder, f"{st['stem']}_network_manholes.csv"),
             "conduits": os.path.join(folder, f"{st['stem']}_network_conduits.csv"),
             "edits": os.path.join(folder, f"{st['stem']}_network_edits.csv")}
    if st.get("saved_edits") == len(st["edits"]) and all(os.path.isfile(f) for f in paths.values()):
        return dict(paths, unchanged=True)       # nothing changed: the files (and the zoning made from them) stay
    net = _tuples(st["net"])
    f_mh, f_co = network.write_csv(net, os.path.join(folder, f"{st['stem']}_network_manholes.csv"),
                                   os.path.join(folder, f"{st['stem']}_network_conduits.csv"))
    f_ed = os.path.join(folder, f"{st['stem']}_network_edits.csv")
    with open(f_ed, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Time", "Change", "Item", "Detail"])
        for e in st["edits"]:
            w.writerow([e["time"], e["change"], e["item"], e["detail"]])
    st["saved"] = time.strftime("%d-%m-%Y %H:%M")
    st["saved_edits"] = len(st["edits"])          # changes after this: the CSV files are older than the network
    store(st)
    return {"manholes": f_mh, "conduits": f_co, "edits": f_ed}
