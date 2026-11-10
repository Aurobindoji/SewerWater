"""Design criteria (data/design_criteria.json: CPHEEO values with page references and project
decisions) and the pipe catalog (data/sewer_catalog.json).

From the original scripts design_check.py (load_criteria, val, table_rows, slope_row) and sewer_design.py (Rules,
load_catalog). sys.exit is replaced by DesignError; file paths are arguments (default: data folder).
"""
import json
import os

from . import DATA_DIR, DesignError

CRITERIA_FILE = os.path.join(DATA_DIR, "design_criteria.json")
CATALOG_FILE = os.path.join(DATA_DIR, "sewer_catalog.json")


def load_criteria(path=None):
    with open(path or CRITERIA_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def val(crit, key):
    item = crit.get(key)
    return None if item is None else item.get("value")


def table_rows(tab):
    """{'200': 0.004, ...} -> [(200.0, 0.004), ...] sorted by size."""
    return sorted((float(k), float(v)) for k, v in (tab or {}).items())


def slope_row(rows, d):
    """Table 3.13 row for diameter d (mm): the largest tabulated size <= d.
    5 % tolerance so that an internal diameter slightly below the nominal size
    (e.g. 194 mm for a 200 mm pipe) still takes the 200 mm row. The last row
    (525 mm) also covers everything larger ('525 and above')."""
    if not rows or d is None:
        return None, None
    fit = [r for r in rows if r[0] <= d * 1.05]
    return fit[-1] if fit else (None, None)


class Rules:
    def __init__(self, crit):
        c = crit["sewer"]
        v = lambda k: val(c, k)                                        # noqa: E731
        self.vmin = v("min_velocity_ultimate_peak_mps")
        self.vmin_init = v("min_velocity_initial_peak_mps")
        self.vmax = v("max_velocity_mps")
        self.ddmax = v("max_d_by_D") or 0.8
        self.dmin = v("min_diameter_mm") or 0
        self.slopes = table_rows(v("min_slope_by_diameter"))
        self.cover = v("min_cover_m") or 0.0
        self.drop_same = (v("drop_same_size_mm") or 0) / 1000.0
        self.drop_mh = v("drop_manhole_threshold_m")
        self.max_depth = v("max_depth_to_invert_m")
        # project decision (12-Oct-2026): no lift stations; sewers may go down to max_depth_project_m (deeper than
        # the CPHEEO max_depth_to_invert_m, justified in the DPR). Absent keys -> CPHEEO behaviour (lift stations
        # studied at max_depth_to_invert_m)
        la = v("lift_stations_allowed")
        self.lifts_allowed = True if la is None else bool(la)
        self.max_depth_project = v("max_depth_project_m") or self.max_depth
        self.s_cap = v("max_slope_for_self_cleansing")
        self.vel_depth = v("max_depth_for_velocity_steepening_m")
        st = v("straight_run_tolerance_deg")
        self.straight_tol = 10.0 if st is None else float(st)
        self.no_reduce = v("no_size_reduction_downstream")
        self.no_reduce = True if self.no_reduce is None else bool(self.no_reduce)
        self.fixed_inv = {}            # {manhole: outgoing invert m} given by the user (manhole table, edits.py)

    def set_start_depth(self, start_depth):
        """Start depth to invert (project decision) -> minimum earth cover over the crown of the smallest
        pipe, as sewer_design.py main() does for --ask / --use-inputs. Returns (new cover, manual cover)."""
        manual = self.cover
        self.cover = float(start_depth) - (self.dmin or 0) / 1000.0
        return self.cover, manual


def load_catalog(name=None, joint="ss", path=None):
    """Active set of sewer_catalog.json -> (name, source, sizes sorted by internal diameter).
    A set may be a combination: "from_sets": [["SET_A", 600], ["SET_B", null]] takes
    SET_A sizes up to 600 mm ID, then SET_B sizes above that."""
    with open(path or CATALOG_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)
    sets = raw.get("sets", {})
    name = name or raw.get("default") or raw.get("active")
    st = sets.get(name)
    if st is None:
        raise DesignError(f"sewer_catalog.json: active set '{name}' not found.")
    if st.get("from_sets"):
        sizes, lo, src = [], 0.0, []
        for sub, upto in st["from_sets"]:
            if sub not in sets:
                raise DesignError(f"sewer_catalog.json: set '{name}' refers to unknown set '{sub}'.")
            if upto is None and sub != st["from_sets"][-1][0]:
                raise DesignError(f"sewer_catalog.json: set '{name}': only the last part may have no upper limit - "
                                  f"fill the switch-over diameter (project decision).")
            part = [dict(x, _set=sub) for x in sets[sub]["sizes"] if x.get("id_mm")
                    and float(x["id_mm"]) > lo and (upto is None or float(x["id_mm"]) <= upto)]
            sizes += part
            src.append(f"{sub}{' up to %g mm' % upto if upto else ' above'}: {sets[sub].get('source', '')}")
            lo = upto if upto is not None else lo
        source = " | ".join(src)
    else:
        sizes, source = [dict(x) for x in st.get("sizes", []) if x.get("id_mm")], st.get("source", "")
    if not sizes:
        raise DesignError(f"sewer_catalog.json: set '{name}' has no sizes - fill it first.")
    for x in sizes:
        x["id_mm"] = float(x["id_mm"])
        jn = (sets.get(x.get("_set", ""), {}) or {}).get("joint_n") or st.get("joint_n")
        if jn:                                    # RCC: Manning n by joint type
            if joint not in jn:
                raise DesignError(f"sewer_catalog.json: set '{name}' has no Manning n for joint '{joint}' "
                                  f"(available: {', '.join(jn)}).")
            x["manning_n"] = jn[joint]
            x["material"] = f"{x['material']}, {'S/S' if joint == 'ss' else joint} joint"
    return name, source, sorted(sizes, key=lambda x: x["id_mm"])
