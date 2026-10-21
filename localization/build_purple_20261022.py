"""Pinned PURPLE update; preserve all existing source-bound client variants."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from build_official_additions import build as build_official

HASHES = {
    "english": "275173f15d13479dcd4ce156467d2fded8976cd6441bc41e34dfb8149da43f79",
    "traditional": "b5f328a5f2947cde5476c1eb8a203264b1c814007ca06313600c955d08c27058",
    "previous": "86784036c93ea93090f0f3e4f3f4859d8e04855d7faa2636e6171499bf61834e",
    "baseline_json": "caae0f1b9c528a97945248304eff22473eca146799a003ff441f3eb23a887bef",
}


def build(english, traditional, previous, baseline):
    if baseline.get("format") != 3 or english.keys() - traditional.keys():
        raise ValueError("Missing official translations or unsupported baseline")
    changed = {key: text for key, text in english.items() if previous.get(key) != text}
    official, rejected = build_official(changed, {key: traditional[key] for key in changed})
    if rejected:
        raise ValueError("Official runtime parameter differences require review")
    result = deepcopy(baseline)
    added = retained = 0
    for key, variant in official["entries"].items():
        variants = result["entries"].setdefault(key, [])
        existing = [item for item in variants if item["source_sha256"] == variant["source_sha256"]]
        if existing:
            if len({item["translation"] for item in existing}) != 1:
                raise ValueError("Conflicting existing source variants: " + key)
            retained += 1
        else:
            variants.append(variant)
            added += 1
    result["origin"] = "Reviewed Steam 26077854 baseline plus PURPLE 2026-10-22 official source variants"
    return result, {"source_keys": len(english), "changed_keys": len(changed),
                    "added_variants": added, "retained_reviewed_variants": retained,
                    "unused_traditional_keys": sorted(traditional.keys() - english.keys()),
                    "runtime_parameter_mismatches": len(rejected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("english", "traditional", "previous", "baseline", "destination"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise ValueError("Destination must be new")
    tables = {}
    for name in ("english", "traditional", "previous", "baseline"):
        raw = getattr(args, name).read_bytes()
        if name == "baseline":
            raw = gzip.decompress(raw)
        if hashlib.sha256(raw).hexdigest() != HASHES["baseline_json" if name == "baseline" else name]:
            raise ValueError("Unreviewed input snapshot: " + name)
        tables[name] = json.loads(raw)
    result, report = build(**tables)
    report["inputs"] = HASHES
    args.destination.mkdir(parents=True)
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (args.destination / "additions.json.gz").write_bytes(gzip.compress(encoded, mtime=0))
    (args.destination / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
