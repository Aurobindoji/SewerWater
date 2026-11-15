"""The wards of a water project and its population projection: the wards drawn on the map and the page's ward table,
their characters, growth and saturation, the town's wards, a ward KML read into the table (restructure stage 2,
15-Nov-2026: out of ui_api.py)."""
import collections
import math
from . import geo as wgeo
from . import project as ui
from . import design as wd
from . import population as wpop


def _wards(stem, req):
    """The wards drawn on a DXF network (user request 30-Oct-2026: its population by ward, not spread evenly) in the
    project's metres: [{"name", "population", "xy"}]; a ring of fewer than 3 points is left out, a population not a
    number: 0."""
    raw = [w for w in (req or {}).get("wards") or [] if len((w or {}).get("latlngs") or []) >= 3]
    if not raw:
        return []
    to_xy = ui.converters_for(stem)[1]
    wt = ward_table(req)
    by_no = {r["no"]: r for r in (wt or {}).get("rows", [])}
    out = []
    for i, w in enumerate(raw, 1):
        try:
            p = max(float(str(w.get("population")).replace(",", "")), 0.0)
        except (TypeError, ValueError):
            p = 0.0
        ring = [[float(q[0]), float(q[1])] for q in w["latlngs"]]
        row = by_no.get(str(w.get("ward_no") or "").strip())
        d = {"name": str(w.get("name") or "").strip() or f"Ward {i}", "population": p,
             "character": char_name(w.get("character")), "xy": [tuple(q) for q in to_xy(ring)]}
        if row:                                    # the table's ward (user decision 7-Nov-2026): its covered population
            d.update(name=row["name"], population=row["covered"], table=row, character=row["char"])
        out.append(d)
    return out


def _has_conn(c):
    """A pipe with service connections: not one marked without them on the DXF network (a feeder / transmission main,
    user 30-Oct-2026), nor a new pipe along a crossing line - no population is put on those."""
    return not (c.get("no_conn") or c.get("crossing"))


def _ward_pop(net, wards):
    """Population per junction from the wards (layout.population_by_polygons: by half the pipe length at each
    junction inside a ward); a junction in no ward gets none (user decision 30-Oct-2026: 0 and a warning, the total
    given on the page not used). -> (pop, note for the flags)."""
    from . import layout as wl
    served = dict(net, conduits=[c for c in net["conduits"] if _has_conn(c)])
    pop, rows = wl.population_by_polygons(served, [(w["xy"], w["population"]) for w in wards])
    half = collections.defaultdict(float)
    for c in served["conduits"]:
        half[c["start_node"]] += (c["length_m"] or 0.0) / 2
        half[c["stop_node"]] += (c["length_m"] or 0.0) / 2
    out = sorted((n for n in half if n not in pop and (net["nodes"].get(n) or {}).get("xy")), key=str)
    of = {}                                    # junction -> its ward (the first drawn that holds it), for the growth
    for i, w in enumerate(wards):
        for n in pop:
            if n not in of and wl.inside(net["nodes"][n]["xy"], w["xy"]):
                of[n] = i
    note = {"wards": len(wards), "population": round(sum(pop.values())), "junctions": len(pop), "ward_of": of,
            "list": [{"name": w["name"], "population": w["population"], "character": w["character"],
                      "table": w.get("table")} for w in wards],
            "outside": out, "outside_m": round(sum(half[n] for n in out)),
            "empty": [w["name"] for w, r in zip(wards, rows) if not r["manholes inside"]],
            "no_pop": [w["name"] for w, r in zip(wards, rows) if r["manholes inside"] and w["population"] <= 0]}
    return pop, note


