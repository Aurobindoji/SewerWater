"""The water DPR workbook (Excel) in the format of the U.P. Jal Nigam estimates (restructure stage 3, 15-Nov-2026:
dpr.py and dpr_*.py made one package). Its parts, each importing only those before it:
    base          settings, the SOR file, Book (the workbook and its styles), helpers
    info          dpr_info - what the workbook needs from a design
    technical     Project sheet, technical statement (T sheets)
    distribution  pipes, DS estimate, house connections, rate sheet, unit estimates, SOR sheet
    tanks         OHT and CWR estimates
    rising_main   the rising mains of the new tube wells (D5 / T15)
    civil, em, emd, tech, more, front, style   the other sheet groups
    workbook      write_dpr - the whole workbook
    usage         the rates a design's DPR uses (the rate xlsx's yellow)
"""
from .base import SETTINGS_FILE, SOR_FILE, previous_dpr, settings, table_rate  # noqa: F401
from .info import dpr_info  # noqa: F401
from .workbook import write_dpr  # noqa: F401
