"""dxf_inspect: what a text of the drawing is - a label, a level, an invert, a diameter - and its patterns."""
import os
import re
from sewer_app import PKG


BASE = os.path.dirname(PKG)                                             # the repository folder


OUT_DIR = os.path.join(BASE, "output", "dxf_inspect")


PIPE_NAME = re.compile(r"pipe|sewer|\bsw\b|^sw|main|line|nala|drain", re.I)


NOT_PIPE_NAME = re.compile(r"rail|road|boundary|electric|canal|pond|text|contour|building|plot|wall|"
                           r"tree|school|temple|well|site|hatch|grid|frame|title|dim", re.I)


OUTFALL_WORD = re.compile(r"\bSTP\b|OUT\s*FALL|\bSPS\b|\bIPS\b|\bMPS\b|\bPS\b|DISPOSAL|PUMPING|TREATMENT|"
                          r"EXIST(ING)?\s*(SEWER|MH|MANHOLE)|TRUNK", re.I)


# SEWER: an invert level (IL) is always below the GL at its manhole (user remark 22-Oct-2026: '0.05 m केवल 5 cm?
# न्यूनतम पाइप व्यास ही 15 cm है') -
IL_MIN_DEPTH_M = 0.15    # at least the smallest sewer (150 mm internal, CPHEEO; design_criteria min_diameter_mm) - less:


                         # its crown would be above the ground, so no IL (not taken);
IL_SHALLOW_M = 1.05      # less than the cover 0.9 m (CPHEEO p3-124, mandatory) + that pipe: taken, but a CHECK;


IL_MAX_DEPTH_M = 15.0    # at most this (deeper: not this manhole's IL, or a wrong text)


Z_TEXT_AGREE_M = 1.0     # Z of the lines is the ground only if within this of the GL texts (median)


LEVEL_TAG = re.compile(r"^(GL|G\.L|RL|R\.L|GROUND|ELEV|ELEVATION|LEVEL|NGL|EGL|LVL|Z)\b", re.I)


INVERT_TAG = re.compile(r"^(IL|I\.L|INV|INVERT)\b", re.I)


NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


ID_RE = re.compile(r"^\s*([A-Za-z]{1,8})\s*[-_ /]\s*(\d+[A-Za-z]?)\s*$")


DEC_RE = re.compile(r"^\s*(?:(GL|G\.L\.?|RL|R\.L\.?|NGL|EGL|EL|ELEV|LEVEL|TBM)\s*[:=.\-]?\s*)?(\d{1,4}\.\d{1,3})\s*(m|M)?\s*$")


IL_RE = re.compile(r"^\s*(IL|I\.L\.?|INV|INVERT)\s*[:=.\-]?\s*(\d{1,4}(?:\.\d{1,3})?)\s*(m|M)?\s*$", re.I)


DIA_RE = re.compile(r"^\s*(?:dia\.?\s*|%%c\s*|\u00d8\s*)?([\d,]+(?:\.\d+)?)\s*mm\s*(?:dia\.?)?\s*$", re.I)


SLOPE_RE = re.compile(r"^\s*([\d,]+(?:\.\d+)?)\s*1\s*/\s*S\s*$|^\s*1\s*(?:in|:)\s*([\d,]+(?:\.\d+)?)\s*$", re.I)


def classify(text):
    """Kinds found in a (multi-line) text: list of (kind, value) with kind in
    id / level / invert / dia / slope_1in. 'level' = a decimal number (1-3 decimals, optional m)."""
    out = []
    for ln in re.split(r"[\r\n]+|\\P", text or ""):
        ln = ln.strip()
        if not ln:
            continue
        m = ID_RE.match(ln)
        if m:
            out.append(("id", f"{m.group(1).upper()}-{m.group(2)}"))
            continue
        m = IL_RE.match(ln)
        if m:
            out.append(("invert", float(m.group(2))))
            continue
        m = DEC_RE.match(ln)
        if m:
            out.append(("level", float(m.group(2))))
            continue
        m = DIA_RE.match(ln)
        if m:
            out.append(("dia", float(m.group(1).replace(",", ""))))
            continue
        m = SLOPE_RE.match(ln)
        if m:
            out.append(("slope_1in", float((m.group(1) or m.group(2)).replace(",", ""))))
    return out


UNITS = {0: "unitless", 1: "inches", 2: "feet", 4: "mm", 5: "cm", 6: "m", 7: "km"}