def _ward_flags(note, ll, xy):
    """The wards' lines among the zoning's flags, and the junctions in no ward for the map."""
    if not note:
        return [], []
    L = lambda a: ", ".join(a[:8]) + (" ..." if len(a) > 8 else "")
    f = [{"zone": None, "level": "info",
          "text": f"population from {note['wards']} ward(s) drawn on the map: {note['population']:,} on "
                  f"{note['junctions']:,} junctions (by the pipe length at each)",
          "hi": f"आबादी नक्शे पर खींचे {note['wards']} वार्डों से: {note['population']:,}, {note['junctions']:,} junctions पर "
                f"(हर junction पर pipe की लंबाई के अनुपात में)"}]
    if note["outside"]:
        f.append({"zone": None, "level": "warn",
                  "text": f"{len(note['outside']):,} junctions ({note['outside_m']:,} m of pipe) lie in no ward - no population "
                          f"there; draw / widen a ward over them if people live there (orange dots on the map)",
                  "hi": f"{len(note['outside']):,} junctions ({note['outside_m']:,} m pipe) किसी वार्ड में नहीं - वहाँ आबादी 0; "
                        f"वहाँ लोग रहते हों तो वार्ड खींचें / बढ़ाएँ (नक्शे पर नारंगी बिंदु)"})
    if note["empty"]:
        f.append({"zone": None, "level": "warn",
                  "text": f"ward(s) with no junction inside - their population not counted: {L(note['empty'])}",
                  "hi": f"जिन वार्डों में कोई junction नहीं - उनकी आबादी नहीं गिनी गई: {L(note['empty'])}"})
    if note["no_pop"]:
        f.append({"zone": None, "level": "warn",
                  "text": f"ward(s) without population - their junctions get none: {L(note['no_pop'])}",
                  "hi": f"जिन वार्डों में population नहीं भरी - उनके junctions पर आबादी 0: {L(note['no_pop'])}"})
    return f, [ll(xy[n]) for n in note["outside"] if n in xy]


def _ward_rest(net, pop, wards, req):
    """The wards of the table with no boundary on the map (user decision 7-Nov-2026): their covered population on the
    junctions in no ward, by the pipe length at each - all junctions when every one is in a ward (a warning)."""
    wt = ward_table(req)
    if not wt:
        return
    drawn = {w["table"]["no"] for w in wards if w.get("table")}
    rest = [r for r in wt["rows"] if r["no"] not in drawn]
    if not rest:
        return
    note = net["ward_note"]
    half = collections.defaultdict(float)
    for c in filter(_has_conn, net["conduits"]):
        half[c["start_node"]] += (c["length_m"] or 0.0) / 2
        half[c["stop_node"]] += (c["length_m"] or 0.0) / 2
    to = [n for n in note["outside"] if half.get(n)] or [n for n in half if (net["nodes"].get(n) or {}).get("xy")]
    L = sum(half[n] for n in to) or 1.0
    tot = sum(r["covered"] for r in rest)
    by_char = collections.defaultdict(float)       # the characters of these wards (7-Nov-2026): each junction's parts
    for r in rest:
        by_char[r["char"]] += r["covered"]
    parts = note.setdefault("rest_parts", {})
    for n in to:
        pop[n] = pop.get(n, 0.0) + tot * half[n] / L
        if any(by_char):
            parts[n] = {c: v * half[n] / L for c, v in by_char.items()}
    note["rest"] = {"wards": [r["no"] for r in rest], "population": round(tot), "on_outside": bool(note["outside"]),
                    "chars": sum(1 for r in rest if r["char"])}
    note["population"] = round(sum(pop.values()))
    if note["outside"]:
        note["outside"] = []                      # the junctions in no ward now have the table's other wards


def _ward_growth(wn, wnet, pop, crit, req):
    """Wards given a character on the map (user decision 6-Nov-2026, Riverside water DPR p76, criteria ward_growth):
    the population on their junctions is the present one, grown by the character's design-year factor in place of the
    factor of the page / projection; every junction gets its base-year and +15 years shares (node["stage"]) - the
    others the page's / projection's, when given, else 1. The ward table's wards without a boundary (7-Nov-2026) share
    junctions in no ward (wn["rest_parts"]: {junction: {character: population}}): such a junction mixes them. Returns
    the number of wards with a character (0: nothing done)."""
    G = crit["ward_growth"]["value"]
    wn = wn or {}
    chars = [w["character"] if w["character"] in G else "" for w in wn.get("list", [])]
    n_rest = (wn.get("rest") or {}).get("chars", 0)
    if not any(chars) and not n_rest:
        return 0
    rest = wn.get("rest_parts") or {}
    f = _factor(req)                               # wnet's population: the junction's x f (_zones)
    pj, given = req.get("_proj"), ui.stage_inputs(req)
    city = sum(v["pop"] for v in wnet["nodes"].values())
    if pj:
        uni = {t: pj["ratio"][t] / pj["ratio"]["ult"] for t in ("init", "mid")}
    else:
        uni = {t: (given[k] / city if given.get(k) and city else 1.0) for t, k in (("init", "pop_initial"),
                                                                                 ("mid", "pop_mid"))}
    for n, v in wnet["nodes"].items():
        p = pop.get(n, 0.0)
        parts = {c: q for c, q in (rest.get(n) or {}).items() if c in G or c == ""}
        i = wn.get("ward_of", {}).get(n)
        own = chars[i] if i is not None else ""
        parts[own] = parts.get(own, 0.0) + max(p - sum(parts.values()), 0.0)
        ult = sum(q * (G[c][2] if c else f) for c, q in parts.items())
        if not any(c and q > 0 for c, q in parts.items()) or ult <= 0:
            v["stage"] = dict(uni)
            continue
        v["pop"] = ult
        v["stage"] = {t: sum(q * (G[c][j] if c else f * uni[t]) for c, q in parts.items()) / ult
                      for j, t in ((0, "init"), (1, "mid"))}
    return sum(1 for c in chars if c) + n_rest


