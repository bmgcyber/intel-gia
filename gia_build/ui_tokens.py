"""UI tokens (Director 2026-10-19 01:30 ET). ONE edit point each:
- --gia-accent-ui: non-severity UI accent (tooltip/badge borders, heading rules, year headings, current chain row, progress).
  TEMPORARY neutral #8d8d8d until the Designer picks a Carbon neutral. Red is severity-only.
- --gia-focus: Carbon $focus on dark themes (#ffffff), 2px outline, inset (outline-offset:-2px) per Carbon.
"""
ACCENT_UI = "#a8a8a8"   # Carbon gray 40 (Designer 01:43 / Director 01:50)
FOCUS = "#ffffff"
PATH = "#c3a6ff"; PATH_PRINT = "#6929c4"   # purple 70: the judgment layer needs an ink twin like every other token   # path / trail / NOW (judgment layer); 2D slides, Leaflet and globe all purple, no yellow (Director 01:35 ET)
# Severity (Director 01:37 ET): ONE screen + ONE print token per level (data/SCHEMA.md: critical|high|elevated|watch).
# Current values = Today's Carbon set (the old map set was Apple system colours: #ff3b30 #ff9f0a #ffd60a #64d2ff).
# Designer posts the final values; edit only this table.
SEV = {  # level: (screen, print, outline)
    "critical": ("#fa4d56", "#a2191f", "#0a1a2a"),   # red 50 / red 70
    "high":     ("#ff832b", "#8a3800", "#0a1a2a"),   # orange 40 / orange 70 (Director 01:59: one print value per level)
    "elevated": ("#fddc69", "#684e00", "#0a1a2a"),   # yellow 20 / yellow 70 (#302400 read as black, QA 01:50)
    "watch":    ("#c1c7cd", "#4d5358", "#0a1a2a"),   # cool gray 30 / cool gray 70
}
# outline: dark keyline hook per level for zone rings / areas, so colour never depends on the tile under it. Designer
# 01:37 ET: 1px #0a1a2a on EVERY level for Leaflet and Cesium rings; "none" switches a level off. The static map keeps
# no halo outline by default (fixed sea/land fills, Director: default none) -> STATIC_HALO_OUTLINE.
SEV_OUTLINE_PX = 1
STATIC_HALO_OUTLINE = False
SEV_CRITICAL = SEV["critical"][0]; SEV_CRITICAL_PRINT = SEV["critical"][1]
SEV_GLYPH = "#fa4d56"      # red 50 (#ff8a8f failed 2.26:1 on the white Leaflet popup); print glyph = ink
SEV_GLYPH_PRINT = "#141312"
# Critical level WORD on screen (meter <b>): the spec keeps #ff8a8f (--sev-critical-tx) for the hifi --ink-3 surface; this build
# has no --ink-3 (meters sit on card #111821 5.32:1 / page #0b0f14 5.73:1), and the Director retired #ff8a8f, so it is red 50.
SEV_CRITICAL_TX = "#fa4d56"
FOCUS_PRINT = "#0f62fe"    # Carbon $focus, white theme
# Links (room 01:58 / spec "Palette rulings 01:50" §1): neutral text, 1px gray 50 rule at offset 3; hover gray 10 text + rule, 2px.
LINK = "#f3efe7"; LINK_RULE = "#8d8d8d"; LINK_HOVER = "#f4f4f4"
LINK_RULE_PX = 1; LINK_HOVER_RULE_PX = 2; LINK_OFFSET_PX = 3
LINK_PRINT = "#141312"; LINK_RULE_PRINT = "#6b665e"
FOCUS_PX = 2; FOCUS_OFFSET_PX = 2      # :focus-visible ring (FOCUS on screen, FOCUS_PRINT in print); :target keeps its inset -2
POPUP_LINK = "#161616"; POPUP_LINK_RULE = "#6f6f6f"   # white Leaflet popup: dark ink link (approved 02:00)
# Headings (Director 02:00): neutral, no blue text left except diplomacy markers.
H2 = "#f3efe7"; H4 = "#d0cac0"; HEAD_PRINT = "#161616"
CHIP_BG = "#262626"; CHIP_BORDER = "#393939"   # Carbon gray 90 / 80: chips + nav buttons that were blue
CARD_BG = "#111821"        # build card surface (.card / .reg)
# Static-map label solver (Director 02:15 item 1): no leader longer than 70 px; a label that needs more becomes a numbered
# marker. EPS absorbs float rounding so a leader at exactly 70 px is kept.
LEADER_MAX_PX = 70; LEADER_EPS_PX = 0.5
# r3 (Director 03:03): the cap is measured in SCREEN px at a 1440 px viewport. The static map's SVG (viewBox width 1000)
# renders 1300 CSS px wide there (main max-width:1300px; measured in headless Chrome 03:04 ET), so 70 screen px =
# 70*1000/1300 = 53.85 map units. LABEL_GAP: label boxes may not touch (strict test), so every label box is grown by this
# much (map units) on each side before any overlap test, which also covers the 3 px text halo and the font's ascent/descent.
MAP_PX_1440 = 1300; MAP_VIEW_W = 1000
LEADER_MAX_UNITS = LEADER_MAX_PX * MAP_VIEW_W / MAP_PX_1440
LABEL_GAP = 4
# Leaflet attribution bar (Director 02:15): card background at full opacity; text + link gray 40 with the standard
# link underline (LINK_RULE 1px, offset 3) and hover (LINK_HOVER, 2px). #a8a8a8 on #111821 = 7.51:1.
ATTRIB_BG = CARD_BG; ATTRIB_TX = "#a8a8a8"
# Example-data tag (spec "Palette rulings 01:50" §4). Not rendered by this build yet (no data is flagged example).
EXAMPLE_BG = ("#525252", "#393939"); EXAMPLE_TX = "#f3efe7"; EXAMPLE_EDGE = "#8d8d8d"   # stripes 6px / 2px at 135deg
EXAMPLE_PRINT = ("#161616", ("#f4f4f4", "#e0e0e0"), "#6f6f6f")                         # (text, stripes, edge)
ACCENT_UI_PRINT = "#6f6f6f"  # print variant: #8d8d8d is 3.30:1 on white (<4.5); Carbon gray 60 = 5.02:1. Temporary.

