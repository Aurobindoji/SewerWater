# PyInstaller spec of the desktop app (user request 30-Oct-2026): one folder dist\SewerWater with SewerWater.exe -
# runs without Python; the projects and results go to Documents\SewerWater (sewer_app.HOME / water_app.HOME).
#     .venv\Scripts\python -m PyInstaller SewerWater.spec --noconfirm        (build_exe.bat)
from PyInstaller.utils.hooks import collect_submodules

datas = [("data", "data"),                                   # sewer: criteria, catalogue, SOR, DPR templates
         ("sewer_app/static", "sewer_app/static"),            # the pages
         ("water_app/static", "water_app/static"),
         ("water_app/criteria.json", "water_app"), ("water_app/pipes.json", "water_app"),
         ("water_app/dpr_water.json", "water_app"), ("water_app/sor_2025_26.json", "water_app"),
         ("water_app/dpr_template.xlsx", "water_app")]

a = Analysis(
    ["app.py"],
    pathex=["."],
    datas=datas,
    # the modules a server imports inside its functions (from . import netedit ...): all of both packages
    hiddenimports=collect_submodules("sewer_app") + collect_submodules("water_app"),
    excludes=["tkinter", "pytest", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SewerWater", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="SewerWater")