def _factor(req):
    f = float(req.get("pop_factor") or 1.0)
    if not 0.1 <= f <= 10:
        raise ValueError("आबादी गुणक 0.1 से 10 के बीच दें")
    return f


def ward_table(req):
    """The wards of the page's table (user decision 7-Nov-2026: the user gives the number of wards, then each ward's
    number, name, population of a year he gives (e.g. 2025) and the share of it covered by the project; households,
    area and the 2011 census for the DPR): {"year", "rows": [{no, name, pop, cov (share 0-1), covered, hh, area,
    census, char, kcov}], "total" (the covered population of that year), "growth"} or None.
    char (user decision 7-Nov-2026): the ward's character - its population grows by the character's factors of the
    page (growth: {character: [base, middle, design]} on the population of the year, default criteria ward_growth =
    the Riverside DPR p76 / technical.xlsx 'T' values) in place of the projection's; "" = the projection's. kcov: the
    share of the ward's area in the zone (from a KML, only shown as a check - % covered is the user's)."""
    t = (req or {}).get("ward_table") or {}
    # a 0 is a number, not empty (9-Nov-2026: a character with no ward in the town - its 0 left Far-open unbalanced)
    num = lambda v, d=0.0: float(str(v).replace(",", "")) if str("" if v is None else v).strip() not in ("", "None") else d
    G = ward_growth_of(t)
    rows = []
    for i, r in enumerate(t.get("rows") or [], 1):
        try:
            pop, cov = max(num(r.get("pop")), 0.0), min(max(num(r.get("cov"), 100.0), 0.0), 100.0) / 100.0
        except ValueError:
            continue
        no = str(r.get("no") or "").strip() or str(i)
        rows.append({"no": no, "name": str(r.get("name") or "").strip() or f"Ward {no}", "pop": pop, "cov": cov,
                     "covered": pop * cov, "hh": num(r.get("hh"), None) if r.get("hh") not in (None, "") else None,
                     "area": num(r.get("area"), None) if r.get("area") not in (None, "") else None,
                     "census": num(r.get("census"), None) if r.get("census") not in (None, "") else None,
                     "char": char_name(r.get("char")) if char_name(r.get("char")) in G else "",
                     "kcov": num(r.get("kcov"), None) if r.get("kcov") not in (None, "") else None})
    if not rows or sum(r["covered"] for r in rows) <= 0:
        return None
    y = t.get("year")
    city, C0 = {}, wd.load_criteria().get("ward_town_population", {}).get("value", {})
    given = {char_name(k): v for k, v in t.get("city").items()} if isinstance(t.get("city"), dict) else {}
    for k in G:                                    # the whole town's population of the year by character (Far-open):
        try:                                       # the page's, else criteria (the example's Springfield)
            city[k] = num(given.get(k), None) if k in given else C0.get(k)
        except ValueError:
            city[k] = None
    sat = t.get("sat") if "sat" in t else wd.load_criteria().get("ward_saturation_density", {}).get("value")
    try:                                           # the saturation density (8-Nov-2026): the page's, blank = none
        sat = num(sat, None)
    except ValueError:
        sat = None
    gd, dens = {char_name(k): v for k, v in t["dens"].items()} if isinstance(t.get("dens"), dict) else {}, {}
    for k, v in WARD_DENS.items():                 # the character by the density (the page's; for the DPR's note)
        try:
            dens[k] = num(gd.get(k), v)
        except ValueError:
            dens[k] = v
    return {"year": int(y) if str(y or "").strip() else None, "rows": rows, "total": sum(r["covered"] for r in rows),
            "growth": G, "city": city, "sat": sat if sat and sat > 0 else None, "dens": dens}


