"""Rising main of a pumping station: DI size, friction head and approximate cost (zoning comparison, PFR stage).

Rates: data/rising_main_rates.json - laying and excavation from the Springfield SOR 2025-26 (user decision
12-Oct-2026), DI K-7 supply (Rate_2025-26 M.193), specials 10 % and thrust blocks (Elmwood DPR) as before.
Size: the smallest DI size with a supply rate whose velocity at the peak flow is not above max_velocity_mps; when
even the largest (600 mm) is too small, parallel mains of one size. Length = straight distance x route_factor.
Friction: Hazen-Williams. Cost per m = supply + laying + specials + excavation (L x (D+0.6) x (D+1.0)) + one thrust
block per 200 m (block quantities of the Elmwood DPR, 200-400 mm; other sizes scaled by (D / nearest)^2 - assumed).
"""
import json
import math
import os

from . import DATA_DIR

RATES_FILE = os.path.join(DATA_DIR, "rising_main_rates.json")


def load_rates(path=None):
    with open(path or RATES_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def size(q_lps, K):
    """(number of parallel mains, DI dia mm, velocity m/s)."""
    vmax = K["design"]["max_velocity_mps"]["value"]
    dias = sorted(int(d) for d in K["pipe_supply_di_k7"]["by_dia_mm"])
    n = 1
    while True:
        for d in dias:
            v = (q_lps / n / 1000.0) / (math.pi * (d / 1000.0) ** 2 / 4)
            if v <= vmax:
                return n, d, v
        n += 1


def friction_m(q_lps, n, d_mm, length_m, K):
    """Hazen-Williams head loss (m) in one of n parallel mains."""
    C = K["design"]["hazen_williams_c"]["value"]
    q = q_lps / n / 1000.0
    return 10.67 * length_m * q ** 1.852 / (C ** 1.852 * (d_mm / 1000.0) ** 4.87)


def rate_per_m(d_mm, K):
    """(Rs per m of one main, {part: Rs per m})."""
    sup = K["pipe_supply_di_k7"]["by_dia_mm"][str(d_mm)]["rate"]
    lay_t = K["laying_di"]["by_dia_mm"]
    lay = lay_t[str(d_mm)]["rate"] if str(d_mm) in lay_t else None
    D = d_mm / 1000.0
    exc = (D + 0.6) * (D + 1.0) * K["excavation"]["rate"]
    tb = K["thrust_block"]
    blocks = {int(k): v for k, v in tb["per_block"].items()}
    near = min(blocks, key=lambda k: abs(k - d_mm))
    f = (d_mm / near) ** 2
    block = f * (blocks[near]["rcc_cum"] * tb["rcc_rate"] + blocks[near]["steel_kg"] * tb["steel_rate"])
    parts = {"DI K-7 supply": sup, "laying (SOR)": lay or 0.0,
             "specials": K["specials_fraction"]["value"] * sup, "excavation (SOR 2001)": exc,
             "thrust blocks": block / tb["spacing_m"]}
    return sum(parts.values()), parts


def rising_main(q_peak_lps, straight_m, K=None):
    """Rising main from a pumping station over a straight distance. Returns a dict: n, dia, velocity, length,
    friction_m, delivery_m, head_m (delivery + friction), per_m, parts, cost_lakh."""
    K = K or load_rates()
    n, d, v = size(q_peak_lps, K)
    L = straight_m * K["design"]["route_factor"]["value"]
    hf = friction_m(q_peak_lps, n, d, L, K)
    per_m, parts = rate_per_m(d, K)
    delivery = K["design"]["delivery_head_m"]["value"]
    return {"n": n, "dia": d, "velocity": v, "length": L, "friction_m": hf, "delivery_m": delivery,
            "head_m": hf + delivery, "per_m": per_m, "parts": parts, "cost_lakh": n * L * per_m / 1e5}
