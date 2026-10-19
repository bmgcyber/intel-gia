"""Today sections ported from the local fork (structure) with the hi-fi look (spec.md, tokens.css):
sec-board, sec-markets, sec-connect, sec-storylines, sec-calendar. Everything comes from data/
as SCHEMA.md defines it; nothing is invented. A section with nothing to show still renders its
id, heading and one plain empty-state line, so shots.py element screenshots always have a box.
No JS. Severity is always bar count + word; market moves are sign + arrow + colour (teal up,
magenta down: never red/green); judgment (causal chains) uses the --judg purple."""
import datetime as _dt, html, json, os, re

esc = lambda s: html.escape(str(s), quote=True)
SEV_RANK = {"critical": 4, "high": 3, "elevated": 2, "watch": 1}
from gia_build import ui_tokens as UI
SEV_COL = {k: v[0] for k, v in UI.SEV.items()}  # ui_tokens.SEV only
from gia_build.markers import GLYPH  # one definition (gia_build/markers.py)
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
# IBM Carbon icons (@carbon/icons 11.90.0, Apache-2.0; studio/engineer/icons/SOURCES.md), path data verbatim.
ICON_ARROW_DOWN = '<svg class="ci" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false"><path d="M12.3 9.3 8.5 13.1 8.5 1 7.5 1 7.5 13.1 3.7 9.3 3 10 8 15 13 10z"/></svg>'
ICON_GLOBE = '<svg class="ci" viewBox="0 0 32 32" width="16" height="16" aria-hidden="true" focusable="false"><path d="M14,4a7,7,0,1,1-7,7,7,7,0,0,1,7-7m0-2a9,9,0,1,0,9,9A9,9,0,0,0,14,2Z"/><path d="M28,11a13.9563,13.9563,0,0,0-4.1051-9.8949L22.4813,2.5187A11.9944,11.9944,0,0,1,5.5568,19.5194l-.0381-.0381L4.1051,20.8949A13.9563,13.9563,0,0,0,14,25v3H10v2H20V28H16V24.84A14.0094,14.0094,0,0,0,28,11Z"/></svg>'
ICON_MAP = '<svg class="ci" viewBox="0 0 32 32" width="16" height="16" aria-hidden="true" focusable="false"><path d="M16,24l-6.09-8.6A8.14,8.14,0,0,1,16,2a8.08,8.08,0,0,1,8,8.13,8.2,8.2,0,0,1-1.8,5.13ZM16,4a6.07,6.07,0,0,0-6,6.13,6.19,6.19,0,0,0,1.49,4L16,20.52,20.63,14A6.24,6.24,0,0,0,22,10.13,6.07,6.07,0,0,0,16,4Z"/><circle cx="16" cy="9" r="2"/><path d="M28,12H26v2h2V28H4V14H6V12H4a2,2,0,0,0-2,2V28a2,2,0,0,0,2,2H28a2,2,0,0,0,2-2V14A2,2,0,0,0,28,12Z"/></svg>'
# Neutral button (also used by path slides, so it is added to the base CSS by build_dashboard.py).
GBTN_CSS = """.gbtn{display:inline-flex;align-items:center;gap:8px;min-height:48px;padding:0 16px;box-sizing:border-box;background:#6f6f6f;color:#ffffff!important;border:0;border-radius:0;font:400 14px/18px "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;text-decoration:none;cursor:pointer}
.gbtn:hover{background:#606060}.gbtn:active{background:#393939}.gbtn:focus-visible{outline:2px solid #ffffff;outline-offset:-4px}.gbtn[hidden]{display:none}.gbtn .ci{width:20px;height:20px;fill:currentColor;flex:none}.gbtn:disabled{cursor:progress}"""
# Phone trim (<=671 px), CSS only (no <details>, no script): rows past these counts get class "x"
# and are hidden on phones; a "more" row, whose count is computed here from the data, links to an
# anchor whose :target shows them again (storylines: "+N more" links to the storyline page).
BOARD_KEEP, CONN_KEEP, ZL_KEEP, SL_CARDS_KEEP, SL_KEEP = 2, 4, 5, 8, 5
PRINT_SL_ENTRIES = 2  # Director 2026-10-19 00:52 ET
# Carbon warning--filled (32, Apache-2.0; icons/warning--filled.svg). Spec "Follow-ups A": the non-colour cue before
# every "Critical". aria-hidden: the word (and the meter title) carry the meaning.
CRIT_PATH = "M16,2C8.3,2,2,8.3,2,16s6.3,14,14,14s14-6.3,14-14C30,8.3,23.7,2,16,2z M14.9,8h2.2v11h-2.2V8z M16,25c-0.8,0-1.5-0.7-1.5-1.5S15.2,22,16,22c0.8,0,1.5,0.7,1.5,1.5S16.8,25,16,25z"
ICON_CRIT = f'<svg class="critg" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><path d="{CRIT_PATH}"/></svg>'
def sev_word(sev, word=None):
    """Severity word with the critical glyph in front (only for critical)."""
    w = esc(word if word is not None else sev)
    return (ICON_CRIT + w) if sev == "critical" else w