# the characters of a ward, densest first (user decision 9-Nov-2026): CPHEEO Manual on Water Supply 2024 Part A
# Annexure 2.7 p974's categories - low / medium / high / saturated, "the cores of the city" at saturation - with the
# Riverside water DPR p76's word in brackets (its Proximal Developed / Core / Proximal Developing / Far-open, in that
# order of density); the old names of a saved project / list / map read as the new (char_name)
WARD_CHARS = ("Saturated (Core)", "High (Proximal Developed)", "Medium (Proximal Developing)", "Low (Far-open)")


OLD_CHARS = dict(zip(("Proximal Developed", "Core", "Proximal Developing", "Far-open"), WARD_CHARS))


CORE_CHAR = WARD_CHARS[0]


def char_name(c):
    """A ward character by its name now: an old one (before 9-Nov-2026) as its new one; "" for none."""
    c = str(c or "").strip()
    return OLD_CHARS.get(c, c)


# the character of a ward by its density of the table's year, persons / ha above (example technical.xlsx 'T' X346; the
# ranges not CPHEEO's - its Annexure 2.7 p974 chooses them by the town's size); the rest Low (Far-open)
WARD_DENS = {WARD_CHARS[0]: 585, WARD_CHARS[1]: 310, WARD_CHARS[2]: 170}


# CPHEEO Water Manual Part A Annexure 2.7 p974: the developed core's density has practically reached saturation -
# "very close to the present density"; its design factor above this warned of (the app's reading: 10 %, as the
# saturation density's default)
CORE_NEAR = 1.10


def saturation_over(wt, ratio):
    """The saturation density (CPHEEO Manual on Water Supply 2024 Part A, Annexure 2.7 p974; user decision 8-Nov-2026:
    only warned of): the developed core's present density, a little above, is the upper limit of every ward's future
    density. The table's wards with an area whose design-year density - the ward's population x its character's
    design factor, else the adopted ratio (ratio["ult"]) - is above it: [{no, name, char, d0, d}] (per ha)."""
    sat, out = (wt or {}).get("sat"), []
    if not sat:
        return out
    for r in wt["rows"]:
        a = r.get("area") or 0.0
        f = wt["growth"][r["char"]][2] if r["char"] else (ratio or {}).get("ult")
        if a <= 0 or r["pop"] <= 0 or not f:
            continue
        d0 = r["pop"] / a
        if d0 * f > sat:
            out.append({"no": r["no"], "name": r["name"], "char": r["char"], "d0": round(d0, 1), "d": round(d0 * f, 1)})
    return out


FAR_OPEN = WARD_CHARS[3]


def far_open_balance(wt, f):
    """The balancing factors of Far-open (user decision 7-Nov-2026; example technical.xlsx 'T' P470 = AD472 / AC473,
    Riverside water DPR p76): the whole town's population of the table's year by character (wt["city"], the page's;
    default the example's Springfield wards 6,98,311 / 6,73,088 / 7,20,858 / 5,87,585), grown by the adopted method
    (f["town_ratio_from"]) is the town of each stage; less the other characters x their factors, over Far-open's
    population: Far-open's factor - so the town's wards add up to the adopted projection in every stage.
    -> {"factors": [init, mid, ult], "city", "total", "target"} or {"error": text} or None (not given)."""
    P, R = (wt or {}).get("city") or {}, (f or {}).get("town_ratio_from")
    if not R or not P or any(v is None for v in P.values()):
        return None
    if any(v < 0 for v in P.values()) or not (P.get(FAR_OPEN) or 0) > 0:
        return {"error": "Far-open की शहर की आबादी 0 से अधिक दें"}
    S = sum(P.values())
    G = wt["growth"]
    out, target = [], {}
    for j, t in enumerate(("init", "mid", "ult")):
        target[t] = S * R[t]
        x = (target[t] - sum(P[k] * G[k][j] for k in P if k != FAR_OPEN)) / P[FAR_OPEN]
        if x <= 0:
            return {"error": f"Far-open का गुणक {x:.3f} ({t}) - बाकी चरित्रों के गुणक शहर की projection से ज़्यादा"}
        out.append(round(x, 6))
    # Far-open growing slower than a denser character: the fixed factors do not suit this town's growth
    low = out[2] < max(G[k][2] for k in P if k != FAR_OPEN)
    # Far-open below 1 (user decision 10-Nov-2026): its wards' population falling - the others' factors too high
    below = [t for t, x in zip(("init", "mid", "ult"), out) if x < 1]
    return {"factors": out, "city": P, "total": S, "target": target, "ratio": R, "low": low, "below": below}


