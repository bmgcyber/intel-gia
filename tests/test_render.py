import glob, json, math, os, re, shutil, subprocess, sys, tempfile, unittest
from datetime import date, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gia_build.md import render
from apply_packet import apply_all

class MarkdownSubsetTests(unittest.TestCase):
    def test_structure(self):
        out = render("# T\n\npara **b** *i* `c`\n\n- a\n- b\n\n1. x\n2. y\n\n> q\n\n---")
        for frag in ("<h2>T</h2>", "<strong>b</strong>", "<em>i</em>", "<code>c</code>", "<ul><li>a</li><li>b</li></ul>",
                     "<ol><li>x</li><li>y</li></ol>", "<blockquote><p>q</p></blockquote>", "<hr>"):
            self.assertIn(frag, out)

    def test_links(self):
        out = render("[s](story:abc) [l](storyline:xyz) [w](https://e.com/a?b=1&c=2) [h](#top)")
        self.assertIn('<a href="trace-abc.html">s</a>', out)
        self.assertIn('<a href="storyline-xyz.html">l</a>', out)
        self.assertIn('<a href="https://e.com/a?b=1&amp;c=2" rel="noopener noreferrer">w</a>', out)
        self.assertIn('<a href="#top">h</a>', out)

    def test_hostile_input_is_inert(self):
        for body in ("<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "[x](javascript:alert(1))",
                     "![i](https://e.com/i.png)", '[x](https://e.com/" onmouseover="alert(1))', "**<b>x</b>**", "[x](data:text/html,hi)"):
            with self.subTest(body=body):
                out = render(body)
                self.assertNotRegex(out, r"<(script|img|iframe)")
                for href in re.findall(r'href="([^"]*)"', out):
                    self.assertTrue(href.startswith(("https://", "http://", "#", "trace-", "storyline-")), href)
                self.assertNotRegex(out, r"<[a-z]+[^>]*\son[a-z]+=")

