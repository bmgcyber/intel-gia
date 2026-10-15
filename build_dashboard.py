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
SEV={"critical":("#ff3b30",13),"high":("#ff9f0a",10),"elevated":("#ffd60a",8),"watch":("#64d2ff",6)}

def zones_for_story(s):
    """Hot zones touched by a story. Prefer explicit story tags; else require ≥2 shared entities
    (avoids lighting Hormuz just because a story tags united-states)."""
    ents=set(s.get('entities',[])); hit=[]
    for z in HZ['zones']:
        if s['id'] in z.get('stories',[]): hit.append(z['id']); continue
        shared=ents & set(z.get('entities',[]))
        if len(shared)>=2: hit.append(z['id'])
    # region fallback so every slide lights something
    if not hit:
        REGZ={"Russia/Eurasia":["ukraine","russia"],"Middle East":["hormuz","yemen","saudi","iraq"],
              "Africa":["drc","mali"],"Asia-Pacific":["taiwan","china"],"Americas":["venezuela","india"],
              "Europe":["ukraine","russia"]}
        for zid in REGZ.get(s.get('region',''),[]):
            if zid in ZD: hit.append(zid)
    return hit

def primary_zone(s):
    zs=zones_for_story(s)
    if not zs: return None
    ents=set(s.get('entities',[]))
    order={"critical":0,"high":1,"elevated":2,"watch":3}
    # prefer most shared entities, then severity (stops petroleum stories lighting Hormuz over Saudi)
    return sorted(zs, key=lambda i: (-len(ents & set(ZD[i].get('entities',[]))), order.get(ZD[i]['severity'],9)))[0]

