#!/usr/bin/env python3
"""GIA static intel dashboard builder (no JS required).
Reads data/{stories,entities,hotzones,storylines,relationships}.json (+ ne110.geojson);
writes dashboard.html, history/*.html, and history/path-<root>/slide-NN.html Path-to-today slideshows.
Schema: data/SCHEMA.md"""
import json, math, html, os, glob, shutil
from collections import defaultdict
D=os.path.dirname(os.path.abspath(__file__)); J=lambda f: json.load(open(f"{D}/data/{f}"))
S=J("stories.json"); ENTS=J("entities.json"); HZ=J("hotzones.json"); SL=J("storylines.json")
RELS=J("relationships.json") if os.path.exists(f"{D}/data/relationships.json") else []
from gia_build.geo import anchor as _anchor, svg_path as _svg_path
for _z in HZ['zones']:  # v7 area zones may omit lat/lon: label anchor inside the area (never a story pin)
    if _z.get('area') and ('lat' not in _z or 'lon' not in _z): _z['lon'],_z['lat']=_anchor(_z['area'])
E={e['id']:e for e in ENTS}; ST={s['id']:s for s in S}; SLD={l['id']:l for l in SL}; ZD={z['id']:z for z in HZ['zones']}
esc=lambda s: html.escape(str(s),quote=True)
REG=["Americas","Europe","Middle East","Africa","Russia/Eurasia","Asia-Pacific"]
CONF_W={"likely":3,"possible":2,"speculative":1}
for _s in S: _s.setdefault('causes',[]); _s['effects']=[]
for _s in S:
    for _c in _s['causes']:
        if _c['story'] in ST: ST[_c['story']]['effects'].append(dict(story=_s['id'],why=_c['why'],confidence=_c['confidence']))
by=defaultdict(list)
for s in S:
    for e in s['entities']: by[e].append(s)
eds=sorted({s.get('edition') or s['date'] for s in S}); ed=eds[-1] if eds else ""
LATEST=[s for s in S if (s.get('edition') or s['date'])==ed]
def ddisp(s):
    p=s.get('date_precision','day'); d=s['date']; return d[:4] if p=='year' else d[:7] if p=='month' else d[:10]

# ---- geographic projection + country outlines (cached) ----
LON0,LON1,LAT0,LAT1=-120,150,-40,72; MW,MH=1000,int(1000*(LAT1-LAT0)/(LON1-LON0))
pj=lambda lon,lat:((lon-LON0)/(LON1-LON0)*MW,(LAT1-lat)/(LAT1-LAT0)*MH)
G=json.load(open(f"{D}/data/ne110.geojson"))
COUNTRY_PATHS=[]
for f in G['features']:
    g=f['geometry']; polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]; d=""
    for poly in polys:
        for ring in poly: d+="M"+"L".join("%.1f,%.1f"%pj(*pt[:2]) for pt in ring)+"Z"
    COUNTRY_PATHS.append(f'<path d="{d}"><title>{esc(f["properties"].get("NAME",""))}</title></path>')
from gia_build import ui_tokens as UI
SEV={k:(UI.sev(k),r) for k,r in (("critical",13),("high",10),("elevated",8),("watch",6))}  # colours: ui_tokens.SEV only

from gia_build import markers as MK   # ONE definition of marker colour / glyph / shape per type (tokens --gia-marker-*)
MARK_COLOR={k:MK.hexcolor(k) for k in MK.MARKERS}   # hex values, for the no-CSS fallback and reports only

def story_places(s):
    """Places the story names and that already have coordinates. Never a hot-zone centroid."""
    out=[]
    for ident in s.get("where") or []:
        ent=E.get(ident)
        lat,lon=(ent or {}).get("lat"),(ent or {}).get("lon")
        if ent and ent.get("type")=="place" and isinstance(lat,(int,float)) and isinstance(lon,(int,float)):
            out.append(ent)
    return out
# Today pins (2D map, Leaflet, globe): shape = the most common event type among today's stories at the place (ties kinetic first)
_pm={}
for _s0 in LATEST:
    for _e0 in story_places(_s0): _pm.setdefault(_e0["id"],[]).append(_s0.get("marker") or "political")
PLACE_MARKER={k: MK.dominant(v) for k,v in _pm.items()}

# Per-type shapes (Designer spec.md 19 Oct): ONE geometry for every surface, MK.SHAPE_SVG on a 16-unit grid, translated by
# -8 and scaled to SPRITE active_px / past_px. Casing = --gia-sprite-outline drawn under the shape (fill: stroke 2w with
# paint-order=stroke, i.e. w outside; stroke shapes: same path at w+2.4 underneath), exactly as the Cesium sprite() does.
_OL="var(--gia-sprite-outline,#0b0f14)"
def _pin_shape(x,y,shp,c,active):
    d,paint,w=MK.SHAPE_SVG.get(shp,MK.SHAPE_SVG["ring"]); px=MK.SPRITE["static_active_px" if active else "static_past_px"]
    tf=f'transform="translate({x:.1f} {y:.1f}) scale({px/16:.4g}) translate(-8 -8)"'
    if paint=="fill":
        return f'<path d="{d}" {tf} style="fill:{c};stroke:{_OL}" stroke-width="{2*w:g}" stroke-linejoin="round" paint-order="stroke"/>'
    return (f'<path d="{d}" {tf} fill="none" style="stroke:{_OL}" stroke-width="{w+2.4:g}" stroke-linecap="round"/>'
            f'<path d="{d}" {tf} fill="none" style="stroke:{c}" stroke-width="{w:g}" stroke-linecap="round"/>')
def halo_r(precision, active=True):
    """Halo ring radius = place precision (spec 'Palette rulings 01:50' §2; 2D maps only, Director 02:00); past x0.75."""
    r=MK.PRECISION_HALO.get(precision or "", MK.HALO["default"])
    return r if active else r*MK.HALO["past_scale"]
def precision_halo(x,y,precision,c,active=True):
    """Halo ring in the pin's own marker colour, 1.5 px; sector dashed 4 / 2.5. No precision filed -> no halo."""
    if precision not in MK.PRECISION_HALO: return ""
    dash=MK.HALO["dash"].get(precision); r=halo_r(precision,active)
    return (f'<circle class="ph" data-precision="{precision}" cx="{x:.1f}" cy="{y:.1f}" r="{r:g}" fill="none" '
            f'style="stroke:{c}" stroke-width="{MK.HALO["stroke"]}"' + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")

def svg_pin(x, y, marker, active=True, label=None, precision=None):
    # Past pins: opacity 1 (Director 01:50 ET); past = smaller glyph (static 11 px), halo x0.75, lighter 400 11px label.
    k=MK.kind(marker); shp=MK.shape(k); c=MK.color(k)
    body=precision_halo(x,y,precision,c,active)+_pin_shape(x,y,shp,c,active)
    if label:
        fill,wt,size=MK.LABEL["active" if active else "past"]
        body+=f'<text class="pl{"" if active else " past"}" x="{x+11:.0f}" y="{y-7:.0f}" fill="{fill}" stroke="#0a1a2a" stroke-width="3" paint-order="stroke" font-size="{size}" font-weight="{wt}" font-family="IBM Plex Sans,Arial,sans-serif">{esc(label)}</text>'
    return f'<g class="mk" data-marker="{k}" data-shape="{shp}"{f' data-precision="{precision}"' if precision else ""}>{body}</g>'

def shape_legend():
    labels=tuple((k,MK.label(k)) for k in MK.MARKERS)
    bits=[]
    for marker,name in labels:
        bits.append(f'<span><svg width="18" height="18" viewBox="-10 -10 20 20" class="pinleg">{svg_pin(0,0,marker,True)}</svg>{name}</span>')
    return '<div class="legend"><b>Events</b> '+"".join(bits)+'</div>'

def precision_legend():
    """Halo key for the 2D world map (Today + map.html): neutral dot + halo ring (tx-1 / tx-2), never a type shape."""
    bits=[]
    for p,name in (("feature","exact site"),("city","city"),("sector","sector / area")):
        r=MK.PRECISION_HALO[p]; vb=r+2; dash=MK.HALO["dash"].get(p)
        ic=(f'<circle r="{r}" fill="none" stroke="{MK.LABEL["past"][0]}" stroke-width="{MK.HALO["stroke"]}"'+(f' stroke-dasharray="{dash}"' if dash else "")+'/>'
            f'<circle r="3" fill="{MK.LABEL["active"][0]}"/>')
        bits.append(f'<span><svg width="18" height="18" viewBox="{-vb} {-vb} {2*vb} {2*vb}" class="pinleg" aria-hidden="true">{ic}</svg>{name}</span>')
    return '<div class="legend plg"><b>Place precision (halo)</b> '+"".join(bits)+'</div>'

def map_svg(active=None, past=None, trail=None, now_place=None, now_date=None, step_n=None, step_total=None, story_title=None, prior_steps=None, region=None):
    """Path-slide map. Pins are event places. Hot-zone rings are not drawn."""
    active=list(active or []); past=list(past or [])
    points=[(p["lon"],p["lat"]) for p in active+past]
    if points:
        lons=[p[0] for p in points]; lats=[p[1] for p in points]
        span_lon=max(lons)-min(lons); span_lat=max(lats)-min(lats)
        pad_lon=max(1.4, span_lon*0.55+0.8); pad_lat=max(1.0, span_lat*0.55+0.6)
        lon0=max(LON0, min(lons)-pad_lon); lon1=min(LON1, max(lons)+pad_lon)
        lat0=max(LAT0, min(lats)-pad_lat); lat1=min(LAT1, max(lats)+pad_lat)
        if lon1-lon0<3: mid=(lon0+lon1)/2; lon0,lon1=mid-1.5,mid+1.5
        if lat1-lat0<2: mid=(lat0+lat1)/2; lat0,lat1=mid-1,mid+1
    else:
        REGION_VIEW={"Russia/Eurasia":(22,48,43,60),"Middle East":(32,62,12,36),"Africa":(-18,16,8,28),
                     "Asia-Pacific":(100,140,18,42),"Americas":(-125,-65,15,50),"Europe":(-5,40,36,62)}
        lon0,lon1,lat0,lat1=REGION_VIEW.get(region or "", (LON0,LON1,LAT0,LAT1))
    # local projection into fixed pixel box
    W,H=1000,560
    def lp(lon,lat):
        return ((lon-lon0)/(lon1-lon0)*W, (lat1-lat)/(lat1-lat0)*H)
    # rebuild country paths for this crop
    paths=[]
    for f in G['features']:
        g=f['geometry']; polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]; d=""
        for poly in polys:
            for ring in poly:
                pts=[]
                for pt in ring:
                    x,y=lp(pt[0],pt[1])
                    # keep all — SVG will clip via viewBox
                    pts.append("%.1f,%.1f"%(x,y))
                if pts: d+="M"+"L".join(pts)+"Z"
        if d: paths.append(f'<path d="{d}"/>')
    out=[f'<svg viewBox="0 0 {W} {H}" width="100%" class="wmap smap" xmlns="http://www.w3.org/2000/svg">',
         f'<rect class="sbg" width="{W}" height="{H}" fill="#071018"/>',
         f'<g class="sland" fill="#152030" stroke="#2a3f55" stroke-width="0.6">{"".join(paths)}</g>']
    if trail and len(trail)>=2:
        for i in range(len(trail)-1):
            a,b=trail[i],trail[i+1]
            if a["lat"]==b["lat"] and a["lon"]==b["lon"]: continue
            x1,y1=lp(a["lon"],a["lat"]); x2,y2=lp(b["lon"],b["lat"])
            mx,my=(x1+x2)/2,(y1+y2)/2; dx,dy=x2-x1,y2-y1; cx,cy=mx-dy*.25,my+dx*.25
            last=i==len(trail)-2
            out.append(f'<path d="M{x1:.0f},{y1:.0f}Q{cx:.0f},{cy:.0f} {x2:.0f},{y2:.0f}" fill="none" stroke="{UI.PATH}" stroke-width="{4 if last else 2}" opacity="{1 if last else .7}" stroke-dasharray="{"0" if last else "6 5"}"/>')
    for ent in past:
        x,y=lp(ent["lon"],ent["lat"])
        out.append(svg_pin(x,y,ent.get("_marker","political"),active=False,label=ent["name"]))
    for ent in active:
        x,y=lp(ent["lon"],ent["lat"])
        out.append(f'<a href="../entity-{ent["id"]}.html">{svg_pin(x,y,ent.get("_marker","political"),active=True,label=ent["name"])}</a>')
    place=esc(now_place or "No placed location")
    date=esc(now_date or '')
    step=f'Step {step_n}/{step_total}' if step_n else ''
    title=esc((story_title or '')[:72])
    out.append(f'<rect class="snow" x="16" y="12" width="640" height="78" rx="8" fill="#0b0f14" fill-opacity=".92" stroke="#c3a6ff" stroke-width="2"/>'
               f'<text x="28" y="34" fill="#c3a6ff" font-size="13" font-weight="600" font-family="Arial">NOW · {date} · {step}</text>'
               f'<text x="28" y="54" fill="#ffffff" font-size="15" font-weight="600" font-family="Arial">{place[:78]}</text>'
               f'<text x="28" y="74" fill="#c8d4e0" font-size="12" font-family="Arial">{title}</text>')
    if prior_steps:
        y=100
        out.append(f'<text x="28" y="{y}" fill="#7f8fa3" font-size="11" font-family="Arial">Path so far</text>'); y+=6
        for i,(pd,pt) in enumerate(prior_steps[-6:]):
            y+=18
            out.append(f'<rect x="28" y="{y-12}" width="8" height="8" rx="2" fill="#c3a6ff" opacity=".5"/>'
                       f'<text x="42" y="{y-4}" fill="#9aa8b8" font-size="11" font-family="Arial">{esc(pd)} · {esc(pt[:40])}</text>')
    out.append('</svg>')
    return "".join(out)

