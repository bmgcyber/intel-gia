/* Command palette. Flexibility and Efficiency scored 1/4 in the 2026-10-19 critique: 136 tab
   stops, no accelerators, no exposed anchors, on a page the operator reads every morning.
   The index is built from the rendered DOM on first open, so it never drifts from the build and
   costs nothing until summoned. Native <dialog> carries the focus trap, Escape and the backdrop. */
(function () {
  "use strict";
  var dlg, inp, list, items = [], view = [], cur = 0, built = false;

  function label(a) { return (a.textContent || "").replace(/\s+/g, " ").trim(); }

  function build() {
    if (built) return; built = true;
    var seen = Object.create(null);
    function add(kind, name, href) {
      name = (name || "").replace(/\s+/g, " ").trim();
      if (!name || !href) return;
      var k = kind + "\u0000" + href; if (seen[k]) return; seen[k] = 1;
      items.push({ kind: kind, name: name, href: href });
    }
    var secs = document.querySelectorAll("section[id]");
    for (var i = 0; i < secs.length; i++) {
      var h = secs[i].querySelector("h2");
      if (h) add("Jump to", label(h), "#" + secs[i].id);
    }
    var as = document.querySelectorAll("main a[href]");
    for (var j = 0; j < as.length; j++) {
      var a = as[j], href = a.getAttribute("href") || "", t = label(a);
      if (!t || t.length < 2) continue;
      if (/\/trace-/.test(href)) add("Story", t, href);
      else if (/\/zone-/.test(href)) add("Hot zone", t, href);
      else if (/\/storyline-/.test(href)) add("Storyline", t, href);
      else if (/\/link-/.test(href)) add("Link", t, href);
    }
  }

  function score(name, q) {
    var n = name.toLowerCase(), i = n.indexOf(q);
    if (i === 0) return 0; if (i > 0) return 1;
    // every term present, in any order
    var parts = q.split(/\s+/), k;
    for (k = 0; k < parts.length; k++) if (parts[k] && n.indexOf(parts[k]) < 0) return -1;
    return 2;
  }

  function render() {
    var q = inp.value.trim().toLowerCase();
    view = [];
    for (var i = 0; i < items.length; i++) {
      var s = q ? score(items[i].name, q) : (items[i].kind === "Jump to" ? 0 : 1);
      if (s >= 0) view.push({ it: items[i], s: s });
    }
    // sort by match quality, then keep each kind contiguous so a group heading appears once
    var rank = { "Jump to": 0, "Story": 1, "Hot zone": 2, "Storyline": 3, "Link": 4 };
    view.sort(function (a, b) {
      return (a.s - b.s) || ((rank[a.it.kind] || 9) - (rank[b.it.kind] || 9)) || a.it.name.localeCompare(b.it.name);
    });
    view = view.slice(0, 40).map(function (v) { return v.it; });
    if (cur >= view.length) cur = Math.max(0, view.length - 1);
    var html = "", last = null;
    for (var n = 0; n < view.length; n++) {
      var v = view[n];
      if (v.kind !== last) { html += '<li class="pg" role="presentation">' + v.kind + "</li>"; last = v.kind; }
      html += '<li role="option" id="pal-o' + n + '" aria-selected="' + (n === cur) + '"' +
              (n === cur ? ' class="on"' : "") + ">" + v.name.replace(/[&<>]/g, function (c) {
                return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; }) + "</li>";
    }
    list.innerHTML = html || '<li class="pg" role="presentation">Nothing matches that.</li>';
    inp.setAttribute("aria-activedescendant", view.length ? "pal-o" + cur : "");
    var on = list.querySelector(".on"); if (on && on.scrollIntoView) on.scrollIntoView({ block: "nearest" });
  }

  function go(n) {
    var v = view[n]; if (!v) return;
    close();
    if (v.href.charAt(0) === "#") {
      var el = document.querySelector(v.href);
      if (el) { el.scrollIntoView({ behavior: "smooth", block: "start" }); location.hash = v.href; }
    } else location.href = v.href;
  }

  function open() {
    build();
    if (!dlg.open) { dlg.showModal(); inp.value = ""; cur = 0; render(); inp.focus(); }
  }
  function close() { if (dlg.open) dlg.close(); }

  function make() {
    dlg = document.createElement("dialog");
    dlg.className = "pal"; dlg.setAttribute("aria-label", "Search this edition");
    dlg.innerHTML =
      '<input class="pal-q" type="text" role="combobox" aria-expanded="true" aria-controls="pal-list" ' +
      'aria-autocomplete="list" autocomplete="off" placeholder="Jump to a section, story, hot zone or storyline">' +
      '<ul class="pal-l" id="pal-list" role="listbox" aria-label="Results"></ul>' +
      '<p class="pal-h">↑↓ to move · Enter to open · Esc to close</p>';
    document.body.appendChild(dlg);
    inp = dlg.querySelector(".pal-q"); list = dlg.querySelector(".pal-l");
    inp.addEventListener("input", function () { cur = 0; render(); });
    dlg.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); if (cur < view.length - 1) { cur++; render(); } }
      else if (e.key === "ArrowUp") { e.preventDefault(); if (cur > 0) { cur--; render(); } }
      else if (e.key === "Enter") { e.preventDefault(); go(cur); }
    });
    list.addEventListener("click", function (e) {
      var li = e.target.closest("li[role=option]"); if (!li) return;
      go(parseInt(li.id.slice(5), 10));
    });
    dlg.addEventListener("click", function (e) { if (e.target === dlg) close(); });
  }

  function typing(t) {
    return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
  }

  document.addEventListener("keydown", function (e) {
    if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) { e.preventDefault(); open(); return; }
    if (e.key === "/" && !typing(e.target) && (!dlg || !dlg.open)) { e.preventDefault(); open(); }
  });

  function init() {
    if (!window.HTMLDialogElement || !document.createElement("dialog").showModal) return;  // no dialog: the page keeps its links
    make();
    var btn = document.querySelector(".palbtn");
    if (btn) { btn.hidden = false; btn.addEventListener("click", open); }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