class V7PagesBuildTest(unittest.TestCase):
    """Real corpus copy + one packet with markets, a report and the 10-18 assessment log -> build."""
    def test_pages_render_without_js(self):
        tmp = Path(tempfile.mkdtemp()) / "r"; tmp.mkdir()
        for n in ("data", "inbox", "vendor", "gia_build"):
            shutil.copytree(ROOT / n, tmp / n)
        shutil.copy(ROOT / "build_dashboard.py", tmp)
        latest = max(json.loads((tmp / "data" / "ledger.json").read_text())["packets"])
        ed = (date.fromisoformat(latest) + timedelta(days=1)).isoformat()
        log = json.loads((ROOT / "tests" / "fixtures" / "assessment_log-2026-10-18.json").read_text())
        packet = {"edition": ed,
            "markets": [{"asset": "brent", "label": "Brent crude (test)", "as_of": latest, "value": 1.0, "unit": "USD/bbl",
                         "change": 0.5, "change_unit": "%", "source": {"name": "Test", "url": "https://example.com/m"}}],
            "reports": [{"id": "render-test", "title": "Render test", "date": ed, "author": "Test",
                         "body": "# Bottom line\n\nSee [the offer](story:iran-seven-day-hormuz-offer).\n\n- one\n- two",
                         "stories": ["iran-seven-day-hormuz-offer"]}],
            "assessment_log": log,
            "calendar": [{"id": "render-cal-day", "date": (date.fromisoformat(latest) + timedelta(days=3)).isoformat(), "time": "22:00", "tz": "America/New_York",
                          "title": "Render test session", "sources": [{"name": "Test cal", "url": "https://example.com/c"}]},
                         {"id": "render-cal-q", "date": f"{int(latest[:4]) + 1}-Q1", "date_precision": "quarter", "title": "Render test quarter",
                          "sources": [{"name": "Test cal", "url": "https://example.com/q"}]},
                         {"id": "render-cal-nosrc", "date": latest, "title": "Dropped: no source", "sources": []}],
            # area-only theater zone (no lat/lon): the build must anchor its label and draw the outline
            "zones": [{"id": "test-black-sea", "name": "Black Sea (test)", "severity": "watch", "note": "Area render test",
                       "entities": ["black-sea", "ukraine", "turkey"],
                       "area": {"type": "Polygon", "coordinates": [[[28.0, 41.5], [41.5, 41.5], [41.5, 46.5], [28.0, 46.5], [28.0, 41.5]]]},
                       "area_source": {"name": "Test outline", "url": "https://example.com/area"}}]}
        (tmp / "inbox" / f"{ed}.json").write_text(json.dumps(packet))
        apply_all(tmp, wikipedia=lambda u: None)
        subprocess.run([sys.executable, "build_dashboard.py"], cwd=tmp, check=True, capture_output=True)
        hd = tmp / "history"
        pages = [hd / "markets.html", hd / "reports" / "index.html", hd / "reports" / "render-test.html", hd / "assessment-log.html"]
        for page in pages:
            with self.subTest(page=page.name):
                h = page.read_text(encoding="utf-8")
                self.assertIn('name="viewport"', h)
                self.assertNotIn("<script", h)
                self.assertIn("@page{size:letter portrait}", h)                  # Director: Letter portrait
                for href in re.findall(r'href="([^"#:]+\.html)"', h):
                    self.assertTrue((page.parent / href).resolve().exists(), f"{page.name} -> {href}")
        rep = (hd / "reports" / "render-test.html").read_text()
        self.assertIn('<a href="../trace-iran-seven-day-hormuz-offer.html">the offer</a>', rep)
        alog = (hd / "assessment-log.html").read_text()
        self.assertEqual(alog.count('class="card"'), len(log))
        self.assertIn("21 accepted, 5 rejected", alog)
        self.assertIn("likely → <b>possible</b>", alog)
        dash = (tmp / "dashboard.html").read_text()
        for sid in ("sec-map", "sec-board", "sec-markets", "sec-connect", "sec-storylines", "sec-calendar", "sec-stories", "gia-leaflet"):
            self.assertEqual(dash.count(f'id="{sid}"'), 1, sid)                  # all 8 shots.py selectors
        self.assertIn('<meta name="viewport"', dash)
        self.assertIn('<span class="up"><span aria-hidden="true">▲</span> +0.5%<span class="sr"> up</span></span>', dash)                   # sign + arrow, teal class
        self.assertIn("Brent crude (test)", dash)
        self.assertIn("Render test session", dash); self.assertIn("PM ET", dash)
        self.assertIn(f"Q1 {int(latest[:4]) + 1}", dash)
        self.assertNotIn("Dropped: no source", dash)
        # phone trim: CSS only, every "more" row carries a count computed from the data
        sts = json.loads((tmp / "data" / "stories.json").read_text()); hzd = json.loads((tmp / "data" / "hotzones.json").read_text())
        sid = {x["id"] for x in sts}; eds = max(x.get("edition") or x["date"] for x in sts); today_ids = {x["id"] for x in sts if (x.get("edition") or x["date"]) == eds}
        n_causal = sum(1 for x in sts if x["id"] in today_ids for c in x.get("causes", []) if c["story"] in sid) \
                 + sum(1 for x in sts for c in x.get("causes", []) if c["story"] in today_ids)          # effects of today's stories
        n_links = sum(1 for l in hzd["links"] if l["from"] in {z["id"] for z in hzd["zones"]} and l["to"] in {z["id"] for z in hzd["zones"]})
        m = re.search(r'<span class="ml">All</span> <b class="mn">(\d+)</b> <span class="ml">connections</span>', dash)
        self.assertIsNotNone(m); self.assertEqual(int(m.group(1)), n_causal + n_links)
        self.assertRegex(dash, r'href="#reg-middle-east"><span class="mt"><b class="mn">\d+</b> <span class="ml">more in Middle East</span></span><svg class="ci"')
        self.assertRegex(dash, r'href="history/storyline-[a-z0-9-]+\.html"><span class="mt"><b class="mn">\+\d+</b> <span class="ml">more</span></span><svg class="ci"')
        # hi-fi fix pass: Carbon secondary buttons, one static-map link, Letter print, Plex fonts (OFL)
        self.assertIn('<a class="gbtn" href="dashboard-cesium.html"><svg class="ci"', dash)
        self.assertNotIn('class="pathbtn"', dash[:dash.index('id="sec-stories"')])
        self.assertIn(".gbtn{display:inline-flex;align-items:center;gap:8px;min-height:48px;padding:0 16px;box-sizing:border-box;background:#6f6f6f;color:#ffffff!important", dash)
        fb = dash[dash.index('<div id="gia-fallback">'):dash.index('</a>', dash.index('<div id="gia-fallback">'))]
        self.assertEqual(len(re.findall(r"<a\b", fb)), 1); self.assertIn('<a id="map" class="maplink" href="map.html"', fb)
        self.assertNotIn('r="8" fill="#3a1414"', fb)                            # no numbered hit circles
        self.assertIn("@page{size:letter portrait;margin:.5in}", dash)
        # 00:27-00:32 round: print cuts, critical glyph, Map page (contract §1), slides, history buttons
        # Director 00:52 ET: phone trims never reach print; #sec-stories, 'more' rows and older storyline entries are print-hidden
        self.assertIn("#sec-stories,main>p.meta,.sltl li.pe,.more{display:none!important}.x{display:revert!important}", dash)
        for ol in re.findall(r'<div class="sltl[^"]*"[^>]*>.*?<ol>(.*?)</ol>', dash):
            items = [li for li in re.findall(r'<li class="([^"]*)"', ol) if "mrow" not in li]
            self.assertEqual(sum("pe" not in c.split() for c in items), min(2, len(items)))   # 2 latest entries print
        # every hot zone on the static map is labelled or numbered (Today and Map page); numbered ones get a legend row
        nz = len(json.loads((tmp / "data" / "hotzones.json").read_text())["zones"])
        for page in ("dashboard.html", "map.html"):
            h = (tmp / page).read_text(encoding="utf-8"); i = h.index('<div id="gia-fallback">'); svg = h[i:h.index("</svg>", i)]
            scr, prn = svg[:svg.index('<g class="prl">')], svg[svg.index('<g class="prl">'):]   # r4: screen + print-only layers
            nlab, nnum = scr.count('<g class="lab">'), scr.count('<g class="nmk">')
            self.assertEqual(nlab + nnum, nz, page); self.assertEqual(prn.count('<g class="lab">') + prn.count('<g class="nmk">'), nz, page)
            self.assertEqual(len(re.findall(r'<b class="nmk">\d+</b>', h)), nnum + (prn.count('<g class="nmk">') if "nlab-pr" in h else 0), page)
            for ln in re.findall(r'<line class="ldr-tuck"[^>]*>', svg): self.assertIn('stroke="#8d8d8d"', ln)   # tuck leaders
        # marker tokens: one definition (gia_build/markers.py), emitted as :root --gia-marker-*; pins use the token;
        # JS hard-codes no marker colour; every pin carries the per-type shape hook
        from gia_build import markers as MK
        dash_h = (tmp / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn(MK.ROOT_CSS, dash_h)
        for k, (_, hx, _, shp) in MK.MARKERS.items():
            for g in re.findall(rf'<g class="mk" data-marker="{k}" data-shape="([a-z]+)">', dash_h): self.assertEqual(g, shp)
        self.assertNotRegex(re.sub(r'<g class="mk".*?</g>', '', dash_h.split('<div id="gia-fallback">')[1].split("</svg>")[0]), r'opacity="(1|\.45)"[^>]*stroke="#fff"')
        for js in ("gia-map.js", "gia-cesium.js"):
            src = (ROOT / "vendor" / js).read_text(encoding="utf-8")
            self.assertNotRegex(src, r"(military|strike|diplomacy|energy|political)\s*:\s*'#", js)   # no per-type colour table
            self.assertIn("getPropertyValue('--gia-marker-'", src, js)
        # UI tokens (Director 01:30 ET): accent + Carbon focus, one definition each; no red in the shared CSS
        from gia_build import ui_tokens as UI
        self.assertIn(UI.ROOT_CSS, dash_h)
        self.assertIn(":target{outline:2px solid var(--gia-focus);outline-offset:-2px", dash_h)
        css = re.search(r"<style>(.*?)</style>", dash_h, re.S).group(1)
        self.assertNotIn("#ff5a4f", css.replace(MK.ROOT_CSS, ""))
        self.assertNotIn("#ff6b5f", css)
        # severity + path tokens (Director 01:35 ET): one critical red, its print twin, the glyph's own token; no yellow on paths
        self.assertNotIn("#ff3b30", dash_h)
        for k, (c, pr, o) in UI.SEV.items():   # one screen + print + outline token per level, emitted once
            self.assertIn(f"--gia-sev-{k}:{c};--gia-sev-{k}-print:{pr};--gia-sev-{k}-outline:{o};", dash_h)
        for old in ("#ff9f0a", "#ffd60a", "#64d2ff", "#7a6634"): self.assertNotIn(old, dash_h)
        self.assertNotIn('"color":', (tmp / "dashboard.html").read_text(encoding="utf-8").split('id="gia-map-data">')[1].split("</script>")[0])
        for js in ("gia-map.js", "gia-cesium.js"):
            src = (ROOT / "vendor" / js).read_text(encoding="utf-8")
            self.assertIn("sevCol(z.sev)", src); self.assertNotIn("z.color", src)
        self.assertIn(f"--gia-sev-critical:{UI.SEV_CRITICAL}", dash_h)
        self.assertIn(".wmap .ls-critical{fill:var(--gia-sev-critical-print)}", dash_h)
        for f in glob.glob(str(tmp / "history" / "path-*" / "slide-0[1-3].html")):
            sh = Path(f).read_text(encoding="utf-8")
            self.assertNotIn('stroke="#ffe08a"', sh)
        for js in ("gia-map.js", "gia-cesium.js"): self.assertNotIn("#ffe08a", (ROOT / "vendor" / js).read_text(encoding="utf-8"))
        # Cesium places: one BillboardCollection + one LabelCollection, sprites cached per shape+colour+state, no entities
        ces = (ROOT / "vendor" / "gia-cesium.js").read_text(encoding="utf-8")
        self.assertEqual(ces.count("new Cesium.BillboardCollection("), 1); self.assertEqual(ces.count("new Cesium.LabelCollection("), 1)
        self.assertIn("b.setImage(sp.key,sp.canvas)", ces); self.assertNotIn("point:cesPoint", ces)
        # zone rings: one cached sprite per level in the SAME BillboardCollection (no keyline point entities); area keyline
        self.assertIn("function ringSprite(l,r)", ces); self.assertIn("rb.setImage(rs.key,rs.canvas)", ces)
        self.assertNotIn("[[S-2*SEV_OPX],[S+6]]", ces); self.assertNotIn("point:{pixelSize:z.r*2", ces)
        self.assertIn("name:'gia-area-keyline'", ces); self.assertIn("fromDegreesArrayHeights(up)", ces)
        for n in MK.SHAPE_SVG: self.assertIn(f"--gia-shape-{n}-d:", dash_h)
        self.assertTrue({v[3] for v in MK.MARKERS.values()} <= set(MK.SHAPE_SVG))
        # Director 01:50 ET palette: markers screen/print, spec SHAPE_SVG, past pins at full opacity, neutral links
        self.assertEqual({k: v[1] for k, v in MK.MARKERS.items()}, {"military": "#ffffff", "strike": "#ffffff", "diplomacy": "#4589ff", "energy": "#a7f0ba", "political": "#878d96"})
        self.assertEqual(MK.PRINT, {"military": "#161616", "strike": "#161616", "diplomacy": "#002d9c", "energy": "#198038", "political": "#697077"})
        self.assertEqual({k: (v[1], v[2]) for k, v in MK.SHAPE_SVG.items()}, {"square": ("fill", 1.0), "x": ("stroke", 3.0), "diamond": ("fill", 1.0), "triangle": ("fill", 1.0), "ring": ("stroke", 2.5)})
        self.assertEqual(MK.SPRITE["past_alpha"], 1.0); self.assertIn("@media print{:root{--gia-marker-military:#161616", dash_h)
        self.assertEqual({k: v[:2] for k, v in UI.SEV.items()}, {"critical": ("#fa4d56", "#a2191f"), "high": ("#ff832b", "#8a3800"), "elevated": ("#fddc69", "#684e00"), "watch": ("#c1c7cd", "#4d5358")})
        self.assertEqual({v[2] for v in UI.SEV.values()}, {"#0a1a2a"}); self.assertEqual((UI.SEV_GLYPH, UI.ACCENT_UI, UI.ACCENT_UI_PRINT), ("#fa4d56", "#a8a8a8", "#6f6f6f"))
        for f in [tmp / "dashboard.html", tmp / "map.html", tmp / "history" / "index.html"] + sorted((tmp / "history").glob("path-*/slide-01.html"))[:1]:
            h = f.read_text(encoding="utf-8")
            self.assertNotRegex(h, r"#(6fb1ff|a9c8ff|ff8a8f|f1c21b|7eb6ff|c9a6ff|ffe08a|ff5a4f|8fb6ff|5e2900|302400|6d675e)\b", f.name)
            self.assertIn("a{color:var(--gia-link);text-decoration:underline", h)
        mks = re.findall(r'<g class="mk".*?</g>', dash_h)
        self.assertTrue(mks); self.assertFalse([g for g in mks if 'stroke="#fff"' in g or 'opacity=".45"' in g])
        self.assertTrue(all("var(--gia-sprite-outline" in g for g in mks))
        # halo size = precision; feature (exact) pins carry no halo
        self.assertTrue(re.search(r'<circle class="ph" data-precision="(city|sector)"', dash_h))
        # halo ring in the pin's own colour, sized by precision (9 / 13 / 19, sector dashed); 2D only (no halo in gia-cesium.js)
        self.assertEqual(MK.PRECISION_HALO, {"feature": 9, "city": 13, "sector": 19})
        for m in re.finditer(r'<circle class="ph" data-precision="(\w+)"[^>]*r="([\d.]+)"[^>]*style="stroke:(var\(--gia-marker-\w+\))"([^>]*)/>', dash_h):
            self.assertEqual(float(m.group(2)), MK.PRECISION_HALO[m.group(1)]); self.assertEqual("stroke-dasharray" in m.group(4), m.group(1) == "sector")
        self.assertNotIn("precision", ces)
        # print severity: one value per level, >= 4.5:1 on white, print sea and print land (room 01:58 / Director 01:59)
        def _l(h):
            c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]; c = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c]
            return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
        for lvl, (_, pr, _) in UI.SEV.items():
            for bg in ("#ffffff", "#f3f1ec", "#dcd7cd"):
                self.assertGreaterEqual((max(_l(pr), _l(bg)) + .05) / (min(_l(pr), _l(bg)) + .05), 4.5, (lvl, pr, bg))
        # links / focus / headings / labels tokens (room 01:58, Director 02:00)
        self.assertEqual((UI.LINK, UI.LINK_RULE, UI.LINK_HOVER, UI.LINK_OFFSET_PX, UI.LINK_RULE_PX, UI.LINK_HOVER_RULE_PX), ("#f3efe7", "#8d8d8d", "#f4f4f4", 3, 1, 2))
        self.assertEqual((UI.FOCUS, UI.FOCUS_PX, UI.FOCUS_OFFSET_PX, UI.FOCUS_PRINT), ("#ffffff", 2, 2, "#0f62fe"))
        self.assertEqual((UI.H2, UI.H4, UI.HEAD_PRINT), ("#f3efe7", "#d0cac0", "#161616"))
        self.assertEqual(MK.LABEL, {"active": ("#f3efe7", 600, 12), "past": ("#d0cac0", 400, 11)})
        self.assertEqual(MK.dominant(["diplomacy", "strike", "diplomacy"]), "diplomacy"); self.assertEqual(MK.dominant(["diplomacy", "military"]), "military")
        self.assertNotIn("#8fb6ff", dash_h); self.assertIn("text-underline-offset:var(--gia-link-offset)", dash_h)
        # Leaflet attribution bar (Director 02:15): card bg token at full opacity, gray 40 text/link, standard underline + hover
        self.assertEqual((UI.ATTRIB_BG, UI.CARD_BG, UI.ATTRIB_TX), ("#111821", "#111821", "#a8a8a8"))
        self.assertIn(".leaflet-container .leaflet-control-container .leaflet-control-attribution{background:var(--gia-attrib-bg);color:var(--gia-attrib-tx);opacity:1}", dash_h)
        self.assertIn(".leaflet-container .leaflet-control-attribution a:hover{color:var(--gia-link-hover)", dash_h)
        js = (ROOT / "vendor" / "gia-map.js").read_text(encoding="utf-8")
        self.assertNotIn('stroke="#fff"', js); self.assertIn("tok('--gia-sprite-outline')", js); self.assertNotIn("active?1:.45", js)
        self.assertIn("css=2*r+W+2*(kl?SEV_OPX:0)+2", ces); self.assertIn("g.arc(css/2,css/2,r,0,Math.PI*2)", ces)
        self.assertIn("text:p.name,", ces); self.assertNotIn("text:mkGlyph(p.marker)", ces)
        # path slides: non-severity accents use --path #c3a6ff (red stays severity-only)
        for f in glob.glob(str(tmp / "history" / "path-*" / "slide-0[1-3]*.html")):
            sh = Path(f).read_text(encoding="utf-8")
            self.assertIn(":root{--path:var(--gia-path)}.prog i{background:var(--path)}", sh)   # spec 19 Oct: rest = accent-ui
            self.assertNotRegex(sh, r"#(6fb1ff|a9c8ff|ff8a8f|f1c21b)\b")
            self.assertNotIn('stroke="#ff5a4f" stroke-width="2"/><text x="28" y="34" fill="#ff5a4f"', sh)
        for m in re.finditer(r'<span class="meter" title="Severity: critical[^"]*">(.*?)</span>', dash):
            self.assertIn('<svg class="critg"', m.group(1))
        mp = (tmp / "map.html").read_text(encoding="utf-8")
        gl = mp[mp.index('<div id="gia-leaflet"'):]
        self.assertTrue(gl.startswith('<div id="gia-leaflet" data-mount="inner" data-state="static"><div id="gia-fallback"><svg'))
        self.assertEqual(mp.count('id="gia-leaflet"'), 1); self.assertEqual(mp.count('id="gia-fallback"'), 1)
        for r in ("americas", "europe", "middle-east", "africa", "russia-eurasia", "asia-pacific"):
            self.assertIn(f'id="reg-{r}"', mp)
        self.assertIn('id="gia-map-open"', mp); self.assertNotIn("<a ", mp[mp.index('<div id="gia-fallback">'):mp.index("</svg>", mp.index('<div id="gia-fallback">'))])
        slide = next((tmp / "history").glob("path-*/slide-01.html")).read_text(encoding="utf-8")
        self.assertIn('class="gd on"', slide); self.assertIn('aria-current=step', slide); self.assertNotIn('fill="#000" font-size', slide)
        self.assertIn(".pathbtn{display:inline-flex;align-items:center;gap:8px;min-height:48px;margin-top:8px;padding:0 16px;box-sizing:border-box;background:#6f6f6f;color:#ffffff!important", slide)
        self.assertIn('src:url(vendor/fonts2/GIA-PlexSans-Regular.woff2)', dash)
        for f in ("PlexSans-Regular", "PlexSans-SemiBold", "PlexMono-Medium"):
            self.assertTrue((tmp / "vendor" / "fonts2" / f"GIA-{f}.woff2").exists(), f)
        # r3: every @font-face file exists; Plex Mono Regular (never loaded) is gone; 600 headings + 500 labels kept
        for u in set(re.findall(r'src:url\((vendor/fonts2/[^)]+)\)', dash)): self.assertTrue((tmp / u).exists(), u)
        self.assertNotIn("PlexMono-Regular", dash); self.assertIn("font-weight:600;font-display:swap;src:url(vendor/fonts2/GIA-PlexSans-SemiBold.woff2)", dash)
        # r4 (Director 03:53): Sans Medium + Italic dropped (files and @font-face); no Sans 500 anywhere, Mono keeps its one 500 face
        for f in ("PlexSans-Medium", "PlexSans-Italic"):
            self.assertFalse((tmp / "vendor" / "fonts2" / f"GIA-{f}.woff2").exists(), f)
        faces = re.findall(r'@font-face\{[^}]*\}', dash); self.assertEqual(len(faces), 3, faces)
        self.assertNotIn("font-style:italic;font-weight", dash)
        for page in [dash, mp, slide, (tmp / "dashboard-cesium.html").read_text(encoding="utf-8"), (tmp / "history" / "index.html").read_text(encoding="utf-8"),
                     (tmp / "vendor" / "gia-cesium.js").read_text(encoding="utf-8")]:
            for m in re.finditer(r'(?:font-weight:\s*500|font:\s*500|500 1\dpx|font-weight="500")', page):
                ctx = page[m.start():m.start() + 120]
                self.assertIn("Mono", ctx + page[max(0, m.start() - 200):m.start()].split("{")[-1], ctx)
        # r4 (Director 04:24 item 3): no synthetic bold: UA bold maps to 600, no 700/900/bold left in any CSS
        for page in (dash, mp, (tmp / "history" / "index.html").read_text(encoding="utf-8")):
            self.assertIn(":where(b,strong,h1,h2,h3,h4,h5,h6,th){font-weight:600}", page)
            self.assertEqual(re.findall(r'font-weight:\s*(?:bold|bolder|700|800|900)|font-weight="(?:bold|700|900)"', page), [])
        # r5 (Director 05:01 items 1-2, Designer r5): history pages load the site's Plex faces with paths relative to the page;
        # notes upright (colour + left rule), nothing italic anywhere; print level words carry a 3 px white halo
        import glob as _g
        deep = sorted(_g.glob(str(tmp / "history" / "path-*" / "slide-*.html")))[:1] + sorted(_g.glob(str(tmp / "history" / "reports" / "*.html")))[:1]
        for f in [tmp / "history" / "index.html", tmp / "history" / "zone-china.html"] + [Path(x) for x in deep]:
            pg = Path(f).read_text(encoding="utf-8"); here = Path(f).parent
            urls = re.findall(r'src:url\(([^)]+\.woff2)\)', pg); self.assertGreaterEqual(len(urls), 3, f)
            for u in urls: self.assertTrue((here / u).resolve().exists(), (f, u))
            self.assertIn('body{font-family:"IBM Plex Sans",Arial', pg)
            self.assertIn(":where(*){font-style:normal}", pg)
        for page in (dash, mp, slide, (tmp / "history" / "zone-china.html").read_text(encoding="utf-8")):
            self.assertEqual(re.findall(r'font-style:\s*(?:italic|oblique)', page), [])
            self.assertIn(":where(*){font-style:normal}", page)
            self.assertIn('.an{color:#d0cac0;font-style:normal;font-weight:400;font-family:"IBM Plex Sans",Arial,sans-serif;border-left:2px solid #525252;padding-left:8px}', page)
            self.assertIn("@media print{.an,.an *{color:#525252!important}.an{border-left:2px solid #a8a8a8!important}}", page)
        # r5 (Director 05:58 items 2-4): print names 8 pt, print leaders #767676, slide maps light in print, globe swaps to static
        from gia_build import ui_tokens as _U
        self.assertIn(f'font-size="{_U.PRINT_NS_UNITS:g}"', dash); self.assertIn(f".wmap .prl .zl{{font-size:{_U.PRINT_NS_UNITS:g}px!important}}", dash); self.assertIn(".wmap .prl line.ldr,.wmap .prl line.ldr-tuck{stroke:#767676!important", dash)
        self.assertIn(".smap .sbg{fill:#f3f1ec!important}", slide); self.assertIn('class="wmap smap"', slide)
        self.assertIn("@media print{#gia-cesium{display:none!important}#gia-fallback{display:block!important}}", (tmp / "dashboard-cesium.html").read_text(encoding="utf-8"))
        self.assertIn(".wmap .ls{stroke:#ffffff!important;stroke-width:8px!important;stroke-linejoin:round;paint-order:stroke;vector-effect:non-scaling-stroke}", dash)
        # r4 (Director 04:24 item 2): print forced light on every page; map.html prints its static map; key row 10.5pt; halos solid
        for f in ("history/index.html", "history/path-2021-11-russia-buildup/slide-10.html"):
            self.assertIn("@media print{html,body{background:#fff!important;color:#141312!important", (tmp / f).read_text(encoding="utf-8"))
        self.assertIn("#gia-leaflet #gia-fallback{display:block!important}", mp); self.assertIn(".mreg h4{color:#54504a!important}", mp)
        self.assertIn(".legend.nlab,.legend.nlab span,.legend.nlab>b{font-size:10.5pt!important", dash)
        self.assertIn(".wmap .hz{opacity:1!important;fill:none!important;stroke-opacity:1!important", dash)
        from gia_build import markers as MK2
        self.assertEqual(MK2.LABEL["active"][1], 600)
        # r3 tap targets (QA r4 item 6, Director 03:06): ONLY chips, toggles and buttons get min-height/min-width 24, at zero
        # specificity, with no display change, never generic links or map surfaces
        from gia_build import ui_tokens as UI
        self.assertEqual(UI.TAP_CSS, ":where(.chip,summary,button,a.btn){min-height:24px;min-width:24px;box-sizing:border-box}")
        for page in (dash, mp, slide):
            self.assertIn(UI.TAP_CSS, page)
        self.assertNotRegex(UI.TAP_CSS, r"display|\ba\{|\ba,|wmap|maplink|leaflet|cesium")
        # r3 print key: swatches and halos take the PRINT severity tokens; level words >= 10.5pt in print
        for lv in ("critical", "high", "elevated", "watch"):
            self.assertIn(f".legend i.sw-{lv}{{background:var(--gia-sev-{lv}-print)!important}}", dash)
            self.assertIn(f".wmap .hz-{lv}{{fill:var(--gia-sev-{lv}-print);stroke:var(--gia-sev-{lv}-print)}}", dash)
            self.assertIn(f'<i class="sw-{lv}"', dash)
        self.assertIn(".legend.hzk span,.legend.nlab .pr-only,.meter b{font-size:10.5pt!important}", dash)
        self.assertGreaterEqual(len(re.findall(r'<(?:circle|path) class="hz hz-', dash[dash.index('class="wmap"'):dash.index("</svg>", dash.index('class="wmap"'))])), 18)
        self.assertTrue((tmp / "vendor" / "fonts2" / "OFL.txt").exists())
        self.assertRegex(dash, r'<a class="more ph all" href="#sec-storylines"><span class="mt"><span class="ml">All</span> <b class="mn">\d+</b> <span class="ml">active storylines</span></span><svg class="ci"')
        seg = dash[dash.index('id="sec-board"'):dash.index('id="sec-stories"')]
        self.assertNotIn("<details", seg); self.assertNotIn("<script", seg)
        self.assertNotIn("No market data filed", dash); self.assertNotIn("No upcoming calendar items", dash)
        self.assertNotIn('<script src="vendor/leaflet/leaflet.js"', dash)       # Leaflet is not fetched up front
        self.assertIn('id="gia-map-loader" data-css="vendor/leaflet/leaflet.css"', dash)
        self.assertIn('<button type="button" id="gia-map-open" class="gbtn" hidden', dash)
        self.assertIn("Black Sea (test): outline Test outline", dash)           # static SVG outline with source
        self.assertIn('"area_source": "Test outline"', dash)                    # Leaflet payload
        ces = (tmp / "dashboard-cesium.html").read_text()
        self.assertNotIn("vendor/leaflet", ces); self.assertNotIn("gia-map-loader", ces)
        self.assertIn("Cesium.js", ces)
        hz = json.loads((tmp / "data" / "hotzones.json").read_text())
        self.assertNotIn("lat", next(z for z in hz["zones"] if z["id"] == "test-black-sea"))  # anchor is build-only
        idx = (hd / "index.html").read_text()
        for link in ("markets.html", "reports/index.html", "assessment-log.html"):
            self.assertIn(link, idx)
        # trace split: every story at most once per trace tree, bounded size, shared graph, year pages
        causal = json.loads((hd / "causal.json").read_text())
        self.assertEqual(len(causal), len(list(hd.glob("trace-*.html"))))
        for t in hd.glob("trace-*.html"):
            h = t.read_text(encoding="utf-8"); ids = re.findall(r'<li id="n-([^"]+)"', h)
            self.assertEqual(len(ids), len(set(ids)), t.name)
            self.assertLess(len(h), 500_000, t.name)
            for a in re.findall(r'href="#n-([^"]+)"', h): self.assertIn(a, ids, t.name)
        self.assertNotIn('class="card"', idx)                                  # cards live on year pages
        for href in re.findall(r'href="(year-\d{4}\.html)"', idx): self.assertTrue((hd / href).exists())