def _plex_adv():
    """r3: exact IBM Plex Sans SemiBold advances (hmtx, per 1000 em) from the shipped woff2, so label boxes match the ink
    the browser draws (the strict zero-overlap test). Falls back to the old class average if fontTools is missing."""
    try:
        from fontTools.ttLib import TTFont
        f=TTFont(os.path.join(os.path.dirname(os.path.abspath(__file__)),"vendor","fonts2","GIA-PlexSans-SemiBold.woff2"))
        cm=f.getBestCmap(); hm=f["hmtx"]; upm=f["head"].unitsPerEm
        return {chr(c):hm[g][0]/upm for c,g in cm.items()}
    except Exception: return None
_ADV=_plex_adv()
def _text_w(t, size=11, ls=0.0):
    """IBM Plex Sans SemiBold advance width at `size` px (+ letter-spacing in em per character)."""
    if _ADV: return sum(_ADV.get(ch,.6)+ls for ch in t)*size
    w=0
    for ch in t:
        w+= .30 if ch in "iljI.,'’:;|!()[] " else .82 if ch in "MWmw@" else .66 if ch.isupper() else .56
    return w*size

import csv as _csv
SHORT_NAMES={r['id']:r['short_name'] for r in _csv.DictReader(open(f"{D}/gia_build/storyline_short_names.csv",encoding="utf-8"))}
from gia_build.today import CRIT_PATH as _CRIT_PATH, ICON_CRIT as _ICON_CRIT, sev_word as _sev_word
MAP_STATS={}
DEBUG_LAB=set(filter(None,os.environ.get('GIA_DEBUG_LAB','').split(',')))
def world_map_dashboard(ls=9, labels_only=False, ns=11):
    """Today's static map (hi-fi fix pass §5). No links inside: the whole map is ONE link (added by the
    caller). Theater zones draw their sourced `area`; point zones a severity halo. Labels are placed by
    priority (highest severity first, then more of today's stories, then name): each tries 8 slots next
    to its mark, then leader-line rings at +26 and +50 px; obstacles are pins, other zones' halos,
    placed labels and the frame. A label with no free slot is hidden and listed in the SVG <desc>.
    r4 (Director 03:53 item 2): `ls` = level-word size in viewBox units (9 on screen). labels_only=True runs the same
    solver with the PRINT level-word size and returns only the label layer (labels, leaders, numbered markers) plus the
    numbered list, for the print-only <g class="prl">; the screen layer is <g class="scl">."""
    SEV_L=SEV; Z={z['id']:z for z in HZ['zones']}; JUDG="#c3a6ff"
    out=[f'<svg viewBox="0 0 {MW} {MH}" width="100%" class="wmap" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="wmap-t"><title id="wmap-t">Hot-zone map, edition {esc(ed)}: shaded areas and halos are hot zones, purple dashed arcs are analytic links, marks are places named in today\'s stories.</title><defs><symbol id="i-crit" viewBox="0 0 32 32"><path d="{_CRIT_PATH}"/></symbol><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L10,5L0,10z" fill="{JUDG}"/></marker></defs>',
         f'<rect class="sea" width="{MW}" height="{MH}" fill="#0a1a2a"/><g class="land" fill="#1c2a3a" stroke="#3a4f66" stroke-width=".5">{"".join(COUNTRY_PATHS)}</g>']
    for i,l in enumerate(HZ['links']):
        a,b=l['from'],l['to']
        if a not in Z or b not in Z: continue
        x1,y1=pj(Z[a]['lon'],Z[a]['lat']); x2,y2=pj(Z[b]['lon'],Z[b]['lat'])
        mx,my=(x1+x2)/2,(y1+y2)/2; dx,dy=x2-x1,y2-y1; k=.25 if i%2 else -.25; cx,cy=mx-dy*k,my+dx*k
        out.append(f'<path d="M{x1:.0f},{y1:.0f}Q{cx:.0f},{cy:.0f} {x2:.0f},{y2:.0f}" fill="none" class="lk" stroke="{JUDG}" stroke-width="1.6" stroke-dasharray="5 3" marker-end="url(#ah)" opacity=".8"><title>{esc(Z[a]["name"])} → {esc(Z[b]["name"])}: {esc(l["label"])}</title></path>')
    halos={}; anchors={}
    for z in HZ['zones']:
        x,y=pj(z['lon'],z['lat']); c,r=SEV_L[z['severity']]; anchors[z['id']]=(x,y,6 if z.get('area') else r*1.6)
        if z.get('area'):  # theater drawn as its sourced outline, in the zone's severity, not a ring
            out.append(f'<path class="hz hz-{z["severity"]}" d="{_svg_path(z["area"],pj)}" fill="{c}" fill-opacity=".14" stroke="{c}" stroke-width="1.2" stroke-dasharray="3 2"><title>{esc(z["name"])}: outline {esc(z["area_source"]["name"])}</title></path>')
            continue
        kl=UI.SEV.get(z['severity'],UI.SEV['watch'])[2]
        if UI.STATIC_HALO_OUTLINE and kl and kl!="none":  # per-level keyline hook, off on the static map by default
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r*1.6}" fill="none" stroke="{kl}" stroke-width="{2+2*UI.SEV_OUTLINE_PX}"/>')
        out.append(f'<circle class="hz hz-{z["severity"]}" cx="{x:.0f}" cy="{y:.0f}" r="{r*1.6}" fill="{c}" opacity=".12" stroke="{c}" stroke-width="2"><title>{esc(z["name"])} · {z["severity"]}</title></circle>')
        hr=r*1.6*.75; halos[z['id']]=(x-hr,y-hr,x+hr,y+hr)
    boxes=[]; pinc=[]; seen=set()
    for s in LATEST:
        for ent in story_places(s):
            if ent["id"] in seen: continue
            seen.add(ent["id"]); x,y=pj(ent["lon"],ent["lat"])
            prec=ent.get("precision"); _hp=(halo_r(prec) if prec in MK.PRECISION_HALO else MK.SPRITE["static_active_px"]/2)+1   # obstacle = halo + 1
            out.append(svg_pin(x,y,PLACE_MARKER.get(ent["id"],"political"),True,None,precision=prec)); boxes.append((x-_hp,y-_hp,x+_hp,y+_hp))
            # drawn extent of the pin (halo ring outer edge, or the glyph's casing circle) for the tight-clearance zones
            pinc.append((x,y,(halo_r(prec)+MK.HALO["stroke"]/2) if prec in MK.PRECISION_HALO else MK.SPRITE["static_active_px"]/2*1.42))
    NPIN=len(boxes)
    today={s['id'] for s in LATEST}; RANK={"critical":0,"high":1,"elevated":2,"watch":3}
    # Director 02:06: Tigray only -> halo clearance shrunk to the pins' drawn ink (exact box-vs-circle test, 0 px margin)
    # instead of the square halo+1 obstacle box; still zero overlap with any label, pin, halo or leader.
    TIGHT={"tigray"}; TIGHT_FALLBACK=[]
    LMAX=UI.LEADER_MAX_UNITS+UI.LEADER_EPS_PX*UI.MAP_VIEW_W/UI.MAP_PX_1440   # 70 SCREEN px at 1440 (Director 03:03) = 53.85 units; every pass
    GAP=UI.LABEL_GAP; grow=lambda b:(b[0]-GAP,b[1]-GAP,b[2]+GAP,b[3]+GAP)   # strict: label boxes may not touch
    def _box_circ(bx,c): qx=min(max(c[0],bx[0]),bx[2]); qy=min(max(c[1],bx[1]),bx[3]); return math.hypot(qx-c[0],qy-c[1])<c[2]
    def _seg_circ(x1,y1,x2,y2,c):
        dx,dy=x2-x1,y2-y1; L=dx*dx+dy*dy; t=0 if L==0 else max(0,min(1,((c[0]-x1)*dx+(c[1]-y1)*dy)/L))
        return math.hypot(x1+t*dx-c[0],y1+t*dy-c[1])<c[2]
    def _ray_exit(x,y,ux,uy,c):   # distance along the unit ray from (x,y), inside circle c, to where it leaves c
        fx,fy=x-c[0],y-c[1]; b=fx*ux+fy*uy; cc=fx*fx+fy*fy-c[2]*c[2]; return -b+math.sqrt(max(0,b*b-cc))
    def obst(own): return boxes[NPIN:] if own in TIGHT else boxes
    def hit(bx, own):
        if bx[0]<2 or bx[1]<2 or bx[2]>MW-2 or bx[3]>MH-2: return True
        bx=grow(bx); ov=lambda o: not(bx[2]<o[0] or bx[0]>o[2] or bx[3]<o[1] or bx[1]>o[3])   # touching = hit (r3 strict)
        if any(seg_hits(*sg,bx) for k,sg in segs.items() if k!=own): return True   # r3: no label box on another zone's leader
        if own in TIGHT and any(_box_circ(bx,c) for c in pinc): return True
        return any(ov(o) for o in obst(own)) or any(ov(o) for k,o in halos.items() if k!=own)
    def hit_why(bx, own):
        ov=lambda o: not(bx[2]<=o[0] or bx[0]>=o[2] or bx[3]<=o[1] or bx[1]>=o[3])
        return (["frame"] if (bx[0]<2 or bx[1]<2 or bx[2]>MW-2 or bx[3]>MH-2) else [])+[("box",[round(v) for v in o]) for o in boxes if ov(o)]+[k for k,o in halos.items() if k!=own and ov(o)]
    hidden=[]; shortened=[]; placed_n=0; crit_w=_text_w("CRITICAL",ls,.04); LAB_GEOM=[]
    # Director 02:06: storyline short names never replace a zone's name on a map label (short_for() removed; the 00:52
    # fallback to the CSV short name of the zone's main storyline is how 'Global oil' / 'Houthis vs Saudi' leaked in).
    # Greedy by ring, then by priority: every label gets its nearest free slot before any label takes a leader ring
    # (so one long leader label cannot take a slot a later label needed next to its own mark). Full names only.
    order=sorted(HZ['zones'],key=lambda z:(RANK[z['severity']],-len(today&set(z.get('stories') or [])),z['name']))
    SLOTS=((1,0),(-1,0),(0,-1),(0,1),(.7,-.7),(-.7,-.7),(.7,.7),(-.7,.7))
    # last pass: a label that found no slot at the standard clearance gets ONE more tuck at the tight (drawn-ink) clearance
    # used for Tigray; only if that also fails does it become a numbered marker (the fallback).
    passes=[(0,4,False,None),(0,26,True,None),(0,50,True,None),(0,12,True,(-1,0)),(0,12,True,'tuck'),(0,12,True,'tight-tuck')]
    def seg_hits(x1,y1,x2,y2,bx):  # does the leader segment cross box bx (Liang-Barsky clip)?
        t0,t1=0.0,1.0; dx,dy=x2-x1,y2-y1
        for pp,qq in ((-dx,x1-bx[0]),(dx,bx[2]-x1),(-dy,y1-bx[1]),(dy,bx[3]-y1)):
            if pp==0:
                if qq<0: return False
            else:
                t=qq/pp
                if pp<0: t0=max(t0,t)
                else: t1=min(t1,t)
        return t0<t1-1e-6
    segs={}   # r3: placed leader segments by zone (a new leader may not cross one, a new label may not sit on one)
    def ss(a,b):
        (x1,y1,x2,y2),(x3,y3,x4,y4)=a,b; d=(x2-x1)*(y4-y3)-(y2-y1)*(x4-x3)
        if d==0: return False
        u=((x3-x1)*(y4-y3)-(y3-y1)*(x4-x3))/d; v=((x3-x1)*(y2-y1)-(y3-y1)*(x2-x1))/d; return 0<u<1 and 0<v<1
    # Director 03:20: the DESKTOP map keeps Tigray below the Sudan (Kordofan / Darfur) label, west of its mark (tuck only,
    # under the same 70 screen-px cap and strict gaps); if no such slot exists it is numbered (03:06 rule), never moved east.
    TUCK_RULES={"tigray":{"below":"sudan-kordofan","side":"west"}}
    def tuck(zid,W,H=24,reach=120):
        """Designer's tuck pass (spec.md 19 Oct): shortest free leader, scanning boxes west then east of the mark on a
        1-unit grid; leader from the ring edge to the box's nearest point; it must not cross a label or pin box."""
        x,y,r=anchors[zid]; best=None
        own_pins=[c for c in pinc if math.hypot(c[0]-x,c[1]-y)<c[2]]   # pins drawn ON the mark (tight zones only)
        # west first (box right edge at or west of the mark: toward Sudan for Tigray, Director 01:23 ET), east only if none
        rule=TUCK_RULES.get(zid); below=None
        if rule:
            ref=done.get(rule["below"])
            if not ref: return None
            below=ref[3][3]+GAP
        for x1 in list(range(int(x)-reach,int(x)+1))+[None]+(list(range(int(x)+1,int(x)+reach)) if not rule else []):
            if x1 is None:
                if best: break
                continue
            for y0 in range(int(y)-reach,int(y)+reach):
                bx=(x1-W,y0,x1,y0+H)
                if below is not None and bx[1]<below: continue
                qx=min(max(x,bx[0]),bx[2]); qy=min(max(y,bx[1]),bx[3]); D=math.hypot(qx-x,qy-y)
                if zid in TIGHT:   # the leader starts where it leaves the zone's own pins (their halos sit on the mark)
                    ux,uy=((qx-x)/D,(qy-y)/D) if D else (0,1); s0=max([r]+[_ray_exit(x,y,ux,uy,c) for c in own_pins])
                else: s0=r
                d=D-s0
                if d<12 or d>LMAX or (best and d>=best[0]): continue   # closer slots were tried by the ring passes; 70 px cap
                if hit(bx,zid): continue
                ex,ey=x+(qx-x)*s0/D,y+(qy-y)*s0/D
                if any(seg_hits(ex,ey,qx,qy,o) for o in obst(zid)): continue
                if zid in TIGHT and any(_seg_circ(ex,ey,qx,qy,c) for c in pinc if c not in own_pins): continue
                if any(seg_hits(ex,ey,qx,qy,o) for k,o in halos.items() if k!=zid): continue
                if any(ss((ex,ey,qx,qy),sg) for k,sg in segs.items() if k!=zid): continue
                if best is None or d<best[0]: best=(d,bx,(ex,ey,qx,qy))
        return best   # None -> numbered fallback
    cand={}
    for z in order:
        cand[z['id']]=[z['name']]   # Director 02:06: a zone's map label is ALWAYS its name in data/hotzones.json
    done={}
    def attempt(z,vi,add,lead,only):
        """One solver pass for one zone; True if it placed the label."""
        if z['id'] in done: return True
        if vi>=len(cand[z['id']]): return False
        if z['id'] in TUCK_RULES and only not in ('tuck','tight-tuck'): return False   # ruled zones: tuck only
        x,y,r=anchors[z['id']]; sub=z['severity']; crit=sub=="critical"; name=cand[z['id']][vi]
        w=max(_text_w(name,ns),_text_w(sub.upper(),ls,.04)+(12*ls/9 if crit else 0))+6; hgt=ns+4+ls+(0 if ls==9 else round(.3*ls,2)); dist=r+add   # print box adds the big level word's font descent
        reach=120
        if only=='tight-tuck': TIGHT_FALLBACK.append(z['id']); TIGHT.add(z['id']); only='tuck'; reach=MW*2//10   # 200 units
        if only=='tuck':
            tk=tuck(z['id'],w,hgt,reach=reach)
            if DEBUG_LAB and z['id'] in DEBUG_LAB: print('tuck',name,tk)
            if tk:
                d_,bx,(ex,ey,qx,qy)=tk; done[z['id']]=(qx,qy,"end",bx,(ex,ey),name,vi==1,True); boxes.append(bx); segs[z['id']]=(ex,ey,qx,qy)
            return z['id'] in done
        for dx,dy in ([only] if only else SLOTS):
            cx,cy=x+dx*dist,y+dy*dist
            anc="start" if dx>0.3 else "end" if dx<-0.3 else "middle"
            x0=cx if anc=="start" else cx-w if anc=="end" else cx-w/2
            y0=cy-hgt/2 if abs(dy)<0.3 else (cy-hgt if dy<0 else cy)
            bx=(x0,y0,x0+w,y0+hgt)
            if DEBUG_LAB and z['id'] in DEBUG_LAB: print('try',name,dist,dx,dy,[round(v) for v in bx],hit_why(bx,z['id']))
            if lead and math.hypot(cx-x,cy-y)>LMAX: continue   # leader cap: longer -> keep looking, else numbered fallback
            if lead and (any(ss((x,y,cx,cy),sg) for k,sg in segs.items() if k!=z['id']) or any(seg_hits(x,y,cx,cy,o) for o in boxes[NPIN:])
                         or any(seg_hits(x,y,cx,cy,o) for k,o in halos.items() if k!=z['id'])   # r3: ring-pass leaders get the same
                         or any(_seg_circ(x,y,cx,cy,c) for c in pinc if math.hypot(c[0]-x,c[1]-y)>=max(c[2],r))): continue   # leader tests
            if not hit(bx,z['id']):
                done[z['id']]=(cx,cy,anc,bx,lead,name,vi==1,only is not None); boxes.append(bx)
                if lead: segs[z['id']]=(x,y,cx,cy)
                break
        return z['id'] in done
    for vi,add,lead,only in passes:
        for z in order: attempt(z,vi,add,lead,only)
    # r3 repair (Director 03:03/03:06): a label still unplaced under the 70 screen-px cap may take the slot of a nearby
    # placed label if that label can then be re-placed by the same solver order (nearest neighbours first). Only if no
    # swap works does it become a numbered marker + key row (03:06 rule).
    REPAIRED=[]
    def place_all(z): return any(attempt(z,*pp) for pp in passes)
    for z in order:
        if z['id'] in done: continue
        x,y,_=anchors[z['id']]; tight0=set(TIGHT); tf0=list(TIGHT_FALLBACK)
        near=sorted((q for q in order if q['id'] in done),key=lambda q:math.hypot(anchors[q['id']][0]-x,anchors[q['id']][1]-y))[:8]
        for q in near:
            keep=done.pop(q['id']); boxes.remove(keep[3]); ksg=segs.pop(q['id'],None)
            if place_all(z):
                if place_all(q): REPAIRED.append((z['id'],q['id'])); break
                boxes.remove(done.pop(z['id'])[3]); segs.pop(z['id'],None)
            done[q['id']]=keep; boxes.append(keep[3])
            if ksg: segs[q['id']]=ksg
            TIGHT.clear(); TIGHT.update(tight0); TIGHT_FALLBACK[:]=tf0
    i_lab=len(out); out.append('<g class="scl">')
    for z in order:
        x,y,r=anchors[z['id']]; sub=z['severity']; crit=sub=="critical"; placed=done.get(z['id'])
        if not placed:  # numbered marker at the pin + a legend row under the map with the zone's full name from data
            hidden.append(z['name']); k=len(hidden)
            out.append(f'<g class="nmk"><title>{k}: {esc(z["name"])} · {sub}</title><circle cx="{x:.0f}" cy="{y:.0f}" r="7" fill="#0b0f14" stroke="#f3efe7" stroke-width="1.5"/>'
                       f'<text x="{x:.0f}" y="{y+3.2:.1f}" text-anchor="middle" fill="#f3efe7" font-size="9" font-weight="600">{k}</text></g>')
            continue
        cx,cy,anc,bx,lead,name,is_short,nudge=placed; placed_n+=1
        if is_short: shortened.append((name,z['name']))
        tx=bx[0]+3 if anc=="start" else bx[2]-3 if anc=="end" else (bx[0]+bx[2])/2; ty=bx[1]+ns
        # short-label leaders (west 12 px nudge, tuck): #8d8d8d (Director 01:23 ET; 4.39:1 on land, 5.30:1 on sea);
        # tuck leaders start at the ring edge; ring-pass leaders keep #aaa398 from the mark
        lx,ly=lead if isinstance(lead,tuple) else (x,y)
        LAB_GEOM.append(dict(id=z['id'],name=name,box=tuple(round(v,1) for v in bx),leader=((lx,ly,cx,cy) if lead else None),
                             leader_px=round(math.hypot(cx-lx,cy-ly),1) if lead else 0.0,tight=z['id'] in TIGHT))
        if lead: out.append(f'<line class="{"ldr-tuck" if isinstance(lead,tuple) else "ldr"}" x1="{lx:.0f}" y1="{ly:.0f}" x2="{cx:.0f}" y2="{cy:.0f}" stroke="{"#8d8d8d" if nudge else "#aaa398"}" stroke-width="1"/>')
        k9=ls/9; sx=tx+(12*k9 if anc=="start" else 6*k9 if anc=="middle" else 0) if crit else tx
        gx=tx if anc=="start" else tx-crit_w-12*k9 if anc=="end" else tx-crit_w/2-6*k9
        glyph=f'<use href="#i-crit" class="critg-svg" x="{gx:.0f}" y="{ty+(ls+2)-8.5*k9:.1f}" width="{10*k9:g}" height="{10*k9:g}" aria-hidden="true"/>' if crit else ""
        out.append(f'<g class="lab">{"<title>"+esc(z["name"])+"</title>" if is_short else ""}<text class="zl" x="{tx:.0f}" y="{ty:.0f}" text-anchor="{anc}" stroke="#0a1a2a" stroke-width="3" paint-order="stroke" fill="#fff" font-size="{ns:g}" font-weight="600">{esc(name)}</text>'
                   f'{glyph}<text class="ls ls-{sub}" x="{sx:.0f}" y="{ty+(ls+2):.0f}" text-anchor="{anc}" stroke="#0a1a2a" stroke-width="3" paint-order="stroke" fill="{SEV_L[sub][0]}" font-size="{ls:g}" font-weight="600" letter-spacing=".04em">{esc(sub.upper())}</text></g>')
    out.append('</g>')
    if labels_only:
        MAP_STATS["print"]=dict(ls=ls,placed=placed_n,numbered=list(hidden),labels=LAB_GEOM,tight_fallback=list(dict.fromkeys(TIGHT_FALLBACK)),repaired=list(REPAIRED))
        return "".join(out[i_lab+1:-1]), list(hidden)
    notes=[]
    if shortened: notes.append("Short labels (storyline short names): "+"; ".join(f"{a} = {b}" for a,b in shortened))
    if hidden: notes.append("Numbered labels (no free slot at this zoom): "+"; ".join(f"{k} = {n}" for k,n in enumerate(hidden,1)))
    if notes: out.append(f'<desc>{esc(". ".join(notes))}.</desc>')
    MAP_STATS.update(placed=placed_n,numbered=list(hidden),shortened=list(shortened),zones=len(HZ['zones']),labels=LAB_GEOM,pins=list(pinc),halos=dict(halos),tight_fallback=list(dict.fromkeys(TIGHT_FALLBACK)),repaired=list(REPAIRED))
    out.append('</svg>'); svg="".join(out)
    # The legend is the control surface: the key that teaches severity is the key that filters it.
    # Real checkboxes, so it is keyboard- and screen-reader-native; CSS :has() does the filtering,
    # so this needs no JavaScript and degrades to "everything visible".
    _chips="".join(f'<input type="checkbox" class="fsw" id="f-{k}" checked>'
                   f'<label class="fchip" for="f-{k}"><i class="sw-{k}" style="background:{c}"></i>{_sev_word(k)}</label>'
                   for k,(c,_) in SEV.items())
    _chips+=('<input type="checkbox" class="fsw" id="f-none" checked>'
             '<label class="fchip" for="f-none"><i class="sw-none"></i>unranked</label>')
    leg=('<div class="legend hzk" role="group" aria-label="Filter by severity"><b>Hot zones</b> '+_chips+'</div>'
         '<p class="fnone">Every severity is filtered out. Re-enable one above to see the stories.</p>')
    # print-only (spec "Palette rulings 01:50" §5): each numbered key row also prints the critical glyph + LEVEL word
    _zsev={z['name']:z['severity'] for z in HZ['zones']}
    if hidden: leg+='<div class="legend nlab"><b>Numbered</b> '+" ".join(f'<span><b class="nmk">{k}</b> {esc(n)}<span class="pr-only"> · {_sev_word(_zsev.get(n,"watch"),_zsev.get(n,"watch").upper())}</span></span>' for k,n in enumerate(hidden,1))+'</div>'
    return svg, leg+shape_legend()+precision_legend()


