"""Operational zones (OZ, one per OHT / ESR) and District Metered Areas (DMA) of a water network - CPHEEO Table 2.7
S.No.18-21 (criteria.json).

    z = make_zones(net, ohts, crit)
    net  = {"nodes": {id: {"xy": (x, y), "elev": m, "pop": design population}},
            "pipes": {id: {"a": node, "b": node, "length": m}}}
    ohts = [{"name": "OHT-1", "node": id, "capacity_kl": 1500 | None (new: sized here), "tubewells": 3}, ...]
    z["oz"][node] -> OHT name, z["dma"][node] -> "OHT-1/DMA-2", z["zones"], z["dmas"], z["closed_pipes"], z["flags"]

1. OZ: every node to the OHT nearest along the pipes (multi-source shortest path).
2. Limits: an OZ above 50,000 population / 10,000 connections (S.No.20 p180), or above what an existing OHT can
   serve (its capacity >= max(33 %, mass balance) of the OZ's daily demand, S.No.12 p175), gives its outermost
   nodes - those farthest from its OHT, at the border with an OZ that still has room - to that OZ, one at a time.
   What cannot be moved is reported: the OZ needs a bigger / another OHT.
3. A new OHT (capacity None) is sized: max(33 %, mass balance) of its OZ's daily demand without fire
   (demand.storage_share) + one third of its fire demand (CPHEEO Table 2.7 S.No.13, user decision 30-Oct-2026: _demands),
   rounded up; CWR 25 % of it when more than 3 NEW tube wells fill it (UPJN rule) - the new ones the +15 years demand
   needs beyond those given (demand.tubewells_new; crit "stage_mid_share" = +15 years / design population); the
   existing tube wells stay engaged with the existing structures, not counted (user decision 27-Oct-2026).
4. DMAs: an OZ with up to 3000 connections is one DMA; above, ceil(connections / 3000) DMAs, at least 2, at most 4
   (S.No.21 p181). The OZ's shortest-path tree from its OHT is cut into subtrees of about equal connections - each
   DMA is a subtree, fed through ONE pipe (its inlet).
5. Pipes joining two OZs / DMAs outside their trees are to be closed (boundary valves) - each OZ / DMA hydraulically
   discrete (S.No.18, 21).
Flags: ground within an OZ varying more than 5 m (S.No.18 p180); a DMA outside 500-3000 connections (S.No.21).

    z = plan(net, ohts, crit)       existing OHTs first, NEW OHTs proposed for the area they cannot serve

plan: every OHT given (an existing one up to what its capacity serves, a new one up to 50,000 population) takes
the nodes nearest to it along the pipes while it has room; the area left over gets new OHTs - as many as its
population needs at 95 % of 50,000 per OZ, the piece halved again and again along the pipes into parts of about
equal population (_bisect), each OHT on the highest ground near the middle of its part - and then make_zones
runs on all of them. A left-over piece too small for one DMA (500 connections) gets no OHT of its own: it stays
with its neighbour, which is then flagged as above its capacity.

Zone loops (user request 27-Oct-2026): an area enclosed on the map is a zone of its own - its pipes crossing the loop
are closed at it (boundary valves, as between OZs - user decision 27-Oct-2026), given in net as closed; loops = [{"name",
"nodes": the junctions inside, "boundary": those pipes, "mode"}]. A loop above the OZ limit (50,000 / 10,000
connections) or below one DMA (500 connections) is handled as the user chose for it (mode): "keep" - one OZ as drawn,
whatever its size (flagged); "split" - new OZs within it as for any area (at least one, however small); "merge" - the
loop goes whole to the neighbouring OZ joined to it by most of its boundary pipes (those pipes open again).
z["loops"] tells each loop's population, connections, OZs and whether it is over / under the limits.

Why each OZ (user request 30-Oct-2026: the reason in a tooltip): z["why"][OZ] = {"kind": "given", "existing"} for an
OHT given on the map; for a proposed one {"kind": "proposed", "piece_population", "piece_nodes", "parts" (the OZs its
piece of the network - "piece" - was cut into for the 50,000 limit), "next_to" (given OHTs whose areas touch the piece - they
could not take it: capacity / 50,000 / height), "loop", "loop_mode"}. Whether the piece is cut off by a barrier line
or is a separate piece of the drawing is the caller's to tell (ui_api).

Height (an existing OHT whose staging cannot give 17 m everywhere): by default (low_head "vfd", CPHEEO Table 2.7
S.No.10 p173) its OZ is what its capacity serves and the design sizes a VFD pump at its outlet. With low_head
"new_oht" it gives 17 m only to ground up to its GL + staging - 17 m, less the head lost in the pipes - it does not
take a node above that, nor (bar, from the design) a node the designed pipes still left below 17 m, except a node
the water passes through to lower ground beyond (up to PASS_HIGH_M). Such nodes go to a new OHT (its staging found
by the design): a piece of a DMA (500 connections) or more gets its own proposed OHT, a smaller one joins a
neighbouring OZ that can serve it - when none can, it stays (flagged: below 17 m).
"""
import bisect
import collections
import heapq
import itertools
import math

