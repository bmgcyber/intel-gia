# intel-gia

Grok Intelligence Agency. A static world-intel site: a daily edition, an archive, entity and hot-zone timelines, causal traces, and path-to-today slideshows.

A Grok bot delivers one JSON packet a day by POSTing it to the ingest Worker. The Worker commits `inbox/YYYY-MM-DD.json`. GitHub Actions checks the packet, merges it into `data/`, rebuilds the HTML, and publishes the site. The laptop does not have to be on.

## How a day lands

The bot sends one JSON object. Whatever records are in it get checked and merged: stories, entities, hot zones, links, storylines, relationships, corrections. A day that only adds a story and a day that also adds a new place are the same kind of file. `docs/examples/1941-12-07-pearl-harbor.json` is a full example, with a new place and a new hot zone included.

`summary` is the reported fact. `analysis` is the judgment, labeled `likely`, `possible`, or `speculative`. A new story also needs `marker` and either `where` (place ids that have coordinates) or `unplaced` (why there is no honest pin). A country center is not a pin. The field rules are in `data/SCHEMA.md`. The bot reads `grokbot_instructions.md`.

Apply rejects the whole packet if a story names an id that is neither in the corpus nor declared in that file. A typo does not become a node. Wikipedia URLs on new entities must return HTTP 200. An older story changes only through `corrections`, which keeps its original edition and records why. Only the latest edition can be republished, by sending a changed copy of that same edition.

## What the bot sends

```bash
curl -X POST https://gia-ingest.bryan-a4a.workers.dev/inbox \
  -H "Authorization: Bearer $INGEST_SECRET" \
  -H "Content-Type: application/json" \
  --data-binary @inbox/2026-10-16.json
```

A `200` means GitHub accepted that file. Publish then checks it. If Publish fails, POST a corrected copy of the same edition. The bearer secret and the GitHub write token stay on the Worker. Setup is in `ingest/README.md`.

## Local

```bash
python3 apply_packet.py
python3 build_dashboard.py
python3 -m http.server 8000
```

Open `http://localhost:8000/dashboard.html`. Cesium needs that server. Leaflet and the static map work from the file directly. `python3 apply_packet.py --skip-wikipedia` skips the article check when offline.

## Pages

The site is published from the `Publish` workflow. On a public repository, GitHub Pages is free, and the URL is world-readable.
