#!/usr/bin/env python3
"""Merge inbox/YYYY-MM-DD.json into data/.

A packet may add stories and, when it declares them, new entities, hot zones,
links, storylines, and relationships. A bare slug that is not declared is an
error, and the whole packet is rejected. Nothing is written unless the packet
is valid. See data/SCHEMA.md.
"""
import argparse, copy, hashlib, json, re, sys, urllib.error, urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

UA = "GIA-apply/1.0 (+https://github.com/bmgcyber/intel-gia)"
REGIONS = {"Americas", "Europe", "Middle East", "Africa", "Russia/Eurasia", "Asia-Pacific"}
CONFIDENCE = {"likely", "possible", "speculative"}
KINDS = {"event", "daily-brief", "analysis", "backfill"}
ENTITY_TYPES = {"country", "group", "person", "place", "organization", "theme"}
REL_TYPES = {"alliance", "rivalry", "patron-proxy", "supplier", "sanction"}
SEVERITY = {"critical", "high", "elevated", "watch"}
PLACE_PRECISIONS = {"city", "sector", "feature"}
MARKERS = {"military", "strike", "diplomacy", "energy", "political"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PACKET_KEYS = {"edition", "entities", "storylines", "zones", "links", "relationships", "stories", "corrections", "place_corrections"}
STORY_KEYS = {"id", "date", "date_precision", "kind", "era", "edition", "region", "title", "summary", "analysis", "sources", "entities", "storylines", "causes", "where", "marker", "unplaced"}
CORRECTION_FIELDS = ["title", "summary", "analysis", "sources", "entities", "storylines", "causes", "region", "date", "date_precision", "kind", "era", "where", "marker", "unplaced"]
ENTITY_KEYS = {"id", "name", "type", "wikipedia"}
PLACE_KEYS = ENTITY_KEYS | {"lat", "lon", "precision"}
ZONE_KEYS = {"id", "name", "lat", "lon", "severity", "note", "entities", "stories", "label_dx", "label_dy"}
LINK_KEYS = {"id", "from", "to", "label", "entities", "stories"}
REL_KEYS = {"id", "a", "b", "type", "start", "end", "stated", "actual", "confidence", "evidence"}
LINE_KEYS = {"id", "name", "entities", "stories", "source"}
PLACE_CORRECTION_KEYS = {"id", "lat", "lon", "precision", "why"}
LIST_KEYS = ("entities", "storylines", "zones", "links", "relationships", "stories", "corrections", "place_corrections")

class PacketError(Exception):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def dump_json(path, obj):
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def is_num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def precision_of(value):
    if not isinstance(value, str):
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
        return "day"
    if re.fullmatch(r"\d{4}-\d{2}", value):
        try:
            datetime.strptime(value, "%Y-%m")
        except ValueError:
            return None
        return "month"
    if re.fullmatch(r"\d{4}", value):
        return "year"
    return None

def after_edition(value, precision, edition):
    if precision == "day":
        return value > edition
    if precision == "month":
        return value > edition[:7]
    return value > edition[:4]

def default_wikipedia(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
    except urllib.error.HTTPError as exc:
        return f"Wikipedia check failed for {url}: HTTP {exc.code}"
    except Exception as exc:
        return f"Wikipedia check failed for {url}: {exc}"
    if code != 200:
        return f"Wikipedia check failed for {url}: HTTP {code}"
    return None

def unknown(obj, allowed, path, errors):
    for key in sorted(set(obj) - set(allowed)):
        errors.append(f"{path}: unknown field {key}")

def need_str(obj, key, path, errors):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}.{key} must be a non-empty string")
        return None
    return value

def need_slug(value, path, errors):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        errors.append(f"{path} must be a lowercase slug")
        return False
    return True

def as_objects(packet, key, errors):
    if key not in packet:
        return []
    value = packet[key]
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return []
    out = []
    seen = set()
    for i, item in enumerate(value):
        path = f"{key}[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{path} must be an object")
            continue
        ident = item.get("id")
        if key == "corrections":
            if not isinstance(ident, str) or not ident:
                errors.append(f"{path}.id must be a non-empty string")
                continue
        elif key in ("links", "relationships"):
            if not isinstance(ident, str) or not ident:
                errors.append(f"{path}.id must be a non-empty string")
                continue
        elif not need_slug(ident, f"{path}.id", errors):
            continue
        if ident in seen:
            errors.append(f"{path} duplicate id {ident}")
            continue
        seen.add(ident)
        out.append(item)
    return out

def check_url(value, path, errors, wikipedia=False):
    if not isinstance(value, str) or not (value.startswith("https://") or value.startswith("http://")):
        errors.append(f"{path} must be an http(s) URL")
        return False
    if wikipedia and (not value.startswith("https://") or "wikipedia.org/wiki/" not in value):
        errors.append(f"{path} must be an https Wikipedia article URL")
        return False
    return True

def check_sources(sources, path, errors):
    if not isinstance(sources, list) or not sources:
        errors.append(f"{path}.sources must list at least one source")
        return
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"{path}.sources[{i}] must be an object")
            continue
        unknown(source, {"name", "url"}, f"{path}.sources[{i}]", errors)
        need_str(source, "name", f"{path}.sources[{i}]", errors)
        check_url(source.get("url"), f"{path}.sources[{i}].url", errors)