CRIT_CSS = (".critg{display:inline-block;width:14px;height:14px;flex:none;vertical-align:-2px;margin:0 4px 0 6px;fill:var(--gia-sev-glyph)}"
            ".legend .critg,.meter .critg,.chip .critg{margin:0 3px 0 0}.meter .critg{margin-left:4px}"
            ".critg-svg{fill:var(--gia-sev-glyph);stroke:#0a1a2a;stroke-width:1px;paint-order:stroke}"
            "@media print{.critg,.critg-svg{fill:#141312!important;stroke:none}}")
def _slug(t): return "".join(c if c.isalnum() else "-" for c in t.lower()).strip("-")
def _more(href, n, label, pre="", cls="more ph"):
    """'[pre] N label': the number in Plex Mono with tabular figures, the words in Plex Sans."""
    p = f'<span class="ml">{esc(pre)}</span> ' if pre else ""
    return f'<a class="{cls}" href="{esc(href)}"><span class="mt">{p}<b class="mn">{n}</b> <span class="ml">{esc(label)}</span></span>{ICON_ARROW_DOWN}</a>'

fonts = UI.fonts   # r5: shared with history pages (ui_tokens.fonts)
FONTS = fonts()
# r4 (Director 04:24 item 3): no synthetic bold: UA bold (700) and bolder (900) map to the 600 face; zero specificity, so
# every author rule still wins
W600 = ":where(b,strong,h1,h2,h3,h4,h5,h6,th){font-weight:600}"
CSS = FONTS + W600 + """body{font-family:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}.meta,small,td.num,.cal td:first-child{font-variant-numeric:tabular-nums}
.maplink{position:relative}.mapopen{position:absolute;right:10px;bottom:10px;display:inline-flex;align-items:center;gap:8px;min-height:48px;padding:0 16px;background:#6f6f6f;color:#fff;font:400 14px/18px "IBM Plex Sans",system-ui,sans-serif}.mapopen .ci{width:20px;height:20px;fill:currentColor}
.leaflet-popup-content a{color:#161616;text-decoration-color:#6f6f6f}.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (min-width:672px){.row h3 a,.rcard li>a,.conn h3 a,.conn li>a,.zlinks a,.sltl li>a,.sltl h3 a,.chip,main .meta a,header .meta a,.cal a,.mkt a{display:inline-block;min-height:24px;line-height:20px;padding:2px 0;box-sizing:border-box}.chip{padding:2px 8px}}
@media print{.up{color:#005d5d}.down{color:#9f1853}.gbtn,.mapopen{display:none}}
.tsec{margin-top:6px}.empty{color:#7f8fa3;font-size:13px;padding:2px 0;margin:4px 0}.qrow{color:#7f8fa3;font-size:13px;margin:10px 0 0}
.rcard{background:#111821;border:1px solid #223041;border-radius:2px;padding:12px 14px;break-inside:avoid}.rcard h3{margin:0 0 8px;font-size:16px;color:#f3efe7;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.rcard ul{margin:4px 0 0;padding:0;list-style:none}.rcard li{font-size:13px;margin:0 0 6px}.rcard .gl{display:inline-block;width:14px;text-align:center;margin-right:4px}.rcard .where{color:#8f897e;font-size:12px}
.meter{display:inline-flex;gap:2px;align-items:center;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}.meter i{display:inline-block;width:6px;height:12px;background:#34312d}.meter b{margin-left:4px}
.boardgrid.rank>.rcard:first-child{grid-column:span 2}
.mkt td,.mkt th{font-variant-numeric:tabular-nums}.mkt td.num{text-align:right;white-space:nowrap;font-family:ui-monospace,Menlo,Consolas,monospace}.up{color:#08bdba}.down{color:#ee5396}.flat{color:#aaa398}
.conn{background:#111821;border:1px solid #223041;border-radius:2px;padding:12px 14px;margin-bottom:10px}.conn h3{margin:0 0 4px;font-size:14px;color:#f3efe7}
.cxg{margin:10px 0 0}.cxlab{margin:0 0 6px;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--gia-path)}.conn ul{margin:0;padding:0;list-style:none}.conn ol{margin:4px 0 0;padding-left:18px}.conn li{font-size:13px;margin:0;padding:8px 0;border-top:1px solid #1c2735}.conn li:first-child{border-top:0;padding-top:0}.zlinks{columns:2;padding-left:18px;font-size:13px}.zlinks li{break-inside:avoid;margin-bottom:4px}.judg{color:#c3a6ff}
.sltl{background:#111821;border:1px solid #223041;border-radius:2px;padding:10px 12px;break-inside:avoid}.sltl h3{margin:0 0 4px;font-size:14px}.sltl ol{margin:4px 0 0;padding-left:0;list-style:none;border-left:2px solid #c3a6ff55}.sltl li{margin:0 0 4px;padding-left:10px;font-size:12px}.sltl li.today{color:#f3efe7;font-weight:600}.sltl li.today:before{content:"● ";color:#c3a6ff}
.cal td:first-child{white-space:nowrap;color:#f3efe7;font-weight:600;width:190px;font-family:ui-monospace,Menlo,Consolas,monospace}
@media (max-width:671px){main{padding:0 16px 32px}header{padding:12px 16px}.boardgrid{grid-template-columns:1fr}.boardgrid.rank>.rcard:first-child{grid-column:auto}.zlinks{columns:1}.idx{columns:1}.two{grid-template-columns:1fr}
.mkt,.mkt tbody,.mkt tr,.mkt td,.cal,.cal tbody,.cal tr,.cal td{display:block;width:auto}.mkt tr:first-child{display:none}.mkt tr,.cal tr{border-bottom:1px solid #1f2a36;padding:6px 0}.mkt td,.cal td{border:0;padding:2px 0;text-align:left!important}
#gia-fallback svg:not(.ci):not(.critg){width:100%;height:auto}}
.more{display:flex;justify-content:space-between;align-items:center;gap:12px;width:100%;box-sizing:border-box;min-height:44px;margin:8px 0 0;padding:10px 0;border-top:1px solid #393939;color:var(--gia-link);text-decoration:none;font:600 14px/20px "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
.more.ph{display:none}.more .ml{font:inherit}.more .mn{font-family:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;font-variant-numeric:tabular-nums;font-weight:500}.more .ci{width:16px;height:16px;fill:currentColor;flex:none}
.sltl li.mrow{padding-left:0;list-style:none}.sltl li.mrow:before{content:none}
.maplink{display:block;text-decoration:none}.wmap{box-sizing:border-box;max-width:100%}.maplink:target{outline:none;background:none}
@page{size:letter portrait;margin:.5in}
@media print{#gia-fallback svg,.wmap{max-width:100%;height:auto}.boardgrid{grid-template-columns:1fr 1fr}.boardgrid.rank>.rcard:first-child{grid-column:span 2}main{max-width:none;padding:0}table{table-layout:fixed}td,th{overflow-wrap:anywhere}.zlinks{columns:1}}
@media (max-width:671px){.sltl{order:var(--o,0)}
main a,header a{display:inline-block;min-height:24px;min-width:24px;line-height:24px;vertical-align:top}
.row h3 a,.rcard li>a,.conn h3 a,.conn li>a,.zlinks a,.sltl li>a,.sltl h3 a,.chip{display:flex;align-items:center;min-height:44px;line-height:20px}
.chip{display:inline-flex;padding:0 12px;box-sizing:border-box}header .meta a,main>p.meta a{min-height:44px;min-width:44px;line-height:44px;text-align:center}.more{display:flex}.maplink{min-height:44px}
.x{display:none!important}.more.ph{display:block}:target .x{display:revert!important}:target>.more.ph,:target .more.ph.all{display:none}}"""

