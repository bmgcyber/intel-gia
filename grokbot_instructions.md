# Grok bot instructions

Read this file at the start of each run. It is the current way to file a GIA packet. Do not git commit, and do not push. Delivery is one HTTP POST.

## What you file

One JSON object for one edition date. The shape is `data/SCHEMA.md`. `docs/examples/1941-12-07-pearl-harbor.json` shows a new place and a new story. Do not copy that example into `inbox/`.

`summary` is the reported fact. `analysis` is the judgment, with `confidence` of `likely`, `possible`, or `speculative`. `sources` lists at least one `{name, url}`. Omit `effects` and `related_stories`. The checker fills those.

An id is a stable lowercase kebab-case slug and is never reused. A slug that is not already in the corpus must be declared in this packet. A typo does not become a node. An older story changes only through `corrections`, which keeps its original edition and records `why`.

## Places

A hot zone is the theater right now. It is not where an event happened. Do not put a hot-zone coordinate on an event.

Every new story has `marker` and exactly one of `where` or `unplaced`.

- `marker` is `military`, `strike`, `diplomacy`, `energy`, or `political`.
- `where` is a list of place ids. The first is the point the path trail uses. Every id is drawn. Each id must be a `place` that already has coordinates, or a place this packet declares with coordinates.
- `unplaced` is a short reason there is no honest pin.

Both `where` and `unplaced` on the same story is an error. A country, a region, or a country centroid is not a pin. If the summary and its sources do not name a place, set `unplaced` and do not guess a dot.

A new place is an entity:

```json
{"id": "kyiv", "name": "Kyiv", "type": "place", "wikipedia": "https://en.wikipedia.org/wiki/Kyiv", "lat": 50.45, "lon": 30.52333333, "precision": "city"}
```

`precision` is `city`, `sector`, or `feature`. `lat` and `lon` come from that place's Wikipedia article. The Wikipedia URL must be `https`, contain `wikipedia.org/wiki/`, and return HTTP 200. If the article has no coordinates, do not invent them. Leave that place out and say so in `unplaced`, or name only the places you can source.

To move a place that already has coordinates, send `place_corrections`. Do not repeat the entity with a different lat or lon. Do not use `place_corrections` for a place this same packet declares. Put those coordinates on the entity.

```json
{"id": "kyiv", "lat": 50.4501, "lon": 30.5234, "precision": "city", "why": "The article coordinate is the city center, not the oblast."}
```

A correction must change the latitude, the longitude, or the precision. A story correction may set `where`, `marker`, and `unplaced`. Setting `where` clears `unplaced`, and the reverse.

Stories already in the corpus with neither field stay unplaced until you correct them. Do not backfill all of them in one packet. Place the story you are filing, and correct an old one when you are fixing a known bad pin.

## How to send it

POST the raw JSON bytes:

```bash
curl -X POST https://gia-ingest.bryan-a4a.workers.dev/inbox \
  -H "Authorization: Bearer $INGEST_SECRET" \
  -H "Content-Type: application/json" \
  --data-binary @packet.json
```

Use the ingest secret you were already given. Do not write that secret into this repo, into the packet, or into a commit. Do not make a new secret.

The file name the Worker writes is `inbox/YYYY-MM-DD.json`, from the `edition` field. `edition` must be a real calendar date.

A `200` means GitHub accepted the file. It does not mean the packet was valid. Publish runs the checker. If Publish fails, POST a corrected copy of that same edition. Sending the same edition again replaces the file. Sending the identical bytes returns `unchanged` and does not commit.

Only the latest edition can be replaced. An older file cannot move the hot-zone snapshot after a newer edition exists.
