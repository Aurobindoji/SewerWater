"""Population projection of a water supply scheme as in the Elmwood water estimate (sheet 'T', Technical statement) -
user request 30-Oct-2026: the base year and its population are given on the page with the census populations of
the town; the population of the base year, +15 years (middle) and +30 years (design) by five methods is shown, one is
adopted (default geometrical, as the Elmwood and Riverside DPRs), and the design runs on it.

    f = project(base_year=2027, base_pop=125180, census="1981 825717, 1991 1139236, 2001 1374963, 2011 1636569")
    f["by_method"]["geometrical"] -> {"init": 125180, "mid": ..., "ult": ...};  f["adopted"], f["ratio"]

From the census (Elmwood 'T' rows 44-55): the increase per decade of each interval (L), the incremental increase (P)
and the decadal growth rate (U, ((P1 / P0) ^ (1 / decades)) - 1); their averages X, Y and r (r: the geometric mean of
the rates, as T U54). Each method projects the census population itself from its last year Pc (as the Elmwood from its
2025 figure), n = decades after that year:
    arithmetical   T = Pc + n X                           (T rows 85-107)
    incremental    T = Pc + n X + n (n + 1) / 2 Y         (T rows 111-135)
    geometrical    T = Pc (1 + r) ^ n                     (T rows 140-161)
    decreasing     decade by decade from Pc: the rate r(k) = r(last) + k S, S the average change of the decadal
                   rates (negative where they fall), P(k) = P(k-1) (1 + r(k)), a part of a decade at its rate
                   (CPHEEO Manual on Water Supply 2024 Part A Annexure 2.8 p979 Eq. 2.5, its example p984; user
                   request 9-Nov-2026 - for a town whose rate of growth falls)
    simple graph   T = Pc + b (year - census year)        b: the slope of the straight line fitted to the census
    semi-log graph T = Pc exp(c (year - census year))     c: the slope of the line fitted to ln(census population)
and the project's population of a year P = P0 x T(year) / T(base year), P0 the base-year population given - the
census may be the town's, the project a part of it (absolute increases of the town are not added to a part of it);
each rounded up to 5 (CEILING(P, 5)). The two graph methods: the Elmwood reads them off a plot by hand; here the line is
fitted by least squares (the same figures every time - user decision 30-Oct-2026)."""
import math
import re

METHODS = ("arithmetical", "incremental", "geometrical", "decreasing", "graph", "semilog")
NAMES = {"arithmetical": ("Arithmetical Increase Method", "Arithmetical (समान वृद्धि)"),
         "incremental": ("Incremental Increase Method", "Incremental (बढ़ती वृद्धि)"),
         "geometrical": ("Geometrical Increase Method", "Geometrical (समान दर)"),
         "decreasing": ("Decreasing Rate of Growth Method", "Decreasing rate (घटती दर)"),
         "graph": ("Simple Graph Method (straight line fitted)", "Simple graph (सीधी रेखा)"),
         "semilog": ("Semi Log Graph Method (straight line fitted)", "Semi-log graph")}
DEFAULT = "geometrical"
STAGE_YEARS = {"init": 0, "mid": 15, "ult": 30}


def parse_census(text):
    """'1971 672634, 1981 825717' / one pair per line / [[y, p], ...] -> sorted [(year, population)]."""
    if isinstance(text, (list, tuple)):
        pairs = [(int(y), float(p)) for y, p in text]
    else:
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(text or "").replace(",", ""))]
        if len(nums) % 2:
            raise ValueError("census: वर्ष और आबादी जोड़ों में दें, जैसे 2001 1374963; 2011 1636569")
        pairs = [(int(nums[i]), nums[i + 1]) for i in range(0, len(nums), 2)]
    for y, p in pairs:
        if not 1800 <= y <= 2200 or p <= 0:
            raise ValueError(f"census: '{y} {p:g}' ठीक नहीं - वर्ष 1800-2200 और आबादी 0 से अधिक")
    return sorted(dict(pairs).items())