def load(root, name):
    p = os.path.join(root, "data", name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f) or []

def _sec(sid, anchor, title, body, note=""):
    return f'<section id="{sid}" class="tsec"><h2 id="{anchor}">{title}</h2>{body}</section>'

def _empty(text): return f'<div class="empty">{esc(text)}</div>'

def meter(sev):
    n = SEV_RANK.get(sev, 0); c = SEV_COL.get(sev, "#4a4640")
    bars = "".join(f'<i style="background:{c if k < n else "#34312d"}"></i>' for k in range(4))
    return (f'<span class="meter" title="Severity: {esc(sev)} ({n} of 4)">{bars}'
            f'{ICON_CRIT if sev == "critical" else ""}<b style="color:{"var(--gia-sev-critical-tx)" if sev == "critical" else c}">{esc(sev)}</b></span>')

def _short(t, n=72): return t if len(t) <= n else t[:n - 2].rsplit(" ", 1)[0] + "…"

# ---------- board: hotzones + today's stories ----------
def board(regions, latest, zones, lines, places_of, ddisp):
    cards, quiet = [], []
    for i, r in enumerate(regions):
        st = [s for s in latest if s.get("region") == r]
        if not st:                      # a card saying "nothing here" twice is dead grid; one line says it once
            quiet.append(r); continue
        ids = {s["id"] for s in st}
        zs = sorted([z for z in zones if ids & set(z.get("stories") or [])], key=lambda z: -SEV_RANK.get(z["severity"], 0))
        top = zs[0]["severity"] if zs else None
        lis = ""
        for k, s in enumerate(sorted(st, key=lambda s: s["date"], reverse=True)):
            pl = ", ".join(e["name"] for e in places_of(s)) or "Not pinned"
            sl = " · ".join(esc(lines[x]["name"]) for x in s.get("storylines") or [] if x in lines)
            g = GLYPH.get(s.get("marker"), "○")
            lis += (f'<li{" class=x" if k >= BOARD_KEEP else ""}><span class="gl" title="{esc(s.get("marker") or "")}">{g}</span><a href="history/trace-{esc(s["id"])}.html">{esc(_short(s["title"]))}</a>'
                    f' <span class="where">· {esc(pl)}{(" · " + sl) if sl else ""}</span></li>')
        zchips = "".join(f'<a class="chip" href="history/zone-{esc(z["id"])}.html">◉ {esc(z["name"])} · {sev_word(z["severity"])}</a>' for z in zs)
        head = meter(top) if top else '<span class="meta">no hot zone linked to today\'s stories</span>'
        rid = f"reg-{_slug(r)}"
        more = _more(f"#{rid}", len(st) - BOARD_KEEP, f"more in {r}") if len(st) > BOARD_KEEP else ""
        body = f'<ul>{lis}</ul>{more}' if lis else '<div class="meta">No stories this edition.</div>'
        cards.append(((-(SEV_RANK.get(top, 0)), -len(st), i),
                      f'<div class="rcard" id="{rid}" style="border-color:{SEV_COL.get(top, "#4a4640")}"><h3>{esc(r)} <small>({len(st)})</small> {head}</h3>{body}'
                      f'{("<div>" + zchips + "</div>") if zchips else ""}</div>'))
    cards.sort(key=lambda c: c[0])
    note = '<div class="meta">Regions ranked by the most severe hot zone that lists one of today\'s stories (then by story count). Severity is the hot zone\'s filed severity.</div>'
    grid = f'<div class="boardgrid rank">{"".join(c[1] for c in cards)}</div>' if cards else ""
    qrow = f'<p class="qrow">Nothing filed this edition: {", ".join(esc(q) for q in quiet)}.</p>' if quiet else ""
    body = (grid + qrow) if latest else _empty("No stories filed for this edition.")
    return _sec("sec-board", "board", "Regional situation board", body, note)

