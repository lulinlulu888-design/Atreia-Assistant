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
import re
from pathlib import Path

from build_official_additions import build as build_official, PARAMETERS

SNAPSHOTS = {
    "steam": "f7f9052a1b15e9a8815337a49db5271f71b7ee713dba13439e3debc696b8c696",
    "purple": "86784036c93ea93090f0f3e4f3f4859d8e04855d7faa2636e6171499bf61834e",
    "traditional": "bd0eab7d1344c07ebb88f2ebd045b6a298a810f48743062d82dc9c947ea6f11c",
    "reviewed_steam": "cb58fcf4751f6bf3ac17a5686f20c6651f04cc5a069d3aad53c1f56586d464db",
}
STEAM_BASELINE_HASH = "f8c79eb669613ba68aaff45a22395b9cd12138631253d5789f96b023330254bf"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def merge(primary, official, steam, purple, steam_baseline=None):
    if primary["format"] != 3 or official["format"] != 1:
        raise ValueError("Expected released format-3 corrections and format-1 official additions")
    result = deepcopy(primary)
    # Legacy callers protect their entire Steam snapshot. A reviewed update
    # supplies the previous snapshot so newly changed shared rows can be filled.
    if steam_baseline is None:
        steam_baseline = steam
    added = protected = retained = 0
    for key, variant in official["entries"].items():
        if key not in purple or variant["source_sha256"] != digest(purple[key]):
            raise ValueError("Official variant does not match the reviewed PURPLE source: " + key)
        # This makes preserving the Steam output a property of the merge, not
        # a hope based on a few hand-picked client-specific text examples.
        if (key in steam and variant["source_sha256"] == digest(steam[key])
                and steam_baseline.get(key) == steam[key]):
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
    result["origin"] = "released Steam corrections plus reviewed current-client variants for PURPLE 123"
    return result, {"added_purple_variants": added, "protected_steam_pairs": protected,
                    "retained_reviewed_pairs": retained}


def load_snapshot(path, name):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SNAPSHOTS[name]:
        raise ValueError("Unreviewed source snapshot: " + name)
    return json.loads(raw)


def append_reviewed_steam(result, review, steam):
    if review.get("format") != 1 or not isinstance(review.get("entries"), dict):
        raise ValueError("Expected source-bound reviewed Steam additions")
    added = replaced_untranslated = 0
    display_tag = {"<红色风味万圣节糖果>": "<Red Halloween Candy>"}
    for key, variant in review["entries"].items():
        if key not in steam or variant.get("source_sha256") != digest(steam[key]):
            raise ValueError("Reviewed variant does not match current Steam source: " + key)
        text = variant.get("translation")
        if not isinstance(text, str) or not text or text == steam[key]:
            raise ValueError("Reviewed variant must provide a translation: " + key)
        if sorted(PARAMETERS.findall(steam[key])) != sorted(PARAMETERS.findall(text)):
            raise ValueError("Reviewed variant changes runtime parameters: " + key)
        expected_tags = re.findall(r"<[^>]*>", steam[key])
        actual_tags = [display_tag.get(tag, tag) for tag in re.findall(r"<[^>]*>", text)]
        if expected_tags != actual_tags:
            raise ValueError("Reviewed variant changes formatting tags: " + key)
        variants = result["entries"].setdefault(key, [])
        existing = [item for item in variants if item["source_sha256"] == variant["source_sha256"]]
        if any(item["translation"] not in (steam[key], text) for item in existing):
            raise ValueError("Reviewed addition would overwrite an existing translation: " + key)
        if existing:
            for item in existing:
                if item["translation"] == steam[key]:
                    item["translation"] = text
                    replaced_untranslated += 1
        else:
            variants.append(deepcopy(variant))
            added += 1
    return {"added_steam_variants": added, "replaced_untranslated_variants": replaced_untranslated,
            "reviewed_steam_rows": len(review["entries"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("primary", "steam", "purple", "traditional", "destination"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--steam-baseline", type=Path, required=True)
    parser.add_argument("--reviewed-steam", type=Path, required=True)
    args = parser.parse_args()
    if args.destination.exists():
        raise ValueError("Destination must be new")
    steam, purple, traditional, review = (load_snapshot(getattr(args, name), name)
                                          for name in SNAPSHOTS)
    baseline_raw = args.steam_baseline.read_bytes()
    if hashlib.sha256(baseline_raw).hexdigest() != STEAM_BASELINE_HASH:
        raise ValueError("Unreviewed previous Steam snapshot")
    steam_baseline = json.loads(baseline_raw)
    if hashlib.sha256(args.primary.read_bytes()).hexdigest() != "768e67b1693156f02d63f2b817990aff4b0cca5ff5f16968ebf69331684014f1":
        raise ValueError("Unreviewed released corrections")
    with gzip.open(args.primary, "rt", encoding="utf-8") as stream:
        primary = json.load(stream)
    official, rejected = build_official(purple, traditional)
    if rejected:
        raise ValueError(f"{len(rejected)} official parameter differences require review")
    result, report = merge(primary, official, steam, purple, steam_baseline)
    report.update(append_reviewed_steam(result, review, steam))
    report["inputs"] = {**SNAPSHOTS, "steam_baseline": STEAM_BASELINE_HASH,
                       "primary": hashlib.sha256(args.primary.read_bytes()).hexdigest()}
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    args.destination.mkdir(parents=True)
    (args.destination / "dual-corrections.json.gz").write_bytes(gzip.compress(encoded, mtime=0))
    (args.destination / "review.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
