# intel-gia

Grok Intelligence Agency. A static world-intel site: a daily edition, an archive, entity and hot-zone timelines, causal traces, and path-to-today slideshows.

A Grok bot delivers one JSON packet a day by committing `inbox/YYYY-MM-DD.json`. GitHub Actions checks the packet, merges it into `data/`, rebuilds the HTML, and publishes the site. The laptop does not have to be on.

## How a day lands

The bot sends one JSON object. Whatever records are in it get checked and merged: stories, entities, hot zones, links, storylines, relationships, corrections. A day that only adds a story and a day that also adds a new place are the same kind of file. `docs/examples/1941-12-07-pearl-harbor.json` is a full example, with a new place and a new hot zone included.

`summary` is the reported fact. `analysis` is the judgment, labeled `likely`, `possible`, or `speculative`. The field rules are in `data/SCHEMA.md`.

Apply rejects the whole packet if a story names an id that is neither in the corpus nor declared in that file. A typo does not become a node. Wikipedia URLs on new entities must return HTTP 200. An older story changes only through `corrections`, which keeps its original edition and records why. Only the latest edition can be republished, by pushing a changed copy of that same file.

## What the bot commits

```bash
python3 apply_packet.py --dry-run inbox/2026-10-16.json
git add inbox/2026-10-16.json
git commit -m "Inbox 2026-10-16"
git push
```

Commit the inbox file only. The Action commits the merged corpus and publishes the site. The bot needs push access to this repo.

## Local

```bash
python3 apply_packet.py
python3 build_dashboard.py
python3 -m http.server 8000
```

Open `http://localhost:8000/dashboard.html`. Cesium needs that server. Leaflet and the static map work from the file directly. `python3 apply_packet.py --skip-wikipedia` skips the article check when offline.

## Pages

The site is published from the `Publish` workflow. On a public repository, GitHub Pages is free, and the URL is world-readable.