# ---------- markets: data/markets.json ----------
def _asof(v):
    if len(v) == 10:
        return f"{int(v[8:10])} {MON[int(v[5:7]) - 1]}"
    return f"{int(v[8:10])} {MON[int(v[5:7]) - 1]}, {v[11:16]} {v[16:].replace('Z', 'UTC') or ''}".strip()

def _num(x):
    """As filed: no added or dropped precision (repr), thousands separators only on the integer part."""
    t = repr(float(x)) if isinstance(x, float) else str(x)
    if t.endswith(".0"): t = t[:-2]
    if "e" in t: return f"{x:g}"
    i, _, f = t.partition("."); i = f"{int(i):,}" if i not in ("-0",) else i
    return i + ("." + f if f else "")

def _move(m):
    if "change" not in m:
        return '<span class="flat">n/a</span>'
    c = m["change"]; u = {"%": "%", "bp": " bp", "abs": ""}[m.get("change_unit", "abs")]
    cls, ar = ("up", "▲") if c > 0 else ("down", "▼") if c < 0 else ("flat", "■")
    sign = "+" if c > 0 else "−" if c < 0 else "±"
    word = {"up": "up", "down": "down", "flat": "unchanged"}[cls]
    return f'<span class="{cls}"><span aria-hidden="true">{ar}</span> {sign}{_num(abs(c))}{u}<span class="sr"> {word}</span></span>'

