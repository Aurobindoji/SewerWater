"""Uniform-flow hydraulics of a circular sewer: Manning, constant n (CPHEEO p187 / p190, Table 3.12).

Taken unchanged from the original scripts design_check.py (manning_partial, uniform_flow) and sewer_design.py
(q_part, slope_for_dd, slope_for_velocity). Units: diameter mm, flow L/s, velocity m/s, slope m/m.
"""
import math


def manning_partial(D, S, n, dd):
    """Circular pipe running part full at depth ratio dd: (area m2, velocity m/s). D in metres."""
    th = 2 * math.acos(1 - 2 * dd)
    A = D * D / 8 * (th - math.sin(th))
    R = A / (D * th / 2)
    return A, (1 / n) * R ** (2 / 3) * S ** 0.5


def uniform_flow(q_lps, d_mm, slope, n):
    """Normal (uniform-flow) depth ratio and velocity by Manning for flow q in a circular
    pipe - the partial-flow method of DPR design. Returns (d/D, v) or (None, None) when it
    cannot be computed (no flow, zero/adverse slope, flow above the pipe's maximum capacity)."""
    if not q_lps or not d_mm or not slope or slope <= 0 or not n:
        return None, None
    D, Q = d_mm / 1000.0, abs(q_lps) / 1000.0
    a_max, v_max = manning_partial(D, slope, n, 0.938)       # maximum discharge at d/D ~0.94
    if Q > a_max * v_max:
        return None, None
    lo, hi = 1e-6, 0.938
    for _ in range(60):
        mid = (lo + hi) / 2
        a, v = manning_partial(D, slope, n, mid)
        lo, hi = (mid, hi) if a * v < Q else (lo, mid)
    a, v = manning_partial(D, slope, n, hi)
    return hi, v


def q_part(d_mm, s, n, dd):
    """Discharge (L/s) of a circular pipe at depth ratio dd."""
    a, v = manning_partial(d_mm / 1000.0, s, n, dd)
    return 1000.0 * a * v


def slope_for_dd(q, d_mm, n, dd_lim):
    """Smallest slope at which flow q runs at d/D = dd_lim (Q is proportional to sqrt(S))."""
    if not q:
        return 0.0
    q1 = q_part(d_mm, 1.0, n, dd_lim)
    return (abs(q) / q1) ** 2


def slope_for_velocity(q, d_mm, n, vmin):
    """Smallest slope giving uniform-flow velocity >= vmin for flow q, or None.
    Direct solution: the flow area must be A = Q / v; find the depth giving that area
    (area grows with depth), then Manning gives S = (v n / R^(2/3))^2."""
    if not q:
        return None
    D, Q = d_mm / 1000.0, abs(q) / 1000.0
    A_need = Q / vmin
    a_full = math.pi * D * D / 4
    if A_need >= a_full * 0.999:
        return None                              # would need the pipe to run (over) full
    lo, hi = 1e-7, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        th = 2 * math.acos(1 - 2 * mid)
        a = D * D / 8 * (th - math.sin(th))
        lo, hi = (mid, hi) if a < A_need else (lo, mid)
    th = 2 * math.acos(1 - 2 * hi)
    a = D * D / 8 * (th - math.sin(th))
    Rh = a / (D * th / 2)
    return (vmin * n / Rh ** (2 / 3)) ** 2
