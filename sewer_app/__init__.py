"""sewer_app - gravity sewer design to CPHEEO rules, without SewerGEMS.

The design logic is taken from the original scripts (sewer_design.py, design_check.py, zoning.py), where it was
checked against SewerGEMS; here it works on plain Python data (CSV / JSON), no OpenFlows API.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the code and its data (read only when packed)
DATA_DIR = os.path.join(ROOT, "data")


def _documents():
    """The user's Documents folder (where Windows has it, also when moved to OneDrive)."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:      # CSIDL_PERSONAL
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def _home():
    """The sewer module's data folder - its projects\\ and output\\ (user request 30-Oct-2026, the desktop app):
    SEWER_APP_HOME when set (the desktop app: <master folder>\\Sewer, chosen by the user); the app packed without it:
    Documents\\SewerWater\\Sewer (its own folder is read only); else the repository, as before."""
    if os.environ.get("SEWER_APP_HOME"):
        return os.environ["SEWER_APP_HOME"]
    if getattr(sys, "frozen", False):
        return os.path.join(_documents(), "SewerWater", "Sewer")
    return ROOT


HOME = _home()


class DesignError(Exception):
    """Input or network problem that stops a design (the scripts in the original scripts used sys.exit)."""
