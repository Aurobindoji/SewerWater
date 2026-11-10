"""Start both map pages - each module on its own server (isolation of sewer and water, user request 21-Oct-2026):

    sewer : sewer_app/ui.py      http://127.0.0.1:8765/   (also the start page: language, module)
    water : water_app/server.py  http://127.0.0.1:8766/water

Only starts them; the two modules share no code. One browser tab opens - the start page, "Sewer network design" -
and choosing water there opens the water page in a tab of its own, "Water network design" (user request
22-Oct-2026; before, 21-Oct-2026, each server opened its own tab). sewer_ui.bat runs this file; water_ui.bat starts
the water one alone (python -m water_app ui, its own tab), python -m sewer_app ui the sewer one alone.
"""
import sys
import threading

from sewer_app import ui as sewer_ui
from water_app import server as water_server


def main(argv):
    no_browser = "--no-browser" in argv
    # one tab: the start page (sewer, 8765); the water server opens none - its page opens from the start page
    threading.Thread(target=water_server.serve, kwargs={"open_browser": False}, daemon=True).start()
    sewer_ui.serve(open_browser=not no_browser)          # Ctrl+C stops both


if __name__ == "__main__":
    main(sys.argv[1:])
