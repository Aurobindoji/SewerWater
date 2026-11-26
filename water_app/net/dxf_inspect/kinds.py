"""dxf_inspect: what a text of the drawing is - a label, a level, a diameter, a length - and its patterns."""
import re


PIPE_NAME = re.compile(r"pipe|sewer|\bsw\b|^sw|main|line|nala|drain", re.I)


# 16-Nov-2026 (a survey drawing): its power line "Ex-Utility-HT Line" and the road "CENTER LINE" were taken for pipes
NOT_PIPE_NAME = re.compile(r"rail|road|boundary|electric|canal|pond|text|contour|building|plot|wall|"
                           r"tree|school|temple|well|site|hatch|grid|frame|title|dim|utility|\bht\b|\blt\b|power|"
                           r"telephone|cable|\bofc\b|cent(er|re)\s*line", re.I)


Z_TEXT_AGREE_M = 1.0     # WATER: Z of the lines is the ground only if within this of the GL texts (median)


LEVEL_TAG = re.compile(r"^(GL|G\.L|RL|R\.L|GROUND|ELEV|ELEVATION|LEVEL|NGL|EGL|LVL|Z)\b", re.I)


NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


# a name: MH-12, J-7A, and in two parts MH-3-441 (zone 3, manhole 441 - 16-Nov-2026, a key plan's every name)
ID_RE = re.compile(r"^\s*([A-Za-z]{1,8})\s*[-_ /]\s*(\d+(?:-\d+)?[A-Za-z]?)\s*$")


# a level, bare or with its tag - E-77.31 m and EL-77.87 m too (16-Nov-2026: two index plans and a key plan write
# the ground level so; it was not read at all)
DEC_RE = re.compile(r"^\s*(?:(GL|G\.L\.?|RL|R\.L\.?|NGL|EGL|EL|ELEV|LEVEL|TBM|E)\s*[:=.\-]?\s*)?(\d{1,4}\.\d{1,4})\s*(m|M)?\s*$")


LEVEL_SPREAD_M = 50.0    # the ground levels of one drawing lie within this (5 % to 95 %): pipe lengths do not


LEVEL_FAR_M = 25.0       # a level this far from the drawing's middle level is a typing error (777.08 for 77.708)


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
