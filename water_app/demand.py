"""Daily water demand of a population, as in the UPJN DPRs and CPHEEO Table 2.7 (criteria.json):

    domestic  = population x LPCD x (1 + distribution losses)          150 x 1.10 = 165 LPCD   (S.No.4, S.No.6)
    floating  = population x floating share x floating LPCD             10 % x 45 LPCD          (S.No.5)
    fire      = 100 sqrt(P) m3/d for the city (P in thousands), shared by population            (S.No.13)

    d = daily_kl(pop, crit, city_pop)    -> {"domestic", "floating", "fire", "total"} in KL/day
    lps(d["total"])                      -> average L/s

Service storage (CPHEEO Table 2.7 S.No.12 p175): balancing capacity by mass balance or 33 % of the ultimate-stage
demand of the OZ, in any case not less than 33 %:

    storage_share(crit)                  -> max(33 %, mass balance) as a share of the daily demand
    mass_balance(crit)                   -> {"share", "hours", "rows": hourly inflow / draw-off / cumulative}
"""
import math
import re


def daily_kl(pop, crit, city_pop=None):
    v = lambda k: crit[k]["value"]
    pop = max(float(pop or 0.0), 0.0)
    dom = pop * v("lpcd") * (1 + v("distribution_losses")) / 1000.0
    flo = pop * v("floating_share") * v("floating_lpcd") / 1000.0
    city = max(float(city_pop or pop), 1.0)
    fire = 100.0 * math.sqrt(city / 1000.0) * (pop / city) if city >= 50000 else \
        100.0 * math.sqrt(50.0) * (pop / 50000.0)      # cities below 50,000: computed for 50,000, scaled down
    return {"domestic": dom, "floating": flo, "fire": fire, "total": dom + flo + fire}


def lps(kl_per_day):
    return kl_per_day / 86.4


def parse_windows(text):
    """'5-12, 13-22' -> [[5.0, 12.0], [13.0, 22.0]]: the hours of the day an OHT is filled (a window may pass midnight,
    '22-6')."""
    out = []
    for part in re.split(r"[,;]", str(text or "")):
        if not part.strip():
            continue
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*", part)
        if not m:
            raise ValueError(f"पानी भरने के घंटे '{part.strip()}' समझ नहीं आए - जैसे 5-12, 13-22 लिखें")
        a, b = float(m.group(1)), float(m.group(2))
        if not (0 <= a <= 24 and 0 <= b <= 24) or a == b:
            raise ValueError(f"पानी भरने के घंटे '{part.strip()}': 0 से 24 के बीच, शुरू और अंत अलग")
        out.append([a, b])
    if not out:
        raise ValueError("पानी भरने के घंटे खाली हैं - जैसे 5-12, 13-22 लिखें")
    return out


def _on(windows, h):
    """Hours of [h, h+1) inside the windows."""
    t = 0.0
    for a, b in windows:
        for lo, hi in ([(a, b)] if a < b else [(a, 24.0), (0.0, b)]):
            t += max(0.0, min(hi, h + 1) - max(lo, h))
    return t


def mass_balance(crit, windows=None):
    """Mass balance of an OHT over a day, in multiples of the average hourly demand (as the Elmwood DPR T3): inflow at
    24 / pumping hours during the filling windows, draw-off by the hourly pattern; balancing capacity = maximum
    excess - maximum deficit of the cumulative difference."""
    win = windows or crit["oht_inflow_hours"]["value"]
    draw = crit["draw_off_pattern"]["value"]
    on = [_on(win, h) for h in range(24)]
    hours = sum(on)
    if hours <= 0:
        raise ValueError("पानी भरने के घंटे 0 हैं")
    rate = 24.0 / hours
    rows, cin, cout, hi, lo = [], 0.0, 0.0, 0.0, 0.0
    for h in range(24):
        cin += on[h] * rate
        cout += draw[h]
        hi, lo = max(hi, cin - cout), min(lo, cin - cout)
        rows.append({"from": h, "to": h + 1, "inflow": round(on[h] * rate, 4), "draw": draw[h],
                     "cum_in": round(cin, 4), "cum_draw": round(cout, 4), "diff": round(cin - cout, 4)})
    return {"share": (hi - lo) / 24.0, "hours": hours, "excess": hi, "deficit": lo, "rows": rows}


def storage_share(crit, windows=None):
    """Share of the OZ's daily demand an OHT must hold: max(33 %, mass balance) - CPHEEO Table 2.7 S.No.12 p175."""
    return max(crit["esr_capacity_share"]["value"], mass_balance(crit, windows)["share"])


def standby(working, crit):
    """Standby for working pumps / tube wells as CPHEEO 5.7.5 (crit "standby_pumps": [[working up to, standby]])."""
    w = int(working or 0)
    if w <= 0:
        return 0
    tab = crit["standby_pumps"]["value"]
    return next((s for up, s in tab if w <= up), tab[-1][1])


def tubewells_new(pop_mid, crit, existing=0, bulk_kld=0.0):
    """New tube wells for the +15 years demand of the pumping main (CPHEEO Table 2.7 S.No.1 p168: pumps for +15 years) -
    as sheet TW of the DPR: (population x lpcd + floating x floating lpcd + bulk consumers' KLD) x 1.11, pumped in the
    tube wells' hours, less what the existing tube wells give, by tube wells of the proposed discharge, rounded up."""
    v = lambda k: crit[k]["value"]
    pop = max(float(pop_mid or 0.0), 0.0)
    kld = ((pop * v("lpcd") + pop * v("floating_share") * v("floating_lpcd")) / 1000.0 + max(float(bulk_kld or 0.0), 0.0)) \
        * v("pumping_main_factor")
    hours = v("tubewell_pumping_hours")
    net = max(0.0, kld - existing * v("existing_tubewell_lpm") * hours * 60 / 1000.0)
    return math.ceil(net * 1000.0 / (v("tubewell_discharge_lpm") * hours * 60) - 1e-9)
