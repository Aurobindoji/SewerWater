"""Isolation of sewer and water (user request 21-Oct-2026): each module works from its own folder - loading every
module of one never loads a module of the other, so a change in one cannot change the other's behaviour."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = """
import importlib, pkgutil, sys
pkg = importlib.import_module("{mine}")
for m in pkgutil.iter_modules(pkg.__path__):
    if m.name in {skip!r}:
        continue
    importlib.import_module("{mine}." + m.name)
other = sorted(k for k in sys.modules if k == "{other}" or k.startswith("{other}."))
print("OTHER:" + ",".join(other))
"""


def loaded(mine, other, skip=()):
    out = subprocess.run([sys.executable, "-c", CODE.format(mine=mine, other=other, skip=list(skip))], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return next(l for l in out.stdout.splitlines() if l.startswith("OTHER:"))[6:]


def test_water_loads_nothing_of_sewer():
    assert loaded("water_app", "sewer_app", skip=("pdf2dxf",)) == ""      # pdf2dxf: the user's own script


def test_sewer_loads_nothing_of_water():
    assert loaded("sewer_app", "water_app") == ""


def test_own_pages_and_servers():
    from sewer_app import ui
    from water_app import server
    assert os.path.dirname(ui.STATIC) != os.path.dirname(server.STATIC)
    assert server.PORT != 8765 and ui.PROJECTS != server.PROJECTS and ui.OUT_ROOT != server.OUT_ROOT
    for f, mod in ((os.path.join(ui.STATIC, "map.html"), "sewer"), (os.path.join(server.STATIC, "map.html"), "water")):
        with open(f, encoding="utf-8") as fh:
            assert f'const MODULE = "{mod}";' in fh.read()
