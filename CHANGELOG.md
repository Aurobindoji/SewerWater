# Changelog

## Unreleased

- Floating population is now a field in the population step of both apps ("Floating population (%)"),
  10 % by default as before. CPHEEO's water manual (Annexure 2.8) suggests 1-3 % when no figures are available.
  The DPR's floating share cell takes the value given; earlier runs keep their 10 %.

## 0.9.3 (beta) - 2026-11-10

- Both apps' side panels are now in numbered steps, from top to bottom: Project, the map (or the DXF network),
  Layout, population, zoning, design, and Intze for water supply. A bar with its name opens each step, and each
  step has its inputs, then its button, then its result.
- The Layout / Zones / Design switch and the legend now float over the map.
- A detailed guide in Hindi (README.hi.md): install, every step of both apps, the outputs and DPRs, and the source
  of every design value.

## 0.9.2 (beta) - 2026-11-10

- Updates from inside the app: menu **App → Check for updates**. If a newer release is out on GitHub, one click
  downloads its setup, checks its SHA-256 against GitHub's, closes the app, installs the update and opens the app
  again. A download that does not match is deleted and nothing is installed. The app checks only when you ask.
- **About** (menu App, and the start page): the version, the licence, the source and the credits.

## 0.9.1 (beta) - 2026-11-10

- Sewer and water supply are now fully independent apps. The start page (language, then sewer or water) starts
  only the module chosen; opening the water supply app no longer starts the sewer app as well.
- Each app has a button beside "CPHEEO" and the language link that opens the other app, in a window of its own.
  Only then do both run. If the other app is open already, its window is brought forward and its work is kept.
- The language link now switches the language on the page itself.

## 0.9.0 (beta) - 2026-11-10

The first public build.

- Sewerage: network from roads (map / KML) or a DXF drawing, drawing check and repair, zoning options with
  pumping stations, gravity design to the CPHEEO Sewerage Manual, design report, plan and L-section DXF, and DPR
  estimate (Excel).
- Water supply: OZ / DMA zoning, ward-wise population with six projection methods, network design with its own
  Hazen-Williams solver, OHT capacity, tube wells and rising mains, Intze OHT design and drawings (one tank at a
  time), and DPR with the technical statement and estimates (Excel).
- Hindi or English interface; all data in one folder you choose.
