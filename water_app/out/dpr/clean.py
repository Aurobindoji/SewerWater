"""A DPR's texts without the source of their figures (user 22-Nov-2026: the public need not be told where a figure
comes from - no DPR and its page, no workbook's sheet and cell, no town, firm or department as the source; the
department's own name is the Project sheet's 'Department / implementing agency'). Applied to every text cell and to
the texts inside formulas just before the workbook is saved; the values and the method stay.

    clean.workbook(wb)      # in place
    clean.text(s) -> s
"""
import re

_I = re.I
SRC = r"(?:Riverside|Elmwood)"
DPR = SRC + r"(?: water)? DPRs?(?: \(U\.P\. Jal Nigam \d{4}\))?"
PAGES = r"p\d+(?:[-–]\d+)?(?:(?:,| and| &)? ?p?\d+(?:[-–]\d+)?)*"
REF = r"(?:'[^']*'(?: / '[^']*')*|[A-Z][\w]*\d*)"               # a sheet: 'Tech ' / T / T3 / 'a' / 'b'
CELL = r"(?: (?:row )?[A-Z]{0,3}\d+(?::[A-Z]{1,3}\d+)?)?"
DEPT = r"U\.? ?P\.? ?Jal Nigam(?: \(Urban\))?|Uttar Pradesh Jal Nigam|UPJN"

RULES = [
    # ---- whole phrases, by what they are
    (r"^As the " + DPR + r" \((.*)\)\.$", r"\1."),
    (r"E&M RATES - U\.P\. JAL NIGAM E&M ESTIMATE RIVERSIDE R3 \([^)]*\)", "E&M RATES"),
    (r"E&M RATES \(U\.P\. JAL NIGAM E&M ESTIMATE R2, DISTRICT \w+ ZONE \w+\)", "E&M RATES"),
    (r"COST INDEX OF SPRINGFIELD", "DISTRICT COST INDEX"),
    (r"Cost index for Springfield", "Cost index of the district"),
    (r"Springfield cost index", "district cost index"),
    (r"Unit Estimate Springfield Urban", "Unit Estimate"),
    (r"(pea gravel [\d.]+) Springfield", r"\1"),
    (r"example technical\.xlsx \(" + SRC + r"\) '[^']*':\s*", ""),
    (r"\s*-\s*average of UPJN order .*$", "."),
    (DPR + r" p345 \(.*?\) and p346-349 \(.*?\)\.\s*", ""),
    (SRC + r" DPR \(UPJN \w+\): population / households = [\d ./]+= ([\d.]+) \(\d{4}\)", r"default persons per household \1"),
    (r"^" + DPR + r" p55 'DMA equipment[^']*' and p329-331 \(([^)]*)\).*$", r"DMA equipment: \1"),
    (r",? as the Elmwood and Riverside DPRs", ""),
    (r"\s*\(" + DPR + r" unit estimates\)", ""),
    (DPR + r" values\b", "values"),
    (r",? U\.P\. Jal Nigam E&M estimate Riverside R3", ""),
    (r"\s*\(U\.P\. Jal Nigam E&M estimate Riverside R3, [\d.]+\)", ""),
    (r" \(lengths as the quantities of DPR [^)]*\)", ""),
    (r"\s*\(as (?:the )?DPR " + PAGES + r"\)", ""),
    (r"(SOR of the CE \(E/M\))(?: U\.P\. Jal Nigam)? p\d+(?:-\d+)?", r"\1"),
    (r",? as (?:the )?" + DPR + r"(?=[\s,;.)]|$)", ""),
    # ---- citations: a DPR and its pages / sheet / cell, as a lead-in or in a clause
    (r"\(" + DPR + r"(?: " + PAGES + r")?:\s*", "("),
    (DPR + r"(?: " + PAGES + r")? = ", ""),
    (DPR + r"(?: practice)?(?: " + REF + r")?" + CELL + r"(?: " + PAGES + r")?(?: \([^()]*\))?(?: " + REF + r")?\s*[:;]\s*", ""),
    (r"\s*-\s*" + DPR + r" " + PAGES, ""),
    (r" of the " + DPR + r" " + PAGES, ""),
    (r"(?:,? as (?:the |in the )?)?" + SRC + r"(?: DPR)? " + REF + CELL + r"(?: -> )?", ""),
    (r"\bR[23] '[^']*'(?: [A-Z]+\d+)?:?\s*", ""),
    (r",? as " + SRC + r"\b(?! DPR)", ""),
    (r",? as (?:the )?DPR " + PAGES + r"(?::[^)]*)?", ""),
    (r";?\s*DPR " + PAGES, ""),
    (r"\s*-\s*data/[\w./]+ '[^']*'", ""),
    (r" (?:of )?(?:its )?unit estimate " + PAGES, " of its unit estimate"),
    # ---- the department: its name only in sheet Project
    (r"\s*-\s*U\.P\. JAL NIGAM,", " -"),
    (r"\(U\.P\. JAL NIGAM (STANDARD COST OF \w+)\)", r"(\1)"),
    (r"^(?:" + DEPT + r"):\s*", ""),
    (r"\b(?:the )?(?:" + DEPT + r")(?:'s)?\s+(practice|rule|standard cost|supply rate|rates?|order)\b", r"\1"),
    (r"(?:" + DEPT + r")\s*:\s*(\d)", r"\1"),
    (r"\s*\((?:" + DEPT + r")\s*(?:\w+\s*)?\)", ""),
    (r"SOR (?:" + DEPT + r"|Jal Nigam)", "SOR"),
    (r"UPJN_", ""),
    (r"Govt\. of U\.P\.", "State Govt."),
    (r"\s*(?:,\s*)?(?:" + DEPT + r")\b(?:\s*\(Urban\))?", ""),
    (r"\s*JAL NIGAM\b", ""),
    # ---- what is left of a source: a bracket naming one goes, then the names themselves
    (r"\s*\([^()]*(?:Riverside|Elmwood|Westbrook|Lakeside|City Council|DPR p\d|technical\.xlsx|\bR[23]\b|user decision|"
     r"user \d)[^()]*\)", ""),
    # (no rule for a bare town's name: it may be the user's own - a ward, the ULB - and the user's own texts stay)
    (r"\s*\bexample technical\.xlsx\b", ""),
]
RULES = [(re.compile(a, _I), b) for a, b in RULES]
TIDY = [(re.compile(a), b) for a, b in [
    (r"\(\s*\)", ""), (r"\(\s*[;,:]\s*", "("), (r"\s*[;,:]\s*\)", ")"), (r":\s*;", ";"), (r";\s*;", ";"),
    (r"\s+([,;:.)])", r"\1"), (r"\(\s+", "("), (r" {2,}", " "), (r"^[\s\-:;,]+", ""), (r"[\s\-:;,]+$", ""),
    (r"\s+-\s*$", ""), (r"\s*\(e\.g\.\)", ""), (r"^\((\w[^()]*)\)", r"\1")]]