# ---- Leaflet progressive enhancement (vendored Leaflet 1.9.4; Carto dark tiles need network) ----
def zone_payload(href_prefix):
    return [dict(id=z['id'],name=z['name'],lat=z['lat'],lon=z['lon'],sev=z['severity'],  # JS reads --gia-sev-<sev> tokens, not a hex
                 r=SEV[z['severity']][1],note=z.get('note',''),href=f"{href_prefix}zone-{z['id']}.html",
                 **({'area':z['area'],'area_source':z['area_source']['name']} if z.get('area') else {})) for z in HZ['zones']]
# Lazy Leaflet (approved): the static SVG map is the page; Leaflet css/js + gia-map.js load only when
# the reader presses "Open interactive map" (or the URL has #map / ?map=1, used by shots.py).
# No JS: the button stays hidden and nothing changes. ~0.6 KB inline instead of 164 KB up front.
LAZY_MAP_JS=("(function(){var b=document.getElementById('gia-map-open'),l=document.getElementById('gia-map-loader');if(!b||!l)return;"
 "var h=document.getElementById('gia-leaflet');var done=0;function go(){if(done)return;done=1;b.disabled=true;b.lastChild.textContent='Loading map…';if(h&&h.dataset.mount)h.dataset.state='loading';"
 "var c=document.createElement('link');c.rel='stylesheet';c.href=l.dataset.css;document.head.appendChild(c);"
 "var s=document.createElement('script');s.src=l.dataset.leaflet;s.onload=function(){var g=document.createElement('script');g.src=l.dataset.giamap;"
 "g.onload=function(){b.hidden=true;};document.body.appendChild(g);};s.onerror=function(){b.lastChild.textContent='Map unavailable (offline?)';if(h&&h.dataset.mount)h.dataset.state='failed';};document.body.appendChild(s);}"
 "b.hidden=false;b.addEventListener('click',go);if(location.hash==='#map'||location.hash==='#interactive'||/[?&]map=1/.test(location.search))go();addEventListener('hashchange',function(){if(location.hash==='#map'||location.hash==='#interactive')go();});})();")