def check_causes(causes, path, known_stories, errors):
    if not isinstance(causes, list):
        errors.append(f"{path}.causes must be a list")
        return
    for i, cause in enumerate(causes):
        cpath = f"{path}.causes[{i}]"
        if not isinstance(cause, dict):
            errors.append(f"{cpath} must be an object")
            continue
        unknown(cause, {"story", "why", "confidence"}, cpath, errors)
        sid = cause.get("story")
        if not isinstance(sid, str) or sid not in known_stories:
            errors.append(f"{cpath}.story is not an existing story")
        elif path.endswith(sid) or path == f"stories[{sid}]":
            pass
        need_str(cause, "why", cpath, errors)
        if cause.get("confidence") not in CONFIDENCE:
            errors.append(f"{cpath}.confidence must be likely, possible, or speculative")

def check_analysis(analysis, path, errors):
    if analysis is None:
        return
    if not isinstance(analysis, dict):
        errors.append(f"{path}.analysis must be an object")
        return
    unknown(analysis, {"text", "confidence"}, f"{path}.analysis", errors)
    need_str(analysis, "text", f"{path}.analysis", errors)
    if analysis.get("confidence") not in CONFIDENCE:
        errors.append(f"{path}.analysis.confidence must be likely, possible, or speculative")

def check_id_list(value, path, known, errors, label):
    if value is None:
        return
    if not isinstance(value, list) or not all(isinstance(i, str) for i in value):
        errors.append(f"{path} must be a list of ids")
        return
    for ident in value:
        if ident not in known:
            errors.append(f"{path}: unknown {label} {ident}")

def same_entity(have, want):
    keys = ["id", "name", "type", "wikipedia"]
    if any(k in have or k in want for k in ("lat", "lon", "precision")):
        keys += ["lat", "lon", "precision"]
    return all(have.get(k) == want.get(k) for k in keys)

def check_coords(item, path, errors):
    lat, lon = item.get("lat"), item.get("lon")
    ok = True
    if not is_num(lat) or not -90 <= lat <= 90:
        errors.append(f"{path}.lat must be a latitude")
        ok = False
    if not is_num(lon) or not -180 <= lon <= 180:
        errors.append(f"{path}.lon must be a longitude")
        ok = False
    if item.get("precision") not in PLACE_PRECISIONS:
        errors.append(f"{path}.precision must be city, sector, or feature")
        ok = False
    return ok

def is_placed(entity):
    if not entity or entity.get("type") != "place":
        return False
    lat, lon = entity.get("lat"), entity.get("lon")
    return (
        is_num(lat) and is_num(lon)
        and -90 <= lat <= 90 and -180 <= lon <= 180
        and entity.get("precision") in PLACE_PRECISIONS
    )

def placed_ids(corpus, lists, prior_entities=None):
    prior_entities = prior_entities or {}
    found = set()
    for ident, entity in corpus.entity.items():
        base = prior_entities[ident] if ident in prior_entities and prior_entities[ident] else entity
        if is_placed(base):
            found.add(ident)
    for item in lists["entities"]:
        if item.get("type") == "place" and check_coords(item, "entities", []):
            found.add(item["id"])
    for item in lists["place_corrections"]:
        have = corpus.entity.get(item.get("id"))
        if have and have.get("type") == "place" and check_coords(item, "place_corrections", []):
            found.add(item["id"])
    return found

def check_marker(item, path, errors, required):
    if "marker" not in item:
        if required:
            errors.append(f"{path}.marker must be military, strike, diplomacy, energy, or political")
        return
    if item.get("marker") not in MARKERS:
        errors.append(f"{path}.marker must be military, strike, diplomacy, energy, or political")

def check_location(item, path, errors, places, entities, required):
    has_where = "where" in item
    has_unplaced = "unplaced" in item
    if has_where and has_unplaced:
        errors.append(f"{path} cannot set both where and unplaced")
        return
    if has_unplaced:
        if not isinstance(item.get("unplaced"), str) or not item["unplaced"].strip():
            errors.append(f"{path}.unplaced must be a non-empty string")
        return
    if has_where:
        where = item.get("where")
        if not isinstance(where, list) or not where or not all(isinstance(i, str) for i in where):
            errors.append(f"{path}.where must list at least one place")
            return
        for ident in where:
            if ident in places:
                continue
            if ident in entities:
                errors.append(f"{path}.where: {ident} is not a placed location")
            else:
                errors.append(f"{path}.where: unknown place {ident}")
        return
    if required:
        errors.append(f"{path} needs where or unplaced")