from . import demand as dm

PASS_HIGH_M = 1000.0                # an OHT passes through ground too high for it for this far along the pipes
BISECT_TRIES = 16                  # moves of a cut of a piece into OZs, to bring its halves to their shares


def _v(crit, k):
    return crit[k]["value"]


def _ref(crit, k):
    """The criterion's source, short (for the Hindi text of a flag: "CPHEEO Table 2.7 S.No.20 p180")."""
    return crit[k]["ref"].split(":")[0]


def _demands(nodes, pop, crit, city):
    """Each node's daily demand (KLD: domestic + floating + fire + bulk consumers), its fire part, and its demand as the
    OHT stores it: the fire at a third (CPHEEO Table 2.7 S.No.13 p176: one third of the OZ's fire requirement kept in
    the ESR - user decision 30-Oct-2026) in place of the balancing share - so that the balancing share x this = the
    capacity it needs: max(33 %, mass balance) x (demand without fire) + fire / 3."""
    share, fs = dm.storage_share(crit), _v(crit, "fire_storage_share")
    dem, fire, kl = {}, {}, {}
    for n, v in nodes.items():
        d = dm.daily_kl(pop[n], crit, city)
        dem[n] = d["total"] + float(v.get("bulk_kl") or 0.0)
        fire[n] = d["fire"]
        kl[n] = dem[n] - fire[n] + fire[n] * fs / share
    return dem, fire, kl


