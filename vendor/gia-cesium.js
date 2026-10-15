/* GIA CesiumJS globe (pinned CDN Cesium 1.122.0). Same embedded #gia-map-data as the Leaflet build.
   No Cesium Ion token needed: Ion is disabled, imagery = Esri dark gray (keyless), ellipsoid terrain. */
(function(){
  var el=document.getElementById('gia-map-data'), box=document.getElementById('gia-cesium');
  if(!el||!box||typeof Cesium==='undefined') return;
  if(location.protocol==='file:'){ // Cesium web workers are blocked on file:// -> globe stays blank. Keep static map + explain.
    var n=document.createElement('div');n.className='gia-badge';n.style.cssText='margin:6px 0;border-color:#ffe08a';
    n.innerHTML='🌐 The 3D globe needs a local web server (browsers block Cesium workers on file://). Double-click <b>open-3d.command</b> (Mac) / <b>open-3d.bat</b> (Windows) in the dashboard folder, or run <code>python3 -m http.server 8000</code> there and open http://localhost:8000/dashboard-cesium.html. Showing the static map meanwhile.';
    box.parentNode.insertBefore(n,box); return; }
  var D; try{D=JSON.parse(el.textContent);}catch(e){return;}
  try{
    Cesium.Ion.defaultAccessToken='';
    box.style.display='block';
    var esri=new Cesium.UrlTemplateImageryProvider({url:'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
      maximumLevel:16,credit:'Tiles © Esri, HERE, Garmin, © OpenStreetMap contributors'});
    var v=new Cesium.Viewer(box,{baseLayer:new Cesium.ImageryLayer(esri),terrainProvider:new Cesium.EllipsoidTerrainProvider(),
      geocoder:false,homeButton:false,sceneModePicker:true,baseLayerPicker:false,navigationHelpButton:false,animation:false,timeline:false,
      fullscreenButton:false,infoBox:false,selectionIndicator:false});
    var ref=new Cesium.UrlTemplateImageryProvider({url:'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',maximumLevel:16});
    v.imageryLayers.addImageryProvider(ref).alpha=.7;
    v.scene.globe.baseColor=Cesium.Color.fromCssColorString('#071018');
    v.scene.backgroundColor=Cesium.Color.fromCssColorString('#05080c');
    var Z={};D.zones.forEach(function(z){Z[z.id]=z;});
    var mode=D.mode, act=D.active||[], past=D.past||[], focus=[];
    function arc(a,b,color,width,dash,height){
      var pos=[],n=40,h=height||Math.min(1500000,Cesium.Cartesian3.distance(Cesium.Cartesian3.fromDegrees(a.lon,a.lat),Cesium.Cartesian3.fromDegrees(b.lon,b.lat))*0.25);
      for(var i=0;i<=n;i++){var t=i/n;pos.push(Cesium.Cartesian3.fromDegrees(a.lon+(b.lon-a.lon)*t,a.lat+(b.lat-a.lat)*t,Math.sin(Math.PI*t)*h));}
      return v.entities.add({polyline:{positions:pos,width:width,material:dash?new Cesium.PolylineDashMaterialProperty({color:color,dashLength:16}):new Cesium.PolylineGlowMaterialProperty({color:color,glowPower:.25})}});
    }
    (D.links||[]).forEach(function(l,i){var a=Z[l.from],b=Z[l.to];if(!a||!b)return;
      var e=arc(a,b,Cesium.Color.fromCssColorString('#ff6b5f').withAlpha(.8),2,true);
      e.name=(i+1)+'. '+l.label; e.description='<p>'+l.label+'</p><p><a href="'+l.href+'" target="_top">Link history →</a></p>';});
    var tr=D.trail||[];
    for(var i=0;i<tr.length-1;i++){var a=Z[tr[i]],b=Z[tr[i+1]];if(!a||!b||a===b)continue;var last=i===tr.length-2;
      arc(a,b,Cesium.Color.fromCssColorString(last?'#ffe08a':'#ff6b5f').withAlpha(last?1:.5),last?6:3,!last);}
    var t0=Date.now();
    D.zones.forEach(function(z){
      var isA=mode==='dashboard'||act.indexOf(z.id)>=0, isP=past.indexOf(z.id)>=0, col=Cesium.Color.fromCssColorString(z.color);
      var size=mode==='dashboard'?z.r*1.6:(isA?22:isP?12:5);
      var pulse=(isA&&mode==='path')?new Cesium.CallbackProperty(function(){return size+8*Math.abs(Math.sin((Date.now()-t0)/350));},false):size;
      var e=v.entities.add({name:z.name,position:Cesium.Cartesian3.fromDegrees(z.lon,z.lat),
        point:{pixelSize:pulse,color:(isA||mode==='dashboard')?col:(isP?col.withAlpha(.45):Cesium.Color.GRAY.withAlpha(.3)),
          outlineColor:isA&&mode==='path'?Cesium.Color.WHITE:Cesium.Color.BLACK,outlineWidth:isA&&mode==='path'?3:1,disableDepthTestDistance:Number.POSITIVE_INFINITY},
        label:(isA||isP||mode==='dashboard')?{text:z.name,font:(isA&&mode==='path'?'bold 18px':'bold 13px')+' Arial',fillColor:isP&&!isA?Cesium.Color.LIGHTGRAY.withAlpha(.7):Cesium.Color.WHITE,
          outlineColor:Cesium.Color.BLACK,outlineWidth:3,style:Cesium.LabelStyle.FILL_AND_OUTLINE,pixelOffset:new Cesium.Cartesian2(16,-14),
          horizontalOrigin:Cesium.HorizontalOrigin.LEFT,disableDepthTestDistance:Number.POSITIVE_INFINITY}:undefined,
        description:'<p><b>'+z.sev+'</b> · '+(z.note||'')+'</p><p><a href="'+z.href+'" target="_top">History →</a></p>'});
      if(mode==='dashboard'||isA) focus.push(z); else if(isP) focus.push(z);
    });
    function rect(zs,pad){var lo=zs.map(function(z){return z.lon;}),la=zs.map(function(z){return z.lat;});
      return Cesium.Rectangle.fromDegrees(Math.min.apply(0,lo)-pad,Math.max(-85,Math.min.apply(0,la)-pad),Math.max.apply(0,lo)+pad,Math.min(85,Math.max.apply(0,la)+pad));}
    if(mode==='dashboard'){ v.camera.setView({destination:Cesium.Cartesian3.fromDegrees(45,22,16000000)}); }
    else {
      if(D.prevBounds&&D.prevBounds.length){var pz=D.prevBounds.map(function(p){return {lat:p[0],lon:p[1]};});v.camera.setView({destination:rect(pz,14)});}
      else v.camera.setView({destination:Cesium.Cartesian3.fromDegrees(focus[0]?focus[0].lon:40,focus[0]?focus[0].lat:25,14000000)});
      var target=act.map(function(id){return Z[id];}).filter(Boolean); if(!target.length) target=focus;
      setTimeout(function(){v.camera.flyTo({destination:rect(target.length?target:focus,target.length>1?8:12),duration:2.2});},400);
    }
    if(D.badge){var d=document.createElement('div');d.className='gia-badge';d.style.cssText='position:absolute;top:10px;left:10px;z-index:5';d.innerHTML=D.badge;box.style.position='relative';box.appendChild(d);}
    // custom info popup (Cesium's iframe InfoBox fails on file://)
    var pop=document.createElement('div');pop.className='gia-badge';pop.style.cssText='position:absolute;right:10px;bottom:40px;z-index:6;display:none;max-width:300px';box.appendChild(pop);
    new Cesium.ScreenSpaceEventHandler(v.scene.canvas).setInputAction(function(m){var p=v.scene.pick(m.position);
      if(Cesium.defined(p)&&p.id&&p.id.description){pop.innerHTML='<b>'+p.id.name+'</b>'+p.id.description.getValue()+'<div style="text-align:right;cursor:pointer" onclick="this.parentNode.style.display=\'none\'">✕ close</div>';pop.style.display='block';}else pop.style.display='none';},Cesium.ScreenSpaceEventType.LEFT_CLICK);
    var fb=document.getElementById('gia-fallback'); if(fb) fb.style.display='none';
    window.GIA_VIEWER=v;
  }catch(e){ box.style.display='none'; var f2=document.getElementById('gia-fallback'); if(f2) f2.style.display=''; if(window.console) console.warn('GIA cesium fallback',e); }
})();
