"""Rising mains of the new tube wells (water phase 2, user decisions 31-Oct-2026): the source is tube wells only, each
OZ's OHT filled by its own; every new tube well has a rising main of its own to its OHT, along the roads (the shortest
path along the network's pipes, CPHEEO 6.8 p403: pipes laid along the roads).

    sites    the new tube wells of each OZ: those placed on the map (the OZ of their nearest junction), and where the
             zoning needs more (tubewells_new), suggested ones - the junctions of the OZ nearest along the roads to its
             OHT, at least tubewell_spacing_m from the OHT and from every other tube well
    size     the economical size (CPHEEO 6.7 p400-402, Annexure 6.1 p1157-1159): of the catalog's sizes within the
             velocity range, the least of pipe cost (+ specials) + pump sets (+ standby, replaced after 15 years at
             present worth) + capitalised energy (two stages of 15 years) - the tube well pumping its discharge its
             pumping hours a day in both; each size's pipe at the rate of the class it needs (K9 above K-7)
    surge    CPHEEO 6.16.4 p428: h = c V / g on a sudden pump stop, c = 1425 / sqrt(1 + k d / (E t)); the pump's head
             against the pipe's allowable operating pressure (AOP, without surge), its head + h against the allowable
             maximum operating pressure (MOP, with surge) - IS 8329 Annex E for DI; a DI main K-7 exceeds: K9
             (user decision 31-Oct-2026, pipe_class)

The pump head of a tube well: from its water level (water_below_gl under its ground) to the top water level of the OHT
- of its CWR in an OZ with one (the caller's top[OZ]) - + the rising main's friction (+ minor losses)."""
import heapq
import math

G = 9.81


