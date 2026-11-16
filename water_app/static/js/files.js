// The Outputs tab (user request 16-Nov-2026): every output of the project in one list - each kind with its make
// button (the step's own, clicked), its newest file (name, time), open it in its program, show it in its folder -
// and below, every other file of the project's output folder. The server lists them (/api/outputs) and opens them
// (/api/open_output, within the project's output folder only).
const OUT_KINDS = [
  { hi: "Layout drawing (DXF)", en: "Layout drawing (DXF)", re: /_layout\.dxf$/,
    note: ["Layout बनाने पर बनती है", "made with the layout"] },
  { hi: "नक्शे की boundary (KML)", en: "Map boundary (KML)", re: /_boundary\.kml$/ },
  { hi: "Project का नक्शा (KML / KMZ)", en: "Project map (KML / KMZ)", re: /_map_\d{8}_\d{4}\.km[lz]$/, make: "mapget", tab: "project" },
  { hi: "वार्ड-वार आबादी (xlsx)", en: "Ward-wise population (xlsx)", re: /_wards\.xlsx$/, tab: "pop" },
  { hi: "Zoning drawing (DXF)", en: "Zoning drawing (DXF)", re: /_zoning_\d{8}_\d{4}\.dxf$/, make: "wexportz", tab: "zoning" },
  { hi: "Network design drawing (DXF)", en: "Network design drawing (DXF)", re: /_design_\d{8}_\d{4}\.dxf$/, make: "wexport", tab: "design" },
  { hi: "Network design - pipes / junctions (xlsx)", en: "Network design - pipes / junctions (xlsx)",
    re: /_water_design_\d{8}_\d{4}\.xlsx$/, note: ["हर Design के साथ बनती है", "made with every design"], tab: "design" },
  { hi: "DPR (xlsx)", en: "DPR (xlsx)", re: /_DPR\.xlsx$/, make: "wexportdpr", tab: "design" },
  { hi: "DPR के rates (xlsx)", en: "DPR rates (xlsx)", re: /_rates_\d{8}_\d{6}\.xlsx$/, make: "wrexp" },
  { hi: "टंकियों की Intze drawings / design (DXF, PDF, xlsx)", en: "Tanks' Intze drawings / design (DXF, PDF, xlsx)",
    re: /^intze\//, tab: "tank", all: true },
  { hi: "Zoning + design drawing (DXF, पुरानी)", en: "Zoning + design drawing (DXF, older)", re: /_water_\d{8}_\d{4}\.dxf$/ },
];
