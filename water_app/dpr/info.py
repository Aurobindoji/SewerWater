"""What the DPR workbook needs from a water design (dpr_info) - restructure stage 3, 15-Nov-2026: out of dpr.py."""
from .base import settings, size_key


def dpr_info(zones, pipes, outlets, dmas, closed, stages, crit, title):
    """What write_dpr needs from a design: the OZs (zoning + the design's OHT outlets), the pipes by OZ and size and the
    sluice valves the network asks for (dpr_water.json valves_rule)."""
    S = settings()
    vop = S["valve_of_pipe"]
    by_lab = {p["label"]: p for p in pipes}
    out = {o["name"]: o for o in outlets}
    zs = []
    for z in zones:
        o = out.get(z["name"], {})
        zs.append({"name": z["name"], "population": z["population"], "connections": z["connections"],
                   "demand_kld": z["demand_kld"], "bulk_kld": z.get("bulk_kld") or 0.0,
                   "capacity_kl": z.get("capacity_kl"), "required_kl": z["required_kl"],
                   "cwr_kl": z.get("cwr_kl"), "tubewells": z.get("tubewells") or 0, "rebore": z.get("rebore") or 0,
                   "dmas": z.get("dma_count") or 1,
                   "existing": bool(z.get("capacity_kl")), "proposed": bool(o.get("proposed") or z.get("proposed")),
                   "staging_m": o.get("staging_m"), "vfd_head_m": o.get("vfd_head_m"), "vfd_kw": o.get("vfd_kw"),
                   "flow_lps": o.get("flow"),
                   "outlet": o.get("size"), "elev_min": z.get("elev_min"), "elev_max": z.get("elev_max")})
    names = [z["name"] for z in zs]
    length = {n: {} for n in names}
    for p in pipes:
        if p.get("size") and p.get("oz") in length:
            length[p["oz"]][p["size"]] = length[p["oz"]].get(p["size"], 0.0) + float(p["length"] or 0.0)
    valves = {n: {} for n in names}

    def add(oz, size):
        d = vop.get(size)
        if oz in valves and d:
            valves[oz][d] = valves[oz].get(d, 0) + 1
    for lab in closed:
        p = by_lab.get(lab)
        if p:
            add(p.get("oz"), p.get("size"))
    for d in dmas:
        p = by_lab.get(d.get("inlet_pipe") or "")
        if p:
            add(d.get("zone"), p.get("size"))
    for z in zs:
        add(z["name"], z["outlet"])
    return {"title": title, "zones": zs, "length": length, "valves": valves, "stages": stages,
            "pop": sum(z["population"] for z in zs), "crit": crit,
            "sizes": sorted({s for v in length.values() for s in v}, key=lambda s: (size_key(s)[0] != "HDPE",
                                                                                   size_key(s)[1]))}