def sev(level): return SEV.get(level, SEV["watch"])[0]
def sev_print(level): return SEV.get(level, SEV["watch"])[1]

ROOT_CSS = (f":root{{--gia-accent-ui:{ACCENT_UI};--gia-accent-ui-print:{ACCENT_UI_PRINT};--gia-focus:{FOCUS};--gia-path:{PATH};"
            f"--gia-link:{LINK};--gia-link-rule:{LINK_RULE};--gia-link-hover:{LINK_HOVER};--gia-link-rule-px:{LINK_RULE_PX}px;"
            f"--gia-link-hover-rule-px:{LINK_HOVER_RULE_PX}px;--gia-link-offset:{LINK_OFFSET_PX}px;--gia-focus-px:{FOCUS_PX}px;--gia-focus-offset:{FOCUS_OFFSET_PX}px;"
            f"--gia-popup-link:{POPUP_LINK};--gia-popup-link-rule:{POPUP_LINK_RULE};--gia-h2:{H2};--gia-h4:{H4};"
            f"--gia-chip-bg:{CHIP_BG};--gia-chip-border:{CHIP_BORDER};--gia-card-bg:{CARD_BG};--gia-attrib-bg:{ATTRIB_BG};--gia-attrib-tx:{ATTRIB_TX};"
            f"--gia-example-a:{EXAMPLE_BG[0]};--gia-example-b:{EXAMPLE_BG[1]};--gia-example-tx:{EXAMPLE_TX};--gia-example-edge:{EXAMPLE_EDGE};"
            f"--gia-sev-critical-tx:{SEV_CRITICAL_TX};"
            + "".join(f"--gia-sev-{k}:{c};--gia-sev-{k}-print:{p};--gia-sev-{k}-outline:{o};" for k, (c, p, o) in SEV.items())
            + f"--gia-sev-outline-px:{SEV_OUTLINE_PX};--gia-sev-glyph:{SEV_GLYPH}}}"
            + f"@media print{{:root{{--gia-focus:{FOCUS_PRINT};--gia-sev-glyph:{SEV_GLYPH_PRINT};--gia-link:{LINK_PRINT};--gia-link-rule:{LINK_RULE_PRINT};"
            f"--gia-path:{PATH_PRINT};--gia-h2:{HEAD_PRINT};--gia-h4:{HEAD_PRINT};--gia-example-tx:{EXAMPLE_PRINT[0]};--gia-example-a:{EXAMPLE_PRINT[1][0]};"
            f"--gia-example-b:{EXAMPLE_PRINT[1][1]};--gia-example-edge:{EXAMPLE_PRINT[2]}}}}}")
