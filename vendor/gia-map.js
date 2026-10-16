/* GIA Leaflet layer. Reads <script type="application/json" id="gia-map-data">.
   Hot zones are rings. Event places are a different shape per marker.
   If Leaflet or tiles fail, the static SVG fallback (#gia-fallback) stays visible. */
(function(){
  var el=document.getElementById('gia-map-data'), box=document.getElementById('gia-leaflet');
  if(!el||!box||typeof L==='undefined') return;
  var D; try{D=JSON.parse(el.textContent);}catch(e){return;}
  try{
    box.style.display='block';
    var fb=document.getElementById('gia-fallback'); if(fb) fb.style.display='none';
    var map=L.map(box,{zoomControl:true,worldCopyJump:true,attributionControl:true});
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',{
      maxZoom:16,attribution:'Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors'}).addTo(map);
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',{maxZoom:16,opacity:.7}).addTo(map);
    function curve(a,b,bend){
      var la=a[0],lo=a[1],lb=b[0],lob=b[1],mx=(la+lb)/2,my=(lo+lob)/2,dx=lb-la,dy=lob-lo;
      var cx=mx-dy*bend,cy=my+dx*bend,pts=[];
      for(var t=0;t<=1.0001;t+=0.05){var u=1-t;pts.push([u*u*la+2*u*t*cx+t*t*lb,u*u*lo+2*u*t*cy+t*t*lob]);}
      return pts;
    }
    var COLORS={military:'#ff5a4f',strike:'#ff5a4f',diplomacy:'#7eb6ff',energy:'#ffe08a',political:'#c9a6ff'};
    function pinHtml(marker, active){
      var c=COLORS[marker]||COLORS.political, o=active?1:.45, s=active?18:12;
      if(marker==='military') return '<div style="width:'+s+'px;height:'+s+'px;background:'+c+';opacity:'+o+';border:2px solid #fff"></div>';
      if(marker==='strike') return '<svg width="'+s+'" height="'+s+'" viewBox="0 0 16 16"><path d="M2 2 L14 14 M14 2 L2 14" stroke="'+c+'" stroke-width="3" opacity="'+o+'" fill="none"/></svg>';
      if(marker==='diplomacy') return '<svg width="'+s+'" height="'+s+'" viewBox="0 0 16 16"><path d="M8 1 L15 8 L8 15 L1 8 Z" fill="'+c+'" opacity="'+o+'" stroke="#fff" stroke-width="1.2"/></svg>';
      if(marker==='energy') return '<svg width="'+s+'" height="'+s+'" viewBox="0 0 16 16"><path d="M8 1 L15 14 L1 14 Z" fill="'+c+'" opacity="'+o+'" stroke="#fff" stroke-width="1.2"/></svg>';
      return '<svg width="'+s+'" height="'+s+'" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="'+c+'" stroke-width="2" opacity="'+o+'"/></svg>';
    }
    function addPin(p, bounds){
      var active=p.role==='active'||p.role==='today';
      var size=active?18:12;
      var icon=L.divIcon({className:'gia-pin',html:pinHtml(p.marker,active),iconSize:[size,size],iconAnchor:[size/2,size/2]});
      var m=L.marker([p.lat,p.lon],{icon:icon,zIndexOffset:active?400:100}).addTo(map);
      m.bindPopup('<b>'+p.name+'</b><br>'+(p.marker||'')+(p.href?'<br><a href="'+p.href+'">Open →</a>':''));
      m.bindTooltip(p.name,{permanent:p.role==='active',direction:'right',offset:[10,0],className:active?'gia-tip':'gia-tip dim'});
      bounds.push([p.lat,p.lon]);
    }
    var Z={};(D.zones||[]).forEach(function(z){Z[z.id]=z;});
    var mode=D.mode, bounds=[];
    (D.links||[]).forEach(function(l,i){
      var a=Z[l.from],b=Z[l.to]; if(!a||!b) return;
      var line=L.polyline(curve([a.lat,a.lon],[b.lat,b.lon],i%2?.25:-.25),{color:'#ff6b5f',weight:2,opacity:.75,dashArray:'6 4'}).addTo(map);
      line.bindTooltip((i+1)+'. '+l.label,{sticky:true}); if(l.href) line.on('click',function(){location.href=l.href;});
    });
    var tr=D.trailPlaces||[];
    for(var i=0;i<tr.length-1;i++){
      var a=tr[i],b=tr[i+1]; if(!a||!b||(a.lat===b.lat&&a.lon===b.lon)) continue;
      var last=i===tr.length-2;
      L.polyline(curve([a.lat,a.lon],[b.lat,b.lon],.22),{color:last?'#ffe08a':'#ff6b5f',weight:last?4:2,opacity:last?.95:.45,dashArray:last?null:'6 4'}).addTo(map);
    }
    if(mode==='dashboard'){
      (D.zones||[]).forEach(function(z){
        var m=L.circleMarker([z.lat,z.lon],{radius:z.r,color:z.color,weight:2,fillColor:z.color,fillOpacity:.15}).addTo(map);
        m.bindPopup('<b>'+z.name+'</b><br>'+z.sev+(z.note?' · '+z.note:'')+'<br><a href="'+z.href+'">Hot zone →</a>');
        m.bindTooltip(z.name,{direction:'right',className:'gia-tip dim'});
        bounds.push([z.lat,z.lon]);
      });
    }
    (D.places||[]).forEach(function(p){addPin(p,bounds);});
    if(!bounds.length){ map.setView([30,30],3); }
    else {
      var b=L.latLngBounds(bounds).pad(mode==='path'?0.45:0.15);
      if(mode==='path'&&D.prevBounds&&D.prevBounds.length){
        map.fitBounds(L.latLngBounds(D.prevBounds).pad(0.45),{animate:false});
        setTimeout(function(){ if(bounds.length===1) map.flyTo(bounds[0],6,{duration:1.4}); else map.flyToBounds(b,{duration:1.4,maxZoom:8}); },250);
      } else if(mode==='path'&&bounds.length===1) map.setView(bounds[0],6);
      else map.fitBounds(b,{maxZoom:mode==='path'?8:4});
    }
    if(D.badge){var c=L.control({position:'topleft'});c.onAdd=function(){var d=L.DomUtil.create('div','gia-badge');d.innerHTML=D.badge;return d;};c.addTo(map);}
    window.GIA_MAP=map;
  }catch(e){ box.style.display='none'; var fb2=document.getElementById('gia-fallback'); if(fb2) fb2.style.display=''; if(window.console) console.warn('GIA map fallback',e); }
})();