def make_zones(net, ohts, crit, city_pop=None, assign=None):
    """assign = {node: OHT name} (from plan): the OZs as given - their trees from each OHT within its own nodes."""
    nodes, pipes = net["nodes"], net["pipes"]
    adj = {n: [] for n in nodes}
    for pid, p in pipes.items():
        if not p.get("closed"):
            adj[p["a"]].append((p["b"], pid, p["length"]))
            adj[p["b"]].append((p["a"], pid, p["length"]))
    ppc = _v(crit, "persons_per_connection")
    city = city_pop or sum(float(v.get("pop") or 0) for v in nodes.values())
    pop = {n: float(v.get("pop") or 0.0) for n, v in nodes.items()}
    dem, fire, kl = _demands(nodes, pop, crit, city)

    # ---- 1 nearest OHT along the pipes
    dist, owner, parent = {}, {}, {}
    pq = []
    for o in ohts:
        dist[o["node"]], owner[o["node"]], parent[o["node"]] = 0.0, o["name"], None
        heapq.heappush(pq, (0.0, str(o["node"]), o["node"]))
    while pq:
        d, _, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, pid, L in adj[u]:
            if assign is not None and assign.get(v) != owner[u]:
                continue                                     # the OZs as given: a tree within its own nodes
            nd = d + L
            if nd < dist.get(v, math.inf):
                dist[v], owner[v], parent[v] = nd, owner[u], (u, pid)
                heapq.heappush(pq, (nd, str(v), v))
    unserved = [n for n in nodes if n not in owner]
    names = [o["name"] for o in ohts]
    byname = {o["name"]: o for o in ohts}

    def limit(name):
        """(max population, max daily KL) of an OZ."""
        o = byname[name]
        maxk = o["capacity_kl"] / dm.storage_share(crit) if o.get("capacity_kl") else math.inf
        return min(_v(crit, "oz_max_population"), _v(crit, "oz_max_connections") * ppc), maxk

    load = {k: [0.0, 0.0] for k in names}
    for n, k in owner.items():
        load[k][0] += pop[n]
        load[k][1] += kl[n]

    def over(k):
        mp, mk = limit(k)
        return load[k][0] > mp + 1e-9 or load[k][1] > mk + 1e-9

    def room(k, n):
        mp, mk = limit(k)
        return load[k][0] + pop[n] <= mp + 1e-9 and load[k][1] + kl[n] <= mk + 1e-9

    # ---- 2 an OZ above its limit gives branches at its border to a neighbouring OZ with room: a subtree of its
    # tree hanging on a border node - both stay connected (the branch joins the other OZ through that border pipe).
    # A branch that brings it within its limit without giving away more than twice the excess, the smallest such;
    # else the biggest smaller branch (and again); a bigger branch only when nothing else is left.
    moved = 0
    for _ in range(len(owner) + 10):
        bad = [k for k in names if over(k)]
        if not bad:
            break
        kids_ = collections.defaultdict(list)
        for n, pr in parent.items():
            if pr is not None and n in owner:
                kids_[pr[0]].append(n)
        best, sub_of = None, {}
        for k in bad:
            mp, mk = limit(k)
            ex_p, ex_k = load[k][0] - mp, load[k][1] - mk
            sub = {}                                         # subtree: population, KL, its nodes

            def subtree(r):
                if r not in sub:
                    st, order = [r], []
                    while st:
                        u = st.pop()
                        order.append(u)
                        st.extend(kids_[u])
                    sub[r] = (sum(pop[u] for u in order), sum(kl[u] for u in order), order)
                return sub[r]
            for n in owner:
                if owner[n] != k or parent[n] is None:
                    continue
                for v, pid, L in adj[n]:
                    t = owner.get(v)
                    if t is None or t == k:
                        continue
                    sp, sk, _ = subtree(n)
                    mpt, mkt = limit(t)
                    if load[t][0] + sp > mpt + 1e-9 or load[t][1] + sk > mkt + 1e-9:
                        continue
                    enough = sp >= ex_p - 1e-9 and sk >= ex_k - 1e-9
                    rank = ((2, -sk) if enough and sk <= 2 * ex_k + 1e-9 else (1, sk) if not enough else (0, -sk))
                    cand = (rank, dist[n], str(n), n, v, pid, L, k, t)
                    if best is None or cand[:3] > best[:3]:
                        best = cand
                        sub_of[(k, n)] = sub[n][2]
        if best is None:
            break
        _, _, _, n, v, pid, L, k, t = best
        order = sub_of[(k, n)]
        shift = dist[v] + L - dist[n]
        parent[n] = (v, pid)
        for u in order:
            owner[u] = t
            dist[u] += shift
            load[k][0] -= pop[u]; load[k][1] -= kl[u]
            load[t][0] += pop[u]; load[t][1] += kl[u]
            moved += 1

    # ---- 3 zones: sizes, OHT capacity, CWR, flags
    flags, zones = [], []
    share, rnd = dm.storage_share(crit), _v(crit, "oht_capacity_round_kl")
    for k in names:
        o = byname[k]
        members = [n for n in owner if owner[n] == k]
        p_, k_ = load[k]                                     # k_: the demand as the OHT stores it (_demands)
        need = math.ceil(share * k_ / rnd) * rnd if k_ else 0
        dem_, fire_ = sum(dem[n] for n in members), sum(fire[n] for n in members)
        cap = o.get("capacity_kl")
        els = [float(nodes[n].get("elev")) for n in members if nodes[n].get("elev") is not None]
        tw = int(o.get("tubewells") or 0)
        rb = int(o.get("rebore") or 0)                       # existing ones rebored: they give as existing ones do
        bulk = sum(float(nodes[n].get("bulk_raw") or 0.0) for n in members)        # KLD without losses
        z = {"name": k, "node": o["node"], "nodes": len(members), "population": round(p_),
             "connections": math.ceil(p_ / ppc), "demand_kld": round(dem_, 1), "fire_kld": round(fire_, 1),
             "balancing_kl": round(share * (dem_ - fire_), 1), "fire_store_kl": round(_v(crit, "fire_storage_share") * fire_, 1),
             "bulk_kld": round(bulk, 1),
             "capacity_kl": cap, "existing": bool(cap), "required_kl": need,
             "elev_min": round(min(els), 2) if els else None, "elev_max": round(max(els), 2) if els else None,
             "tubewells": tw, "rebore": rb, "cwr_kl": None}
        # the new tube wells the +15 years demand needs beyond those given (as sheet TW of the DPR; the +15 years
        # population: this OZ's share of the page's, else the design's - user, 26-Oct-2026); a CWR when more than 3
        # of them - the existing ones stay with the existing structures (user decision 27-Oct-2026)
        mid = crit.get("stage_mid_share", {}).get("value", 1.0)
        z["tubewells_new"] = dm.tubewells_new(round(p_ * mid), crit, tw + rb, bulk)    # bulk: the same every stage
        # standby tube wells as CPHEEO 5.7.5 (user decision 7-Nov-2026), each built whole; the CWR rule counts the
        # working ones (those filling the OHT at a time)
        z["tubewells_standby"] = dm.standby(z["tubewells_new"], crit)
        if z["tubewells_new"] > _v(crit, "cwr_when_tubewells_over"):
            z["cwr_kl"] = math.ceil(_v(crit, "cwr_capacity_share") * (cap or need) / rnd) * rnd
        if over(k):
            mp, mk = limit(k)
            why, why_hi = [], []
            if p_ > mp + 1e-9:
                why.append(f"population {p_:,.0f} > {mp:,.0f} ({crit['oz_max_population']['ref']})")
                why_hi.append(f"आबादी {p_:,.0f} > {mp:,.0f} ({_ref(crit, 'oz_max_population')})")
            if k_ > mk + 1e-9:
                why.append(f"daily demand {dem_:,.0f} KL needs {need:,.0f} KL of OHT, it has {cap:,.0f} KL "
                           f"({crit['esr_capacity_share']['ref']}; + 1/3 of the fire demand)")
                why_hi.append(f"दैनिक माँग {dem_:,.0f} KL के लिए {need:,.0f} KL की OHT चाहिए, है {cap:,.0f} KL "
                              f"({_ref(crit, 'esr_capacity_share')})")
            flags.append({"zone": k, "level": "error", "text": f"{k}: " + "; ".join(why) +
                          " - its neighbours have no room: a bigger OHT or one more OHT is needed",
                          "hi": f"{k}: " + "; ".join(why_hi) + " - पड़ोसी OZ में जगह नहीं: बड़ी OHT या एक और OHT चाहिए"})
        if els and max(els) - min(els) > _v(crit, "oz_max_slope_m"):
            # the two junctions the difference is between (user request 30-Oct-2026), their names and GL
            gl = {n: float(nodes[n]["elev"]) for n in members if nodes[n].get("elev") is not None}
            lo, hi_ = min(gl, key=lambda n: (gl[n], str(n))), max(gl, key=lambda n: (gl[n], str(n)))
            flags.append({"zone": k, "level": "warn",
                          "text": f"{k}: ground varies {max(els) - min(els):.1f} m within the OZ (> {_v(crit, 'oz_max_slope_m'):g} m, "
                                  f"{crit['oz_max_slope_m']['ref']}) - lowest {lo} GL {gl[lo]:.2f} m, highest {hi_} "
                                  f"GL {gl[hi_]:.2f} m",
                          "hi": f"{k}: OZ के भीतर ज़मीन {max(els) - min(els):.1f} m ऊँची-नीची है (> {_v(crit, 'oz_max_slope_m'):g} m, "
                                f"{_ref(crit, 'oz_max_slope_m')}) - सबसे नीचा {lo} GL {gl[lo]:.2f} m, सबसे ऊँचा "
                                f"{hi_} GL {gl[hi_]:.2f} m",
                          "low": lo, "high": hi_})
        zones.append(z)

    # ---- 4 DMAs: the OZ's tree cut into subtrees of about equal connections
    dma, dmas = {}, []
    kids = {n: [] for n in owner}
    for n in owner:
        if parent[n] is not None:
            kids[parent[n][0]].append(n)
    cmax, cmin, nmax = _v(crit, "dma_max_connections"), _v(crit, "dma_min_connections"), _v(crit, "dma_max_per_oz")
    for z in zones:
        k = z["name"]
        conn = z["connections"]
        nd = 1 if conn <= cmax else min(nmax, max(2, math.ceil(conn / cmax)))
        root = z["node"]
        order, stack = [], [root]                        # pre-order over the OZ's tree
        while stack:
            u = stack.pop()
            order.append(u)
            stack.extend(kids[u])

        def cuts(nd):
            """Roots of the subtrees cut off for nd DMAs: the tree halved (a subtree as near as possible to the
            share of the first half), each half halved again - parts of about equal connections."""
            cut = []

            def region(r):
                out, stack = [], [r]
                while stack:
                    u = stack.pop()
                    out.append(u)
                    stack.extend(c for c in kids[u] if c not in cut)
                return out

            def split(r, k):
                if k <= 1:
                    return
                reg = region(r)
                sub = {}
                for u in reversed(reg):                  # region() is a pre-order: children after parents
                    sub[u] = pop[u] / ppc + sum(sub[c] for c in kids[u] if c not in cut)
                k1 = k // 2
                target = sub[r] * k1 / k
                cand = [u for u in reg if u != r and sub[u] > 0]
                if not cand:
                    return
                u = min(cand, key=lambda x: abs(sub[x] - target))
                cut.append(u)
                split(u, k1)
                split(r, k - k1)
            split(root, nd)
            return cut

        def sizes(cut):
            out = []
            for r in [root] + cut:
                stack, c_ = [r], 0.0
                while stack:
                    u = stack.pop()
                    c_ += pop[u] / ppc
                    stack.extend(c for c in kids[u] if c not in cut)
                out.append(c_)
            return out
        cut = cuts(nd)
        while nd < nmax and max(sizes(cut)) > cmax:      # a DMA still too big: one more (CPHEEO up to 4)
            nd += 1
            cut = cuts(nd)
        z["dma_count"] = len(cut) + 1
        nd = z["dma_count"]
        roots = [root] + cut
        for i, r in enumerate(roots, 1):
            name = f"{k}/DMA-{i}"
            stack, members = [r], []
            while stack:
                u = stack.pop()
                members.append(u)
                dma[u] = name
                stack.extend(c for c in kids[u] if c not in cut)
            c_ = sum(pop[m] for m in members) / ppc
            inlet = parent[r][1] if r != root else None
            dmas.append({"name": name, "zone": k, "root": r, "inlet_pipe": inlet, "nodes": len(members),
                         "population": round(sum(pop[m] for m in members)), "connections": math.ceil(c_)})
            if c_ > cmax * 1.05 or (nd > 1 and c_ < cmin):
                flags.append({"zone": k, "level": "warn",
                              "text": f"{name}: {c_:,.0f} connections (outside {cmin:g}-{cmax:g}, {crit['dma_max_connections']['ref']})",
                              "hi": f"{name}: {c_:,.0f} कनेक्शन ({cmin:g}-{cmax:g} की सीमा से बाहर, "
                                    f"{_ref(crit, 'dma_max_connections')})"})

    # ---- 5 pipes to close: joining two OZs or two DMAs, not a pipe of a tree
    tree = {pr[1] for pr in parent.values() if pr is not None}
    closed = sorted((pid for pid, p in pipes.items() if not p.get("closed") and pid not in tree
                     and (owner.get(p["a"]) != owner.get(p["b"]) or dma.get(p["a"]) != dma.get(p["b"]))), key=str)
    if unserved:
        flags.append({"zone": None, "level": "error", "text": f"{len(unserved)} nodes have no pipe path to any OHT",
                      "hi": f"{len(unserved)} junctions किसी OHT से pipe द्वारा नहीं जुड़े"})
    return {"oz": owner, "dma": dma, "dist": dist, "zones": zones, "dmas": dmas, "closed_pipes": closed,
            "unserved": unserved, "moved": moved, "flags": flags}


