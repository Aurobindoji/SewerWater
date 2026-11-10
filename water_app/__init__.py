"""Water supply network: zoning (OZ / DMA) and design to CPHEEO (Manual on Water Supply 2024) - see criteria.json."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the code and its data (read only when packed)


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
    """The water module's data folder - its projects\\ and output\\ (the water module's copy of sewer_app._home,
    isolation of the modules): WATER_APP_HOME when set (the desktop app: <master folder>\\Water, chosen by the user -
    user request 30-Oct-2026); the app packed without it: Documents\\SewerWater\\Water; else water_app\\ of the
    repository, as before."""
    if os.environ.get("WATER_APP_HOME"):
        return os.environ["WATER_APP_HOME"]
    if getattr(sys, "frozen", False):
        return os.path.join(_documents(), "SewerWater", "Water")
    return os.path.join(ROOT, "water_app")


HOME = _home()


class DesignError(Exception):
    """Input or network problem that stops a run."""