class Corpus:
    def __init__(self, root):
        self.root = Path(root)
        data = self.root / "data"
        self.stories = load_json(data / "stories.json")
        self.entities = load_json(data / "entities.json")
        self.storylines = load_json(data / "storylines.json")
        self.hotzones = load_json(data / "hotzones.json")
        self.relationships = load_json(data / "relationships.json")
        ledger_path = data / "ledger.json"
        self.ledger = load_json(ledger_path) if ledger_path.exists() else {"packets": {}}
        paths = data / "paths.json"
        self.paths = load_json(paths) if paths.exists() else {}
        self.dirty = set()
        self.reindex()

    def reindex(self):
        self.story = {s["id"]: s for s in self.stories}
        self.entity = {e["id"]: e for e in self.entities}
        self.line = {s["id"]: s for s in self.storylines}
        self.zone = {z["id"]: z for z in self.hotzones.get("zones", [])}
        self.link = {l["id"]: l for l in self.hotzones.get("links", [])}
        self.rel = {r["id"]: r for r in self.relationships}

    def save(self):
        data = self.root / "data"
        if "stories" in self.dirty:
            dump_json(data / "stories.json", self.stories)
        if "entities" in self.dirty:
            dump_json(data / "entities.json", self.entities)
        if "storylines" in self.dirty:
            dump_json(data / "storylines.json", self.storylines)
        if "hotzones" in self.dirty:
            dump_json(data / "hotzones.json", self.hotzones)
        if "relationships" in self.dirty:
            dump_json(data / "relationships.json", self.relationships)
        if "ledger" in self.dirty:
            dump_json(data / "ledger.json", self.ledger)
        self.dirty.clear()

class Undo:
    def __init__(self):
        self.stories, self.zones, self.links = {}, {}, {}
        self.relationships, self.storylines = {}, {}
        self.entities = {}
        self.entities_added = []
        self.date_saved = False
        self.hotzones_date = None

    def to_json(self):
        return {
            "stories": self.stories, "zones": self.zones, "links": self.links,
            "relationships": self.relationships, "storylines": self.storylines,
            "entities": self.entities,
            "entities_added": self.entities_added, "date_saved": self.date_saved,
            "hotzones_date": self.hotzones_date,
        }

    @classmethod
    def from_json(cls, raw):
        undo = cls()
        for name in ("stories", "zones", "links", "relationships", "storylines"):
            setattr(undo, name, (raw or {}).get(name) or {})
        undo.entities = (raw or {}).get("entities") or {}
        undo.entities_added = list((raw or {}).get("entities_added") or [])
        undo.date_saved = bool((raw or {}).get("date_saved"))
        undo.hotzones_date = (raw or {}).get("hotzones_date")
        return undo

def remember(bucket, ident, current):
    if ident not in bucket:
        bucket[ident] = copy.deepcopy(current) if current is not None else None

def restore(corpus, undo):
    def put_back(items, saved):
        saved = saved or {}
        by = {item["id"]: item for item in items}
        for ident, before in saved.items():
            if before is None:
                by.pop(ident, None)
            else:
                by[ident] = copy.deepcopy(before)
        return [by[item["id"]] for item in items if item["id"] in by]

    if undo.stories:
        corpus.stories = put_back(corpus.stories, undo.stories)
        corpus.dirty.add("stories")
    if undo.zones or undo.links or undo.date_saved:
        corpus.hotzones["zones"] = put_back(corpus.hotzones.get("zones", []), undo.zones)
        corpus.hotzones["links"] = put_back(corpus.hotzones.get("links", []), undo.links)
        if undo.date_saved:
            corpus.hotzones["date"] = undo.hotzones_date
        corpus.dirty.add("hotzones")
    if undo.relationships:
        corpus.relationships = put_back(corpus.relationships, undo.relationships)
        corpus.dirty.add("relationships")
    if undo.storylines:
        corpus.storylines = put_back(corpus.storylines, undo.storylines)
        corpus.dirty.add("storylines")
    if undo.entities:
        by = {item["id"]: i for i, item in enumerate(corpus.entities)}
        for ident, before in undo.entities.items():
            if before and ident in by:
                corpus.entities[by[ident]] = copy.deepcopy(before)
        corpus.dirty.add("entities")
    corpus.reindex()

def path_ids(paths):
    found = set()
    if isinstance(paths, dict):
        for info in paths.values():
            if isinstance(info, dict):
                found.update(s for s in info.get("steps") or [] if isinstance(s, str))
    return found

def union(have, more):
    out = list(have or [])
    for ident in more:
        if ident not in out:
            out.append(ident)
    return out

def related_ids(corpus, story):
    out, seen = [], {story["id"]}
    def add(ident):
        if ident and ident not in seen and ident in corpus.story:
            seen.add(ident)
            out.append(ident)
    for cause in story.get("causes") or []:
        add(cause.get("story"))
    for other in corpus.stories:
        if any(c.get("story") == story["id"] for c in other.get("causes") or []):
            add(other["id"])
    ents = set(story.get("entities") or [])
    if len(ents) >= 3:
        for other in corpus.stories:
            if len(ents & set(other.get("entities") or [])) >= 3:
                add(other["id"])
    return out

def recompute_related(corpus, undo, touched):
    corpus.reindex()
    for sid in touched:
        story = corpus.story[sid]
        rel = related_ids(corpus, story)
        if story.get("related_stories") != rel:
            remember(undo.stories, sid, corpus.story.get(sid))
            story["related_stories"] = rel
            corpus.dirty.add("stories")
    for sid in touched:
        story = corpus.story[sid]
        for cause in story.get("causes") or []:
            oid = cause.get("story")
            if oid in touched or oid not in corpus.story:
                continue
            other = corpus.story[oid]
            rel = list(other.get("related_stories") or [])
            if sid not in rel:
                remember(undo.stories, oid, other)
                other["related_stories"] = rel + [sid]
                corpus.dirty.add("stories")