def _dist_in(region, adj, srcs):
    """Shortest distance along the pipes from srcs to every node of region, through region only."""
    dist = {x: 0.0 for x in srcs}
    q = [(0.0, str(x), x) for x in srcs]
    heapq.heapify(q)
    while q:
        d, _, u = heapq.heappop(q)
        if d > dist[u]:
            continue
        for v, L in adj[u]:
            if v in region and d + L < dist.get(v, math.inf):
                dist[v] = d + L
                heapq.heappush(q, (d + L, str(v), v))
    return dist


def _bisect(comp, pop, adj, k):
    """A connected piece cut into k parts of about equal population (user report 21-Oct-2026: OZs of 69,074 and
    68,397 beside OZs of 12,063 - parts grown from far-apart seeds were unequal, the middle left over): the piece
    halved along its longest way (A and B its two far ends, along the pipes) at the population share k1 / k - the
    nodes in the order of dist(A) - dist(B) (ties: nearer A first), the first ones to A - and each half again. A bit
    of a half not joined to the rest of it (equal values behind A, cut apart) goes to the other half, which it
    touches - so every part is connected along its own pipes; the cut is then moved (BISECT_TRIES times at most)
    until A's half, so mended, is nearest to its share."""
    region = set(comp)
    if k <= 1 or len(comp) < 2:
        return [list(comp)]
    a = max(_dist_in(region, adj, [comp[0]]).items(), key=lambda kv: (kv[1], str(kv[0])))[0]
    da = _dist_in(region, adj, [a])
    b = max(da.items(), key=lambda kv: (kv[1], str(kv[0])))[0]
    db = _dist_in(region, adj, [b])
    order = sorted(comp, key=lambda n: (round(da[n] - db[n], 6), da[n], str(n)))
    k1 = k // 2
    target = sum(pop[n] for n in comp) * k1 / k

    def halves(cut):
        one, two = set(order[:cut]), set(order[cut:])
        for mine, other, seed, d in ((one, two, a, da), (two, one, b, db)):
            if seed not in mine:                            # (the far end itself fell to the other side)
                seed = min(mine, key=lambda n: (d[n], str(n)))
            keep = set(_dist_in(mine, adj, [seed]))
            other |= mine - keep
            mine &= keep
        return one, two

    cum = list(itertools.accumulate(pop[n] for n in order))
    lo, hi = 1, len(order) - 1
    cut = min(max(bisect.bisect_left(cum, target) + 1, lo), hi)
    best = None
    for _ in range(BISECT_TRIES):
        one, two = halves(cut)
        got = sum(pop[n] for n in one)
        if one and two and (best is None or abs(got - target) < best[0]):
            best = (abs(got - target), one, two)
        if abs(got - target) <= 0.01 * target or lo >= hi:
            break
        if got < target:
            lo = cut + 1
        else:
            hi = cut - 1
        cut = min(max((lo + hi) // 2, 1), len(order) - 1)
    if best is None:
        return [list(comp)]
    _, one, two = best
    return _bisect(sorted(one, key=str), pop, adj, k1) + _bisect(sorted(two, key=str), pop, adj, k - k1)


def _site(nodes, xy, pop, mem):
    """The highest ground near the middle (by population) of these nodes."""
    tot = sum(pop[n] for n in mem)
    wt = {n: (pop[n] if tot > 0 else 1.0) for n in mem}
    cx = sum(xy[n][0] * wt[n] for n in mem) / sum(wt.values())
    cy = sum(xy[n][1] * wt[n] for n in mem) / sum(wt.values())
    near = sorted(mem, key=lambda n: (xy[n][0] - cx) ** 2 + (xy[n][1] - cy) ** 2)[:15]
    return max(near, key=lambda n: (nodes[n].get("elev") is not None, nodes[n].get("elev") or 0.0,
                                    -((xy[n][0] - cx) ** 2 + (xy[n][1] - cy) ** 2)))


def plan(net, ohts, crit, city_pop=None, bar=None, loops=None):
    """bar = {OHT name: nodes it must not take} - nodes the design left below 17 m in its OZ; loops: see the module
    text."""
    nodes, pipes = net["nodes"], net["pipes"]
    adj = {n: [] for n in nodes}
    for pid, p in pipes.items():
        if not p.get("closed"):
            adj[p["a"]].append((p["b"], p["length"]))
            adj[p["b"]].append((p["a"], p["length"]))
    ppc = _v(crit, "persons_per_connection")
    city = city_pop or sum(float(v.get("pop") or 0) for v in nodes.values())
    pop = {n: float(v.get("pop") or 0.0) for n, v in nodes.items()}
    kl = _demands(nodes, pop, crit, city)[2]
    max_pop = min(_v(crit, "oz_max_population"), _v(crit, "oz_max_connections") * ppc)
    rh = _v(crit, "residual_head_m")
    slope = _v(crit, "existing_oht_head_loss_m_per_km") / 1000.0
    bar = {k: set(v) for k, v in (bar or {}).items()}
    src = {o["name"]: o["node"] for o in ohts}
    # the highest ground an OHT with a given staging gives 17 m at (before the head lost in the pipes)
    gtop = {o["name"]: (nodes[o["node"]]["elev"] + float(o["staging_m"]) - rh
                        if o.get("staging_m") is not None and nodes[o["node"]].get("elev") is not None else None)
            for o in ohts}
    lh = {o["name"]: o.get("low_head") for o in ohts}
    loops = loops or []
    in_loop = {n: lp for lp in loops for n in lp["nodes"]}
    free = {n for n, lp in in_loop.items() if lp["mode"] == "keep"}         # a loop kept as drawn: no population limit
    tops = {k: (t if lh[k] == "new_oht" else None) for k, t in gtop.items()}      # only these give up higher ground
    bar = {k: v for k, v in bar.items() if tops.get(k) is not None}
    high = {}                                                # node -> the OHT that could not serve it at 17 m

    def too_high(k, u, d):
        if u == src.get(k):
            return False
        if u in bar.get(k, ()):
            return True
        t, e = tops.get(k), nodes[u].get("elev")
        return t is not None and e is not None and e > t - slope * d

    # ---- the given OHTs grow along the pipes while they have room
    # (a node too high for it is passed through - the water flows on to lower ground beyond - but not counted)
    owner, load, pq, parent = {}, {}, [], {}
    for o in ohts:
        cap = o.get("capacity_kl")
        load[o["name"]] = [0.0, 0.0, cap / dm.storage_share(crit) if cap else math.inf]
        heapq.heappush(pq, (0.0, str(o["node"]), o["node"], o["name"], None, 0.0))
    while pq:
        d, _, u, k, par, run = heapq.heappop(pq)
        if u in owner:
            continue
        hi = too_high(k, u, d)
        if hi and run > PASS_HIGH_M:
            continue                                         # a high area, not a high spot: not crossed
        lp, lk, mk = load[k]
        if not hi and (lp + pop[u] > max_pop and u not in free or lk + kl[u] > mk) and lp > 0:
            continue                                         # no room: another OHT (or a new one) takes it
        owner[u], parent[u] = k, par
        if hi:
            high[u] = k
        else:
            load[k][0] += pop[u]
            load[k][1] += kl[u]
        for v, L in adj[u]:
            if v not in owner:
                heapq.heappush(pq, (d + L, str(v), v, k, u, (run if hi else 0.0) + L))
    # the nodes too high for their OHT that no other node of its OZ is fed through: to a new OHT; those on the way
    # to lower ground stay (below 17 m - reported)
    kids = collections.defaultdict(list)
    for u, p in parent.items():
        if p is not None:
            kids[p].append(u)
    for k, s0 in src.items():
        if s0 not in owner or owner[s0] != k:
            continue
        order, st = [], [s0]
        while st:
            u = st.pop()
            order.append(u)
            st.extend(kids[u])
        need = {}
        for u in reversed(order):
            need[u] = u not in high or any(need[c] for c in kids[u])
        for u in order:
            if not need[u]:
                del owner[u]

    # ---- the area left over: pieces (connected), each with new OHTs at 50,000 per OZ
    left = {n for n in nodes if n not in owner and adj[n]}
    proposed, seen = [], set()
    xy = {n: v["xy"] for n, v in nodes.items()}
    for start in sorted(left, key=str):
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v, _ in adj[u]:
                if v in left and v not in seen:
                    seen.add(v)
                    stack.append(v)
        P = sum(pop[n] for n in comp)
        own = in_loop.get(comp[0])                           # a piece of a zone loop (closed at its boundary)
        if own is not None and any(in_loop.get(n) is not own for n in comp):
            own = None
        if P / ppc < _v(crit, "dma_min_connections") and own is None:
            continue                                         # too small for an OHT of its own: stays with a neighbour
        if own is not None and own["mode"] == "keep":
            parts = [comp]                                   # one OZ as drawn, whatever its size
        else:
            k = max(1, math.ceil(P / (0.95 * max_pop)))
            parts = _bisect(comp, pop, adj, k)
            while max(sum(pop[n] for n in m) for m in parts) > max_pop and k < len(comp):
                k += 1                                       # a part still above 50,000: one more OHT
                parts = _bisect(comp, pop, adj, k)
        next_to = sorted({owner[v] for u in comp for v, _ in adj[u] if v in owner}, key=str)
        for mem in parts:
            why = {"kind": "proposed", "piece": str(start), "piece_population": round(P), "piece_nodes": len(comp),
                   "parts": len(parts),
                   "next_to": next_to, "loop": own["name"] if own is not None else None,
                   "loop_mode": own["mode"] if own is not None else None}
            proposed.append({"name": f"_P{len(proposed) + 1}", "node": _site(nodes, xy, pop, mem), "capacity_kl": None,
                             "staging_m": None, "tubewells": 0, "proposed": True, "_members": mem, "why": why})
    # the OZs as found: the given OHTs' areas, the proposed ones' parts; a left-over piece too small for an OHT
    # joins the OZ next to it (which make_zones then flags if it is now above its capacity)
    assign = dict(owner)
    for p in proposed:
        for n in p.pop("_members"):
            assign[n] = p["name"]
    # a small left-over piece: to the neighbouring OZ that still has room for it - a new / proposed OHT first, else
    # the one with the most room; only when none has room, to the one least over (flagged); a piece touching no
    # OZ at all has no pipe to any OHT (reported)
    room_kl = {o["name"]: (o["capacity_kl"] / dm.storage_share(crit) if o.get("capacity_kl") else math.inf)
               for o in list(ohts) + proposed}
    lp = collections.defaultdict(float)
    lk = collections.defaultdict(float)
    for n, k in assign.items():
        lp[k] += pop[n]
        lk[k] += kl[n]
    def serves(k, piece):
        """An OHT that gives the piece 17 m on its ground (no staging given: the design finds one that does)."""
        t = tops.get(k)
        return not (bar.get(k, set()) & set(piece)) and (
            t is None or all(nodes[n].get("elev") is None or nodes[n]["elev"] <= t for n in piece))

    todo = {n for n in nodes if n not in assign and adj[n]}
    while todo:
        progress = False
        for start in sorted(todo, key=str):
            if start not in todo:
                continue
            piece, stack = [start], [start]
            todo.discard(start)
            while stack:
                u = stack.pop()
                for v, _ in adj[u]:
                    if v in todo:
                        todo.discard(v)
                        piece.append(v)
                        stack.append(v)
            near = {assign[v] for u in piece for v, _ in adj[u] if v in assign}
            if not near:
                continue
            pp, pk = sum(pop[n] for n in piece), sum(kl[n] for n in piece)

            def spare(k):
                return min(max_pop - lp[k] - pp, room_kl[k] - lk[k] - pk)
            k = max(near, key=lambda k: (serves(k, piece), spare(k) >= 0, room_kl[k] == math.inf, spare(k), str(k)))
            for n in piece:
                assign[n] = k
            lp[k] += pp
            lk[k] += pk
            progress = True
        todo = {n for n in nodes if n not in assign and adj[n]
                and any(v in assign for v, _ in adj[n])}
        if not progress:
            break
    # a zone loop to merge: whole to the neighbouring OZ joined to it by most of its boundary pipes (ties: by name);
    # those pipes open again, the OHTs proposed inside it are not needed
    for lp in loops:
        if lp["mode"] != "merge":
            continue
        inside = lp["nodes"]
        if any(o["node"] in inside for o in ohts):
            lp["note"] = "an OHT given inside the loop: not merged"
            continue
        votes, own_oz = collections.Counter(), {assign.get(n) for n in inside}
        for pid in lp["boundary"]:
            p = pipes[pid]
            o_ = p["b"] if p["a"] in inside else p["a"]
            if assign.get(o_) is not None and assign[o_] not in own_oz:
                votes[assign[o_]] += 1
        if not votes:
            lp["note"] = "no neighbouring OZ joined to it by a pipe: not merged"
            continue
        k = min(votes, key=lambda x: (-votes[x], str(x)))
        for pid in lp["boundary"]:
            p = pipes[pid]
            if assign.get(p["b"] if p["a"] in inside else p["a"]) == k:
                p["closed"] = False
        for n in inside:
            assign[n] = k
        lp["merged_into"] = k
    if any(lp.get("merged_into") for lp in loops):
        held = set(assign.values())
        proposed = [p for p in proposed if p["name"] in held]
    names = {o["name"] for o in ohts}
    import re
    k0 = max([int(m.group(1)) for m in (re.match(r"^Prop-OHT-(\d+)$", nm) for nm in names) if m] or [0])
    ren = {}
    for i, p in enumerate(proposed, 1):                      # numbered on after the new tanks already drawn
        nm = f"Prop-OHT-{k0 + i}"
        while nm in names:
            nm += "'"
        names.add(nm)
        ren[p["name"]] = p["name"] = nm
    assign = {n: ren.get(k, k) for n, k in assign.items()}
    for lp in loops:
        if lp.get("merged_into"):
            lp["merged_into"] = ren.get(lp["merged_into"], lp["merged_into"])
    z = make_zones(net, list(ohts) + proposed, crit, city, assign=assign)
    z["proposed"] = proposed
    z["why"] = {o["name"]: {"kind": "given", "existing": o.get("capacity_kl") is not None} for o in ohts}
    z["why"].update({p["name"]: p["why"] for p in proposed})
    # the pipes still closed at the zone loops: boundary valves too
    shut = {pid for lp in loops for pid in lp["boundary"] if pipes[pid].get("closed")}
    z["closed_pipes"] = sorted(set(z["closed_pipes"]) | shut, key=str)
    z["loops"] = []
    dmin = _v(crit, "dma_min_connections")
    for lp in loops:
        P = sum(pop[n] for n in lp["nodes"])
        zs = sorted({z["oz"][n] for n in lp["nodes"] if n in z["oz"]}, key=str)
        x = {"name": lp["name"], "mode": lp["mode"], "nodes": len(lp["nodes"]), "population": round(P),
             "connections": math.ceil(P / ppc), "zones": zs, "boundary_pipes": len(lp["boundary"]),
             "over": P > max_pop + 1e-9, "under": P / ppc < dmin, "max_population": max_pop,
             "min_connections": dmin, "merged_into": lp.get("merged_into"), "note": lp.get("note")}
        if lp["mode"] == "keep" and len(zs) > 1:            # the loop's pipes inside are not one network
            x["note"] = f"its pipes inside form {len(zs)} separate pieces - an OZ each; join them to make it one"
        z["loops"].append(x)
        if lp["mode"] == "keep":                             # over the limit as the user chose: a warning, not an error
            for f in z["flags"]:
                if f["zone"] in zs and f["level"] == "error":
                    f["level"] = "warn"
                    f["text"] += f" - kept as drawn: zone loop {lp['name']} (user's choice)"
                    f["hi"] = f.get("hi", f["text"]) + f" - zone लूप {lp['name']} जैसा खींचा वैसा रखा (आपका चुनाव)"
    # an existing OHT keeping ground its staging cannot give 17 m: a VFD pump at its outlet (sized by the design)
    for o in ohts:
        k, t = o["name"], gtop.get(o["name"])
        if o.get("low_head") != "vfd" or t is None:
            continue
        hi = [n for n, kk in z["oz"].items() if kk == k and (nodes[n].get("elev") or -math.inf) > t]
        if hi:
            z["flags"].append({"zone": k, "level": "warn", "text":
                               f"{k}: {len(hi)} nodes on ground above GL {t:.2f} m - its staging {float(o['staging_m']):g} m "
                               f"cannot give them 17 m: a VFD pump at its outlet (CPHEEO Table 2.7 S.No.10 p173), "
                               f"sized by the Design",
                               "hi": f"{k}: {len(hi)} junctions GL {t:.2f} m से ऊँची ज़मीन पर - इसकी staging "
                                     f"{float(o['staging_m']):g} m वहाँ 17 m नहीं दे सकती: outlet पर VFD pump (CPHEEO "
                                     f"Table 2.7 S.No.10 p173), जिसका size Design बताएगा"})
    # the nodes an OHT could not serve at 17 m: where they went
    z["too_high"] = {}
    for o in ohts:
        k = o["name"]
        mine = [n for n, kk in high.items() if kk == k]
        if not mine or not tops.get(k) and not bar.get(k):
            continue
        went = collections.Counter(z["oz"].get(n) for n in mine)
        z["too_high"][k] = {"nodes": len(mine), "population": round(sum(pop[n] for n in mine)),
                            "to": {t: c for t, c in went.items() if t not in (None, k)},
                            "stayed": went.get(k, 0), "unserved": went.get(None, 0)}
        to = ", ".join(sorted(z["too_high"][k]["to"]))
        z["flags"].append({"zone": k, "level": "warn", "text":
                           f"{k}: ground too high for its staging {float(o['staging_m']):g} m (17 m only up to GL "
                           f"{tops[k]:.2f} m, less the head lost in the pipes) is not given to it" +
                           (f" - new OHTs take it: {to}" if to else "") +
                           (f"; {went[k]} stay with it, below 17 m (water passes through them to lower ground, or a "
                            f"piece too small for an OHT of its own)" if went.get(k) else ""),
                           "hi": f"{k}: इसकी staging {float(o['staging_m']):g} m के लिए ऊँची ज़मीन (17 m केवल GL "
                                 f"{tops[k]:.2f} m तक, pipes के head loss घटाकर) इसे नहीं दी गई" +
                                 (f" - नई OHTs लेंगी: {to}" if to else "") +
                                 (f"; {went[k]} junctions इसी के पास, 17 m से कम (पानी उनसे होकर नीची ज़मीन तक जाता है, या "
                                  f"टुकड़ा अपनी OHT के लिए बहुत छोटा)" if went.get(k) else "")})
    return z
