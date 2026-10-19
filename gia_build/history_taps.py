"""History-page phone tap targets: the Designer's proposal (2026-10-19 00:32 ET), PENDING the Director's call.
Isolated so it is easy to swap: build with GIA_HISTORY_TAPS=off to drop it. It doesn't change desktop or print.
- On phones (<=671 px) chips are >=24 px tall with 8 px gaps (WCAG 2.5.8).
- A chip group longer than 12 shows the first 12, then a 44 px '+N more' row that reveals the rest on the same
  page (CSS :target, no JS; like Today). N is counted at build time.
- 'Trace causal chain' and Wikipedia links become 44 px rows."""
import os
ON = os.environ.get("GIA_HISTORY_TAPS", "designer") != "off"
KEEP = 12
_ARROW = '<svg class="ci" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false"><path d="M12.3 9.3 8.5 13.1 8.5 1 7.5 1 7.5 13.1 3.7 9.3 3 10 8 15 13 10z"/></svg>'
CSS = ("" if not ON else
       ".hm{display:none}"
       "@media screen and (max-width:671px){"
       ".hc{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}.hc .chip{display:inline-flex;align-items:center;min-height:24px;margin:0;box-sizing:border-box}"
       ".hc .x{display:none}.hc:target .x{display:inline-flex}.hc:target>.hm{display:none}"
       ".hm{display:flex;justify-content:space-between;align-items:center;flex:1 0 100%;min-height:44px;box-sizing:border-box;border-top:1px solid #393939;"
       "color:var(--gia-link);text-decoration:none;font:600 14px/20px \"IBM Plex Sans\",system-ui,sans-serif}.hm .ci{width:16px;height:16px;fill:currentColor}"
       ".hm b{font-family:\"IBM Plex Mono\",ui-monospace,monospace;font-variant-numeric:tabular-nums;font-weight:500}"
       ".trc a,.wik a{display:flex;align-items:center;min-height:44px}"
       ".hc:target{outline:none;background:none}}")
def group(chips, gid, cls="chips"):
    """chips: list of chip <a> html strings. Returns the group wrapped for the phone trim (or plain when off)."""
    if not chips: return ""
    if not ON: return f'<div class="{cls}">{"".join(chips)}</div>' if cls else "".join(chips)
    if len(chips) <= KEEP: return f'<div class="{cls} hc">{"".join(chips)}</div>'
    body = "".join(chips[:KEEP]) + "".join(c.replace('class="chip', 'class="x chip', 1) for c in chips[KEEP:])
    return (f'<div class="{cls} hc" id="{gid}">{body}<a class="hm" href="#{gid}"><span><b>+{len(chips) - KEEP}</b> more</span>{_ARROW}</a></div>')