def ward_growth_of(t):
    """The factors of each ward character (base / middle / design on the population of the ward table's year): the
    page's (t["growth"], yellow on the page, 7-Nov-2026) where given as three positive numbers, else criteria.json
    ward_growth."""
    G = {k: list(v) for k, v in wd.load_criteria()["ward_growth"]["value"].items()}
    for k, v in ((t or {}).get("growth") or {}).items():
        k = char_name(k)
        try:
            f = [float(str(x).replace(",", "")) for x in v]
        except (TypeError, ValueError):
            continue
        if k in G and len(f) == 3 and all(x > 0 for x in f):
            G[k] = f
    fo = (t or {}).get("_far_open")                # balanced by the projection (_with_projection, 7-Nov-2026)
    if fo and FAR_OPEN in G:
        G[FAR_OPEN] = list(fo)
    return G


def ward_stages(wt, ratio):
    """The wards of the table in the base / middle / design years: a ward with a character its covered population x
    the character's factors, the others x ratio ({init, mid, ult} from the table's year; None: those not counted).
    -> {"init", "mid", "ult", "rows": [{no, char, init, mid, ult}]}."""
    out = {"init": 0.0, "mid": 0.0, "ult": 0.0, "rows": []}
    for r in wt["rows"]:
        f = wt["growth"][r["char"]] if r["char"] else ([ratio[t] for t in ("init", "mid", "ult")] if ratio else None)
        x = {"no": r["no"], "char": r["char"]}
        for j, t in enumerate(("init", "mid", "ult")):
            x[t] = r["covered"] * f[j] if f else None
            out[t] += x[t] or 0.0
        out["rows"].append(x)
    return out


WARD_NO_KEYS = ("w_num", "ward_no", "ward no", "wardno", "w_no", "ward_num", "ward number")


WARD_NAME_KEYS = ("w_name", "ward_name", "ward name", "wardname")


WARD_HH_KEYS = ("w_hh", "hh", "households", "household", "house_hold")


