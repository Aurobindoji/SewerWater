"""netedit: the drawing's coordinates to latitude / longitude and back."""


# ---------------------------------------------------------------- coordinates
def converters(st):
    """(to_latlng([[x, y], ...]) -> [[lat, lon], ...], to_xy([[lat, lon], ...]) -> [[x, y], ...]). Without an EPSG
    (local drawing coordinates) metres are laid out around 0 deg / 0 deg (no background map). A network placed on
    the map (place) is shifted by st["shift"] metres in its EPSG; x, y stay the drawing's."""
    if st.get("epsg"):
        from pyproj import Transformer
        fwd = Transformer.from_crs(st["epsg"], 4326, always_xy=True)
        inv = Transformer.from_crs(4326, st["epsg"], always_xy=True)
        dx, dy = st.get("shift") or (0.0, 0.0)

        def to_ll(pts):
            if not pts:
                return []
            lon, lat = fwd.transform([p[0] + dx for p in pts], [p[1] + dy for p in pts])
            return [[round(a, 7), round(b, 7)] for a, b in zip(lat, lon)]

        def to_xy(pts):
            if not pts:
                return []
            x, y = inv.transform([p[1] for p in pts], [p[0] for p in pts])
            return [[round(a - dx, 3), round(b - dy, 3)] for a, b in zip(x, y)]
        return to_ll, to_xy
    x0, y0 = st.get("origin") or (0.0, 0.0)
    return (lambda pts: [[round((p[1] - y0) / 110574.0, 8), round((p[0] - x0) / 111320.0, 8)] for p in pts],
            lambda pts: [[round(p[1] * 111320.0 + x0, 3), round(p[0] * 110574.0 + y0, 3)] for p in pts])
