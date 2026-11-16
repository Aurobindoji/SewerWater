"""The project's map as KML / KMZ (user request 16-Nov-2026: "नक्शा बनाएँ", then download the map made - for Google
Earth and the like; a DXF project had no KML of its own).

    path, counts = kmlmap.export(stem, req, parts, fmt)   # output\\<stem>\\<stem>_map_<date>_<time>.kml | .kmz

One folder per part, each switched on / off in Google Earth; the parts asked for (PARTS) that the project has:
    network     the pipes - after a design one folder per size, each in its own colour (label, size, length, flow,
                velocity in the description); the closed (boundary) pipes red
    junctions   the junctions (name, GL; after a design HGL and residual head) - many: off by default on the page
    tanks       the OHTs: of the last zoning (its proposed ones too, capacity, staging from the design), else the map's
    tubewells   the new tube wells and their rising mains (the design's), else the map's
    bulk, prv   the bulk consumers and PRVs placed on the map
    zones, dma  the OZ (each its colour) and DMA boundaries of the last zoning, with population / connections
    valves      the boundary valves (closed pipes) of the last zoning
    wards       the wards drawn on the map (name, population)
    barriers    the barrier lines (highway / railway ...)
req: the page's request (wInputs) - the map's own items. The zoning / design: the last ones kept for the page, and only
when they are of the network as it is now (a stale one is left out, counts["stale"] says which).
"""
import io
import math
import os
import time
import zipfile
from xml.sax.saxutils import escape

from . import project as ui

PARTS = ("network", "junctions", "tanks", "tubewells", "bulk", "prv", "zones", "dma", "valves", "wards", "barriers")
DEFAULT = ("network", "tanks", "tubewells", "bulk", "prv", "zones", "dma", "valves", "wards", "barriers")
# pipe sizes in the order of pipes.json, a colour each (RRGGBB; as wdxf's SIZE_COLOURS: not red - the closed pipes)
SIZE_RGB = ["1e88e5", "fb8c00", "8e24aa", "fdd835", "00acc1", "6d4c41", "3949ab", "d81b60", "43a047", "00897b",
            "5e35b1", "c0ca33", "f4511e", "546e7a"]
OZ_RGB = ["e53935", "43a047", "1e88e5", "8e24aa", "fb8c00", "00acc1", "fdd835", "6d4c41", "d81b60", "3949ab",
          "7cb342", "00897b", "5e35b1", "f4511e", "546e7a"]
PIPE_RGB, CLOSED_RGB = "1565c0", "d50000"


def _kml_colour(rgb, alpha="ff"):
    """KML's aabbggrr from RRGGBB."""
    return alpha + rgb[4:6] + rgb[2:4] + rgb[0:2]


def _coords(latlngs):
    return " ".join(f"{float(p[1]):.7f},{float(p[0]):.7f},0" for p in latlngs)


def _desc(rows):
    """A placemark's description: a small table of (name, value), the empty ones left out."""
    rows = [(k, v) for k, v in rows if v not in (None, "")]
    if not rows:
        return ""
    body = "".join(f"<tr><td>{escape(str(k))}</td><td><b>{escape(str(v))}</b></td></tr>" for k, v in rows)
    return f"<description><![CDATA[<table>{body}</table>]]></description>"


def _num(v, nd=2):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f"{f:.{nd}f}"


class _Doc:
    def __init__(self, name):
        self.name, self.styles, self.folders = name, {}, []

    def style(self, sid, line=None, width=2.0, poly=None, icon=None, scale=1.0, label=False):
        if sid not in self.styles:
            s = f'<Style id="{sid}">'
            if icon:
                s += (f'<IconStyle><color>{_kml_colour(icon)}</color><scale>{scale}</scale><Icon><href>'
                      'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon></IconStyle>')
            s += f"<LabelStyle><scale>{0.8 if label else 0}</scale></LabelStyle>"
            if line:
                s += f"<LineStyle><color>{_kml_colour(line)}</color><width>{width}</width></LineStyle>"
            s += (f"<PolyStyle><color>{_kml_colour(poly, '40')}</color></PolyStyle>" if poly
                  else "<PolyStyle><fill>0</fill></PolyStyle>")
            self.styles[sid] = s + "</Style>"
        return sid

    def folder(self, name, items, visible=True):
        if items:
            self.folders.append(f"<Folder><name>{escape(name)}</name><visibility>{int(visible)}</visibility>"
                                f"<open>0</open>{''.join(items)}</Folder>")
        return len(items)

    def text(self):
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                f"<name>{escape(self.name)}</name>{''.join(self.styles.values())}{''.join(self.folders)}"
                "</Document></kml>\n")