from gia_build.today import ICON_MAP
# Neutral button (Designer spec, Director-approved): Carbon layer-02 #393939, text #f4f4f4 14 px, 48 px tall,
# 1 px border-strong #6f6f6f, Carbon icon. No red, no purple.
MAP_BTN=f'<button type="button" id="gia-map-open" class="gbtn" hidden style="margin:6px 0">{ICON_MAP}<span>Open interactive map</span></button>'
def leaflet_html(data, vprefix, height=520):
    js=json.dumps(data,ensure_ascii=False).replace('</','<\\/')
    return (MAP_BTN+
            f'<div id="gia-leaflet" style="display:none;height:{height}px;border:1px solid #223041;border-radius:8px;background:#071018"></div>'
            f'<script type="application/json" id="gia-map-data">{js}</script>'
            f'<script id="gia-map-loader" data-css="{vprefix}vendor/leaflet/leaflet.css" data-leaflet="{vprefix}vendor/leaflet/leaflet.js" data-giamap="{vprefix}vendor/gia-map.js">{LAZY_MAP_JS}</script>')

# ---- Path-to-today: best forward path from a root to a 2026 descendant ----
def best_path(start, goal, maxd=30):
    best=None
    def dfs(cur, path, score):
        nonlocal best
        if len(path)>maxd: return
        if cur==goal:
            if best is None or score>best[0] or (score==best[0] and len(path)<len(best[1])):
                best=(score, path[:])
            return
        for e in ST[cur].get('effects',[]):
            if e['story'] in {p[0] for p in path}: continue
            dfs(e['story'], path+[(e['story'], e['why'], e['confidence'])], score+CONF_W.get(e['confidence'],1))
    dfs(start, [(start, None, None)], 0)
    return best

# Hand-picked demo paths (root → 2026 destination)
DEMO_PATHS=[
    ("2021-11-russia-buildup","energy-ceasefire","Russia buildup → energy ceasefire 2026"),
    ("2021-12-wagner-mali","kidal","Wagner in Mali → Kidal 2026"),
    ("2022-01-abu-dhabi-attack","houthis-hit-aramco","Houthi Abu Dhabi attack → Aramco HQ 2026"),
    ("2022-08-09-chips-act","rare-earth-nov10","CHIPS Act → rare-earth standoff 2026"),
    ("2022-08-02-pelosi","pla-drills","Pelosi Taiwan visit → PLA drills 2026"),
]
PATH_INDEX={}  # root_id -> {goal, title, slides:[{id,why,conf},...]}
for root,goal,title in DEMO_PATHS:
    r=best_path(root,goal)
    if not r: print("WARN no path",root,goal); continue
    PATH_INDEX[root]=dict(goal=goal,title=title,score=r[0],steps=r[1])
    # also index every intermediate so "Path to current day" from mid-path events can jump in
    for i,(sid,_,_) in enumerate(r[1]):
        PATH_INDEX.setdefault(sid, dict(goal=goal,title=title,score=r[0],steps=r[1][i:],root=root,offset=i))

def path_btn(sid, pre="history/"):
    info=PATH_INDEX.get(sid)
    if not info: return ""
    root=info.get("root",sid); off=info.get("offset",0)
    return f'<a class="pathbtn" href="{pre}path-{root}/slide-{off+1:02d}.html">▶ Path to current day ({len(info["steps"])} steps → {esc(ST[info["goal"]]["title"][:48])}…)</a>'

from gia_build import history_taps as _HT  # Designer's history tap-target proposal, PENDING Director (GIA_HISTORY_TAPS=off drops it)
def chip(i,pre="history/"): return f'<a class="chip" href="{pre}entity-{i}.html" title="History of {esc(E[i]["name"])}">{esc(E[i]["name"])}</a>'
def chain(s,pre):
    def li(c):
        t=ST.get(c['story']); return f'<li><a href="{pre}trace-{t["id"]}.html">{esc(t["title"])}</a> <span class="meta">{ddisp(t)}</span> — <span class="an"><span class="conf {c["confidence"]}">{c["confidence"]}</span>{esc(c["why"])}</span></li>' if t else ''
    o=''
    if s.get('causes'): o+='<div class="cz"><b>⬆ Led to this</b><ul>'+''.join(li(c) for c in s['causes'])+'</ul></div>'
    if s.get('effects'): o+='<div class="cz"><b>⬇ What it set off</b><ul>'+''.join(li(c) for c in s['effects'])+'</ul></div>'
    return o+f'<div class="meta trc"><a href="{pre}trace-{s["id"]}.html">⟲ Trace causal chain</a></div>'+path_btn(s['id'],pre)
def card(s,pre="history/",home="",anchor=True):
    a=f' id="story-{s["id"]}"' if anchor else ''
    src=" · ".join(f'<a href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["name"])}</a>' for x in s['sources'])
    an=s.get('analysis') or {}; c=an.get('confidence','')
    sls_l=[f'<a class="chip sl" href="{pre}storyline-{l}.html">⟿ {esc(SLD[l]["name"])}</a>' for l in s.get('storylines',[]) if l in SLD]; sls="".join(sls_l)
    rel=" · ".join(f'<a href="{pre}year-{ST[r]["date"][:4]}.html#story-{r}">{esc(ST[r]["title"])}</a>' for r in s.get('related_stories',[]) if r in ST)
    rev="".join(f'<div class="meta">Corrected in {esc(v.get("edition",""))}: {esc(v.get("why",""))}</div>' for v in s.get("revisions") or [])
    return (f'<article class="card"{a}><h3>{esc(s["title"])}</h3><div class="meta">{ddisp(s)} · {esc(s.get("region",""))} · {esc(s.get("kind","event"))}</div>'
            f'<p>{esc(s["summary"])}</p>{rev}'+(f'<p class="an"><span class="conf {c}">{c}</span>{esc(an.get("text",""))}</p>' if an else '')+
            f'<div class="meta">Sources: {src}</div>{_HT.group([chip(i,pre) for i in s["entities"] if i in E], f"c-{s['id']}")}'
            +(_HT.group(sls_l, f"s-{s['id']}") if sls else '')+chain(s,pre)+(f'<div class="rel">Related: {rel}</div>' if rel else '')+'</article>')

