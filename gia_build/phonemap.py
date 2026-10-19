"""Today's phone static map (<672 px), ported from the Designer's hifi/phonemap.py, spec.md 'Today: phone static map' v3
(approved for r3, Director 03:20). Same rules and numbers; adapted to this build's data and drawing:
- zones come from data/hotzones.json; this build has no hifi THEATERS (the Persian Gulf / Red Sea stand-in shapes are hifi
  only and no zone in data/ files an `area`), so Hormuz and Yemen are drawn and placed as point zones with their halo;
- pins = today's story places (story_places), shape = PLACE_MARKER, halo = MK.PRECISION_HALO, drawn by the caller's svg_pin;
- land = data/ne110.geojson through a cropped equirectangular view.
Labels are HTML at a true 11 px over a fixed-aspect box (CSS caps the box at 390 px); the SVG holds geography, halos, pins
and leaders. Two bands, each solved at its narrowest box: a = 320-389 viewport (box 286 px, Lebanon + Tigray numbered by
rule), b = 390-671 (box 356 px). Strict gaps: every name box, numbered marker and leader keeps >= 2 px from every other
name box, marker, pin, halo and leader (touching fails); leaders 12-70 screen px. Full hotzones.json names only.
No JS. verify() re-checks every band width in CSS px. Every word comes from data/."""
import math, re
from html import escape as _esc

MW = 356; BOX_MIN, BOX_MAX = 286, 390
FONT = 11; LS = .04; LINE = 13; PAD_X = 3
LAB_MAX = 140; GAP = 2; LEAD_MAX = 70; SLACK = 2
WINDOW = dict(lon0=25, lon1=62, lat_s=10, lat_n=42)
PAD = dict(w=4.0, e=4.0, n=3.0, s=3.0)
TUCK_RULES = {}          # spec v3: the v2 Tigray rule (west, below Sudan) is dropped for the phone map
SEVR = {"critical": 26, "high": 20, "elevated": 15, "watch": 11}
SEV_ORDER = ["watch", "elevated", "high", "critical"]
NUM_D = 20
SEV_WORD = {"critical": "Critical", "high": "High", "elevated": "Elevated", "watch": "Watch"}
VIEWPORTS = {320: 286, 356: 322, 360: 326, 389: 355, 390: 356, 414: 380, 671: 390}   # viewport -> box px (vw-34, cap 390)
BANDS = [dict(id="a", solve=286, vmin=320, vmax=389, number=("lebanon", "tigray")),
         dict(id="b", solve=356, vmin=390, vmax=671, number=("lebanon",))]
# r3 deviation from spec v3 (band b = all 7 placed): this build has no hifi THEATERS (no zone in data/ files an `area`), so
# Hormuz and Yemen keep their point halos; Yemen's critical halo sits beside Tigray's mark. With all 7 free the 300-step
# DFS (and a 1,500-step test run, 03:40 ET) found no full placement; with Lebanon numbered, Tigray tucks EAST of its mark
# and the other 5 keep their slots (search: 7 steps). Lebanon is numbered from 390 up until the data files the theaters.

class View:
    def __init__(s, lon0, lon1, lat0, lat1, w):
        s.lon0, s.lon1, s.lat0, s.lat1, s.w = lon0, lon1, lat0, lat1, w; s.h = round(w * (lat0 - lat1) / (lon1 - lon0))
    def p(s, lon, lat): return ((lon - s.lon0) / (s.lon1 - s.lon0) * s.w, (s.lat0 - lat) / (s.lat0 - s.lat1) * s.h)

