"""Safe-subset Markdown -> HTML for report bodies (rendered at build time; no JS needed).

Supported: ATX headings (#..####, shifted down one level so the report title stays the page h1),
paragraphs, `-`/`*`/`1.` lists (one level), `>` blockquotes, `---` rules, **bold**, *italic*,
`code`, and links whose target is http(s), #anchor, story:<id> or storyline:<id>.
Everything else is text: input is HTML-escaped before any markup is added, so raw HTML,
images and javascript: links cannot reach the page even if apply's validator were bypassed.
"""
import html, re

LINK = re.compile(r"\[([^\]\n]*)\]\(([^)\s]+)\)")
CODE = re.compile(r"`([^`\n]+)`")
BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
ITAL = re.compile(r"(?<![\*\w])\*(?=\S)(.+?)(?<=\S)\*(?![\*\w])")

def _href(target, story_href, storyline_href):
    if target.startswith(("https://", "http://")):
        return target, True
    if target.startswith("#") and re.fullmatch(r"#[A-Za-z0-9_-]+", target):
        return target, False
    if target.startswith("story:"):
        return story_href(target[6:]), False
    if target.startswith("storyline:"):
        return storyline_href(target[10:]), False
    return None, False

def inline(text, story_href, storyline_href):
    """`text` is raw Markdown; returns safe HTML."""
    out, pos = [], 0
    for m in LINK.finditer(text):
        out.append(_fmt(html.escape(text[pos:m.start()], quote=False)))
        href, external = _href(m.group(2), story_href, storyline_href)
        label = _fmt(html.escape(m.group(1), quote=False))
        if href is None:
            out.append(label)
        else:
            rel = ' rel="noopener noreferrer"' if external else ""
            out.append(f'<a href="{html.escape(href, quote=True)}"{rel}>{label}</a>')
        pos = m.end()
    out.append(_fmt(html.escape(text[pos:], quote=False)))
    return "".join(out)

def _fmt(escaped):
    codes = []
    def keep(m):
        codes.append(m.group(1)); return f"\x00{len(codes) - 1}\x00"
    s = CODE.sub(keep, escaped)
    s = BOLD.sub(r"<strong>\1</strong>", s)
    s = ITAL.sub(r"<em>\1</em>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", s)

def render(body, story_href=lambda i: f"trace-{i}.html", storyline_href=lambda i: f"storyline-{i}.html"):
    lines = (body or "").replace("\r\n", "\n").split("\n")
    out, para, i = [], [], 0
    il = lambda t: inline(t, story_href, storyline_href)
    def flush():
        if para:
            out.append("<p>" + il(" ".join(x.strip() for x in para)) + "</p>"); para.clear()
    while i < len(lines):
        line = lines[i]; s = line.strip()
        if not s:
            flush(); i += 1; continue
        m = re.match(r"^(#{1,4})\s+(.*?)\s*#*$", s)
        if m:
            flush(); lvl = min(len(m.group(1)) + 1, 5)
            out.append(f"<h{lvl}>{il(m.group(2))}</h{lvl}>"); i += 1; continue
        if re.fullmatch(r"(?:-\s*){3,}|(?:\*\s*){3,}", s):
            flush(); out.append("<hr>"); i += 1; continue
        if s.startswith(">"):
            flush(); quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip()); i += 1
            out.append("<blockquote>" + render("\n".join(quote), story_href, storyline_href) + "</blockquote>"); continue
        ul, ol = re.match(r"^[-*]\s+(.*)", s), re.match(r"^\d+[.)]\s+(.*)", s)
        if ul or ol:
            flush(); tag = "ul" if ul else "ol"; pat = r"^[-*]\s+(.*)" if ul else r"^\d+[.)]\s+(.*)"; items = []
            while i < len(lines):
                t = lines[i].strip(); mm = re.match(pat, t)
                if mm:
                    items.append(mm.group(1))
                elif t and items and lines[i].startswith((" ", "\t")):
                    items[-1] += " " + t  # continuation line
                else:
                    break
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{il(x)}</li>" for x in items) + f"</{tag}>"); continue
        para.append(line); i += 1
    flush()
    return "\n".join(out)
