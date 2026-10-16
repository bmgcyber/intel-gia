# GIA intel data schema (v2, 2026-10-14)

All files are UTF-8 JSON in `data/`. IDs are stable, lowercase kebab-case slugs and are never reused. Daily drops land in `inbox/YYYY-MM-DD.json` and are merged with `python3 apply_packet.py`. Rebuild with `python3 build_dashboard.py`. It writes `dashboard.html` (latest edition only) and `history/*.html` (full archive).

## stories.json: array of Story
| field | type | req | notes |
|---|---|---|---|
| id | slug | yes | unique; for backfill use `YYYY-short-slug` |
| date | ISO string | yes | `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; 1990+ (no limit in code). Sorts lexically. |
| date_precision | `year`\|`month`\|`day` | no (default day) | controls display |
| kind | `event`\|`daily-brief`\|`analysis`\|`backfill` | no (default event) | |
| era | string | no | e.g. `1990s`, `post-9/11` |
| edition | ISO date | no | the brief edition that published it; the main dashboard shows only the latest edition. Backfill omits it |
| region | Americas, Europe, Middle East, Africa, Russia/Eurasia, Asia-Pacific | yes | |
| title, summary | string | yes | summary = reported fact only |
| analysis | {text, confidence: likely\|possible\|speculative} | no | judgment, kept separate from fact |
| sources | [{name, url}] | yes | |
| entities | [entity id] | yes | tag all relevant actors, places and themes together |
| where | [place id] | one of where / unplaced | places where it happened. The first is the trail point. Every id must be a place that has coordinates. New packet stories need this or `unplaced` |
| marker | military\|strike\|diplomacy\|energy\|political | yes on new stories | how the event is drawn. Hot zones are not a marker |
| unplaced | string | one of where / unplaced | short reason there is no honest pin. A country centroid is not a pin |
| storylines | [storyline id] | no | |
| related_stories | [story id] | no | derived: same storyline, or sharing ≥3 entities |

## entities.json
`{id, name, type: country|group|person|place|organization|theme, wikipedia}`. The Wikipedia URL must be verified (HTTP 200) before it is added. Optional for later: `aliases[]`, `start`, `end`.

A `place` also has `lat`, `lon`, and `precision: city|sector|feature`. Those coordinates come from that place's Wikipedia article. A country centroid is not a precision and cannot be an event pin. A later edition changes coordinates only through `place_corrections`, which stores `location_revisions: [{edition, why, lat, lon, precision}]`.

## storylines.json (threads from intel/threads.md)
`{id, name, entities[], stories[], source}`. A storyline page shows `stories` ∪ every story whose `storylines` contains this id.

## hotzones.json `{date, zones[], links[]}`
- zone: `{id, name, lat, lon, severity: critical|high|elevated|watch, note, entities[], stories[], label_dx?, label_dy?}`. The history page shows its `stories` plus any story sharing ≥2 of its entities.
- link (causal arc, analysis): `{id: "from--to", from, to, label, entities[], stories[]}`.

## Generated pages (relative links, no JS)
`history/index.html` (all stories by year), `history/entity-<id>.html`, `history/zone-<id>.html`, `history/link-<id>.html`, `history/storyline-<id>.html`. Each page is a timeline, oldest → newest, grouped by year then date, with related-entity chips. Entity pages also carry the Wikipedia link, storylines and zones.

## Integrity
Every referenced id must exist. With scripts stripped, there must be no broken internal links.

## v3 additions (2026-10-14): causality and relationships
### Story fields
- `causes`: [{story, why, confidence: likely|possible|speculative}]. Upstream stories that led to this one. This is the authored field. Links may point forward across years (e.g. a 2026 story citing a 2022 cause).
- `effects`: same shape. The inverse of `causes`; the builder recomputes it on every build, so edit `causes` only.
- `batch`: provenance tag, e.g. `backfill-2021-22`. `kind: backfill` marks historical stories.
- `related_stories`: derived from causal neighbours plus stories sharing ≥3 entities.
### relationships.json: actor relationships over time
`{id: "a--type--b", a, b, type: alliance|rivalry|patron-proxy|supplier|sanction, start, end|null, stated, actual, confidence, evidence: [story ids]}`. Direction runs a → b (patron → proxy, sanctioner → target, supplier → buyer). `actual` is analysis.
### Generated
- `history/trace-<story>.html`: roots, a chronological chain (roots → event), a nested "led to this" tree (cycle-safe), and the downstream set.
- Story cards show "Led to this" / "What it set off" and a Trace link.
- Entity pages show a relationships table sorted by start date.
### Backfill files
- `backfill/bYYYY.py` holds batch source data (stories, new entities, forward links, relationships), merged into the JSON files.
- Every Wikipedia URL is HTTP-checked before merge.

## Path-to-today slideshows (v4)
Demo paths are listed in `data/paths.json` and generated under `history/path-<root-story-id>/slide-NN.html` (+ `index.html`).
Each slide is static HTML: a map of the places that step happened, with earlier steps dimmed, a gold trail through each step's first place, Prev/Next + progress dots, and a bottom panel (date, title, summary, analysis, sources, why-next). A step with no honest place draws no pin and says why. Hot-zone rings are not drawn on a path slide. Optional keyboard arrows via progressive-enhancement JS.
`Path to current day` buttons appear on Trace pages and story cards for events that sit on a demo path. To add a path, append `(root_id, goal_id, title)` to `DEMO_PATHS` in `build_dashboard.py` and rebuild.

## Interactive maps (v5)
- `vendor/leaflet/` holds a vendored copy of Leaflet 1.9.4, so there is no CDN dependency. `vendor/gia-map.js` is the shared init script.
- Each page embeds its own map data as `<script type="application/json" id="gia-map-data">`, so nothing is fetched except tiles. Dashboard mode includes hot-zone rings, today's event pins, and links. Path mode adds activePlaces, pastPlaces, trailPlaces, prevBounds (the previous slide's view, so the map flies to the new theater on load) and badge. Pins differ by marker. Rings are hot zones only.
- Tiles come from Esri World Dark Gray Base and Reference (no API key; works from file://) and **need network**. Carto dark tiles were rejected because they return "API key required" without a Referer.
- Fallback: the static SVG sits in `#gia-fallback` and is hidden only after Leaflet initialises. With no JS (e.g. a chat viewer), the static map shows.

