#!/usr/bin/env python3
"""Derive per-edition hot-zone severity history at build time (PROTOTYPE).

Reads inbox/*.json (read-only) and data/{hotzones,ledger}.json (read-only). Writes nothing
unless --json PATH is given. No schema change: the history is derived, never stored in data/.

Rules
- Only packets whose bytes match the ledger sha256 (i.e. what apply actually merged) count.
- An edition whose packet lists a zone WITH severity -> {"edition", "severity", "basis": "filed"}.
- A zone listed WITHOUT severity is a touch: severity unchanged -> basis "carried".
- Severity before a zone's first filed value is unknown, except that the ledger undo snapshot
  of the first touching edition records the prior state -> basis "prior" (dated to that edition's eve).
- Zones never touched by a packet get only the current snapshot value -> basis "snapshot".
"""
import argparse, hashlib, json
from pathlib import Path

def derive(root):
    root = Path(root)
    zones = {z["id"]: z for z in json.loads((root / "data/hotzones.json").read_text())["zones"]}
    ledger = json.loads((root / "data/ledger.json").read_text()).get("packets", {})
    hist, skipped, editions_with_zones = {z: [] for z in zones}, [], []
    for path in sorted((root / "inbox").glob("*.json")):
        ed = path.stem
        rec = ledger.get(ed)
        if not rec or rec.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            skipped.append(ed); continue
        packet = json.loads(path.read_text(encoding="utf-8"))
        items = [z for z in packet.get("zones") or [] if isinstance(z, dict) and z.get("id")]
        if not items: continue
        editions_with_zones.append(ed)
        prior = ((rec.get("undo") or {}).get("zones") or {})
        for z in items:
            h = hist.setdefault(z["id"], [])
            if not h and prior.get(z["id"]) and prior[z["id"]].get("severity"):
                h.append({"edition": ed, "severity": prior[z["id"]]["severity"], "basis": "prior"})
            if z.get("severity"):
                h.append({"edition": ed, "severity": z["severity"], "basis": "filed"})
            elif h:
                h.append({"edition": ed, "severity": h[-1]["severity"], "basis": "carried"})
    for zid, h in hist.items():
        if not h and zid in zones:
            h.append({"edition": None, "severity": zones[zid]["severity"], "basis": "snapshot"})
    def trend(h):
        filed = [x["severity"] for x in h if x["basis"] in ("filed", "prior")]
        order = ["watch", "elevated", "high", "critical"]
        if len(filed) < 2: return "n/a"
        d = order.index(filed[-1]) - order.index(filed[-2])
        return "up" if d > 0 else "down" if d < 0 else "flat"
    changes = sum(1 for h in hist.values() for a, b in zip(h, h[1:]) if a["severity"] != b["severity"])
    return {"zones": {z: {"history": h, "trend": trend(h)} for z, h in hist.items()},
            "coverage": {"packets": len(list((root / "inbox").glob("*.json"))), "editions_with_zones": editions_with_zones,
                         "zones_in_snapshot": len(zones),
                         "zones_with_filed_severity": sum(any(x["basis"] == "filed" for x in h) for z, h in hist.items() if z in zones),
                         "zones_snapshot_only": sorted(z for z, h in hist.items() if h and h[0]["basis"] == "snapshot"),
                         "severity_changes_observed": changes, "skipped_unapplied_or_mismatched": skipped}}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=str(Path(__file__).resolve().parent)); ap.add_argument("--json")
    a = ap.parse_args(); out = derive(a.root)
    if a.json: Path(a.json).write_text(json.dumps(out, indent=1))
    print(json.dumps(out["coverage"], indent=1))
    for z, v in out["zones"].items(): print(f"{z:22} {v['trend']:5} " + " ".join(f"{x['edition'] or '-'}:{x['severity']}({x['basis'][0]})" for x in v["history"]))