def _pm(name, style, geom, rows=()):
    return (f"<Placemark><name>{escape(str(name))}</name>{_desc(rows)}<styleUrl>#{style}</styleUrl>{geom}"
            "</Placemark>")


def _point(lat, lng):
    return f"<Point><coordinates>{float(lng):.7f},{float(lat):.7f},0</coordinates></Point>"


def _line(latlngs):
    return f"<LineString><tessellate>1</tessellate><coordinates>{_coords(latlngs)}</coordinates></LineString>"


def _poly(rings):
    """A polygon (the first ring outer, the rest holes) - rings of [lat, lng]."""
    def ring(r):
        r = list(r)
        if r and list(r[0]) != list(r[-1]):
            r = r + [r[0]]
        return f"<LinearRing><coordinates>{_coords(r)}</coordinates></LinearRing>"
    inner = "".join(f"<innerBoundaryIs>{ring(r)}</innerBoundaryIs>" for r in rings[1:])
    return f"<Polygon><tessellate>1</tessellate><outerBoundaryIs>{ring(rings[0])}</outerBoundaryIs>{inner}</Polygon>"


def _results(stem):
    """(zoning or None, design or None, [stale parts]) of the network as it is now."""
    from . import results, zoning_run  # noqa: F401
    try:
        last = results.last_results(stem)
    except Exception:
        return None, None, []
    stale = []
    z = last.get("zoning")
    if z and z.get("stale"):
        z, stale = None, stale + ["zoning"]
    d = last.get("design")
    if d and (d.get("stale") or not z or d.get("net_rev") != z.get("net_rev")):
        d, stale = None, stale + ["design"]
    return z, d, stale