CSS="""body{margin:0;background:#0b0f14;color:#d6dde6;font:14px/1.5 Arial,Helvetica,sans-serif}header{padding:16px 24px;border-bottom:1px solid #1f2a36;background:#0f1722}
h1{margin:0;font-size:28px;line-height:1.15;letter-spacing:.04em;color:#fff}h1 b{color:var(--gia-accent-ui)}h2{color:var(--gia-h2);font-size:22px;line-height:1.25;letter-spacing:-.01em;font-weight:600;margin:40px 0 14px;padding:0}
main{padding:0 24px 40px;max-width:1300px;margin:auto}.meta,small{color:#7f8fa3;font-size:12px}
.boardgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.reg{background:#111821;border:1px solid #223041;border-radius:2px;padding:8px}.reg ul{margin:6px 0 0;padding-left:16px}
.card{background:#111821;border:1px solid #223041;border-radius:2px;padding:12px 14px;margin-bottom:12px}.skip{position:absolute;left:-9999px;top:0;z-index:10;background:#111821;color:#f3efe7;padding:10px 14px;border:1px solid #223041}.skip:focus{left:8px;top:8px}.snav{display:flex;flex-wrap:wrap;gap:4px 18px;margin-top:10px;font-size:13px}.snav a{color:#d6dde6;min-height:44px;display:inline-flex;align-items:center}@media print{.skip,.snav{display:none!important}}.fsw{position:absolute;width:1px;height:1px;opacity:0;margin:0}.fchip{display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0 10px;margin-right:2px;border:1px solid transparent;border-radius:2px;cursor:pointer;user-select:none}.fchip:hover{background:#172230}.fsw:focus-visible+.fchip{outline:var(--gia-focus-px) solid var(--gia-focus);outline-offset:-2px}.fsw:not(:checked)+.fchip{opacity:.4}.fsw:not(:checked)+.fchip i{box-shadow:inset 0 0 0 1px #8d8d8d;background:transparent!important}.sw-none{display:inline-block;width:10px;height:10px;border-radius:50%;box-shadow:inset 0 0 0 1px #8d8d8d}.fnone{display:none;color:#7f8fa3;font-size:13px;margin:10px 0}body:has(#f-critical:not(:checked)) [data-fsev="critical"],body:has(#f-critical:not(:checked)) .hz-critical,body:has(#f-critical:not(:checked)) .ls-critical{display:none}body:has(#f-high:not(:checked)) [data-fsev="high"],body:has(#f-high:not(:checked)) .hz-high,body:has(#f-high:not(:checked)) .ls-high{display:none}body:has(#f-elevated:not(:checked)) [data-fsev="elevated"],body:has(#f-elevated:not(:checked)) .hz-elevated,body:has(#f-elevated:not(:checked)) .ls-elevated{display:none}body:has(#f-watch:not(:checked)) [data-fsev="watch"],body:has(#f-watch:not(:checked)) .hz-watch,body:has(#f-watch:not(:checked)) .ls-watch{display:none}body:has(#f-none:not(:checked)) [data-fsev="none"]{display:none}body:has(#f-critical:not(:checked)):has(#f-high:not(:checked)):has(#f-elevated:not(:checked)):has(#f-watch:not(:checked)):has(#f-none:not(:checked)) .fnone{display:block}@media print{.fsw,.fnone{display:none!important}.fchip{min-height:0;padding:0 6px}}.ckey .conf{margin-right:6px}.ckey{align-items:center}.palbtn{margin-left:auto;display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0 10px;background:transparent;border:1px solid #223041;border-radius:2px;color:#a8a8a8;font:400 13px/1 "IBM Plex Sans",Arial,sans-serif;cursor:pointer}.palbtn:hover{border-color:#8d8d8d;color:#f3efe7}.palbtn kbd{font:500 11px/1 "IBM Plex Mono",monospace;background:#262626;border:1px solid #393939;border-radius:2px;padding:2px 5px;color:#f3efe7}.pal{width:min(640px,92vw);max-height:70vh;padding:0;background:#111821;color:#f3efe7;border:1px solid #393939;border-radius:2px;overflow:hidden}.pal::backdrop{background:#0b0f14cc}.pal-q{width:100%;box-sizing:border-box;padding:14px 16px;background:transparent;border:0;border-bottom:1px solid #223041;color:#f3efe7;font:400 16px/1.4 "IBM Plex Sans",Arial,sans-serif;outline:none}.pal-q::placeholder{color:#7f8fa3}.pal-q:focus-visible{outline:var(--gia-focus-px) solid var(--gia-focus);outline-offset:-2px}.pal-l{list-style:none;margin:0;padding:6px 0;max-height:46vh;overflow:auto}.pal-l li{padding:8px 16px;font-size:14px;cursor:pointer}.pal-l li.on{background:#1d2a3a}.pal-l .pg{padding:10px 16px 4px;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--gia-path);cursor:default}.pal-h{margin:0;padding:10px 16px;border-top:1px solid #223041;color:#7f8fa3;font-size:12px}@media print{.palbtn,.pal{display:none!important}}.zmapwrap{max-width:900px;margin:0 0 20px}.zmap{display:block;width:100%;height:auto;border:1px solid #223041;border-radius:2px}.zl{font-family:"IBM Plex Sans",Arial,sans-serif;paint-order:stroke;stroke:#0a1a2a;stroke-width:3.5px;stroke-linejoin:round}.zl-n{font-size:13px;fill:#c1c7cd}.zl-s{font-size:20px;font-weight:600;fill:#f3efe7}.zl-v{font-size:14px;font-weight:600;letter-spacing:.06em}@media print{.zmap{-webkit-print-color-adjust:exact;print-color-adjust:exact}.zmap .sea{fill:#f3f1ec!important}.zmap .land{fill:#e2ded6!important;stroke:#b9b2a7!important}.zl{stroke:#f3f1ec!important}.zl-n{fill:#54504a!important}.zl-s{fill:#141312!important}}.row p,.row .an{max-width:72ch}.row .an{margin-top:8px}.corr{font-style:normal}.card h3{margin:0 0 6px;font-size:17px;line-height:1.3;color:#fff}
::selection{background:#2d3f55;color:#f3efe7}html{scrollbar-color:#2a3a4d #0b0f14;scrollbar-width:thin;caret-color:var(--gia-accent-ui)}::-webkit-scrollbar{width:11px;height:11px}::-webkit-scrollbar-track{background:#0b0f14}::-webkit-scrollbar-thumb{background:#2a3a4d;border:2px solid #0b0f14;border-radius:6px}::-webkit-scrollbar-thumb:hover{background:#3a4e66}.conf{font-style:normal;font-size:11px;padding:1px 6px;border-radius:999px;margin-right:6px;text-transform:uppercase}.likely{background:#173d24;color:#7fe0a0}.possible{background:#4d3208;color:#ffbf5a}.speculative{background:#3a1430;color:#ff8bd2}
.chip{display:inline-block;margin:3px 4px 0 0;padding:1px 8px;border-radius:999px;background:var(--gia-chip-bg);border:1px solid var(--gia-chip-border);color:var(--gia-link);font-size:12px;text-decoration:none}
.idx{columns:4;list-style:none;padding:0}.idx li{break-inside:avoid}
.wmap{border:1px solid #223041;border-radius:2px;display:block}.wmap .zs{fill:#000;font-size:11px;font-weight:600}.wmap .zl{fill:#fff;font-size:11px;font-weight:600}
.legend{margin:8px 0}.legend span{margin-right:14px;font-size:12px}.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}.legend b{margin-right:8px;color:#9ab}.pinleg{vertical-align:middle;margin-right:4px}.two{display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:13px}.links,.zones{margin:6px 0}
.row{border-bottom:1px solid #1f2a36;padding:12px 0}.row h3{margin:0;font-size:16px;color:#fff}.row p{margin:4px 0 0}.gia-pin{background:transparent!important;border:none!important}
:target{outline:2px solid var(--gia-focus);outline-offset:-2px;background:#1a1f2b}#q{padding:6px;background:#121a24;border:1px solid #2a3a4e;color:#fff;border-radius:6px;width:260px}.tl h3.yr{color:var(--gia-accent-ui);font-size:18px;margin:22px 0 4px}.tl h4{color:var(--gia-h4);margin:10px 0 4px;font-size:12px}.sl{background:#2a1f3a;color:#d6b8ff}
.cz{font-size:12px;margin-top:6px}.cz ul{margin:2px 0;padding-left:18px}.tree{border-left:2px solid color-mix(in srgb,var(--gia-accent-ui) 55%,transparent);margin-left:6px;padding-left:16px;list-style:none}.tree li{margin:6px 0}.chainlist li.cur{color:var(--gia-accent-ui);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{border-bottom:1px solid #1f2a36;padding:5px;text-align:left;vertical-align:top}.rt{font-size:10px;padding:1px 6px;border-radius:999px;background:#1b2d4a}.rt.rivalry{background:#4a1b1b}.rt.alliance{background:#173d24}.rt.patron-proxy{background:#3a2a10}.rt.sanction{background:#3a1430}.rel{font-size:12px;color:#9aa8b8}
.gia-badge{background:#0b0f14e6;border:2px solid var(--gia-accent-ui);border-radius:2px;padding:8px 12px;color:#fff;font:13px Arial;max-width:340px}.gia-tip{background:#0b0f14;color:var(--gia-label);border:1px solid var(--gia-accent-ui);font:600 12px/16px 'IBM Plex Sans',Arial,sans-serif}.gia-tip.dim{border-color:color-mix(in srgb,var(--gia-accent-ui) 60%,transparent);color:var(--gia-label-past);font:400 11px/14px 'IBM Plex Sans',Arial,sans-serif}@keyframes giapulse{0%{stroke-width:3;stroke-opacity:1}50%{stroke-width:14;stroke-opacity:.25}100%{stroke-width:3;stroke-opacity:1}}.gia-pulse{animation:giapulse 1.6s ease-in-out infinite}.leaflet-container{background:#071018}
.pathbtn{display:inline-flex;align-items:center;gap:8px;min-height:48px;margin-top:8px;padding:0 16px;box-sizing:border-box;background:#6f6f6f;color:#ffffff!important;text-decoration:none;border:0;border-radius:0;font:400 14px/18px "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}.pathbtn:hover{background:#606060}.pathbtn:active{background:#393939}.pathbtn:focus-visible{outline:2px solid #fff;outline-offset:-4px}
.slidewrap{max-width:1100px;margin:auto;padding:12px 20px 40px}.navrow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:10px 0}
.navrow a.btn{padding:8px 16px;background:var(--gia-chip-bg);border:1px solid var(--gia-chip-border);color:var(--gia-link);text-decoration:none;border-radius:6px;font-weight:600}
.navrow a.btn.disabled{opacity:.3;pointer-events:none}
.dots{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
/* step markers (spec Follow-ups B): thin bars with a padded hit area, 24x24 desktop, 24x44 phone */
.dots a.gd{display:block;box-sizing:content-box;width:24px;height:4px;padding:10px 0;background:#4a4640;background-clip:content-box;text-decoration:none}
.dots a.gd.past{background-color:#aaa398}.dots a.gd.on{height:6px;padding:9px 0;background-color:#f3efe7}
.dots a.gd:focus-visible{outline:2px solid #f3efe7;outline-offset:2px}
@media screen and (max-width:671px){.dots a.gd{width:16px;padding:20px 4px}.dots a.gd.on{padding:19px 4px}
 .navrow{flex-wrap:wrap;row-gap:4px}.navrow .dots{order:-1;flex:1 0 100%;justify-content:center}.navrow .prog{order:0}}.prog{flex:1;height:6px;background:#1f2a36;border-radius:3px;overflow:hidden}.prog i{display:block;height:100%;background:var(--gia-path)}
.panel{background:#111821;border:1px solid #223041;border-radius:2px;padding:14px 16px;margin-top:10px}.panel h2{margin:0 0 6px;color:#fff;font-size:18px;border:0;letter-spacing:0;text-transform:none;padding:0}
.why{background:#1a1428;border-left:3px solid #b9a7ff;padding:8px 12px;margin-top:10px}
.paths{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}.pathcard{background:#111821;border:1px solid #223041;border-radius:2px;padding:12px}"""

from gia_build.today import GBTN_CSS as _GBTN_CSS, CRIT_CSS as _CRIT_CSS
CSS+=":where(b,strong,h1,h2,h3,h4,h5,h6,th){font-weight:600}"+UI.UPRIGHT_CSS+UI.NOTE_CSS+UI.LINK_CSS+UI.TAP_CSS+_GBTN_CSS+_CRIT_CSS+_HT.CSS+MK.ROOT_CSS+UI.ROOT_CSS
# Path slides: non-severity accents move from #ff5a4f to --path #c3a6ff (spec.md 19 Oct
# "Map labels at AA"; Director 01:23 ET). Severity reds elsewhere are unchanged.
# spec.md 19 Oct "Non-severity reds -> tokens": on slides too, tip/badge/h2/year/current-row/tree/wordmark take
# --gia-accent-ui (base CSS); only the progress bar and the 2D trail take --path.
SLIDE_CSS=(":root{--path:var(--gia-path)}.prog i{background:var(--path)}"+UI.SLIDE_PRINT_CSS)
CSS+='.legend b.nmk{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;background:#0b0f14;color:#f3efe7;border:1.5px solid #f3efe7;box-sizing:border-box;font:600 10px/1 "IBM Plex Sans",sans-serif;margin:0 4px 0 0}@media print{.legend b.nmk{background:#fff!important;color:#141312!important;border:.6pt solid #141312}.wmap .nmk circle{fill:#fff;stroke:#141312}.wmap .nmk text{fill:#141312}}'
# history pages now carry a viewport meta, so give them a phone layout (no 448 px tables pushing the page sideways)
CSS+="@media (max-width:671px){.boardgrid{grid-template-columns:minmax(0,1fr)}main{padding:0 16px 32px}header{padding:12px 16px}.idx{columns:2}.two{grid-template-columns:1fr}main table{display:block;overflow-x:auto;max-width:100%}}"
# r4 (Director 03:53 item 2): print level words at 10.5pt = 14 CSS px. The print map is drawn UI.PRINT_MAP_PX wide (measured in
# print media), so 14 px = PRINT_LS_UNITS viewBox units; a print-only label layer is solved at that size (same solver,
# same rules), and print hides the screen layer. Run first: the screen call below owns MAP_STATS' top-level keys.
_PRL,_PR_HIDDEN=world_map_dashboard(ls=UI.PRINT_LS_UNITS,labels_only=True,ns=UI.PRINT_NS_UNITS)
WMAP,WLEG=world_map_dashboard()
WMAP=WMAP.replace('</svg>','<g class="prl">'+_PRL+'</g></svg>')
if _PR_HIDDEN!=MAP_STATS["numbered"]:   # print numbers differ from screen: a print-only key row set (screen one hidden in print)
    _zs={z['name']:z['severity'] for z in HZ['zones']}
    WLEG=WLEG.replace('<div class="legend nlab">','<div class="legend nlab scr-only">',1)
    _pk='<div class="legend nlab nlab-pr"><b>Numbered</b> '+" ".join(f'<span><b class="nmk">{k}</b> {esc(n)}<span class="pr-only"> · {_sev_word(_zs.get(n,"watch"),_zs.get(n,"watch").upper())}</span></span>' for k,n in enumerate(_PR_HIDDEN,1))+'</div>'
    WLEG=WLEG.replace('<div class="legend nlab scr-only">',_pk+'<div class="legend nlab scr-only">',1) if 'nlab scr-only' in WLEG else _pk+WLEG
CSS+=".wmap .prl,.legend.nlab-pr{display:none}@media print{.wmap .scl,.legend.scr-only{display:none!important}.wmap .prl{display:inline!important}.legend.nlab-pr{display:block!important}}"
# Designer spec: the static map is ONE link to the map (there is no separate Map page in this build, so it
# opens the interactive map on this page via #map; with JS off the link lands on the map itself).
_nz=len(HZ['zones']); _np=len({e['id'] for _s in LATEST for e in story_places(_s)}); _nu=sum(1 for _s in LATEST if not story_places(_s))
assert '<a ' not in WMAP, "static map must carry no links inside"
WMAP_SVG=WMAP
WMAP=(f'<a id="map" class="maplink" href="map.html" aria-label="Open the full hot-zone map: {_nz} zones, {_np} pinned places, {_nu} stories not pinned">'
      f'{WMAP}<span class="mapopen">{ICON_MAP}<span>Full map page</span></span></a>')
# ---- Today phone static map (<672 px): Designer spec.md v3, approved for r3 (Director 03:20); gia_build/phonemap.py ----
from gia_build import phonemap as _PM
_pm_pins=[]; _pm_seen=set()
for _s in LATEST:
    for _ent in story_places(_s):
        if _ent["id"] in _pm_seen: continue
        _pm_seen.add(_ent["id"]); _pm_pins.append((_ent["id"],_ent["lon"],_ent["lat"],PLACE_MARKER.get(_ent["id"],"political"),_ent.get("precision")))
PHONE=_PM.PhoneMap(HZ['zones'],_pm_pins,_text_w,G['features'],svg_pin,UI.sev)
_PL=PHONE.layouts(); PHONE_CHECK=PHONE.verify(_PL)
PHONE_HTML="<!--mp-->"+PHONE.html(_PL)+"<!--/mp-->"; PHONE_EXTRA="<!--mp-->"+PHONE.extras(_PL,full_map_icon=ICON_MAP)+"<!--/mp-->"
assert all(not v["overlaps"] for v in PHONE_CHECK.values()), {k:v["overlaps"] for k,v in PHONE_CHECK.items() if v["overlaps"]}
WMAP_DASH=WMAP.replace('<span class="mapopen">',PHONE_HTML+'<span class="mapopen">',1)
print("phone map:", {k:(v["placed"],v["numbered"],v["min_gap"][:2] if v["min_gap"] else None,v["leaders_px"]) for k,v in PHONE_CHECK.items()})
_today_places=[]; _seen_today=set()
for _s in LATEST:
    for _ent in story_places(_s):
        if _ent["id"] in _seen_today: continue
        _seen_today.add(_ent["id"])
        _today_places.append(dict(id=_ent["id"],name=_ent["name"],lat=_ent["lat"],lon=_ent["lon"],
            marker=PLACE_MARKER.get(_ent["id"],"political"),precision=_ent.get("precision"),role="today",href=f"history/trace-{_s['id']}.html"))
LEAF_DASH=leaflet_html(dict(mode="dashboard",zones=zone_payload("history/"),places=_today_places,
    links=[{"from":l["from"],"to":l["to"],"label":l["label"],"href":f"history/link-{l['id']}.html"} for l in HZ['links']]),"")