class TodayEmptyStates(unittest.TestCase):
    def test_sections_render_with_ids_when_data_missing(self):
        from gia_build import today
        tmp = Path(tempfile.mkdtemp()); (tmp / "data").mkdir()
        (tmp / "data" / "markets.json").write_text("[]")              # empty file and missing calendar.json
        ts = today.sections(str(tmp), regions=["Europe"], latest=[], all_stories=[], by_id={}, zones=[], zone_links=[], lines=[],
                            edition="2026-10-18", places_of=lambda s: [], ddisp=lambda s: s["date"])
        for key, sid, text in [("board", "sec-board", "No stories filed for this edition."), ("markets", "sec-markets", "No market data filed for this edition."),
                               ("connect", "sec-connect", "No causal links recorded"), ("storylines", "sec-storylines", "No storyline has a story"),
                               ("calendar", "sec-calendar", "No upcoming calendar items filed.")]:
            self.assertIn(f'<section id="{sid}"', ts[key]); self.assertIn(text, ts[key])

    def test_calendar_labels(self):
        from gia_build.today import cal_label
        self.assertEqual(cal_label({"date": "2026-10-27"}), "Tue Oct 27")
        self.assertEqual(cal_label({"date": "2026-10-18", "time": "22:00", "tz": "America/New_York"}), "Sun Oct 18, 10 PM ET")
        self.assertEqual(cal_label({"date": "2026-10-27", "date_precision": "range", "end": "2026-10-28"}), "Oct 27–28")
        self.assertEqual(cal_label({"date": "2026-10-19", "date_precision": "range", "end": "2026-11-02"}), "Oct 19 – Nov 2")
        self.assertEqual(cal_label({"date": "2026-12", "date_precision": "month"}), "Dec 2026")
        self.assertEqual(cal_label({"date": "2027-Q1", "date_precision": "quarter"}), "Q1 2027")

