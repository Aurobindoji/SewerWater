"""Approximate cost of a sewage pumping station (capex and O&M) and of the STP, for comparing options at PFR stage.

User decision (12-Oct-2026): no rule per MLD exists for pumping stations - they are worked out from civil,
mechanical and electrical parts; a logical approximate cost now, checked properly when the DPR is made.
STP: Rs 1.5 crore per MLD (user). Data and every assumption: data/pumping_station_cost.json.

The cost follows the three pumping stations of the user's DPR files (Riverside SPS-1 55.25 MLD; Lakeside SPS-1
11 MLD and SPS-2 4 MLD - capacities taken as peak flows). fit() gives, for every E&M part and for the civil
works, cost = A x (Q / Q_L)^e through Riverside (Q_L) and the mean of the two Lakeside stations (at the geometric
mean of their flows); a part that does not grow with the flow in these data (e < 0: DG sets, automation, HT
substation) is the mean of the three stations. Civil works also follow the depth of the incoming sewer: the deep
structures (wet well, inlet and screen chambers - 77.9 % of the Riverside civil cost) by (depth + 1.3) /
(10.74 + 1.3). Plus the power connection charge per station (Lakeside).
O&M per year = energy at the average flow x tariff + om_em_fraction x E&M + om_civil_fraction x civil; its
present value over npv_years at discount_rate.
"""
import json
import math
import os

from . import DATA_DIR

COST_FILE = os.path.join(DATA_DIR, "pumping_station_cost.json")
MLD = 1e6 / 86400.0                                       # L/s per MLD


