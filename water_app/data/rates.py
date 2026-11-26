"""The rates of the water DPR, changeable by the user (user decisions 15-Nov-2026): Export rate xlsx / Import rate xlsx.

Two kinds, as the DPR uses them:
  SOR   - the schedule of rates 2025-26 (sor_2025_26.json, sheet 'R SOR 2025-26' of the DPR, read there by VLOOKUP of
          the item number);
  UPJN  - the U.P. Jal Nigam rates by size in dpr_water.json (pipe supply HDPE / DI K-7, DI K-9, HDPE carting, NRV,
          PRV).
An imported xlsx changes only the rates of the items and sizes the app has (the list itself stays: the DPR's formulas
point at it); the changed rates are kept in the master folder (<HOME>\\rates\\water_rates.json) for every project and
outlive an update of the app. 'मूल rates वापस' (reset) removes that file.
The exported xlsx marks yellow the rates the project's last design's DPR uses (dpr/usage.py finds them by
writing that DPR to a temporary file: its SOR VLOOKUPs and the UPJN rates it read).
"""
import contextlib
import io
import json
import os
import time

from water_app import HOME, PKG

HERE = PKG                                       # the package folder: the SOR, the DPR settings
SOR_FILE = os.path.join(HERE, "sor_2025_26.json")
SETTINGS_FILE = os.path.join(HERE, "dpr_water.json")
USER_FILE = os.path.join(HOME, "rates", "water_rates.json")
# the UPJN rates by size of dpr_water.json: (key, text, unit)
UPJN = [("pipe_supply", "Pipe supply - HDPE PN-6 PE-100 / DI K-7 (UPJN M.194 / M.193)", "Rs / m"),
        ("pipe_supply_k9", "Pipe supply - DI K-9 (UPJN M.193, rising mains)", "Rs / m"),
        ("hdpe_carting", "HDPE carting, laying, jointing and testing (AOR)", "Rs / m"),
        ("nrv_rate", "Non-return valve - supply (UPJN), by dia mm", "Rs / no."),
        ("prv_rate", "Pressure reducing valve - INDICATIVE, by dia mm", "Rs / no.")]
UPJN_KEYS = [k for k, _, _ in UPJN]
YELLOW = "FFFF00"
SOR_SHEET, UPJN_SHEET = "SOR", "UPJN rates"
HEAD_ROW = 4                                    # the header row of both sheets; the rows below it the items

_track = None             # {key: set of sizes} while a DPR is written to find the rates it uses (dpr/usage.py)


