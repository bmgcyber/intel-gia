import hashlib, json, shutil, sys, tempfile, unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apply_packet import PacketError, apply_all

EXAMPLE = ROOT / "docs" / "examples" / "1941-12-07-pearl-harbor.json"

def dump(path, obj):
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def hashes(root):
    out = {}
    for path in sorted((root / "data").glob("*.json")):
        out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out

def fixture():
    tmp = Path(tempfile.mkdtemp())
    root = tmp / "gia"
    data, inbox = root / "data", root / "inbox"
    data.mkdir(parents=True)
    inbox.mkdir()
    dump(data / "entities.json", [
        {"id": "japan", "name": "Japan", "type": "country", "wikipedia": "https://en.wikipedia.org/wiki/Japan"},
        {"id": "united-states", "name": "United States", "type": "country", "wikipedia": "https://en.wikipedia.org/wiki/United_States"},
    ])
    dump(data / "stories.json", [{
        "id": "1941-11-26-hull-note", "date": "1941-11-26", "date_precision": "day",
        "kind": "event", "edition": "1941-11-26", "region": "Asia-Pacific",
        "title": "Hull note delivered", "summary": "The United States delivered a note to Japan.",
        "sources": [{"name": "Example", "url": "https://example.com/hull"}],
        "entities": ["japan", "united-states"], "causes": [], "effects": [],
    }])
    dump(data / "storylines.json", [{
        "id": "pacific-war", "name": "Pacific war", "entities": ["japan", "united-states"],
        "stories": ["1941-11-26-hull-note"], "source": "fixture",
    }])
    dump(data / "hotzones.json", {"date": "1941-11-26", "zones": [{
        "id": "japan-home", "name": "Japan", "lat": 36.2, "lon": 138.2, "severity": "watch",
        "note": "Negotiations", "entities": ["japan"], "stories": ["1941-11-26-hull-note"],
    }], "links": []})
    dump(data / "relationships.json", [])
    dump(data / "paths.json", {})
    dump(data / "ledger.json", {"packets": {}})
    return root

def drop(root, edition, packet):
    path = root / "inbox" / f"{edition}.json"
    dump(path, packet)
    return path

def wiki_ok(_url):
    return None

def shock(summary="Japanese aircraft attacked the US Pacific Fleet at Pearl Harbor.", severity="critical", name="Pearl Harbor"):
    return {
        "edition": "1941-12-07",
        "entities": [{
            "id": "pearl-harbor", "name": name, "type": "place",
            "wikipedia": "https://en.wikipedia.org/wiki/Pearl_Harbor",
            "lat": 21.3679, "lon": -157.9771, "precision": "feature",
        }],
        "zones": [{
            "id": "hawaii", "name": "Hawaii", "lat": 21.36, "lon": -157.95, "severity": severity,
            "note": "Pacific Fleet attacked", "entities": ["pearl-harbor", "united-states", "japan"],
        }],
        "stories": [{
            "id": "1941-12-07-pearl-harbor", "date": "1941-12-07", "region": "Asia-Pacific",
            "title": "Japan attacks Pearl Harbor", "summary": summary,
            "sources": [{"name": "Example", "url": "https://example.com/pearl"}],
            "entities": ["japan", "united-states", "pearl-harbor"],
            "where": ["pearl-harbor"], "marker": "strike",
            "causes": [{"story": "1941-11-26-hull-note", "why": "Diplomacy had already failed.", "confidence": "likely"}],
        }],
    }