class PhoneMap:
    def __init__(self, zones, pins, text_w, land_features, svg_pin, sev_color, crit_symbol_id="i-crit"):
        """zones: hotzones.json zones; pins: [(id, lon, lat, marker, precision)]; text_w(t, px): Plex SemiBold advance;
        svg_pin(x, y, marker, active, label, precision) -> svg; sev_color(level) -> screen hex."""
        self.zones, self.pins_in, self.text_w, self.land, self.svg_pin, self.sevc = zones, pins, text_w, land_features, svg_pin, sev_color
        self.crit = crit_symbol_id; self.v = self._view()

    # ---- geometry helpers (from hifi/phonemap.py) ----
    def crop_zones(self):
        w = WINDOW; return [z for z in self.zones if w['lon0'] <= z['lon'] <= w['lon1'] and w['lat_s'] <= z['lat'] <= w['lat_n']]
    def _view(self):
        zs = self.crop_zones(); lons = [z['lon'] for z in zs]; lats = [z['lat'] for z in zs]
        return View(round(min(lons) - PAD['w'], 2), round(max(lons) + PAD['e'], 2), round(max(lats) + PAD['n'], 2), round(min(lats) - PAD['s'], 2), MW)
    @staticmethod
    def mono_w(t, px=FONT, ls=LS): return len(t) * .6 * px + max(0, len(t) - 1) * ls * px
    def wrap_name(self, name):
        room = LAB_MAX - 2 * PAD_X - SLACK
        if self.text_w(name, FONT) <= room: return [name]
        ws = name.split(' '); best = None
        for i in range(1, len(ws)):
            l1, l2 = ' '.join(ws[:i]), ' '.join(ws[i:]); w = max(self.text_w(l1, FONT), self.text_w(l2, FONT))
            key = (l2.startswith('/'), w)
            if w <= room and (best is None or key < best[0]): best = (key, [l1, l2])
        if not best: raise ValueError(f"{name!r} needs more than 2 lines at {LAB_MAX}px")
        return best[1]
    def label_px(self, z, lines):
        crit = z['severity'] == 'critical'
        w = max(max(self.text_w(t, FONT) for t in lines), self.mono_w(z['severity'].upper()) + (14 if crit else 0)) + 2 * PAD_X + SLACK
        return (w, (len(lines) + 1) * LINE)
    def obstacles(self):
        v = self.v; pins = []
        from gia_build import markers as MK
        for pid, lon, lat, mk, prec in self.pins_in:
            x, y = v.p(lon, lat)
            hr = (MK.PRECISION_HALO[prec] + 1) if prec in MK.PRECISION_HALO else MK.SPRITE["static_active_px"] / 2 * 1.42
            if 0 <= x <= v.w and 0 <= y <= v.h: pins.append((x, y, hr))
        halos = {}
        for z in self.zones:
            hx, hy = v.p(z['lon'], z['lat']); hr = SEVR[z['severity']] * (v.w / 1000) ** .5 + 1
            if 0 <= hx <= v.w and 0 <= hy <= v.h: halos[z['id']] = (hx, hy, hr)
        return pins, halos

    def layout(self, box_w, reserved, K=6, budget=300):
        v = self.v; zs = self.crop_zones(); pins, halos = self.obstacles(); k = MW / box_w; g = GAP * k
        bmax = next((min(b['vmax'] - 34, BOX_MAX) for b in BANDS if b['solve'] == box_w), BOX_MAX)
        lead_cap = LEAD_MAX * MW / bmax; reserved = set(reserved)
        marks = {z['id']: v.p(z['lon'], z['lat']) + (halos.get(z['id'], (0, 0, SEVR[z['severity']] * (v.w / 1000) ** .5 + 1))[2],) for z in zs}
        cluster = {zid: [c for c in pins if math.hypot(c[0] - m[0], c[1] - m[1]) <= m[2]] for zid, m in marks.items()}
        def exit_pt(zid, a):
            x, y, r = marks[zid]; t = r
            while any(math.hypot(x + t * math.cos(a) - c[0], y + t * math.sin(a) - c[1]) < c[2] for c in cluster[zid]): t += .25
            return (x + t * math.cos(a), y + t * math.sin(a))
        numbox = lambda zid: box_at(marks[zid][:2], "middle", "middle", NUM_D, NUM_D, box_w)
        rects = [(zid, numbox(zid)) for zid in reserved if zid in marks]; leads = []
        def box_ok(bx):
            if bx[0] < g or bx[1] < g or bx[2] > v.w - g or bx[3] > v.h - g: return False
            if any(rect_gap(bx, o) < g for _, o in rects): return False
            if any(rect_circ_gap(bx, c) < g for c in pins): return False
            if any(rect_circ_gap(bx, c) < g for c in halos.values()): return False
            if any(seg_rect_gap(p, q, bx) < g for _, p, q in leads): return False
            return True
        def lead_ok(own, p0, q):
            if math.hypot(q[0] - p0[0], q[1] - p0[1]) > lead_cap + 1e-9: return False
            if any(seg_rect_gap(p0, q, o) < g for oid, o in rects if oid != own): return False
            if any(seg_circ_gap(p0, q, c) < g for c in pins if c not in cluster[own]): return False
            if any(seg_circ_gap(p0, q, c) < g for zid, c in halos.items() if zid != own): return False
            if any(seg_seg_gap(p0, q, a, b) < g for _, a, b in leads): return False
            return True
        def candidates(z):
            x, y, r = marks[z['id']]; lines = self.wrap_name(z['name']); wpx, hpx = self.label_px(z, lines); out = []
            mk = lambda A, ax, ay, lead, kind: dict(A=A, ax=ax, ay=ay, wpx=wpx, hpx=hpx, lines=lines, lead=lead, kind=kind)
            for dist, lead in ((r + (4 + GAP) * k, False), (r + 26 * k, True), (r + 50 * k, True)):
                for dx, dy in ((1, 0), (-1, 0), (0, -1), (0, 1), (.7, -.7), (-.7, -.7), (.7, .7), (-.7, .7)):
                    A = (x + dx * dist, y + dy * dist)
                    ax = "start" if dx > .3 else "end" if dx < -.3 else "middle"; ay = "middle" if abs(dy) < .3 else ("bottom" if dy < 0 else "top")
                    bx = box_at(A, ax, ay, wpx, hpx, box_w)
                    if not box_ok(bx): continue
                    p0 = exit_pt(z['id'], math.atan2(dy, dx))
                    if lead and math.hypot(A[0] - p0[0], A[1] - p0[1]) < 12 * k: continue
                    if lead and not lead_ok(z['id'], p0, A): continue
                    out.append(mk(A, ax, ay, (p0, A) if lead else None, "ring" if lead else "slot"))
            tk = []; R = int(lead_cap + r) + 2
            for ix in range(int(x) - R, int(x) + R + 1):
                for iy in range(int(y) - R, int(y) + R + 1):
                    ax = "end" if ix <= x - 1 else "start" if ix >= x + 1 else "middle"; ay = "top" if iy >= y else "bottom"
                    d0 = math.hypot(ix - x, iy - y) - r
                    if d0 < 12 * k - 1e-9 and not cluster[z['id']] or d0 > lead_cap: continue
                    bx = box_at((ix, iy), ax, ay, wpx, hpx, box_w)
                    qx = min(max(x, bx[0]), bx[2]); qy = min(max(y, bx[1]), bx[3])
                    if abs(qx - ix) > .01 or abs(qy - iy) > .01: continue
                    tk.append((d0, (ix, iy), ax, ay, bx))
            tk.sort(key=lambda t: t[0]); kept = []
            for d0, A, ax, ay, bx in tk:
                if any(math.hypot(A[0] - B[0], A[1] - B[1]) < 4 * k for B in kept): continue
                if not box_ok(bx): continue
                p0 = exit_pt(z['id'], math.atan2(A[1] - y, A[0] - x)); dl = math.hypot(A[0] - p0[0], A[1] - p0[1])
                if dl < 12 * k - 1e-9: continue
                if not lead_ok(z['id'], p0, A): continue
                kept.append(A); out.append(mk(A, ax, ay, (p0, A), "tuck"))
                if len(kept) >= K: break
            return out[:K]
        order = [z for z in sorted(zs, key=lambda z: (-SEV_ORDER.index(z['severity']), z['name'])) if z['id'] not in reserved]
        best = [None]; steps = [0]
        def dfs(i, placed):
            steps[0] += 1
            if best[0] is None or len(placed) > len(best[0]): best[0] = list(placed)
            if i == len(order): return True
            if steps[0] > budget: return False
            z = order[i]
            for c in candidates(z):
                c.update(id=z['id'], name=z['name'], sev=z['severity'], mark=marks[z['id']])
                rects.append((z['id'], box_at(c['A'], c['ax'], c['ay'], c['wpx'], c['hpx'], box_w)))
                if c['lead']: leads.append((z['id'],) + tuple(c['lead']))
                placed.append(c)
                if dfs(i + 1, placed): return True
                placed.pop(); rects.pop()
                if c['lead']: leads.pop()
            return False
        full = dfs(0, []); items = best[0]; ids = {it['id'] for it in items}
        numbered = [dict(id=z['id'], name=z['name'], sev=z['severity'], mark=marks[z['id']])
                    for z in sorted(zs, key=lambda z: (-SEV_ORDER.index(z['severity']), z['name'])) if z['id'] not in ids]
        numbered.sort(key=lambda n: (n['id'] not in reserved, n['name']))
        for i, n in enumerate(numbered): n['n'] = i + 1
        return dict(items=items, numbered=numbered, pins=pins, halos=halos, zones=zs, solved_at=box_w, complete=full, steps=steps[0], cluster=cluster)
    def layouts(self):
        LS_ = {b['id']: self.layout(b['solve'], b['number']) for b in BANDS}
        for b in BANDS: self.place_badges(LS_[b['id']], [bw for vw, bw in VIEWPORTS.items() if b['vmin'] <= vw <= b['vmax']])
        return LS_
    def place_badges(self, L, widths):
        """r4 (Director 04:24 item 4; QA round 5 §5): a numbered badge sits on its mark unless that leaves < GAP px (+0.5 margin)
        to any pin, label, leader, other badge or other zone's halo at ANY width of its band; then it moves to the nearest
        free spot within 12 px of the mark (searched at the band's narrowest width; checked at every width)."""
        v = self.v
        def ok(n, at, done):
            for bw in widths:
                s_ = bw / MW; nb = box_at(at, "middle", "middle", NUM_D, NUM_D, bw); need = (GAP + .5) / s_
                if nb[0] < 0 or nb[1] < 0 or nb[2] > v.w or nb[3] > v.h: return False
                if any(rect_circ_gap(nb, c) < need for c in L['pins'] if c not in L['cluster'][n['id']]): return False   # own pins sit on the mark
                if any(rect_gap(nb, box_at(it['A'], it['ax'], it['ay'], it['wpx'], it['hpx'], bw)) < need for it in L['items']): return False
                if any(seg_rect_gap(it['lead'][0], it['lead'][1], nb) < need for it in L['items'] if it['lead']): return False
                if any(rect_gap(nb, box_at(o['at'], "middle", "middle", NUM_D, NUM_D, bw)) < need for o in done): return False
                if any(rect_circ_gap(nb, c) < need for hz, c in L['halos'].items() if hz != n['id']): return False
            return True
        done = []
        for n in L['numbered']:
            x, y, _ = n['mark']; k = MW / min(widths); best = None
            for rad in [0] + [i * .5 for i in range(1, 25)]:          # 0..12 px in .5 px steps (at the narrowest width)
                for a in range(0, 360, 15) if rad else [0]:
                    at = (x + rad * k * math.cos(math.radians(a)), y - rad * k * math.sin(math.radians(a)))
                    if ok(n, at, done): best = (rad, a, at); break
                if best: break
            n['at'] = best[2] if best else (x, y); n['moved_px'] = best[0] if best else None; done.append(n)

    # ---- markup ----
    def _land(self):
        v = self.v; out = []
        for f in self.land:
            gm = f['geometry']; polys = gm['coordinates'] if gm['type'] == 'MultiPolygon' else [gm['coordinates']]
            for poly in polys:
                pts = []; last = None
                for lon, lat in [pt[:2] for pt in poly[0]]:
                    x, y = v.p(lon, lat); q = (round(x), round(y))
                    if q != last: pts.append(q); last = q
                if len(pts) < 3: continue
                xs = [a for a, _ in pts]; ys = [b for _, b in pts]
                if max(xs) < -20 or min(xs) > v.w + 20 or max(ys) < -20 or min(ys) > v.h + 20 or max(xs) - min(xs) > v.w * 4: continue
                out.append("M" + "L".join(f"{x} {y}" for x, y in pts) + "Z")
        return "".join(out)
    def html(self, LS_=None):
        LS_ = LS_ or self.layouts(); v = self.v; L0 = next(iter(LS_.values()))
        P = [f'<svg class="mp-phone" preserveAspectRatio="none" viewBox="0 0 {v.w} {v.h}" aria-hidden="true" focusable="false">',
             f'<rect class="sea" width="{v.w}" height="{v.h}" fill="#0a1a2a"/><path class="land" d="{self._land()}" fill="#1c2a3a" stroke="#3a4f66" stroke-width=".5"/>']
        for zid, (x, y, r) in L0['halos'].items():
            z = next(z for z in self.zones if z['id'] == zid); c = self.sevc(z['severity'])
            P.append(f'<circle class="halo hz hz-{z["severity"]}" data-z="{zid}" cx="{x:.1f}" cy="{y:.1f}" r="{r - 1:.1f}" fill="{c}" fill-opacity=".12" stroke="{c}" stroke-width="1.2"/>')
        for pid, lon, lat, mk, prec in self.pins_in:
            x, y = v.p(lon, lat)
            if 0 <= x <= v.w and 0 <= y <= v.h: P.append(self.svg_pin(x, y, mk, True, None, prec).replace('<g class="mk"', '<g class="mk pin"', 1))
        for b, L in LS_.items():
            P.append(f'<g class="mp-b-{b}">' + "".join(
                f'<line class="lead{" tuck" if it["kind"] == "tuck" else ""}" data-z="{it["id"]}" x1="{it["lead"][0][0]:.1f}" y1="{it["lead"][0][1]:.1f}" x2="{it["lead"][1][0]:.1f}" y2="{it["lead"][1][1]:.1f}" vector-effect="non-scaling-stroke"/>'
                for it in L['items'] if it['lead']) + '</g>')
        P.append('</svg>')
        layers = "".join(f'<div class="mp-labs mp-b-{b}" aria-hidden="true">{self._labels(L)}</div>' for b, L in LS_.items())
        return f'<div class="mp-box"><div class="mp-ar" style="padding-top:{100 * v.h / v.w:.4f}%">{"".join(P)}{layers}</div></div>'
    def _pct(self, x, y): return f"left:{100 * x / self.v.w:.3f}%;top:{100 * y / self.v.h:.3f}%"
    def _labels(self, L):
        out = []
        for it in L['items']:
            x, y = it['A']; crit = it['sev'] == 'critical'
            gl = f'<svg class="critg" aria-hidden="true" viewBox="0 0 32 32"><use href="#{self.crit}"/></svg>' if crit else ''
            out.append(f'<span class="mpl x-{it["ax"]} y-{it["ay"]}" style="{self._pct(x, y)}" data-z="{it["id"]}"><b>{"<br>".join(_esc(t) for t in it["lines"])}</b><i class="s-{it["sev"]}-t">{gl}{_esc(it["sev"].upper())}</i></span>')
        for nb in L['numbered']:
            x, y = nb.get('at', nb['mark'][:2]); out.append(f'<span class="mpn nm-{nb["sev"]}" style="{self._pct(x, y)}" data-z="{nb["id"]}">{nb["n"]}</span>')
        return "".join(out)
    def extras(self, LS_=None, href=lambda zid: f"history/zone-{zid}.html", full_map_icon=""):
        LS_ = LS_ or self.layouts(); inn = {z['id'] for z in self.crop_zones()}
        out = [z for z in sorted(self.zones, key=lambda z: (-SEV_ORDER.index(z['severity']), z['name'])) if z['id'] not in inn]
        leg = "".join(f'<ol class="mp-num mp-b-{b}">' + "".join(f'<li><span class="mk">{n["n"]}</span><a href="{href(n["id"])}">{_esc(n["name"])}</a> <span class="sv sv-{n["sev"]}">{SEV_WORD[n["sev"]]}</span></li>' for n in L['numbered']) + '</ol>'
                      for b, L in LS_.items() if L['numbered'])
        also = ('<p class="mp-also"><span class="lbl">Also active</span> ' + ", ".join(f'<a href="{href(z["id"])}">{_esc(z["name"])}</a>' for z in out) + '</p>') if out else ''
        return f'<div class="mp-ph">{leg}{also}<a class="mp-full" href="map.html"><span>Open the full map</span>{full_map_icon}</a></div>'

    def verify(self, LS_=None):
        """every band width in CSS px: strict >= GAP px between name boxes, markers, pins, halos, leaders; leaders <= 70 px;
        labels <= 140 px; every label = its full hotzones.json name (exemptions as hifi/phonemap.verify)."""
        LS_ = LS_ or self.layouts(); out = {}; names = {z['id']: z['name'] for z in self.zones}
        for vw, bw in VIEWPORTS.items():
            L = LS_[next(b['id'] for b in BANDS if b['vmin'] <= vw <= b['vmax'])]; s_ = bw / MW; v = self.v
            R = [(it['id'], 'label', box_at(it['A'], it['ax'], it['ay'], it['wpx'], it['hpx'], bw)) for it in L['items']]
            R += [(n['id'], 'number', box_at(n.get('at', n['mark'][:2]), "middle", "middle", NUM_D, NUM_D, bw)) for n in L['numbered']]
            S = [(it['id'],) + tuple(it['lead']) for it in L['items'] if it['lead']]
            gaps = []; bad = []
            def chk(kind, a, b, gu):
                gp = gu * s_; gaps.append((round(gp, 2), kind, a, b))
                if gp < GAP - 1e-6: bad.append((kind, a, b, round(gp, 2)))
            for i, (ia, ta, ra) in enumerate(R):
                for ib, tb, rb in R[i + 1:]: chk(f"{ta}/{tb}", ia, ib, rect_gap(ra, rb))
                for j, c in enumerate(L['pins']):
                    if not (ta == 'number' and c in L['cluster'][ia]): chk(f"{ta}/pin", ia, f"pin{j}", rect_circ_gap(ra, c))   # r4: badges vs pins too (own mark's pins exempt)
                for hz, c in L['halos'].items():
                    if not (ta == 'number' and hz == ia): chk(f"{ta}/halo", ia, hz, rect_circ_gap(ra, c))
                if ra[0] < 0 or ra[1] < 0 or ra[2] > v.w or ra[3] > v.h: bad.append(("frame", ia))
                if ta == 'label' and (ra[2] - ra[0]) * s_ > LAB_MAX + 1e-6: bad.append(("label>140px", ia))
            for i, (iz, p0, q) in enumerate(S):
                ln = math.hypot(q[0] - p0[0], q[1] - p0[1]) * s_
                if ln > LEAD_MAX + 1e-6: bad.append(("leader>70px", iz, round(ln, 1)))
                for ib, tb, rb in R:
                    if not (ib == iz and tb == 'label'): chk(f"leader/{tb}", iz, ib, seg_rect_gap(p0, q, rb))
                for j, c in enumerate(L['pins']):
                    if c not in L['cluster'][iz]: chk("leader/pin", iz, f"pin{j}", seg_circ_gap(p0, q, c))
                for hz, c in L['halos'].items():
                    if hz != iz: chk("leader/halo", iz, hz, seg_circ_gap(p0, q, c))
                for jz, a2, b2 in S[i + 1:]: chk("leader/leader", iz, jz, seg_seg_gap(p0, q, a2, b2))
            for it in L['items']:
                if ' '.join(it['lines']) != names[it['id']]: bad.append(("name!=hotzones.json", it['id']))
            tg = next((it for it in L['items'] if it['id'] == 'tigray'), None)
            out[vw] = dict(box_px=bw, placed=len(L['items']), numbered=[n['id'] for n in L['numbered']], overlaps=bad,
                           min_gap=min(gaps) if gaps else None, badge_pin_min=min((g for g in gaps if g[1] == 'number/pin'), default=None),
                           badges={n['id']: dict(moved_px=n.get('moved_px')) for n in L['numbered']}, leaders_px={iz: round(math.hypot(q[0] - p0[0], q[1] - p0[1]) * s_, 1) for iz, p0, q in S},
                           tigray=dict(east=tg['A'][0] > tg['mark'][0], kind=tg['kind']) if tg else None,
                           lines={it['id']: it['lines'] for it in L['items']})
        return out

