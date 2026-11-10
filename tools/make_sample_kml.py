"""Write samples/sample_area.kml - a made-up area near Springfield showing how a KML for
'python -m sewer_app layout' is drawn in Google Earth: roads (Paths), project boundary, wards with population,
spot levels and the STP point - all in one file, each in its own folder.

    .venv\\Scripts\\python tools\\make_sample_kml.py
"""
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "samples", "sample_area.kml")
LON0, LAT0 = 82.9900, 25.3300                          # south-west corner of the sample area
M_LAT = 110850.0                                       # metres per degree of latitude
M_LON = 111320.0 * math.cos(math.radians(LAT0))        # metres per degree of longitude here


def ll(x, y):
    """Local metres (east, north from the SW corner) -> 'lon,lat,0'."""
    return f"{LON0 + x / M_LON:.7f},{LAT0 + y / M_LAT:.7f},0"


def coords(pts):
    return " ".join(ll(x, y) for x, y in pts)


ROADS = [
    ("Main road (east-west)", [(0, 250), (200, 252), (420, 248), (700, 250)]),
    ("North road", [(0, 480), (650, 480)]),
    ("South road", [(100, 40), (700, 40)]),
    ("Cross street 1", [(80, 40), (80, 480)]),
    ("Cross street 2", [(240, 40), (240, 480)]),
    ("Cross street 3", [(400, 40), (400, 480)]),
    ("Cross street 4", [(560, 40), (560, 250)]),
    ("Lane A (dead end)", [(160, 250), (160, 380)]),
    ("Lane B (dead end)", [(320, 250), (320, 120)]),
    ("Lane C (dead end)", [(480, 480), (480, 360)]),
    ("Curved road", [(600, 250), (630, 300), (660, 360), (680, 420), (690, 480)]),
    ("Link to STP", [(80, 40), (40, 25), (10, 20)]),
]
BOUNDARY = [(-20, 0), (720, 0), (720, 510), (-20, 510), (-20, 0)]
WARDS = [("Ward 1 (west)", 5200, [(-20, 0), (370, 0), (370, 510), (-20, 510), (-20, 0)]),
         ("Ward 2 (east)", 3800, [(370, 0), (720, 0), (720, 510), (370, 510), (370, 0)])]
STP = (10, 20)


def gl(x, y):
    """Ground falling from the north-east (about 83.2 m) to the south-west (about 80.6 m)."""
    return 80.6 + 2.6 * (x / 720 * 0.45 + y / 510 * 0.55)


def main():
    rnd = random.Random(3)
    spots = [(x, y) for x in (60, 250, 450, 650) for y in (30, 180, 330, 490)]
    pm = []
    pm.append("<Folder><name>Roads (Paths)</name>")
    for name, pts in ROADS:
        pm.append(f"<Placemark><name>{name}</name><styleUrl>#road</styleUrl><LineString><tessellate>1</tessellate>"
                  f"<coordinates>{coords(pts)}</coordinates></LineString></Placemark>")
    pm.append("</Folder><Folder><name>Project boundary</name>")
    pm.append(f"<Placemark><name>Project boundary</name><styleUrl>#boundary</styleUrl><Polygon><outerBoundaryIs>"
              f"<LinearRing><coordinates>{coords(BOUNDARY)}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
              f"</Placemark>")
    pm.append("</Folder><Folder><name>Wards with population</name>")
    for name, pop, pts in WARDS:
        pm.append(f"<Placemark><name>{name}</name><styleUrl>#ward</styleUrl><ExtendedData>"
                  f"<Data name=\"population\"><value>{pop}</value></Data></ExtendedData><Polygon><outerBoundaryIs>"
                  f"<LinearRing><coordinates>{coords(pts)}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
                  f"</Placemark>")
    pm.append("</Folder><Folder><name>Spot levels (GL)</name>")
    for x, y in spots:
        v = gl(x, y) + rnd.uniform(-0.05, 0.05)
        pm.append(f"<Placemark><name>GL {v:.2f}</name><styleUrl>#level</styleUrl><Point>"
                  f"<coordinates>{ll(x, y)}</coordinates></Point></Placemark>")
    pm.append("</Folder><Folder><name>STP / outfall</name>")
    pm.append(f"<Placemark><name>STP</name><styleUrl>#stp</styleUrl><Point><coordinates>{ll(*STP)}</coordinates>"
              f"</Point></Placemark></Folder>")
    desc = ("नमूना क्षेत्र (काल्पनिक, स्प्रिंगफ़ील्ड के पास) - sewer_app layout के लिए KML ऐसे बनाएँ: "
            "1) सड़कें: Google Earth में 'Add Path' से हर सड़क की बीच की रेखा (centreline); चौराहे पर रेखाएँ एक-दूसरे को "
            "काटें या छुएँ (1 m तक की चूक अपने-आप जुड़ जाती है)। "
            "2) Project boundary: 'Add Polygon' - सबसे बड़ा polygon boundary माना जाता है। "
            "3) वार्ड / मोहल्ले: 'Add Polygon', Properties में ExtendedData 'population' (या नाम --population-field से)। "
            "4) Spot levels: 'Add Placemark' - नाम में स्तर, जैसे 'GL 81.25' (Google Earth नीचे cursor की ऊँचाई दिखाता है; "
            "यह PFR स्तर का अनुमान है)। "
            "5) STP: 'Add Placemark', नाम STP - सबसे पास का manhole layout बताता है। "
            "File > Save Place As > KML/KMZ।")
    styles = ('<Style id="road"><LineStyle><color>ff0000ff</color><width>3</width></LineStyle></Style>'
              '<Style id="boundary"><LineStyle><color>ff00ffff</color><width>2</width></LineStyle>'
              '<PolyStyle><fill>0</fill></PolyStyle></Style>'
              '<Style id="ward"><LineStyle><color>ff00aa00</color><width>1</width></LineStyle>'
              '<PolyStyle><color>3300aa00</color></PolyStyle></Style>'
              '<Style id="level"><IconStyle><scale>0.6</scale></IconStyle></Style>'
              '<Style id="stp"><IconStyle><scale>1.2</scale></IconStyle></Style>')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                 f"<name>sewer_app sample area (Springfield)</name><description>{desc}</description>{styles}"
                 + "".join(pm) + "</Document></kml>\n")
    print(OUT)


if __name__ == "__main__":
    main()
