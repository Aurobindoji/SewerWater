"""Steady-state hydraulics of a water distribution network - the app's own solver (no WaterGEMS / EPANET).

Global gradient method (Todini & Pilati 1988, the method EPANET uses): the heads of all junctions and the flows of
all pipes are found together by Newton iterations on
    energy      H_a - H_b = h(Q)            for every pipe a -> b
    continuity  inflow - outflow = demand   at every junction
with the head loss of CPHEEO eq 6.4 (p393, Hazen-Williams)
    h = 10.68 (Q / C)^1.852 L / D^4.87          Q m3/s, L and D m
and the minor losses as a longer pipe (CPHEEO 6.6(vi) p400: +10 %).

    net = {"nodes": {id: {"elev": m, "demand": L/s, "head": None | m}},     head given = OHT / reservoir
           "pipes": {id: {"a": node, "b": node, "length": m, "d_mm": internal mm, "C": 140}}}
    r = solve(net)
    r["head"][n], r["pressure"][n] (m), r["flow"][p] (L/s, + from a to b), r["velocity"][p] (m/s),
    r["hl_per_km"][p] (m/km), r["unsupplied"] (junctions with no path to a fixed head)

A node with a fixed head is an OHT / ESR (its lowest water level = ground + staging) or a reservoir. A closed pipe
("closed": True) carries nothing. A junction cut off from every fixed head gets no result and is listed.
"""
import collections
import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

N_HW = 1.852
K_HW = 10.68          # CPHEEO eq 6.4 (EPANET uses 10.67)
E_D = 4.87


def resistance(length_m, d_mm, c, minor=1.0):
    """r of h = r Q^1.852 (Q m3/s, h m)."""
    d = max(d_mm, 1.0) / 1000.0
    return K_HW * max(length_m, 0.1) * minor / (c ** N_HW * d ** E_D)