class ApplyTests(unittest.TestCase):
    def test_rejects_undeclared_entity(self):
        root = fixture()
        packet = shock()
        del packet["entities"]
        drop(root, "1941-12-07", packet)
        before = hashes(root)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("pearl-harbor", str(caught.exception))
        self.assertEqual(before, hashes(root))

    def test_shock_day_declares_entity_zone_and_story(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertIn("1 story", notes[0])
        self.assertIn("1 entity", notes[0])
        stories = read(root / "data" / "stories.json")
        pearl = next(s for s in stories if s["id"] == "1941-12-07-pearl-harbor")
        self.assertEqual(pearl["edition"], "1941-12-07")
        self.assertEqual(pearl["summary"], shock()["stories"][0]["summary"])
        self.assertIn("1941-11-26-hull-note", [c["story"] for c in pearl["causes"]])
        entities = read(root / "data" / "entities.json")
        self.assertIn("pearl-harbor", [e["id"] for e in entities])
        zones = read(root / "data" / "hotzones.json")
        self.assertEqual(zones["date"], "1941-12-07")
        self.assertEqual(next(z for z in zones["zones"] if z["id"] == "hawaii")["severity"], "critical")
        hull = next(s for s in stories if s["id"] == "1941-11-26-hull-note")
        self.assertIn("1941-12-07-pearl-harbor", hull["related_stories"])

    def test_wikipedia_failure_writes_nothing(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        before = hashes(root)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=lambda url: f"HTTP 404 for {url}")
        self.assertIn("404", str(caught.exception))
        self.assertEqual(before, hashes(root))

    def test_same_bytes_skip_wikipedia(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        calls = []
        def wiki(url):
            calls.append(url)
            return None
        apply_all(root, wikipedia=wiki)
        self.assertEqual(len(calls), 1)
        calls.clear()
        notes = apply_all(root, wikipedia=wiki)
        self.assertTrue(notes[0].startswith("unchanged"))
        self.assertEqual(calls, [])

    def test_republish_replaces_story_zone_and_owned_entity(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-07", shock(summary="The attack sank battleships at Pearl Harbor.", severity="high", name="Pearl Harbour"))
        apply_all(root, wikipedia=wiki_ok)
        stories = [s for s in read(root / "data" / "stories.json") if s["id"] == "1941-12-07-pearl-harbor"]
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["summary"], "The attack sank battleships at Pearl Harbor.")
        zones = read(root / "data" / "hotzones.json")
        self.assertEqual(next(z for z in zones["zones"] if z["id"] == "hawaii")["severity"], "high")
        entity = next(e for e in read(root / "data" / "entities.json") if e["id"] == "pearl-harbor")
        self.assertEqual(entity["name"], "Pearl Harbour")

    def test_republish_blocked_after_a_later_edition(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-08", {
            "edition": "1941-12-08",
            "stories": [{
                "id": "1941-12-08-declaration", "date": "1941-12-08", "region": "Asia-Pacific",
                "title": "The United States declares war", "summary": "Congress declared war on Japan.",
                "sources": [{"name": "Example", "url": "https://example.com/war"}],
                "entities": ["united-states", "japan"],
                "marker": "political", "unplaced": "Congress declared war in Washington, and the record names no single building.",
                "causes": [{"story": "1941-12-07-pearl-harbor", "why": "The attack was the immediate cause.", "confidence": "likely"}],
            }],
        })
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-07", shock(summary="A retracted summary."))
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("latest edition", str(caught.exception))
        pearl = next(s for s in read(root / "data" / "stories.json") if s["id"] == "1941-12-07-pearl-harbor")
        self.assertNotIn("retracted", pearl["summary"])

    def test_older_packet_cannot_move_the_snapshot(self):
        root = fixture()
        drop(root, "1941-12-08", {
            "edition": "1941-12-08",
            "zones": [{"id": "japan-home", "severity": "critical", "note": "At war"}],
            "stories": [{
                "id": "1941-12-08-declaration", "date": "1941-12-08", "region": "Asia-Pacific",
                "title": "The United States declares war", "summary": "Congress declared war on Japan.",
                "sources": [{"name": "Example", "url": "https://example.com/war"}],
                "entities": ["japan", "united-states"],
                "marker": "political", "unplaced": "Congress declared war in Washington, and the record names no single building.",
            }],
        })
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-07", {"edition": "1941-12-07", "zones": [{"id": "japan-home", "severity": "watch", "note": "Backdated"}]})
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("hot zone snapshot", str(caught.exception))
        zones = read(root / "data" / "hotzones.json")
        self.assertEqual(next(z for z in zones["zones"] if z["id"] == "japan-home")["severity"], "critical")
        packet = shock()
        del packet["zones"]
        drop(root, "1941-12-07", packet)
        apply_all(root, wikipedia=wiki_ok)
        zones = read(root / "data" / "hotzones.json")
        self.assertEqual(zones["date"], "1941-12-08")
        self.assertEqual(next(z for z in zones["zones"] if z["id"] == "japan-home")["severity"], "critical")
        self.assertTrue(any(s["id"] == "1941-12-07-pearl-harbor" for s in read(root / "data" / "stories.json")))

    def test_correction_keeps_original_edition(self):
        root = fixture()
        drop(root, "1941-12-07", {
            "edition": "1941-12-07",
            "corrections": [{
                "id": "1941-11-26-hull-note", "why": "The note's wording was confirmed.",
                "summary": "The United States delivered the Hull note to Japan.",
            }],
        })
        apply_all(root, wikipedia=wiki_ok)
        story = read(root / "data" / "stories.json")[0]
        self.assertEqual(story["edition"], "1941-11-26")
        self.assertEqual(story["summary"], "The United States delivered the Hull note to Japan.")
        self.assertEqual(story["revisions"][0]["edition"], "1941-12-07")
        self.assertIn("wording", story["revisions"][0]["why"])

    def test_old_story_must_use_corrections(self):
        root = fixture()
        packet = shock()
        packet["stories"].append({
            "id": "1941-11-26-hull-note", "date": "1941-11-26", "region": "Asia-Pacific",
            "title": "Rewritten", "summary": "Rewritten without a correction.",
            "sources": [{"name": "Example", "url": "https://example.com/hull"}],
            "entities": ["japan"],
        })
        drop(root, "1941-12-07", packet)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("corrections", str(caught.exception))

    def test_relationship_id_and_a_valid_one(self):
        root = fixture()
        packet = shock()
        packet["relationships"] = [{
            "id": "japan--rivalry--usa", "a": "japan", "b": "united-states", "type": "rivalry",
            "start": "1941", "end": None, "stated": "War", "actual": "Open war",
            "confidence": "likely", "evidence": ["1941-12-07-pearl-harbor"],
        }]
        drop(root, "1941-12-07", packet)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("japan--rivalry--united-states", str(caught.exception))
        packet["relationships"][0]["id"] = "japan--rivalry--united-states"
        drop(root, "1941-12-07", packet)
        apply_all(root, wikipedia=wiki_ok)
        rel = read(root / "data" / "relationships.json")[0]
        self.assertEqual(rel["evidence"], ["1941-12-07-pearl-harbor"])

    def test_several_errors_at_once(self):
        root = fixture()
        drop(root, "1941-12-07", {
            "edition": "1941-12-07", "comment": "nope",
            "stories": [{
                "id": "1941-12-07-bare", "date": "1941-12-07", "region": "Asia-Pacific",
                "title": "Bare", "summary": "A story with no source and a typo.",
                "entities": ["pearl-harbur"],
            }],
        })
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        text = str(caught.exception)
        self.assertIn("unknown field comment", text)
        self.assertIn("sources", text)
        self.assertIn("pearl-harbur", text)

    def test_filename_must_be_a_real_date_and_match(self):
        root = fixture()
        path = root / "inbox" / "2026-02-31.json"
        dump(path, {"edition": "2026-02-31"})
        with self.assertRaises(PacketError):
            apply_all(root, wikipedia=wiki_ok)
        path.unlink()
        drop(root, "1941-12-07", {"edition": "1941-12-08", "stories": []})
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("edition must be 1941-12-07", str(caught.exception))

    def test_dry_run_does_not_write(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        before = hashes(root)
        notes = apply_all(root, wikipedia=wiki_ok, dry_run=True)
        self.assertTrue(notes[0].startswith("dry-run applied"))
        self.assertEqual(before, hashes(root))

    def test_example_packet_applies(self):
        root = fixture()
        shutil.copy(EXAMPLE, root / "inbox" / "1941-12-07.json")
        apply_all(root, wikipedia=wiki_ok)
        ids = [e["id"] for e in read(root / "data" / "entities.json")]
        self.assertIn("pearl-harbor", ids)

    def test_identical_zone_packet_is_recorded_and_skipped_next_time(self):
        root = fixture()
        drop(root, "1941-12-07", {
            "edition": "1941-12-07",
            "zones": [{
                "id": "japan-home", "name": "Japan", "lat": 36.2, "lon": 138.2,
                "severity": "watch", "note": "Negotiations",
                "entities": ["japan"], "stories": ["1941-11-26-hull-note"],
            }],
        })
        before = hashes(root)
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertEqual(notes, ["applied 1941-12-07: no change"])
        after = hashes(root)
        self.assertEqual({k: v for k, v in after.items() if k != "ledger.json"},
                         {k: v for k, v in before.items() if k != "ledger.json"})
        self.assertIn("1941-12-07", read(root / "data" / "ledger.json")["packets"])
        again = apply_all(root, wikipedia=wiki_ok)
        self.assertEqual(again, ["unchanged 1941-12-07"])
        self.assertEqual(hashes(root), after)

    def test_real_corpus_empty_inbox_is_noop(self):
        tmp = Path(tempfile.mkdtemp())
        root = tmp / "gia"
        shutil.copytree(ROOT / "data", root / "data")
        (root / "inbox").mkdir()
        before = hashes(root)
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertEqual(notes, [])
        self.assertEqual(before, hashes(root))

    def test_story_applies_onto_real_corpus_copy(self):
        tmp = Path(tempfile.mkdtemp())
        root = tmp / "gia"
        shutil.copytree(ROOT / "data", root / "data")
        (root / "inbox").mkdir()
        before_zones = read(root / "data" / "hotzones.json")["date"]
        before_summary = next(s["summary"] for s in read(root / "data" / "stories.json") if s["id"] == "gfs-pride-sunk")
        # The real corpus advances daily; a hard-coded 2026-10-16 became an (illegal) republish of an
        # older edition once 10-17 was applied. File the test packet as the day after the latest edition.
        latest = max(read(root / "data" / "ledger.json")["packets"])
        ed = (date.fromisoformat(latest) + timedelta(days=1)).isoformat()
        drop(root, ed, {
            "edition": ed,
            "stories": [{
                "id": "2026-10-16-apply-test", "date": ed, "region": "Middle East",
                "title": "Apply test", "summary": "This story exists only in a test copy.",
                "sources": [{"name": "Test", "url": "https://example.com/apply-test"}],
                "entities": ["iran", "united-states"],
                "marker": "political", "unplaced": "This test story names no place.",
                "causes": [{"story": "gfs-pride-sunk", "why": "Test link into the archive.", "confidence": "possible"}],
            }],
        })
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertIn("1 story", notes[0])
        stories = read(root / "data" / "stories.json")
        added = next(s for s in stories if s["id"] == "2026-10-16-apply-test")
        self.assertEqual(added["edition"], ed)
        self.assertEqual(added["batch"], f"inbox-{ed}")
        pride = next(s for s in stories if s["id"] == "gfs-pride-sunk")
        self.assertEqual(pride["summary"], before_summary)
        self.assertIn("2026-10-16-apply-test", pride.get("related_stories") or [])
        self.assertEqual(read(root / "data" / "hotzones.json")["date"], before_zones)

    def test_country_is_not_a_pin(self):
        root = fixture()
        packet = shock()
        packet["stories"][0]["where"] = ["japan"]
        drop(root, "1941-12-07", packet)
        before = hashes(root)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("not a placed location", str(caught.exception))
        self.assertEqual(before, hashes(root))

    def test_unknown_place_is_rejected(self):
        root = fixture()
        packet = shock()
        packet["stories"][0]["where"] = ["midway"]
        drop(root, "1941-12-07", packet)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("unknown place midway", str(caught.exception))

    def test_new_place_needs_coordinates(self):
        root = fixture()
        packet = shock()
        for key in ("lat", "lon", "precision"):
            del packet["entities"][0][key]
        drop(root, "1941-12-07", packet)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("lat must be a latitude", str(caught.exception))

    def test_where_and_unplaced_conflict(self):
        root = fixture()
        packet = shock()
        packet["stories"][0]["unplaced"] = "Somewhere in the Pacific."
        drop(root, "1941-12-07", packet)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("cannot set both where and unplaced", str(caught.exception))

    def test_conflicting_coordinate_needs_a_correction(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-08", {
            "edition": "1941-12-08",
            "entities": [{
                "id": "pearl-harbor", "name": "Pearl Harbor", "type": "place",
                "wikipedia": "https://en.wikipedia.org/wiki/Pearl_Harbor",
                "lat": 21.3, "lon": -157.9, "precision": "feature",
            }],
            "stories": [{
                "id": "1941-12-08-declaration", "date": "1941-12-08", "region": "Asia-Pacific",
                "title": "The United States declares war", "summary": "Congress declared war on Japan.",
                "sources": [{"name": "Example", "url": "https://example.com/war"}],
                "entities": ["japan", "united-states"],
                "marker": "political", "unplaced": "Congress declared war in Washington, and the record names no single building.",
            }],
        })
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("place_corrections", str(caught.exception))
        entity = next(e for e in read(root / "data" / "entities.json") if e["id"] == "pearl-harbor")
        self.assertEqual(entity["lat"], 21.3679)

    def test_place_correction_updates_and_republish_rolls_back(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-08", {
            "edition": "1941-12-08",
            "place_corrections": [{
                "id": "pearl-harbor", "lat": 21.35, "lon": -157.96, "precision": "feature",
                "why": "The pin marks the harbor basin.",
            }],
        })
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertIn("1 place correction", notes[-1])
        entity = next(e for e in read(root / "data" / "entities.json") if e["id"] == "pearl-harbor")
        self.assertEqual(entity["lat"], 21.35)
        self.assertEqual(entity["location_revisions"][0]["edition"], "1941-12-08")
        self.assertIn("harbor basin", entity["location_revisions"][0]["why"])
        drop(root, "1941-12-08", {
            "edition": "1941-12-08",
            "stories": [{
                "id": "1941-12-08-declaration", "date": "1941-12-08", "region": "Asia-Pacific",
                "title": "The United States declares war", "summary": "Congress declared war on Japan.",
                "sources": [{"name": "Example", "url": "https://example.com/war"}],
                "entities": ["japan", "united-states"],
                "marker": "political", "unplaced": "Congress declared war in Washington, and the record names no single building.",
            }],
        })
        apply_all(root, wikipedia=wiki_ok)
        entity = next(e for e in read(root / "data" / "entities.json") if e["id"] == "pearl-harbor")
        self.assertEqual(entity["lat"], 21.3679)
        self.assertNotIn("location_revisions", entity)

    def test_same_packet_place_correction_is_rejected(self):
        root = fixture()
        packet = shock()
        packet["place_corrections"] = [{
            "id": "pearl-harbor", "lat": 21.35, "lon": -157.96, "precision": "feature",
            "why": "Put these on the entity instead.",
        }]
        drop(root, "1941-12-07", packet)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("put the coordinates on the entity", str(caught.exception))

    def test_correction_can_place_a_story(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-08", {
            "edition": "1941-12-08",
            "corrections": [{
                "id": "1941-11-26-hull-note", "why": "The note was delivered in Washington, but the placed record we have is the harbor it led to.",
                "where": ["pearl-harbor"], "marker": "diplomacy",
            }],
        })
        apply_all(root, wikipedia=wiki_ok)
        hull = next(s for s in read(root / "data" / "stories.json") if s["id"] == "1941-11-26-hull-note")
        self.assertEqual(hull["where"], ["pearl-harbor"])
        self.assertEqual(hull["marker"], "diplomacy")
        self.assertNotIn("unplaced", hull)
        self.assertEqual(hull["edition"], "1941-11-26")
        drop(root, "1941-12-09", {
            "edition": "1941-12-09",
            "corrections": [{
                "id": "1941-12-07-pearl-harbor", "why": "The slide should say the pin is not a single building.",
                "unplaced": "The attack covered the harbor, not one building.",
                "marker": "strike",
            }],
        })
        apply_all(root, wikipedia=wiki_ok)
        pearl = next(s for s in read(root / "data" / "stories.json") if s["id"] == "1941-12-07-pearl-harbor")
        self.assertNotIn("where", pearl)
        self.assertEqual(pearl["unplaced"], "The attack covered the harbor, not one building.")