def user_rates():
    """{"sor": {code: rate}, "upjn": {key: {size: rate}}, "file", "time"} of the last import, or {}."""
    try:
        with open(USER_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _base_sor():
    with open(SOR_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def _base_upjn():
    with open(SETTINGS_FILE, encoding="utf-8") as fh:
        s = json.load(fh)
    return {k: dict(s[k]["value"]) for k in UPJN_KEYS}


class _Keys:
    """The key of each SOR row with an item number: the number; the n-th row of a number met before 'number#n' (the SOR
    has 2.7.4.2 twice - Mixed Strata, Rock)."""

    def __init__(self):
        self.seen = {}

    def __call__(self, code):
        k = _code(code)
        n = self.seen[k] = self.seen.get(k, 0) + 1
        return k if n == 1 else f"{k}#{n}"


def _base_items():
    key = _Keys()
    return {key(c): r for c, _, _, r in _base_sor()["items"] if _code(c)}           # r None: a heading with a number


def sor():
    """The SOR as sor_2025_26.json ({title, items: [[code, text, unit, rate]]}) with the user's rates."""
    d = _base_sor()
    mine = user_rates().get("sor") or {}
    if mine:
        key, items = _Keys(), []
        for c, t, u, r in d["items"]:
            if _code(c):
                k = key(c)
                r = mine.get(k, r) if r is not None else r
            items.append([c, t, u, r])
        d["items"] = items
    return d


class _Seen(dict):
    """A rate table that notes the sizes read from it (while _track is set)."""

    def __init__(self, key, d):
        super().__init__(d)
        self.key = key

    def _note(self, k):
        if _track is not None:
            _track.setdefault(self.key, set()).add(str(k))

    def __getitem__(self, k):
        self._note(k)
        return super().__getitem__(k)

    def get(self, k, default=None):
        if k in self:
            self._note(k)
        return super().get(k, default)


def apply(S):
    """dpr.settings() with the user's UPJN rates (in place; returns S)."""
    mine = user_rates().get("upjn") or {}
    for k in UPJN_KEYS:
        if k in S:
            S[k] = _Seen(k, {s: mine.get(k, {}).get(str(s), r) for s, r in S[k].items()})
    return S


def _num(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        raise ValueError(f"'{v}' संख्या नहीं / not a number") from None


def _code(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip() if v not in (None, "") else ""


# ------------------------------------------------------------------------------------------------------- the xlsx
def export_xlsx(path, use=None, note=""):
    """The rate workbook at path: sheet SOR (Item No., description, unit, rate, the app's rate) and sheet UPJN rates
    (key, item, size, unit, rate, the app's rate); the rates in use (use = used()) yellow. Returns
    {"path", "sor_used", "upjn_used", "changed"}."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    codes, upjn = use or (set(), {})
    fill = PatternFill("solid", start_color=YELLOW, end_color=YELLOW)
    bold, wrap = Font(bold=True), Alignment(wrap_text=True, vertical="top")
    base_items, key = _base_items(), _Keys()
    d = sor()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SOR_SHEET
    ws["A1"] = d.get("title") or "SCHEDULE OF RATES"
    ws["A1"].font = bold
    ws["A2"] = ("पीली पंक्ति = इस project की आख़िरी Design की DPR में उपयोग हो रहा rate. सिर्फ़ 'Rate' column बदलें; "
                "Item No. / पंक्तियाँ न जोड़ें न हटाएँ - फिर 'Import rate xlsx…' से app में लें. / Yellow = a rate the DPR "
                "of the project's last design uses. Change only the 'Rate' column, then 'Import rate xlsx…'.")
    ws["A3"] = note
    heads = ["Item No.", "Description of item", "Unit", "Rate", "App rate (SOR 2025-26)"]
    for j, (h, w) in enumerate(zip(heads, [10, 90, 10, 14, 14]), 1):
        ws.cell(HEAD_ROW, j, h).font = bold
        ws.column_dimensions["ABCDE"[j - 1]].width = w
    n_sor = changed = 0
    for i, (c, t, u, r) in enumerate(d["items"]):
        x = HEAD_ROW + 1 + i
        k = _code(c)
        ws.cell(x, 1, int(k) if k.isdigit() else (k or None))
        ws.cell(x, 2, t).alignment = wrap
        ws.cell(x, 3, u or None)
        ws.cell(x, 4, r)
        r0 = base_items.get(key(c)) if k else None
        if k and r is not None:
            ws.cell(x, 5, r0)
            changed += r0 != r
        if k in codes and r is not None:
            n_sor += 1
            for j in range(1, 6):
                ws.cell(x, j).fill = fill
        if not k or r is None:
            ws.cell(x, 2).font = bold
    ws.freeze_panes = ws.cell(HEAD_ROW + 1, 1)
    ws2 = wb.create_sheet(UPJN_SHEET)
    ws2["A1"] = "U.P. JAL NIGAM RATES BY SIZE (dpr_water.json)"
    ws2["A1"].font = bold
    ws2["A2"] = ws["A2"].value
    ws2["A3"] = note
    heads = ["Key", "Item", "Size", "Unit", "Rate", "App rate"]
    for j, (h, w) in enumerate(zip(heads, [16, 60, 12, 10, 14, 14]), 1):
        ws2.cell(HEAD_ROW, j, h).font = bold
        ws2.column_dimensions["ABCDEF"[j - 1]].width = w
    base = _base_upjn()
    mine = user_rates().get("upjn") or {}
    x, n_upjn = HEAD_ROW + 1, 0
    for k, text, unit in UPJN:
        for s, r0 in base[k].items():
            r = mine.get(k, {}).get(str(s), r0)
            for j, v in enumerate([k, text, s, unit, r, r0], 1):
                ws2.cell(x, j, v)
            changed += r != r0
            if str(s) in (upjn.get(k) or ()):
                n_upjn += 1
                for j in range(1, 7):
                    ws2.cell(x, j).fill = fill
            x += 1
    ws2.freeze_panes = ws2.cell(HEAD_ROW + 1, 1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return {"path": path, "sor_used": n_sor, "upjn_used": n_upjn, "changed": changed}


def _header(ws, want):
    """The row and {name: column} of the header row (the first row with want[0] in it)."""
    for r in range(1, 15):
        names = {str(ws.cell(r, c).value or "").strip().lower(): c for c in range(1, 12)}
        if want[0].lower() in names:
            miss = [w for w in want if w.lower() not in names]
            if miss:
                raise ValueError(f"sheet '{ws.title}': column {', '.join(miss)} नहीं / missing")
            return r, {w: names[w.lower()] for w in want}
    raise ValueError(f"sheet '{ws.title}': '{want[0]}' वाली header row नहीं मिली / no header row")


def import_xlsx(data, fname=""):
    """Reads an exported (and changed) rate xlsx (bytes): the rates that differ from the app's own are kept as the
    user's (USER_FILE), for every project. Items / sizes the app does not have are left out (told in notes); an empty
    rate cell keeps the app's rate. Returns {"sor_changed", "upjn_changed", "notes": [[hi, en]]}."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=False)
    except Exception as e:
        raise ValueError(f"xlsx नहीं खुली / not an xlsx: {type(e).__name__}") from None
    if SOR_SHEET not in wb.sheetnames and UPJN_SHEET not in wb.sheetnames:
        raise ValueError(f"इसमें '{SOR_SHEET}' / '{UPJN_SHEET}' sheet नहीं - 'Export rate xlsx' वाली file चुनें / "
                         f"not an exported rate xlsx")
    notes = []
    base_items, key = _base_items(), _Keys()
    new_sor, extra = {}, []
    if SOR_SHEET in wb.sheetnames:
        ws = wb[SOR_SHEET]
        h, col = _header(ws, ["Item No.", "Rate"])
        for r in range(h + 1, ws.max_row + 1):
            k = _code(ws.cell(r, col["Item No."]).value)
            if not k:
                continue
            try:
                v = _num(ws.cell(r, col["Rate"]).value)
            except ValueError as e:
                raise ValueError(f"SOR row {r} (item {k}): {e}") from None
            kk = key(k)
            if kk not in base_items:
                extra.append(k)
            elif base_items[kk] is not None and v is not None and v != base_items[kk]:
                new_sor[kk] = v
    base = _base_upjn()
    new_upjn, extra_u = {}, []
    if UPJN_SHEET in wb.sheetnames:
        ws = wb[UPJN_SHEET]
        h, col = _header(ws, ["Key", "Size", "Rate"])
        for r in range(h + 1, ws.max_row + 1):
            k = str(ws.cell(r, col["Key"]).value or "").strip()
            if not k:
                continue
            s = _code(ws.cell(r, col["Size"]).value)
            try:
                v = _num(ws.cell(r, col["Rate"]).value)
            except ValueError as e:
                raise ValueError(f"UPJN row {r} ({k} {s}): {e}") from None
            if k not in base or s not in {str(x) for x in base[k]}:
                extra_u.append(f"{k} {s}")
                continue
            r0 = next(rv for sz, rv in base[k].items() if str(sz) == s)
            if v is not None and v != r0:
                new_upjn.setdefault(k, {})[s] = v
    if extra:
        notes.append([f"SOR के {len(extra)} item app में नहीं, छोड़े: " + ", ".join(extra[:10]) + (" …" if len(extra) > 10 else ""),
                      f"{len(extra)} SOR items not in the app, left out: " + ", ".join(extra[:10]) + (" ..." if len(extra) > 10 else "")])
    if extra_u:
        notes.append(["UPJN की ये पंक्तियाँ app में नहीं, छोड़ीं: " + ", ".join(extra_u[:10]),
                      "UPJN rows not in the app, left out: " + ", ".join(extra_u[:10])])
    keep = {"sor": new_sor, "upjn": new_upjn, "file": os.path.basename(fname or ""),
            "time": time.strftime("%d-%m-%Y %H:%M")}
    os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
    tmp = USER_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, USER_FILE)
    return {"sor_changed": len(new_sor), "upjn_changed": sum(len(v) for v in new_upjn.values()), "notes": notes,
            "file": keep["file"], "time": keep["time"]}


def reset():
    """Back to the app's own rates (the user's file removed). Returns whether there was one."""
    with contextlib.suppress(FileNotFoundError):
        os.remove(USER_FILE)
        return True
    return False


def stamp():
    """Which rates are in use: "" the app's own, else the time of the import (a DPR written before it is old)."""
    u = user_rates()
    return f"{u.get('time', '')}|{u.get('file', '')}" if u else ""


def status():
    """{"changed": n rates the user's own, "file", "time"} for the page."""
    u = user_rates()
    n = len(u.get("sor") or {}) + sum(len(v) for v in (u.get("upjn") or {}).values())
    return {"changed": n, "file": u.get("file") or "", "time": u.get("time") or ""}