def ward_kml_table(text):
    """The ward table from a KML of the ward boundaries (user decision 7-Nov-2026, e.g. 'MAPLEWOOD ZONE AND WARDS.kml'):
    a polygon with a ward number / ward name field is a ward, the others the zone. Each ward: its number, name, area
    (ha, of its boundary), the share of that area inside the zone (kcov, only a check: % covered stays the user's, by
    population as technical.xlsx T1) and, where the KML gives them above 0, population and households; its boundary
    (the largest part) for the map. -> {"rows", "wards": [{no, name, latlngs}], "zone": {name, area_ha} | None,
    "notes": [(hi, en)]}."""
    import numpy as np
    from matplotlib.path import Path
    k = wgeo.read_kml("wards.kml", text=text)
    low = lambda d: {str(a).strip().lower(): b for a, b in (d or {}).items() if a}
    pick = lambda d, keys: next((str(d[x]).strip() for x in keys if str(d.get(x) or "").strip()), "")
    polys = [p for p in k["polygons"] if len(p["coords"]) >= 3]
    if not polys:
        raise ValueError("KML में कोई polygon नहीं")
    c0 = polys[0]["coords"][0]
    epsg = wgeo.utm_epsg(c0[0], c0[1])
    wards, zone = collections.OrderedDict(), []
    for p in polys:
        d = low(p["data"])
        no, nm = pick(d, WARD_NO_KEYS), pick(d, WARD_NAME_KEYS)
        xy = np.array(wgeo.to_xy(p["coords"], epsg))
        a = abs(float(np.dot(xy[:-1, 0], xy[1:, 1]) - np.dot(xy[1:, 0], xy[:-1, 1])
                      + xy[-1, 0] * xy[0, 1] - xy[0, 0] * xy[-1, 1])) / 2
        if a < 1.0:                                # a ring of no area
            continue
        if not no and not nm:
            zone.append((p, xy, a))
            continue
        key = no or nm
        w = wards.setdefault(key, {"no": no, "name": nm or p["name"] or f"Ward {no}", "parts": [], "data": d})
        w["parts"].append((p, xy, a))
    if not wards:
        raise ValueError("KML में कोई वार्ड नहीं (ward number / name का field, जैसे W_NUM / W_Name)")
    zpaths = [Path(z[1]) for z in zone]
    num = lambda v: wgeo.number(v) if wgeo.number(v) and wgeo.number(v) > 0 else None
    rows, out_w, notes = [], [], []
    for i, (key, w) in enumerate(wards.items(), 1):
        area = sum(x[2] for x in w["parts"])
        kcov = None
        if zpaths:
            inside = total = 0
            for _, xy, a in w["parts"]:
                step = max(math.sqrt(a / 60000.0), 1.0)
                (x0, y0), (x1, y1) = xy.min(axis=0), xy.max(axis=0)
                gx, gy = np.meshgrid(np.arange(x0 + step / 2, x1, step), np.arange(y0 + step / 2, y1, step))
                pts = np.column_stack([gx.ravel(), gy.ravel()])
                pts = pts[Path(xy).contains_points(pts)]
                total += len(pts)
                hit = np.zeros(len(pts), bool)
                for zp in zpaths:
                    hit |= zp.contains_points(pts)
                inside += int(hit.sum())
            kcov = round(100.0 * inside / total, 1) if total else None
        pop, hh = num(w["data"].get("w_pop") or pick(w["data"], wgeo.POP_KEYS)), num(pick(w["data"], WARD_HH_KEYS))
        no = w["no"] or str(i)
        rows.append({"no": no, "name": w["name"], "pop": round(pop) if pop else "", "cov": "",
                     "hh": round(hh) if hh else "", "area": round(area / 1e4, 2), "census": "", "char": "",
                     "kcov": kcov if kcov is not None else ""})
        big = max(w["parts"], key=lambda x: x[2])[0]
        out_w.append({"no": no, "name": w["name"], "latlngs": [[c[1], c[0]] for c in big["coords"]]})
        if len(w["parts"]) > 1:
            notes.append((f"{w['name']}: {len(w['parts'])} हिस्से - नक्शे पर सबसे बड़ा, क्षेत्रफल सबका",
                          f"{w['name']}: {len(w['parts'])} parts - the largest on the map, the area of all"))
    if pop_given := [r for r in rows if r["pop"] != ""]:
        notes.append((f"KML की आबादी {len(pop_given)} वार्डों में भरी - उसका वर्ष जाँचें (तालिका का वर्ष "
                      f"ऊपर है), बाकी में भरें",
                      f"the KML's population filled in {len(pop_given)} ward(s) - check its year (the table's year "
                      f"is above), fill in the others"))
    if not zone:
        notes.append(("KML में zone का polygon (बिना ward number) नहीं - zone में क्षेत्रफल-% नहीं निकला",
                      "no zone polygon (one without a ward number) in the KML - no area share in the zone"))
    zi = {"name": " + ".join(z[0]["name"] or "zone" for z in zone),
          "area_ha": round(sum(z[2] for z in zone) / 1e4, 2)} if zone else None
    return {"rows": rows, "wards": out_w, "zone": zi, "notes": notes}