def text(s):
    if not s or not isinstance(s, str):
        return s
    t = s
    for rx, rep in RULES:
        t = rx.sub(rep, t)
    if t == s:
        return s
    for rx, rep in TIDY:
        t = rx.sub(rep, t)
    if s[:1].isupper() and t[:1].islower():
        t = t[:1].upper() + t[1:]
    if s.rstrip().endswith(".") and t and not t.endswith((".", ")")):
        t += "."
    return t


def formula(f):
    """The texts inside a formula's quotes."""
    return re.sub(r'"((?:[^"]|"")*)"', lambda m: '"' + text(m.group(1).replace('""', '"')).replace('"', '""') + '"', f)


def workbook(wb):
    """Every text of the workbook - but the user's own: the values typed in sheet Project (its column C) and any text
    that holds one of them (a heading with the ULB's name, a ward's row) stay as they are."""
    own = set()
    if "Project" in wb.sheetnames:
        for (v,) in wb["Project"].iter_rows(min_col=3, max_col=3, values_only=True):
            if isinstance(v, str) and len(v.strip()) >= 4 and not v.startswith("=") and any(ch.isupper() for ch in v):
                own.add(v.strip().lower())            # a name (the ULB, a town) - not a method like 'geometrical'
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if isinstance(v, str) and (ws.title == "Project" and c.column == 3 or any(o in v.lower() for o in own)):
                    continue
                if isinstance(v, str):
                    nv = formula(v) if v.startswith("=") else text(v)
                    if nv != v:
                        c.value = nv
    return wb