# ---- v7 optional sections: markets and calendar ----
def market(**over):
    item = {"asset": "brent", "label": "Brent crude (front month)", "as_of": "1941-12-06", "value": 74.12,
            "unit": "USD/bbl", "change": 1.8, "change_unit": "%", "basis": "settle",
            "source": {"name": "Example", "url": "https://example.com/brent"},
            "stories": ["1941-11-26-hull-note"]}
    item.update(over)
    return item

def event(**over):
    item = {"id": "1941-12-08-congress-session", "date": "1941-12-08", "time": "12:30", "tz": "America/New_York",
            "title": "Joint session of Congress", "kind": "other", "region": "Americas",
            "sources": [{"name": "Example", "url": "https://example.com/session"}], "storylines": ["pacific-war"],
            "stories": ["1941-11-26-hull-note"], "entities": ["united-states"]}
    item.update(over)
    return item

class MarketsCalendarTests(unittest.TestCase):
    def test_packet_without_sections_writes_no_new_files_or_ledger_keys(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        self.assertFalse((root / "data" / "markets.json").exists())
        self.assertFalse((root / "data" / "calendar.json").exists())
        undo = read(root / "data" / "ledger.json")["packets"]["1941-12-07"]["undo"]
        self.assertEqual(set(undo), {"stories", "zones", "links", "relationships", "storylines", "entities",
                                     "entities_added", "date_saved", "hotzones_date"})

    def test_sections_apply_into_new_files(self):
        root = fixture()
        packet = shock()
        packet["markets"] = [market(series=[["1941-12-04", 73.0], ["1941-12-05", 72.8], ["1941-12-06", 74.12]]),
                             market(asset="gold", label="Gold", value=35.0, unit="USD/ozt")]
        for key in ("change", "change_unit"):
            del packet["markets"][1][key]
        packet["calendar"] = [event()]
        drop(root, "1941-12-07", packet)
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertIn("2 market figures", notes[0])
        self.assertIn("1 calendar item", notes[0])
        figs = read(root / "data" / "markets.json")
        self.assertEqual([f["id"] for f in figs], ["brent--1941-12-06", "gold--1941-12-06"])
        self.assertEqual(figs[0]["edition"], "1941-12-07")
        self.assertEqual(figs[0]["source"]["url"], "https://example.com/brent")
        cal = read(root / "data" / "calendar.json")
        self.assertEqual(cal[0]["id"], "1941-12-08-congress-session")
        self.assertEqual(cal[0]["edition"], "1941-12-07")

    def test_sections_alone_are_a_valid_packet(self):
        root = fixture()
        drop(root, "1941-11-27", {"edition": "1941-11-27", "markets": [market(as_of="1941-11-26")]})
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertEqual(notes, ["applied 1941-11-27: 1 market figure"])

    def test_identical_figure_restated_later_is_a_noop_and_change_is_rejected(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), markets=[market()]))
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-08", {"edition": "1941-12-08", "markets": [market()]})
        self.assertEqual(apply_all(root, wikipedia=wiki_ok)[-1], "applied 1941-12-08: no change")
        drop(root, "1941-12-09", {"edition": "1941-12-09", "markets": [market(value=75.0)]})
        before = hashes(root)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("already recorded by edition 1941-12-07", str(caught.exception))
        self.assertEqual(before, hashes(root))

    def test_calendar_update_unions_and_marks_updated(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), calendar=[event()]))
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-08", {"edition": "1941-12-08",
                                  "calendar": [event(time="12:40", stories=["1941-12-07-pearl-harbor"])]})
        apply_all(root, wikipedia=wiki_ok)
        item = read(root / "data" / "calendar.json")[0]
        self.assertEqual(item["time"], "12:40")
        self.assertEqual(item["edition"], "1941-12-07")
        self.assertEqual(item["updated"], "1941-12-08")
        self.assertEqual(item["stories"], ["1941-11-26-hull-note", "1941-12-07-pearl-harbor"])

    def test_republish_rolls_sections_back(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), markets=[market()], calendar=[event()]))
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        self.assertEqual(read(root / "data" / "markets.json"), [])
        self.assertEqual(read(root / "data" / "calendar.json"), [])

    def test_invalid_sections_reject_whole_packet(self):
        bad = [
            ({"markets": {"asset": "brent"}}, "markets must be a list"),
            ({"markets": [market(value="74.12")]}, "value must be a number"),
            ({"markets": [market(value=float("nan"))]}, "value must be a number"),
            ({"markets": [dict((k, v) for k, v in market().items() if k != "source")]}, "source must be an object"),
            ({"markets": [market(source={"name": "x", "url": "ftp://x"})]}, "must be an http(s) URL"),
            ({"markets": [market(as_of="Dec 6")]}, "as_of must be YYYY-MM-DD or an ISO date-time"),
            ({"markets": [market(as_of="1941-12-06T16:30")]}, "as_of must be YYYY-MM-DD or an ISO date-time"),
            ({"markets": [market(as_of="1941-12-06T25:30-05:00")]}, "as_of must be YYYY-MM-DD or an ISO date-time"),
            ({"markets": [market(as_of="1941-12-08T09:30-05:00")]}, "as_of is after the edition"),
            ({"markets": [market(as_of="1941-12-08")]}, "as_of is after the edition"),
            ({"markets": [market(stories=["nope"])]}, "unknown story nope"),
            ({"markets": [market(), market()]}, "duplicate figure brent--1941-12-06"),
            ({"markets": [market(level="$74")]}, "unknown field level"),
            ({"markets": [market(change_unit="pct")]}, "change_unit must be one of"),
            ({"markets": [dict((k, v) for k, v in market().items() if k != "change_unit")]}, "change_unit must be one of"),
            ({"markets": [dict((k, v) for k, v in market().items() if k != "change")]}, "change_unit needs change"),
            ({"markets": [market(series=[["1941-12-06", 1], ["1941-12-05", 2]])]}, "strictly ascending"),
            ({"markets": [market(series=[["1941-12-07", 1]])]}, "is after as_of"),
            ({"markets": [market(series=[["Dec 5", "72"]])]}, "must be [YYYY-MM-DD or ISO date-time, number]"),
            ({"calendar": [event(kind="summit")]}, "kind must be one of"),
            ({"calendar": [event(region="Pacific")]}, "region must be a known region"),
            ({"calendar": [event(storylines=["nope"])]}, "unknown storyline nope"),
            ({"calendar": [event(date="Mon Dec 8")]}, "date must be a YYYY-MM-DD date"),
            ({"calendar": [event(time="12:30 PM")]}, "time must be HH:MM"),
            ({"calendar": [dict((k, v) for k, v in event().items() if k != "tz")]}, "time needs tz"),
            ({"calendar": [event(sources="Example")]}, "sources must list at least one source"),  # malformed, not missing: still rejects
            ({"calendar": [event(date_precision="range", end="1941-12-01")]}, "end must be after date"),
            ({"calendar": [event(end="1941-12-10")]}, "end needs date_precision range"),
            ({"calendar": [event(date_precision="range")]}, "end must be a YYYY-MM-DD date for range"),
            ({"calendar": [event(date_precision="month", date="1941-12-08")]}, "must be YYYY-MM for month"),
            ({"calendar": [event(date_precision="quarter", date="1941-Q5")]}, "must be YYYY-Qn for quarter"),
            ({"calendar": [dict(event(date_precision="month", date="1941-12"))]}, "time needs day or range precision"),
            ({"calendar": [event(date_precision="week")]}, "date_precision must be year, month, day, quarter or range"),
            ({"calendar": [dict(event(date_precision="year", date="1941-12"))]}, "must be YYYY for year precision"),
            ({"calendar": [dict((k, v) for k, v in event().items() if k not in ("time", "tz")) | {"date_precision": "year", "date": "1942", "time": "10:00", "tz": "UTC"}]}, "time needs day or range precision"),
            ({"calendar": [dict((k, v) for k, v in event().items() if k != "date")]}, "undated items belong in the brief"),
            ({"calendar": [event(entities=["nowhere"])]}, "unknown entity nowhere"),
            ({"calendar": [event(id="Not A Slug")]}, "must be a lowercase slug"),
        ]
        for extra, message in bad:
            with self.subTest(message=message):
                root = fixture()
                drop(root, "1941-12-07", dict(shock(), **extra))
                before = hashes(root)
                with self.assertRaises(PacketError) as caught:
                    apply_all(root, wikipedia=wiki_ok)
                self.assertIn(message, str(caught.exception))
                self.assertEqual(before, hashes(root))
                self.assertFalse((root / "data" / "markets.json").exists())

    def test_real_corpus_and_inbox_replay_is_unchanged(self):
        tmp = Path(tempfile.mkdtemp())
        root = tmp / "gia"
        shutil.copytree(ROOT / "data", root / "data")
        shutil.copytree(ROOT / "inbox", root / "inbox")
        before = hashes(root)
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertTrue(notes and all(n.startswith("unchanged ") for n in notes))
        self.assertEqual(before, hashes(root))

