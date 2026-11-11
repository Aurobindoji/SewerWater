# Sewer & Water Network Design

**हिन्दी:** पूरी उपयोग पुस्तिका और हर मानक का स्रोत - [README.hi.md](README.hi.md)

A Windows desktop app for planning and designing urban **sewerage** and **water supply** networks to the
CPHEEO manuals (Government of India). You start from a map or a CAD drawing. The app gives you a checked
network design, CAD drawings and a DPR cost estimate in Excel. You do not need SewerGEMS or WaterGEMS.

> **Beta (v0.9.4).** The app is a design aid. A qualified engineer must check every result before it is used
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
  sizes the rising mains and the tube wells. Pressure-reducing valves are an option.
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
- Hindi or English interface. Exported files are always in English.
- Works offline. Only the map tiles need the internet.
- All projects and results are kept in one folder that you choose.

## How it works

1. **Start** the app. Choose the language and the module: Sewer or Water.
2. **Make a project.** Draw on the map (roads, boundary, wards, OHTs, levels), or open a KML / KMZ or DXF.
   **Save** keeps it as a Google Earth KML.
3. **Layout.** The app builds the network: manholes and sewers, or junctions and pipes. It lists any
   problems found, and you can fix them on the map.
4. **Zoning.** The app proposes zones (sewer) or OZ / DMA boundaries (water), shown in colour on the map.
5. **Design.** The app sizes every pipe and tank and checks it against the CPHEEO limits. The results show
   on the map with a tooltip for each pipe.
6. **Outputs.** Excel reports, the DPR, DXF drawings and maps are written to
   `<your folder>\Sewer\output\<project>` or `<your folder>\Water\output\<project>`.

## Install

**Requirements:**
- Windows 10 or 11, 64-bit.
- Microsoft Edge WebView2. It is already on Windows 11. The setup installs it where it is missing, which needs
  the internet once.
- An internet connection for the map background (optional).

**Steps:**
1. Download `SewerWater_Setup_0.9.4.exe` from the [Releases](../../releases) page.
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
- `.venv\Scripts
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