def growth(census):
    """Per interval (Elmwood 'T' rows 46-52): the increase per decade, the incremental increase, the decadal rate; and
    their averages X, Y, r (T L54, P54, U54)."""
    rows = []
    for (y0, p0), (y1, p1) in zip(census, census[1:]):
        dec = (y1 - y0) / 10.0
        rows.append({"from": y0, "to": y1, "increase": (p1 - p0) / dec, "rate": (p1 / p0) ** (1.0 / dec) - 1.0})
    for a, b in zip(rows, rows[1:]):
        b["incremental"] = b["increase"] - a["increase"]
    X = sum(r["increase"] for r in rows) / len(rows)
    incs = [r["incremental"] for r in rows if "incremental" in r]
    Y = sum(incs) / len(incs) if incs else None
    rates = [r["rate"] for r in rows]
    if all(x > 0 for x in rates):
        r = math.prod(rates) ** (1.0 / len(rates))           # the geometric mean of the rates, as Elmwood T U54
    else:                                                   # a decade of decline: the mean of the growth factors
        r = math.prod(1 + x for x in rates) ** (1.0 / len(rates)) - 1
    return rows, X, Y, r


def decreasing(census_last, rows, dy):
    """The decreasing rate of growth (CPHEEO Annexure 2.8 Eq. 2.5): the population dy years after the last census,
    decade by decade at r(last) + k S (not below 0), the part of a decade at its rate; S = the average change of the
    decadal rates (their consecutive differences - (r(last) - r(first)) / (intervals - 1)). None: fewer than two
    intervals."""
    if len(rows) < 2:
        return None
    pc, r0 = census_last[1], rows[-1]["rate"]
    S = (rows[-1]["rate"] - rows[0]["rate"]) / (len(rows) - 1)
    if dy <= 0:
        return pc * (1 + r0) ** (dy / 10.0)
    n = dy / 10.0
    m = int(math.floor(n + 1e-9))
    p = pc
    for k in range(1, m + 1):
        p *= 1 + max(0.0, r0 + k * S)
    return p * (1 + max(0.0, r0 + (m + 1) * S)) ** (n - m)


def decrease_s(rows):
    """S of the decreasing rate method: the average change of the decadal rates per decade, or None."""
    return (rows[-1]["rate"] - rows[0]["rate"]) / (len(rows) - 1) if len(rows) > 1 else None


