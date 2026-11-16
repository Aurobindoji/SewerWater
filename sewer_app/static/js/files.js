// The Outputs tab's outputs of the sewer page (user request 16-Nov-2026; the list itself: outlist.js).
const OUT_KINDS = [
  { hi: "Layout drawing (DXF)", en: "Layout drawing (DXF)", re: /_layout\.dxf$/,
    note: ["Layout बनाने पर बनती है", "made with the layout"] },
  { hi: "नक्शे की boundary (KML)", en: "Map boundary (KML)", re: /_boundary\.kml$/ },
  { hi: "Zoning options - workbook, costs, zone boundaries, networks", en: "Zoning options - workbook, costs, zone boundaries, networks",
    re: /_zoning_\d{8}_\d{4}(\.xlsx|_costs\.xlsx|_zone_boundaries\.dxf|_\d{2}_.*_network\.dxf)$/, all: true, tab: "zoning",
    note: ["Zoning options निकालने पर बनती हैं", "made with the zoning options"] },
  { hi: "चुना zoning option - DXF + KML + Excel", en: "The chosen zoning option - DXF + KML + Excel",
    re: /_zones_.+_\d{8}_\d{4}/, all: true, make: "zexport", tab: "zoning" },
  { hi: "Network design - report (xlsx)", en: "Network design - report (xlsx)", re: /_sewer_design_\d{8}_\d{4}(_PFR)?\.xlsx$/,
    note: ["हर Design के साथ बनती है", "made with every design"], tab: "design" },
  { hi: "DPR (xlsx)", en: "DPR (xlsx)", re: /_DPR\.xlsx$/, tab: "design" },
  { hi: "Network design - plan (DXF)", en: "Network design - plan (DXF)", re: /_sewer_design_\d{8}_\d{4}(_PFR)?\.dxf$/, tab: "design" },
  { hi: "Network design - L-section (DXF)", en: "Network design - L-section (DXF)", re: /_Lsection\.dxf$/, tab: "design" },
];