def map_svg(active=None, past=None, trail=None, href_prefix="../", show_links=True, current_label=None, now_place=None, now_date=None, step_n=None, step_total=None, story_title=None, prior_steps=None):
    """Render world map. Auto-zooms to active theater. Current zones bright+labeled; past dim; rest nearly invisible."""
    active=set(active or []); past=set(past or [])-active
    # --- compute crop around action ---
    focus_ids=list(active) or list(past) or [z['id'] for z in HZ['zones'][:1]]
    # theater presets (lon0,lon1,lat0,lat1) — tighter than world
    THEATERS={
        "gulf":(30,65,8,40), "eeurope":(10,55,35,65), "sahel":(-20,50,-10,30),
        "easia":(95,145,5,45), "americas":(-100,-40,-20,25), "world":(LON0,LON1,LAT0,LAT1),
    }
    # pick theater by which active/past zones dominate
    ZTHEATER={"hormuz":"gulf","yemen":"gulf","saudi":"gulf","iraq":"gulf","india":"gulf",
              "ukraine":"eeurope","russia":"eeurope",
              "mali":"sahel","drc":"sahel",
              "taiwan":"easia","china":"easia",
              "venezuela":"americas"}
    votes={}
    for zid in list(active)+list(past):
        t=ZTHEATER.get(zid,"world"); votes[t]=votes.get(t,0)+(2 if zid in active else 1)
    theater=max(votes, key=votes.get) if votes else "world"
    lon0,lon1,lat0,lat1=THEATERS[theater]
    # further tighten around active zone centroids with padding
    if active:
        lons=[ZD[z]['lon'] for z in active]; lats=[ZD[z]['lat'] for z in active]
        if past:
            lons+=[ZD[z]['lon'] for z in past]; lats+=[ZD[z]['lat'] for z in past]
        pad_lon=max(12,(max(lons)-min(lons))*0.8+8); pad_lat=max(8,(max(lats)-min(lats))*0.8+6)
        lon0=max(LON0, min(lons)-pad_lon); lon1=min(LON1, max(lons)+pad_lon)
        lat0=max(LAT0, min(lats)-pad_lat); lat1=min(LAT1, max(lats)+pad_lat)
        if lon1-lon0<20: mid=(lon0+lon1)/2; lon0,lon1=mid-10,mid+10
        if lat1-lat0<14: mid=(lat0+lat1)/2; lat0,lat1=mid-7,mid+7
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
    out=[f'<svg viewBox="0 0 {W} {H}" width="100%" class="wmap" xmlns="http://www.w3.org/2000/svg">',
         f'<rect width="{W}" height="{H}" fill="#071018"/>',
         f'<g fill="#152030" stroke="#2a3f55" stroke-width="0.6">{"".join(paths)}</g>']
    # trail arcs (only up through this step)
    if trail and len(trail)>=2:
        for i in range(len(trail)-1):
            a,b=trail[i],trail[i+1]
            if a not in ZD or b not in ZD: continue
            if a==b: continue
            x1,y1=lp(ZD[a]['lon'],ZD[a]['lat']); x2,y2=lp(ZD[b]['lon'],ZD[b]['lat'])
            mx,my=(x1+x2)/2,(y1+y2)/2; dx,dy=x2-x1,y2-y1; cx,cy=mx-dy*.25,my+dx*.25
            last=i==len(trail)-2
            out.append(f'<path d="M{x1:.0f},{y1:.0f}Q{cx:.0f},{cy:.0f} {x2:.0f},{y2:.0f}" fill="none" stroke="{"#ffe08a" if last else "#ff6b5f"}" stroke-width="{4 if last else 2}" opacity="{.95 if last else .4}" stroke-dasharray="{"0" if last else "6 4"}"/>')
    # inactive first (nearly invisible)
    for z in HZ['zones']:
        zid=z['id']
        if zid in active or zid in past: continue
        x,y=lp(z['lon'],z['lat'])
        if x<-50 or x>W+50 or y<-50 or y>H+50: continue
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="4" fill="#1a2838" opacity=".35"/>')
    # past zones
    for zid in past:
        z=ZD[zid]; x,y=lp(z['lon'],z['lat']); c,_=SEV[z['severity']]
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="18" fill="{c}" opacity=".12" stroke="{c}" stroke-width="2" stroke-dasharray="4 3"/>'
                   f'<circle cx="{x:.0f}" cy="{y:.0f}" r="6" fill="{c}" opacity=".55"/>'
                   f'<text x="{x+12:.0f}" y="{y-10:.0f}" fill="#99aabb" font-size="12" font-family="Arial" opacity=".7">{esc(z["name"])}</text>')
    # active zones — BIG
    for zid in active:
        z=ZD[zid]; x,y=lp(z['lon'],z['lat']); c,_=SEV[z['severity']]
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="42" fill="{c}" opacity=".2"/>'
                   f'<circle cx="{x:.0f}" cy="{y:.0f}" r="28" fill="none" stroke="{c}" stroke-width="3" opacity=".85"/>'
                   f'<circle cx="{x:.0f}" cy="{y:.0f}" r="12" fill="{c}" stroke="#fff" stroke-width="3"/>'
                   f'<text x="{x+20:.0f}" y="{y-18:.0f}" fill="#000" font-size="16" font-weight="bold" font-family="Arial">{esc(z["name"])}</text>'
                   f'<text x="{x+19:.0f}" y="{y-19:.0f}" fill="#fff" font-size="16" font-weight="bold" font-family="Arial">{esc(z["name"])}</text>')
    # NOW badge (always changes per slide) — includes story title so same-theater paths still look different
    place=esc(now_place or (ZD[next(iter(active))]['name'] if active else '—'))
    date=esc(now_date or '')
    step=f'Step {step_n}/{step_total}' if step_n else ''
    title=esc((story_title or '')[:72])
    out.append(f'<rect x="16" y="12" width="520" height="78" rx="8" fill="#0b0f14" fill-opacity=".92" stroke="#ff5a4f" stroke-width="2"/>'
               f'<text x="28" y="34" fill="#ff5a4f" font-size="13" font-weight="bold" font-family="Arial">NOW · {date} · {step}</text>'
               f'<text x="28" y="54" fill="#ffffff" font-size="16" font-weight="bold" font-family="Arial">{place}</text>'
               f'<text x="28" y="74" fill="#c8d4e0" font-size="12" font-family="Arial">{title}</text>')
    # prior-step timeline pills (grow each slide) — key for Ukraine-only paths
    if prior_steps:
        y=100
        out.append(f'<text x="28" y="{y}" fill="#7f8fa3" font-size="11" font-family="Arial">Path so far</text>'); y+=6
        for i,(pd,pt) in enumerate(prior_steps[-8:]):  # last 8
            y+=18
            out.append(f'<rect x="28" y="{y-12}" width="8" height="8" rx="2" fill="#ff5a4f" opacity=".5"/>'
                       f'<text x="42" y="{y-4}" fill="#9aa8b8" font-size="11" font-family="Arial">{esc(pd)} · {esc(pt[:40])}</text>')
    # theater tag
    out.append(f'<text x="{W-12}" y="28" fill="#7f8fa3" font-size="11" font-family="Arial" text-anchor="end">zoom: {theater}</text>')
    out.append('</svg>')
    return "".join(out)