def markets(items, edition, stories):
    latest = {}
    for m in items:
        if str(m.get("as_of", ""))[:10] <= edition and (m["asset"] not in latest or m["as_of"] > latest[m["asset"]]["as_of"]):
            latest[m["asset"]] = m
    if not latest:
        return _sec("sec-markets", "markets", "Markets &amp; commodities", _empty("No market data filed for this edition."))
    rows = ""
    for m in sorted(latest.values(), key=lambda m: m["asset"]):
        rel = " · ".join(f'<a href="history/trace-{esc(i)}.html">{esc(_short(stories[i]["title"], 48))}</a>' for i in m.get("stories") or [] if i in stories)
        src = m["source"]
        rows += (f'<tr><td>{esc(m["label"])}</td><td class="num">{_num(m["value"])} <small>{esc(m["unit"])}</small></td><td class="num">{_move(m)}</td>'
                 f'<td><span class="meta">{esc(_asof(m["as_of"]))}{(" · " + esc(m["basis"])) if m.get("basis") else ""}</span></td>'
                 f'<td>{esc(m.get("note", ""))} <a href="{esc(src["url"])}" rel="noopener">{esc(src["name"])}</a>{("<div class=meta>" + rel + "</div>") if rel else ""}</td></tr>')
    t = f'<table class="mkt"><tr><th>Instrument</th><th>Value</th><th>Move</th><th>As of</th><th>Context · source</th></tr>{rows}</table>'
    return _sec("sec-markets", "markets", "Markets &amp; commodities", t + '<div class="meta">Latest filed figure per instrument, as reported by the cited source; not live quotes. <a href="history/markets.html">All figures</a></div>')

# ---------- connections: today's causes/effects + hotzone links ----------
def connect(latest, by_id, zone_links, zones_by_id, ddisp):
    today = {s["id"] for s in latest}
    cards, n_cards, n_conn = "", 0, 0
    for s in sorted(latest, key=lambda s: s["date"], reverse=True):
        cz = [c for c in s.get("causes") or [] if c["story"] in by_id]
        ef = [e for e in s.get("effects") or [] if e["story"] in by_id]
        if not cz and not ef:
            continue
        # Causes and effects are opposite directions; one numbered list mixing them reads as a
        # sequence it is not. Each direction gets its own labelled group instead.
        czli = "".join(f'<li><a href="history/trace-{esc(c["story"])}.html">{esc(_short(by_id[c["story"]]["title"], 80))}</a> <span class="meta">{ddisp(by_id[c["story"]])}</span>'
                       f'<div class="an"><span class="conf {esc(c["confidence"])}">{esc(c["confidence"])}</span>{esc(c["why"])}</div></li>' for c in cz)
        efli = "".join(f'<li><a href="history/trace-{esc(e["story"])}.html">{esc(_short(by_id[e["story"]]["title"], 80))}</a> <span class="meta">{ddisp(by_id[e["story"]])}</span>'
                       f'<div class="an"><span class="conf {esc(e["confidence"])}">{esc(e["confidence"])}</span>{esc(e["why"])}</div></li>' for e in ef)
        li = (f'<div class="cxg"><p class="cxlab">What led to this</p><ul>{czli}</ul></div>' if czli else "")
        li += (f'<div class="cxg"><p class="cxlab">What this led to</p><ul>{efli}</ul></div>' if efli else "")
        n_conn += len(cz) + len(ef)
        cards += f'<div class="conn{" x" if n_cards >= CONN_KEEP else ""}"><h3><a href="history/trace-{esc(s["id"])}.html">{esc(s["title"])}</a></h3>{li}</div>'
        n_cards += 1
    zl = sorted(zone_links, key=lambda l: (not (today & set(l.get("stories") or [])), l["id"]))
    zl = [l for l in zl if l["from"] in zones_by_id and l["to"] in zones_by_id]
    zli = "".join(f'<li{" class=x" if k >= ZL_KEEP else ""}><a href="history/link-{esc(l["id"])}.html">{esc(zones_by_id[l["from"]]["name"])} → {esc(zones_by_id[l["to"]]["name"])}</a>: {esc(l["label"])}'
                  f'{" <small>· today</small>" if today & set(l.get("stories") or []) else ""}</li>' for k, l in enumerate(zl))
    body = (cards or _empty("No causal links recorded for today's stories."))
    body += '<h3 class="meta" style="margin:12px 0 4px">Hot-zone links</h3>' + (f'<ul class="zlinks">{zli}</ul>' if zli else _empty("No hot-zone links filed."))
    total = n_conn + len(zl)
    if n_cards > CONN_KEEP or len(zl) > ZL_KEEP:   # phone: one row reveals the whole section via :target
        body += _more("#sec-connect", total, "connections", pre="All", cls="more ph all")
    note = '<div class="meta">Analytic causal links (judgment, labelled by confidence) between sourced stories, then the analytic links between hot zones.</div>'
    return _sec("sec-connect", "connect", "How today's events connect", body, note)

