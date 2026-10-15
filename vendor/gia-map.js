/* GIA Leaflet layer. Reads <script type="application/json" id="gia-map-data">. Progressive enhancement:
   if Leaflet or tiles fail, the static SVG fallback (#gia-fallback) stays visible. */
(function(){
  var el=document.getElementById('gia-map-data'), box=document.getElementById('gia-leaflet');
  if(!el||!box||typeof L==='undefined') return;
  var D; try{D=JSON.parse(el.textContent);}catch(e){return;}
  try{
    box.style.display='block';
    var fb=document.getElementById('gia-fallback'); if(fb) fb.style.display='none';
    var map=L.map(box,{zoomControl:true,worldCopyJump:true,attributionControl:true});
    // Esri Dark Gray Canvas: no API key, works from file:// (Carto dark tiles now demand a key without a Referer)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',{
      maxZoom:16,attribution:'Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors'}).addTo(map);
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',{maxZoom:16,opacity:.7}).addTo(map);
    function curve(a,b,bend){ // quadratic bezier as polyline in lat/lng space
      var la=a[0],lo=a[1],lb=b[0],lob=b[1],mx=(la+lb)/2,my=(lo+lob)/2,dx=lb-la,dy=lob-lo;
      var cx=mx-dy*bend,cy=my+dx*bend,pts=[];
      for(var t=0;t<=1.0001;t+=0.05){var u=1-t;pts.push([u*u*la+2*u*t*cx+t*t*lb,u*u*lo+2*u*t*cy+t*t*lob]);}
      return pts;
    }
    var Z={};D.zones.forEach(function(z){Z[z.id]=z;});
    var mode=D.mode, act=D.active||[], past=D.past||[], bounds=[];
    // causal links
    (D.links||[]).forEach(function(l,i){
      var a=Z[l.from],b=Z[l.to]; if(!a||!b) return;
      var line=L.polyline(curve([a.lat,a.lon],[b.lat,b.lon],i%2?.25:-.25),{color:'#ff6b5f',weight:2,opacity:.75,dashArray:'6 4'}).addTo(map);
      line.bindTooltip((i+1)+'. '+l.label,{sticky:true}); if(l.href) line.on('click',function(){location.href=l.href;});
    });
    // gold trail
    var tr=D.trail||[];
    for(var i=0;i<tr.length-1;i++){var a=Z[tr[i]],b=Z[tr[i+1]]; if(!a||!b||a===b) continue;
      var last=i===tr.length-2;
      L.polyline(curve([a.lat,a.lon],[b.lat,b.lon],.22),{color:last?'#ffe08a':'#ff6b5f',weight:last?4:2,opacity:last?.95:.45,dashArray:last?null:'6 4'}).addTo(map);}
    D.zones.forEach(function(z){
      var isA=mode==='dashboard'||act.indexOf(z.id)>=0, isP=past.indexOf(z.id)>=0;
      if(mode!=='dashboard'&&!isA&&!isP){L.circleMarker([z.lat,z.lon],{radius:3,color:'#334',fillColor:'#223',fillOpacity:.4,weight:1}).addTo(map);return;}
      var r=mode==='dashboard'?z.r:(isA?16:8);
      var m=L.circleMarker([z.lat,z.lon],{radius:r,color:isA?'#fff':z.color,weight:isA&&mode!=='dashboard'?3:1.5,
        fillColor:z.color,fillOpacity:isA?.85:.3,dashArray:isP?'4 3':null,className:(isA&&mode==='path')?'gia-pulse':''}).addTo(map);
      m.bindPopup('<b>'+z.name+'</b><br>'+z.sev+(z.note?' · '+z.note:'')+'<br><a href="'+z.href+'">History →</a>');
      m.bindTooltip(z.name,{permanent:isA,direction:'right',offset:[r+4,0],className:isA?'gia-tip':'gia-tip dim'});
      if(isA||mode==='dashboard') bounds.push([z.lat,z.lon]);
      if(isP) bounds.push([z.lat,z.lon]);
    });
    if(!bounds.length) bounds=D.zones.map(function(z){return [z.lat,z.lon];});
    var b=L.latLngBounds(bounds).pad(mode==='path'?0.6:0.15);
    if(mode==='path'&&D.prevBounds){ // start at previous slide's view, then fly → visible motion between static pages
      map.fitBounds(L.latLngBounds(D.prevBounds).pad(0.6),{animate:false});
      setTimeout(function(){ if(bounds.length===1) map.flyTo(bounds[0],5,{duration:1.4}); else map.flyToBounds(b,{duration:1.4,maxZoom:6}); },250);
    } else { if(mode==='path'&&bounds.length===1) map.setView(bounds[0],5); else map.fitBounds(b,{maxZoom:mode==='path'?6:4}); }
    if(D.badge){var c=L.control({position:'topleft'});c.onAdd=function(){var d=L.DomUtil.create('div','gia-badge');d.innerHTML=D.badge;return d;};c.addTo(map);}
    window.GIA_MAP=map;
  }catch(e){ box.style.display='none'; var fb2=document.getElementById('gia-fallback'); if(fb2) fb2.style.display=''; if(window.console) console.warn('GIA map fallback',e); }
})();