def world_map_dashboard():
    # Full-world dashboard map (no path zoom)
    SEV_L=SEV; Z={z['id']:z for z in HZ['zones']}
    out=[f'<svg viewBox="0 0 {MW} {MH}" width="100%" class="wmap" xmlns="http://www.w3.org/2000/svg"><defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L10,5L0,10z" fill="#ff6b5f"/></marker></defs>',
         f'<rect width="{MW}" height="{MH}" fill="#0a1a2a"/><g fill="#1c2a3a" stroke="#3a4f66" stroke-width=".5">{"".join(COUNTRY_PATHS)}</g>']
    for i,l in enumerate(HZ['links']):
        a,b=l['from'],l['to']; x1,y1=pj(Z[a]['lon'],Z[a]['lat']); x2,y2=pj(Z[b]['lon'],Z[b]['lat'])
        mx,my=(x1+x2)/2,(y1+y2)/2; dx,dy=x2-x1,y2-y1; k=.25 if i%2 else -.25; cx,cy=mx-dy*k,my+dx*k
        out.append(f'<a href="history/link-{l["id"]}.html"><path d="M{x1:.0f},{y1:.0f}Q{cx:.0f},{cy:.0f} {x2:.0f},{y2:.0f}" fill="none" stroke="#ff6b5f" stroke-width="1.6" stroke-dasharray="5 3" marker-end="url(#ah)" opacity=".85"/><circle cx="{(mx+cx)/2:.0f}" cy="{(my+cy)/2-4:.0f}" r="8" fill="#3a1414" stroke="#ff6b5f"/><text x="{(mx+cx)/2:.0f}" y="{(my+cy)/2:.0f}" fill="#ffd0cc" font-size="10" font-weight="bold" font-family="Arial" text-anchor="middle">{i+1}</text></a>')
    for z in HZ['zones']:
        x,y=pj(z['lon'],z['lat']); c,r=SEV_L[z['severity']]
        out.append(f'<a href="history/zone-{z["id"]}.html"><circle cx="{x:.0f}" cy="{y:.0f}" r="{r*1.8}" fill="{c}" opacity=".25"/><circle cx="{x:.0f}" cy="{y:.0f}" r="{r/2+2}" fill="{c}" stroke="#000" stroke-width="1"/><text x="{x+z.get("label_dx",r)+1:.0f}" y="{y+z.get("label_dy",-r/2)+1:.0f}" fill="#000" font-size="11" font-weight="bold" font-family="Arial">{esc(z["name"])}</text><text x="{x+z.get("label_dx",r):.0f}" y="{y+z.get("label_dy",-r/2):.0f}" fill="#fff" font-size="11" font-weight="bold" font-family="Arial">{esc(z["name"])}</text></a>')
    out.append('</svg>'); svg="".join(out)
    leg='<div class="legend">'+" ".join(f'<span><i style="background:{c}"></i>{k}</span>' for k,(c,_) in SEV.items())+'</div>'
    lk='<ol class="links">'+"".join(f'<li><a href="history/zone-{l["from"]}.html">{esc(ZD[l["from"]]["name"])}</a> → <a href="history/zone-{l["to"]}.html">{esc(ZD[l["to"]]["name"])}</a>: {esc(l["label"])} · <a href="history/link-{l["id"]}.html">History</a></li>' for l in HZ['links'])+'</ol>'
    zl='<ul class="zones">'+"".join(f'<li><a href="history/zone-{z["id"]}.html">{esc(z["name"])}</a> <small>{z["severity"]}</small>: {esc(z["note"])}</li>' for z in HZ['zones'])+'</ul>'
    return svg, leg+'<div class="two">'+lk+zl+'</div>'


# ---- Leaflet progressive enhancement (vendored Leaflet 1.9.4; Carto dark tiles need network) ----
def zone_payload(href_prefix):
    return [dict(id=z['id'],name=z['name'],lat=z['lat'],lon=z['lon'],sev=z['severity'],color=SEV[z['severity']][0],
                 r=SEV[z['severity']][1],note=z.get('note',''),href=f"{href_prefix}zone-{z['id']}.html") for z in HZ['zones']]
def leaflet_html(data, vprefix, height=520):
    js=json.dumps(data,ensure_ascii=False).replace('</','<\\/')
    return (f'<link rel="stylesheet" href="{vprefix}vendor/leaflet/leaflet.css">'
            f'<div id="gia-leaflet" style="display:none;height:{height}px;border:1px solid #223041;border-radius:8px;background:#071018"></div>'
            f'<script type="application/json" id="gia-map-data">{js}</script>'
            f'<script src="{vprefix}vendor/leaflet/leaflet.js"></script><script src="{vprefix}vendor/gia-map.js"></script>')

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

def chip(i,pre="history/"): return f'<a class="chip" href="{pre}entity-{i}.html" title="History of {esc(E[i]["name"])}">{esc(E[i]["name"])}</a>'
def chain(s,pre):
    def li(c):
        t=ST.get(c['story']); return f'<li><a href="{pre}trace-{t["id"]}.html">{esc(t["title"])}</a> <span class="meta">{ddisp(t)}</span> — <span class="an"><span class="conf {c["confidence"]}">{c["confidence"]}</span>{esc(c["why"])}</span></li>' if t else ''
    o=''
    if s.get('causes'): o+='<div class="cz"><b>⬆ Led to this</b><ul>'+''.join(li(c) for c in s['causes'])+'</ul></div>'
    if s.get('effects'): o+='<div class="cz"><b>⬇ What it set off</b><ul>'+''.join(li(c) for c in s['effects'])+'</ul></div>'
    return o+f'<div class="meta"><a href="{pre}trace-{s["id"]}.html">⟲ Trace causal chain</a></div>'+path_btn(s['id'],pre)