def integrity(corpus):
    errors = []
    stories, entities = set(corpus.story), set(corpus.entity)
    lines, zones = set(corpus.line), set(corpus.zone)
    def req(ident, known, path, label):
        if ident not in known:
            errors.append(f"integrity: {path} unknown {label} {ident}")
    for story in corpus.stories:
        for ident in story.get("entities") or []:
            req(ident, entities, story["id"], "entity")
        for ident in story.get("storylines") or []:
            req(ident, lines, story["id"], "storyline")
        for ident in story.get("related_stories") or []:
            req(ident, stories, story["id"], "story")
        for cause in story.get("causes") or []:
            req(cause.get("story"), stories, story["id"], "cause")
        if story.get("where") and story.get("unplaced"):
            errors.append(f"integrity: {story['id']} sets both where and unplaced")
        if "marker" in story and story.get("marker") not in MARKERS:
            errors.append(f"integrity: {story['id']} has an unknown marker")
        for ident in story.get("where") or []:
            if not is_placed(corpus.entity.get(ident)):
                errors.append(f"integrity: {story['id']} where {ident} is not a placed location")
    for zone in corpus.hotzones.get("zones", []):
        for ident in zone.get("entities") or []:
            req(ident, entities, zone["id"], "entity")
        for ident in zone.get("stories") or []:
            req(ident, stories, zone["id"], "story")
    for link in corpus.hotzones.get("links", []):
        req(link.get("from"), zones, link["id"], "zone")
        req(link.get("to"), zones, link["id"], "zone")
        for ident in link.get("entities") or []:
            req(ident, entities, link["id"], "entity")
        for ident in link.get("stories") or []:
            req(ident, stories, link["id"], "story")
    for rel in corpus.relationships:
        req(rel.get("a"), entities, rel["id"], "entity")
        req(rel.get("b"), entities, rel["id"], "entity")
        for ident in rel.get("evidence") or []:
            req(ident, stories, rel["id"], "story")
    for line in corpus.storylines:
        for ident in line.get("entities") or []:
            req(ident, entities, line["id"], "entity")
        for ident in line.get("stories") or []:
            req(ident, stories, line["id"], "story")
    return errors