def box_at(A, ax, ay, wpx, hpx, box_w):
    k = MW / box_w; w, h = wpx * k, hpx * k; x, y = A
    x0 = x if ax == "start" else x - w if ax == "end" else x - w / 2
    y0 = y if ay == "top" else y - h if ay == "bottom" else y - h / 2
    return (x0, y0, x0 + w, y0 + h)
def _pt_rect(px, py, r): return math.hypot(max(r[0] - px, 0, px - r[2]), max(r[1] - py, 0, py - r[3]))
def rect_gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2]); dy = max(b[1] - a[3], a[1] - b[3])
    return max(dx, dy) if dx <= 0 and dy <= 0 else math.hypot(max(dx, 0), max(dy, 0))
def rect_circ_gap(a, c):
    cx, cy, r = c
    return -r if a[0] <= cx <= a[2] and a[1] <= cy <= a[3] else _pt_rect(cx, cy, a) - r
def _seg_pts(p, q, n=120): return [(p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n) for i in range(n + 1)]
def seg_rect_gap(p, q, a): return min((-1 if (a[0] < x < a[2] and a[1] < y < a[3]) else _pt_rect(x, y, a)) for x, y in _seg_pts(p, q))
def _pt_seg(x, y, p, q):
    vx, vy = q[0] - p[0], q[1] - p[1]; L2 = vx * vx + vy * vy or 1e-9
    t = max(0, min(1, ((x - p[0]) * vx + (y - p[1]) * vy) / L2)); return math.hypot(x - p[0] - t * vx, y - p[1] - t * vy)