def card(s,pre="history/",home="",anchor=True):
    a=f' id="story-{s["id"]}"' if anchor else ''
    src=" · ".join(f'<a href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["name"])}</a>' for x in s['sources'])
    an=s.get('analysis') or {}; c=an.get('confidence','')
    sls="".join(f'<a class="chip sl" href="{pre}storyline-{l}.html">⟿ {esc(SLD[l]["name"])}</a>' for l in s.get('storylines',[]) if l in SLD)
    rel=" · ".join(f'<a href="{pre}index.html#story-{r}">{esc(ST[r]["title"])}</a>' for r in s.get('related_stories',[]) if r in ST)
    rev="".join(f'<div class="meta">Corrected in {esc(v.get("edition",""))}: {esc(v.get("why",""))}</div>' for v in s.get("revisions") or [])
    return (f'<article class="card"{a}><h3>{esc(s["title"])}</h3><div class="meta">{ddisp(s)} · {esc(s.get("region",""))} · {esc(s.get("kind","event"))}</div>'
            f'<p>{esc(s["summary"])}</p>{rev}'+(f'<p class="an"><span class="conf {c}">{c}</span>{esc(an.get("text",""))}</p>' if an else '')+
            f'<div class="meta">Sources: {src}</div><div class="chips">{"".join(chip(i,pre) for i in s["entities"] if i in E)}</div>'
            +(f'<div class="chips">{sls}</div>' if sls else '')+chain(s,pre)+(f'<div class="rel">Related: {rel}</div>' if rel else '')+'</article>')

CSS="""body{margin:0;background:#0b0f14;color:#d6dde6;font:14px/1.5 Arial,Helvetica,sans-serif}header{padding:16px 24px;border-bottom:1px solid #1f2a36;background:#0f1722}
h1{margin:0;font-size:20px;letter-spacing:.08em;color:#fff}h1 b{color:#ff5a4f}h2{color:#8fb6ff;font-size:13px;letter-spacing:.12em;text-transform:uppercase;border-left:3px solid #ff5a4f;padding-left:8px;margin-top:26px}
main{padding:0 24px 40px;max-width:1300px;margin:auto}a{color:#6fb1ff}.meta,small{color:#7f8fa3;font-size:12px}
.boardgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.reg{background:#111821;border:1px solid #223041;border-radius:8px;padding:8px}.reg ul{margin:6px 0 0;padding-left:16px}
.card{background:#111821;border:1px solid #223041;border-radius:8px;padding:12px 14px;margin-bottom:12px}.card h3{margin:0 0 4px;font-size:15px;color:#fff}
.an{color:#b9a7ff;font-style:italic}.conf{font-style:normal;font-size:10px;padding:1px 6px;border-radius:8px;margin-right:6px;text-transform:uppercase}.likely{background:#173d24;color:#7fe0a0}.possible{background:#4d3208;color:#ffbf5a}.speculative{background:#3a1430;color:#ff8bd2}
.chip{display:inline-block;margin:3px 4px 0 0;padding:1px 8px;border-radius:10px;background:#1b2d4a;color:#a9c8ff;font-size:12px;text-decoration:none}
.idx{columns:4;list-style:none;padding:0}.idx li{break-inside:avoid}
.wmap{border:1px solid #223041;border-radius:8px;display:block}.wmap .zs{fill:#000;font-size:11px;font-weight:bold}.wmap .zl{fill:#fff;font-size:11px;font-weight:bold}
.legend span{margin-right:14px;font-size:12px}.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}.two{display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:13px}.links,.zones{margin:6px 0}
:target{outline:2px solid #ff5a4f;background:#1a1f2b}#q{padding:6px;background:#121a24;border:1px solid #2a3a4e;color:#fff;border-radius:6px;width:260px}.tl h3.yr{color:#ff5a4f;font-size:18px;margin:22px 0 4px}.tl h4{color:#8fb6ff;margin:10px 0 4px;font-size:13px}.sl{background:#2a1f3a;color:#d6b8ff}
.cz{font-size:12px;margin-top:6px}.cz ul{margin:2px 0;padding-left:18px}.tree{border-left:2px solid #ff5a4f55;margin-left:6px;padding-left:16px;list-style:none}.tree li{margin:6px 0}.chainlist li.cur{color:#ff5a4f;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{border-bottom:1px solid #1f2a36;padding:5px;text-align:left;vertical-align:top}.rt{font-size:10px;padding:1px 6px;border-radius:8px;background:#1b2d4a}.rt.rivalry{background:#4a1b1b}.rt.alliance{background:#173d24}.rt.patron-proxy{background:#3a2a10}.rt.sanction{background:#3a1430}.rel{font-size:12px;color:#9aa8b8}
.gia-badge{background:#0b0f14e6;border:2px solid #ff5a4f;border-radius:8px;padding:8px 12px;color:#fff;font:13px Arial;max-width:340px}.gia-tip{background:#0b0f14;color:#fff;border:1px solid #ff5a4f;font-weight:bold}.gia-tip.dim{border-color:#445;color:#9ab;font-weight:normal}@keyframes giapulse{0%{stroke-width:3;stroke-opacity:1}50%{stroke-width:14;stroke-opacity:.25}100%{stroke-width:3;stroke-opacity:1}}.gia-pulse{animation:giapulse 1.6s ease-in-out infinite}.leaflet-container{background:#071018}
.pathbtn{display:inline-block;margin-top:8px;padding:8px 14px;background:#ff5a4f;color:#fff!important;text-decoration:none;border-radius:6px;font-weight:700;font-size:13px}.pathbtn:hover{background:#ff7a70}
.slidewrap{max-width:1100px;margin:auto;padding:12px 20px 40px}.navrow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:10px 0}
.navrow a.btn{padding:8px 16px;background:#1b2d4a;color:#a9c8ff;text-decoration:none;border-radius:6px;font-weight:700}
.navrow a.btn.disabled{opacity:.3;pointer-events:none}.dots a{display:inline-block;width:10px;height:10px;border-radius:50%;background:#3a4f66;margin:0 3px;text-decoration:none}
.dots a.on{background:#ff5a4f;transform:scale(1.3)}.prog{flex:1;height:6px;background:#1f2a36;border-radius:3px;overflow:hidden}.prog i{display:block;height:100%;background:#ff5a4f}
.panel{background:#111821;border:1px solid #223041;border-radius:8px;padding:14px 16px;margin-top:10px}.panel h2{margin:0 0 6px;color:#fff;font-size:18px;border:0;letter-spacing:0;text-transform:none;padding:0}
.why{background:#1a1428;border-left:3px solid #b9a7ff;padding:8px 12px;margin-top:10px}
.paths{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}.pathcard{background:#111821;border:1px solid #223041;border-radius:8px;padding:12px}"""

