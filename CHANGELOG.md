# Changelog

## Unreleased

- A window's **close button (✕) or Alt+F4 now hides it to the tray**: the app keeps running, its servers and the
  pages' work stay; a double click on the tray icon brings the windows back. The first time a notice says so. The app
  ends from the tray menu ("Quit") or from the new "Quit" in the menu "App". Windows shutting down or logging off
  still closes the app, and the one-click update still closes it before the setup runs.
- Water supply, new tube wells: **only as many as each OZ needs** (the zoning's new + standby). In an OZ whose OHT the
  zoning proposed, the tube wells are suggested with the OHT and the map's are left out (taken only where no site is
  found); in an OZ of an OHT placed on the map, the map's tube wells nearest to the OHT along the roads are taken and
  the rest left out. The design lists the tube wells left out, per OZ. Before, every tube well on the map was designed,
  however many the OZ needed.

## 0.9.9 (beta) - 2026-11-14

- The taskbar showed the icon of an older version after 0.9.8: the app now has its own name on the taskbar, its
  windows take the icon file itself (every size), and the setup makes Windows read the icons again.
- A **tray icon** while the app runs: a double click brings its windows forward; its menu opens the master folder,
  the update check and About, and closes the app.

## 0.9.8 (beta) - 2026-11-14

- Water supply, the two **Export DXF** buttons now make two drawings, and neither is called "zoning + design":
  the one beside "Zoning (OZ / DMA)" exports the zoning alone (`<project>_zoning_<date>_<time>.dxf`), also when a
  design is there; the one beside "Design" exports the design made with the current zoning
  (`<project>_design_...dxf`) and asks for a design first when there is none. The design's progress line reads
  "Water design (with the current zoning)".
- An app icon: the program, its windows, the shortcuts and the setup carry it; the start page shows it, and every
  page has it on its tab.

## 0.9.7 (beta) - 2026-11-14

- Water supply: an **Export DXF** button beside "Zoning (OZ / DMA)" too, for the DXF right after a zoning, before
  any design. It is the same export as the button beside "Design".
- Water supply: a zone's line now goes round empty land instead of running on into it. The zones are drawn across
  open land only up to 120 m (400 m before) - the blocks between streets - and land they close in on every side
  is theirs only up to 3 ha; wider empty land stays outside every zone. A zone's line also runs 20 m beside its
  outer pipes, not on them. The area of a zone (and its persons per hectare) is smaller by the empty land.

## 0.9.6 (beta) - 2026-11-14

- Water supply, the DXF of the zoning and design: an OZ boundary and a DMA boundary no longer look alike. An OZ
  boundary is a thick dash-dot line, a DMA boundary a thin dashed line, and where both run together the OZ's lies
  on top. The dashes are sized for a drawing in metres, and the drawing shows the lineweights on the screen.
- Water supply, the zone boundaries on the map and in the DXF are straight where they can be, with no needless
  zig-zag. Between two zones a boundary now runs half way in a straight line, and every stretch is straightened as
  long as no pipe changes its side by it. An OZ's line is the very line of its DMAs. A zone reached by one pipe
  across open land is drawn with a strip along that pipe, so its outline no longer shrinks to a point and crosses.
  A zone's line also no longer cuts the other zone's main where two mains run along one road: the lines are now
  worked out from points every 10 m along the pipes (40 m before), and a pipe between two zones is cut half way,
  where its valve is drawn.
  Open land that the zones close in on every side now belongs to them, so their lines meet there in one line
  instead of leaving an empty figure. The area of a zone (and its persons per hectare) changes with these.

## 0.9.5 (beta) - 2026-11-14

- Water supply, a network from a DXF: **junctions only where pipes join**. A drawing with a point every 20-30 m
  (as a sewer's manholes) used to give a junction on each. Tick the option when importing, or press
  "Junction केवल joints पर" on a network already imported: a junction where only two pipes meet is removed and its
  two pipes become one, with the same route and length. Ends, joints, and the junctions of an OHT, a tube well or
  a bulk consumer stay. Undo takes it back. The ground levels of the removed junctions are no longer checked.

## 0.9.4 (beta) - 2026-11-11

- Floating population is now a field in the population step of both apps ("Floating population (%)"),
  10 % by default as before. CPHEEO's water manual (Annexure 2.8) suggests 1-3 % when no figures are available.
  The DPR's floating share cell takes the value given; earlier runs keep their 10 %.
- Safer on a computer that is also browsing the web: the sewer and water servers now refuse a request to change
  anything (save, layout, design ...) that comes from a page of another site. The app's own pages work as before.
- Inside: each server's calls are now a table of small functions (one per call) in place of one long chain;
  variables and imports nothing used are gone; `ruff check` (settings in pyproject.toml) guards against new ones.
  No design result changes.
- Inside: the long writers of the DPR workbooks are now one function per sheet group (sewer `write_dpr`; water
  `abstracts`, `om_economics`, `salient`; sewer `om`, `economics`). Every cell of the DPRs was compared before and after: the same.

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