if __name__ == "__main__":
    unittest.main()


class MapSurfaceAndLabelTest(unittest.TestCase):
    """Fresh render of the real corpus in a temp dir (never build-next): link styling never on a map/globe surface
    (qa/link_surface_check.py, Director 01:59), every map label = its zone's name in data/hotzones.json (Director 02:06),
    and the static-map label solve has zero overlaps (labels, pins, halos, leaders)."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp()) / "r"; cls.tmp.mkdir()
        for n in ("data", "inbox", "vendor", "gia_build"): shutil.copytree(ROOT / n, cls.tmp / n, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(ROOT / "build_dashboard.py", cls.tmp)
        cls.geom = cls.tmp.parent / "geom.json"
        env = dict(os.environ, GIA_MAP_GEOM=str(cls.geom), PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
        subprocess.run([sys.executable, "build_dashboard.py"], cwd=cls.tmp, check=True, capture_output=True, env=env)
        cls.zones = json.loads((ROOT / "data" / "hotzones.json").read_text(encoding="utf-8"))["zones"]   # read only
    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp.parent, ignore_errors=True)

    def test_link_surface_check(self):
        chk = ROOT.parent / "qa" / "link_surface_check.py"
        if not chk.exists(): self.skipTest("qa/link_surface_check.py not beside this repo copy")
        r = subprocess.run([sys.executable, str(chk), str(self.tmp)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:]); self.assertIn("0 FLAGGED", r.stdout)

    def test_map_labels_equal_zone_names(self):
        import html as _h
        names = {z["id"]: z["name"] for z in self.zones}
        for page in ("dashboard.html", "map.html"):
            h = (self.tmp / page).read_text(encoding="utf-8")
            for svg0 in re.findall(r'<svg\b[^>]*class="wmap"[^>]*>.*?</svg>', h, re.S):
              # r4: the screen layer (g.scl) and the print-only layer (g.prl) each label every zone once
              for svg in ([svg0[:svg0.index('<g class="prl">')], svg0[svg0.index('<g class="prl">'):]] if '<g class="prl">' in svg0 else [svg0]):
                labs = [_h.unescape(t) for t in re.findall(r'<text class="zl"[^>]*>([^<]*)</text>', svg)]
                nums = [_h.unescape(t).split(": ", 1)[1].rsplit(" · ", 1)[0] for t in re.findall(r'<g class="nmk"><title>([^<]*)</title>', svg)]
                with self.subTest(page=page):
                    self.assertTrue(set(labs) <= set(names.values()), set(labs) - set(names.values()))
                    self.assertEqual(sorted(labs + nums), sorted(names.values()))   # every zone labelled once, by its name
            for il in re.findall(r'<text class="il"[^>]*>([^<]*)</text>', h): self.assertIn(_h.unescape(il), names.values())
            for m in re.finditer(r'"zones":\s*(\[.*?\])\s*,\s*"places"', h):   # Leaflet payload
                self.assertEqual({z["id"]: z["name"] for z in json.loads(m.group(1))}, names)
        c = (self.tmp / "dashboard-cesium.html").read_text(encoding="utf-8")
        m = re.search(r'"zones":\s*(\[.*?\])\s*,\s*"places"', c); self.assertTrue(m, "Cesium zone payload not found")
        self.assertEqual({z["id"]: z["name"] for z in json.loads(m.group(1))}, names)
        self.assertIn("label:{text:z.name", (self.tmp / "vendor" / "gia-cesium.js").read_text(encoding="utf-8").replace(" ", ""))
        self.assertIn("bindTooltip(z.name", (self.tmp / "vendor" / "gia-map.js").read_text(encoding="utf-8"))

    def test_phone_map(self):
        """Director 03:20 / spec v3: phone static map, strict 2 px gaps at every band width, leaders <= 70 px, full names,
        Sudan wraps after 'Kordofan /', 320-389 numbers Lebanon + Tigray with full-name key rows; Today only."""
        import html as _h
        P = json.loads(self.geom.read_text())["phone"]; names = {z["id"]: z["name"] for z in self.zones}
        for vw, v in P.items():
            with self.subTest(vw=vw):
                self.assertEqual(v["overlaps"], []); self.assertGreaterEqual(v["min_gap"][0], 2)
                if v["numbered"]: self.assertGreaterEqual(v["badge_pin_min"][0], 2, v["badge_pin_min"])   # r4: badge vs pins
                self.assertTrue(all(x <= 70 for x in v["leaders_px"].values()), v["leaders_px"])
                for zid, lines in v["lines"].items(): self.assertEqual(" ".join(lines), names[zid])
                if "sudan-kordofan" in v["lines"]: self.assertEqual(v["lines"]["sudan-kordofan"], ["Sudan (Kordofan /", "Darfur)"])
                if int(vw) < 390: self.assertEqual(sorted(v["numbered"]), ["lebanon", "tigray"])
                else: self.assertTrue(v["tigray"] and v["tigray"]["east"], v["tigray"])
        d = (self.tmp / "dashboard.html").read_text(encoding="utf-8")
        ph = d[d.index('<div class="mp-ph">'):]; ph = ph[:ph.index("<!--/mp-->")]
        rows = [(z, _h.unescape(t)) for z, t in re.findall(r'<li><span class="mk">\d+</span><a href="history/zone-([^.]+)\.html">([^<]*)</a>', ph)]
        self.assertIn(("lebanon", "Lebanon (Israel–Hezbollah)"), rows); self.assertIn(("tigray", "Tigray / Ethiopia-Eritrea border"), rows)
        for z, t in re.findall(r'<a href="history/zone-([^.]+)\.html">([^<]*)</a>', ph): self.assertEqual(_h.unescape(t), names[z])
        also = re.search(r'<p class="mp-also">(.*?)</p>', ph).group(1); self.assertEqual(len(re.findall(r"<a ", also)), 11)
        self.assertIn('<div class="mp-box">', d[d.index('id="map" class="maplink"'):d.index('<span class="mapopen">')])
        self.assertNotIn("mp-box", (self.tmp / "dashboard-cesium.html").read_text(encoding="utf-8"))
        self.assertNotIn("mp-box", (self.tmp / "map.html").read_text(encoding="utf-8"))

    def test_label_solve_has_zero_overlaps(self):
        G = json.loads(self.geom.read_text()); H, P, L = G["halos"], G["pins"], G["labels"]
        self.assertEqual(G["shortened"], []); self.assertEqual(G["placed"] + len(G["numbered"]), len(self.zones))
        from gia_build import ui_tokens as UI
        g = UI.LABEL_GAP; grow = lambda b: (b[0] - g, b[1] - g, b[2] + g, b[3] + g)
        # r3 strict (Director 03:03): boxes may not even TOUCH; each label box is grown by LABEL_GAP (text halo + ascent/descent)
        ov = lambda a, b: not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])
        def bc(b, c): qx = min(max(c[0], b[0]), b[2]); qy = min(max(c[1], b[1]), b[3]); return math.hypot(qx - c[0], qy - c[1]) < c[2]
        def sc(s, c):
            x1, y1, x2, y2 = s; dx, dy = x2 - x1, y2 - y1; n = dx * dx + dy * dy
            t = 0 if n == 0 else max(0, min(1, ((c[0] - x1) * dx + (c[1] - y1) * dy) / n)); return math.hypot(x1 + t * dx - c[0], y1 + t * dy - c[1]) < c[2]
        def sb(s, bx):
            x1, y1, x2, y2 = s; t0, t1 = 0.0, 1.0; dx, dy = x2 - x1, y2 - y1
            for pp, qq in ((-dx, x1 - bx[0]), (dx, bx[2] - x1), (-dy, y1 - bx[1]), (dy, bx[3] - y1)):
                if pp == 0:
                    if qq < 0: return False
                else:
                    t = qq / pp
                    if pp < 0: t0 = max(t0, t)
                    else: t1 = min(t1, t)
            return t0 < t1 - 1e-6
        def ss(a, b):
            (x1, y1, x2, y2), (x3, y3, x4, y4) = a, b; d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
            if d == 0: return False
            u = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d; v = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d; return 0 < u < 1 and 0 < v < 1
        # r4 (Director 03:53 item 2): the print-only label layer (level words at 10.5pt) obeys the same rules
        for L, layer in ((G["labels"], "screen"), (G["print"]["labels"], "print")):
            bad = []
            for i, a in enumerate(L):
                bad += [("label/label", a["id"], b["id"]) for b in L[i + 1:] if ov(grow(a["box"]), b["box"])]
                bad += [("label/pin", a["id"], c) for c in P if bc(a["box"], c)]
                bad += [("label/halo", a["id"], k) for k, h in H.items() if k != a["id"] and ov(a["box"], h)]
                if a["leader"]:
                    s = a["leader"]; h0 = H[a["id"]]; cx, cy, hr = (h0[0] + h0[2]) / 2, (h0[1] + h0[3]) / 2, (h0[2] - h0[0]) / 2 / .75
                    bad += [("leader/label", a["id"], b["id"]) for b in L if b["id"] != a["id"] and sb(s, b["box"])]
                    bad += [("leader/leader", a["id"], b["id"]) for b in L if b["id"] != a["id"] and b["leader"] and ss(s, b["leader"])]
                    # pins drawn inside the zone's own halo sit under the mark the leader starts from
                    bad += [("leader/pin", a["id"], c) for c in P if math.hypot(c[0] - cx, c[1] - cy) >= max(c[2], hr) and sc(s, c)]
                    bad += [("leader/halo", a["id"], k) for k, h in H.items() if k != a["id"] and sb(s, h)]
            self.assertEqual(bad, [], layer)
        L = G["labels"]
        # leader cap (Director 03:03): every static-map leader <= 70 SCREEN px (+eps) at a 1440 viewport, where the 1000-unit
        # map is MAP_PX_1440 = 1300 px wide; geometry and drawn <line>
        cap = (UI.LEADER_MAX_PX + UI.LEADER_EPS_PX) * UI.MAP_VIEW_W / UI.MAP_PX_1440
        for l in L:
            if l["leader"]: self.assertLessEqual(math.hypot(l["leader"][2] - l["leader"][0], l["leader"][3] - l["leader"][1]), cap, l["id"])
        for page in ("dashboard.html", "map.html"):
            for x1, y1, x2, y2 in re.findall(r'<line class="ldr[^"]*" x1="([\d.-]+)" y1="([\d.-]+)" x2="([\d.-]+)" y2="([\d.-]+)"', (self.tmp / page).read_text(encoding="utf-8")):
                self.assertLessEqual(math.hypot(float(x2) - float(x1), float(y2) - float(y1)), cap + 1.5, page)   # drawn ends rounded to whole units
        L = G["labels"]
        for l in G["print"]["labels"]:
            if l["leader"]: self.assertLessEqual(math.hypot(l["leader"][2] - l["leader"][0], l["leader"][3] - l["leader"][1]), cap, "print " + l["id"])
        self.assertEqual(G["print"]["placed"] + len(G["print"]["numbered"]), len(self.zones))
        self.assertEqual(G["print"]["ls"], UI.PRINT_LS_UNITS); self.assertAlmostEqual(UI.PRINT_LS_UNITS * UI.PRINT_MAP_PX / UI.MAP_VIEW_W, 14, delta=.01)
        dash = (self.tmp / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn('<g class="scl">', dash); self.assertIn('<g class="prl">', dash)
        prl = dash[dash.index('<g class="prl">'):dash.index("</svg>", dash.index('<g class="prl">'))]
        self.assertEqual(set(re.findall(r'class="ls ls-[a-z]+"[^>]*font-size="([\d.]+)"', prl)), {f"{UI.PRINT_LS_UNITS:g}"})
        self.assertIn("@media print{.wmap .scl,.legend.scr-only{display:none!important}.wmap .prl{display:inline!important}", dash)
        tg = {l["id"]: l for l in L}.get("tigray")
        if tg:   # r3: Tigray placed by the solver order under the screen-px cap (it now sits ABOVE Sudan's label, west of its pin)
            self.assertTrue(tg["leader"])


class GlobeR3Test(unittest.TestCase):
    """r3 (Director 03:03): requestRenderMode, Plex zone labels, zone-over-place declutter, adaptive fallback on the container."""
    js = (ROOT / "vendor" / "gia-cesium.js").read_text(encoding="utf-8")
    def test_request_render_mode(self):
        self.assertIn("requestRenderMode:true,maximumRenderTimeChange:Infinity", self.js)
        for why in ("'sprite'", "'declutter'", "'selection'", "'resize'", "'slide'", "'data',2000", "'ready'", "'fonts'"):
            self.assertIn("wake(" + why, self.js)
        self.assertNotIn("glowPower", self.js.split("function trail")[1].split("}")[0])   # trail: static materials only
    def test_zone_labels_plex_and_declutter(self):
        self.assertIn("ZFONT='600 13px \"IBM Plex Sans\", Arial'", self.js); self.assertNotIn("bold 13px Arial", self.js)
        self.assertIn("kind:'zone'", self.js); self.assertIn("rank:active?10:20", self.js)   # zones (0-3) outrank places
        self.assertIn("v.camera.changed.addEventListener(declutter)", self.js); self.assertIn("MOUSE_MOVE", self.js)
    def test_zone_leaders_not_hidden(self):
        """r4 (Director 03:53 item 3): a front-facing zone label that meets another zone label moves onto a <= 70 px leader
        (billboard in the shared collection, #8d8d8d) instead of hiding; hidden leader slots never keep the globe awake."""
        for a in ("LDR_MAX=70", "len<=LDR_MAX", "why='leader'", "strokeStyle='#8d8d8d'", "if(b.show&&b.ready===false)return false;",
                  "var lb=BB.add({position:P,show:false", "state:function()"):
            self.assertIn(a, self.js)
        self.assertNotIn("Cesium.PolylineCollection", self.js)   # no extra primitive for leaders
    def test_fallback_on_container(self):
        for a in ("box.dataset.giaGlobeScale", "box.dataset.giaGlobeMs", "box.dataset.giaReady='globe'"): self.assertIn(a, self.js)
        # r4 (Director 04:24 item 1): forced, GPU-synced sample frames in one window; URL override; no postRender-gap timing
        for a in ("gl.readPixels(0,0,1,1", "v.scene.requestRender();v.render();", "THRESH=40", "giaGlobeScaleSource", "/[?&]gia-scale=([12])(?:&|$)/",
                  "'override'", "'adaptive'"):
            self.assertIn(a, self.js)
        self.assertNotIn("t-last", self.js); self.assertNotIn("preUpdate -> postRender", self.js)
        # r5 (steering 05:47): the window runs only after the ready signal (tiles loaded), warm-ups discarded, the timed frames
        # back to back in one task (no rAF / timer inside the window), median of >= 8
        for a in ("for(i=0;i<WARM;i++)frame();for(i=0;i<N;i++)ms.push(frame());", "if(GIA_SAMPLE()){", "v.scene.globe.tilesLoaded"):
            self.assertIn(a, self.js)
        n = int(re.search(r"WARM=(\d+), N=(\d+)", self.js).group(2)); self.assertGreaterEqual(n, 8)
        self.assertNotIn("requestAnimationFrame(step)", self.js); self.assertNotIn("},1500);", self.js)
        # r5 (Director 05:58 item 1): 15 s tile cap -> 'timeout' (never judged); tiles-loaded readout; comment fixed
        for a in ("CAP_MS=15000", "'timeout'", "box.dataset.giaGlobeTilesLoaded='true '", "box.dataset.giaGlobeTilesLoaded='timeout '", "!FLOWN||!v.scene.globe.tilesLoaded"):
            self.assertIn(a, self.js)
        self.assertNotIn("after shader compile", self.js)

    @unittest.skipUnless(os.environ.get("GIA_BROWSER_TESTS"), "set GIA_BROWSER_TESTS=<built dir served at http://127.0.0.1:PORT/> to run")
    def test_globe_labels_no_overlap_in_browser(self):
        """Real screen space at the default dashboard camera, 1440 wide: no two visible label boxes touch."""
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
            pg = b.new_page(viewport={"width": 1440, "height": 900}); pg.goto(os.environ["GIA_BROWSER_TESTS"] + "dashboard-cesium.html")
            pg.wait_for_function("document.getElementById('gia-cesium').dataset.giaReady === 'globe'", timeout=60000)
            vis = pg.evaluate("GIA_LABELS.visible()"); b.close()
        bad = [(a["name"], c["name"]) for i, a in enumerate(vis) for c in vis[i + 1:]
               if not (a["box"][2] < c["box"][0] or a["box"][0] > c["box"][2] or a["box"][3] < c["box"][1] or a["box"][1] > c["box"][3])]
        self.assertEqual(bad, []); self.assertGreaterEqual(sum(1 for v in vis if v["kind"] == "zone"), 1)