# ---------- storylines: data/storylines.json ----------
def storylines(lines, all_stories, edition, ddisp, keep=5, zones=()):
    cards = []
    for l in lines:
        st = sorted([s for s in all_stories if l["id"] in (s.get("storylines") or []) or s["id"] in l.get("stories", [])], key=lambda s: (s["date"], s["id"]))
        tids = {s["id"] for s in st if (s.get("edition") or s["date"]) == edition}
        n_today = len(tids)
        if not n_today:
            continue
        sev = max((SEV_RANK.get(z["severity"], 0) for z in zones if tids & set(z.get("stories") or [])), default=0)
        last = st[-1]["date"]
        shown = st[-keep:]
        # print shows each storyline's 2 latest entries (Director 00:52): older shown entries carry class pe (print-hidden)
        lis = "".join(f'<li class="{" ".join(c for c in ("today" if (s.get("edition") or s["date"]) == edition else "", "pe" if k < len(shown) - PRINT_SL_ENTRIES else "") if c)}"><span class="meta">{ddisp(s)}</span> <a href="history/trace-{esc(s["id"])}.html">{esc(_short(s["title"], 84))}</a></li>' for k, s in enumerate(shown))
        extra = len(st) - min(keep, len(st))
        plus = (f'<li class="mrow">' + _more(f"history/storyline-{l['id']}.html", f"+{extra}", "more", cls="more") + '</li>' if extra else "")
        cards.append((-n_today, l["name"].lower(), f'<div class="sltl" data-sev="{sev}" data-last="{esc(last)}"><h3><a href="history/storyline-{esc(l["id"])}.html">⟿ {esc(l["name"])}</a> <small>{n_today} today · {len(st)} total</small></h3><ol>{lis}{plus}</ol></div>'))
    cards.sort()
    # DOM order stays (today's count, name) so desktop and print are unchanged; phones reorder with CSS
    # `order` by severity, then latest entry, and show the top SL_CARDS_KEEP (rest: class x).
    phone = sorted(range(len(cards)), key=lambda k: (-int(re.search(r'data-sev="(\d)"', cards[k][2]).group(1)),
                                                      tuple(-ord(c) for c in re.search(r'data-last="([^"]*)"', cards[k][2]).group(1)), k))
    rank = {k: r for r, k in enumerate(phone)}
    cards = [(a, b, h.replace('<div class="sltl"', f'<div class="sltl{" x" if rank[k] >= SL_CARDS_KEEP else ""}" style="--o:{rank[k]}"', 1)) for k, (a, b, h) in enumerate(cards)]
    body = f'<div class="boardgrid">{"".join(c[2] for c in cards)}</div>' if cards else _empty("No storyline has a story in this edition.")
    if len(cards) > SL_CARDS_KEEP:
        body += _more("#sec-storylines", len(cards), "active storylines", pre="All", cls="more ph all")
    return _sec("sec-storylines", "storylines", "Active storylines: running timeline", body,
                '<div class="meta">Storylines with at least one story in this edition; last five entries each, today\'s in bold.<span class="po"> In print: the 2 latest entries each.</span></div>')

# ---------- calendar: data/calendar.json ----------
def _d(s): return _dt.date(int(s[:4]), int(s[5:7]), int(s[8:10]))
def _tz(t): return {"America/New_York": "ET", "UTC": "UTC", "Etc/UTC": "UTC"}.get(t, t)

def cal_span(c):
    """(first day, last day) of the item's period."""
    p, d = c.get("date_precision", "day"), c["date"]
    if p == "year": return _dt.date(int(d), 1, 1), _dt.date(int(d), 12, 31)
    if p == "month":
        y, m = int(d[:4]), int(d[5:7]); nxt = _dt.date(y + (m == 12), m % 12 + 1, 1)
        return _dt.date(y, m, 1), nxt - _dt.timedelta(days=1)
    if p == "quarter":
        y, q = int(d[:4]), int(d[6]); a = _dt.date(y, 3 * q - 2, 1)
        nxt = _dt.date(y + (q == 4), (3 * q) % 12 + 1, 1)
        return a, nxt - _dt.timedelta(days=1)
    if p == "range": return _d(d), _d(c["end"])
    return _d(d), _d(d)

def cal_label(c):
    p, d = c.get("date_precision", "day"), c["date"]
    if p == "year": return d
    if p == "month": return f"{MON[int(d[5:7]) - 1]} {d[:4]}"
    if p == "quarter": return f"Q{d[6]} {d[:4]}"
    a, b = cal_span(c)
    if p == "range":
        if a.month == b.month and a.year == b.year: return f"{MON[a.month - 1]} {a.day}–{b.day}"
        return f"{MON[a.month - 1]} {a.day} – {MON[b.month - 1]} {b.day}"
    lab = f"{a.strftime('%a')} {MON[a.month - 1]} {a.day}"
    if c.get("time"):
        hh, mm = int(c["time"][:2]), c["time"][3:]
        lab += f", {hh % 12 or 12}{(':' + mm) if mm != '00' else ''} {'AM' if hh < 12 else 'PM'} {_tz(c.get('tz', ''))}"
    return lab

