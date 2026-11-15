"""The rates the DPR of a design uses - the yellow of the rate xlsx (rates.py; restructure stage 3, 15-Nov-2026: out
of rates.py, so that rates does not import the DPR): the DPR written to a temporary folder (nothing left behind) with the
UPJN reads noted (rates._track), its SOR VLOOKUPs read back."""
import os
import re
import shutil
import tempfile

from .. import rates
from .workbook import write_dpr


LOOKUP = re.compile(r"VLOOKUP\(([^,()]+),'?[^,!']*SOR[^,!']*'?!\$A", re.I)
CELL = re.compile(r"^(?:'?([^'!]+)'?!)?\$?([A-Z]{1,3})\$?(\d+)$")


def used(info):
    """({SOR codes}, {UPJN key: {sizes}}) the DPR of this design (dpr_info) uses: the DPR written to a temporary
    folder (nothing left behind) with the UPJN reads noted, its SOR VLOOKUPs read back."""
    import openpyxl

    tmp = tempfile.mkdtemp(prefix="wrates_")
    try:
        rates._track = {}
        try:
            path = write_dpr(info, os.path.join(tmp, "probe_DPR.xlsx"))
        finally:
            upjn, rates._track = rates._track, None
        wb = openpyxl.load_workbook(path)
        codes = set()
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    v = c.value
                    if not (isinstance(v, str) and "VLOOKUP" in v.upper()):
                        continue
                    for arg in LOOKUP.findall(v):
                        a = arg.strip()
                        m = CELL.match(a.replace(" ", ""))
                        if m:
                            sh = wb[m.group(1)] if m.group(1) and m.group(1) in wb.sheetnames else ws
                            a = sh[f"{m.group(2)}{m.group(3)}"].value
                        elif a.startswith('"') and a.endswith('"'):
                            a = a[1:-1]
                        k = rates._code(a)
                        if k:
                            codes.add(k)
        wb.close()
        return codes, upjn
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