## 3D Cesium build (v6)
- Parallel pages: `dashboard-cesium.html` and `history/path-*/slide-NN-cesium.html`. They're generated by the end of `build_dashboard.py` from the Leaflet pages and use the same embedded `#gia-map-data`. Init script: `vendor/gia-cesium.js`. The Leaflet and Cesium versions link to each other.
- CesiumJS 1.122.0 is pinned from the cdnjs CDN. It isn't vendored because the full build is about 40 MB. **No Cesium Ion token is used**: Ion is disabled, imagery is Esri World Dark Gray (keyless), and terrain is the plain ellipsoid. Tiles and Cesium itself **need network**.
- **Must be served over http** because browsers block Cesium's web workers on file://. Use `open-3d.command` (Mac), `open-3d.bat` (Windows) or `open-3d.sh`, or run `python3 -m http.server 8000`. On file://, the page shows an explanation and keeps the static SVG map.

## Daily packet (inbox/YYYY-MM-DD.json)
One edition per file. The file name is the edition date. `apply_packet.py` rejects the whole file on any error and leaves the corpus unchanged. There is one packet shape. Include whichever records this edition has: stories, new entities, zones, links, storylines, relationships, corrections, place corrections. A new place is an object in `entities`, same as any other field, and it carries its coordinates.

| field | required | notes |
|---|---|---|
| edition | yes | `YYYY-MM-DD`, must match the file name |
| stories | no | new stories for this edition. An id that already exists must go in `corrections`, not here |
| corrections | no | `{id, why, ...fields}` rewrites an older story and records `revisions`. `edition` on that story stays the day it was first published. Fields include `where`, `marker`, and `unplaced`. Setting `where` clears `unplaced`, and the reverse |
| entities | no | new `{id, name, type, wikipedia}`. A place also needs `lat`, `lon`, and `precision` of `city`, `sector`, or `feature`. Wikipedia must be https and return HTTP 200. An entity a previous edition created is permanent. Sending a different coordinate for an old place fails |
| place_corrections | no | `{id, lat, lon, precision, why}` moves an existing place. It must change a coordinate or the precision. Do not use it for a place this same packet declares |
| storylines | no | new `{id, name, entities, stories}`. An existing line keeps its name; entities and stories are unioned |
| zones | no | new hot zone, or an update of severity, note, position, entities, stories. Updates union entities and stories |
| links | no | `{id: "from--to", from, to, label, entities, stories}` |
| relationships | no | `{id: "a--type--b", a, b, type, start, end, stated, actual, confidence, evidence}` |

Story fields match the corpus: `summary` is reported fact, `analysis` is judgment with `likely`, `possible`, or `speculative`. `sources` is required. A new story needs `marker` and exactly one of `where` or `unplaced`. `where` lists place ids that already have coordinates, or places this packet declares with coordinates. `causes` point at story ids that already exist or are in this same packet. Omit `effects` and `related_stories`; apply fills `related_stories`, and the builder fills `effects`. Stories already in the corpus may have neither `where` nor `unplaced`; the map then draws no pin for them.

Rules:
- A slug on a story, zone, link, or relationship that is neither in the corpus nor declared in this packet fails the edition.
- Only the latest applied edition can be republished. POST a changed copy of that edition, or push a changed `inbox/YYYY-MM-DD.json`. Apply rolls that edition back and merges the new bytes. An older file cannot move the hot-zone snapshot after a newer edition exists.
- Entities are not deleted. A republish of the edition that created an entity may still fix that entity's name, type, Wikipedia URL, and, for a place, its coordinates. A later edition uses `place_corrections`. Republishing that edition rolls the coordinates back before the new packet is applied.
- `data/ledger.json` records the packet hash and the undo snapshot. Do not edit it by hand.