def calendar(items, edition, stories, limit=12):
    if edition:
        today = _d(edition)
        up = [c for c in items if cal_span(c)[1] >= today]
    else:
        up = []
    up.sort(key=lambda c: (cal_span(c)[0], {"day": 0, "range": 1, "month": 2, "quarter": 3, "year": 4}.get(c.get("date_precision", "day"), 5), c["id"]))
    if not up:
        return _sec("sec-calendar", "calendar", "Upcoming calendar", _empty("No upcoming calendar items filed."))
    rows = ""
    for c in up[:limit]:
        src = " · ".join(f'<a href="{esc(s["url"])}" rel="noopener">{esc(s["name"])}</a>' for s in c.get("sources") or [])
        rel = " · ".join(f'<a href="history/trace-{esc(i)}.html">{esc(_short(stories[i]["title"], 48))}</a>' for i in c.get("stories") or [] if i in stories)
        rows += (f'<tr><td>{esc(cal_label(c))}</td><td><b>{esc(c["title"])}</b>{(" <small>· " + esc(c["region"]) + "</small>") if c.get("region") else ""}'
                 f'{("<div>" + esc(c["note"]) + "</div>") if c.get("note") else ""}<div class="meta">{src}{(" · " + rel) if rel else ""}</div></td></tr>')
    more = f'<div class="meta">{len(up) - limit} more upcoming item(s) not shown.</div>' if len(up) > limit else ""
    return _sec("sec-calendar", "calendar", "Upcoming calendar", f'<table class="cal">{rows}</table>{more}')

def sections(root, *, regions, latest, all_stories, by_id, zones, zone_links, lines, edition, places_of, ddisp):
    zbi = {z["id"]: z for z in zones}; lbi = {l["id"]: l for l in lines}
    return {
        "board": board(regions, latest, zones, lbi, places_of, ddisp),
        "markets": markets(load(root, "markets.json"), edition, by_id),
        "connect": connect(latest, by_id, zone_links, zbi, ddisp),
        "storylines": storylines(lines, all_stories, edition, ddisp, zones=zones),
        "calendar": calendar(load(root, "calendar.json"), edition, by_id),
    }