def build(stem, req=None, parts=DEFAULT):
    """(kml text, counts)."""
    from . import design as wd
    from . import zoning_run
    req, parts = req or {}, set(parts or DEFAULT) & set(PARTS)
    z, d, stale = _results(stem)
    n = {"stale": stale}
    doc = _Doc(f"{stem} - water supply network")
    net = None
    if ui.has_network(stem) and parts & {"network", "junctions"}:
        net = zoning_run.cut_net(stem, z.get("req")) if z else ui.project_net(stem)
    to_ll = ui.converters_for(stem)[0] if net else None

    # ---- the pipes: one folder per size after a design
    if net and "network" in parts:
        dp = {p["label"]: p for p in (d or {}).get("pipes", [])}
        order = [x["name"] for x in wd.load_pipes()]
        groups = {}
        for c in net["conduits"]:
            P = [tuple(p) for p in (c.get("vertices") or [])]
            if len(P) < 2:
                a, b = net["nodes"].get(c["start_node"], {}).get("xy"), net["nodes"].get(c["stop_node"], {}).get("xy")
                P = [tuple(a), tuple(b)] if a and b else []
            if len(P) < 2:
                continue
            p = dp.get(c["label"], {})
            key = "closed" if p.get("closed") else (p.get("size") or "")
            rows = [("pipe", c["label"]), ("size (mm)", p.get("size")), ("length (m)", _num(c.get("length_m"), 1)),
                    ("flow (L/s)", _num(p.get("flow"), 2) if p else None), ("velocity (m/s)", _num(p.get("v"), 2) if p else None),
                    ("OZ", p.get("oz")), ("DMA", p.get("dma")), ("closed (boundary valve)", "yes" if p.get("closed") else None)]
            groups.setdefault(key, []).append((c["label"], P, rows))
        keys = sorted(groups, key=lambda k: (k == "closed", k == "", order.index(k) if k in order else len(order), k))
        n["pipes"] = 0
        for k in keys:
            if k == "closed":
                sid, title = doc.style("pipe_closed", line=CLOSED_RGB, width=3), "Pipes - closed (OZ / DMA boundary)"
            elif k:
                i = order.index(k) if k in order else len(order) + keys.index(k)
                sid = doc.style("pipe_" + "".join(ch if ch.isalnum() else "_" for ch in k),
                                line=SIZE_RGB[i % len(SIZE_RGB)], width=3)
                title = f"Pipes - {k} mm"
            else:
                sid, title = doc.style("pipe", line=PIPE_RGB, width=2), "Pipes" if not d else "Pipes - no size"
            items = [_pm(lab, sid, _line(to_ll(P)), rows) for lab, P, rows in groups[k]]
            length = sum(float(r[2][1]) for _, _, r in groups[k] if r[2][1])
            n["pipes"] += doc.folder(f"{title} ({len(items)}, {length:,.0f} m)", items)
    # ---- the junctions
    if net and "junctions" in parts:
        dn = {x["label"]: x for x in (d or {}).get("nodes", [])}
        lab_xy = [(lab, v["xy"]) for lab, v in net["nodes"].items() if v.get("xy")]
        lls = to_ll([xy for _, xy in lab_xy])
        ok, low = doc.style("jn", icon="2e7d32", scale=0.4), doc.style("jn_low", icon="d50000", scale=0.5)
        items = []
        for (lab, _), ll in zip(lab_xy, lls):
            e, v = dn.get(lab, {}), net["nodes"][lab]
            is_low = e.get("p") is not None and e["p"] < 17.0 - 1e-6
            items.append(_pm(lab, low if is_low else ok, _point(*ll),
                             [("junction", lab), ("GL (m)", _num(e.get("gl", v.get("ground")))), ("HGL (m)", _num(e.get("head"))),
                              ("residual head (m)", _num(e.get("p"))), ("OZ", e.get("oz")), ("DMA", e.get("dma"))]))
        n["junctions"] = doc.folder(f"Junctions ({len(items)})", items)

    # ---- the tanks: the zoning's (proposed too), else the map's
    if "tanks" in parts:
        items = []
        if z:
            outl = {o["name"]: o for o in (d or {}).get("outlets", [])}
            ex, new = doc.style("oht_ex", icon="00838f", scale=1.1, label=True), doc.style("oht_new", icon="f57c00", scale=1.1, label=True)
            for x in z["zones"]:
                ll = x.get("latlng") or x.get("oht_latlng")
                if not ll and net is not None and x.get("node") in net["nodes"]:
                    ll = to_ll([net["nodes"][x["node"]]["xy"]])[0]
                if not ll:
                    continue
                o = outl.get(x["name"], {})
                items.append(_pm(x["name"], new if x.get("proposed") or not x.get("capacity_kl") else ex, _point(*ll),
                                 [("OHT", x["name"]), ("capacity (KL)", f"{x['capacity_kl']:g}" if x.get("capacity_kl") else None),
                                  ("required (KL, new)", f"{x['required_kl']:g}" if not x.get("capacity_kl") and x.get("required_kl") else None),
                                  ("staging (m)", o.get("staging_m", x.get("staging_m"))),
                                  ("proposed by the zoning", "yes" if x.get("proposed") else None), ("population", f"{x.get('population', 0):,}"),
                                  ("connections", f"{x.get('connections', 0):,}"), ("DMAs", x.get("dma_count"))]))
        else:
            ex, new = doc.style("oht_ex", icon="00838f", scale=1.1, label=True), doc.style("oht_new", icon="f57c00", scale=1.1, label=True)
            for x in req.get("ohts") or []:
                if x.get("lat") is None:
                    continue
                items.append(_pm(x.get("name") or "OHT", ex if str(x.get("existing")) == "1" else new, _point(x["lat"], x["lng"]),
                                 [("capacity (KL)", x.get("capacity_kl")), ("staging (m)", x.get("staging_m"))]))
        n["tanks"] = doc.folder(f"Tanks (OHT) ({len(items)})", items)
    # ---- the new tube wells and their rising mains
    if "tubewells" in parts:
        tws = ((d or {}).get("rising") or {}).get("tws") or []
        tw, rm = doc.style("tw", icon="00897b", scale=0.9, label=True), doc.style("rm", line="00897b", width=3)
        items = []
        if tws:
            for x in tws:
                ll = x.get("latlng")
                if ll:
                    items.append(_pm(x["name"], tw, _point(*ll), [("tube well", x["name"]), ("discharge (LPM)", x.get("lpm")),
                                                                    ("rising main", x.get("size")), ("length (m)", _num(x.get("length_m"), 0))]))
                if x.get("path"):
                    items.append(_pm(f"RM {x['name']}", rm, _line(x["path"]), [("rising main", x.get("size")),
                                                                               ("length (m)", _num(x.get("length_m"), 0))]))
        else:
            for x in req.get("tws") or []:
                if x.get("lat") is not None:
                    items.append(_pm(x.get("name") or "TW", tw, _point(x["lat"], x["lng"]), [("discharge (LPM)", x.get("discharge_lpm"))]))
        n["tubewells"] = doc.folder(f"New tube wells ({sum(1 for x in items if 'Point' in x)})", items)
    # ---- the map's bulk consumers and PRVs
    if "bulk" in parts:
        sid = doc.style("bulk", icon="6d4c41", scale=0.9, label=True)
        items = [_pm(x.get("name") or "Bulk", sid, _point(x["lat"], x["lng"]), [("KL/day", x.get("kld")), ("peak factor", x.get("peak"))])
                 for x in req.get("bulk") or [] if x.get("lat") is not None]
        n["bulk"] = doc.folder(f"Bulk consumers ({len(items)})", items)
    if "prv" in parts:
        sid = doc.style("prv", icon="ff6f00", scale=0.9, label=True)
        items = [_pm(x.get("name") or "PRV", sid, _point(x["lat"], x["lng"]), [("setting (m)", x.get("setting_m"))])
                 for x in req.get("prvs") or [] if x.get("lat") is not None]
        n["prv"] = doc.folder(f"PRVs ({len(items)})", items)

    # ---- the zoning: OZ, DMA, boundary valves
    if z and "zones" in parts:
        items = []
        for i, x in enumerate(z["zones"]):
            rgb = OZ_RGB[i % len(OZ_RGB)]
            sid = doc.style(f"oz{i % len(OZ_RGB)}", line=rgb, width=4, poly=rgb)
            for ring in x.get("rings") or []:
                if len(ring) >= 3:
                    items.append(_pm(x["name"], sid, _poly([ring]), [("OZ", x["name"]), ("population", f"{x.get('population', 0):,}"),
                                                                    ("connections", f"{x.get('connections', 0):,}"), ("DMAs", x.get("dma_count"))]))
        n["zones"] = doc.folder(f"Operational zones (OZ) ({len(z['zones'])})", items)
    if z and "dma" in parts:
        sid = doc.style("dma", line="616161", width=1.5)
        items = [_pm(x["name"], sid, _poly([ring]), [("DMA", x["name"]), ("population", f"{x.get('population', 0):,}"),
                                                    ("connections", f"{x.get('connections', 0):,}"), ("inlet pipe", x.get("inlet_pipe"))])
                 for x in z["dmas"] for ring in (x.get("rings") or []) if len(ring) >= 3]
        n["dma"] = doc.folder(f"DMAs ({len(z['dmas'])})", items, visible=False)
    if z and "valves" in parts:
        sid = doc.style("valve", icon="d50000", scale=0.6)
        items = [_pm(f"{c['pipe']} closed", sid, _point(*c["latlng"]), [("closed pipe", c["pipe"])])
                 for c in z.get("closed") or [] if c.get("latlng")]
        n["valves"] = doc.folder(f"Boundary valves (closed pipes) ({len(items)})", items)
    # ---- the map's wards and barrier lines
    if "wards" in parts:
        sid = doc.style("ward", line="2e7d32", width=2, poly="2e7d32")
        items = [_pm(x.get("name") or "Ward", sid, _poly([x["latlngs"]]), [("ward no.", x.get("ward_no")), ("population", x.get("population"))])
                 for x in req.get("wards") or [] if len(x.get("latlngs") or []) >= 3]
        n["wards"] = doc.folder(f"Wards ({len(items)})", items)
    if "barriers" in parts:
        sid = doc.style("barrier", line="37474f", width=5)
        items = [_pm(x.get("name") or "Barrier", sid, _line(x["latlngs"]), [("type", x.get("type"))])
                 for x in req.get("barriers") or [] if len(x.get("latlngs") or []) >= 2]
        n["barriers"] = doc.folder(f"Barrier lines ({len(items)})", items)
    n["design"], n["zoning"] = bool(d), bool(z)
    return doc.text(), n


def export(stem, req=None, parts=DEFAULT, fmt="kml", path=None):
    """Writes the map (KML, or KMZ = the KML zipped as doc.kml). Returns (path, counts)."""
    fmt = "kmz" if str(fmt).lower() == "kmz" else "kml"
    text, n = build(stem, req, parts)
    if not any(v for k, v in n.items() if k not in ("stale", "design", "zoning")):
        raise ValueError("नक्शे में कुछ नहीं - network, टंकियाँ या zoning पहले बनाएँ (nothing to put on the map yet)")
    if path is None:
        folder = os.path.join(ui.out_root(), stem)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{stem}_map_{time.strftime('%Y%m%d_%H%M')}.{fmt}")
    if fmt == "kmz":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("doc.kml", text)
        data = buf.getvalue()
    else:
        data = text.encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    return path, n