def brief(**over):
    item = {"bottom_line": "Japan struck the Pacific Fleet; war is now certain.",
            "board": [{"region": "Asia-Pacific", "status": "critical", "trend": "up", "note": "Fleet attacked.",
                       "stories": ["1941-12-07-pearl-harbor"]}],
            "threads": [{"storyline": "pacific-war", "note": "Declaration expected"}],
            "connections": [{"title": "Embargo to attack", "confidence": "likely",
                             "steps": ["Oil embargo", "Hull note", "Attack"], "stories": ["1941-11-26-hull-note", "1941-12-07-pearl-harbor"]}],
            "deep_dive": {"title": "Why Hawaii", "summary": "The fleet had moved to Pearl Harbor in 1940.",
                          "analysis": {"text": "Basing forward invited a first strike.", "confidence": "possible"},
                          "sources": [{"name": "Example", "url": "https://example.com/dd"}], "stories": ["1941-12-07-pearl-harbor"]},
            "next_up": ["1941-12-08-congress-session"]}
    item.update(over)
    return item

class BriefAndOptionalFieldTests(unittest.TestCase):
    def test_brief_applies_into_new_file_and_rolls_back(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), calendar=[event()], brief=brief()))
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertIn("1 brief", notes[0])
        briefs = read(root / "data" / "briefs.json")
        self.assertEqual(briefs[0]["edition"], "1941-12-07")
        self.assertEqual(briefs[0]["next_up"], ["1941-12-08-congress-session"])
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        self.assertEqual(read(root / "data" / "briefs.json"), [])

    def test_brief_minimal_and_without_brief_no_file(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        self.assertFalse((root / "data" / "briefs.json").exists())
        drop(root, "1941-12-08", {"edition": "1941-12-08", "brief": {"bottom_line": "Quiet day."}})
        self.assertEqual(apply_all(root, wikipedia=wiki_ok)[-1], "applied 1941-12-08: 1 brief")

    def test_invalid_brief_rejects_whole_packet(self):
        dd = brief()["deep_dive"]
        bad = [
            ({"brief": []}, "brief must be an object"),
            ({"brief": brief(bottom_line="")}, "bottom_line must be a non-empty string"),
            ({"brief": brief(headline="x")}, "unknown field headline"),
            ({"brief": brief(board=[{"region": "Asia-Pacific", "status": "severe", "note": "x"}])}, "status must be"),
            ({"brief": brief(board=[{"region": "Pacific", "status": "high", "note": "x"}])}, "region must be a known region"),
            ({"brief": brief(board=[{"region": "Asia-Pacific", "status": "high", "trend": "rising", "note": "x"}])}, "trend must be up, flat or down"),
            ({"brief": brief(board=brief()["board"] * 2)}, "duplicate region Asia-Pacific"),
            ({"brief": brief(threads=[{"storyline": "nope"}])}, "unknown storyline nope"),
            ({"brief": brief(connections=[{"title": "x", "confidence": "sure", "steps": ["a", "b"], "stories": ["1941-11-26-hull-note"]}])}, "confidence must be"),
            ({"brief": brief(connections=[{"title": "x", "confidence": "likely", "steps": ["a"], "stories": ["1941-11-26-hull-note"]}])}, "at least two"),
            ({"brief": brief(connections=[{"title": "x", "confidence": "likely", "steps": ["a", "b"], "stories": []}])}, "must cite at least one story"),
            ({"brief": brief(deep_dive=dict(dd, sources=[]))}, "sources must list at least one source"),
            ({"brief": brief(deep_dive=dict(dd, analysis={"text": "x", "confidence": "sure"}))}, "confidence"),
            ({"brief": brief(next_up=["no-such-event"])}, "unknown calendar item no-such-event"),
        ]
        for extra, message in bad:
            with self.subTest(message=message):
                root = fixture()
                drop(root, "1941-12-07", dict(shock(), calendar=[event()], **extra))
                before = hashes(root)
                with self.assertRaises(PacketError) as caught:
                    apply_all(root, wikipedia=wiki_ok)
                self.assertIn(message, str(caught.exception))
                self.assertEqual(before, hashes(root))

    def test_story_lede_new_and_by_correction(self):
        root = fixture()
        packet = shock()
        packet["stories"][0]["lede"] = "Japan attacked Pearl Harbor at dawn."
        drop(root, "1941-12-07", packet)
        apply_all(root, wikipedia=wiki_ok)
        pearl = next(s for s in read(root / "data" / "stories.json") if s["id"] == "1941-12-07-pearl-harbor")
        self.assertEqual(pearl["lede"], "Japan attacked Pearl Harbor at dawn.")
        drop(root, "1941-12-08", {"edition": "1941-12-08", "corrections": [
            {"id": "1941-11-26-hull-note", "why": "Add a phone lede.", "lede": "Washington set terms Tokyo rejected."}]})
        apply_all(root, wikipedia=wiki_ok)
        hull = next(s for s in read(root / "data" / "stories.json") if s["id"] == "1941-11-26-hull-note")
        self.assertEqual(hull["lede"], "Washington set terms Tokyo rejected.")
        self.assertEqual(hull["revisions"][-1]["fields"], ["lede"])

    def test_story_lede_too_long_rejected(self):
        root = fixture()
        packet = shock()
        packet["stories"][0]["lede"] = "x" * 161
        drop(root, "1941-12-07", packet)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("lede must be at most 160 characters", str(caught.exception))

    def test_storyline_short_name_set_on_existing_line_and_limit(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), storylines=[{"id": "pacific-war", "name": "Pacific war", "short_name": "Pacific"}]))
        apply_all(root, wikipedia=wiki_ok)
        line = read(root / "data" / "storylines.json")[0]
        self.assertEqual(line["short_name"], "Pacific")
        drop(root, "1941-12-08", {"edition": "1941-12-08", "storylines": [{"id": "pacific-war", "name": "Pacific war", "short_name": "x" * 25}]})
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("short_name must be at most 24 characters", str(caught.exception))

