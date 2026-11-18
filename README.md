# PravaahForge - Sewer & Water Network Design

**हिन्दी:** पूरी उपयोग पुस्तिका और हर मानक का स्रोत - [README.hi.md](README.hi.md)

A Windows desktop app for planning and designing urban **sewerage** and **water supply** networks to the
CPHEEO manuals (Government of India). You start from a map or a CAD drawing. The app gives you a checked
network design, CAD drawings and a DPR cost estimate in Excel. You do not need SewerGEMS or WaterGEMS.

> **Beta (v0.9.34).** The app is a design aid. A qualified engineer must check every result before it is used
> for tender or construction. This applies most of all to the structural design of the Intze tanks.

## Features

### Sewerage
- **Network from roads or a drawing.** You can draw roads on the map, or open a KML / KMZ from Google Earth.
  The app lays out the sewers and manholes along the roads. You can also open an existing DXF network, with
  the pipes and manholes on named layers.
- **Drawing check and repair.** The app finds gaps, loops, missing labels and missing ground levels, and
  suggests labels and levels from the drawing's own text. You can fix the network on the map: move, join, split
  or delete. Undo works for every edit.
- **Zoning options.** The app compares ways of splitting the network into zones with pumping stations. For
  each option it shows the depth, the pipe cost and the total cost. You pick one.
- **Gravity design to the CPHEEO Sewerage Manual:**
  - Manning partial flow with a constant n.
  - Velocity and d/D limits.
  - Peak factors and infiltration.
  - A manhole every 30 m, and drops.
  - Fixed outfall levels.
  - An economise pass that brings the pipe sizes down.
- **Outputs:**
  - Design report (Excel).
  - Plan and longitudinal-section drawings (DXF).
  - Zone maps.
  - A DPR estimate (Excel). Its formulas stay live, on the schedule of rates.

### Water supply
- **Network on the map or from a DXF**, with ground levels, existing and proposed overhead tanks (OHTs),
  tube wells and bulk consumers.
- **Zoning into operational zones (OZ) and DMAs** by population, number of connections and ground slope.
  OHT capacity follows CPHEEO Table 2.7: the mass balance or 33 % of the daily demand, whichever is larger,
  plus one third of the fire demand.
- **Population:**
  - Ward-wise population, and a town-wide list of wards that you export to Excel and import back.
  - Six projection methods: arithmetical, incremental, geometrical, decreasing rate, simple graph and
    semi-log.
  - Growth factors by ward character, balanced so that the wards add up to the town's projection.
  - A check against the saturation density.
- **Hydraulic design.** The app has its own network solver. Head loss is by Hazen-Williams (CPHEEO). The
  design checks the minimum and maximum residual head, the velocity limits, and sizes for each stage. It also
  sizes the rising mains and the tube wells. Pressure-reducing valves are an option. Compared with WaterGEMS
  2024 (steady state and extended period): heads within about 1 cm.
- **Load options:** the population on the junctions by pipe length, by nearest area (Thiessen) or equal; the
  peak factor 2.5 urban / 3.0 rural or your own.
- **Load cases and a 24 h simulation:** the designed network at the average, at night and with a fire flow; hour
  by hour each OHT's water level and the network's pressures, with charts and checks.
- **Design constraints**, each optional: design for the busiest hour and the fire flow too, a maximum pressure,
  pipe sizes, a head-loss limit, the largest staging, a margin on the OHT capacity.
- **Intze OHT design** for each new tank, one tank at a time:
  - Working-stress design to IS 3370, IS 456, IS 1893 (Part 2) and IS 875 (Part 3).
  - An annular raft foundation and an RCC staircase.
  - A1 drawing sheets (DXF and PDF), a design calculation report (PDF), and a bar bending schedule and
    quantities (Excel).
- **DPR (Excel):**
  - The technical statement: population, wards, zones, DMAs, OHT mass balance and static heads.
  - Pipe tables and pumping plant.
  - Civil and E&M estimates on the UP Jal Nigam schedule of rates.

