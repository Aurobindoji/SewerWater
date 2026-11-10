"""KML / KMZ (Google Earth) input and map projection.

    k = geo.read_kml("roads.kml")              # {"lines": [...], "polygons": [...], "points": [...]} in lon / lat
    epsg = geo.utm_epsg(lon, lat)              # Springfield: 32644 (UTM 44N, as the drawings)
    xy = geo.to_xy(coords, epsg)               # [(x, y)] in metres

Each feature: {"name", "coords": [(lon, lat[, alt])], "data": {ExtendedData name: value}, "folder": folder name}.
A MultiGeometry gives one feature per part. KMZ = zipped KML (the first .kml inside is read).
"""
import re
import xml.etree.ElementTree as ET
import zipfile


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _coords(text):
    out = []
    for tok in (text or "").split():
        p = tok.split(",")
        if len(p) >= 2:
            try:
                out.append(tuple(float(v) for v in p[:3]))
            except ValueError:
                continue
    return out


_ROW = re.compile(r"<tr[^>]*>\s*<td[^>]*>((?:(?!</?t[dr]|<table).)*)</td>\s*<td[^>]*>((?:(?!</?t[dr]|<table).)*)</td>\s*</tr>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")


def desc_table(html):
    """{field: value} from the two-cell rows of a KML description table."""
    out = {}
    for k, v in _ROW.findall(html or ""):
        k, v = _TAG.sub("", k).strip(), _TAG.sub("", v).strip()
        if k and "<" not in k:
            out.setdefault(k, v)
    return out


POP_KEYS = ("population", "pop", "w_pop", "total_pop", "tot_pop", "jansankhya", "जनसंख्या")


BARRIER_FOLDER = "Barrier lines"      # the map page's folder of barrier lines (no pipe crosses one, 27-Oct-2026)
CROSSING_FOLDER = "Crossings"         # the map page's folder of crossings (a pipe across a barrier / loop)
LOOP_FOLDER = "Zone loops"            # the map page's folder of zone loops (an area enclosed = a zone, 27-Oct-2026)


def read_kml(path):
    if path.lower().endswith(".kmz"):
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".kml"))
            root = ET.fromstring(z.read(name))
    else:
        root = ET.parse(path).getroot()
    out = {"lines": [], "polygons": [], "points": [], "barriers": [], "zone_loops": [], "crossings": []}

    def walk(el, folder):
        tag = _local(el.tag)
        if tag in ("Folder", "Document"):
            nm = next((c.text for c in el if _local(c.tag) == "name"), None) or folder
            for c in el:
                walk(c, nm if tag == "Folder" else folder)
            return
        if tag == "Placemark":
            name = next((c.text for c in el if _local(c.tag) == "name"), "") or ""
            data = {}
            for d in el.iter():
                t = _local(d.tag)
                if t == "Data":
                    v = next((c.text for c in d if _local(c.tag) == "value"), None)
                    data[d.get("name")] = v
                elif t == "SimpleData":
                    data[d.get("name")] = d.text
            desc = next((c.text for c in el if _local(c.tag) == "description"), None)
            if desc:
                data.setdefault("description", desc)
                for k_, v_ in desc_table(desc).items():      # GIS exports (ArcGIS ...): the fields as a table
                    data.setdefault(k_, v_)
            for g in el.iter():
                t = _local(g.tag)
                if t == "LineString":
                    c = next((x.text for x in g if _local(x.tag) == "coordinates"), "")
                    # a barrier line / crossing of the map page is no road: kept apart
                    key = ("barriers" if folder == BARRIER_FOLDER or data.get("kind") == "barrier" else
                           "crossings" if folder == CROSSING_FOLDER or data.get("kind") == "crossing" else "lines")
                    out[key].append({"name": name, "coords": _coords(c), "data": data, "folder": folder})
                elif t == "Polygon":
                    outer = next((x for x in g.iter() if _local(x.tag) == "outerBoundaryIs"), None)
                    c = next((x.text for x in (outer.iter() if outer is not None else g.iter())
                              if _local(x.tag) == "coordinates"), "")
                    # a zone loop of the map page is no ward / boundary: kept apart
                    key = "zone_loops" if folder == LOOP_FOLDER or data.get("kind") == "zone_loop" else "polygons"
                    out[key].append({"name": name, "coords": _coords(c), "data": data, "folder": folder})
                elif t == "Point":
                    c = next((x.text for x in g if _local(x.tag) == "coordinates"), "")
                    out["points"].append({"name": name, "coords": _coords(c), "data": data, "folder": folder})
            return
        for c in el:
            walk(c, folder)
    walk(root, "")
    return out


def utm_epsg(lon, lat):
    """EPSG code of the WGS84 UTM zone of a point (north: 326zz, south: 327zz)."""
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def to_xy(coords, epsg):
    """[(lon, lat[, alt])] -> [(x, y)] in the projected system epsg."""
    from pyproj import Transformer
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    return [tuple(t.transform(c[0], c[1])) for c in coords]


def number(v):
    """A number from a KML data value such as '12,345' or '12345 persons'; None if none."""
    m = re.search(r"-?\d[\d,]*\.?\d*", str(v or ""))
    return float(m.group(0).replace(",", "")) if m else None