class MarketsTimeAndCalendarPrecisionTests(unittest.TestCase):
    def test_intraday_figures_same_day_are_distinct(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), markets=[
            market(as_of="1941-12-06"),
            market(as_of="1941-12-07T10:00-05:00", value=75.0),
            market(as_of="1941-12-07T15:30Z", value=76.0)]))
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertIn("3 market figures", notes[0])
        ids = [f["id"] for f in read(root / "data" / "markets.json")]
        self.assertEqual(ids, ["brent--1941-12-06", "brent--1941-12-07T10:00-05:00", "brent--1941-12-07T15:30Z"])

    def test_calendar_item_without_source_is_dropped_not_rejected(self):
        # Director 2026-10-18: drop the sourceless item, name it in the publish log, apply the rest.
        root = fixture()
        nosrc = {k: v for k, v in event(id="no-sources-key").items() if k != "sources"}
        drop(root, "1941-12-07", dict(shock(), calendar=[event(), event(id="empty-sources", sources=[]), nosrc]))
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertEqual(notes[:2], [
            "1941-12-07: dropped calendar.empty-sources: no source (a calendar item needs at least one source)",
            "1941-12-07: dropped calendar.no-sources-key: no source (a calendar item needs at least one source)"])
        self.assertTrue(notes[-1].startswith("applied 1941-12-07:"))
        self.assertIn("1 calendar item", notes[-1])
        self.assertEqual([c["id"] for c in read(root / "data" / "calendar.json")], ["1941-12-08-congress-session"])
        self.assertTrue(any(s["id"] == "1941-12-07-pearl-harbor" for s in read(root / "data" / "stories.json")))
        self.assertEqual(apply_all(root, wikipedia=wiki_ok), ["unchanged 1941-12-07"])        # replay: no drop lines, no change
        # a packet whose only content is a sourceless item applies as "no change", it is not rejected
        drop(root, "1941-12-08", {"edition": "1941-12-08", "calendar": [event(id="lonely", sources=[])]})
        notes = apply_all(root, wikipedia=wiki_ok)
        self.assertIn("1941-12-08: dropped calendar.lonely: no source (a calendar item needs at least one source)", notes)
        self.assertEqual(notes[-1], "applied 1941-12-08: no change")
        self.assertNotIn("lonely", [c["id"] for c in read(root / "data" / "calendar.json")])

    def test_calendar_month_quarter_range(self):
        root = fixture()
        undated = {k: v for k, v in event().items() if k not in ("time", "tz")}
        drop(root, "1941-12-07", dict(shock(), calendar=[
            dict(undated, id="q1-plan", date_precision="quarter", date="1942-Q1"),
            dict(undated, id="dec-session", date_precision="month", date="1941-12"),
            dict(undated, id="conference", date_precision="range", date="1941-12-22", end="1942-01-14"),
            dict(undated, id="year-plan", date_precision="year", date="1942"),
            event()]))
        apply_all(root, wikipedia=wiki_ok)
        cal = read(root / "data" / "calendar.json")
        self.assertEqual([c["id"] for c in cal], ["dec-session", "1941-12-08-congress-session", "conference", "year-plan", "q1-plan"])
        self.assertEqual(cal[4]["date_precision"], "quarter")
        self.assertEqual(cal[3]["date_precision"], "year")  # same start day: coarser first (date sorts "1942" < "1942-Q1")

