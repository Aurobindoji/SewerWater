# Changelog

## 0.9.38 (beta) - 2026-11-23

Sewer:
- "DXF network…": a "Show network" button, as on the water page - the whole network of the ticked layers on the
  map, nothing saved: the largest part blue, other parts orange, open ends red, with the counts of manholes,
  sewers, parts, loops, open ends and manholes without GL, and the drawing's problems.

Water supply - Intze OHT:
- Staircase: each landing beam rests on what is there - B1 on a column of the staging below the columns' top, B3
  on the cone or the balcony's edge up to the balcony, B4 above the balcony as a balanced cantilever on the
  staircase column alone (no longer through the tank wall), B5 at the roof from the top ring beam, the landing
  carried on flat to the ring beam. Design, calculation report, bar schedule and quantities by beam.
- Sheet 3: the plans show each beam and the roof landing; new section 14-14 along B5, elevations of B3 and B4 and
  sections of all four beams.
- Sheet 2: a large detail of the joint of wall, balcony and cone with its bars.
- "Show network" now reads in English on the English water page too.

## 0.9.37 (beta) - 2026-11-22

- DPR (water and sewer): the department's name is entered once in sheet Project ("Department / implementing
  agency", blank by default) and taken from there on the cover, certificate, Form J, salient features and the
  signatures. The workbooks' notes give values and methods only.
- The pages' tooltips and notes give the default values only.

## 0.9.36 (beta) - 2026-11-22

Water supply - Intze OHT drawings and design:
- Sheet 2 laid out anew: the tank's section at 1:30 over the sheet's height, the details in a
  column on the right; the domes' plans with their crown; a detail of the top ring beam.
- No text over another text, over a drawn line or off the frame (checked with the real font, for tanks from 100 to
  3400 KL).
- Concrete drawn as one piece (no joint lines); the cone's face runs down to the bottom ring beam's side; the top
  dome meets the wall without a step.
- Bars: at the top ring beam the wall's outer verticals run on into the dome's top layer and the dome's bars are
  hooked in the beam; the stair flight's top bar stays inside the concrete; bar ends at landings and in the landing
  beam no longer meet.
