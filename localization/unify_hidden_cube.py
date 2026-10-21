"""Normalize reviewed Hidden Cube terminology after pinned baseline generation."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(source, translation):
    # Never reinterpret an ordinary backpack, or rewrite formatting tokens.
    visible = re.sub(r"<[^>]*>|\{[^}]*\}", "", source)
    if not re.search(r"\bHidden Cubes?\b", visible):
        return translation
    return re.sub(r"(<[^>]*>|\{[^}]*\})|隐藏背包|隱藏背包",
                  lambda match: match[1] or "隐藏宝箱", translation)


def build(bundle, sources):
    if bundle.get("format") != 3:
        raise ValueError("Expected format-3 reviewed baseline")
    result = deepcopy(bundle)
    changed = 0
    for section in ("entries", "corrections"):
        for key, variants in result[section].items():
            for variant in variants:
                for source in sources:
                    original = source.get(key)
                    if original is None or digest(original) != variant["source_sha256"]:
                        continue
                    previous = variant["translation"]
                    variant["translation"] = normalize(original, previous)
                    changed += variant["translation"] != previous
                    break
    # Some unchanged object names come directly from the pinned engine, not
    # additions. Bind their correction to both the complete source and old name.
    for source in sources:
        for key, original in source.items():
            if original != "Hidden Cube":
                continue
            variants = result["corrections"].setdefault(key, [])
            for previous in ("隐藏背包", "隱藏背包"):
                binding = (digest(original), digest(previous))
                if any((item["source_sha256"], item["previous_translation_sha256"]) == binding
                       for item in variants):
                    continue
                variants.append({"source_sha256": binding[0],
                                 "previous_translation_sha256": binding[1],
                                 "translation": "隐藏宝箱"})
                changed += 1
    return result, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("sources", nargs="+", type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise ValueError("Destination must be new")
    bundle = json.loads(gzip.decompress(args.baseline.read_bytes()))
    result, changed = build(bundle, [json.loads(path.read_bytes()) for path in args.sources])
    args.destination.write_bytes(gzip.compress(json.dumps(
        result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), mtime=0))
    print(json.dumps({"hidden_cube_variants_updated": changed}))


if __name__ == "__main__":
    main()
