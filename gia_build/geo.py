"""Geometry helpers for the build (stdlib only)."""

def _rings(area):
    return [area["coordinates"]] if area["type"] == "Polygon" else list(area["coordinates"])

def _ring_area_centroid(ring):
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        f = x1 * y2 - x2 * y1
        a += f; cx += (x1 + x2) * f; cy += (y1 + y2) * f
    if a == 0:
        xs, ys = zip(*ring); return 0.0, sum(xs) / len(xs), sum(ys) / len(ys)
    return a / 2, cx / (3 * a), cy / (3 * a)

def inside(lon, lat, area):
    def in_ring(ring):
        c = False
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                c = not c
        return c
    return any(in_ring(p[0]) and not any(in_ring(h) for h in p[1:]) for p in _rings(area))

def anchor(area):
    """Label anchor (lon, lat) inside the area: centroid of the largest polygon if it falls
    inside, else the middle of the widest inside stretch along the centroid's latitude.
    A label position only; never a story pin."""
    poly = max(_rings(area), key=lambda p: abs(_ring_area_centroid(p[0])[0]))
    _, cx, cy = _ring_area_centroid(poly[0])
    if inside(cx, cy, area):
        return round(cx, 3), round(cy, 3)
    xs = sorted(x1 + (cy - y1) * (x2 - x1) / (y2 - y1) for ring in poly for (x1, y1), (x2, y2) in zip(ring, ring[1:]) if (y1 > cy) != (y2 > cy))
    spans = [(b - a, (a + b) / 2) for a, b in zip(xs[::2], xs[1::2])]
    return (round(max(spans)[1], 3), round(cy, 3)) if spans else (round(cx, 3), round(cy, 3))

def svg_path(area, project):
    parts = []
    for poly in _rings(area):
        for ring in poly:
            pts = [project(x, y) for x, y in ring]
            parts.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return "".join(parts)