def validate(corpus, packet, edition, gone, owned, wikipedia, prior_entities=None):
    errors = []
    unknown(packet, PACKET_KEYS, "packet", errors)
    if packet.get("edition") != edition:
        errors.append(f"edition must be {edition}")
    lists = {key: as_objects(packet, key, errors) for key in LIST_KEYS}
    if not any(lists.values()):
        errors.append("packet has nothing to apply")
    known_entities = set(corpus.entity) | {e["id"] for e in lists["entities"]}
    known_lines = (set(corpus.line) - gone["storylines"]) | {s["id"] for s in lists["storylines"]}
    known_zones = (set(corpus.zone) - gone["zones"]) | {z["id"] for z in lists["zones"]}
    known_stories = (set(corpus.story) - gone["stories"]) | {s["id"] for s in lists["stories"]}
    wiki_urls = []

    for item in lists["entities"]:
        path = f"entities.{item['id']}"
        unknown(item, PLACE_KEYS if item.get("type") == "place" else ENTITY_KEYS, path, errors)
        need_str(item, "name", path, errors)
        if item.get("type") not in ENTITY_TYPES:
            errors.append(f"{path}.type must be a known entity type")
        have = corpus.entity.get(item["id"])
        if item.get("type") == "place" and (have is None or any(k in item for k in ("lat", "lon", "precision"))):
            check_coords(item, path, errors)
        if check_url(item.get("wikipedia"), f"{path}.wikipedia", errors, wikipedia=True):
            if have and item["id"] not in owned:
                moved = any(k in item and have.get(k) != item.get(k) for k in ("lat", "lon", "precision"))
                if same_entity(have, item):
                    errors.append(f"{path} already exists; omit it")
                elif moved:
                    errors.append(f"{path} coordinates can only change through place_corrections")
                else:
                    errors.append(f"{path} already exists and cannot be changed by a later edition")
            elif have and item["id"] in owned:
                if have.get("wikipedia") != item.get("wikipedia"):
                    wiki_urls.append(item["wikipedia"])
            elif have is None:
                wiki_urls.append(item["wikipedia"])

    for item in lists["storylines"]:
        path = f"storylines.{item['id']}"
        unknown(item, LINE_KEYS, path, errors)
        need_str(item, "name", path, errors)
        have = corpus.line.get(item["id"]) if item["id"] not in gone["storylines"] else None
        if have and have.get("name") != item.get("name"):
            errors.append(f"{path} already exists with a different name")
        check_id_list(item.get("entities", []), f"{path}.entities", known_entities, errors, "entity")
        check_id_list(item.get("stories", []), f"{path}.stories", known_stories, errors, "story")

    for item in lists["zones"]:
        path = f"zones.{item['id']}"
        unknown(item, ZONE_KEYS, path, errors)
        new = item["id"] not in corpus.zone or item["id"] in gone["zones"]
        if new:
            for key in ("name", "note"):
                need_str(item, key, path, errors)
            if not is_num(item.get("lat")) or not -90 <= item.get("lat", 999) <= 90:
                errors.append(f"{path}.lat must be a latitude")
            if not is_num(item.get("lon")) or not -180 <= item.get("lon", 999) <= 180:
                errors.append(f"{path}.lon must be a longitude")
            if item.get("severity") not in SEVERITY:
                errors.append(f"{path}.severity must be critical, high, elevated, or watch")
            if not item.get("entities"):
                errors.append(f"{path}.entities must name at least one entity")
        else:
            present = [k for k in ("name", "lat", "lon", "severity", "note", "entities", "stories", "label_dx", "label_dy") if k in item]
            if not present:
                errors.append(f"{path} does not change the zone")
            if "severity" in item and item["severity"] not in SEVERITY:
                errors.append(f"{path}.severity must be critical, high, elevated, or watch")
            if "lat" in item and (not is_num(item["lat"]) or not -90 <= item["lat"] <= 90):
                errors.append(f"{path}.lat must be a latitude")
            if "lon" in item and (not is_num(item["lon"]) or not -180 <= item["lon"] <= 180):
                errors.append(f"{path}.lon must be a longitude")
            if "name" in item:
                need_str(item, "name", path, errors)
            if "note" in item:
                need_str(item, "note", path, errors)
        for key in ("label_dx", "label_dy"):
            if key in item and not is_num(item[key]):
                errors.append(f"{path}.{key} must be a number")
        check_id_list(item.get("entities"), f"{path}.entities", known_entities, errors, "entity")
        check_id_list(item.get("stories"), f"{path}.stories", known_stories, errors, "story")

    for item in lists["links"]:
        path = f"links.{item['id']}"
        unknown(item, LINK_KEYS, path, errors)
        expect = f"{item.get('from')}--{item.get('to')}"
        if item["id"] != expect:
            errors.append(f"{path} id must be {expect}")
        if item.get("from") not in known_zones or item.get("to") not in known_zones:
            errors.append(f"{path} from and to must be hot zones")
        new = item["id"] not in corpus.link or item["id"] in gone["links"]
        if new:
            need_str(item, "label", path, errors)
            if not item.get("entities"):
                errors.append(f"{path}.entities must name at least one entity")
        elif not any(k in item for k in ("label", "entities", "stories")):
            errors.append(f"{path} does not change the link")
        check_id_list(item.get("entities"), f"{path}.entities", known_entities, errors, "entity")
        check_id_list(item.get("stories"), f"{path}.stories", known_stories, errors, "story")

    for item in lists["relationships"]:
        path = f"relationships.{item['id']}"
        unknown(item, REL_KEYS, path, errors)
        if item.get("type") not in REL_TYPES:
            errors.append(f"{path}.type must be a known relationship type")
        expect = f"{item.get('a')}--{item.get('type')}--{item.get('b')}"
        if item.get("a") not in known_entities or item.get("b") not in known_entities:
            errors.append(f"{path} a and b must be entities")
        elif item["id"] != expect:
            errors.append(f"{path} id must be {expect}")
        new = item["id"] not in corpus.rel or item["id"] in gone["relationships"]
        if new:
            for key in ("stated", "actual"):
                need_str(item, key, path, errors)
            if item.get("confidence") not in CONFIDENCE:
                errors.append(f"{path}.confidence must be likely, possible, or speculative")
            if precision_of(item.get("start")) is None:
                errors.append(f"{path}.start must be a date")
            if "end" in item and item["end"] is not None and precision_of(item["end"]) is None:
                errors.append(f"{path}.end must be a date or null")
            if not item.get("evidence"):
                errors.append(f"{path}.evidence must cite at least one story")
        else:
            have = corpus.rel[item["id"]]
            if (item.get("a"), item.get("b"), item.get("type")) != (have.get("a"), have.get("b"), have.get("type")):
                errors.append(f"{path} cannot change a, b, or type")
            if not any(k in item for k in ("start", "end", "stated", "actual", "confidence", "evidence")):
                errors.append(f"{path} does not change the relationship")
        check_id_list(item.get("evidence"), f"{path}.evidence", known_stories, errors, "story")

    story_ids = {s["id"] for s in lists["stories"]}
    for item in lists["stories"]:
        path = f"stories.{item['id']}"
        unknown(item, STORY_KEYS, path, errors)
        if item["id"] in corpus.story and item["id"] not in gone["stories"]:
            errors.append(f"{path} already exists; change it with corrections")
        if item.get("edition") not in (None, edition):
            errors.append(f"{path}.edition must be {edition}")
        prec = precision_of(item.get("date"))
        if prec is None:
            errors.append(f"{path}.date must be YYYY, YYYY-MM, or YYYY-MM-DD")
        elif item.get("date_precision", prec) != prec:
            errors.append(f"{path}.date_precision does not match date")
        elif after_edition(item["date"], prec, edition):
            errors.append(f"{path}.date is after the edition")
        if item.get("region") not in REGIONS:
            errors.append(f"{path}.region must be a known region")
        if item.get("kind", "event") not in KINDS:
            errors.append(f"{path}.kind must be a known kind")
        need_str(item, "title", path, errors)
        need_str(item, "summary", path, errors)
        check_analysis(item.get("analysis"), path, errors)
        check_sources(item.get("sources"), path, errors)
        if not item.get("entities"):
            errors.append(f"{path}.entities must name at least one entity")
        check_id_list(item.get("entities"), f"{path}.entities", known_entities, errors, "entity")
        check_id_list(item.get("storylines"), f"{path}.storylines", known_lines, errors, "storyline")
        causes = item.get("causes", [])
        if any(isinstance(c, dict) and c.get("story") == item["id"] for c in causes or []):
            errors.append(f"{path} cannot cause itself")
        check_causes(causes, path, known_stories - {item["id"]}, errors)
        check_marker(item, path, errors, required=True)
        check_location(item, path, errors, placed_ids(corpus, lists, prior_entities), known_entities, required=True)

    for item in lists["corrections"]:
        path = f"corrections.{item['id']}"
        unknown(item, {"id", "why", *CORRECTION_FIELDS}, path, errors)
        need_str(item, "why", path, errors)
        if item["id"] in story_ids or item["id"] in gone["stories"]:
            errors.append(f"{path} is owned by this edition; put the full story in stories")
            continue
        have = corpus.story.get(item["id"])
        if have is None:
            errors.append(f"{path} is not an existing story")
            continue
        if not any(k in item for k in CORRECTION_FIELDS):
            errors.append(f"{path} does not change the story")
        if "region" in item and item["region"] not in REGIONS:
            errors.append(f"{path}.region must be a known region")
        if "kind" in item and item["kind"] not in KINDS:
            errors.append(f"{path}.kind must be a known kind")
        if "date" in item:
            prec = precision_of(item["date"])
            want = item.get("date_precision", prec)
            if prec is None or want != prec:
                errors.append(f"{path}.date must match date_precision")
            elif after_edition(item["date"], prec, edition):
                errors.append(f"{path}.date is after the edition")
        check_analysis(item.get("analysis"), path, errors) if "analysis" in item else None
        if "sources" in item:
            check_sources(item.get("sources"), path, errors)
        check_id_list(item.get("entities"), f"{path}.entities", known_entities, errors, "entity")
        check_id_list(item.get("storylines"), f"{path}.storylines", known_lines, errors, "storyline")
        check_marker(item, path, errors, required=False)
        check_location(item, path, errors, placed_ids(corpus, lists, prior_entities), known_entities, required=False)
        if "causes" in item:
            if any(isinstance(c, dict) and c.get("story") == item["id"] for c in item.get("causes") or []):
                errors.append(f"{path} cannot cause itself")
            check_causes(item.get("causes"), path, known_stories - {item["id"]}, errors)
        changed = any(have.get(k) != item.get(k) for k in CORRECTION_FIELDS if k in item)
        if "where" in item and have.get("unplaced") and "unplaced" not in item:
            changed = True
        if "unplaced" in item and have.get("where") and "where" not in item:
            changed = True
        if not changed:
            errors.append(f"{path} matches the story already on file")

    declared = {e["id"] for e in lists["entities"]}
    for item in lists["place_corrections"]:
        path = f"place_corrections.{item['id']}"
        unknown(item, PLACE_CORRECTION_KEYS, path, errors)
        need_str(item, "why", path, errors)
        if item["id"] in declared or item["id"] in owned:
            errors.append(f"{path} is declared in this packet; put the coordinates on the entity")
            continue
        have = corpus.entity.get(item["id"])
        if have is None or have.get("type") != "place":
            errors.append(f"{path} is not an existing place")
            continue
        base = prior_entities.get(item["id"]) if prior_entities and prior_entities.get(item["id"]) else have
        if not check_coords(item, path, errors):
            continue
        if (base.get("lat"), base.get("lon"), base.get("precision")) == (item.get("lat"), item.get("lon"), item.get("precision")):
            errors.append(f"{path} does not change the place")

    latest = max(corpus.ledger.get("packets") or {"": {}})
    if latest and edition < latest and (lists["zones"] or lists["links"]):
        errors.append(f"hot zone snapshot is owned by edition {latest}")
    if not errors:
        for url in dict.fromkeys(wiki_urls):
            message = wikipedia(url)
            if message:
                errors.append(message)
    return errors, lists

