"""Restore reviewed PURPLE variants without changing the released Steam table.

Inputs are maintainer-owned, pinned snapshots, kept in release materials, not Git.
Steam corrections remain authoritative for identical key/source pairs. PURPLE
only contributes variants that cannot match the current Steam source for a key.
"""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from build_official_additions import build as build_official

SNAPSHOTS = {
    "steam": "f8c79eb669613ba68aaff45a22395b9cd12138631253d5789f96b023330254bf",
    "purple": "0c7b67bda6f4b0b1e5fec862fdf21b49b90711a198a59f457e2756ead154c172",
    "traditional": "186429b1f630c119ffe59be7a492febbcf90a05fff4ea1269256af57b2ef1780",
}


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def merge(primary, official, steam, purple):
    if primary["format"] != 3 or official["format"] != 1:
        raise ValueError("Expected released format-3 corrections and format-1 official additions")
    result = deepcopy(primary)
    added = protected = retained = 0
    for key, variant in official["entries"].items():
        if key not in purple or variant["source_sha256"] != digest(purple[key]):
            raise ValueError("Official variant does not match the reviewed PURPLE source: " + key)
        # This makes preserving the Steam output a property of the merge, not
        # a hope based on a few hand-picked client-specific text examples.
        if key in steam and variant["source_sha256"] == digest(steam[key]):
            protected += 1
            continue
        variants = result["entries"].setdefault(key, [])
        existing = [v for v in variants if v["source_sha256"] == variant["source_sha256"]]
        if existing:
            if len({v["translation"] for v in existing}) != 1:
                raise ValueError("Conflicting released variants: " + key)
            retained += 1
            continue
        variants.append(deepcopy(variant))
        added += 1
    result["origin"] = "released Steam corrections plus source-bound official PURPLE 122 variants"
    return result, {"added_purple_variants": added, "protected_steam_pairs": protected,
                    "retained_reviewed_pairs": retained}


def load_snapshot(path, name):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SNAPSHOTS[name]:
        raise ValueError("Unreviewed source snapshot: " + name)
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("primary", "steam", "purple", "traditional", "destination"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise ValueError("Destination must be new")
    steam, purple, traditional = (load_snapshot(getattr(args, name), name)
                                   for name in SNAPSHOTS)
    if hashlib.sha256(args.primary.read_bytes()).hexdigest() != "768e67b1693156f02d63f2b817990aff4b0cca5ff5f16968ebf69331684014f1":
        raise ValueError("Unreviewed released corrections")
    with gzip.open(args.primary, "rt", encoding="utf-8") as stream:
        primary = json.load(stream)
    official, rejected = build_official(purple, traditional)
    if rejected:
        raise ValueError(f"{len(rejected)} official parameter differences require review")
    result, report = merge(primary, official, steam, purple)
    report["inputs"] = {**SNAPSHOTS, "primary": hashlib.sha256(args.primary.read_bytes()).hexdigest()}
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    args.destination.mkdir(parents=True)
    (args.destination / "dual-corrections.json.gz").write_bytes(gzip.compress(encoded, mtime=0))
    (args.destination / "review.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
