"""Event-place marker tokens: the ONE definition of each marker type's colour, text glyph and shape.

Everything reads from here:
- Python SVG (static map on Today and map.html, path-slide static images, the Events legend) via `color()`/`shape()`;
  pins carry `style="fill|stroke:var(--gia-marker-<type>,<hex>)"`, so the CSS token wins and the hex (from this table)
  is only the no-CSS fallback.
- CSS: `ROOT_CSS` emits `--gia-marker-<type>` (colour), `--gia-marker-<type>-shape` and `--gia-marker-<type>-glyph`
  into :root of every page (added to the shared history/Today CSS).
- JS (vendor/gia-map.js Leaflet, vendor/gia-cesium.js globe + slide 3D) reads the same custom properties with
  getComputedStyle (window.GIA_MK), so nothing in JS hard-codes a marker colour.

Director 2026-10-19 01:26 ET: military and strike must stop using red (red is severity-only). The Designer picks the
new Carbon colour (not red, orange, yellow, #08bdba, #ee5396 or #c3a6ff) and a glyph shape per type. Until then the
values below are the CURRENT ones, so output is visually unchanged. `shape` names the current drawing; the per-type
shape hook (SHAPES in build_dashboard.svg_pin, pinHtml in gia-map.js, cesPoint in gia-cesium.js) dispatches on it.
"""
# type: (label, colour, text glyph, shape)   -- current values; Designer TBD (colour for military/strike, shapes)
# Designer palette (spec.md "Event markers, severity scale and UI accent", 19 Oct; Director 01:50 ET). Carbon v11.
MARKERS = {
    "military":  ("Military",  "#ffffff", "■", "square"),     # white
    "strike":    ("Strike",    "#ffffff", "✕", "x"),          # white (same colour by ruling; shape separates)
    "diplomacy": ("Diplomacy", "#4589ff", "◆", "diamond"),    # blue 50
    "energy":    ("Energy",    "#a7f0ba", "▲", "triangle"),   # green 20
    "political": ("Political", "#878d96", "○", "ring"),       # cool gray 50
}
PRINT = {"military": "#161616", "strike": "#161616", "diplomacy": "#002d9c", "energy": "#198038", "political": "#697077"}
# Place precision -> halo ring radius (px at 1x; static map at 1000 px wide) on the 2D maps only (Director 02:00): spec
# "Palette rulings 01:50" §2. The ring is drawn in the pin's OWN marker colour (adds no colour pairs); sector is dashed.
PRECISION_HALO = {"feature": 9, "city": 13, "sector": 19}
HALO = {"stroke": 1.5, "dash": {"sector": "4 2.5"}, "past_scale": 0.75, "default": 13}
# Pin shape = the most common event type among the stories at the place; ties go kinetic first, then MARKERS order.
TIE_ORDER = ("strike", "military", "energy", "diplomacy", "political")
def dominant(markers):
    from collections import Counter
    c = Counter(kind(m) for m in markers if m)
    if not c: return "political"
    return min(c, key=lambda k: (-c[k], TIE_ORDER.index(k) if k in TIE_ORDER else 99))
# Pin labels (room 01:58; r4 Director 03:53: Medium face dropped, 500 -> 600): active 600 12px tx-1, past 400 11px tx-2.
LABEL = {"active": ("#f3efe7", 600, 12), "past": ("#d0cac0", 400, 11)}
DEFAULT = "political"

# Sprite geometry per shape, for the batched Cesium billboards (globe + slide 3D) and the Leaflet pins.
# 16x16 viewBox; (SVG path d, paint "fill"|"stroke", stroke width in viewBox units). PLACEHOLDERS = today's Leaflet
# shapes; the Designer's shapes replace these entries (data-only edit). The 2D static SVG keeps its own SHAPES
# drawing in build_dashboard.py for now (byte-stable output); it dispatches on the same `shape` names.
SHAPE_SVG = {   # spec.md 19 Oct "Shapes: SHAPE_SVG entries" (Carbon square--solid, close, diamond--solid, triangle--solid, circle--outline)
    "square":   ("M4 3H12A1 1 0 0 1 13 4V12A1 1 0 0 1 12 13H4A1 1 0 0 1 3 12V4A1 1 0 0 1 4 3Z", "fill",   1.0),
    "x":        ("M3.5 3.5L12.5 12.5M12.5 3.5L3.5 12.5",                                       "stroke", 3.0),
    "diamond":  ("M8 1L15 8L8 15L1 8Z",                                                        "fill",   1.0),
    "triangle": ("M8 1.5L15 13.5H1Z",                                                          "fill",   1.0),
    "ring":     ("M3 8A5 5 0 1 0 13 8A5 5 0 1 0 3 8Z",                                         "stroke", 2.5),
}
SPRITE = {"outline": "#0b0f14", "outline_print": "#ffffff", "active_px": 18, "past_px": 12, "past_alpha": 1.0,
          "static_active_px": 16, "static_past_px": 11}   # spec §3: static map glyph 16 / 11 px (Leaflet + globe 18 / 12)

def kind(m): return m if m in MARKERS else DEFAULT
def label(m): return MARKERS[kind(m)][0]
def hexcolor(m): return MARKERS[kind(m)][1]
def glyph(m): return MARKERS[kind(m)][2]
def shape(m): return MARKERS[kind(m)][3]
def color(m):
    """CSS colour value for SVG style/inline use: the token, with this table's hex as the no-CSS fallback."""
    k = kind(m); return f"var(--gia-marker-{k},{MARKERS[k][1]})"

ROOT_CSS = ":root{" + "".join(
    f"--gia-marker-{k}:{c};--gia-marker-{k}-shape:{s};--gia-marker-{k}-glyph:\"{g}\";" for k, (_, c, g, s) in MARKERS.items()) + "}" 
ROOT_CSS = ROOT_CSS[:-1] + "".join(
    f"--gia-shape-{n}-d:\"{d}\";--gia-shape-{n}-paint:{pt};--gia-shape-{n}-w:{w};" for n, (d, pt, w) in SHAPE_SVG.items()) + (
    f"--gia-sprite-outline:{SPRITE['outline']};--gia-sprite-active:{SPRITE['active_px']};--gia-sprite-past:{SPRITE['past_px']};"
    f"--gia-sprite-past-alpha:{SPRITE['past_alpha']};--gia-precision-stroke:{HALO['stroke']};--gia-precision-past-scale:{HALO['past_scale']};"
    f"--gia-precision-sector-dash:{HALO['dash']['sector']};--gia-label:{LABEL['active'][0]};--gia-label-past:{LABEL['past'][0]};"
    + "".join(f"--gia-precision-{p}:{r};" for p, r in PRECISION_HALO.items())) + "}" + (
    "@media print{:root{" + "".join(f"--gia-marker-{k}:{c};" for k, c in PRINT.items()) + f"--gia-sprite-outline:{SPRITE['outline_print']}}}}}")
def inline_svg(m, px=13):
    """One small marker for text rows (board lists). Same path data, same --gia-marker-* token and
    same label the map and the legend already use, so the key the legend teaches is the key the rest
    of the page honours. role=img + aria-label, because a title= on a span is not reliably announced."""
    k = kind(m); d, paint, w = SHAPE_SVG[MARKERS[k][3]]
    ink = (f'fill="{color(k)}"' if paint == "fill"
           else f'fill="none" stroke="{color(k)}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"')
    return (f'<svg class="mkin" width="{px}" height="{px}" viewBox="0 0 16 16" role="img" aria-label="{label(k)}">'
            f'<path d="{d}" {ink}/></svg>')

GLYPH = {k: v[2] for k, v in MARKERS.items()}