def apply_changes(corpus, lists, edition, owned, counts):
    undo = Undo()
    known_before = set(corpus.entity)
    for item in lists["entities"]:
        have = corpus.entity.get(item["id"])
        if have and item["id"] in owned:
            updates = {k: item[k] for k in ("name", "type", "wikipedia")}
            if item.get("type") == "place":
                for key in ("lat", "lon", "precision"):
                    if key in item:
                        updates[key] = item[key]
            if any(have.get(k) != v for k, v in updates.items()):
                if any(have.get(k) != updates.get(k) for k in ("lat", "lon", "precision") if k in updates):
                    remember(undo.entities, item["id"], have)
                have.update(updates)
                counts["entity"] += 1
                corpus.dirty.add("entities")
        elif have is None:
            stored = {k: item[k] for k in ("id", "name", "type", "wikipedia")}
            if item.get("type") == "place":
                stored.update({k: item[k] for k in ("lat", "lon", "precision")})
            corpus.entities.append(stored)
            counts["entity"] += 1
            corpus.dirty.add("entities")
            corpus.reindex()
    undo.entities_added = sorted(set(owned) | ({e["id"] for e in lists["entities"]} - known_before))

    for item in lists["storylines"]:
        have = corpus.line.get(item["id"])
        if have is None:
            remember(undo.storylines, item["id"], None)
            corpus.storylines.append({
                "id": item["id"], "name": item["name"],
                "entities": list(item.get("entities") or []),
                "stories": list(item.get("stories") or []),
                "source": item.get("source") or "inbox",
            })
            counts["storyline"] += 1
            corpus.dirty.add("storylines")
            corpus.reindex()
        else:
            before = copy.deepcopy(have)
            have["entities"] = union(have.get("entities"), item.get("entities") or [])
            have["stories"] = union(have.get("stories"), item.get("stories") or [])
            if have != before:
                undo.storylines[item["id"]] = before
                counts["storyline"] += 1
                corpus.dirty.add("storylines")

    zone_changed = False
    for item in lists["zones"]:
        have = corpus.zone.get(item["id"])
        if have is None:
            remember(undo.zones, item["id"], None)
            zone = {k: item[k] for k in ("id", "name", "lat", "lon", "severity", "note")}
            zone["entities"] = list(item.get("entities") or [])
            zone["stories"] = list(item.get("stories") or [])
            for key in ("label_dx", "label_dy"):
                if key in item:
                    zone[key] = item[key]
            corpus.hotzones["zones"].append(zone)
            zone_changed = True
            corpus.reindex()
        else:
            before = copy.deepcopy(have)
            for key in ("name", "lat", "lon", "severity", "note", "label_dx", "label_dy"):
                if key in item:
                    have[key] = item[key]
            if "entities" in item:
                have["entities"] = union(have.get("entities"), item["entities"])
            if "stories" in item:
                have["stories"] = union(have.get("stories"), item["stories"])
            if have != before:
                undo.zones[item["id"]] = before
                zone_changed = True
        if zone_changed:
            counts["zone"] = counts.get("zone", 0) + 1
            corpus.dirty.add("hotzones")
            zone_changed = False

    link_changed = False
    for item in lists["links"]:
        have = corpus.link.get(item["id"])
        if have is None:
            remember(undo.links, item["id"], None)
            link = {k: item[k] for k in ("id", "from", "to", "label")}
            link["entities"] = list(item.get("entities") or [])
            link["stories"] = list(item.get("stories") or [])
            corpus.hotzones.setdefault("links", []).append(link)
            link_changed = True
            corpus.reindex()
        else:
            before = copy.deepcopy(have)
            if "label" in item:
                have["label"] = item["label"]
            if "entities" in item:
                have["entities"] = union(have.get("entities"), item["entities"])
            if "stories" in item:
                have["stories"] = union(have.get("stories"), item["stories"])
            if have != before:
                undo.links[item["id"]] = before
                link_changed = True
        if link_changed:
            counts["link"] = counts.get("link", 0) + 1
            corpus.dirty.add("hotzones")
            link_changed = False

    for item in lists["relationships"]:
        have = corpus.rel.get(item["id"])
        if have is None:
            remember(undo.relationships, item["id"], None)
            rel = {k: item.get(k) for k in ("id", "a", "b", "type", "start", "end", "stated", "actual", "confidence")}
            rel["end"] = item["end"] if "end" in item else None
            rel["evidence"] = list(item.get("evidence") or [])
            corpus.relationships.append(rel)
            counts["relationship"] += 1
            corpus.dirty.add("relationships")
            corpus.reindex()
        else:
            before = copy.deepcopy(have)
            for key in ("start", "end", "stated", "actual", "confidence"):
                if key in item:
                    have[key] = item[key]
            if "evidence" in item:
                have["evidence"] = union(have.get("evidence"), item["evidence"])
            if have != before:
                undo.relationships[item["id"]] = before
                counts["relationship"] += 1
                corpus.dirty.add("relationships")

    touched = []
    for item in lists["stories"]:
        prec = item.get("date_precision") or precision_of(item["date"])
        remember(undo.stories, item["id"], corpus.story.get(item["id"]))
        stored = {
            "id": item["id"], "date": item["date"], "date_precision": prec,
            "kind": item.get("kind") or "event", "edition": edition,
            "region": item["region"], "title": item["title"], "summary": item["summary"],
            "sources": copy.deepcopy(item["sources"]), "entities": list(item["entities"]),
            "causes": copy.deepcopy(item.get("causes") or []), "effects": [],
            "batch": f"inbox-{edition}",
        }
        if item.get("analysis"):
            stored["analysis"] = copy.deepcopy(item["analysis"])
        if item.get("storylines"):
            stored["storylines"] = list(item["storylines"])
        if item.get("era"):
            stored["era"] = item["era"]
        stored["marker"] = item["marker"]
        if item.get("where"):
            stored["where"] = list(item["where"])
        if item.get("unplaced"):
            stored["unplaced"] = item["unplaced"]
        corpus.stories.append(stored)
        touched.append(item["id"])
        counts["story"] += 1
        corpus.dirty.add("stories")
        corpus.reindex()

    for item in lists["corrections"]:
        story = corpus.story[item["id"]]
        remember(undo.stories, item["id"], story)
        changed = []
        for key in CORRECTION_FIELDS:
            if key in item and story.get(key) != item.get(key):
                story[key] = copy.deepcopy(item[key])
                changed.append(key)
        if "date" in item and "date_precision" not in item:
            story["date_precision"] = precision_of(item["date"])
        if "where" in item and story.get("unplaced"):
            story.pop("unplaced", None)
            changed.append("unplaced")
        if "unplaced" in item and story.get("where"):
            story.pop("where", None)
            changed.append("where")
        story.setdefault("revisions", []).append({"edition": edition, "why": item["why"], "fields": changed})
        touched.append(item["id"])
        counts["correction"] += 1
        corpus.dirty.add("stories")

    if counts.get("zone") or counts.get("link"):
        if not undo.date_saved:
            undo.hotzones_date = corpus.hotzones.get("date")
            undo.date_saved = True
        current = corpus.hotzones.get("date") or ""
        if edition >= current:
            corpus.hotzones["date"] = edition
            corpus.dirty.add("hotzones")

    for item in lists["place_corrections"]:
        have = corpus.entity[item["id"]]
        remember(undo.entities, item["id"], have)
        have["lat"] = item["lat"]
        have["lon"] = item["lon"]
        have["precision"] = item["precision"]
        have.setdefault("location_revisions", []).append({
            "edition": edition, "why": item["why"],
            "lat": item["lat"], "lon": item["lon"], "precision": item["precision"],
        })
        counts["place"] += 1
        corpus.dirty.add("entities")

    recompute_related(corpus, undo, touched)
    corpus.reindex()
    return undo