def load_params(path=None):
    with open(path or COST_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def _v(P, key):
    return P[key]["value"]


def depth_factor(depth_m, d0, P):
    """Civil cost at depth / civil cost at the reference depth d0: the deep structures (deep_share) by their
    height (depth + chamber_extra_height_m), the rest unchanged."""
    s, ex = _v(P, "deep_share"), _v(P, "chamber_extra_height_m")
    return (1 - s) + s * (depth_m + ex) / (d0 + ex)


def fit(P):
    """{"Q_L": L/s, "civil": (A, e), "em": {part: (A, e)}} from the data points (see module text)."""
    L, R = P["data_points"]["Riverside SPS-1"], P["data_points"]["Lakeside SPS-1 + SPS-2"]
    qL = L["capacity_mld"][0] * MLD
    qR = math.exp(sum(math.log(q * MLD) for q in R["capacity_mld"]) / R["count"])      # geometric mean
    span = math.log(qL / qR)

    def two_point(cL, cR):
        e = math.log(cL / cR) / span
        if e < 0:                                     # not growing with the flow: mean of the three stations
            return (cL + R["count"] * cR) / (1 + R["count"]), 0.0
        return cL, e
    d0 = L["incoming_depth_m"][0]
    depths = [d if d is not None else d0 for d in R["incoming_depth_m"]]
    # civil cost of each Lakeside station brought to the Riverside depth (depth_factor) before the fit
    civ_R = sum(c / depth_factor(d, d0, P) for c, d in zip(R["civil_lakh_each"], depths)) / R["count"]
    out = {"Q_L": qL, "Q_R": qR, "civil": two_point(L["civil_lakh"], civ_R), "em": {}}
    for part, cL in L["em_lakh"].items():
        out["em"][part] = two_point(cL, R["em_lakh"][part] / R["count"])
    return out


def head_m(depth_m, P, rm_head=None):
    """Pumping head (m): incoming depth + inlet drop + wet-well effective depth + rising-main head (delivery +
    friction; the assumed rising_main_head_m when the rising main is not known)."""
    return (depth_m + _v(P, "inlet_drop_m") + _v(P, "wet_well_effective_depth_m")
            + (rm_head if rm_head is not None else _v(P, "rising_main_head_m")))


def pump_kw(q_lps, depth_m, P, rm_head=None):
    return 9.81 * (q_lps / 1000.0) * head_m(depth_m, P, rm_head) / _v(P, "pump_efficiency")


def wet_well(q_lps, depth_m, P):
    """(diameter m, height m) of a circular wet well (report only): effective volume = retention x peak flow."""
    vol = q_lps / 1000.0 * _v(P, "wet_well_retention_s")
    dia = max(_v(P, "wet_well_min_dia_m"), math.sqrt(4 * vol / (math.pi * _v(P, "wet_well_effective_depth_m"))))
    return dia, depth_m + _v(P, "inlet_drop_m") + _v(P, "wet_well_effective_depth_m") + 0.5


def npv_factor(P):
    r, n = _v(P, "discount_rate"), _v(P, "npv_years")
    return (1 - (1 + r) ** -n) / r if r else float(n)


def sps_cost(q_peak_lps, q_avg_lps, depth_m, P=None, rm_head=None, q_em_lps=None):
    """Approximate cost of one pumping station. q in L/s, depth = incoming sewer invert below GL (m), rm_head =
    delivery + friction head of its rising main (m) when known. q_em_lps = the peak flow the pumps and the E&M are
    sized for (CPHEEO Table 2.1 p2-9: pumping machinery 15 years - the +15 years peak; default q_peak_lps), while
    the civil works (wet well) take q_peak_lps (30 years). Returns a dict: components [(group, name, Rs lakh, how)],
    civil, em, power, capex (Rs lakh), kw, connected_kw, ht, head, energy_kwh_year, om_year, om_npv, total_npv
    (capex + O&M present value), all in Rs lakh."""
    P = P or load_params()
    F = fit(P)
    r = q_peak_lps / F["Q_L"]
    q_em = q_peak_lps if q_em_lps is None else q_em_lps
    r_em = q_em / F["Q_L"]
    d0 = P["data_points"]["Riverside SPS-1"]["incoming_depth_m"][0]
    kw = pump_kw(q_em, depth_m, P, rm_head)
    conn = kw * _v(P, "connected_load_factor")
    ht = conn > _v(P, "ht_threshold_kw")
    comps = []
    A, e = F["civil"]
    dep_f = depth_factor(depth_m, d0, P)
    comps.append(("civil", "civil works (wet well, chambers, screens, buildings, DG platform, boundary, road)",
                  A * r ** e * dep_f, f"{A:.1f} x (Q ratio {r:.3f})^{e:.3f} x depth factor {dep_f:.3f}"))
    for part, (A, e) in F["em"].items():
        if part.startswith("HT") and not ht:
            comps.append(("E&M", "LT connection (no HT supply)", _v(P, "lt_connection_lakh"),
                          f"connected load {conn:.0f} kW <= {_v(P, 'ht_threshold_kw'):g} kW"))
            continue
        how = (f"{A:.2f} x (Q ratio {r_em:.3f})^{e:.3f}" if e else
               f"{A:.2f} = mean of the 3 DPR stations (does not grow with the flow)")
        comps.append(("E&M", part, A * r_em ** e, how))
    comps.append(("power", "power connection charges", _v(P, "power_connection_lakh"), "Lakeside 162.15 / 2"))
    civil = sum(a for g, _, a, _ in comps if g == "civil")
    em = sum(a for g, _, a, _ in comps if g == "E&M")
    power = sum(a for g, _, a, _ in comps if g == "power")
    kw_avg = pump_kw(q_avg_lps, depth_m, P, rm_head)
    kwh = kw_avg * 8760.0
    energy = kwh * _v(P, "tariff_rs_per_kwh") / 1e5
    om = energy + _v(P, "om_em_fraction") * em + _v(P, "om_civil_fraction") * civil
    om_npv = om * npv_factor(P)
    dia, hw = wet_well(q_peak_lps, depth_m, P)
    return {"components": comps, "civil": civil, "em": em, "power": power, "capex": civil + em + power,
            "kw": kw, "connected_kw": conn, "ht": ht, "head": head_m(depth_m, P, rm_head),
            "wet_well_dia": dia, "wet_well_height": hw, "energy_kwh_year": kwh, "energy_year": energy,
            "om_year": om, "om_npv": om_npv, "total_npv": civil + em + power + om_npv}


def fit_check(P=None):
    """Rows (station, Q L/s, part, DPR Rs lakh, model Rs lakh) - how the model reproduces the three stations."""
    P = P or load_params()
    rows = []
    L, R = P["data_points"]["Riverside SPS-1"], P["data_points"]["Lakeside SPS-1 + SPS-2"]
    d0 = L["incoming_depth_m"][0]
    cL = sps_cost(L["capacity_mld"][0] * MLD, 0.0, d0, P)
    cR = [sps_cost(q * MLD, 0.0, d if d is not None else d0, P)
          for q, d in zip(R["capacity_mld"], R["incoming_depth_m"])]
    rows.append(("Riverside SPS-1", "civil", L["civil_lakh"], cL["civil"]))
    rows.append(("Riverside SPS-1", "E&M", sum(L["em_lakh"].values()), cL["em"]))
    rows.append(("Lakeside SPS-1 + SPS-2", "civil", sum(R["civil_lakh_each"]), sum(c["civil"] for c in cR)))
    rows.append(("Lakeside SPS-1 + SPS-2", "E&M", sum(R["em_lakh"].values()), sum(c["em"] for c in cR)))
    return rows


def stp_cost_lakh(avg_flow_lps, P=None):
    """STP at the user's rate per MLD of average flow (Rs lakh)."""
    P = P or load_params()
    return avg_flow_lps / MLD * _v(P, "stp_lakh_per_mld")