def report(**over):
    item = {"id": "pacific-assessment", "title": "Pacific assessment", "date": "1941-12-07", "author": "GIA Analysis",
            "body": "# Bottom line\n\nThe [attack](story:1941-12-07-pearl-harbor) follows the [Hull note](story:1941-11-26-hull-note).\n\n- one\n- two\n\nSee [the storyline](storyline:pacific-war) and [source](https://example.com/x).",
            "stories": ["1941-12-07-pearl-harbor"], "storylines": ["pacific-war"],
            "sources": [{"name": "Example", "url": "https://example.com/report"}]}
    item.update(over)
    return item

def logitem(**over):
    item = {"id": "rt-1941-12-07-01", "date": "1941-12-07T18:00-10:00", "status": "accepted", "author": "GIA Desk",
            "raised_by": "Red Team", "title": "Attack timing overstated", "reason": "Checked against the logs.",
            "stories": ["1941-12-07-pearl-harbor"], "confidence_from": "likely", "confidence_to": "possible",
            "wording_from": "at dawn", "wording_to": "shortly before 8 am", "sources": [{"name": "Example", "url": "https://example.com/log"}],
            "revision_edition": "1941-12-07"}
    item.update(over)
    return item

class ReportsAndAssessmentLogTests(unittest.TestCase):
    def test_reports_apply_noop_resend_reject_rewrite_and_rollback(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), reports=[report()]))
        self.assertIn("1 report", apply_all(root, wikipedia=wiki_ok)[0])
        self.assertEqual(read(root / "data" / "reports.json")[0]["edition"], "1941-12-07")
        drop(root, "1941-12-08", {"edition": "1941-12-08", "reports": [report()]})
        self.assertEqual(apply_all(root, wikipedia=wiki_ok)[-1], "applied 1941-12-08: no change")
        drop(root, "1941-12-09", {"edition": "1941-12-09", "reports": [report(title="Changed")]})
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("a report is not rewritten", str(caught.exception))
        (root / "inbox" / "1941-12-09.json").unlink()
        drop(root, "1941-12-08", {"edition": "1941-12-08", "reports": [report(id="second", title="Second")]})
        apply_all(root, wikipedia=wiki_ok)
        self.assertEqual([r["id"] for r in read(root / "data" / "reports.json")], ["pacific-assessment", "second"])

    def test_no_section_writes_no_new_files(self):
        root = fixture()
        drop(root, "1941-12-07", shock())
        apply_all(root, wikipedia=wiki_ok)
        for name in ("reports.json", "assessment_log.json", "markets.json", "calendar.json", "briefs.json"):
            self.assertFalse((root / "data" / name).exists(), name)

    def test_invalid_reports(self):
        bad = [
            (report(body="<script>alert(1)</script>"), "must not contain raw HTML"),
            (report(body="Hi <b>x</b>"), "must not contain raw HTML"),
            (report(body="![x](https://example.com/a.png)"), "must not embed images"),
            (report(body="[x](javascript:alert(1))"), "must be http(s), #anchor, story: or storyline:"),
            (report(body="[x](story:nope)"), "links unknown story nope"),
            (report(body="[x](storyline:nope)"), "links unknown storyline nope"),
            (report(body="  "), "body must be non-empty Markdown text"),
            (report(date="Dec 7"), "date must be a YYYY-MM-DD date"),
            (report(date="1941-12-08"), "date is after the edition"),
            (report(stories=["nope"]), "unknown story nope"),
            (report(storylines=["nope"]), "unknown storyline nope"),
            (report(author=""), "author must be a non-empty string"),
            (report(pdf="x.pdf"), "unknown field pdf"),
            (report(sources=[]), "sources must list at least one source"),
        ]
        for item, message in bad:
            with self.subTest(message=message):
                root = fixture()
                drop(root, "1941-12-07", dict(shock(), reports=[item]))
                before = hashes(root)
                with self.assertRaises(PacketError) as caught:
                    apply_all(root, wikipedia=wiki_ok)
                self.assertIn(message, str(caught.exception))
                self.assertEqual(before, hashes(root))

    def test_log_append_only_supersedes_and_rollback(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), assessment_log=[logitem(), logitem(id="rt-1941-12-07-02", status="rejected",
            title="Not a surprise", reason="No source supports it.", confidence_from="likely", confidence_to="likely",
            wording_to=None)]))
        pkt = read(root / "inbox" / "1941-12-07.json"); del pkt["assessment_log"][1]["wording_to"]; del pkt["assessment_log"][1]["revision_edition"]; dump(root / "inbox" / "1941-12-07.json", pkt)
        self.assertIn("2 assessment-log items", apply_all(root, wikipedia=wiki_ok)[0])
        drop(root, "1941-12-08", {"edition": "1941-12-08", "assessment_log": [logitem()]})
        self.assertEqual(apply_all(root, wikipedia=wiki_ok)[-1], "applied 1941-12-08: no change")
        drop(root, "1941-12-08", {"edition": "1941-12-08", "assessment_log": [logitem(reason="Edited")]})
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("the log is append-only", str(caught.exception))
        drop(root, "1941-12-08", {"edition": "1941-12-08", "assessment_log": [logitem(id="rt-1941-12-08-01", date="1941-12-08",
            supersedes="rt-1941-12-07-01", reason="Revised after logs.", revision_edition="1941-12-07")]})
        apply_all(root, wikipedia=wiki_ok)
        log = read(root / "data" / "assessment_log.json")
        self.assertEqual([c["id"] for c in log], ["rt-1941-12-07-01", "rt-1941-12-07-02", "rt-1941-12-08-01"])
        self.assertEqual(log[2]["supersedes"], "rt-1941-12-07-01")
        drop(root, "1941-12-08", {"edition": "1941-12-08", "brief": {"bottom_line": "x"}})
        apply_all(root, wikipedia=wiki_ok)
        self.assertEqual(len(read(root / "data" / "assessment_log.json")), 2)

    def test_invalid_log(self):
        base = {k: v for k, v in logitem().items()}
        bad = [
            (logitem(status="partly"), "status must be accepted or rejected"),
            (logitem(scope="tweet"), "scope must be story, brief or site"),
            (logitem(stories=[]), "must name at least one story for scope story"),
            (logitem(stories=["nope"]), "unknown story nope"),
            ({k: v for k, v in base.items() if k != "confidence_to"}, "needs both confidence_from and confidence_to"),
            (logitem(confidence_to="certain"), "confidence_to must be"),
            (logitem(status="rejected"), "rejected; it cannot carry wording_to"),
            (dict({k: v for k, v in base.items() if k != "wording_to"}, status="rejected"), "rejected; confidence cannot change"),
            (logitem(supersedes="rt-none"), "supersedes unknown assessment log entry"),
            (logitem(supersedes="rt-1941-12-07-01"), "cannot supersede itself"),
            (logitem(revision_edition="Dec 7"), "revision_edition must be a YYYY-MM-DD edition"),
            (dict({k: v for k, v in base.items() if k != "wording_to"}, status="rejected", confidence_to="likely"), "rejected; it cannot point at a revision"),
            (logitem(revision_edition="1900-01-01"), "has no ledger entry"),
            (logitem(date="1941-12-09"), "date is after the edition"),
            (logitem(date="yesterday"), "date must be YYYY-MM-DD or an ISO date-time"),
            (logitem(reason=""), "reason must be a non-empty string"),
            (logitem(editor="x"), "unknown field editor"),
        ]
        for item, message in bad:
            with self.subTest(message=message):
                root = fixture()
                drop(root, "1941-12-07", dict(shock(), assessment_log=[item]))
                before = hashes(root)
                with self.assertRaises(PacketError) as caught:
                    apply_all(root, wikipedia=wiki_ok)
                self.assertIn(message, str(caught.exception))
                self.assertEqual(before, hashes(root))

    def test_log_supersede_once_and_revision_ref(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), assessment_log=[logitem()]))
        apply_all(root, wikipedia=wiki_ok)
        drop(root, "1941-12-08", {"edition": "1941-12-08", "assessment_log": [
            logitem(id="rt-a", date="1941-12-08", supersedes="rt-1941-12-07-01"),
            logitem(id="rt-b", date="1941-12-08", supersedes="rt-1941-12-07-01")]})
        before = hashes(root)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("supersedes rt-1941-12-07-01, which is already superseded", str(caught.exception))
        self.assertEqual(before, hashes(root))
        # revision_edition must name an edition that actually revised (or owns) the story
        drop(root, "1941-12-08", {"edition": "1941-12-08", "assessment_log": [logitem(id="rt-c", date="1941-12-08", stories=["1941-11-26-hull-note"], revision_edition="1941-12-07")]})
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("story 1941-11-26-hull-note has no revision or republish in edition 1941-12-07", str(caught.exception))
        # ... and a correction in the same packet counts
        drop(root, "1941-12-08", {"edition": "1941-12-08",
            "corrections": [{"id": "1941-12-07-pearl-harbor", "why": "Red Team", "summary": "Japan attacked Pearl Harbor shortly before 8 am."}],
            "assessment_log": [logitem(id="rt-c", date="1941-12-08", revision_edition="1941-12-08")]})
        self.assertIn("1 correction, 1 assessment-log item", apply_all(root, wikipedia=wiki_ok)[-1])
        self.assertEqual(read(root / "data" / "ledger.json")["packets"]["1941-12-08"]["undo"]["assessment_log"], {"rt-c": None})

    def test_real_fixture_2026_10_18_validates_and_replays_exactly(self):
        fixture_path = ROOT / "tests" / "fixtures" / "assessment_log-2026-10-18.json"
        entries = read(fixture_path)
        self.assertEqual(sum(e["status"] == "accepted" and e.get("scope", "story") == "story" for e in entries), 17)
        self.assertEqual(sum(e["status"] == "rejected" for e in entries), 5)
        outputs = []
        for _ in range(2):
            tmp = Path(tempfile.mkdtemp()); root = tmp / "gia"
            shutil.copytree(ROOT / "data", root / "data"); (root / "inbox").mkdir()
            shutil.copytree(ROOT / "inbox", root / "inbox", dirs_exist_ok=True)
            latest = max(read(root / "data" / "ledger.json")["packets"])
            ed = (date.fromisoformat(latest) + timedelta(days=1)).isoformat()
            drop(root, ed, {"edition": ed, "assessment_log": entries})
            notes = apply_all(root, wikipedia=wiki_ok)
            self.assertEqual(notes[-1], f"applied {ed}: {len(entries)} assessment-log items")
            again = apply_all(root, wikipedia=wiki_ok)
            self.assertTrue(all(n.startswith("unchanged ") for n in again))
            outputs.append((root / "data" / "assessment_log.json").read_bytes())
            log = read(root / "data" / "assessment_log.json")
            self.assertEqual([{k: v for k, v in e.items() if k != "edition"} for e in log], entries)
        self.assertEqual(outputs[0], outputs[1])