- The top ring beam is nominal (4 - 12 #); the rest of the top dome's pull goes into the wall's top band of hoops.
- Small tanks: the raft is made deep enough for its foundation ring beam (a 150 KL tank's drawing used to hang).

## 0.9.35 (beta) - 2026-11-18

- "DXF network…" (sewer and water): the panel now opens just below the bar with the tabs, so its DXF file box and
  Browse button are in view - before, the page scrolled them under that bar.

## 0.9.34 (beta) - 2026-11-18

Water supply:
- The DXF import's problems and summary in water words: junctions, not manholes ("no junction label in the
  drawing", "junction on a continuous line"); loops are no longer listed as a problem (a water network has them),
  and separate parts ask for a tank / source each, not an outfall. Projects saved before keep their checks.
- The network preview lists the drawing's problems in Hindi on a Hindi page.
- "नक्शा बनाएँ (KML / KMZ)" is now "नक्शा export करें (KML / KMZ)" ("Export the map"); the tooltips and the guide
  tell it apart from "KML download" (only the drawing made by hand, to open again).

## 0.9.33 (beta) - 2026-11-18

DXF import (water supply; the layer ticks in sewer too):
- A layer ticked under Pipe / Junction / GL shows on the map at once, and goes when its last tick is taken off; the
  suggested layers are shown as soon as the drawing is read.
- "Network देखें" shows the whole network the ticked layers would make, before the import and without saving it:
  the largest connected part in blue, separate parts in orange, open ends in red (the other junctions when zoomed
  in), with the counts of junctions, pipes, km, parts, open ends, junctions without GL and the drawing's problems.
  The drawing is not read again, so it takes a few seconds.

Simulation: the EPS player runs on from hour 0 after the last hour, until it is paused.

## 0.9.32 (beta) - 2026-11-17

- Simulation tab: tanks whose levels run alike are drawn as one line named after all of them; every chart shows
  the hour's values on hover; a card shows the share of pipes slower than 0.3 m/s and how many of them are of the
  smallest size (the street ends, at CPHEEO's 100 mm minimum).
- The tray message says only that the app is running in the background.

## 0.9.31 (beta) - 2026-11-17

Water supply - a Simulation tab, beside Network Design:
- The network of the last design (pipe sizes, tank stagings, PRVs) is solved again under any load, without
  designing again. Run the design once after updating so that the tab has its data.
- **SSA** (one moment): average, peak, night, any hour of the day or an own factor; the population stage (design,
  +15 years, base year); extra loads and fires at junctions, with a head to hold at the fire.
- **EPS** (24, 48 or 72 hours): the 24 h draw-off pattern can be edited on the page, and the tanks' filling hours
  given; a time slider and a player step through the hours.
- The map shows each junction's head and each pipe's velocity, flow or head loss in colour, with a legend. Click a
  junction or pipe for its values and, in an EPS, its curve through the run; add a load or a fire there. Charts of
  the tanks' levels, the network's heads and the demand; the weak spots listed.
- The design's own load cases, 24 h run and fire flow are now in this tab.

## 0.9.30 (beta) - 2026-11-17

Water supply - DXF drawings converted from a PDF now import:
- A drawing with everything on one layer in many colours gets a layer per colour ("0 colour 82"). The pipe colours
  are suggested by their pipe labels (P-, D-, L-..m); in a mixed colour (black: buildings, roads and some pipes) the
  labelled lines get a layer of their own ("0 colour 7 labelled").
- A drawing at paper size is scaled to metres when its length labels (L-5m, 12.3 m) agree on one ratio.
- Small symbol strokes are not taken for pipes; a pipe drawn twice a little apart is kept once; pipes that stop a few
  metres short of their junctions are joined there. The import summary says each of these.

Water supply - a layout from a survey drawing's roads:
- New button **सड़कों से layout** in the DXF panel: tick the road centreline layer under Pipe (and the level layer
  under GL, or leave it empty for the drawing's levels and survey points). The roads and ground levels come onto the
  map as a new project; add the boundary and tanks, save, and make the layout as for a KML.

## 0.9.29 (beta) - 2026-11-17

Water supply - junction and pipe names:
- The junction prefix chosen at the DXF import is now put on the drawing's own names too: the letters before the
  number change, the number stays (MH-1-595 becomes JN-1-595). A name another junction already has keeps its own.
- The page's "change prefix" takes the letters before the first number as the prefix (MH- of MH-3-441, not MH-3-).
- New button on the Network tab, **all new names - from the tanks 1, 2, 3 …**: every junction and pipe gets the
  prefix above it and a number, counted out from each tank of the last zoning along its zone's pipes (the
  straightest way first). The drawing's name stays on each card as the old name, and is saved in
  `<name>_network_old_names.csv`. One undo step. Run Zoning and Design again afterwards.

Faster, same results:
- A large water design (about 12,500 junctions) takes about 33 s instead of 38 s; the results and the Excel report
  are unchanged.
- Code cleanup inside the app (unused code removed, the network corrections reorganised); nothing changes in use.

## 0.9.28 (beta) - 2026-11-16

- The welcome video is sharper: 1920 px wide, made again from the original at a much higher quality (it was a
  strongly compressed 1280 px copy); the start page's backdrop (its last frame) too.

## 0.9.27 (beta) - 2026-11-16

Water supply - a network from a badly made DXF (rules measured on real drawings):
- Ground levels written **E-77.31 m** or **EL-77.87 m** are read, and two-part names such as **MH-3-441**.
- A node layer that writes its levels with a tag (GL / EL / E) gives only those: the depths and lengths beside them
  are no ground level.
- No false ground levels: a layer whose numbers spread more than 50 m (pipe lengths), bare numbers written to one
  decimal (26.8 m), a level 25 m away from all the others (a typing error such as 777.08 - listed under Problems),
  and one Z at every line end (the elevation the lines were drawn at) are not used.
- **Survey points** (POINT with a height) give the ground level where there is no GL text.
- A line drawn twice on the pipe layers is kept once.
- The guess of the pipe layers leaves out power lines (HT / LT, utility, cable), road centre lines and sewer layers.

## 0.9.26 (beta) - 2026-11-16

- Both module pages: Help, Tour, CPHEEO, the language and the other app now sit close together on the title's line,
  at its right, with the ☀ / 🌙 theme icon at the far right (a narrow sidebar puts them under the title, still on the
  right). Simple / Advanced has its own line.

## 0.9.25 (beta) - 2026-11-16

- Both module pages: **Help, Tour, CPHEEO, the language and the other app in one line** at the top of the sidebar,
  and the theme is now one icon - ☀ light / 🌙 dark, a click switches it (the "as Windows" choice is gone from the
  page). Simple / Advanced on the line below.

## 0.9.24 (beta) - 2026-11-16

- The windows' **title bar** is dark when the pages are dark (the dark theme, or System with Windows in dark mode),
  light otherwise - it changes at once when the theme is changed on a page.
- **Check for updates** in one language (the one chosen last, as About) and in the pages' theme; its messages too.

## 0.9.23 (beta) - 2026-11-16

- The app opens fast again: about 1 s to its window (0.9.22 took about 3.4 s). The check for a copy already running
  is now instant (a Windows named mutex) - asking the app's port when nothing listened cost Windows 2 s at every start.

## 0.9.22 (beta) - 2026-11-16

- The start page in the welcome video's look: when the video ends its last picture stays, slowly dims and the
  choices rise in front of it - the PravaahForge title in its blue and orange, glowing buttons (water supply now on
  the left).
- The dark tray menu and menu **App**: their text now white and clear.
- **One app at a time:** starting the app again while it runs (for example hidden in the tray) brings the running
  one forward instead of a second app with a second tray icon.

## 0.9.21 (beta) - 2026-11-16

- A short **welcome video** (the PravaahForge logo, 5 s, silent) when the app opens, then the start page. A click or
  any key skips it; it does not play again when you come back from a module.

## 0.9.20 (beta) - 2026-11-16

- The start page has **PravaahForge** as its title; the choice of language is a small line under it. Under Sewer and
  Water supply the same kind of line, in the language chosen.
- The tray menu, the menu **App** of the windows, the tray's note and **About** are in the language chosen last
  (Hindi or English, no longer both), and **dark** when the pages are dark (the dark theme, or System with Windows
  in dark mode).

## 0.9.19 (beta) - 2026-11-16

- The app is now called **PravaahForge** (Sewer & Water network design): the window, the start page, About, the
  setup, the Start menu / desktop shortcuts. The old name's shortcuts are removed by the setup. Nothing else
  changes: the same program file, install folder, settings and master folder, and updates as before.

## 0.9.18 (beta) - 2026-11-16

- Water supply: **Make a map (KML / KMZ)** on the Project tab - the project's whole map for Google Earth, the parts
  ticked: pipes (a colour and folder per size after a design, closed pipes red), junctions, tanks, new tube wells and
  their rising mains, bulk consumers, PRVs, OZ / DMA boundaries, boundary valves, wards, barrier lines; each part a
  folder, details on a click. For DXF projects too. The file also stays in the Outputs tab.
- An active drawing / network tool now shows itself: a cross cursor, and a note at the mouse saying which tool is on,
  what to do next and how to turn it off (both modules).
- Opening a DXF under the name of a project already there asks first (it would replace that project's network and
  its corrections); Cancel suggests a free name.
- Fixes: "DXF network…" on the Project tab opens its panel (on the Network tab); disabled buttons look disabled and
  say why; in the dark theme the inputs filled by the projection and the projection chart's labels are readable;
  Bulk consumer / new tube well / PRV buttons once each.
- Sewer plan DXF: pipe labels kept off the manhole texts, the other labels and the pipes (as the water drawing) - a
  bent pipe's along its longest straight part, else the other side, slid along, or on a leader.

## 0.9.17 (beta) - 2026-11-16

- **A full guide in the app** (❓ Help on the tab bar, both modules): per step the data needed, the order of work and
  every field - what to give, why, where it comes from, its default and its CPHEEO / UPJN reference; reading the
  results, common mistakes; Hindi / English, search, print / PDF. It opens at the chapter of the tab you are on.
- **A tour** on the first start: the page dimmed, one part lit at a time with a few lines (Back / Next / Skip);
  **▶ Tour** shows it again.
- Tabs **Network Design** and, in the water app, **Tank Design** (the Intze tanks); an **Outputs** tab in both: every
  output in one list - make it, open it in its program, show it in its folder - with the project's output folder.
- README / README.hi brought up to date with the new page.

## 0.9.16 (beta) - 2026-11-16

- Both map pages: the sidebar in **tabs** by the work's steps (Project, Network, Population, Zoning, Design, Outputs); a
  **Simple / Advanced** switch (Simple: the essential fields, the rest at the CPHEEO / UPJN defaults when run); a
  **light / dark / system theme** (dark dims the map too), on the start page as well, the same on every page.
- Water supply: **how the population is put on the junctions** - by the pipe length (as before), by the nearest area
  (Thiessen) or equal; **peak factor** 2.5 urban / 3.0 rural (CPHEEO Table 2.7 S.No.7) or a given value.
- Water supply: **load cases** - the designed network at the average, at night (the lowest hour of the draw-off
  pattern) and with a fire flow at each OZ's weakest junction (flow and head given on the page).
- Water supply: a **24 h simulation** - hour by hour each OHT's water level (filled in its filling hours, drawn by its
  outlet) and the network's pressures, with a table and charts; a check when a tank runs dry or over, a red warning
  when it nearly empties. Compared with WaterGEMS 2024 (steady state and EPS): pressures within about 1 cm.
- Water supply: **design constraints** on the page, each only when ticked: design for the busiest hour and the fire
  flow too, a maximum pressure (at night), the pipe sizes (smallest, largest, HDPE up to), a head loss limit, the
  largest staging of a new OHT, a margin on the OHT capacity.
- Water supply DXF: a bent pipe's label along its longest straight part; pipe labels cross no pipe.

## 0.9.15 (beta) - 2026-11-16

- Water supply DXF: a pipe's label gives its material and diameter, e.g. `P-9943 DI 350mm L=31.0`; the pipes of
  each size are on a layer and in a colour of their own (`W_PIPE_HDPE_110`, `W_PIPE_DI_350` ...), with a legend of
  the sizes and their lengths under the network.
- Water supply DXF: a junction's residual head is written `RH 21.95` (was `P 21.95`).
- Water supply DXF: pipe labels no longer lie over a junction's name / GL / HGL / RH. A label goes to the first
  clear place: the middle of the pipe as before, the other side, slid along the pipe, or on a leader.
- Both map pages: no "Don't wait" button on the loading cover; it stays until the work is done.

## 0.9.14 (beta) - 2026-11-15

- Inside only: the code of both modules arranged anew, in stages, nothing the app makes changed. Each module is in
  layers - calculations, the network, a project's files, the outputs (DPR, report, drawings), the work behind a page
  call, the server - and a module imports only from the layers below it (a test keeps it so). Water: the page's calls
  in zoning / design / wards / results modules, the DPR one package; sewer: the server apart from the zoning and
  design runs and from the command line, the zoning apart from its workbooks and drawings. Both map pages are now an
  HTML file, a stylesheet and a set of scripts.
- Checked by comparing 73 outputs of mock projects (every API answer, every DPR / report cell, every DXF entity) with
  those of 0.9.13: all the same.

## 0.9.13 (beta) - 2026-11-15

- Water supply: the **DPR workbook is made only by the Export DPR (xlsx) button**, no longer with every design. The
  design keeps what the DPR needs; the first click writes the workbook and opens it, the next clicks open the same
  file (until the next design, or until the rates change).
- Water supply: **Export rate xlsx / Import rate xlsx…** under Design, for when the rates change. The xlsx has the
  schedule of rates (sheet SOR: item no., description, unit, rate) and the U.P. Jal Nigam rates by size (pipe supply
  HDPE / DI K-7, DI K-9, HDPE carting, NRV, PRV); the rates the DPR of the project's last design uses are
  **yellow**. Change the Rate column and import it: the changed rates are kept in the master folder for every
  project (an update of the app keeps them) and go into the DPR and the rising mains' cost from then on; items the
  app does not have are left out and told. **"मूल rates वापस"** goes back to the app's own rates.

## 0.9.12 (beta) - 2026-11-15

- Water supply: **✕ on the app's own suggestions** too, beside "move" in the hover card. A suggested OHT taken away
  just goes: the next zoning has no OHT there and its area joins the neighbouring OZs (or stays joined to no OHT). A
  suggested tube well taken away: none comes in its place - the other tube wells of its OZ become yours on the map,
  only the map's are designed there, and when they are too few the design fails (✖) with the OZ's +15 years demand
  and how many tube wells it needs; the sites for the rest show as red T! (not in the design).
- Under Zoning: **"Remove all suggested OHTs"** and **"Remove all suggested tube wells"**, with "bring back" to undo.
  The choices are kept with the project (by the sites, as the zoning renames its OZs when it runs again).
- Water supply: an **Export DPR (xlsx)** button beside Design / Export DXF - it opens the last design's DPR
  workbook in Excel and tells its folder (and warns when the network changed after that design).
- The folding rows (such as "Intze OHT drawings: tanks and their inputs") open on a click anywhere on the row, not
  only on the small triangle; the Intze row is now a bar with ▶ / ▼.

## 0.9.11 (beta) - 2026-11-15

- Water supply, the zone lines: **no ring round empty land inside the zones** any more. Land the zones close in on
  every side is now theirs whatever its size (3 ha before - larger land got a line of its own round it, in the map
  and in the DXF); the lines run only where two zones meet and along the outer edge, as in a DPR's key plan. Open
  land reaching the outside still stays outside the zones. The zones' areas grow by that land (persons per hectare
  change; the design does not). An existing project shows it after its Zoning runs again.

## 0.9.10 (beta) - 2026-11-15

- A window's **close button (✕) or Alt+F4 now hides it to the tray**: the app keeps running, its servers and the
  pages' work stay; a double click on the tray icon brings the windows back. The first time a notice says so. The app
  ends from the tray menu ("Quit") or from the new "Quit" in the menu "App". Windows shutting down or logging off
  still closes the app, and the one-click update still closes it before the setup runs.
- Water supply, new tube wells: **only as many as each OZ needs** (the zoning's new + standby). In an OZ whose OHT the
  zoning proposed, the tube wells are suggested with the OHT and the map's are left out (taken only where no site is
  found); in an OZ of an OHT placed on the map, the map's tube wells nearest to the OHT along the roads are taken and
  the rest left out. The design lists the tube wells left out, per OZ. Before, every tube well on the map was designed,
  however many the OZ needed.
- Water supply, a **hover card on every tube well and tank**: its zone, discharge or capacity, CWR, staging, outlet,
  whether it is yours (on the map) or the app's (auto), and main or standby; the map's own have ✕ (remove) and
  ✥ move. Moving a suggested tube well or a proposed OHT makes it yours: a proposed OHT comes on the map with its
  OZ's suggested tube wells (a suggested tube well of such an OZ the same way), so the next design keeps them.
- Water supply: the **standby tube wells** of an OZ are now the ones farthest from its OHT along the roads (marked on
  the map and in the card). A new option under Zoning, "Standby tube wells अपने हिसाब से" (off and grey by default:
  CPHEEO 5.7.5), gives the new tube wells a table of your own - up to how many working, how many standby - with the
  CPHEEO rule in a popup. Booster and CWR pumps keep the CPHEEO table.

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
