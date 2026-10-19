"""Static pages for the optional v7 data files (Markets, Reports library, Assessment log).
Each page is complete HTML without JS, has a viewport meta tag and a single-column layout
below 720 px. A missing or empty data file writes no page and returns no index link, so a
corpus without v7 sections builds byte-for-byte as before."""
import html, json, os
from .md import render
from .ui_tokens import PRINT_FORCE_LIGHT as _PFL, UPRIGHT_CSS as _UPR, fonts as _fonts

esc = lambda s: html.escape(str(s), quote=True)
CSS = """:root{--bg:#0b0f14;--fg:#f3efe7;--mute:#a8a8a8;--line:#223041;--acc:#f3efe7;--ok:#42be65;--no:#ff832b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
header,main{max-width:860px;margin:0 auto;padding:16px}header h1{font-size:1.4rem;margin:.2em 0}header .meta{color:var(--mute);font-size:.9rem}
a{color:var(--acc);text-decoration:underline;text-decoration-color:#8d8d8d;text-underline-offset:3px;text-decoration-thickness:1px}a:hover{color:#f4f4f4;text-decoration-color:#f4f4f4;text-decoration-thickness:2px}h2{font-size:1.15rem;border-bottom:1px solid var(--line);padding-bottom:4px;margin-top:1.6em}h3{font-size:1rem}
.card{border:1px solid var(--line);border-radius:2px;padding:12px 14px;margin:12px 0}.k{color:var(--mute);font-size:.85rem}
.chip{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:2px 4px 2px 0;font-size:.85rem;min-height:28px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:600;font-size:.85rem}.num{text-align:right}.st-accepted{color:var(--ok)}.st-rejected{color:var(--no)}
blockquote{border-left:1px solid var(--line);margin:0;padding:0 12px;color:var(--mute)}code{background:#111821;padding:0 4px;border-radius:3px}
del{color:var(--mute)}ins{text-decoration:none;color:var(--fg);background:#22301f}
@media (max-width:720px){body{font-size:17px}table,thead,tbody,tr,th,td{display:block}thead{display:none}tr{border-bottom:1px solid var(--line);padding:6px 0}td{border:0;padding:2px 0}td[data-k]::before{content:attr(data-k) ": ";color:var(--mute)}.num{text-align:left}}
@page{size:letter portrait}@media print{body{background:#fff;color:#000}a{color:#000}}"""

def _page(title, sub, body, back="index.html", home="../dashboard.html"):
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}: GIA</title><style>{CSS}{_fonts(home[:-len("dashboard.html")])}body{{font-family:"IBM Plex Sans",Arial,Helvetica,sans-serif}}{_UPR}{_PFL}</style></head><body><header><h1>{esc(title)}</h1>'
            f'<div class="meta">{sub} · <a href="{back}">← Archive</a> · <a href="{home}">Dashboard</a></div></header><main>{body}</main></body></html>\n')

def _load(root, name):
    p = os.path.join(root, "data", name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f) or []

def _story_chips(ids, stories, pre=""):
    return "".join(f'<a class="chip" href="{pre}trace-{esc(i)}.html">{esc(stories[i]["title"])}</a>' for i in ids or [] if i in stories)

def _line_chips(ids, lines, pre=""):
    return "".join(f'<a class="chip" href="{pre}storyline-{esc(i)}.html">⟿ {esc(lines[i]["name"])}</a>' for i in ids or [] if i in lines)

def _sources(srcs):
    return ", ".join(f'<a href="{esc(s["url"])}" rel="noopener noreferrer">{esc(s["name"])}</a>' for s in srcs or [])

def write_reports(root, hd, stories, lines):
    reports = _load(root, "reports.json")
    if not reports:
        return ""
    os.makedirs(os.path.join(hd, "reports"), exist_ok=True)
    rows = []
    for r in sorted(reports, key=lambda r: (r["date"], r["id"]), reverse=True):
        body = render(r["body"], story_href=lambda i: f"../trace-{i}.html", storyline_href=lambda i: f"../storyline-{i}.html")
        meta = f'{esc(r["date"])} · {esc(r["author"])} · filed in edition {esc(r.get("edition", ""))}'
        extra = ""
        if r.get("stories"): extra += f'<h2>Stories</h2><div>{_story_chips(r["stories"], stories, "../")}</div>'
        if r.get("storylines"): extra += f'<h2>Storylines</h2><div>{_line_chips(r["storylines"], lines, "../")}</div>'
        if r.get("sources"): extra += f'<h2>Sources</h2><p>{_sources(r["sources"])}</p>'
        with open(os.path.join(hd, "reports", f'{r["id"]}.html'), "w", encoding="utf-8") as f:
            f.write(_page(r["title"], meta, f'<article>{body}</article>{extra}', back="index.html", home="../../dashboard.html"))
        rows.append(f'<div class="card"><a href="{esc(r["id"])}.html"><b>{esc(r["title"])}</b></a><div class="k">{meta}</div></div>')
    with open(os.path.join(hd, "reports", "index.html"), "w", encoding="utf-8") as f:
        f.write(_page("Reports library", f"{len(reports)} reports, newest first", "".join(rows), back="../index.html", home="../../dashboard.html"))
    return f'<h2>Reports</h2><ul class="idx"><li><a href="reports/index.html">Reports library</a> <small>{len(reports)}</small></li></ul>'

