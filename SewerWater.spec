# PyInstaller spec of the desktop app (user request 30-Oct-2026): one folder dist\SewerWater with SewerWater.exe -
# runs without Python; the projects and results go to Documents\SewerWater (sewer_app.HOME / water_app.HOME).
#     .venv\Scripts\python -m PyInstaller SewerWater.spec --noconfirm        (build_exe.bat)
from PyInstaller.utils.hooks import collect_submodules

datas = [("data", "data"),                                   # sewer: criteria, catalogue, SOR, DPR templates
         ("sewer_app/static", "sewer_app/static"),            # the pages
         ("water_app/static", "water_app/static"),
         ("water_app/criteria.json", "water_app"), ("water_app/pipes.json", "water_app"),
         ("water_app/dpr_water.json", "water_app"), ("water_app/sor_2025_26.json", "water_app"),
         ("water_app/dpr_template.xlsx", "water_app"),
         ("launcher/static", "launcher/static"),               # the start page (language, sewer / water)
         ("installer/SewerWater.ico", ".")]                    # the icon of the windows and of the tray (app.py)

a = Analysis(
    ["app.py"],
    pathex=["."],
    datas=datas,
    # the modules a server imports inside its functions (from . import netedit ...): all of both packages
    hiddenimports=collect_submodules("sewer_app") + collect_submodules("water_app") + collect_submodules("launcher"),
    excludes=["tkinter", "pytest", "IPython"],
)
pyz = PYZ(a.pure)
# the app icon (user request 14-Nov-2026): the exe, its windows and the shortcuts the setup makes
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SewerWater", console=False,
          icon="installer/SewerWater.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="SewerWater")
