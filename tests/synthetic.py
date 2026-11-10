"""Small synthetic sewer networks for tests: a 1.2 km main sewer to OUT with 6 branches of 240 m,
manholes every 30 m, ground 100 m +-5 cm, optionally falling towards the outfall."""
import random

INP = {"catalog": "UPJN_RCC_NP3_SRC", "joint": "ss", "pop_total": 60000, "pop_dist": "length",
       "sewage_lpcd": 108.0, "infil_basis": "none", "peak": "table", "start_depth": 0.7}


def synth(n_main=40, n_branch=6, blen=8, seed=1, ground_slope=0.0):
    """ground_slope = fall of the ground per metre towards the outfall (0 = flat)."""
    rnd = random.Random(seed)
    nodes, conds = {}, []

    def node(lab, x, y):
        nodes[lab] = {"ground": 100.0 - ground_slope * x + rnd.uniform(-0.05, 0.05), "xy": (x, y),
                      "gl_source": "synthetic"}
    node("OUT", n_main * 30.0, 0.0)
    for i in range(n_main):
        node(f"M{i}", i * 30.0, 0.0)
    for i in range(n_main):
        conds.append({"label": f"C{i}", "start_node": f"M{i}", "stop_node": f"M{i + 1}" if i + 1 < n_main else "OUT",
                      "length_m": 30.0, "vertices": []})
    for b in range(n_branch):
        at = (b + 1) * n_main // (n_branch + 1)
        prev = f"M{at}"
        for j in range(blen):
            lab = f"B{b}_{j}"
            node(lab, at * 30.0, (j + 1) * 30.0 * (1 if b % 2 else -1))
            conds.append({"label": f"BC{b}_{j}", "start_node": lab, "stop_node": prev, "length_m": 30.0, "vertices": []})
            prev = lab
    return {"nodes": nodes, "conduits": conds, "outfalls": ["OUT"]}
