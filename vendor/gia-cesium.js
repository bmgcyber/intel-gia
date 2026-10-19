/* GIA CesiumJS globe (pinned CDN Cesium 1.122.0). Same embedded #gia-map-data as the Leaflet build.
   No Cesium Ion token needed: Ion is disabled, imagery = Esri dark gray (keyless), ellipsoid terrain.
   Hot zones are rings. Event places use a glyph per marker. */
(function(){
  var CRITG='<svg class="critg" viewBox="0 0 32 32" aria-hidden="true" focusable="false" style="width:12px;height:12px;fill:var(--gia-sev-glyph);vertical-align:-1px;margin-right:3px"><path d="M16,2C8.3,2,2,8.3,2,16s6.3,14,14,14s14-6.3,14-14C30,8.3,23.7,2,16,2z M14.9,8h2.2v11h-2.2V8z M16,25c-0.8,0-1.5-0.7-1.5-1.5S15.2,22,16,22c0.8,0,1.5,0.7,1.5,1.5S16.8,25,16,25z"/></svg>';  // Carbon warning--filled before 'critical' (spec Follow-ups A)
  var el=document.getElementById('gia-map-data'), box=document.getElementById('gia-cesium');
  if(!el||!box||typeof Cesium==='undefined') return;
  if(location.protocol==='file:'){
    var n=document.createElement('div');n.className='gia-badge';n.style.cssText='margin:6px 0;border-color:var(--gia-accent-ui)';
    n.innerHTML='The 3D globe needs a local web server (browsers block Cesium workers on file://). Double-click <b>open-3d.command</b> (Mac) / <b>open-3d.bat</b> (Windows) in the dashboard folder, or run <code>python3 -m http.server 8000</code> there and open http://localhost:8000/dashboard-cesium.html. Showing the static map meanwhile.';
    box.parentNode.insertBefore(n,box); return; }
  var D; try{D=JSON.parse(el.textContent);}catch(e){return;}
  try{
    Cesium.Ion.defaultAccessToken='';
    box.style.display='block';
    var esri=new Cesium.UrlTemplateImageryProvider({url:'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
      maximumLevel:16,credit:'Tiles © Esri, HERE, Garmin, © OpenStreetMap contributors'});
    var v=new Cesium.Viewer(box,{baseLayer:new Cesium.ImageryLayer(esri),terrainProvider:new Cesium.EllipsoidTerrainProvider(),
      geocoder:false,homeButton:false,sceneModePicker:true,baseLayerPicker:false,navigationHelpButton:false,animation:false,timeline:false,
      fullscreenButton:false,infoBox:false,selectionIndicator:false,
      useBrowserRecommendedResolution:false,msaaSamples:1,
      // r3 (Director 03:03): render only on request. Camera moves, tile loads and canvas resizes already request a frame
      // inside Cesium; everything else this file changes calls wake() below. Nothing animates while idle.
      requestRenderMode:true,maximumRenderTimeChange:Infinity});
    var RR={why:{},n:0};   // QA: which element asked for frames (counts by reason), and frames rendered
    function wake(why,ms){RR.why[why]=(RR.why[why]||0)+1; v.scene.requestRender();
      // 'for ms after a data change': keep requesting frames until the deadline, then go silent
      if(ms){var end=performance.now()+ms;(function f(){if(performance.now()<end){v.scene.requestRender();requestAnimationFrame(f);}})();}}
    v.scene.postRender.addEventListener(function(){RR.n++;});
    window.addEventListener('resize',function(){wake('resize');});
    // Sharpness at DPR>1 (ARCHITECTURE §9 #1): render at device pixels, capped at 2x so phones and
    // 3x screens stay fast; drop to CSS-pixel resolution once if the first frames are slow. FXAA
    // replaces MSAA (cheaper on integrated/software GPUs).
    var DPR=window.devicePixelRatio||1, CAP=2;
    v.resolutionScale=Math.min(DPR,CAP)/DPR;
    v.scene.postProcessStages.fxaa.enabled=true;
    // Adaptive fallback (r5; r4 Director 04:24 item 1, QA rounds 5-6; Director 05:58 item 1). The r3 version timed the gaps
    // between postRender events (idle gaps in, GPU time out). r4 timed forced frames one per rAF from 1.5 s while tiles,
    // imagery and sprites were still loading, so it also counted their uploads (344 ms vs QA's 79 ms at dpr 1).
    // Now ONE window, started only by the ready signal below: the slide fly-in is done AND scene.globe.tilesLoaded is true
    // (and that frame has rendered), plus a 300 ms settle. WARM=3 forced frames are discarded, then N=10 are timed back to
    // back in one task with nothing else in the window. Each timed frame = requestRender() + render() + one 1-pixel
    // gl.readPixels (which waits for the GPU to finish that frame). Median of the 10 = the real per-frame cost at the current
    // scale: > 40 ms -> drop to 1x (CSS pixels). If tiles are not loaded within CAP_MS (15 s) the window never runs: the
    // scale stays as set (2x on a 2x screen) and the source reads 'timeout'; no judgement is made from loading frames.
    // Nothing is requested after the window except one 'fallback' frame when the scale changes, so idle stays at 0 frames.
    // Readout on the globe container (and <html>): data-gia-globe-ms = that median, data-gia-globe-scale = the decision,
    // data-gia-globe-frames = timed samples, data-gia-globe-scale-source = adaptive | override | timeout,
    // data-gia-globe-tiles-loaded = "true <ms waited>" | "timeout <ms waited>" (container only).
    // ?gia-scale=1 or ?gia-scale=2 forces the scale and skips the measurement.
    var GIA_SAMPLE=null, GIA_OUT=null, CAP_MS=15000;
    (function(){var THRESH=40, WARM=3, N=10, gl=null;
      function out(sc,src,m,n){sc=String(sc);box.dataset.giaGlobeScale=sc;box.dataset.giaGlobeScaleSource=src;box.dataset.giaGlobeMs=m;
        box.dataset.giaGlobeFrames=String(n);document.documentElement.dataset.giaGlobeScale=sc;document.documentElement.dataset.giaGlobeScaleSource=src;}
      GIA_OUT=out;
      var q=/[?&]gia-scale=([12])(?:&|$)/.exec(location.search);
      if(q){var f=+q[1];v.resolutionScale=f/DPR;wake('override');out(f,'override','',0);return;}
      try{gl=(v.scene.context&&v.scene.context._gl)||v.scene.canvas.getContext('webgl2')||v.scene.canvas.getContext('webgl');}catch(e){gl=null;}
      var px=new Uint8Array(4);
      function frame(){var t0=performance.now();v.scene.requestRender();v.render();
        if(gl)gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px);RR.why.sample=(RR.why.sample||0)+1;return performance.now()-t0;}
      // returns true when the scale changed (the caller waits for that frame before signalling ready)
      GIA_SAMPLE=function(){var ms=[],i,g=v.scene.globe,su=g&&g._surface,ql=function(q){return q?q.length:null;};window.GIA_SAMPLE_STATE={t:+performance.now().toFixed(0),tilesLoaded:g.tilesLoaded,queue:su?{high:ql(su._tileLoadQueueHigh),medium:ql(su._tileLoadQueueMedium),low:ql(su._tileLoadQueueLow)}:null,imageryPending:(function(){try{var n=0,L=v.imageryLayers;for(var j=0;j<L.length;j++){var c=L.get(j)._imageryCache;for(var k in c){var im=c[k];if(im&&im.state!==Cesium.ImageryState.READY&&im.state!==Cesium.ImageryState.FAILED&&im.state!==Cesium.ImageryState.INVALID)n++;}}return n;}catch(e){return null;}})()};for(i=0;i<WARM;i++)frame();for(i=0;i<N;i++)ms.push(frame());
        var srt=ms.slice().sort(function(a,b){return a-b;}),m=(srt[(N>>1)-1]+srt[N>>1])/2,ch=false;
        if(m>THRESH&&v.resolutionScale>1/DPR){v.resolutionScale=1/DPR;ch=true;}
        out(Math.round(v.resolutionScale*DPR*100)/100,'adaptive',m.toFixed(1)+(gl?'':' (no readPixels sync)'),ms.length);
        window.GIA_SAMPLE_MS=ms;return ch;};})();
    var ref=new Cesium.UrlTemplateImageryProvider({url:'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',maximumLevel:16});
    v.imageryLayers.addImageryProvider(ref).alpha=.7;
    v.scene.globe.baseColor=Cesium.Color.fromCssColorString('#071018');
    v.scene.backgroundColor=Cesium.Color.fromCssColorString('#05080c');
    var Z={};(D.zones||[]).forEach(function(z){Z[z.id]=z;});
    var JUDG=Cesium.Color.fromCssColorString('#c3a6ff');  // hifi tokens.css --judg (dark set)
    // Marker tokens (gia_build/markers.py -> :root --gia-marker-<type>[-shape|-glyph]); no colour is hard-coded here.
    var _cs=getComputedStyle(document.documentElement);
    function mk(t,f){var v=_cs.getPropertyValue('--gia-marker-'+t+(f?'-'+f:'')).trim();return f==='glyph'?v.replace(/^"|"$/g,''):v;}
    function mkKind(m){return mk(m)?m:'political';}
    function mkCol(m){return mk(mkKind(m))||'#8d8d8d';}  // neutral grey only if the page has no token CSS
    function mkShape(m){return mk(mkKind(m),'shape')||'ring';}
    function mkGlyph(m){return mk(mkKind(m),'glyph')||'○';}
    // Batched place sprites (Director 01:30 ET): ONE BillboardCollection + ONE LabelCollection for every event place,
    // no Entities. Geometry comes from markers.py via :root tokens (--gia-shape-<shape>-d/-paint/-w, --gia-sprite-*),
    // so the Designer's shapes are a data-only edit. Each shape+colour+state is rasterised ONCE (Path2D on a canvas,
    // at min(DPR,2) device px) and registered in the collection's texture atlas under that key via setImage(key,…),
    // so every marker of the same kind reuses one atlas slot.
    function tok(n){return _cs.getPropertyValue(n).trim().replace(/^"|"$/g,'');}
    var SPR={outline:tok('--gia-sprite-outline')||'#0b0f14',on:+tok('--gia-sprite-active')||18,off:+tok('--gia-sprite-past')||12,
      offA:+tok('--gia-sprite-past-alpha')||1}, SDPR=Math.min(window.devicePixelRatio||1,2), SPRITES={};
    function sprite(shape,col,active){
      var key='gia-'+shape+'-'+col+'-'+(active?'on':'off');
      if(SPRITES[key]) return SPRITES[key];
      var css=active?SPR.on:SPR.off, px=Math.ceil(css*SDPR), c=document.createElement('canvas'); c.width=c.height=px;
      var g=c.getContext('2d'), d=tok('--gia-shape-'+shape+'-d')||tok('--gia-shape-ring-d'), paint=tok('--gia-shape-'+shape+'-paint')||'stroke',
          w=+tok('--gia-shape-'+shape+'-w')||2, path=new Path2D(d);
      g.scale(px/16,px/16); g.globalAlpha=active?1:SPR.offA; g.lineJoin='round'; g.lineCap='round';
      if(paint==='fill'){g.lineWidth=w*2;g.strokeStyle=SPR.outline;g.stroke(path);g.fillStyle=col;g.fill(path);}
      else{g.lineWidth=w+2.4;g.strokeStyle=SPR.outline;g.stroke(path);g.lineWidth=w;g.strokeStyle=col;g.stroke(path);}
      return (SPRITES[key]={key:key,canvas:c,css:css});
    }
    // TRANSLUCENT only: sprites and SDF labels have soft alpha edges, and one blend pass = one draw command per collection
    var BB=v.scene.primitives.add(new Cesium.BillboardCollection({scene:v.scene,blendOption:Cesium.BlendOption.TRANSLUCENT})),
        LB=v.scene.primitives.add(new Cesium.LabelCollection({scene:v.scene,blendOption:Cesium.BlendOption.TRANSLUCENT}));
    // QA hook (browser check pending): primitives, sprites and the last frame's command count
    window.GIA_PLACES={billboards:BB,labels:LB,sprites:SPRITES,count:function(){v.scene.render();
      return {entities:v.entities.values.length,primitives:v.scene.primitives.length,billboards:BB.length,labels:LB.length,
              sprites:Object.keys(SPRITES).length,commands:v.scene.frameState.commandList.length};}};
    function kick(n){wake('sprite');  // requestRenderMode-safe: re-render until every sprite is in the atlas (setImage)
      if(n>0&&BB.length&&!(function(){for(var k=0;k<BB.length;k++){var b=BB.get(k);if(b.show&&b.ready===false)return false;   /* r4: hidden (image-less) leader slots never block idle */}return true;})())
        requestAnimationFrame(function(){kick(n-1);}); }
    function arc(a,b,color,width,dash,height){
      var pos=[],n=40,h=height||Math.min(1500000,Cesium.Cartesian3.distance(Cesium.Cartesian3.fromDegrees(a.lon,a.lat),Cesium.Cartesian3.fromDegrees(b.lon,b.lat))*0.25);
      for(var i=0;i<=n;i++){var t=i/n;pos.push(Cesium.Cartesian3.fromDegrees(a.lon+(b.lon-a.lon)*t,a.lat+(b.lat-a.lat)*t,Math.sin(Math.PI*t)*h));}
      return v.entities.add({polyline:{positions:pos,width:width,material:dash?new Cesium.PolylineDashMaterialProperty({color:color,dashLength:16}):new Cesium.PolylineGlowMaterialProperty({color:color,glowPower:.25})}});
    }
    // Globe trail (spec "Follow-ups B"): past segments dashed (gap transparent, dash 14, width 3, alpha .9),
    // today's (last) segment solid #c3a6ff, width 5.
    function trail(a,b,last){
      var pos=[],n=40,h=Math.min(1500000,Cesium.Cartesian3.distance(Cesium.Cartesian3.fromDegrees(a.lon,a.lat),Cesium.Cartesian3.fromDegrees(b.lon,b.lat))*0.25);
      for(var i=0;i<=n;i++){var t=i/n;pos.push(Cesium.Cartesian3.fromDegrees(a.lon+(b.lon-a.lon)*t,a.lat+(b.lat-a.lat)*t,Math.sin(Math.PI*t)*h));}
      return v.entities.add({polyline:{positions:pos,width:last?5:3,material:last?new Cesium.ColorMaterialProperty(JUDG)
        :new Cesium.PolylineDashMaterialProperty({color:JUDG.withAlpha(.9),gapColor:Cesium.Color.TRANSPARENT,dashLength:14})}});
    }
    (D.links||[]).forEach(function(l,i){var a=Z[l.from],b=Z[l.to];if(!a||!b)return;
      var e=arc(a,b,JUDG.withAlpha(.7),2,true);  // causal link = judgment layer, not severity
      e.name=(i+1)+'. '+l.label; e.description='<p>'+l.label+'</p><p><a href="'+l.href+'" target="_top">Link history →</a></p>';});
    var tr=D.trailPlaces||[];
    for(var i=0;i<tr.length-1;i++){var a=tr[i],b=tr[i+1];if(!a||!b||(a.lat===b.lat&&a.lon===b.lon))continue;var last=i===tr.length-2;
      trail(a,b,last);}  // path to today: purple (tokens --judg); red is severity only
    // Severity tokens (gia_build/ui_tokens.py -> :root --gia-sev-<level>[-outline]); no severity hex in JS.
    var _ss=getComputedStyle(document.documentElement);
    function sevTok(l,f){return _ss.getPropertyValue('--gia-sev-'+l+(f?'-'+f:'')).trim();}
    function sevCol(l){return sevTok(l)||sevTok('watch')||'#8d8d8d';}
    function sevLine(l){var o=sevTok(l,'outline');return o&&o!=='none'?o:null;}  // dark keyline hook, 'none' = off
    var SEV_OPX=+(_ss.getPropertyValue('--gia-sev-outline-px').trim())||1;
    var AREA_LIFT=1500;  // m: dashed area line above its dark keyline at height 0
    // Ring sprite (Director 01:41 ET): the 3 px severity ring of radius r*2 px (same geometry as the old point: pixelSize r*2,
    // outlineWidth 3) with the --gia-sev-<l>-outline keyline (--gia-sev-outline-px) baked in on both sides; 'none' = no keyline.
    // Rasterised once per level+size+state at min(DPR,2) and cached; registered by key in the shared BillboardCollection atlas.
    function ringSprite(l,r){
      var c=sevCol(l), kl=sevLine(l), key='gia-zone-'+l+'-'+r+'-'+c+'-'+(kl||'none')+'-'+SEV_OPX;
      if(SPRITES[key]) return SPRITES[key];
      // spec.md 19 Oct: 3px ring centred on r, 1px keyline each side, 1px AA margin: css = 2r+3+2*opx+2 -> 33/27/23/19 at r 13/10/8/6
      var W=3, css=2*r+W+2*(kl?SEV_OPX:0)+2, px=Math.ceil(css*SDPR), cv=document.createElement('canvas');
      cv.width=cv.height=px; var g=cv.getContext('2d'); g.scale(px/css,px/css);
      g.beginPath(); g.arc(css/2,css/2,r,0,Math.PI*2);
      if(kl){g.lineWidth=W+2*SEV_OPX; g.strokeStyle=kl; g.stroke();}
      g.lineWidth=W; g.strokeStyle=c; g.stroke();
      return (SPRITES[key]={key:key,canvas:cv,css:css});
    }
    var mode=D.mode, focus=[];
    var ZFONT='600 13px "IBM Plex Sans", Arial', ZOFF=[14,-10], SRANK={critical:0,high:1,elevated:2,watch:3}, LABS=[];
    if(mode==='dashboard'){
      (D.zones||[]).forEach(function(z){
        var col=Cesium.Color.fromCssColorString(sevCol(z.sev)), kl=sevLine(z.sev), P=Cesium.Cartesian3.fromDegrees(z.lon,z.lat);
        if(z.area){var polys=z.area.type==='Polygon'?[z.area.coordinates]:z.area.coordinates;  // sourced theater outline (hot zone `area`)
          polys.forEach(function(pg){var ring=pg[0],flat=[],up=[];ring.forEach(function(q){flat.push(q[0],q[1]);up.push(q[0],q[1],AREA_LIFT);});
            v.entities.add({polygon:{hierarchy:Cesium.Cartesian3.fromDegreesArray(flat),material:col.withAlpha(.14),height:0}});
            // Area keyline (Director 01:41 ET): a solid dark polyline at height 0, the dashed severity line lifted AREA_LIFT m
            // above it, so the depth test always draws the dash on top (deterministic, no z-fighting). All keylines share one
            // solid-colour material, so Cesium batches them into ONE primitive: +1 draw command for all areas together.
            if(kl) v.entities.add({name:'gia-area-keyline',polyline:{positions:Cesium.Cartesian3.fromDegreesArray(flat),width:2+2*SEV_OPX,arcType:Cesium.ArcType.GEODESIC,
              material:new Cesium.ColorMaterialProperty(Cesium.Color.fromCssColorString(kl))}});
            v.entities.add({polyline:{positions:Cesium.Cartesian3.fromDegreesArrayHeights(up),width:2,clampToGround:false,arcType:Cesium.ArcType.GEODESIC,
              material:new Cesium.PolylineDashMaterialProperty({color:col,dashLength:12})}});});}
        // Severity ring = ONE cached billboard sprite per level (ring + its keyline baked in), in the shared BillboardCollection.
        // (a zone with a filed `area` is drawn as that outline, not a ring: same either/or as Leaflet and the static map)
        var rs=z.area?null:ringSprite(z.sev,z.r), zpid={name:z.name,description:{getValue:function(){return '<p><b>'+(z.sev==='critical'?CRITG:'')+z.sev+'</b> · '+(z.note||'')+'</p><p><a href="'+z.href+'" target="_top">Hot zone →</a></p>';}}};
        if(rs){var rb=BB.add({position:P,width:rs.css,height:rs.css,id:zpid,disableDepthTestDistance:Number.POSITIVE_INFINITY}); rb.setImage(rs.key,rs.canvas);}
        // r3 (Director 03:03): zone labels in IBM Plex Sans 600 13px (light tx-1, #0b0f14 outline like the place labels),
        // LEFT/CENTER at a fixed pixel offset so their screen box is known exactly for the declutter below.
        var e=v.entities.add({name:z.name,position:P,
          label:{text:z.name,font:ZFONT,fillColor:Cesium.Color.fromCssColorString(tok('--gia-label')||'#f3efe7'),outlineColor:Cesium.Color.fromCssColorString('#0b0f14'),outlineWidth:4,
            style:Cesium.LabelStyle.FILL_AND_OUTLINE,horizontalOrigin:Cesium.HorizontalOrigin.LEFT,verticalOrigin:Cesium.VerticalOrigin.CENTER,
            pixelOffset:new Cesium.Cartesian2(ZOFF[0],ZOFF[1]),disableDepthTestDistance:Number.POSITIVE_INFINITY},
          description:zpid.description.getValue()});
        // r4 (Director 03:53): a zone label that collides with a higher-ranked zone label moves onto a short leader instead
        // of hiding. The leader is a billboard in the shared collection (no extra primitive), hidden until needed.
        var lb=BB.add({position:P,show:false,disableDepthTestDistance:Number.POSITIVE_INFINITY});
        LABS.push({kind:'zone',id:z.id,name:z.name,pos:P,font:ZFONT,ox:ZOFF[0],oy:ZOFF[1],h:13,rank:SRANK[z.sev]===undefined?9:SRANK[z.sev],pid:zpid,
          rr:rs?rs.css/2:8,lb:lb,cand:null,why:'',
          set:function(on){e.label.show=on;},
          place:function(c){var o=c?[c.ox,c.oy]:ZOFF;e.label.pixelOffset=new Cesium.Cartesian2(o[0],o[1]);
            if(c){var sp=leaderSprite(c);lb.setImage(sp.key,sp.canvas);lb.width=sp.w;lb.height=sp.h;lb.pixelOffset=new Cesium.Cartesian2(c.mx,c.my);lb.show=true;kick(30);}
            else lb.show=false;},shown:true});
        focus.push(z);
      });
    }
    (D.places||[]).forEach(function(p){
      var active=p.role==='active'||p.role==='today', pos=Cesium.Cartesian3.fromDegrees(p.lon,p.lat), sp=sprite(mkShape(p.marker),mkCol(p.marker),active);
      // pick payload in the same shape the click handler reads from entities (name + description.getValue())
      var html='<p>'+(p.marker||'')+'</p>'+(p.href?'<p><a href="'+p.href+'" target="_top">Open →</a></p>':''),
          pid={name:p.name,description:{getValue:function(){return html;}}};
      var b=BB.add({position:pos,width:sp.css,height:sp.css,id:pid,disableDepthTestDistance:Number.POSITIVE_INFINITY});
      b.setImage(sp.key,sp.canvas);
      // spec.md 19 Oct "Map labels at AA": light labels (tx-1 #f3efe7 active / tx-2 #d0cac0 past) with a #0b0f14 outline;
      // the sprite carries the type, so no text glyph (spec.md 19 Oct); label at pixelOffset (css/2+6, 0), LEFT origin.
      var pf=(active?'600 12px':'400 11px')+' "IBM Plex Sans", Arial';
      var lab=LB.add({position:pos,id:pid,text:p.name,font:pf,   /* room 01:58 (r4: 600): active 600 12 tx-1, past 400 11 tx-2 */
        fillColor:Cesium.Color.fromCssColorString(active?(tok('--gia-label')||'#f3efe7'):(tok('--gia-label-past')||'#d0cac0')),outlineColor:Cesium.Color.fromCssColorString('#0b0f14'),outlineWidth:4,
        style:Cesium.LabelStyle.FILL_AND_OUTLINE,horizontalOrigin:Cesium.HorizontalOrigin.LEFT,verticalOrigin:Cesium.VerticalOrigin.CENTER,
        pixelOffset:new Cesium.Cartesian2(sp.css/2+6,0),disableDepthTestDistance:Number.POSITIVE_INFINITY});
      LABS.push({kind:'place',id:p.name,name:p.name,pos:pos,font:pf,ox:sp.css/2+6,oy:0,h:active?12:11,rank:active?10:20,pid:pid,
        set:function(on){lab.show=on;},shown:true});
      focus.push(p);
    });
    kick(120);
    // Label declutter (r3, Director 03:03 item 3), in screen space: zone labels outrank place labels (then severity, then
    // active before past places). A label whose box (text + 2 px outline, boxes may not even touch) meets a higher-priority
    // visible box is hidden at this camera; labels on the far side of the globe are hidden too. Re-run on every camera
    // change, so a hidden place label returns on zoom-in; hovering a place shows its label until the pointer leaves.
    var _mc=document.createElement('canvas').getContext('2d'), W2C=Cesium.SceneTransforms.worldToWindowCoordinates||Cesium.SceneTransforms.wgs84ToWindowCoordinates;
    function tw(L){if(L.w===undefined){_mc.font=L.font;L.w=_mc.measureText(L.name).width;}return L.w;}
    // Leader sprites (r4): 1 px #8d8d8d like the 2D leaders, on a 3 px #0b0f14 casing (the label outline colour) so it
    // reads over imagery. One cached canvas per (ring radius, distance, angle): a fixed, finite candidate set.
    var LDR_MAX=70, LDR_ANG=[0,30,-30,60,-60,90,-90,120,-120,150,-150,180];
    function leaderSprite(c){var key='gia-ldr-'+c.k;if(SPRITES[key])return SPRITES[key];
      var w=Math.abs(c.x2-c.x1)+6,h=Math.abs(c.y2-c.y1)+6,cv=document.createElement('canvas');cv.width=Math.ceil(w*SDPR);cv.height=Math.ceil(h*SDPR);
      var g=cv.getContext('2d');g.scale(SDPR,SDPR);var ax=3+(c.x1<=c.x2?0:c.x1-c.x2),ay=3+(c.y1<=c.y2?0:c.y1-c.y2),bx=ax+c.x2-c.x1,by=ay+c.y2-c.y1;
      g.lineCap='round';g.strokeStyle='#0b0f14';g.lineWidth=3;g.beginPath();g.moveTo(ax,ay);g.lineTo(bx,by);g.stroke();
      g.strokeStyle='#8d8d8d';g.lineWidth=1;g.beginPath();g.moveTo(ax,ay);g.lineTo(bx,by);g.stroke();
      return (SPRITES[key]={key:key,canvas:cv,w:w,h:h});}
    function hits(b,kept){return kept.some(function(k){return !(b[2]<k[0]||b[0]>k[2]||b[3]<k[1]||b[1]>k[3]);});}
    function segHits(x1,y1,x2,y2,kept){for(var t=0;t<=1.0001;t+=1/16){var x=x1+(x2-x1)*t,y=y1+(y2-y1)*t;
      if(kept.some(function(k){return x>=k[0]&&x<=k[2]&&y>=k[1]&&y<=k[3];}))return true;}return false;}
    // candidate offsets for a zone label: attach point A at distance d (ring edge + 10..70 px) and angle a; the box hangs off A
    // on the side away from the mark; the leader runs from the ring edge to A (drawn length = d - rr <= 70 px)
    function leaderFor(L,q,kept,rings){var w=tw(L)+4,hh=L.h*.6+2,rr=L.rr;
      for(var len=10;len<=LDR_MAX;len+=10)for(var i=0;i<LDR_ANG.length;i++){var a=LDR_ANG[i]*Math.PI/180,cx=Math.cos(a),cy=-Math.sin(a),d=rr+len;
        var Ax=Math.round(cx*d),Ay=Math.round(cy*d),x0=cx>0.3?Ax:(cx<-0.3?Ax-w:Ax-w/2),yc=cy>0.6?Ay+hh:(cy<-0.6?Ay-hh:Ay);
        var b=[q.x+x0,q.y+yc-hh,q.x+x0+w,q.y+yc+hh];
        if(hits(b,kept)||hits(b,rings))continue;
        var x1=Math.round(cx*rr),y1=Math.round(cy*rr);
        if(segHits(q.x+x1,q.y+y1,q.x+Ax,q.y+Ay,kept))continue;
        return {k:rr+'-'+len+'-'+LDR_ANG[i],ox:x0+2,oy:yc,x1:x1,y1:y1,x2:Ax,y2:Ay,mx:(x1+Ax)/2,my:(y1+Ay)/2,len:len,ang:LDR_ANG[i],box:b};}
      return null;}
    var HOVER=null, LAST=[];
    function declutter(){
      var occ=new Cesium.EllipsoidalOccluder(Cesium.Ellipsoid.WGS84,v.camera.positionWC), kept=[], changed=false, vis=[], rings=[];
      // screen boxes of every front-facing zone mark (labels never sit on another zone's ring)
      LABS.forEach(function(L){L.q=null;L.front=occ.isPointVisible(L.pos);if(L.front){L.q=W2C(v.scene,L.pos);
        if(L.q&&L.kind==='zone')rings.push([L.q.x-L.rr,L.q.y-L.rr,L.q.x+L.rr,L.q.y+L.rr,L]);}});
      LABS.slice().sort(function(a,b){return a.rank-b.rank||(a.name<b.name?-1:1);}).forEach(function(L){
        var on=false, b=null, q=L.q, cand=null, why=L.front?'offscreen':'far';
        if(q){var x0=q.x+L.ox-2,yc=q.y+L.oy,hh=L.h*.6+2;b=[x0,yc-hh,x0+tw(L)+4,yc+hh];why='';
            on=!hits(b,kept);
            if(!on&&L.kind==='zone'){   // r4: zone vs zone -> short leader, never hidden while front-facing
              var others=rings.filter(function(R){return R[4]!==L;});cand=leaderFor(L,q,kept,others);
              if(cand){on=true;b=cand.box;why='leader';}else why='nofit';}
            else if(!on)why='collision';
            if(!on&&HOVER&&L.pid===HOVER){on=true;why='hover';}   // hover wins for its own label
            if(on){kept.push(b);vis.push({kind:L.kind,name:L.name,box:b.map(function(n){return Math.round(n*10)/10;}),leader:cand?cand.len:0,ang:cand?cand.ang:null});}}
        L.why=why;
        if(L.kind==='zone'){var k=cand?cand.k:'';if(k!==(L.cand?L.cand.k:'')){L.cand=cand;L.place(cand);changed=true;}}
        if(on!==L.shown){L.shown=on;L.set(on);changed=true;}});
      LAST=vis; if(changed)wake('declutter');}
    v.camera.percentageChanged=0.02; v.camera.changed.addEventListener(declutter); v.camera.moveEnd.addEventListener(declutter);
    new Cesium.ScreenSpaceEventHandler(v.scene.canvas).setInputAction(function(m){var p=v.scene.pick(m.endPosition),h=null;
      if(Cesium.defined(p)&&p.id&&LABS.some(function(L){return L.pid===p.id;}))h=p.id;
      if(h!==HOVER){HOVER=h;declutter();}},Cesium.ScreenSpaceEventType.MOUSE_MOVE);
    v.scene.canvas.addEventListener('pointerleave',function(){if(HOVER){HOVER=null;declutter();}});   // leaving the globe ends a hover
    // QA hook: the visible label boxes at the current camera (screen px) and the render-request log
    window.GIA_LABELS={visible:function(){declutter();return LAST;},hidden:function(){return LABS.filter(function(L){return !L.shown;}).map(function(L){return L.kind+':'+L.name;});},
      state:function(){declutter();return LABS.filter(function(L){return L.kind==='zone';}).map(function(L){return {name:L.name,rank:L.rank,shown:L.shown,why:L.why||'',
        leader:L.cand?{len:L.cand.len,ang:L.cand.ang,from:[L.cand.x1,L.cand.y1],to:[L.cand.x2,L.cand.y2]}:null};});}};
    window.GIA_RENDER=RR;
    // fonts first: Cesium rasterises label glyphs once, so Plex must be loaded before the first frame that draws them
    if(document.fonts&&document.fonts.load){Promise.all([document.fonts.load(ZFONT),document.fonts.load('600 12px "IBM Plex Sans"'),document.fonts.load('400 11px "IBM Plex Sans"')])
      .then(function(){LABS.forEach(function(L){L.w=undefined;});declutter();wake('fonts');},function(){});}
    function rect(zs,pad){var lo=zs.map(function(z){return z.lon;}),la=zs.map(function(z){return z.lat;});
      return Cesium.Rectangle.fromDegrees(Math.min.apply(0,lo)-pad,Math.max(-85,Math.min.apply(0,la)-pad),Math.max.apply(0,lo)+pad,Math.min(85,Math.max.apply(0,la)+pad));}
    var FLOWN=mode==='dashboard';
    var pins=(D.places||[]).filter(function(p){return p.role==='active';});
    if(!pins.length) pins=(D.places||[]);
    if(mode==='dashboard'){ v.camera.setView({destination:Cesium.Cartesian3.fromDegrees(45,22,16000000)}); declutter(); }
    else if(pins.length){
      if(D.prevBounds&&D.prevBounds.length){var pz=D.prevBounds.map(function(p){return {lat:p[0],lon:p[1]};});v.camera.setView({destination:rect(pz,6)});}
      else v.camera.setView({destination:Cesium.Cartesian3.fromDegrees(pins[0].lon,pins[0].lat,8000000)});
      setTimeout(function(){v.camera.flyTo({destination:rect(pins,pins.length>1?4:2),duration:2.2,complete:function(){declutter();FLOWN=true;wake('slide');}});},400);
    }
    if(D.badge){var d=document.createElement('div');d.className='gia-badge';d.style.cssText='position:absolute;top:10px;left:10px;z-index:5';d.innerHTML=D.badge;box.style.position='relative';box.appendChild(d);}
    var pop=document.createElement('div');pop.className='gia-badge';pop.style.cssText='position:absolute;right:10px;bottom:40px;z-index:6;display:none;max-width:300px';box.appendChild(pop);
    new Cesium.ScreenSpaceEventHandler(v.scene.canvas).setInputAction(function(m){var p=v.scene.pick(m.position);
      if(Cesium.defined(p)&&p.id&&p.id.description){pop.innerHTML='<b>'+p.id.name+'</b>'+p.id.description.getValue()+'<div style="text-align:right;cursor:pointer" onclick="this.parentNode.style.display=\'none\'">close</div>';pop.style.display='block';}else pop.style.display='none';wake('selection');},Cesium.ScreenSpaceEventType.LEFT_CLICK);
    var fb=document.getElementById('gia-fallback'); if(fb) fb.style.display='none';
    window.GIA_VIEWER=v;
    // Ready signal for headless shots (r3): once the slide flight is done and every tile is in, request one frame and set
    // data-gia-ready="globe" on the container from that frame's postRender, so a screenshot always has a rendered frame.
    (function(){var set=false,T0=performance.now(),capped=false;
      setTimeout(function(){if(set)return;capped=true;box.dataset.giaGlobeTilesLoaded='timeout '+Math.round(performance.now()-T0);
        if(GIA_SAMPLE){GIA_SAMPLE=null;GIA_OUT(Math.round(v.resolutionScale*DPR*100)/100,'timeout','',0);}},CAP_MS);
      function chk(){if(set||!FLOWN||!v.scene.globe.tilesLoaded)return;set=true;
      if(!capped)box.dataset.giaGlobeTilesLoaded='true '+Math.round(performance.now()-T0);
      var fin=function(){v.scene.postRender.removeEventListener(fin);box.dataset.giaReady='globe';};
      var once=function(){v.scene.postRender.removeEventListener(once);
        if(!GIA_SAMPLE){box.dataset.giaReady='globe';return;}
        setTimeout(function(){if(GIA_SAMPLE()){v.scene.postRender.addEventListener(fin);wake('fallback');}else box.dataset.giaReady='globe';},300);};
      v.scene.postRender.addEventListener(once);wake('ready');}
      v.scene.globe.tileLoadProgressEvent.addEventListener(function(n){if(n===0)setTimeout(chk,0);});
      var iv=setInterval(function(){chk();if(set)clearInterval(iv);},250);})();
    wake('data',2000);
  }catch(e){ box.style.display='none'; var f2=document.getElementById('gia-fallback'); if(f2) f2.style.display=''; if(window.console) console.warn('GIA cesium fallback',e); }
})();
