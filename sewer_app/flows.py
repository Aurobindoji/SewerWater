"""Design flow of every sewer from the population (CPHEEO sec 3.5 / Table 3.2 / sec 3.6).

From the original scripts sewer_design.py (distribute_population, peak_factor, design_flows), unchanged except that
orient / topo_order come from design.py. Units: population persons, flows L/s, infiltration rate per day.
"""
import math
import re

from .design import orient, topo_order


def distribute_population(total, method, data, manholes, csv_path=None):
    """{manhole: population} for the design population. equal = same on every manhole of the network;
    length = in proportion to half the length of the sewers meeting at the manhole; csv = from file."""
    ends = {n for k in data["conduits"] for n in (k["start_node"], k["stop_node"])}
    used = [m for m in manholes if m in ends]
    if method == "csv":
        import csv
        out = {}
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            for row in csv.reader(fh):
                if len(row) < 2 or not row[0].strip():
                    continue
                try:
                    out[row[0].strip()] = float(row[1])
                except ValueError:
                    continue                                   # header line
        return out
    if method == "length":
        w = {m: 0.0 for m in used}
        for k in data["conduits"]:
            for n in (k["start_node"], k["stop_node"]):
                if n in w:
                    w[n] += (k["length_m"] or 0) / 2.0
        tot = sum(w.values()) or 1.0
        return {m: total * w[m] / tot for m in used}
    return {m: total / len(used) for m in used} if used else {}


def cut_heads(nodes):
    """{new head manhole: its manhole} for the heads made where a conduit was disconnected (repair loop cut, zoning
    option): node attribute cut_of, or - after a CSV round trip - a label <manhole>-C<n> at the place of <manhole>."""
    out = {}
    for n, v in nodes.items():
        up = v.get("cut_of")
        if not up:
            m = re.fullmatch(r"(.+)-C\d+", str(n))
            if m and m.group(1) in nodes:
                a, b = v.get("xy"), nodes[m.group(1)].get("xy")
                if a and b and None not in a and None not in b and math.dist(a, b) < 0.01:
                    up = m.group(1)
        if up and up in nodes:
            out[n] = up
    return out


def share_cut_heads(pop, data, heads):
    """A population file (pop_dist csv) knows only the manholes of the network as drawn; a manhole cut by a loop
    or zone boundary is now that manhole + new head(s) <manhole>-C<n>, each with its own sewers. The manhole's
    population is shared among them in proportion to the sewer length meeting each (as pop_dist 'length' does);
    the total does not change. Heads given in the file keep their value. Returns rows {manhole, head, population}."""
    L = {}
    for k in data["conduits"]:
        for n in (k["start_node"], k["stop_node"]):
            L[n] = L.get(n, 0.0) + (k["length_m"] or 0.0)
    groups = {}
    for h, up in heads.items():
        if h not in pop:
            groups.setdefault(up, []).append(h)
    rows = []
    for up, hs in sorted(groups.items()):
        if not pop.get(up):
            continue
        members = [up] + sorted(hs)
        w = {m: L.get(m, 0.0) for m in members}
        tot = sum(w.values())
        total = pop[up]
        for m in members:
            pop[m] = total * (w[m] / tot if tot else 1.0 / len(members))
        rows += [{"manhole": up, "head": h, "population": pop[h]} for h in hs]
    return rows


def peak_factor(P, spec, rows):
    if spec != "table":
        return float(spec)
    for upto, pf in rows:
        if upto is None or P <= upto:
            return pf
    return rows[-1][1]


def average_flows(pop, sewage_lpcd):
    """{manhole: average sewage L/s} = population x L/capita/day / 86400."""
    return {m: p * sewage_lpcd / 86400.0 for m, p in pop.items()}


def design_flows(data, avg, pop, manholes, spec, rows, infil):
    """Design flow of every conduit from the loads: contributory population P and average flow are
    summed from the heads of sewers down (design direction = towards the outfall), peak factor from
    P (Table 3.2, or a fixed value), infiltration from the upstream sewer length or manhole count,
    limited to infil['cap'] x peak sewage flow. Returns {conduit: record}."""
    conds = [dict(k) for k in data["conduits"]]
    for k in conds:
        k["_from"], k["_to"], k["_rev"] = orient(k)
    order, inc, out = topo_order(conds)
    acc = {}
    for nd in order:
        ins = [acc[k["label"]] for k in inc.get(nd, [])]
        P = pop.get(nd, 0.0) + sum(x["P"] for x in ins)
        A = avg.get(nd, 0.0) + sum(x["A"] for x in ins)
        Lup = sum(x["L"] for x in ins)
        N = (1 if nd in manholes else 0) + sum(x["N"] for x in ins)
        for k in out.get(nd, []):
            L = Lup + (k["length_m"] or 0)
            pf = peak_factor(P, spec, rows)
            peak = pf * A
            if infil["basis"] == "km":
                raw = infil["rate"] * L / 1000.0 / 86400.0
            elif infil["basis"] == "manhole":
                raw = infil["rate"] * N / 86400.0
            else:
                raw = 0.0
            inf = min(raw, (infil.get("cap") or float("inf")) * peak)
            acc[k["label"]] = {"P": P, "A": A, "L": L, "N": N, "pf": pf, "peak": peak, "infil_raw": raw,
                               "infil": inf, "Q": peak + inf, "from": nd, "to": k["_to"]}
    return acc
