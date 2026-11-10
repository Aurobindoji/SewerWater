"""Start the app in the browser (sewer_ui.bat): the launcher's start page - the language, then sewer or water.

    start page : launcher/server.py     http://127.0.0.1:8764/
    sewer      : sewer_app/ui.py        http://127.0.0.1:8765/sewer    started only when chosen
    water      : water_app/server.py    http://127.0.0.1:8766/water    started only when chosen

User decision 10-Nov-2026: the two apps are fully independent - the module chosen opens alone (in the start page's
tab); the other starts only from its button beside "CPHEEO / language" on a module's page, in a tab of its own.
Each module also runs alone: python -m sewer_app ui, python -m water_app ui (water_ui.bat).
"""
import sys

from launcher import server as launcher


def main(argv):
    launcher.serve(open_browser="--no-browser" not in argv)      # Ctrl+C stops it and the modules it started


if __name__ == "__main__":
    main(sys.argv[1:])