def format_counts(counts):
    parts = []
    for key, label in (
        ("story", "story"), ("correction", "correction"), ("entity", "entity"),
        ("place", "place correction"),
        ("zone", "zone"), ("link", "link"), ("relationship", "relationship"),
        ("storyline", "storyline"),
    ):
        n = counts.get(key, 0)
        if n:
            parts.append(f"{n} {label}" + ("" if n == 1 else "s"))
    return ", ".join(parts)

def merge_packet(corpus, path, wikipedia):
    edition = path.stem
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", edition) or precision_of(edition) != "day":
        raise PacketError([f"{path.name}: file name must be a real YYYY-MM-DD date"])
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PacketError([f"{path.name}: {exc}"])
    if not isinstance(packet, dict):
        raise PacketError([f"{path.name}: packet must be a JSON object"])
    digest = sha256(path)
    previous = (corpus.ledger.get("packets") or {}).get(edition)
    replacing = previous is not None
    if replacing and previous.get("sha256") == digest:
        return f"unchanged {edition}"
    packets = corpus.ledger.get("packets") or {}
    latest = max(packets) if packets else ""
    if replacing and edition != latest:
        raise PacketError([f"{path.name}: only the latest edition ({latest}) can be republished"])
    gone = {"stories": set(), "zones": set(), "links": set(), "relationships": set(), "storylines": set()}
    owned = set()
    if replacing:
        old = Undo.from_json(previous.get("undo"))
        owned = set(old.entities_added)
        for name in gone:
            gone[name] = {i for i, before in getattr(old, name).items() if before is None}
        new_story_ids = {s.get("id") for s in packet.get("stories") or [] if isinstance(s, dict)}
        blocked = sorted((gone["stories"] - new_story_ids) & path_ids(corpus.paths))
        if blocked:
            raise PacketError([f"{path.name}: {', '.join(blocked)} is on a published path and must stay in the packet"])
    prior_entities = Undo.from_json(previous.get("undo")).entities if replacing else {}
    errors, lists = validate(corpus, packet, edition, gone, owned, wikipedia, prior_entities)
    if errors:
        raise PacketError([f"{path.name}: {err}" for err in errors])
    if replacing:
        restore(corpus, Undo.from_json(previous.get("undo")))
    counts = Counter()
    undo = apply_changes(corpus, lists, edition, owned, counts)
    if not any(counts.values()) and not replacing:
        # Restating the current corpus is a successful ingest. Record the bytes
        # so a later edit of this edition is a republish, and do not write the
        # other data files. Raising here leaves the file on main and blocks Pages.
        corpus.dirty.clear()
        corpus.ledger.setdefault("packets", {})[edition] = {"sha256": digest, "undo": undo.to_json()}
        corpus.dirty.add("ledger")
        return f"applied {edition}: no change"
    broken = integrity(corpus)
    if broken:
        raise PacketError([f"{path.name}: {err}" for err in broken])
    corpus.ledger.setdefault("packets", {})[edition] = {"sha256": digest, "undo": undo.to_json()}
    corpus.dirty.add("ledger")
    return f"applied {edition}: {format_counts(counts) or 'republished'}"

