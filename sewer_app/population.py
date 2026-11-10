"""Population forecast of a scheme as in the Riverside DPR (sheet 'T', Technical statement) - user decision 22-Oct-2026:
the user gives the base-year population and the census populations of the town on the page; the +15 and +30 years
population and the floating population follow by themselves, and the design runs on them.

    f = forecast(base_year=2027, base_pop=224207, census=[(1971, 672634), (1981, 825717), ...])
    f["design"] -> {"init": ..., "mid": ..., "ult": ...}       # population incl. the equivalent floating population

Methods (Riverside 'T' rows 44-161; CPHEEO water manual 2.2): from the census the increase per decade (X), the
incremental increase (Y) and the decadal growth rate (r, geometric mean of the decades' rates, as Riverside U54); then
from the base-year population with n = decades after the base year:
    arithmetical  P = P0 + n X                incremental  P = P0 + n X + n (n + 1) / 2 Y        geometrical  P = P0 (1 + r)^n
each rounded up to 5 (CEILING(P, 5)). The adopted method (Riverside: geometrical) gives the +15 and +30 years
population. Without census figures the default decadal rate (data/dpr_sewer.json 'forecast') is used, geometrically.
Floating and institutional population = share x population; its sewage as an equivalent population =
floating x floating lpcd / water supply lpcd (Riverside 'Tech ' rows 131-134: 10 %, 45 / 150).
"""
import json
import math
import os

from . import DATA_DIR

METHODS = ("arithmetical", "incremental", "geometrical")
STAGE_YEARS = {"init": 0, "mid": 15, "ult": 30}


def settings():
    with open(os.path.join(DATA_DIR, "dpr_sewer.json"), encoding="utf-8") as fh:
        return json.load(fh)["forecast"]["value"]


def parse_census(text):
    """'1971 672634, 1981 825717' / one pair per line / [[y, p], ...] -> sorted [(year, population)]."""
    if isinstance(text, (list, tuple)):
        pairs = [(int(y), float(p)) for y, p in text]
    else:
        import re
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(text or "").replace(",", " "))]
        if len(nums) % 2:
            raise ValueError("census: वर्ष और आबादी जोड़ों में दें, जैसे 2001 1374963, 2011 1636569")
        pairs = [(int(nums[i]), nums[i + 1]) for i in range(0, len(nums), 2)]
    for y, p in pairs:
        if not 1800 <= y <= 2200 or p <= 0:
            raise ValueError(f"census: '{y} {p:g}' ठीक नहीं - वर्ष 1800-2200 और आबादी 0 से अधिक")
    out = sorted(dict(pairs).items())
    return out


def growth(census):
    """Per interval: increase per decade, incremental increase, decadal rate; and their averages X, Y, r
    (Riverside 'T' L54, P54, U54)."""
    rows = []
    for (y0, p0), (y1, p1) in zip(census, census[1:]):
        dec = (y1 - y0) / 10.0
        inc = (p1 - p0) / dec
        rate = (p1 / p0) ** (1.0 / dec) - 1.0
        rows.append({"from": y0, "to": y1, "increase": inc, "rate": rate})
    for a, b in zip(rows, rows[1:]):
        b["incremental"] = b["increase"] - a["increase"]
    X = sum(r["increase"] for r in rows) / len(rows) if rows else None
    incs = [r["incremental"] for r in rows if "incremental" in r]
    Y = sum(incs) / len(incs) if incs else 0.0
    rates = [r["rate"] for r in rows]
    if rates and all(x > 0 for x in rates):
        r = math.prod(rates) ** (1.0 / len(rates))       # geometric mean of the decadal rates, as Riverside U54
    elif rates:
        r = sum(rates) / len(rates)
    else:
        r = None
    return rows, X, Y, r


def xround(x):
    """Excel's ROUND(x, 0) (half away from zero), so that the DPR sheet's formulas give the same figures."""
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


def ceil5(x):
    return math.ceil(x / 5.0 - 1e-9) * 5


def forecast(base_year, base_pop, census=None, method=None, sewage_lpcd=None, S=None):
    """The forecast dict: base_year, years, census, growth rows, X, Y, r (fraction per decade), per method the
    population of each stage, adopted method, pop (without floating), floating, equivalent floating, design (pop +
    equivalent floating) - stages 'init' / 'mid' / 'ult'."""
    S = S or settings()
    base_year, base_pop = int(base_year), float(base_pop)
    census = parse_census(census) if census else []
    rows, X, Y, r = growth(census) if len(census) >= 2 else ([], None, 0.0, None)
    default = r is None
    if default:
        r = S["default_decadal_rate"]
    method = method or S["adopted_method"]
    if method not in METHODS or (X is None and method != "geometrical"):
        method = "geometrical"
    by = {}
    for m in METHODS:
        if m != "geometrical" and X is None:
            continue
        by[m] = {}
        for tag, add in STAGE_YEARS.items():
            n = add / 10.0
            if tag == "init":
                by[m][tag] = base_pop
            elif m == "arithmetical":
                by[m][tag] = ceil5(base_pop + n * X)
            elif m == "incremental":
                by[m][tag] = ceil5(base_pop + n * X + n * (n + 1) * 0.5 * Y)
            else:
                by[m][tag] = ceil5(base_pop * (1 + r) ** n)
    pop = by[method]
    water = (sewage_lpcd / S["return_factor"]) if sewage_lpcd else S["water_supply_lpcd"]
    eq = S["floating_lpcd"] / water
    fl = {t: xround(p * S["floating_share"]) for t, p in pop.items()}
    eqf = {t: xround(fl[t] * eq) for t in pop}
    return {"base_year": base_year, "years": {t: base_year + a for t, a in STAGE_YEARS.items()}, "census": census,
            "growth": rows, "X": X, "Y": Y, "r": r, "default_rate": default, "by_method": by, "method": method,
            "pop": pop, "floating_share": S["floating_share"], "floating": fl, "floating_lpcd": S["floating_lpcd"],
            "water_lpcd": water, "equivalent": eqf, "design": {t: pop[t] + eqf[t] for t in pop}}


def summary(f):
    """One line for the log / page."""
    src = (f"census {f['census'][0][0]}-{f['census'][-1][0]}, " if f["census"] else "no census - default ")
    return (f"population forecast ({f['method']}, {src}r = {f['r'] * 100:.2f} % per decade): "
            + ", ".join(f"{f['years'][t]} {f['pop'][t]:,.0f} + floating {f['equivalent'][t]:,.0f} = {f['design'][t]:,.0f}"
                        for t in ("init", "mid", "ult")))