# ---------- print sheet (Director 2026-10-19 00:32 ET; Designer's paper set, studio/hifi/tokens.css @media print) ----------
# Letter portrait, 0.5 in margins, light palette, no navigation chrome. Director 00:52 ET (final): the phone trims never
# reach print. Print shows every board row, every connection and every active storyline (its 2 latest entries);
# it hides the full story list (#sec-stories) and the 'more' rows.
PRINT_CSS = """@media print{
html,body{background:#fff!important;color:#2a2826;font:400 9.5pt/13.5pt "IBM Plex Sans",system-ui,sans-serif}
header{background:none!important;border-bottom:.6pt solid #d9d4cb;padding:0 0 4pt}header .meta{color:#54504a}
header .gbtn,header div:has(>.gbtn),.gbtn,.mapopen,.pathbtn,.more,#gia-map-open,#gia-leaflet{display:none!important}
h1{color:#141312;font-size:15pt}h1 b{color:var(--gia-accent-ui-print)}
h2{color:#141312;border-left:2pt solid #141312;font-size:9pt;margin:8pt 0 3pt;break-after:avoid}
a{color:#141312!important;text-decoration:none}.meta,small{color:#54504a!important;font-size:7.5pt;line-height:10pt}h2+.meta{break-after:avoid}
main{padding:0!important}
main a,header a,.row h3 a,.rcard li>a,.conn h3 a,.conn li>a,.zlinks a,.sltl li>a,.sltl h3 a{display:inline!important;min-height:0!important;min-width:0!important;line-height:inherit!important;padding:0!important}
.chip{display:inline-block!important;min-height:0!important;line-height:inherit!important}
main a.more,main li.mrow,main a.gbtn,header a.gbtn,main .mapopen{display:none!important}
.rcard,.conn,.sltl,.card,.panel{background:#fff!important;border-color:#d9d4cb!important;padding:4pt 6pt!important}
.rcard h3,.conn h3,.sltl h3,.row h3{color:#141312!important;font-size:9.5pt!important;margin:0 0 2pt!important}
.rcard li,.conn li,.sltl li,.zlinks{font-size:8pt!important;line-height:10.5pt!important;margin:0 0 2pt!important}
.rcard .where{color:#54504a!important;font-size:7.5pt}
.chip{background:#f5f3ef!important;color:#141312!important;border:.6pt solid #d9d4cb;font-size:6.8pt;padding:0 4pt!important;margin:1pt 2pt 0 0}
.meter i{background:transparent!important;border:.7pt solid #141312;width:3pt;height:8pt;box-sizing:border-box}
.meter i:not([style*="#34312d"]){background:#141312!important}.meter b{color:#141312!important}
.judg{color:#6929c4!important}.conn{border-left:2pt solid #6929c4!important}
.likely{background:#e5f6ea!important;color:#0e6027!important}.possible{background:#fcf0e0!important;color:#8a3800!important}.speculative{background:#fbeaf3!important;color:#9f1853!important}
.sltl ol{border-left-color:#c9b6ef!important}.sltl li.today{color:#141312!important}.sltl li.today:before{color:#6929c4}
td,th{border-bottom:.6pt solid #d9d4cb!important;padding:2pt 3pt!important;font-size:7.4pt}
/* board: 3 CSS columns, cards may split across a page so the board starts on p1 under the map (no p1 gap) */
.boardgrid{display:block!important;columns:3;column-gap:5pt}.boardgrid>.rcard{display:block;break-inside:auto!important;margin:0 0 5pt}.rcard h3{break-after:avoid}.rcard li{break-inside:avoid}
.tsec,#sec-connect>div,#sec-storylines>div{gap:4pt}
#sec-connect .tsec,#sec-storylines .tsec{display:grid;grid-template-columns:1fr 1fr;gap:4pt;align-items:start}
.conn{margin:0!important}.zlinks{columns:2!important}
#sec-stories,main>p.meta,.sltl li.pe,.more{display:none!important}.x{display:revert!important}.po{display:inline!important}
.legend{margin:3pt 0;font-size:7pt}.legend b{color:#54504a!important}.legend span{font-size:7pt;margin-right:8pt}
.wmap{border-color:#d9d4cb!important}
.wmap .sea{fill:#f3f1ec}.wmap .land{fill:#dcd7cd;stroke:#b8b1a5}.wmap .lk{stroke:#6929c4}
.wmap .zl,.wmap .pl{fill:#141312!important;stroke:#f3f1ec!important}.wmap .prl .zl{font-size:PRINT_NS_PXpx!important}.wmap .prl line.ldr,.wmap .prl line.ldr-tuck{stroke:PRINT_LEADER!important;stroke-width:1.5px!important;vector-effect:non-scaling-stroke}.wmap .ls{stroke:#ffffff!important;stroke-width:PRINT_HALO_SW!important;stroke-linejoin:round;paint-order:stroke;vector-effect:non-scaling-stroke}
.wmap .ls-critical{fill:var(--gia-sev-critical-print)}.wmap .ls-high{fill:var(--gia-sev-high-print)}.wmap .ls-elevated{fill:var(--gia-sev-elevated-print)}.wmap .ls-watch{fill:var(--gia-sev-watch-print)}
/* r3 print key (QA round 4 nit 1/2): key swatches and map halos use the PRINT severity tokens; HTML level words >= 10.5pt */
.legend i.sw-critical{background:var(--gia-sev-critical-print)!important}.legend i.sw-high{background:var(--gia-sev-high-print)!important}
.legend i.sw-elevated{background:var(--gia-sev-elevated-print)!important}.legend i.sw-watch{background:var(--gia-sev-watch-print)!important}
.wmap .hz-critical{fill:var(--gia-sev-critical-print);stroke:var(--gia-sev-critical-print)}.wmap .hz-high{fill:var(--gia-sev-high-print);stroke:var(--gia-sev-high-print)}
.wmap .hz-elevated{fill:var(--gia-sev-elevated-print);stroke:var(--gia-sev-elevated-print)}.wmap .hz-watch{fill:var(--gia-sev-watch-print);stroke:var(--gia-sev-watch-print)}
.legend.hzk span,.legend.nlab .pr-only,.meter b{font-size:10.5pt!important}
/* r4 (Director 04:24 item 2; QA round 5 §6): numbered key row at 10.5pt; map halos at full strength (solid print-token ring,
   no 12% wash); light page + dark text even with background graphics on; key swatches always print */
.legend.nlab,.legend.nlab span,.legend.nlab>b{font-size:10.5pt!important;line-height:14pt}.legend.nlab b.nmk{width:14pt;height:14pt;font-size:9pt!important}
.wmap .hz{opacity:1!important;fill:none!important;stroke-opacity:1!important;stroke-width:2.5px!important}
html,body,main,header,section{background:#fff!important}
.legend i,.meter i{-webkit-print-color-adjust:exact;print-color-adjust:exact}

.critg-svg{stroke:none}
.empty{color:#54504a;border-color:#d9d4cb}
}
"""
PRINT_CSS = PRINT_CSS.replace("PRINT_HALO_SW", f"{2 * UI.PRINT_HALO_PX}px").replace("PRINT_LEADER", UI.PRINT_LEADER).replace("PRINT_NS_PX", f"{UI.PRINT_NS_UNITS:g}")   # r5: visible halo = half the stroke
CSS += ".po{display:none}" + PRINT_CSS