WMAP,WLEG=world_map_dashboard()
LEAF_DASH=leaflet_html(dict(mode="dashboard",zones=zone_payload("history/"),
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

out=f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>GIA World Intel — {ed}</title><style>{CSS}</style></head><body id="top">
<header><h1>GIA <b>//</b> WORLD INTEL</h1><div class="meta">Edition {ed} · {len(LATEST)} stories this edition · {len(S)} in archive · {len(ENTS)} entities · <span class="an">purple = analysis with confidence label</span> · works without JavaScript</div>
<div class="meta"><a href="#world">World map</a> · <a href="#paths">Path to today</a> · <a href="#board">Regional board</a> · <a href="#storylines">Storylines</a> · <a href="#stories">Stories</a> · <a href="#index">Entity index</a> · <a href="history/index.html">Full history archive</a></div></header><main>
<h2 id="world">World hot zones</h2><div class="meta">Markers are sized and colored by severity (analysis). Click a marker or a numbered arc to open its history timeline. Interactive map (Leaflet, Esri dark-gray tiles with OpenStreetMap data) when JavaScript and network are available; static map otherwise.</div><div id="gia-fallback">{WMAP}</div>{LEAF_DASH}{WLEG}
<h2 id="paths">Path to current day</h2><div class="meta">Click a past event, then walk the causal chain forward as a slideshow on the world map — no JavaScript required.</div><div class="paths">{pathcards}</div>
<h2 id="board">Regional board</h2><div class="boardgrid">{"".join(board)}</div>
<h2 id="storylines">Storylines (history)</h2><ul class="idx">{slh}</ul>
<h2 id="stories">Stories, edition {ed}</h2><div class="meta">Each chip opens that entity's history timeline. Look for the red <b>Path to current day</b> button on backfilled events.</div>{"".join(card(s) for s in sorted(LATEST,key=lambda s:s['date'],reverse=True))}
<h2 id="index">Entity index (history)</h2><input id="q" placeholder="Filter (needs JS; optional)" hidden><ul class="idx" id="idxl">{idx}</ul>
<p class="meta">Sources linked on each story. Generated by build_dashboard.py.</p></main>
<script>(function(){{var q=document.getElementById('q');if(!q)return;q.hidden=false;q.oninput=function(){{var v=q.value.toLowerCase();document.querySelectorAll('#idxl li').forEach(function(l){{l.style.display=l.dataset.n.indexOf(v)>=0?'':'none';}});}};}})();</script>
</body></html>"""
open(f"{D}/dashboard.html","w").write(out)

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
    return "".join(chip(e,"") for e,_ in sorted(c.items(),key=lambda x:-x[1]))
def page(fn,title,sub,stories,extra="",exclude=()):
    years=sorted({s['date'][:4] for s in stories}); jump=" · ".join(f'<a href="#y{y}">{y}</a>' for y in years)
    open(f"{HD}/{fn}","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{esc(title)} — history</title><style>{CSS}</style></head><body id="top">
<header><h1>GIA <b>//</b> HISTORY: {esc(title)}</h1><div class="meta">{sub} · {len(stories)} stor{'y' if len(stories)==1 else 'ies'} · oldest → newest · <a href="../dashboard.html">← Dashboard</a> · <a href="index.html">Archive</a></div><div class="meta">Years: {jump}</div></header><main>
{extra}<h2>Related entities</h2><div>{related_ents(stories,exclude) or '<span class="meta">none</span>'}</div><h2>Timeline</h2>{timeline(stories)}</main></body></html>""")

for e in ENTS:
    st=by[e['id']]; sls=[l for l in SL if e['id'] in l['entities']]; zs=[z for z in HZ['zones'] if e['id'] in z['entities']]
    ex=f'<p><a href="{esc(e["wikipedia"])}" target="_blank" rel="noopener">Wikipedia ↗</a></p>'
    if sls: ex+='<h2>Storylines</h2><div>'+"".join(f'<a class="chip sl" href="storyline-{l["id"]}.html">⟿ {esc(l["name"])}</a>' for l in sls)+'</div>'
    if zs: ex+='<h2>Hot zones</h2><div>'+"".join(f'<a class="chip" href="zone-{z["id"]}.html">◉ {esc(z["name"])}</a>' for z in zs)+'</div>'
    rs=sorted([r for r in RELS if e['id'] in (r['a'],r['b'])],key=lambda r:str(r['start']))
    if rs:
        ex+='<h2>Alliances, rivalries &amp; relationships over time</h2><table><tr><th>Period</th><th>Relationship</th><th>Stated</th><th class="an">Actual interest (analysis)</th><th>Evidence</th></tr>'+"".join(
          f'<tr><td>{esc(r["start"])} → {esc(r["end"] or "present")}</td><td><span class="rt {r["type"]}">{r["type"]}</span> <a href="entity-{r["a"]}.html">{esc(E[r["a"]]["name"])}</a> → <a href="entity-{r["b"]}.html">{esc(E[r["b"]]["name"])}</a></td><td>{esc(r["stated"])}</td><td class="an"><span class="conf {r["confidence"]}">{r["confidence"]}</span>{esc(r["actual"])}</td><td>'+" · ".join(f'<a href="trace-{x}.html">{esc(ddisp(ST[x]))}</a>' for x in r["evidence"] if x in ST)+'</td></tr>' for r in rs)+'</table>'
    page(f"entity-{e['id']}.html",e['name'],esc(e['type']),st,ex,exclude=(e['id'],))
def ents_block(ids): return '<h2>Tagged entities</h2><div>'+"".join(chip(i,"") for i in ids if i in E)+'</div>'
for z in HZ['zones']:
    st=[ST[i] for i in z['stories'] if i in ST]; seen={s['id'] for s in st}
    st+=[s for s in S if s['id'] not in seen and len(set(s['entities'])&set(z['entities']))>=2]
    lk=[l for l in HZ['links'] if z['id'] in (l['from'],l['to'])]
    ex=f'<p>Severity: <b>{z["severity"]}</b> · {esc(z["note"])}</p>'+ents_block(z['entities'])+('<h2>Causal links</h2><ul>'+"".join(f'<li><a href="link-{l["id"]}.html">{esc(ZD[l["from"]]["name"])} → {esc(ZD[l["to"]]["name"])}: {esc(l["label"])}</a></li>' for l in lk)+'</ul>' if lk else '')
    page(f"zone-{z['id']}.html",z['name'],"Hot zone",st,ex,exclude=z['entities'])
for l in HZ['links']:
    st=[ST[i] for i in l['stories'] if i in ST]
    ex=f'<p><a href="zone-{l["from"]}.html">{esc(ZD[l["from"]]["name"])}</a> → <a href="zone-{l["to"]}.html">{esc(ZD[l["to"]]["name"])}</a>: <b>{esc(l["label"])}</b> <span class="an">(analytic causal link)</span></p>'+ents_block(l['entities'])
    page(f"link-{l['id']}.html",f'{ZD[l["from"]]["name"]} → {ZD[l["to"]]["name"]}',"Causal link",st,ex,exclude=l['entities'])
for l in SL:
    st=[s for s in S if l['id'] in s.get('storylines',[]) or s['id'] in l['stories']]
    page(f"storyline-{l['id']}.html",l['name'],"Storyline",st,ents_block(l['entities']),exclude=l['entities'])

# ---- trace pages ----
def up_tree(sid,seen):
    s=ST[sid]; kids=[c for c in s.get('causes',[]) if c['story'] in ST]
    if not kids: return '<ul class="tree"><li><span class="meta">◆ root (no recorded causes)</span></li></ul>'
    o='<ul class="tree">'
    for c in kids:
        t=ST[c['story']]; o+=f'<li><a href="trace-{t["id"]}.html"><b>{esc(t["title"])}</b></a> <span class="meta">{ddisp(t)}</span><div class="an"><span class="conf {c["confidence"]}">{c["confidence"]}</span>{esc(c["why"])}</div>'
        o+=('<div class="meta">↺ already shown above</div>' if t['id'] in seen else up_tree(t['id'],seen|{t['id']}))+'</li>'
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
    open(f"{HD}/trace-{s['id']}.html","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Trace: {esc(s['title'])}</title><style>{CSS}</style></head><body id="top">
<header><h1>GIA <b>//</b> TRACE</h1><div class="meta"><a href="../dashboard.html">← Dashboard</a> · <a href="index.html">Archive</a> · {len(ups)} upstream events · {len(roots)} root{'s' if len(roots)!=1 else ''} · {len(downs)} downstream</div></header><main>
{card(s,pre="",anchor=False)}
<h2>Roots</h2><ul>{"".join(f'<li><span class="meta">{ddisp(r)}</span> <a href="trace-{r["id"]}.html">{esc(r["title"])}</a></li>' for r in roots) or '<li class="meta">This event is itself a root.</li>'}</ul>
<h2>Chronological chain (roots → this event)</h2><ol class="chainlist">{tl}</ol>
<h2>Causal tree: led to this</h2>{up_tree(s['id'],{s['id']})}
<h2>Downstream: everything it set off</h2><ul>{dl or '<li class="meta">No recorded effects yet.</li>'}</ul>
<p class="meta">Causal links are analytic judgments with confidence labels; events are sourced facts.</p></main></body></html>""")

# ---- Path-to-today slideshow pages ----
def write_path(root, info):
    steps=info['steps']; n=len(steps); pd=f"{HD}/path-{root}"; os.makedirs(pd,exist_ok=True)
    # precompute primary zones along path for trail
    prims=[]
    for sid,_,_ in steps:
        pz=primary_zone(ST[sid]); prims.append(pz)
    for i,(sid,why,conf) in enumerate(steps):
        s=ST[sid]; nn=i+1
        past_ids=set()
        for j in range(i): past_ids |= set(zones_for_story(ST[steps[j][0]]))
        active=set(zones_for_story(s))
        trail=[p for p in prims[:i+1] if p]
        # collapse consecutive duplicates in trail for cleaner arcs
        t2=[]
        for z in trail:
            if not t2 or t2[-1]!=z: t2.append(z)
        # place label: prefer primary zone name, else region
        pz=primary_zone(s); place=(ZD[pz]['name'] if pz else s.get('region','—'))
        # if trail is a single repeated zone, still show step markers by appending synthetic offsets via step badge
        prior=[(ddisp(ST[steps[j][0]]), ST[steps[j][0]]['title']) for j in range(i)]
        prevb=None
        if i>0:
            pa=set(zones_for_story(ST[steps[i-1][0]])); prevb=[[ZD[z]['lat'],ZD[z]['lon']] for z in pa] or None
        badge=f'<b style="color:#ff5a4f">NOW · {esc(ddisp(s))} · Step {nn}/{n}</b><br><b>{esc(ZD[primary_zone(s)]["name"] if primary_zone(s) else s.get("region",""))}</b><br><span>{esc(s["title"][:80])}</span>'
        leaf=leaflet_html(dict(mode="path",zones=zone_payload("../"),active=sorted(active),past=sorted(past_ids-active),trail=t2,prevBounds=prevb,badge=badge),"../../",height=500)
        svg=map_svg(active=active, past=past_ids, trail=t2, href_prefix="../", show_links=False,
                    current_label=ddisp(s), now_place=place, now_date=ddisp(s), step_n=nn, step_total=n,
                    story_title=s['title'], prior_steps=prior)
        prev=f'<a class="btn" href="slide-{nn-1:02d}.html">← Prev</a>' if nn>1 else '<a class="btn disabled" href="#">← Prev</a>'
        nxt=f'<a class="btn" href="slide-{nn+1:02d}.html">Next →</a>' if nn<n else f'<a class="btn" href="index.html">Finish ✓</a>'
        dots="".join(f'<a class="{"on" if k==nn else ""}" href="slide-{k:02d}.html" title="{esc(ST[steps[k-1][0]]["title"])}"></a>' for k in range(1,n+1))
        pct=int(100*nn/n)
        an=s.get('analysis') or {}; ac=an.get('confidence',''); at=an.get('text','')
        src=" · ".join(f'<a href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["name"])}</a>' for x in s['sources'])
        why_html=''
        if nn<n:
            nw,nc=steps[nn][1],steps[nn][2]  # edge why is stored on the destination step
            if nw: why_html=f'<div class="why"><b>Why this led to the next:</b> <span class="an"><span class="conf {nc}">{nc}</span>{esc(nw)}</span></div>'
        nxt_title=esc(ST[steps[nn][0]]['title']) if nn<n else '<span class="meta">Arrived at current day.</span>'
        open(f"{pd}/slide-{nn:02d}.html","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Path {nn}/{n}: {esc(s['title'])}</title><style>{CSS}</style></head><body>
<header><h1>GIA <b>//</b> PATH TO TODAY</h1><div class="meta">{esc(info['title'])} · slide {nn} of {n} · <a href="../../dashboard.html">Dashboard</a> · <a href="index.html">Path index</a> · <a href="../trace-{sid}.html">Trace</a></div></header>
<div class="slidewrap">
<div class="navrow">{prev}<div class="prog"><i style="width:{pct}%"></i></div>{nxt}<div class="dots">{dots}</div></div>
<div class="meta">Bright = active this step · Dim = earlier in path · Gold arc = path so far</div>
<div id="gia-fallback">{svg}</div>{leaf}
<div class="panel">
<div class="meta">{ddisp(s)} · {esc(s.get('region',''))} · step {nn}/{n}</div>
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
    open(f"{pd}/index.html","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{esc(info['title'])}</title><style>{CSS}</style></head><body>
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
arch="".join(f'<h3 class="yr" id="y{y}">{y}</h3>'+"".join(card(s,pre="") for s in v) for y,v in sorted(byyear.items()))
lists=('<h2>Path to today</h2><div class="paths">'+pathcards.replace('history/path-','path-')+'</div>'
 '<h2>Storylines</h2><ul class="idx">'+"".join(f'<li><a href="storyline-{l["id"]}.html">{esc(l["name"])}</a></li>' for l in SL)+'</ul>'
 '<h2>Hot zones</h2><ul class="idx">'+"".join(f'<li><a href="zone-{z["id"]}.html">{esc(z["name"])}</a></li>' for z in HZ['zones'])+'</ul>'
 '<h2>Causal links</h2><ul class="idx">'+"".join(f'<li><a href="link-{l["id"]}.html">{esc(ZD[l["from"]]["name"])} → {esc(ZD[l["to"]]["name"])}</a></li>' for l in HZ['links'])+'</ul>'
 '<h2>Entities</h2><ul class="idx">'+"".join(f'<li><a href="entity-{e["id"]}.html">{esc(e["name"])}</a> <small>{len(by[e["id"]])}</small></li>' for e in order)+'</ul>')
open(f"{HD}/index.html","w").write(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>GIA history archive</title><style>{CSS}</style></head><body id="top">
<header><h1>GIA <b>//</b> HISTORY ARCHIVE</h1><div class="meta">{len(S)} stories · {', '.join(sorted(byyear))} · <a href="../dashboard.html">← Dashboard</a></div></header><main>{lists}<h2>All stories, oldest → newest</h2>{arch}</main></body></html>""")

# dump path catalog for SCHEMA
json.dump({k:{"title":v["title"],"goal":v["goal"],"steps":[x[0] for x in v["steps"]]} for k,v in PATH_INDEX.items() if "root" not in v},
          open(f"{D}/data/paths.json","w"),indent=1)
print("wrote dashboard.html;", len(list(glob.glob(f"{HD}/**/*.html",recursive=True))),"history html;",
      len(PATH_INDEX),"path index keys;", sum(1 for k,v in PATH_INDEX.items() if 'root' not in v),"demo paths")

# ---- Parallel CesiumJS 3D build (derived from the Leaflet pages) ----
import re as _re
CES="https://cdnjs.cloudflare.com/ajax/libs/cesium/1.122.0/"
def to_cesium(h, vprefix):
    h=_re.sub(r'<link rel="stylesheet" href="[^"]*vendor/leaflet/leaflet.css">', f'<link rel="stylesheet" href="{CES}Widgets/widgets.css">', h)
    h=h.replace('<div id="gia-leaflet" style="display:none;','<div id="gia-cesium" style="display:none;overflow:hidden;')
    h=_re.sub(r'<script src="[^"]*vendor/leaflet/leaflet.js"></script><script src="[^"]*vendor/gia-map.js"></script>',
              f'<script>window.CESIUM_BASE_URL="{CES}";</script><script src="{CES}Cesium.js"></script><script src="{vprefix}vendor/gia-cesium.js"></script>', h)
    return h
def add_toggle(h, href, label):
    return h.replace('</header>', f'<div class="meta" style="margin-top:4px"><a class="pathbtn" style="padding:4px 10px;font-size:12px;margin:0" href="{href}">{label}</a></div></header>',1)
dash=open(f"{D}/dashboard.html").read()
ced=to_cesium(dash,"")
ced=_re.sub(r'(history/path-[^"/]+/)slide-(\d\d)\.html', r'\1slide-\2-cesium.html', ced)
ced=ced.replace('Interactive map (Leaflet,','Interactive 3D globe (CesiumJS 1.122, served over http;').replace('<title>GIA World Intel','<title>GIA 3D (Cesium) World Intel')
open(f"{D}/dashboard-cesium.html","w").write(add_toggle(ced,"dashboard.html","↩ 2D Leaflet version"))
open(f"{D}/dashboard.html","w").write(add_toggle(dash,"dashboard-cesium.html","🌐 Try 3D Cesium version"))
for f in glob.glob(f"{HD}/path-*/slide-??.html"):
    h=open(f).read(); base=os.path.basename(f); c=base.replace('.html','-cesium.html')
    ch=to_cesium(h,"../../")
    ch=_re.sub(r'href="slide-(\d\d)\.html"', r'href="slide-\1-cesium.html"', ch)
    ch=ch.replace('href="../../dashboard.html"','href="../../dashboard-cesium.html"')
    open(f.replace(base,c),"w").write(add_toggle(ch,base,"↩ 2D Leaflet version of this slide"))
    open(f,"w").write(add_toggle(h,c,"🌐 3D Cesium version of this slide"))
print("cesium build: dashboard-cesium.html +", len(glob.glob(f"{HD}/path-*/slide-??-cesium.html")), "cesium slides")