def projection_of(req):
    """The population projection of the page (population.py, user request 30-Oct-2026): req["projection"] =
    {base_pop, census, method} with req["base_year"]; None when no base-year population or census is given. With the
    ward table (user decision 7-Nov-2026) its covered population of its year, grown from that year."""
    p = (req or {}).get("projection") or {}
    wt = ward_table(req)
    if not str(p.get("census") or "").strip() or (p.get("base_pop") in (None, "") and not wt):
        return None
    if (req or {}).get("base_year") in (None, ""):
        raise ValueError("projection के लिए आधार वर्ष दें")
    if wt:
        if not wt["year"]:
            raise ValueError("वार्डों की आबादी का वर्ष दें (जैसे 2025)")
        f = wpop.project(req["base_year"], wt["total"], p["census"], p.get("method"), from_year=wt["year"])
        fo = far_open_balance(wt, f)               # Far-open by the adopted method (7-Nov-2026)
        if fo and "factors" in fo:
            wt["growth"][FAR_OPEN] = fo["factors"]
            f["far_open"] = fo
        elif fo:
            f["far_open_error"] = fo["error"]
        if wt["sat"]:                              # the saturation density (CPHEEO Annexure 2.7, 8-Nov-2026)
            f["saturation"] = {"value": wt["sat"], "over": saturation_over(wt, f["ratio_from"])}
        pd = wt["growth"].get(CORE_CHAR)
        if pd and pd[2] > CORE_NEAR:               # CPHEEO Annexure 2.7 p974: the core near saturation
            f["core_factor"] = pd[2]
        if any(r["char"] for r in wt["rows"]):     # wards with a character (7-Nov-2026): the project's own stages
            f["wards"] = ward_stages(wt, f["ratio_from"])
        return f
    return wpop.project(req["base_year"], float(str(p["base_pop"]).replace(",", "")), p["census"], p.get("method"))


def _with_projection(req):
    """With a projection: the population on the junctions (the wards / the total of the page) is the base year's -
    grown by the adopted method's +30 years ratio, in place of the factor of the page; the stage check's base year and
    +15 years from the same ratios (set in _zones, where the base-year population on the junctions is known)."""
    f = projection_of(req)
    if f is None:
        wt = ward_table(req)                        # the ward table, no census: its population x the page's factor
        return dict(req, pop_total=wt["total"]) if wt else req
    if f.get("from_year"):                          # the wards' population of their year: grown from it
        out = dict(req, pop_factor=f["ratio_from"]["ult"], pop_total=f["from_pop"], _proj=f)
        if f.get("far_open"):                       # the balanced Far-open: for every ward_table(req) after this
            out["ward_table"] = dict(req["ward_table"], _far_open=f["far_open"]["factors"])
    else:
        out = dict(req, pop_factor=f["ratio"]["ult"], pop_total=f["base_pop"], _proj=f)
    out.pop("pop_initial", None)
    out.pop("pop_mid", None)
    return out