def zone_area(**over):
    item = {"id": "test-sea", "name": "Test sea", "severity": "watch", "note": "Area theater", "entities": ["japan"],
            "area": {"type": "Polygon", "coordinates": [[[130, 30], [140, 30], [140, 40], [130, 40], [130, 30]]]},
            "area_source": {"name": "Test boundary authority", "url": "https://example.com/area"}}
    item.update(over)
    return item

class AreaTests(unittest.TestCase):
    def test_area_only_zone_and_point_inside(self):
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), zones=shock()["zones"] + [zone_area(), zone_area(id="sea-two", lat=35.0, lon=135.0,
            area={"type": "MultiPolygon", "coordinates": [[[[130, 30], [140, 30], [140, 40], [130, 40], [130, 30]]]]})]))
        apply_all(root, wikipedia=wiki_ok)
        zones = {z["id"]: z for z in read(root / "data" / "hotzones.json")["zones"]}
        self.assertNotIn("lat", zones["test-sea"])
        self.assertEqual(zones["test-sea"]["area_source"]["name"], "Test boundary authority")
        self.assertEqual(zones["sea-two"]["lat"], 35.0)

    def test_area_rejections(self):
        open_ring = [[[130, 30], [140, 30], [140, 40], [130, 40]]]
        bad = [
            (zone_area(area_source=None), "area_source must be an object"),
            ({k: v for k, v in zone_area().items() if k != "area_source"}, "area needs area_source"),
            ({k: v for k, v in zone_area().items() if k != "area"}, "area_source needs area"),
            (zone_area(area={"type": "Point", "coordinates": [1, 2]}), "must be a GeoJSON Polygon or MultiPolygon"),
            (zone_area(area={"type": "Polygon", "coordinates": open_ring}), "ring must be closed"),
            (zone_area(area={"type": "Polygon", "coordinates": [[[130, 30], [200, 30], [140, 40], [130, 30]]]}), "position must be [lon, lat] in range"),
            (zone_area(lat=10.0, lon=10.0), "lat/lon is more than 25 km outside its area"),
            (zone_area(lat=29.5, lon=135.0), "lat/lon is more than 25 km outside its area"),   # ~55 km south of the edge
            (zone_area(area={"type": "Polygon", "coordinates": [[[130 + i * 0.01, 30] for i in range(400)] + [[130, 30]]]}), "simplify to at most"),
        ]
        for item, message in bad:
            with self.subTest(message=message):
                root = fixture()
                drop(root, "1941-12-07", dict(shock(), zones=shock()["zones"] + [item]))
                before = hashes(root)
                with self.assertRaises(PacketError) as caught:
                    apply_all(root, wikipedia=wiki_ok)
                self.assertIn(message, str(caught.exception))
                self.assertEqual(before, hashes(root))

    def test_area_on_existing_zone_point_tolerance(self):
        # The zone point is a marker/label anchor (often on the coast): inside the area or within 25 km
        # of its edge. Adding an area to an existing zone changes only area and area_source.
        root = fixture()
        pt = {k: v for k, v in zone_area(id="sea-pt", lat=29.9, lon=135.0).items() if k not in ("area", "area_source")}  # ~11 km outside
        drop(root, "1941-12-07", dict(shock(), zones=shock()["zones"] + [pt]))
        apply_all(root, wikipedia=wiki_ok)
        before = {z["id"]: z for z in read(root / "data" / "hotzones.json")["zones"]}
        area = zone_area()
        drop(root, "1941-12-08", {"edition": "1941-12-08", "zones": [{"id": "sea-pt", "area": area["area"], "area_source": area["area_source"]}]})
        self.assertEqual(apply_all(root, wikipedia=wiki_ok)[-1], "applied 1941-12-08: 1 zone")
        after = {z["id"]: z for z in read(root / "data" / "hotzones.json")["zones"]}
        self.assertEqual(list(before), list(after))
        changed = {k for k in set(before["sea-pt"]) | set(after["sea-pt"]) if before["sea-pt"].get(k) != after["sea-pt"].get(k)}
        self.assertEqual(changed, {"area", "area_source"})
        self.assertEqual({k: v for k, v in before.items() if k != "sea-pt"}, {k: v for k, v in after.items() if k != "sea-pt"})

    def test_no_second_precision_field(self):
        # Director: precision stays the existing place `precision` (city|sector|feature).
        for where in ("stories", "zones"):
            with self.subTest(where=where):
                root = fixture()
                packet = shock(); packet[where][0]["geo_precision"] = "feature"
                drop(root, "1941-12-07", packet)
                with self.assertRaises(PacketError) as caught:
                    apply_all(root, wikipedia=wiki_ok)
                self.assertIn("unknown field geo_precision", str(caught.exception))

    def test_area_theater_check(self):
        # The test polygon (130-140E, 30-40N) covers Japan: accepted. Moved to the Atlantic: rejected.
        far = {"type": "Polygon", "coordinates": [[[-40, 30], [-30, 30], [-30, 40], [-40, 40], [-40, 30]]]}
        for item, message in [
            (zone_area(area=far), "is not within 100 km of any named country (japan)"),
            (zone_area(entities=["pearl-harbor"]), "name at least one country entity"),
        ]:
            with self.subTest(message=message):
                root = fixture()
                drop(root, "1941-12-07", dict(shock(), zones=shock()["zones"] + [item]))
                before = hashes(root)
                with self.assertRaises(PacketError) as caught:
                    apply_all(root, wikipedia=wiki_ok)
                self.assertIn(message, str(caught.exception))
                self.assertEqual(before, hashes(root))
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), zones=shock()["zones"] + [zone_area(entities=["japan", "united-states"])]))
        self.assertIn("applied", apply_all(root, wikipedia=wiki_ok)[0])

    def test_area_does_not_place_entity_and_old_zones_unchanged(self):
        root = fixture()
        ents = read(root / "data" / "entities.json")
        ents.append({"id": "test-sea-place", "name": "Test sea", "type": "place", "wikipedia": "https://en.wikipedia.org/wiki/Sea"})
        dump(root / "data" / "entities.json", ents)
        packet = dict(shock(), zones=shock()["zones"] + [zone_area(entities=["japan", "test-sea-place"])])
        packet["stories"][0]["where"] = ["test-sea-place"]
        drop(root, "1941-12-07", packet)
        with self.assertRaises(PacketError) as caught:
            apply_all(root, wikipedia=wiki_ok)
        self.assertIn("test-sea-place is not a placed location", str(caught.exception))
        root = fixture()
        drop(root, "1941-12-07", dict(shock(), zones=shock()["zones"] + [zone_area()]))
        apply_all(root, wikipedia=wiki_ok)
        zones = {z["id"]: z for z in read(root / "data" / "hotzones.json")["zones"]}
        self.assertNotIn("area", zones["hawaii"])
        self.assertEqual((zones["hawaii"]["lat"], zones["hawaii"]["lon"]), (21.36, -157.95))

if __name__ == "__main__":
    unittest.main()