def _dijkstra(adj, src):
    dist, prev, pq = {src: 0.0}, {}, [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, math.inf):
            continue
        for v, L in adj.get(u, ()):
            nd = d + L
            if nd < dist.get(v, math.inf) - 1e-9:
                dist[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    return dist, prev


def _path(prev, src, n):
    out = [n]
    while out[-1] != src:
        out.append(prev[out[-1]])
    return out


def hf(L, q_m3s, d_m, C):
    """Hazen-Williams head loss (m) of L m of pipe (CPHEEO Eq. 6.4)."""
    return 10.67 * L * q_m3s ** 1.852 / (C ** 1.852 * d_m ** 4.87) if q_m3s > 0 else 0.0


def wall_mm(s):
    """Wall thickness of a catalog size: HDPE (OD - ID) / 2; DI K-7 e = 7 (0.5 + 0.001 DN), at least 5 mm (IS 8329:2000
    clause 4.3, Table 2: DN 200 5.0 mm, DN 300 5.6 mm)."""
    if s["name"].startswith("HDPE"):
        return (s["nominal"] - s["id_mm"]) / 2
    return max(5.0, 7 * (0.5 + 0.001 * s["nominal"]))


def celerity(s, crit, wall=None):
    S = crit["surge"]["value"]
    E = S["E"]["HDPE" if s["name"].startswith("HDPE") else "DI"]
    return 1425.0 / math.sqrt(1 + S["k"] * (s["id_mm"] / 1000) / (E * (wall or wall_mm(s)) / 1000))


MPA = 101.97           # m of water in 1 MPa


def pipe_class(s, head, v, crit):
    """The class of a rising main and its surge: (class, c, h, AOP m, MOP m, ok). DI: K-7 when its head is within the
    AOP and its head + surge within the MOP of K-7 (IS 8329 Annex E), else K9 (user decision 31-Oct-2026) with its own
    wall (Table 2), surge and AOP / MOP; HDPE: PN-6 (no other class in the catalog; no surge allowance in IS 4984 -
    not a rising main, crit rising_main_material)."""
    S = crit["surge"]["value"]
    mat = "HDPE" if s["name"].startswith("HDPE") else "DI"
    c = celerity(s, crit)
    h, aop, mop = c * v / G, S["aop_m"][mat], S["mop_m"][mat]
    cls = "PN-6" if mat == "HDPE" else "K7"
    K = crit["di_k9"]["value"]
    dn = str(s["nominal"])
    if mat == "DI" and (head > aop or head + h > mop) and dn in K["wall_mm"]:
        cls, c = "K9", celerity(s, crit, K["wall_mm"][dn])
        h, aop, mop = c * v / G, K["aop_mpa"][dn] * MPA, K["mop_mpa"][dn] * MPA
    return cls, c, h, aop, mop, head <= aop and head + h <= mop


def economic(L, q_m3s, static, sizes, rate, crit):
    """The candidates (velocity range of crit, widened by one size where the least is at an end - CPHEEO 6.7.2) and
    their costs; [(row, ...)] with row = {size, cls, v, hf, head, kw, pipe, pumps, energy, total}, the least flagged.
    Each candidate's pipe at the rate of the class its own head and surge need (pipe_class: a DI size above K-7 at
    its K9 rate - rate(name, cls)), so a size that needs K9 competes at its K9 cost."""
    X = crit["rising_main_economics"]["value"]
    hours = crit["tubewell_pumping_hours"]["value"]
    lo, hi = crit["rising_main_velocity"]["value"]
    r, n = X["interest"], X["pump_life"]
    cf = (1 - (1 + r) ** -n) / r                         # capitalising an annual cost over 15 years (Eq. 1)
    pw = (1 + r) ** -n                                   # the second stage's present worth (Eq. 3 - 5)

    def row(s):
        d = s["id_mm"] / 1000
        v = q_m3s / (math.pi * d * d / 4)
        h = hf(L, q_m3s, d, s["C"]) * (1 + X["minor"])
        head = static + h
        kw = G * q_m3s * head / X["efficiency"]
        aec = kw * hours * 365 * X["energy_rs_per_kwh"]
        cls = pipe_class(s, head, v, crit)[0]
        pipe = L * rate(s["name"], cls) * (1 + X["specials"])
        pumps = kw * (1 + X["standby"]) * X["pump_rs_per_kw"]
        energy = aec * cf * (1 + pw)
        return {"size": s["name"], "cls": cls, "v": v, "hf": h, "head": head, "kw": kw, "pipe": pipe,
                "pumps": pumps * (1 + pw), "energy": energy, "total": pipe + pumps * (1 + pw) + energy}
    rows = [row(s) for s in sizes]
    idx = [i for i, x in enumerate(rows) if lo <= x["v"] <= hi]
    if not idx:                                          # no size in the range: the nearest ones to it
        idx = sorted(range(len(rows)), key=lambda i: min(abs(rows[i]["v"] - lo), abs(rows[i]["v"] - hi)))[:2]
        idx.sort()
    while True:                                          # the least at an end of the candidates: the next size too
        best = min(idx, key=lambda i: rows[i]["total"])
        if best == idx[0] and best > 0 and rows[best - 1]["v"] <= 3.0:
            idx.insert(0, best - 1)
        elif best == idx[-1] and best < len(rows) - 1 and rows[best + 1]["v"] >= 0.3:
            idx.append(best + 1)
        else:
            break
    out = [dict(rows[i], best=i == best) for i in idx]
    return out


def plan(wnet, z, ohts, placed, crit, sizes, rate, top, need, below=6.0):
    """The new tube wells and their rising mains.
        wnet   nodes {n: {xy, elev}}, pipes {lab: {a, b, length}} (the roads: closed pipes too)
        z      the zoning (z["oz"]: junction -> OZ)
        ohts   [{name, node}]
        placed [{name, xy, discharge_lpm}] - those on the map, in metres
        top    {OZ: top water level of its OHT (m)}
        need   {OZ: new tube wells the zoning asks for}
        rate   (size name, class) -> Rs per m laid (supply + laying; K9 at its own supply rate)
        below  the water level of a tube well under its ground (m)
    {"tws": [...], "oz": {OZ: {friction_m, length_m, n}}, "flags": [...]}
    The candidate sizes: those of the materials of crit rising_main_material (DI only - user decision 7-Nov-2026)."""
    mats = (crit.get("rising_main_material") or {}).get("value") or ["DI"]
    sizes = [s for s in sizes if any(s["name"].startswith(m) for m in mats)]
    N, P = wnet["nodes"], wnet["pipes"]
    adj = {}
    for p in P.values():
        if p["a"] in N and p["b"] in N:
            adj.setdefault(p["a"], []).append((p["b"], p["length"]))
            adj.setdefault(p["b"], []).append((p["a"], p["length"]))
    xy = {n: v["xy"] for n, v in N.items() if v.get("xy")}
    spacing = crit["tubewell_spacing_m"]["value"]
    q_new = crit["tubewell_discharge_lpm"]["value"]
    flags, tws = [], []
    ohtn = {o["name"]: o["node"] for o in ohts}
    for t in placed:                                     # on the map: its nearest junction, its OZ
        n = min(xy, key=lambda k: math.dist(xy[k], t["xy"])) if xy else None
        oz = z["oz"].get(n) if n else None
        if oz not in ohtn:
            flags.append(f"tube well {t['name']}: its nearest junction {n} is in no OZ - not designed")
            continue
        tws.append({"name": t["name"], "node": n, "oz": oz, "xy": tuple(t["xy"]), "snap_m": math.dist(xy[n], t["xy"]),
                    "lpm": float(t.get("discharge_lpm") or q_new), "placed": True})
    route = {}
    for oz, src in ohtn.items():
        if src in adj:
            route[oz] = _dijkstra(adj, src)
    for oz, k in sorted(need.items()):                   # suggested sites where the map has fewer than needed
        have = sum(1 for t in tws if t["oz"] == oz)
        if k <= have or oz not in route:
            continue
        dist, _ = route[oz]
        src = ohtn[oz]
        cand = sorted((d, n) for n, d in dist.items() if z["oz"].get(n) == oz and n in xy)
        taken = [t["xy"] for t in tws] + [xy[src]]
        made = 0
        for d, n in cand:
            if made >= k - have:
                break
            if all(math.dist(xy[n], p) >= spacing for p in taken):
                tws.append({"name": f"TW-{oz}-{have + made + 1}", "node": n, "oz": oz, "xy": tuple(xy[n]), "snap_m": 0.0,
                            "lpm": q_new, "placed": False})
                taken.append(xy[n])
                made += 1
        if made < k - have:
            flags.append(f"{oz}: {k - have - made} of the {k} new tube wells found no site {spacing:g} m from the others "
                         f"- place them on the map")
    per_oz = {}
    for t in tws:
        dist, prev = route.get(t["oz"], ({}, {}))
        if t["node"] not in dist:
            t["note"] = f"no road from it to the OHT of {t['oz']}"
            flags.append(f"tube well {t['name']}: {t['note']}")
            continue
        path = _path(prev, ohtn[t["oz"]], t["node"])                 # tube well -> OHT
        L = dist[t["node"]] + t["snap_m"]
        q = t["lpm"] / 60000.0
        gl = N[t["node"]].get("elev")
        static = top[t["oz"]] - ((gl if gl is not None else 0.0) - below)
        alts = economic(L, q, static, sizes, rate, crit)
        b = next(a for a in alts if a["best"])
        s = next(x for x in sizes if x["name"] == b["size"])
        cls, c, h, aop, mop, ok = pipe_class(s, b["head"], b["v"], crit)
        t.update(path=path, length_m=L, q_lps=q * 1000, static_m=static, gl=gl, size=b["size"], cls=cls, v=b["v"],
                 hf_m=b["hf"],
                 head_m=b["head"], kw=b["kw"], alts=alts, celerity=c, surge_m=h, max_m=b["head"] + h,
                 min_m=b["head"] - h, rating_m=mop, aop_m=aop, surge_ok=ok)
        g = per_oz.setdefault(t["oz"], {"friction_m": 0.0, "length_m": 0.0, "n": 0, "by_size": {}})
        g["friction_m"] = max(g["friction_m"], b["hf"])
        g["length_m"] += L
        g["n"] += 1
        g["by_size"][b["size"]] = g["by_size"].get(b["size"], 0.0) + L
    return {"tws": tws, "oz": per_oz, "flags": flags}