def _slope(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0


def ceil5(x):
    return math.ceil(x / 5.0 - 1e-9) * 5


def project(base_year, base_pop, census, method=None, from_year=None):
    """The projection dict: base_year, years {init, mid, ult}, census, growth rows, X, Y, r, b (persons / year of the
    straight line), c (per year, of the semi-log line), by_method {method: {init, mid, ult}}, adopted, pop (the adopted
    method's), ratio {init: 1, mid, ult} to the base-year population, notes (Hindi / English pairs).
    from_year (user decision 7-Nov-2026: the wards' population of a year the user gives, e.g. 2025): base_pop is the
    population of that year, each method grows it to the base, middle and design years (its town projection of the
    year / of from_year); then from_year, from_pop and ratio_from {init, mid, ult} to it as well."""
    base_year, base_pop = int(base_year), float(base_pop)
    from_year = int(from_year) if from_year not in (None, "") else None
    if base_pop <= 0:
        raise ValueError("आधार वर्ष की आबादी 0 से अधिक दें")
    census = parse_census(census)
    if len(census) < 2:
        raise ValueError("कम से कम दो census (वर्ष और आबादी) दें - projection की वृद्धि उन्हीं से")
    if census[-1][0] > base_year:
        raise ValueError(f"census का वर्ष {census[-1][0]} आधार वर्ष {base_year} के बाद है")
    rows, X, Y, r = growth(census)
    years = [y for y, _ in census]
    b = _slope(years, [p for _, p in census])
    c = _slope(years, [math.log(p) for _, p in census])
    yc, pc = census[-1]
    by, town, tf = {}, {}, {}
    stages = dict(STAGE_YEARS, **({"from": from_year - base_year} if from_year else {}))
    for m in METHODS:
        if (m == "incremental" and Y is None) or (m == "decreasing" and len(rows) < 2):
            continue
        town[m] = {}
        for tag, add in stages.items():
            dy = base_year + add - yc
            n = dy / 10.0
            town[m][tag] = {"arithmetical": lambda: pc + n * X,
                            "incremental": lambda: pc + n * X + n * (n + 1) * 0.5 * Y,
                            "geometrical": lambda: pc * (1 + r) ** n,
                            "decreasing": lambda: decreasing(census[-1], rows, dy),
                            "graph": lambda: pc + b * dy,
                            "semilog": lambda: pc * math.exp(c * dy)}[m]()
        if town[m]["init"] <= 0 or min(town[m].values()) <= 0:
            del town[m]                                     # a line falling to nothing: no projection
            continue
        if from_year:
            tf[m] = town[m].pop("from")
            by[m] = {t: ceil5(base_pop * town[m][t] / tf[m]) for t in STAGE_YEARS}
        else:
            by[m] = {t: base_pop if t == "init" else ceil5(base_pop * v / town[m]["init"]) for t, v in town[m].items()}
    adopted = method if method in by else DEFAULT if DEFAULT in by else next(iter(by))
    pop = by[adopted]
    from_pop = base_pop if from_year else None
    if from_year:
        base_pop = float(pop["init"])                      # the base year's, of the adopted method
    notes = []
    if Y is None:
        notes.append(("incremental: तीन census चाहिए", "incremental: three census figures needed"))
    elif Y < 0:
        notes.append((f"औसत incremental वृद्धि ऋणात्मक ({Y:,.0f} प्रति दशक) - वृद्धि घट रही है",
                      f"the average incremental increase is negative ({Y:,.0f} per decade) - growth is slowing"))
    S = decrease_s(rows)
    if S is not None and S >= 0:                    # CPHEEO: the method is for a rate of growth falling
        notes.append((f"decreasing rate: दशक-वार वृद्धि दर घट नहीं रही (औसत बदलाव +{S * 100:.2f} % प्रति दशक) - CPHEEO "
                      f"Annexure 2.8: यह विधि घटती दर वाले शहर के लिए",
                      f"decreasing rate: the decadal rate of growth is not falling (average change +{S * 100:.2f} % "
                      f"per decade) - CPHEEO Annexure 2.8: the method is for a town whose rate falls"))
    hi = {m: v["ult"] / base_pop for m, v in by.items()}
    lo_m, hi_m = min(hi, key=hi.get), max(hi, key=hi.get)
    if hi[hi_m] > 2 * hi[lo_m]:
        notes.append((f"विधियों में बड़ा अंतर: +30 वर्ष पर {NAMES[lo_m][1]} {hi[lo_m]:.2f} गुना, {NAMES[hi_m][1]} "
                      f"{hi[hi_m]:.2f} गुना - अपनाई विधि सोचकर चुनें",
                      f"the methods differ widely: at +30 years {NAMES[lo_m][0]} x {hi[lo_m]:.2f}, {NAMES[hi_m][0]} "
                      f"x {hi[hi_m]:.2f} - choose the adopted method with care"))
    # town_ratio_from: the town's own growth from from_year by the adopted method (unrounded) - for the balancing
    # character Far-open of the wards (ui_api.far_open_balance, user decision 7-Nov-2026)
    extra = {"from_year": from_year, "from_pop": from_pop,
             "ratio_from": {t: pop[t] / from_pop for t in pop},
             "town_from": tf[adopted], "town_ratio_from": {t: town[adopted][t] / tf[adopted] for t in STAGE_YEARS}
             } if from_year else {}
    return {**extra, "base_year": base_year, "base_pop": base_pop,
            "years": {t: base_year + a for t, a in STAGE_YEARS.items()}, "census": census, "growth": rows,
            "X": X, "Y": Y, "r": r, "S": S, "b": b, "c": c, "town": town, "by_method": by, "adopted": adopted, "pop": pop,
            "ratio": {t: pop[t] / base_pop for t in pop}, "names": {m: NAMES[m] for m in by}, "notes": notes}


def summary(f):
    """One line for the log."""
    return (f"population projection ({NAMES[f['adopted']][0]}, census {f['census'][0][0]}-{f['census'][-1][0]}): "
            + ", ".join(f"{f['years'][t]} {f['pop'][t]:,.0f}" for t in ("init", "mid", "ult")))