board=[]
for r in REG:
    l=[s for s in LATEST if s.get('region')==r]
    items="".join(f'<li><a href="#story-{s["id"]}">{esc(s["title"])}</a></li>' for s in l) or ('<li class="meta">No primary stories this edition; see Russia/Eurasia and the EU tag.</li>' if r=="Europe" else '<li class="meta">No stories this edition.</li>')
    board.append(f'<details class="reg" open><summary><b>{r}</b> ({len(l)})</summary><ul>{items}</ul></details>')
order=sorted(ENTS,key=lambda e:e['name'].lower())
idx="".join(f'<li data-n="{esc((e["name"]+" "+e["type"]).lower())}"><a href="history/entity-{e["id"]}.html">{esc(e["name"])}</a> <small>{e["type"]} · {len(by[e["id"]])}</small></li>' for e in order)
slh="".join(f'<li><a href="history/storyline-{l["id"]}.html">{esc(l["name"])}</a> <small>{len(l["stories"])} stories</small></li>' for l in SL)
pathcards="".join(f'<div class="pathcard"><b>{esc(info["title"])}</b><div class="meta">{len(info["steps"])} slides · {ddisp(ST[root])} → {ddisp(ST[info["goal"]])}</div><p class="meta">{esc(ST[root]["title"])} → … → {esc(ST[info["goal"]]["title"])}</p><a class="pathbtn" href="history/path-{root}/slide-01.html">▶ Play path</a></div>' for root,info in ((k,v) for k,v in PATH_INDEX.items() if v.get("root") is None or k==v.get("root")))
# only top-level demos
pathcards="".join(f'<div class="pathcard"><b>{esc(v["title"])}</b><div class="meta">{len(v["steps"])} slides · {ddisp(ST[k])} → {ddisp(ST[v["goal"]])}</div><p class="meta">{esc(ST[k]["title"])} → … → {esc(ST[v["goal"]]["title"])}</p><a class="pathbtn" href="history/path-{k}/slide-01.html">▶ Play path</a></div>' for k,v in PATH_INDEX.items() if "root" not in v)

from gia_build.today import SEV_RANK as _SEV_RANK, meter as _row_meter
# A story inherits the worst severity of any hot zone that lists it. One ordering for the
# whole page: the board already ranked this way; the stories and the connect section did not.
_STORY_SEV={}
for _z in HZ["zones"]:
    for _sid in _z.get("stories") or []:
        if _SEV_RANK.get(_z["severity"],0) > _SEV_RANK.get(_STORY_SEV.get(_sid,""),0): _STORY_SEV[_sid]=_z["severity"]
def _srank(s): return _SEV_RANK.get(_STORY_SEV.get(s["id"],""),0)

def edition_row(s):
    named=", ".join(ent["name"] for ent in story_places(s))
    loc=named or s.get("unplaced") or "Location not placed yet"
    sev=_STORY_SEV.get(s["id"])
    an=s.get("analysis") or {}; c=an.get("confidence","")
    # The reported fact and the judgment on it are the product; the dashboard rendered only the fact.
    judg=(f'<p class="an"><span class="conf {c}">{c}</span>{esc(an.get("text",""))}</p>' if an else '')
    rev="".join(f'<div class="meta corr">Corrected in {esc(v.get("edition",""))}: {esc(v.get("why",""))}</div>' for v in s.get("revisions") or [])
    return (f'<article class="row" data-fsev="{sev or "none"}"><h3><a href="history/trace-{s["id"]}.html">{esc(s["title"])}</a></h3>'
            f'<div class="meta">{ddisp(s)} · {esc(s.get("region",""))} · {esc(loc)}{(" " + _row_meter(sev)) if sev else ""}</div>'
            f'<p>{esc(s["summary"])}</p>{rev}{judg}</article>')

from gia_build import today as _today  # Today sections (sec-board/markets/connect/storylines/calendar), from data/ only
TS=_today.sections(D,regions=REG,latest=LATEST,all_stories=S,by_id=ST,zones=HZ['zones'],zone_links=HZ['links'],lines=SL,edition=ed,places_of=story_places,ddisp=ddisp)
out=f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GIA World Intel — {ed}</title><style>{CSS}{_today.CSS}/*mp*/{_PM.CSS}/*/mp*/</style></head><body id="top">
<a class="skip" href="#sec-stories">Skip to today's stories</a><header><h1>GIA <b>//</b> WORLD INTEL</h1><div class="meta">Edition {ed} · {len(LATEST)} stories today · {len(S)} in the archive · <a href="history/index.html">Archive</a></div><nav class="snav" aria-label="Sections"><a href="#sec-map">Map</a><a href="#sec-board">Board</a><a href="#sec-stories">Stories</a><a href="#sec-connect">Connections</a><a href="#sec-storylines">Storylines</a><button type="button" class="palbtn" hidden>Search <kbd>/</kbd></button></nav><div class="meta" hidden></div></header><main>
<section id="sec-map"><h2 id="world">Right now</h2><div id="gia-fallback">{WMAP_DASH}{PHONE_EXTRA}</div>{LEAF_DASH}{WLEG}</section>
{TS["board"]}
<section id="sec-stories"><h2 id="stories">Today, {ed}</h2><div class="legend ckey"><b>Confidence</b> <span class="conf likely">likely</span><span class="conf possible">possible</span><span class="conf speculative">speculative</span><span class="meta"> rates the judgment under each summary, not the event itself.</span></div>{"".join(edition_row(s) for s in sorted(LATEST,key=lambda s:(_srank(s),s['date']),reverse=True))}</section>
{TS["connect"]}
{TS["storylines"]}
{TS["markets"]}
{TS["calendar"]}
<p class="meta">Paths, the full regional board, all storylines, and the entity index are in the <a href="history/index.html">archive</a>. Generated by build_dashboard.py.</p></main>
<script src="vendor/gia-palette.js" defer></script></body></html>"""
open(f"{D}/dashboard.html","w").write(out)

# ---- Map page (hi-fi contract §1): #gia-leaflet always visible; the static SVG (#gia-fallback) sits inside it and
# Leaflet mounts before it on "Open interactive map" (or #interactive), setting data-state loading -> ready|failed.
from gia_build.today import _slug as _rslug, meter as _meter
def inset_svg():
    """Gulf / Red Sea inset, drawn only from zones' `area` (none filed -> None)."""
    az=[z for z in HZ['zones'] if z.get('area')]
    if not az: return None
    xs=[];ys=[]
    for z in az:
        for poly in (z['area']['coordinates'] if z['area']['type']=='MultiPolygon' else [z['area']['coordinates']]):
            for ring in poly:
                for lon,lat in (pt[:2] for pt in ring): x,y=pj(lon,lat); xs.append(x); ys.append(y)
    pad=8; x0,y0,x1,y1=min(xs)-pad,min(ys)-pad,max(xs)+pad,max(ys)+pad; k=(x1-x0)/720  # viewBox units per CSS px at the 720 px max width
    o=[f'<svg viewBox="{x0:.1f} {y0:.1f} {x1-x0:.1f} {y1-y0:.1f}" width="100%" class="wmap inset" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="inset-t"><title id="inset-t">Inset: sea areas of existing hot zones ({esc(", ".join(z["name"] for z in az))})</title>'
       f'<rect class="sea" x="{x0:.1f}" y="{y0:.1f}" width="{x1-x0:.1f}" height="{y1-y0:.1f}" fill="#0a1a2a"/><g class="land" fill="#1c2a3a" stroke="#3a4f66" stroke-width="{.5*k:.3f}">{"".join(COUNTRY_PATHS)}</g>']
    for z in az:
        c=SEV[z['severity']][0]; x,y=pj(z['lon'],z['lat'])
        o.append(f'<path d="{_svg_path(z["area"],pj)}" fill="{c}" fill-opacity=".18" stroke="{c}" stroke-width="{1.4*k:.3f}" stroke-dasharray="{4*k:.2f} {2*k:.2f}"><title>{esc(z["name"])}: outline {esc(z["area_source"]["name"])}</title></path>'
                 f'<text class="il" x="{x+(-8 if x>(x0+x1)/2 else 8)*k:.1f}" y="{y:.1f}" text-anchor="{"end" if x>(x0+x1)/2 else "start"}" fill="#fff" stroke="#0a1a2a" stroke-width="{3*k:.2f}" paint-order="stroke" font-size="{13*k:.2f}" font-weight="600">{esc(z["name"])}</text>')
    o.append('</svg>'); return "".join(o)
def map_page():
    zrows=[]
    for z in sorted(HZ['zones'],key=lambda z:({"critical":0,"high":1,"elevated":2,"watch":3}[z['severity']],z['name'])):
        nt=len(set(z.get('stories') or [])&{s['id'] for s in LATEST})
        outline=esc(z['area_source']['name']) if z.get('area') else '<span class="meta">point and halo</span>'
        zrows.append(f'<tr><th scope="row"><a href="history/zone-{z["id"]}.html">{esc(z["name"])}</a></th><td>{_meter(z["severity"])}</td><td class="num">{nt}</td><td>{outline}</td></tr>')
    regs=[]
    for r in REG:
        st=sorted([s for s in LATEST if s.get('region')==r],key=lambda s:s['date'],reverse=True)
        pin=[s for s in st if story_places(s)]; unp=[s for s in st if not story_places(s)]
        pl="".join(f'<li><a href="history/trace-{s["id"]}.html">{esc(s["title"])}</a> <span class="meta">· {esc(", ".join(e["name"] for e in story_places(s)))}</span></li>' for s in pin)
        up="".join(f'<li><a href="history/trace-{s["id"]}.html">{esc(s["title"])}</a> <span class="meta">· {esc(s.get("unplaced") or "Location not placed yet")}</span></li>' for s in unp)
        body=(f'<h4>Pinned ({len(pin)})</h4><ul>{pl}</ul>' if pin else '')+(f'<h4>Not pinned ({len(unp)})</h4><ul>{up}</ul>' if unp else '')
        regs.append(f'<article class="mreg" id="reg-{_rslug(r)}"><h3>{esc(r)} <small>({len(st)})</small></h3>{body or "<div class=meta>No stories this edition.</div>"}</article>')
    ins=inset_svg()
    js=json.dumps(dict(mode="dashboard",zones=zone_payload("history/"),places=_today_places,
        links=[{"from":l["from"],"to":l["to"],"label":l["label"],"href":f"history/link-{l['id']}.html"} for l in HZ['links']]),ensure_ascii=False).replace('</','<\\/')
    jump=" · ".join(f'<a href="#reg-{_rslug(r)}">{esc(r)}</a>' for r in REG)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GIA hot-zone map — {ed}</title><style>{CSS}{_today.CSS}{MAP_CSS}</style></head><body id="top">
