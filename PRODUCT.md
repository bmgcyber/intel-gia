# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: the operator (Bryan), reading the day's edition as a daily instrument — scanning what changed, where it escalated, and what connects to what.

Secondary: a reader arriving cold at the public GitHub Pages site with no prior context, who must be able to tell within seconds what this is, what is most urgent today, and where to start reading. The owner intends to show the site to others, so a cold reader's first impression is a product requirement, not a nice-to-have.

## Product Purpose

A static world-intelligence site published as a dated daily edition. It carries a current edition, a full archive, entity and hot-zone timelines, analytic causal traces between stories, and path-to-today slideshows. Success is that a reader can see today's situation, understand why it got there, and follow a chain of events backward through sourced stories.

## Positioning

The causal layer, with its epistemics on the surface. Reported fact (`summary`) is structurally separated from analytic judgment (`analysis`), and every judgment carries an explicit confidence label — `likely`, `possible`, or `speculative`. Links between stories and between hot zones are themselves labelled judgments, not implied adjacency. A neighboring news aggregator could not truthfully copy this without adopting the same separation and labelling discipline.

Corpus integrity is part of the claim: a packet is rejected whole if a story names an id that is neither in the corpus nor declared in that packet, so a typo never becomes a node. Older stories change only through `corrections`, which preserve the original edition and record why.

## Operating Context

One JSON packet per day. A Grok bot POSTs it to a Cloudflare Worker, which commits `inbox/YYYY-MM-DD.json`. GitHub Actions validates the packet, merges it into `data/`, rebuilds the HTML, and deploys to GitHub Pages. The operator's machine does not need to be on. Publication is unattended, so the build must fail loudly rather than deploy something wrong.

The site is read on both desktop and phone; the build solves map label placement separately per viewport band. The 2D map is the default view and is rendered as inline SVG at build time; Leaflet is lazy-loaded only when the reader opens the interactive map.

Print fidelity and no-JavaScript support are explicitly NOT binding constraints (owner, 2026-10-19): existing print styles are kept because they already work, but they must never hold back on-screen design.

## Capabilities and Constraints

- Static output. No backend at read time; every page is generated ahead of deploy.
- Build is Python 3.12 (uses PEP 701 f-string syntax; 3.11 and earlier fail). Requires `fontTools` and `Brotli` to read exact IBM Plex metrics from the vendored woff2.
- HTML and CSS are generated from Python. Design changes land in `gia_build/ui_tokens.py`, `gia_build/today.py`, `gia_build/v7pages.py`, `gia_build/markers.py`, and the CSS strings in `build_dashboard.py`. `dashboard.html`, `dashboard-cesium.html`, `map.html` and `history/` are gitignored build artifacts and must never be edited directly.
- Field rules live in `data/SCHEMA.md`. Severity taxonomy is fixed: `critical`, `high`, `elevated`, `watch`.
- Only the latest edition can be republished. New entities must have Wikipedia URLs returning HTTP 200.
- The 2D maps (Leaflet interactive, plus the static SVG fallback) are confirmed working and good. The Cesium 3D view is being retired at the owner's direction.

## Brand Commitments

Name: Grok Intelligence Agency (GIA). Confirmed and binding:

- The IBM Carbon-derived palette is kept as the substrate, including its documented contrast rulings. Severity colors carry meaning and are not decorative.
- IBM Plex Sans and IBM Plex Mono, self-hosted from `vendor/fonts2/`.
- Red is severity-only; it is never a generic UI accent.

## Evidence on Hand

Real corpus: 141 merged editions spanning 2000-03-31 to the present, 18 hot zones, entities, storylines, and analytic links. `docs/examples/1941-12-07-pearl-harbor.json` is a complete worked packet.

There are no customers, testimonials, usage numbers, press mentions, or pricing. Future work must not fabricate any of these.

## Product Principles

1. Fact and judgment stay visually and structurally distinct; confidence is always visible where a judgment appears.
2. Honest absence over false precision — a story with no defensible location gets no pin, and an empty section says so plainly.
3. The interface should be self-evident rather than self-explaining; if a section needs a paragraph describing how to read it, the design has failed.
4. Density is the point, but density without hierarchy is noise. The reader must always have an obvious place to look first.
5. Unattended publication demands that correctness failures stop the build rather than ship quietly.

## Accessibility & Inclusion

Required, and treated as a hard constraint rather than a finishing pass. (This still holds; only print and no-JS were relaxed.) The incumbent palette carries verified contrast ratios recorded inline at their definition. Keyboard focus is themed (`:focus-visible`, 2px). Interactive targets meet a 48px minimum. Print styles ship for every page. Any redesign must preserve or improve measured contrast, never regress it.
