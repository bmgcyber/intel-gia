/* GIA Leaflet layer. Reads <script type="application/json" id="gia-map-data">.
   Hot zones are rings. Event places are a different shape per marker.
   If Leaflet or tiles fail, the static SVG fallback (#gia-fallback) stays visible. */
(function(){
  var CRITG='<svg class="critg" viewBox="0 0 32 32" aria-hidden="true" focusable="false" style="width:12px;height:12px;fill:var(--gia-sev-glyph);vertical-align:-1px;margin-right:3px"><path d="M16,2C8.3,2,2,8.3,2,16s6.3,14,14,14s14-6.3,14-14C30,8.3,23.7,2,16,2z M14.9,8h2.2v11h-2.2V8z M16,25c-0.8,0-1.5-0.7-1.5-1.5S15.2,22,16,22c0.8,0,1.5,0.7,1.5,1.5S16.8,25,16,25z"/></svg>';  // Carbon warning--filled before 'critical' (spec Follow-ups A)
  var el=document.getElementById('gia-map-data'), host=document.getElementById('gia-leaflet'), box=host;
  if(!el||!host||typeof L==='undefined') return;
  var inner=host.dataset.mount==='inner';  // Map page: host always visible, Leaflet mounts inside it (contract §1)
  var D; try{D=JSON.parse(el.textContent);}catch(e){return;}
  try{
    if(inner){ box=document.createElement('div'); box.className='gia-lmap'; box.style.height='560px'; host.insertBefore(box,host.firstChild); }
    else box.style.display='block';
    var fb=document.getElementById('gia-fallback'); if(fb) fb.style.display='none';
    var map=L.map(box,{zoomControl:true,worldCopyJump:true,attributionControl:true});
    var base=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',{
      maxZoom:16,attribution:'Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors'}).addTo(map);
    base.once('load',function(){document.documentElement.dataset.giaReady='map'; if(inner) host.dataset.state='ready';});  // readiness signal for shots.py
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',{maxZoom:16,opacity:.7}).addTo(map);
    function curve(a,b,bend){
      var la=a[0],lo=a[1],lb=b[0],lob=b[1],mx=(la+lb)/2,my=(lo+lob)/2,dx=lb-la,dy=lob-lo;
      var cx=mx-dy*bend,cy=my+dx*bend,pts=[];
      for(var t=0;t<=1.0001;t+=0.05){var u=1-t;pts.push([u*u*la+2*u*t*cx+t*t*lb,u*u*lo+2*u*t*cy+t*t*lob]);}
      return pts;
    }
    // Marker tokens (gia_build/markers.py -> :root --gia-marker-<type>[-shape|-glyph]); no colour is hard-coded here.
    var _cs=getComputedStyle(document.documentElement);
    function mk(t,f){var v=_cs.getPropertyValue('--gia-marker-'+t+(f?'-'+f:'')).trim();return f==='glyph'?v.replace(/^"|"$/g,''):v;}
    function mkKind(m){return mk(m)?m:'political';}
    function mkCol(m){return mk(mkKind(m))||'#8d8d8d';}  // neutral grey only if the page has no token CSS
    function mkShape(m){return mk(mkKind(m),'shape')||'ring';}
    function mkGlyph(m){return mk(mkKind(m),'glyph')||'○';}
    // Per-type shape hook: geometry from markers.py tokens (--gia-shape-<shape>-d/-paint/-w), the same data the Cesium
    // sprites use, so the Designer's shapes are a data-only edit. Fill shapes keep the white 2D outline.
    function tok(n){return _cs.getPropertyValue(n).trim().replace(/^"|"$/g,'');}
    function pinHtml(marker, active, prec){
      // ONE divIcon per pin = precision halo + type glyph, both in the marker token (spec "Palette rulings 01:50" §2).
      // Halo radius --gia-precision-<feature|city|sector> (9 / 13 / 19 px, sector dashed), past x --gia-precision-past-scale.
      // Past pins: opacity --gia-sprite-past-alpha (1); smaller glyph only. Casing = --gia-sprite-outline under the shape.
      var o=active?1:(+tok('--gia-sprite-past-alpha')||1), g=active?18:12, c=mkCol(marker), sh=mkShape(marker), ol=tok('--gia-sprite-outline')||'#0b0f14',
          d=tok('--gia-shape-'+sh+'-d')||tok('--gia-shape-ring-d'), paint=tok('--gia-shape-'+sh+'-paint')||'stroke', w=+(tok('--gia-shape-'+sh+'-w')||'2');
      var hr=prec?+(tok('--gia-precision-'+prec)||0)*(active?1:(+tok('--gia-precision-past-scale')||.75)):0, hw=+(tok('--gia-precision-stroke')||1.5),
          B=Math.ceil(Math.max(g,2*(hr+hw))+2), k=g/16, t='translate('+(B/2-g/2)+' '+(B/2-g/2)+') scale('+k+')';
      var halo=hr>0?'<circle class="ph" cx="'+B/2+'" cy="'+B/2+'" r="'+hr+'" fill="none" stroke="'+c+'" stroke-width="'+hw+'"'+
          (prec==='sector'?' stroke-dasharray="'+(tok('--gia-precision-sector-dash')||'4 2.5')+'"':'')+'/>':'';
      var body=paint==='fill'?'<path transform="'+t+'" d="'+d+'" fill="'+c+'" stroke="'+ol+'" stroke-width="'+(2*w)+'" stroke-linejoin="round" paint-order="stroke"/>'
              :'<path transform="'+t+'" d="'+d+'" fill="none" stroke="'+ol+'" stroke-width="'+(w+2.4)+'" stroke-linecap="round"/><path transform="'+t+'" d="'+d+'" fill="none" stroke="'+c+'" stroke-width="'+w+'" stroke-linecap="round"/>';
      return {B:B,html:'<svg width="'+B+'" height="'+B+'" viewBox="0 0 '+B+' '+B+'" data-shape="'+sh+'"'+(prec?' data-precision="'+prec+'"':'')+' opacity="'+o+'">'+halo+body+'</svg>'};
    }
    function addPin(p, bounds){
      var active=p.role==='active'||p.role==='today', pi=pinHtml(p.marker,active,p.precision);
      var icon=L.divIcon({className:'gia-pin',html:pi.html,iconSize:[pi.B,pi.B],iconAnchor:[pi.B/2,pi.B/2]});
      var m=L.marker([p.lat,p.lon],{icon:icon,zIndexOffset:active?400:100}).addTo(map);
      m.bindPopup('<b>'+p.name+'</b><br>'+(p.marker||'')+(p.href?'<br><a href="'+p.href+'">Open →</a>':''));
      m.bindTooltip(p.name,{permanent:p.role==='active',direction:'right',offset:[10,0],className:active?'gia-tip':'gia-tip dim'});
      bounds.push([p.lat,p.lon]);
    }
    var Z={};(D.zones||[]).forEach(function(z){Z[z.id]=z;});
    var mode=D.mode, bounds=[];
    (D.links||[]).forEach(function(l,i){
      var a=Z[l.from],b=Z[l.to]; if(!a||!b) return;
      var line=L.polyline(curve([a.lat,a.lon],[b.lat,b.lon],i%2?.25:-.25),{color:tok('--gia-path')||'#c3a6ff',weight:2,opacity:.8,dashArray:'6 4'}).addTo(map);
      line.bindTooltip((i+1)+'. '+l.label,{sticky:true}); if(l.href) line.on('click',function(){location.href=l.href;});
    });
    // Severity tokens (gia_build/ui_tokens.py -> :root --gia-sev-<level>[-outline]); no severity hex in JS.
    var _ss=getComputedStyle(document.documentElement);
    function sevTok(l,f){return _ss.getPropertyValue('--gia-sev-'+l+(f?'-'+f:'')).trim();}
    function sevCol(l){return sevTok(l)||sevTok('watch')||'#8d8d8d';}
    function sevLine(l){var o=sevTok(l,'outline');return o&&o!=='none'?o:null;}  // dark keyline hook, 'none' = off
    var SEV_OPX=+(_ss.getPropertyValue('--gia-sev-outline-px').trim())||1;
    var tr=D.trailPlaces||[];
    for(var i=0;i<tr.length-1;i++){
      var a=tr[i],b=tr[i+1]; if(!a||!b||(a.lat===b.lat&&a.lon===b.lon)) continue;
      var last=i===tr.length-2;
      L.polyline(curve([a.lat,a.lon],[b.lat,b.lon],.22),{color:'#c3a6ff',weight:2.5,opacity:last?1:.7,dashArray:last?null:'6 5'}).addTo(map);
    }
    if(mode==='dashboard'){
      (D.zones||[]).forEach(function(z){
        var zc=sevCol(z.sev), zl=sevLine(z.sev);
        var m=z.area
          ? (zl&&L.geoJSON(z.area,{interactive:false,style:{color:zl,weight:1.5+2*SEV_OPX,fill:false}}).addTo(map),  // keyline under
             L.geoJSON(z.area,{style:{color:zc,weight:1.5,dashArray:'4 3',fillColor:zc,fillOpacity:.14}}).addTo(map))  // sourced theater outline, not a pin
          : (zl&&L.circleMarker([z.lat,z.lon],{interactive:false,radius:z.r,color:zl,weight:2+2*SEV_OPX,fill:false}).addTo(map),
             L.circleMarker([z.lat,z.lon],{radius:z.r,color:zc,weight:2,fillColor:zc,fillOpacity:.15}).addTo(map));
        if(z.area_source) map.attributionControl.addAttribution('Sea areas: '+z.area_source.split(' (')[0]);
        m.bindPopup('<b>'+z.name+'</b><br>'+(z.sev==='critical'?CRITG:'')+z.sev+(z.note?' · '+z.note:'')+'<br><a href="'+z.href+'">Hot zone →</a>');
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
  }catch(e){ if(inner){ if(box!==host&&box.parentNode) box.parentNode.removeChild(box); host.dataset.state='failed'; } else box.style.display='none'; var fb2=document.getElementById('gia-fallback'); if(fb2) fb2.style.display=''; if(window.console) console.warn('GIA map fallback',e); }
})();