<header><h1>GIA <b>//</b> HOT-ZONE MAP</h1><div class="meta">Edition {ed} · {_nz} zones · {_np} pinned places · {_nu} stories not pinned · <a href="dashboard.html">Today</a> · <a href="history/index.html">Archive</a></div><div class="meta">Regions: {jump}</div></header><main>
<section id="sec-map"><h2>Where today's stories happened</h2><div class="meta">Rings are hot zones, colored by severity; zones with a filed sea outline are drawn as that area. Pins are places named in today's stories; a story with no honest place has no pin. The interactive layer (Leaflet, Esri dark-gray tiles) loads only when you open it.</div>
<div id="gia-leaflet" data-mount="inner" data-state="static"><div id="gia-fallback">{WMAP_SVG}</div></div>
{MAP_BTN}<script type="application/json" id="gia-map-data">{js}</script><script id="gia-map-loader" data-css="vendor/leaflet/leaflet.css" data-leaflet="vendor/leaflet/leaflet.js" data-giamap="vendor/gia-map.js">{LAZY_MAP_JS}</script>{WLEG}</section>
<section id="sec-areas"><h2>Gulf and Red Sea</h2>{ins if ins else '<div class="empty">No hot zone has a filed sea outline in this edition.</div>'}<div class="meta">Sea outlines are areas of existing zones, never zones of their own, and carry no pins.</div></section>
<section id="sec-zones"><h2>Hot zones</h2><div class="meta">The same zones as the map, most severe first.</div><table class="mz"><tr><th>Zone</th><th>Severity</th><th>Today's stories</th><th>Shape on the map</th></tr>{"".join(zrows)}</table></section>
<section id="sec-regions"><h2>By region</h2><div class="mregs">{"".join(regs)}</div></section>
<p class="meta">Generated by build_dashboard.py from data/ only.</p></main></body></html>"""
MAP_CSS=("@media print{#gia-leaflet[data-mount]{display:block!important}#gia-leaflet #gia-fallback{display:block!important}#gia-leaflet .gia-lmap,#gia-leaflet .leaflet-container{display:none!important}.mreg h4{color:#54504a!important}}"   # r4: map.html prints the static map + key
         "#gia-leaflet[data-mount]{display:block;position:relative}.gia-lmap{border:1px solid #223041;border-radius:2px;background:#071018}"
         "#gia-leaflet[data-state=ready] #gia-fallback{display:none}.mregs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}"
         ".mreg{background:#111821;border:1px solid #223041;border-radius:2px;padding:10px 12px}.mreg h3{margin:0 0 4px;font-size:15px;color:#f3efe7}.mreg h4{margin:8px 0 2px;font-size:12px;color:#aaa398;font-weight:600}"
         "@media (min-width:672px){.mreg li>a,.mz th a,main h4+ul a{display:inline-block;min-height:24px;line-height:20px;padding:2px 0;box-sizing:border-box}}"
         ".mreg ul{margin:0;padding-left:16px}.mreg li{font-size:13px;margin:0 0 4px}.mz td.num{text-align:right}.wmap.inset{max-width:720px}"
         "@media (max-width:671px){.mregs{grid-template-columns:1fr}.mreg li>a,.mz th a{display:flex;align-items:center;min-height:44px}}"
         "@media print{.wmap .il{fill:#141312;stroke:#f3f1ec}.mregs{grid-template-columns:1fr 1fr}.mreg{background:#fff!important;border-color:#d9d4cb!important}.mreg h3{color:#141312!important}#gia-map-open{display:none}}")
open(f"{D}/map.html","w").write(map_page())

# ---- history pages ----
HD=f"{D}/history"; os.makedirs(HD,exist_ok=True)
# wipe old history html & path dirs (keep nothing stale)
for f in glob.glob(f"{HD}/*.html"): os.remove(f)
for p in glob.glob(f"{HD}/path-*"):
    if os.path.isdir(p): shutil.rmtree(p)

def timeline(stories):
    st=sorted(stories,key=lambda s:(s['date'],s['id'])); o=[]; yr=dt=None
    for s in st:
        if s['date'][:4]!=yr: yr=s['date'][:4]; dt=None; o.append(f'<h3 class="yr" id="y{yr}">{yr}</h3>')
        if ddisp(s)!=dt: dt=ddisp(s); o.append(f'<h4>{dt}</h4>')
        o.append(card(s,pre="",anchor=False))
    return '<div class="tl">'+"".join(o)+'</div>' if o else '<p class="meta">No stories yet.</p>'
def related_ents(stories,exclude=()):
    c=defaultdict(int)
    for s in stories:
        for e in s['entities']:
            if e not in exclude and e in E: c[e]+=1
    return _HT.group([chip(e,"") for e,_ in sorted(c.items(),key=lambda x:-x[1])], "related", cls="")
# r5 (Director 05:01 item 1): history pages load the site's Plex faces (same files + @font-face, path relative to the page)
def HFONT(pre):
    return (_today.fonts(pre)+'body{font-family:"IBM Plex Sans",Arial,Helvetica,sans-serif}'
            'svg text[font-family="Arial"]{font-family:"IBM Plex Sans",Arial,sans-serif}'
            '.gia-badge,.gia-badge *{font-family:"IBM Plex Sans",Arial,sans-serif}')
def page(fn,title,sub,stories,extra="",exclude=()):
    years=sorted({s['date'][:4] for s in stories}); jump=" · ".join(f'<a href="#y{y}">{y}</a>' for y in years)
    open(f"{HD}/{fn}","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} — history</title><style>{CSS}{HFONT("../")}{UI.PRINT_FORCE_LIGHT}</style></head><body id="top">
<header><h1>GIA <b>//</b> HISTORY: {esc(title)}</h1><div class="meta">{sub} · {len(stories)} stor{'y' if len(stories)==1 else 'ies'} · oldest → newest · <a href="../dashboard.html">← Dashboard</a> · <a href="index.html">Archive</a></div><div class="meta">Years: {jump}</div></header><main>
{extra}<h2>Related entities</h2><div>{related_ents(stories,exclude) or '<span class="meta">none</span>'}</div><h2>Timeline</h2>{timeline(stories)}</main></body></html>""")

for e in ENTS:
    st=by[e['id']]; sls=[l for l in SL if e['id'] in l['entities']]; zs=[z for z in HZ['zones'] if e['id'] in z['entities']]
    ex=f'<p class="wik"><a href="{esc(e["wikipedia"])}" target="_blank" rel="noopener">Wikipedia ↗</a></p>'
    if sls: ex+='<h2>Storylines</h2><div>'+"".join(f'<a class="chip sl" href="storyline-{l["id"]}.html">⟿ {esc(l["name"])}</a>' for l in sls)+'</div>'
    if zs: ex+='<h2>Hot zones</h2><div>'+"".join(f'<a class="chip" href="zone-{z["id"]}.html">◉ {esc(z["name"])}</a>' for z in zs)+'</div>'
    rs=sorted([r for r in RELS if e['id'] in (r['a'],r['b'])],key=lambda r:str(r['start']))
    if rs:
        ex+='<h2>Alliances, rivalries &amp; relationships over time</h2><table><tr><th>Period</th><th>Relationship</th><th>Stated</th><th class="an">Actual interest (analysis)</th><th>Evidence</th></tr>'+"".join(
          f'<tr><td>{esc(r["start"])} → {esc(r["end"] or "present")}</td><td><span class="rt {r["type"]}">{r["type"]}</span> <a href="entity-{r["a"]}.html">{esc(E[r["a"]]["name"])}</a> → <a href="entity-{r["b"]}.html">{esc(E[r["b"]]["name"])}</a></td><td>{esc(r["stated"])}</td><td class="an"><span class="conf {r["confidence"]}">{r["confidence"]}</span>{esc(r["actual"])}</td><td>'+" · ".join(f'<a href="trace-{x}.html">{esc(ddisp(ST[x]))}</a>' for x in r["evidence"] if x in ST)+'</td></tr>' for r in rs)+'</table>'
    page(f"entity-{e['id']}.html",e['name'],esc(e['type']),st,ex,exclude=(e['id'],))
ZONE_MAP_R = {"critical": 17, "high": 14, "elevated": 11, "watch": 9}
def zone_map(z, all_zones):
    """Locator map for a hot-zone page: where this zone is, and which other filed zones sit near it.
    Its own window, centred on the zone, so a reader landing from a link gets the region rather than
    the whole world. Same land data, sea/land fills and severity tokens as the edition map."""
    lon, lat = z.get("lon"), z.get("lat")
    if lon is None or lat is None: return ""
    W, H = 1000, 520
    dlon, dlat = 19.0, 11.0
    lon0, lon1 = max(-179.0, lon - dlon), min(179.0, lon + dlon)
    lat0, lat1 = max(-84.0, lat - dlat), min(84.0, lat + dlat)
    def lp(x, y): return ((x - lon0) / (lon1 - lon0) * W, (lat1 - y) / (lat1 - lat0) * H)
    paths = []
    for f in G["features"]:
        g = f["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        d = ""
        for poly in polys:
            for ring in poly:
                if not any(lon0 - 6 <= px <= lon1 + 6 and lat0 - 6 <= py <= lat1 + 6 for px, py in ring): continue
                pts = [lp(px, py) for px, py in ring]
                d += "M" + "L".join(f"{a:.1f},{b:.1f}" for a, b in pts) + "Z"
        if d: paths.append(f'<path d="{d}"/>')
    near = [o for o in all_zones if o["id"] != z["id"] and o.get("lon") is not None
            and lon0 < o["lon"] < lon1 and lat0 < o["lat"] < lat1]
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" class="zmap" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="Locator map: {esc(z["name"])} and {len(near)} other filed hot zone{"" if len(near)==1 else "s"} nearby.">',
           f'<rect class="sea" width="{W}" height="{H}" fill="#0a1a2a"/>',
           f'<g class="land" fill="#1c2a3a" stroke="#3a4f66" stroke-width=".5">{"".join(paths)}</g>']
    for o in near:                                   # neighbours stay quiet: this page is about one zone
        x, y = lp(o["lon"], o["lat"]); c = SEV[o["severity"]][0]
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{c}" fill-opacity=".30" stroke="{c}" stroke-opacity=".55"/>'
                   f'<text x="{x:.1f}" y="{y - 11:.1f}" class="zl zl-n" text-anchor="middle">{esc(o["name"])}</text>')
    x, y = lp(lon, lat); r = ZONE_MAP_R.get(z["severity"], 10); c = SEV[z["severity"]][0]
    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{c}" fill-opacity=".34" stroke="{c}" stroke-width="2"/>'
               f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{c}"/>'
               f'<text x="{x:.1f}" y="{y + r + 20:.1f}" class="zl zl-s" text-anchor="middle">{esc(z["name"])}</text>'
               f'<text x="{x:.1f}" y="{y + r + 38:.1f}" class="zl zl-v" text-anchor="middle" fill="{c}">{esc(z["severity"].upper())}</text>')
    out.append("</svg>")
    return '<div class="zmapwrap">' + "".join(out) + "</div>"

def ents_block(ids): return '<h2>Tagged entities</h2>'+_HT.group([chip(i,"") for i in ids if i in E], "tagged", cls="tags")
for z in HZ['zones']:
    st=[ST[i] for i in z['stories'] if i in ST]; seen={s['id'] for s in st}
    st+=[s for s in S if s['id'] not in seen and len(set(s['entities'])&set(z['entities']))>=2]
    lk=[l for l in HZ['links'] if z['id'] in (l['from'],l['to'])]
    ex=f'<p>Severity: <b>{_sev_word(z["severity"])}</b> · {esc(z["note"])}</p>'+ents_block(z['entities'])+('<h2>Causal links</h2><ul>'+"".join(f'<li><a href="link-{l["id"]}.html">{esc(ZD[l["from"]]["name"])} → {esc(ZD[l["to"]]["name"])}: {esc(l["label"])}</a></li>' for l in lk)+'</ul>' if lk else '')
    ex = zone_map(z, HZ['zones']) + ex
    page(f"zone-{z['id']}.html",z['name'],"Hot zone",st,ex,exclude=z['entities'])
for l in HZ['links']:
    st=[ST[i] for i in l['stories'] if i in ST]
    ex=f'<p><a href="zone-{l["from"]}.html">{esc(ZD[l["from"]]["name"])}</a> → <a href="zone-{l["to"]}.html">{esc(ZD[l["to"]]["name"])}</a>: <b>{esc(l["label"])}</b> <span class="an">(analytic causal link)</span></p>'+ents_block(l['entities'])
    page(f"link-{l['id']}.html",f'{ZD[l["from"]]["name"]} → {ZD[l["to"]]["name"]}',"Causal link",st,ex,exclude=l['entities'])
for l in SL:
    st=[s for s in S if l['id'] in s.get('storylines',[]) or s['id'] in l['stories']]
    page(f"storyline-{l['id']}.html",l['name'],"Storyline",st,ents_block(l['entities']),exclude=l['entities'])

# ---- trace pages ----
TRACE_DEPTH=3  # static causal tree depth; deeper ancestors via their own trace page or gia-trace.js + causal.json
def up_tree(sid,shown,depth=1):
    """Causal DAG rendered once per page: each ancestor is expanded the first time it appears
    (shown = page-global set) and later occurrences are one-line links to its first node.
    Size is O(nodes+edges) instead of O(paths): ARCHITECTURE §6."""
    s=ST[sid]; kids=[c for c in s.get('causes',[]) if c['story'] in ST]
    if not kids: return '<ul class="tree"><li><span class="meta">◆ root (no recorded causes)</span></li></ul>'
    o='<ul class="tree">'
    for c in kids:
        t=ST[c['story']]; tid=t['id']
        why=f'<div class="an"><span class="conf {c["confidence"]}">{c["confidence"]}</span>{esc(c["why"])}</div>'
        if tid in shown:
            o+=f'<li><a href="#n-{tid}">↺ {esc(t["title"])}</a> <span class="meta">{ddisp(t)} · shown above</span>{why}</li>'; continue
        shown.add(tid)
        o+=f'<li id="n-{tid}"><a href="trace-{tid}.html"><b>{esc(t["title"])}</b></a> <span class="meta">{ddisp(t)}</span>{why}'
        up=[x for x in t.get('causes',[]) if x['story'] in ST]
        if not up: o+='<ul class="tree"><li><span class="meta">◆ root (no recorded causes)</span></li></ul>'
        elif depth<TRACE_DEPTH: o+=up_tree(tid,shown,depth+1)
        else: o+=f'<div class="meta">▸ {len(up)} earlier cause{"s" if len(up)!=1 else ""}: <a href="trace-{tid}.html">open its trace</a> <button type="button" class="more" data-id="{tid}" hidden>expand here</button></div>'
        o+='</li>'
    return o+'</ul>'
def collect(sid,key):
    out,st=set(),[sid]
    while st:
        x=st.pop()
        for c in ST[x].get(key,[]):
            if c['story'] in ST and c['story'] not in out: out.add(c['story']); st.append(c['story'])
    return out