class Model:
    """The network's structure, built once: which junctions are fed, the matrix pattern, lengths. set_pipe() changes
    a pipe's diameter / C, set_head() a fixed head; solve() runs Newton from the last flows (warm start)."""

    def __init__(self, net, minor_loss=1.10, demand_factor=1.0):
        nodes, pipes = net["nodes"], net["pipes"]
        self.nodes, self.pipes, self.minor = nodes, pipes, minor_loss
        fixed = {n for n, v in nodes.items() if v.get("head") is not None}
        adj = collections.defaultdict(list)                   # junctions with a path to a fixed head
        for pid, p in pipes.items():
            if not p.get("closed"):
                adj[p["a"]].append(p["b"])
                adj[p["b"]].append(p["a"])
        seen, stack = set(fixed), list(fixed)
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        self.fixed = fixed
        self.junc = [n for n in nodes if n not in fixed and n in seen]
        self.unsupplied = sorted((n for n in nodes if n not in fixed and n not in seen), key=str)
        self.jx = {n: i for i, n in enumerate(self.junc)}
        self.live = [pid for pid, p in pipes.items() if not p.get("closed") and p["a"] in seen and p["b"] in seen]
        self.pk = {pid: k for k, pid in enumerate(self.live)}
        live = self.live
        self.L = np.array([max(pipes[p]["length"], 0.1) for p in live])
        self.d = np.array([max(pipes[p]["d_mm"], 1.0) for p in live])
        self.C = np.array([float(pipes[p].get("C", 140)) for p in live])
        self.ia = np.array([self.jx.get(pipes[p]["a"], -1) for p in live], dtype=int)
        self.ib = np.array([self.jx.get(pipes[p]["b"], -1) for p in live], dtype=int)
        self.ha = np.array([nodes[pipes[p]["a"]]["head"] if pipes[p]["a"] in fixed else 0.0 for p in live])
        self.hb = np.array([nodes[pipes[p]["b"]]["head"] if pipes[p]["b"] in fixed else 0.0 for p in live])
        self.dem = np.array([float(nodes[n].get("demand") or 0.0) * demand_factor / 1000.0 for n in self.junc])
        self.elev = np.array([float(nodes[n].get("elev") or 0.0) for n in self.junc])
        ia, ib = self.ia, self.ib
        self.ma, self.mb = ia >= 0, ib >= 0
        self.mab, self.ma_only, self.mb_only = self.ma & self.mb, self.ma & ~self.mb, self.mb & ~self.ma
        self.rows = np.concatenate([ia[self.ma], ib[self.mb], ia[self.mab], ib[self.mab]])
        self.cols = np.concatenate([ia[self.ma], ib[self.mb], ib[self.mab], ia[self.mab]])
        self._r()
        self.q = None

    def _r(self):
        self.r = K_HW * self.L * self.minor / (self.C ** N_HW * (self.d / 1000.0) ** E_D)
        self.area = np.pi * (self.d / 1000.0) ** 2 / 4

    def set_pipe(self, pid, d_mm, c):
        k = self.pk.get(pid)
        if k is None:
            return
        self.d[k], self.C[k] = max(d_mm, 1.0), float(c)
        self.r[k] = K_HW * self.L[k] * self.minor / (self.C[k] ** N_HW * (self.d[k] / 1000.0) ** E_D)
        self.area[k] = math.pi * (self.d[k] / 1000.0) ** 2 / 4

    def set_head(self, node, h):
        self.nodes[node]["head"] = h
        for k, pid in enumerate(self.live):
            p = self.pipes[pid]
            if p["a"] == node:
                self.ha[k] = h
            if p["b"] == node:
                self.hb[k] = h

    def solve(self, tol=1e-7, max_iter=200, start=None):
        nodes, pipes, live = self.nodes, self.pipes, self.live
        ia, ib, ha, hb, r = self.ia, self.ib, self.ha, self.hb, self.r
        m, nj = len(live), len(self.junc)
        if start:
            q = np.array([start[p] / 1000.0 if p in start and abs(start[p]) > 1e-9 else 0.3 * self.area[k]
                          for k, p in enumerate(live)])
        elif self.q is not None:
            q = self.q.copy()
        else:
            q = 0.3 * self.area                                       # start: 0.3 m/s everywhere
        H = np.zeros(nj)
        ma, mb, mab, ma_only, mb_only = self.ma, self.mb, self.mab, self.ma_only, self.mb_only
        it, dq = 0, 0.0
        for it in range(1, max_iter + 1):
            aq = np.maximum(np.abs(q), 1e-8)
            g = N_HW * r * aq ** (N_HW - 1)                           # dh/dQ
            g = np.maximum(g, 1e-6)
            pinv = 1.0 / g
            y = q - r * aq ** (N_HW - 1) * q / g                      # = q (1 - 1/n)
            vals = np.concatenate([pinv[ma], pinv[mb], -pinv[mab], -pinv[mab]])
            F = -self.dem.copy()
            np.add.at(F, ia[ma], -y[ma])                              # pipe leaves a
            np.add.at(F, ib[mb], y[mb])                               # pipe enters b
            np.add.at(F, ia[ma_only], pinv[ma_only] * hb[ma_only])    # b a fixed head
            np.add.at(F, ib[mb_only], pinv[mb_only] * ha[mb_only])    # a a fixed head
            if nj:
                A = sp.csc_matrix((vals, (self.rows, self.cols)), shape=(nj, nj))
                H = np.atleast_1d(spl.spsolve(A, F, permc_spec="MMD_AT_PLUS_A"))     # A is symmetric
            Ha = np.where(ma, H[np.maximum(ia, 0)] if nj else 0.0, ha)
            Hb = np.where(mb, H[np.maximum(ib, 0)] if nj else 0.0, hb)
            qn = y + pinv * (Ha - Hb)
            dq = np.abs(qn - q).max() if m else 0.0
            q = qn
            if dq < tol:
                break
        self.q = q
        head = {n: float(nodes[n]["head"]) for n in self.fixed}
        head.update(zip(self.junc, H.tolist()))
        qa = np.abs(q)
        flow = dict(zip(live, (q * 1000.0).tolist()))
        vel = dict(zip(live, (qa / self.area).tolist()))
        hlk = dict(zip(live, (r * qa ** N_HW / self.L * 1000.0).tolist()))
        for pid in pipes:
            if pid not in flow:
                flow[pid], vel[pid], hlk[pid] = 0.0, 0.0, 0.0
        pressure = {n: head[n] - float(nodes[n].get("elev") or 0.0) for n in self.fixed}
        pressure.update(zip(self.junc, (H - self.elev).tolist()))
        return {"head": head, "pressure": pressure, "flow": flow, "velocity": vel, "hl_per_km": hlk,
                "iterations": it, "converged": (dq < tol) if m else True, "unsupplied": self.unsupplied}


def solve(net, minor_loss=1.10, demand_factor=1.0, tol=1e-7, max_iter=200, start=None):
    """start = the "flow" of an earlier result of (nearly) the same network: Newton starts from it (fewer
    iterations when a design changes a few pipes and runs again)."""
    return Model(net, minor_loss, demand_factor).solve(tol=tol, max_iter=max_iter, start=start)
