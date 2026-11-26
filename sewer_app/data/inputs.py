"""The inputs of a sewer zoning / design from the page (restructure stage 6, 15-Nov-2026: out of ui.py): the pipe
catalogues, the design inputs and their defaults, the CPHEEO criteria with the page's changes."""
import csv
import json
import os
from sewer_app.core import store
from sewer_app.data.project import STAGE_KEYS, is_dxf, paths, stage_inputs


# ---------------------------------------------------------------- zoning and design from the page
ZCACHE = {}                    # stem -> (key of the inputs, zoning result): design of an option needs no re-run


INPUT_DEFAULTS = {"catalog": None, "joint": "ss", "sewage_lpcd": 108.0, "start_depth": 0.7, "peak": "table",
                  "infil_basis": "none", "infil_rate": 0.0, "data_grade": "PFR"}


def catalogs():
    """Pipe catalogs of data/sewer_catalog.json that can be used as they are: [{name, source, joints}], default
    first. Test sets and combinations still to be filled are left out."""
    from sewer_app.engine.criteria import CATALOG_FILE, load_catalog
    with open(CATALOG_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = []
    for name, st in raw.get("sets", {}).items():
        if "TEST" in name.upper():
            continue
        joints = sorted((st.get("joint_n") or {}).keys())
        try:
            load_catalog(name, joints[0] if joints else "ss")
        except Exception:
            continue
        out.append({"name": name, "source": str(st.get("source") or "")[:160], "joints": joints})
    default = raw.get("default")
    return sorted(out, key=lambda c: (c["name"] != default, c["name"]))


def design_inputs(stem, req):
    """Inputs of zoning / design (the keys of an inputs.json) from the page, written to output\\<stem>\\
    <stem>_inputs.json so that the command line gives the same run. Population (user decision 22-Oct-2026): the
    base-year population of the page (or, without it, the wards' population of the layout) and the town's census
    figures -> the +15 / +30 years population with the floating population (population.forecast, as the Riverside
    DPR); the design runs on the +30 years figure, the wards' population only shares it out. An older run with only
    a design population (pop_total) still works as before."""
    from sewer_app.engine import population
    folder, _, _, f_pop = paths(stem)
    inp = dict(INPUT_DEFAULTS)
    for k in ("catalog", "joint", "sewage_lpcd", "start_depth"):
        if req.get(k) not in (None, ""):
            inp[k] = req[k] if k in ("catalog", "joint") else float(req[k])
    if not inp["catalog"]:
        inp["catalog"] = catalogs()[0]["name"]
    if is_dxf(stem):
        inp.pop("data_grade")               # levels of the drawing: DPR unless they are interpolated / assumed
    wards = None
    if os.path.isfile(f_pop):
        with open(f_pop, encoding="utf-8") as fh:
            wards = sum(float(r["Population"]) for r in csv.DictReader(fh))
        inp.update(pop_dist="csv", pop_csv=f_pop)
    else:
        inp.update(pop_dist="length")
    st = stage_inputs(req)
    base = st.get("pop_initial") or (wards if not req.get("pop_total") else None)
    if base:
        f = population.forecast(st.get("base_year") or 2027, base, req.get("census") or None,
                                req.get("pop_method") or None, sewage_lpcd=float(inp["sewage_lpcd"]),
                                floating_share=population.floating_share_of(req.get("floating_pct")))
        inp.update(base_year=f["base_year"], pop_initial=f["design"]["init"], pop_mid=f["design"]["mid"],
                   pop_total=f["design"]["ult"], forecast=f)
    else:
        inp["pop_total"] = round(wards, 1) if wards else float(req.get("pop_total") or 0)
        inp.update(st)
    if wards and inp.get("pop_total"):
        inp["pop_scale"] = inp["pop_total"] / wards          # the wards' population shares the design population out
    if not inp.get("pop_total"):
        raise ValueError("आबादी नहीं है: आधार वर्ष की आबादी दें (या वार्ड में population भरकर Layout दोबारा बनाएँ)")
    store.write_text(os.path.join(folder, f"{stem}_inputs.json"),
                     json.dumps(dict(inp, _readme="written by the map UI (python -m sewer_app ui)"), ensure_ascii=False,
                                indent=2))
    return inp


def bend_drop_on(v):
    """'मोड़ पर 30 mm drop' of the page: on unless switched off (an older saved run has no such field)."""
    return v not in (False, 0, "0", "false", "off", "no")


MH_SPACING_RANGE = (5.0, 150.0)


BEND_ANGLE_RANGE = (1.0, 90.0)


def criteria_for(max_depth=None, bend_drop=True, mh_spacing=None, bend_angle=None, trunk=None):
    """design_criteria.json, with the project depth limit (max_depth_project_m) given on the page for this run, the
    30 mm drop where a sewer of the same size changes direction (drop_same_size_mm) switched off when the page says so
    (user decision 16-Oct-2026: on by default, as CPHEEO), and the largest distance between manholes
    (max_manhole_spacing_m, default 30 m, CPHEEO 3.71.1) and the bend that gets a manhole (bend_manhole_min_angle_deg,
    default 20 deg, a project decision) given on the page (user requests 20-Oct-2026); trunk: the sewers marked on the
    page as trunk sewers with no house connections (trunk_conduits - CPHEEO Table 3.31 spacing, user request
    21-Oct-2026)."""
    from sewer_app.engine.criteria import load_criteria
    crit = load_criteria()
    if trunk:
        tc = crit["sewer"].setdefault("trunk_conduits", {})
        tc["note"] = (f"PROJECT DECISION (marked in the map UI): {len(trunk)} trunk sewer(s) with no house "
                      f"connections - manhole spacing by CPHEEO Table 3.31 (p3-127). " + str(tc.get("note") or ""))
        tc["value"] = sorted(str(x) for x in trunk)
    if mh_spacing not in (None, ""):
        v = float(mh_spacing)
        if not MH_SPACING_RANGE[0] <= v <= MH_SPACING_RANGE[1]:
            raise ValueError(f"Manholes की दूरी {MH_SPACING_RANGE[0]:g} से {MH_SPACING_RANGE[1]:g} m के बीच दें")
        sp = crit["sewer"]["max_manhole_spacing_m"]
        if abs(v - float(sp["value"])) > 1e-9:
            sp["note"] = (f"PROJECT DECISION (user input in the map UI): {v:g} m for this run (design_criteria.json: "
                          f"{float(sp['value']):g} m, CPHEEO 3.71.1 p3-126: 30 m). " + str(sp.get("note") or ""))
            sp["value"] = v
    if bend_angle not in (None, ""):
        v = float(bend_angle)
        if not BEND_ANGLE_RANGE[0] <= v <= BEND_ANGLE_RANGE[1]:
            raise ValueError(f"मोड़ का कोण {BEND_ANGLE_RANGE[0]:g} से {BEND_ANGLE_RANGE[1]:g} degree के बीच दें")
        ba = crit["sewer"]["bend_manhole_min_angle_deg"]
        if ba.get("value") != v:
            ba["note"] = (f"PROJECT DECISION (user input in the map UI): {v:g} deg for this run (design_criteria.json: "
                          f"{ba.get('value')}). " + str(ba.get("note") or ""))
            ba["value"] = v
    if max_depth not in (None, ""):
        v = float(max_depth)
        if not 2.0 <= v <= 30.0:
            raise ValueError("अधिकतम गहराई 2 से 30 m के बीच दें")
        mp = crit["sewer"]["max_depth_project_m"]
        if abs(v - float(mp["value"])) > 1e-9:
            mp["note"] = (f"PROJECT DECISION (user input in the map UI): {v:g} m for this run (design_criteria.json: "
                          f"{float(mp['value']):g} m). " + str(mp.get("note") or ""))
            mp["value"] = v
    if not bend_drop_on(bend_drop):
        dr = crit["sewer"]["drop_same_size_mm"]
        dr["note"] = (f"PROJECT DECISION (user input in the map UI): no drop at a change of direction for this run "
                      f"(design_criteria.json: {float(dr['value'] or 0):g} mm, CPHEEO 'usually 30 mm'). "
                      + str(dr.get("note") or ""))
        dr["value"] = 0
    return crit


FIELDS = ("catalog", "joint", "sewage_lpcd", "start_depth", "stp", "max_zones", "pop_total", "mode", "max_depth",
          "bend_drop", "edits", "mh_spacing", "bend_angle", "barriers", "loops", "crossings") + STAGE_KEYS