def seg_circ_gap(p, q, c): return _pt_seg(c[0], c[1], p, q) - c[2]
def seg_seg_gap(p, q, a, b): return min(min(_pt_seg(x, y, a, b) for x, y in _seg_pts(p, q, 60)), min(_pt_seg(x, y, p, q) for x, y in _seg_pts(a, b, 60)))

# CSS: the Designer's v2 block + the 03:10 fix block (site.css), ported to this build's tokens; screen <=671 px only.
CSS = """.mp-box,.mp-ph{display:none}
@media screen and (max-width:671px){
#gia-fallback a.maplink{display:block;min-height:0;min-width:0}
.maplink svg.wmap{display:none}.maplink .mapopen{display:none}
.mp-box{display:block;width:100%;max-width:390px;margin:0 auto}.mp-ph{display:block;padding:12px 0 0}}
@media screen and (max-width:389px){.mp-b-b{display:none}}
@media screen and (min-width:390px){.mp-b-a{display:none}}
.mp-ar{position:relative;height:0;overflow:hidden}
#gia-fallback .mp-ar>svg.mp-phone{position:absolute;top:0;left:0;width:100%;height:100%;display:block}
.mp-labs{position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none}
.mpl{position:absolute;display:block;padding:0 3px;white-space:nowrap;font-kerning:normal;text-shadow:0 0 2px #0b0f14,0 0 2px #0b0f14,0 0 3px #0b0f14}
.mpl b{display:block;font:600 11px/13px "IBM Plex Sans",system-ui,sans-serif;color:var(--gia-label,#f3efe7)}
.mpl i{display:flex;align-items:center;gap:3px;font:500 11px/13px "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.04em;font-style:normal}
#gia-fallback .mpl svg.critg{width:11px;height:11px;fill:var(--gia-sev-glyph);flex:none}   /* beats Today's #gia-fallback svg{width:100%} */
.mpl.x-start{text-align:left}.mpl.x-end i{justify-content:flex-end}.mpl.x-middle i{justify-content:center}.mpl.x-end{text-align:right}.mpl.x-middle{text-align:center}
.mpl.x-start.y-top{transform:none}.mpl.x-start.y-middle{transform:translate(0,-50%)}.mpl.x-start.y-bottom{transform:translate(0,-100%)}
.mpl.x-end.y-top{transform:translate(-100%,0)}.mpl.x-end.y-middle{transform:translate(-100%,-50%)}.mpl.x-end.y-bottom{transform:translate(-100%,-100%)}
.mpl.x-middle.y-top{transform:translate(-50%,0)}.mpl.x-middle.y-middle{transform:translate(-50%,-50%)}.mpl.x-middle.y-bottom{transform:translate(-50%,-100%)}
.s-critical-t{color:var(--gia-sev-critical-tx,var(--gia-sev-critical))}.s-high-t{color:var(--gia-sev-high)}.s-elevated-t{color:var(--gia-sev-elevated)}.s-watch-t{color:var(--gia-sev-watch)}
.mpn{position:absolute;width:20px;height:20px;box-sizing:border-box;margin:-10px 0 0 -10px;border-radius:50%;border:1.5px solid;background:#0b0f14;display:grid;place-items:center;font:500 11px/1 "IBM Plex Mono",ui-monospace,monospace;color:var(--gia-label,#f3efe7)}
.mpn.nm-critical{border-color:var(--gia-sev-critical)}.mpn.nm-high{border-color:var(--gia-sev-high)}.mpn.nm-elevated{border-color:var(--gia-sev-elevated)}.mpn.nm-watch{border-color:var(--gia-sev-watch)}
svg.mp-phone .lead{stroke:#aaa398;stroke-width:1}svg.mp-phone .lead.tuck{stroke:#8d8d8d}
.mp-num{list-style:none;margin:0 0 8px;padding:0}.mp-num li{display:flex;align-items:center;gap:8px;min-height:44px;border-top:1px solid #393939;font:400 14px/20px "IBM Plex Sans",system-ui,sans-serif}
.mp-num .mk{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;border:1.5px solid #d0cac0;font:500 11px/1 "IBM Plex Mono",ui-monospace,monospace;color:var(--gia-label,#f3efe7);flex:none}
.mp-num a{display:inline-flex;align-items:center;min-height:44px}
.sv{font:500 12px/16px "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.04em}.sv-critical{color:var(--gia-sev-critical-tx,var(--gia-sev-critical))}.sv-high{color:var(--gia-sev-high)}.sv-elevated{color:var(--gia-sev-elevated)}.sv-watch{color:var(--gia-sev-watch)}
.mp-also{margin:0;font:400 14px/24px "IBM Plex Sans",system-ui,sans-serif;color:#d0cac0}.mp-also .lbl{margin-right:6px}
.mp-also a{display:inline-flex;align-items:center;min-height:24px}
.mp-full{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:44px;box-sizing:border-box;margin-top:8px;padding:10px 0;border-top:1px solid #393939;border-bottom:1px solid #393939;color:var(--gia-label,#f3efe7);text-decoration:none;font:600 14px/20px "IBM Plex Sans",system-ui,sans-serif}
.mp-full .ci{width:16px;height:16px;fill:currentColor}
@media print{.mp-box,.mp-ph{display:none!important}}"""