# Link/chip/example rules (shared CSS). Focus keeps --gia-focus (:focus-visible) everywhere.
LINK_CSS = ("a{color:var(--gia-link);text-decoration:underline;text-decoration-color:var(--gia-link-rule);text-decoration-thickness:var(--gia-link-rule-px);"
            "text-underline-offset:var(--gia-link-offset)}"
            "a:hover{color:var(--gia-link-hover);text-decoration-color:var(--gia-link-hover);text-decoration-thickness:var(--gia-link-hover-rule-px)}"
            "a:focus-visible,button:focus-visible{outline:var(--gia-focus-px) solid var(--gia-focus);outline-offset:var(--gia-focus-offset)}"
            # Leaflet popups are white: link = dark ink with a gray 60 rule (17.7:1), not the dark-theme #f3efe7
            ".leaflet-popup-content a{color:var(--gia-popup-link);text-decoration-color:var(--gia-popup-link-rule)}"
            ".leaflet-popup-content a:hover{color:#000;text-decoration-color:currentColor}"
            ".chip:hover,.navrow a.btn:hover{color:var(--gia-link-hover);border-color:var(--gia-link)}"
            # Leaflet attribution bar (Director 02:15). Selectors out-rank leaflet.css (lazy-loaded after this sheet).
            ".leaflet-container .leaflet-control-container .leaflet-control-attribution{background:var(--gia-attrib-bg);color:var(--gia-attrib-tx);opacity:1}"
            ".leaflet-container .leaflet-control-attribution a{color:var(--gia-attrib-tx);text-decoration:underline;text-decoration-color:var(--gia-link-rule);"
            "text-decoration-thickness:var(--gia-link-rule-px);text-underline-offset:var(--gia-link-offset)}"
            ".leaflet-container .leaflet-control-attribution a:hover{color:var(--gia-link-hover);text-decoration:underline;"
            "text-decoration-color:var(--gia-link-hover);text-decoration-thickness:var(--gia-link-hover-rule-px)}"
            ".leaflet-container .leaflet-control-attribution a:focus-visible{outline:var(--gia-focus-px) solid var(--gia-focus);outline-offset:var(--gia-focus-offset)}"
            # map surfaces never show link styling (Director 01:59; qa/link_surface_check.py): pin links in the 2D slide maps
            ".wmap a{text-decoration:none;color:inherit}.wmap a:hover{text-decoration:none}"
            ".gia-example{display:inline-block;padding:0 6px;font:600 11px/18px 'IBM Plex Mono',monospace;letter-spacing:.04em;"
            "color:var(--gia-example-tx);border:1px solid var(--gia-example-edge);"
            "background:repeating-linear-gradient(135deg,var(--gia-example-a) 0 6px,var(--gia-example-b) 6px 8px)}"
            "@media print{.gia-example{print-color-adjust:exact;-webkit-print-color-adjust:exact}}"
            # print-only marks (spec "Palette rulings 01:50" §5): every printed severity mark carries its word or glyph
            ".pr-only{display:none}@media print{.pr-only{display:inline}}"
            # headings (Director 02:00): neutral, Plex Sans 600; h2 keeps its size, h4 12px uppercase .32px
            "h2{color:var(--gia-h2);font-family:'IBM Plex Sans',Arial,sans-serif;font-weight:600}"
            ".tl h4,h4{color:var(--gia-h4);font:600 12px/16px 'IBM Plex Sans',Arial,sans-serif;text-transform:uppercase;letter-spacing:.32px}")


# r3 tap targets (QA round 4 item 6, Director 03:06): ONLY chips, toggles (<summary>, the 'expand here' button.more) and
# buttons (<button>, nav a.btn) get a 24 px minimum (WCAG 2.5.8). min-height/min-width only: never display, never generic
# links, never the static-map link, slide-map pin links or map containers. :where() = zero specificity, so every existing
# larger rule (44 px phone rows, 48 px .gbtn) and the print reset (.chip min-height:0 !important) still win.
TAP_MIN_PX = 24
TAP_CSS = (":where(.chip,summary,button,a.btn){min-height:%dpx;min-width:%dpx;box-sizing:border-box}" % (TAP_MIN_PX, TAP_MIN_PX))

# r4 (Director 03:53 item 2): print map level words at 10.5pt = 14 CSS px (96 dpi). PRINT_MAP_PX = the static map's drawn
# width in print media (Letter portrait, 0.5 in margins), measured in Chrome print emulation (qa/r4/print_measure.py).
PRINT_LEVEL_PX = 14
PRINT_MAP_PX = 717   # measured: svg.wmap box 720 px in print media (DOM); PDF text at 19.44 units printed 10.46 pt -> drawn width 717 px
PRINT_LS_UNITS = round(PRINT_LEVEL_PX * MAP_VIEW_W / PRINT_MAP_PX, 2)