def apply_all(root, paths=None, wikipedia=None, dry_run=False):
    root = Path(root)
    wiki = default_wikipedia if wikipedia is None else wikipedia
    corpus = Corpus(root)
    if paths is None:
        chosen = sorted((root / "inbox").glob("*.json"))
    else:
        chosen = [Path(p) for p in paths]
    notes = []
    for path in chosen:
        note = merge_packet(corpus, path, wiki)
        if dry_run:
            notes.append("dry-run " + note)
            continue
        if note.startswith("applied") and corpus.dirty:
            corpus.save()
        notes.append(note)
    if dry_run:
        # Discard the in-memory merge. Disk was not written.
        return notes
    return notes

def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply inbox/YYYY-MM-DD.json packets onto data/.")
    parser.add_argument("packets", nargs="*", help="packet files; default is every inbox/*.json")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-wikipedia", action="store_true")
    args = parser.parse_args(argv)
    wiki = (lambda url: None) if args.skip_wikipedia else None
    try:
        notes = apply_all(args.root, paths=args.packets or None, wikipedia=wiki, dry_run=args.dry_run)
    except PacketError as exc:
        print(exc, file=sys.stderr)
        return 1
    for note in notes:
        print(note)
    if not notes:
        print("no packets")
    return 0

if __name__ == "__main__":
    sys.exit(main())
