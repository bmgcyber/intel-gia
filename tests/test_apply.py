import hashlib, json, shutil, sys, tempfile, unittest
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
        drop(root, "2026-10-16", {
            "edition": "2026-10-16",
            "stories": [{
                "id": "2026-10-16-apply-test", "date": "2026-10-16", "region": "Middle East",
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
        self.assertEqual(added["edition"], "2026-10-16")
        self.assertEqual(added["batch"], "inbox-2026-10-16")
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

if __name__ == "__main__":
    unittest.main()