def write_assessment_log(root, hd, stories, lines):
    log = _load(root, "assessment_log.json")
    if not log:
        return ""
    by = {c["id"]: c for c in log}
    later = {c["supersedes"]: c["id"] for c in log if c.get("supersedes")}
    cards = []
    for c in reversed(log):  # newest filing first; file order is filing order
        st = c["status"]
        bits = [f'<span class="st-{st}"><b>{esc(st)}</b></span>', esc(c["date"]), esc(c.get("scope", "story")),
                f'raised by {esc(c["raised_by"])}' if c.get("raised_by") else "", f'by {esc(c["author"])}']
        conf = (f'<div><span class="k">Confidence</span> {esc(c["confidence_from"])} → <b>{esc(c["confidence_to"])}</b></div>'
                if "confidence_from" in c else "")
        words = ""
        if c.get("wording_from") or c.get("wording_to"):
            words = ('<div><span class="k">Wording</span> ' + (f'<del>{esc(c["wording_from"])}</del> ' if c.get("wording_from") else "")
                     + (f'→ <ins>{esc(c["wording_to"])}</ins>' if c.get("wording_to") else "") + "</div>")
        links = ""
        if c.get("supersedes") in by: links += f'<div class="k">Supersedes <a href="#{esc(c["supersedes"])}">{esc(c["supersedes"])}</a></div>'
        if c["id"] in later: links += f'<div class="k">Superseded by <a href="#{esc(later[c["id"]])}">{esc(later[c["id"]])}</a></div>'
        if c.get("revision_edition"): links += f'<div class="k">Change filed in edition {esc(c["revision_edition"])}</div>'
        cards.append(f'<div class="card" id="{esc(c["id"])}"><div class="k">{" · ".join(b for b in bits if b)} · <code>{esc(c["id"])}</code></div>'
                     f'<h3>{esc(c["title"])}</h3><p>{esc(c["reason"])}</p>{conf}{words}<div>{_story_chips(c.get("stories"), stories)}{_line_chips(c.get("storylines"), lines)}</div>'
                     f'{"<div class=k>Sources: " + _sources(c["sources"]) + "</div>" if c.get("sources") else ""}{links}</div>')
    acc = sum(c["status"] == "accepted" for c in log)
    with open(os.path.join(hd, "assessment-log.html"), "w", encoding="utf-8") as f:
        f.write(_page("Assessment log", f"Red Team review: {acc} accepted, {len(log) - acc} rejected · append-only", "".join(cards)))
    return f'<h2>Assessment log</h2><ul class="idx"><li><a href="assessment-log.html">Red Team assessment log</a> <small>{len(log)}</small></li></ul>'

def write_markets(root, hd, stories):
    figs = _load(root, "markets.json")
    if not figs:
        return ""
    latest = {}
    for m in figs:  # file is sorted by (as_of, id); last wins
        latest[m["asset"]] = m
    def chg(m):
        if "change" not in m: return ""
        u = {"%": "%", "bp": " bp", "abs": ""}[m["change_unit"]]
        return f'{m["change"]:+g}{u}'
    rows = "".join(
        f'<tr><td data-k="Asset">{esc(m["label"])}</td><td class="num" data-k="Level">{m["value"]:g} <span class="k">{esc(m["unit"])}</span></td>'
        f'<td class="num" data-k="Move">{esc(chg(m))}</td><td data-k="As of">{esc(m["as_of"])}{" · " + esc(m["basis"]) if m.get("basis") else ""}</td>'
        f'<td data-k="Context">{esc(m.get("note", ""))} {_story_chips(m.get("stories"), stories)}</td>'
        f'<td data-k="Source"><a href="{esc(m["source"]["url"])}" rel="noopener noreferrer">{esc(m["source"]["name"])}</a></td></tr>'
        for m in sorted(latest.values(), key=lambda m: m["label"]))
    table = f'<table><thead><tr><th>Asset</th><th class="num">Level</th><th class="num">Move</th><th>As of</th><th>Context</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>'
    with open(os.path.join(hd, "markets.html"), "w", encoding="utf-8") as f:
        f.write(_page("Markets", f"Latest filed figure per asset ({len(latest)} assets, {len(figs)} figures on file)", table))
    return f'<h2>Markets</h2><ul class="idx"><li><a href="markets.html">Markets and commodities</a> <small>{len(latest)}</small></li></ul>'

def write_all(root, hd, stories, lines):
    """Returns extra archive-index HTML ('' when no v7 files exist)."""
    return write_markets(root, hd, stories) + write_reports(root, hd, stories, lines) + write_assessment_log(root, hd, stories, lines)