def _proj_flags(f, s0):
    """The projection among the zoning's flags: the adopted method and its stages; a base-year population on the
    junctions (wards) not the one given."""
    if not f:
        return []
    nm = f["names"][f["adopted"]]
    st = ", ".join(f"{f['years'][t]} {f['pop'][t]:,.0f}" for t in ("init", "mid", "ult"))
    out = [{"zone": None, "level": "info",
            "text": f"population projection - {nm[0]}: {st} (x {f['ratio']['ult']:.3f} at +30 years)",
            "hi": f"आबादी projection - {nm[1]}: {st} (+30 वर्ष पर x {f['ratio']['ult']:.3f})"}]
    out += [{"zone": None, "level": "warn", "text": en, "hi": hi} for hi, en in f["notes"]]
    fo = f.get("far_open")
    if fo:
        x = " / ".join(f"{v:.4f}" for v in fo["factors"])
        out.append({"zone": None, "level": "info",
                    "text": f"Far-open balanced by {nm[0]}: x {x} (the town's wards {fo['total']:,.0f} add up to the projection)",
                    "hi": f"Far-open {nm[1]} से balance: x {x} (शहर के वार्ड {fo['total']:,.0f} का जोड़ projection के बराबर)"})
    if fo and fo.get("below"):                  # more particular than "low" (10-Nov-2026)
        x = ", ".join(f"{t} {v:.4f}" for t, v in zip(("init", "mid", "ult"), fo["factors"]) if t in fo["below"])
        out.append({"zone": None, "level": "warn",
                    "text": f"Far-open's factor below 1 ({x}): its wards' population falls - the other characters' "
                            "factors too high for this town's projection; 'Factors to the projection' on the page",
                    "hi": f"Far-open का गुणक 1 से कम ({x}): उसके वार्डों की आबादी घटती दिखती है - बाकी चरित्रों के "
                          "गुणक इस शहर की projection के लिए ज़्यादा; पन्ने पर 'गुणक projection से मिलाएँ'"})
    elif fo and fo.get("low"):
        out.append({"zone": None, "level": "warn",
                    "text": "Far-open grows slower than a denser character - the other characters' factors seem high for this town's growth",
                    "hi": "Far-open किसी घने चरित्र से धीमा बढ़ रहा है - इस शहर की बढ़त के लिए बाकी चरित्रों के गुणक ज़्यादा लगते हैं"})
    if f.get("far_open_error"):
        out.append({"zone": None, "level": "warn", "text": "Far-open not balanced: " + f["far_open_error"],
                    "hi": "Far-open balance नहीं हुआ: " + f["far_open_error"] + " - पन्ने वाले गुणक लगे"})
    sv = f.get("saturation")
    if sv and sv["over"]:                      # only warned (user decision 8-Nov-2026)
        L = ", ".join(f"{w['name']} {w['d0']:,.0f} -> {w['d']:,.0f}" for w in sv["over"])
        out.append({"zone": None, "level": "warn",
                    "text": f"ward(s) above the saturation density {sv['value']:,.0f} per ha in the design year (CPHEEO "
                            f"Water Manual Part A Annexure 2.7 p974): {L} - lower their character's factors, or check the area",
                    "hi": f"Design वर्ष में saturation density {sv['value']:,.0f} प्रति ha से ऊपर के वार्ड (CPHEEO Water "
                          f"Manual Part A Annexure 2.7 p974): {L} - उनके चरित्र के गुणक घटाएँ, या क्षेत्रफल जाँचें"})
    if f.get("core_factor"):
        cf = f["core_factor"]
        out.append({"zone": None, "level": "warn",
                    "text": f"{CORE_CHAR} x {cf:.2f} in the design year: the developed core's density has practically "
                            f"reached saturation unless the FSI is raised - keep its factor close to 1 (CPHEEO Water Manual "
                            f"Part A Annexure 2.7 p974; warned above {CORE_NEAR:.2f})",
                    "hi": f"{CORE_CHAR} x {cf:.2f} (Design वर्ष): विकसित core की density लगभग saturation पर है, जब तक "
                          f"FSI न बढ़े - इसका गुणक 1 के पास रखें (CPHEEO Water Manual Part A Annexure 2.7 p974; "
                          f"{CORE_NEAR:.2f} से ऊपर चेतावनी)"})
    if f.get("from_year"):                     # the wards' table: its population is the one spread
        return out
    if s0 and abs(s0 - f["base_pop"]) > 0.02 * f["base_pop"]:
        out.append({"zone": None, "level": "warn",
                    "text": f"the population on the junctions (wards) {s0:,.0f} is not the base-year population given "
                            f"{f['base_pop']:,.0f} - it is grown by the same ratio",
                    "hi": f"junctions (वार्डों) पर आबादी {s0:,.0f} है, दी गई आधार वर्ष की आबादी {f['base_pop']:,.0f} नहीं - "
                          f"उसी अनुपात से बढ़ाई गई"})
    return out


def _town_list(req, wt):
    """The town's list of wards chosen on the page (city_wards, user decisions 9-Nov-2026), for DPR T2 Town Wards:
    {city, year, rows: [{no, name, pop, hh, area, census, char}]} - each ward's character the list's, else by the
    density limits of the page on its Eq. area (as the page) - or None."""
    name = str(((req.get("ward_table") or {}).get("citylist")) or "").strip()
    if not name:
        return None
    from . import city_wards as cw
    try:
        d = cw.load(name)
    except (OSError, ValueError):
        return None
    D = sorted(((v, k) for k, v in (wt.get("dens") or WARD_DENS).items() if k in WARD_DENS), reverse=True)

    def char(w):
        c = char_name(w.get("char"))
        if c in WARD_CHARS:
            return c
        p, a = w.get("pop") or 0, w.get("area") or 0
        if p > 0 and a > 0:
            return next((k for v, k in D if p / a > v), FAR_OPEN)
        return ""
    return {"city": d["city"], "year": d.get("year"),
            "rows": [dict({k: w.get(k) for k in ("no", "name", "pop", "hh", "area", "census")}, char=char(w))
                     for w in d.get("rows") or []]}