for s in S:
    ups=collect(s['id'],'causes'); downs=collect(s['id'],'effects')
    roots=sorted([ST[i] for i in ups if not ST[i].get('causes')],key=lambda x:x['date'])
    chainlist=sorted([ST[i] for i in ups],key=lambda x:x['date'])+[s]
    tl="".join(f'<li{" class=cur" if x is s else ""}><span class="meta">{ddisp(x)}</span> <a href="trace-{x["id"]}.html">{esc(x["title"])}</a></li>' for x in chainlist)
    dl="".join(f'<li><span class="meta">{ddisp(ST[i])}</span> <a href="trace-{i}.html">{esc(ST[i]["title"])}</a></li>' for i in sorted(downs,key=lambda i:ST[i]['date']))
    open(f"{HD}/trace-{s['id']}.html","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trace: {esc(s['title'])}</title><style>{CSS}{HFONT("../")}{UI.PRINT_FORCE_LIGHT}</style></head><body id="top">
<header><h1>GIA <b>//</b> TRACE</h1><div class="meta"><a href="../dashboard.html">← Dashboard</a> · <a href="index.html">Archive</a> · {len(ups)} upstream events · {len(roots)} root{'s' if len(roots)!=1 else ''} · {len(downs)} downstream</div></header><main>
{card(s,pre="",anchor=False)}
<h2>Roots</h2><ul>{"".join(f'<li><span class="meta">{ddisp(r)}</span> <a href="trace-{r["id"]}.html">{esc(r["title"])}</a></li>' for r in roots) or '<li class="meta">This event is itself a root.</li>'}</ul>
<h2>Chronological chain (roots → this event)</h2><ol class="chainlist">{tl}</ol>
<h2>Causal tree: led to this</h2>{up_tree(s['id'],{s['id']})}<script src="../vendor/gia-trace.js" defer></script>
<h2>Downstream: everything it set off</h2><ul>{dl or '<li class="meta">No recorded effects yet.</li>'}</ul>
<p class="meta">Causal links are analytic judgments with confidence labels; events are sourced facts.</p></main></body></html>""")

# ---- Path-to-today slideshow pages ----
def write_path(root, info):
    steps=info['steps']; n=len(steps); pd=f"{HD}/path-{root}"; os.makedirs(pd,exist_ok=True)
    def marked(sid):
        story=ST[sid]; marker=story.get("marker") or "political"
        out=[]
        for ent in story_places(story):
            pin=dict(ent); pin["_marker"]=marker; out.append(pin)
        return out
    firsts=[]
    for sid,_,_ in steps:
        pins=marked(sid); firsts.append(pins[0] if pins else None)
    for i,(sid,why,conf) in enumerate(steps):
        s=ST[sid]; nn=i+1
        active=marked(sid)
        active_ids={p["id"] for p in active}
        past=[]
        seen=set(active_ids)
        for j in range(i):
            for ent in marked(steps[j][0]):
                if ent["id"] in seen: continue
                seen.add(ent["id"]); past.append(ent)
        trail=[p for p in firsts[:i+1] if p]
        t2=[]
        for p in trail:
            if not t2 or (t2[-1]["lat"],t2[-1]["lon"])!=(p["lat"],p["lon"]): t2.append(p)
        if active:
            place=", ".join(p["name"] for p in active)
        else:
            place=s.get("unplaced") or "No honest location for this step"
        prior=[(ddisp(ST[steps[j][0]]), ST[steps[j][0]]['title']) for j in range(i)]
        prevb=None
        if i>0:
            prev_pins=marked(steps[i-1][0]) or past
            prevb=[[p["lat"],p["lon"]] for p in prev_pins] or None
        badge=f'<b style="color:#c3a6ff">NOW · {esc(ddisp(s))} · Step {nn}/{n}</b><br><b>{esc(place)}</b><br><span>{esc(s["title"][:80])}</span>'
        def pack(ent, role):
            return dict(id=ent["id"],name=ent["name"],lat=ent["lat"],lon=ent["lon"],marker=ent["_marker"],role=role,href=f"../entity-{ent['id']}.html")
        places=[pack(p,"past") for p in past]+[pack(p,"active") for p in active]
        trail_pts=[dict(lat=p["lat"],lon=p["lon"]) for p in t2]
        leaf=leaflet_html(dict(mode="path",zones=[],places=places,trailPlaces=trail_pts,prevBounds=prevb,badge=badge),"../../",height=500)
        svg=map_svg(active=active, past=past, trail=t2, now_place=place, now_date=ddisp(s), step_n=nn, step_total=n,
                    story_title=s['title'], prior_steps=prior, region=s.get("region"))
        prev=f'<a class="btn" href="slide-{nn-1:02d}.html">← Prev</a>' if nn>1 else '<a class="btn disabled" href="#">← Prev</a>'
        nxt=f'<a class="btn" href="slide-{nn+1:02d}.html">Next →</a>' if nn<n else f'<a class="btn" href="index.html">Finish ✓</a>'
        dots="".join(f'<a class="gd{" on" if k==nn else " past" if k<nn else ""}" href="slide-{k:02d}.html" title="{esc(ST[steps[k-1][0]]["title"])}" aria-label="Step {k} of {n}: {esc(ST[steps[k-1][0]]["title"])}"{" aria-current=step" if k==nn else ""}></a>' for k in range(1,n+1))
        pct=int(100*nn/n)
        an=s.get('analysis') or {}; ac=an.get('confidence',''); at=an.get('text','')
        src=" · ".join(f'<a href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["name"])}</a>' for x in s['sources'])
        why_html=''
        if nn<n:
            nw,nc=steps[nn][1],steps[nn][2]  # edge why is stored on the destination step
            if nw: why_html=f'<div class="why"><b>Why this led to the next:</b> <span class="an"><span class="conf {nc}">{nc}</span>{esc(nw)}</span></div>'
        nxt_title=esc(ST[steps[nn][0]]['title']) if nn<n else '<span class="meta">Arrived at current day.</span>'
        open(f"{pd}/slide-{nn:02d}.html","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Path {nn}/{n}: {esc(s['title'])}</title><style>{CSS}{SLIDE_CSS}{HFONT("../../")}{UI.PRINT_FORCE_LIGHT}</style></head><body>
<header><h1>GIA <b>//</b> PATH TO TODAY</h1><div class="meta">{esc(info['title'])} · slide {nn} of {n} · <a href="../../dashboard.html">Dashboard</a> · <a href="index.html">Path index</a> · <a href="../trace-{sid}.html">Trace</a></div></header>
<div class="slidewrap">
<div class="navrow">{prev}<div class="prog"><i style="width:{pct}%"></i></div>{nxt}<div class="dots">{dots}</div></div>
<div class="meta">Bright pin = this step · Dim pin = an earlier place · Purple line = the path (dashed earlier steps, solid last step) · No pin means the step has no honest location. Square military, X strike, diamond diplomacy, triangle energy, hollow ring political.</div>
<div id="gia-fallback">{svg}</div>{leaf}
<div class="panel">
<div class="meta">{ddisp(s)} · {esc(s.get('region',''))} · step {nn}/{n} · {esc(place)}</div>
<h2>{esc(s['title'])}</h2>
<p>{esc(s['summary'])}</p>
{(f'<p class="an"><span class="conf {ac}">{ac}</span>{esc(at)}</p>' if at else '')}
<div class="meta">Sources: {src or '—'}</div>
<div class="chips">{"".join(chip(i,"../") for i in s['entities'] if i in E)}</div>
{why_html}
<div class="meta">Next: {nxt_title}</div>
</div>
<div class="navrow">{prev}{nxt}</div>
</div>
<script>(function(){{function go(t){{var a=[].slice.call(document.querySelectorAll('.navrow a.btn')).filter(function(x){{return t.test(x.textContent)&&!x.classList.contains('disabled');}})[0];if(a)location.href=a.href;}}document.addEventListener('keydown',function(e){{if(e.key==='ArrowRight'||e.key===' '){{e.preventDefault();go(/Next|Finish/);}}else if(e.key==='ArrowLeft'){{go(/Prev/);}}}});}})();</script>
</body></html>""")
    # path index
    lis="".join(f'<li><a href="slide-{i+1:02d}.html"><span class="meta">{ddisp(ST[sid])}</span> {esc(ST[sid]["title"])}</a></li>' for i,(sid,_,_) in enumerate(steps))
    open(f"{pd}/index.html","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(info['title'])}</title><style>{CSS}{HFONT("../../")}{UI.PRINT_FORCE_LIGHT}</style></head><body>
<header><h1>GIA <b>//</b> PATH: {esc(info['title'])}</h1><div class="meta">{n} slides · <a href="../../dashboard.html">Dashboard</a> · <a href="../index.html">Archive</a></div></header>
<main><p>{esc(ST[root]['title'])} → … → {esc(ST[info['goal']]['title'])}</p>
<a class="pathbtn" href="slide-01.html">▶ Start slideshow</a>
<ol>{lis}</ol></main></body></html>""")

for root,info in list(PATH_INDEX.items()):
    if "root" in info: continue  # only generate once per demo path
    write_path(root, info)

# archive index
byyear=defaultdict(list)
for s in sorted(S,key=lambda s:(s['date'],s['id'])): byyear[s['date'][:4]].append(s)
for _y,_v in sorted(byyear.items()):  # per-year archive pages (index was 3.5 MB with every card inline)
    open(f"{HD}/year-{_y}.html","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GIA archive {_y}</title><style>{CSS}{HFONT("../")}{UI.PRINT_FORCE_LIGHT}</style></head><body id="top">
<header><h1>GIA <b>//</b> ARCHIVE {_y}</h1><div class="meta">{len(_v)} stories · oldest → newest · <a href="index.html">← Archive</a> · <a href="../dashboard.html">Dashboard</a></div></header><main>{"".join(card(s,pre="") for s in _v)}</main></body></html>""")
arch='<ul class="idx">'+"".join(f'<li><a href="year-{y}.html">{y}</a> <small>{len(v)} stories</small></li>' for y,v in sorted(byyear.items()))+'</ul>'+"".join(
    f'<h3 class="yr" id="y{y}"><a href="year-{y}.html">{y}</a></h3><ul>'+"".join(f'<li id="story-{x["id"]}"><span class="meta">{ddisp(x)}</span> <a href="trace-{x["id"]}.html">{esc(x["title"])}</a></li>' for x in v)+'</ul>' for y,v in sorted(byyear.items()))
lists=('<h2 id="board">Regional board, edition '+esc(ed)+'</h2><div class="boardgrid">'+"".join(board)+'</div>'
 '<h2>Path to today</h2><div class="paths">'+pathcards.replace('history/path-','path-')+'</div>'
 '<h2>Storylines</h2><ul class="idx">'+"".join(f'<li><a href="storyline-{l["id"]}.html">{esc(l["name"])}</a></li>' for l in SL)+'</ul>'
 '<h2>Hot zones</h2><ul class="idx">'+"".join(f'<li><a href="zone-{z["id"]}.html">{esc(z["name"])}</a></li>' for z in HZ['zones'])+'</ul>'
 '<h2>Causal links</h2><ul class="idx">'+"".join(f'<li><a href="link-{l["id"]}.html">{esc(ZD[l["from"]]["name"])} → {esc(ZD[l["to"]]["name"])}</a></li>' for l in HZ['links'])+'</ul>'
 '<h2>Entities</h2><ul class="idx">'+"".join(f'<li><a href="entity-{e["id"]}.html">{esc(e["name"])}</a> <small>{len(by[e["id"]])}</small></li>' for e in order)+'</ul>')
# v7 optional data (markets, reports, assessment log): pages only when the files exist.
from gia_build.v7pages import write_all as _v7
lists=lists+_v7(D,HD,ST,SLD)
open(f"{HD}/index.html","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GIA history archive</title><style>{CSS}{HFONT("../")}{UI.PRINT_FORCE_LIGHT}</style></head><body id="top">
<header><h1>GIA <b>//</b> HISTORY ARCHIVE</h1><div class="meta">{len(S)} stories · {', '.join(sorted(byyear))} · <a href="../dashboard.html">← Dashboard</a></div></header><main>{lists}<h2>All stories by year, oldest → newest</h2>{arch}</main></body></html>""")

# shared causal graph for client-side expansion of trace trees (gia-trace.js); build output, not data/
json.dump({x['id']:[x['title'],ddisp(x),[[c['story'],c['confidence'],c['why']] for c in x.get('causes',[]) if c['story'] in ST]] for x in S},
          open(f"{HD}/causal.json","w"),ensure_ascii=False,separators=(",",":"))
# dump path catalog for SCHEMA
json.dump({k:{"title":v["title"],"goal":v["goal"],"steps":[x[0] for x in v["steps"]]} for k,v in PATH_INDEX.items() if "root" not in v},
          open(f"{D}/data/paths.json","w"),indent=1)
print("wrote dashboard.html;", len(list(glob.glob(f"{HD}/**/*.html",recursive=True))),"history html;",
      len(PATH_INDEX),"path index keys;", sum(1 for k,v in PATH_INDEX.items() if 'root' not in v),"demo paths")

import re as _re
print("static map labels:", {k: v for k, v in MAP_STATS.items() if k not in ("labels", "pins", "halos")})
if os.environ.get("GIA_MAP_GEOM"):   # label audit geometry, written OUTSIDE the site (tests / QA), never into the build dir
    MAP_STATS["phone"]={str(k):v for k,v in PHONE_CHECK.items()}
    json.dump(MAP_STATS, open(os.environ["GIA_MAP_GEOM"], "w"), default=list)