# r4 (Director 04:24 item 2; QA round 5 §2): pages without Today's print sheet (history, slides, v7 pages) print light with
# dark text even with "Background graphics" ON: explicit white page + transparent boxes + #141312 text, all !important at
# zero specificity (any !important print rule of the page still wins); SVG content keeps its own fills.
PRINT_FORCE_LIGHT = ("@media print{html,body{background:#fff!important;color:#141312!important;-webkit-print-color-adjust:economy;print-color-adjust:economy}"
    ":where(:not(svg,svg *)){background-color:transparent!important;background-image:none!important;color:#141312!important;"
    "box-shadow:none!important;text-shadow:none!important;border-color:#d9d4cb!important}"
    ":where(a,a *){color:#141312!important}"
    "a.pathbtn,a.pathbtn *{color:#141312!important;background:transparent!important;border:.6pt solid #d9d4cb!important}}")

# r5 (Director 05:01 item 2, Designer r5 spec 05:01): notes upright Plex Sans 400, marked by colour + a left rule, never italic.
NOTE_TX, NOTE_RULE = "#d0cac0", "#525252"            # screen
NOTE_TX_PRINT, NOTE_RULE_PRINT = "#525252", "#a8a8a8"  # print
UPRIGHT_CSS = ":where(*){font-style:normal}"          # zero specificity: UA em/i/cite/var/dfn/address go upright; no synthetic oblique
NOTE_CSS = (f'.an{{color:{NOTE_TX};font-style:normal;font-weight:400;font-family:"IBM Plex Sans",Arial,sans-serif;border-left:2px solid {NOTE_RULE};padding-left:8px}}'
            f'.an em,.an i{{font-style:normal}}'
            f'@media print{{.an,.an *{{color:{NOTE_TX_PRINT}!important}}.an{{border-left:2px solid {NOTE_RULE_PRINT}!important}}}}')
# r5 (Designer r5 05:01): print level-word halo = visible 3 px outside the glyph (paint-order stroke: half the stroke shows),
# in CSS px via vector-effect:non-scaling-stroke. Raise PRINT_HALO_PX to 4 if the audit reads under 6:1 anywhere.
PRINT_HALO_PX = 4   # r5: Designer rule: the r4-method audit read under 6:1 at 3 px (4.49 on the SCS WATCH), so raised to 4 px

def fonts(prefix=""):
    """@font-face for the 3 kept faces; prefix is the relative path to the site root ("../" from history/, "../../" from a path folder)."""
    return "".join(f'@font-face{{font-family:"IBM Plex {fam}";font-weight:{w};font-display:swap;src:url({prefix}vendor/fonts2/GIA-Plex{fam}-{f}.woff2) format("woff2")}}'
                   for fam, w, f in (("Sans", 400, "Regular"), ("Sans", 600, "SemiBold"), ("Mono", 500, "Medium")))   # r4: Sans Medium + Italic dropped

# r5 (Director 05:58 item 2): print map zone names 8 pt = 10.667 CSS px at the measured 717 px print map width
PRINT_NS_UNITS = round(8 / 0.75 * MAP_VIEW_W / PRINT_MAP_PX, 2)
# r5 (Director 05:58 item 3): print leaders; colour measured in the PDF against the print sea (qa/r5/print_pdf_audit.json)
PRINT_LEADER = "#767676"
# r5 (Director 05:58 item 4; Designer site.css print rules): slide SVG maps print on the light print palette like Today's
# print map: sea #f3f1ec, land #dcd7cd / #b8b1a5, label text #161616 with a 3 px white halo, the NOW card on white.
SLIDE_PRINT_CSS = ("@media print{.smap{-webkit-print-color-adjust:exact;print-color-adjust:exact}"
    ".smap .sbg{fill:#f3f1ec!important}.smap .sland{fill:#dcd7cd!important;stroke:#b8b1a5!important}"
    ".smap .snow{fill:#ffffff!important;fill-opacity:1!important;stroke:#a8a8a8!important}"
    ".smap text{fill:#161616!important;stroke:#ffffff!important;stroke-width:6px!important;stroke-linejoin:round;paint-order:stroke;vector-effect:non-scaling-stroke}"
    ".smap rect:not(.sbg):not(.snow){fill:#a8a8a8!important;opacity:1!important}}")
