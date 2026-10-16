/* GIA CesiumJS globe (pinned CDN Cesium 1.122.0). Same embedded #gia-map-data as the Leaflet build.
   No Cesium Ion token needed: Ion is disabled, imagery = Esri dark gray (keyless), ellipsoid terrain.
   Hot zones are rings. Event places use a glyph per marker. */
(function(){
  var el=document.getElementById('gia-map-data'), box=document.getElementById('gia-cesium');
  if(!el||!box||typeof Cesium==='undefined') return;
  if(location.protocol==='file:'){
    var n=document.createElement('div');n.className='gia-badge';n.style.cssText='margin:6px 0;border-color:#ffe08a';
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
      fullscreenButton:false,infoBox:false,selectionIndicator:false});
    var ref=new Cesium.UrlTemplateImageryProvider({url:'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',maximumLevel:16});
    v.imageryLayers.addImageryProvider(ref).alpha=.7;
    v.scene.globe.baseColor=Cesium.Color.fromCssColorString('#071018');
    v.scene.backgroundColor=Cesium.Color.fromCssColorString('#05080c');
    var Z={};(D.zones||[]).forEach(function(z){Z[z.id]=z;});
    var COLORS={military:'#ff5a4f',strike:'#ff5a4f',diplomacy:'#7eb6ff',energy:'#ffe08a',political:'#c9a6ff'};
    var GLYPH={military:'■',strike:'✕',diplomacy:'◆',energy:'▲',political:'○'};
    function arc(a,b,color,width,dash,height){
      var pos=[],n=40,h=height||Math.min(1500000,Cesium.Cartesian3.distance(Cesium.Cartesian3.fromDegrees(a.lon,a.lat),Cesium.Cartesian3.fromDegrees(b.lon,b.lat))*0.25);
      for(var i=0;i<=n;i++){var t=i/n;pos.push(Cesium.Cartesian3.fromDegrees(a.lon+(b.lon-a.lon)*t,a.lat+(b.lat-a.lat)*t,Math.sin(Math.PI*t)*h));}
      return v.entities.add({polyline:{positions:pos,width:width,material:dash?new Cesium.PolylineDashMaterialProperty({color:color,dashLength:16}):new Cesium.PolylineGlowMaterialProperty({color:color,glowPower:.25})}});
    }
    (D.links||[]).forEach(function(l,i){var a=Z[l.from],b=Z[l.to];if(!a||!b)return;
      var e=arc(a,b,Cesium.Color.fromCssColorString('#ff6b5f').withAlpha(.8),2,true);
      e.name=(i+1)+'. '+l.label; e.description='<p>'+l.label+'</p><p><a href="'+l.href+'" target="_top">Link history →</a></p>';});
    var tr=D.trailPlaces||[];
    for(var i=0;i<tr.length-1;i++){var a=tr[i],b=tr[i+1];if(!a||!b||(a.lat===b.lat&&a.lon===b.lon))continue;var last=i===tr.length-2;
      arc(a,b,Cesium.Color.fromCssColorString(last?'#ffe08a':'#ff6b5f').withAlpha(last?1:.5),last?6:3,!last);}
    var mode=D.mode, focus=[];
    if(mode==='dashboard'){
      (D.zones||[]).forEach(function(z){
        var col=Cesium.Color.fromCssColorString(z.color);
        var e=v.entities.add({name:z.name,position:Cesium.Cartesian3.fromDegrees(z.lon,z.lat),
          point:{pixelSize:z.r*2,color:Cesium.Color.TRANSPARENT,outlineColor:col,outlineWidth:3,disableDepthTestDistance:Number.POSITIVE_INFINITY},
          label:{text:z.name,font:'bold 13px Arial',fillColor:Cesium.Color.WHITE,outlineColor:Cesium.Color.BLACK,outlineWidth:3,
            style:Cesium.LabelStyle.FILL_AND_OUTLINE,pixelOffset:new Cesium.Cartesian2(14,-10),disableDepthTestDistance:Number.POSITIVE_INFINITY},
          description:'<p><b>'+z.sev+'</b> · '+(z.note||'')+'</p><p><a href="'+z.href+'" target="_top">Hot zone →</a></p>'});
        focus.push(z);
      });
    }
    (D.places||[]).forEach(function(p){
      var active=p.role==='active'||p.role==='today';
      var col=Cesium.Color.fromCssColorString(COLORS[p.marker]||COLORS.political).withAlpha(active?1:.5);
      var e=v.entities.add({name:p.name,position:Cesium.Cartesian3.fromDegrees(p.lon,p.lat),
        label:{text:(GLYPH[p.marker]||'○')+' '+p.name,font:(active?'bold 18px':'14px')+' Arial',fillColor:col,
          outlineColor:Cesium.Color.BLACK,outlineWidth:3,style:Cesium.LabelStyle.FILL_AND_OUTLINE,
          disableDepthTestDistance:Number.POSITIVE_INFINITY},
        description:'<p>'+(p.marker||'')+'</p>'+(p.href?'<p><a href="'+p.href+'" target="_top">Open →</a></p>':'')});
      focus.push(p);
    });
    function rect(zs,pad){var lo=zs.map(function(z){return z.lon;}),la=zs.map(function(z){return z.lat;});
      return Cesium.Rectangle.fromDegrees(Math.min.apply(0,lo)-pad,Math.max(-85,Math.min.apply(0,la)-pad),Math.max.apply(0,lo)+pad,Math.min(85,Math.max.apply(0,la)+pad));}
    var pins=(D.places||[]).filter(function(p){return p.role==='active';});
    if(!pins.length) pins=(D.places||[]);
    if(mode==='dashboard'){ v.camera.setView({destination:Cesium.Cartesian3.fromDegrees(45,22,16000000)}); }
    else if(pins.length){
      if(D.prevBounds&&D.prevBounds.length){var pz=D.prevBounds.map(function(p){return {lat:p[0],lon:p[1]};});v.camera.setView({destination:rect(pz,6)});}
      else v.camera.setView({destination:Cesium.Cartesian3.fromDegrees(pins[0].lon,pins[0].lat,8000000)});
      setTimeout(function(){v.camera.flyTo({destination:rect(pins,pins.length>1?4:2),duration:2.2});},400);
    }
    if(D.badge){var d=document.createElement('div');d.className='gia-badge';d.style.cssText='position:absolute;top:10px;left:10px;z-index:5';d.innerHTML=D.badge;box.style.position='relative';box.appendChild(d);}
    var pop=document.createElement('div');pop.className='gia-badge';pop.style.cssText='position:absolute;right:10px;bottom:40px;z-index:6;display:none;max-width:300px';box.appendChild(pop);
    new Cesium.ScreenSpaceEventHandler(v.scene.canvas).setInputAction(function(m){var p=v.scene.pick(m.position);
      if(Cesium.defined(p)&&p.id&&p.id.description){pop.innerHTML='<b>'+p.id.name+'</b>'+p.id.description.getValue()+'<div style="text-align:right;cursor:pointer" onclick="this.parentNode.style.display=\'none\'">close</div>';pop.style.display='block';}else pop.style.display='none';},Cesium.ScreenSpaceEventType.LEFT_CLICK);
    var fb=document.getElementById('gia-fallback'); if(fb) fb.style.display='none';
    window.GIA_VIEWER=v;
  }catch(e){ box.style.display='none'; var f2=document.getElementById('gia-fallback'); if(f2) f2.style.display=''; if(window.console) console.warn('GIA cesium fallback',e); }
})();
