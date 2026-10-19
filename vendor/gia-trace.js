/* GIA trace pages: progressive enhancement only. The server-rendered tree (depth 3, each
   story once) is complete text; this script reveals "expand here" buttons on depth-capped
   nodes and expands them 3 more levels from the shared history/causal.json (fetched once,
   on first click). Stories already on the page become "shown above" links. Needs http(s);
   on file:// the fetch fails and the "open its trace" link remains. */
(function(){
  var btns=document.querySelectorAll('button.more[data-id]'); if(!btns.length||!window.fetch) return;
  var G=null;
  function esc(t){return String(t).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function tree(id,depth){
    var n=G[id]; if(!n||!n[2].length) return '<ul class="tree"><li><span class="meta">◆ root (no recorded causes)</span></li></ul>';
    var o='<ul class="tree">';
    n[2].forEach(function(c){var t=G[c[0]]; if(!t) return;
      var why='<div class="an"><span class="conf '+esc(c[1])+'">'+esc(c[1])+'</span>'+esc(c[2])+'</div>';
      if(document.getElementById('n-'+c[0])||seen[c[0]]){o+='<li><a href="#n-'+esc(c[0])+'">↺ '+esc(t[0])+'</a> <span class="meta">'+esc(t[1])+' · shown above</span>'+why+'</li>';return;}
      seen[c[0]]=1;
      o+='<li id="n-'+esc(c[0])+'"><a href="trace-'+esc(c[0])+'.html"><b>'+esc(t[0])+'</b></a> <span class="meta">'+esc(t[1])+'</span>'+why;
      o+=(depth<3||!t[2].length)?tree(c[0],depth+1):'<div class="meta">▸ <a href="trace-'+esc(c[0])+'.html">open its trace</a></div>';
      o+='</li>';});
    return o+'</ul>';
  }
  var seen={};
  [].forEach.call(btns,function(b){b.hidden=false;b.addEventListener('click',function(){
    b.disabled=true;
    (G?Promise.resolve(G):fetch('causal.json').then(function(r){return r.json();}).then(function(j){G=j;return j;}))
      .then(function(){var d=document.createElement('div');d.innerHTML=tree(b.dataset.id,1);b.parentNode.parentNode.appendChild(d);b.parentNode.removeChild(b);})
      .catch(function(){b.textContent='unavailable offline';});
  });});
})();