### Common
- The work in **tabs**, step by step; a **Simple / Advanced** switch (Simple shows the essential fields and runs
  the rest at the CPHEEO / UPJN defaults); a **light / dark / system theme**.
- A **full guide in the app** (❓ Help): every field of every step - what to give, why, where it comes from, its
  default and its CPHEEO / UPJN reference. A **tour** on the first start (▶ Tour to see it again).
- An **Outputs** tab: every output in one list - make it, open it in its program, show it in its folder.
- Hindi or English interface. Exported files are always in English.
- Works offline. Only the map tiles need the internet.
- All projects and results are kept in one folder that you choose.

## How it works

The page follows the tabs at its top. **❓ Help** opens the full guide of the tab you are on.

1. **Start** the app. Choose the language and the module: Sewer or Water. A short tour shows the page.
2. **Project.** Draw on the map (roads, boundary, wards, OHTs, levels), or open a KML / KMZ or DXF.
   **Save** keeps it as a Google Earth KML.
3. **Network.** The app builds the network: manholes and sewers, or junctions and pipes. It lists any
   problems found, and you can fix them on the map.
4. **Population.** Ward-wise or a total; stages and the projection (Advanced).
5. **Zoning.** The app proposes zones (sewer) or OZ / DMA boundaries (water), shown in colour on the map.
6. **Network Design.** The app sizes every pipe and checks it against the CPHEEO limits. The results show
   on the map with a tooltip for each pipe. Water: load cases, the 24 h simulation and the constraints.
7. **Tank Design** (water): the Intze design and drawings of each new tank.
8. **Outputs.** Excel reports, the DPR, DXF drawings and maps, in
   `<your folder>\Sewer\output\<project>` or `<your folder>\Water\output\<project>` - opened from the tab.

## Install

**Requirements:**
- Windows 10 or 11, 64-bit.
- Microsoft Edge WebView2. It is already on Windows 11. The setup installs it where it is missing, which needs
  the internet once.
- An internet connection for the map background (optional).

**Steps:**
1. Download `SewerWater_Setup_0.9.34.exe` from the [Releases](../../releases) page.
2. Run it. The setup installs for your user account only, so it needs no administrator rights.
3. The setup is not code-signed. If Windows SmartScreen warns you, click **More info**, then **Run anyway**.
4. On the first start, choose a folder for your data. The app makes `Sewer`, `Water` and `App` sub-folders in
   it. You can change the folder later from the **App** menu.

Uninstalling the app does not delete your data folder.

**Updates:** from version 0.9.2, use the menu **App → Check for updates**. If a newer release is out, one click
downloads its setup, checks its SHA-256 against the one GitHub gives, closes the app, installs the update and opens
the app again. Your data folder is kept. **App → About** shows the version and the licence.

## Run from source

You need Python 3.10 or newer on Windows.

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

- `.venv\Scripts\python app.py` opens the desktop window.
- `sewer_ui.bat` runs the same app in the browser instead.
- `build_setup.bat` builds the setup. It needs PyInstaller and Inno Setup 6.
- `.venv\Scripts\python -m pytest` runs the tests.
- `.venv\Scripts\ruff check` looks for mistakes such as unused or undefined names.

## Standards used

- CPHEEO Manual on Sewerage and Sewage Treatment Systems (2013).
- CPHEEO Manual on Water Supply and Treatment (2024).
- IS 3370, IS 456, IS 1893 and IS 875 for the Intze tanks.
- UP Jal Nigam schedule of rates 2025-26 for the estimates.

Where a manual leaves a choice, the value the app uses and its source are shown in the reports.

## Credits

- **Aurobindoji**: the engineering requirements, design decisions, reference data and testing.
- **Claude** (Anthropic): written together with Aurobindoji, as an AI coding assistant.

## License

Copyright (C) 2026 Aurobindoji.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
Public License, version 3 or (at your option) any later version. See [LICENSE](LICENSE). It comes with
ABSOLUTELY NO WARRANTY.
