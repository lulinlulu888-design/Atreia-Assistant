"""Generate reviewed corrections bound to both source and previous translation.

Only writes new staging files. The preview JSON is not an installable game file.
An optional existing additions resource is preserved in the format-3 bundle.
"""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re

from build_official_additions import PARAMETERS, load_mainland_terms, mainland_terms
from reviewed_mainland import reviewed_translation

TAGS = re.compile(r"<[^>]*>")


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build(source, previous, additions=None, converter=None):
    if list(source) != list(previous):
        raise ValueError("Source and previous translation must have identical key order")
    additions = deepcopy(additions) if additions is not None else {"format": 2, "entries": {}}
    if additions["format"] not in (1, 2):
        raise ValueError("Expected original format-1/2 additions, not an already corrected resource")
    entries = additions["entries"]
    if additions["format"] == 1:
        entries = {key: [value] for key, value in entries.items()}
    terms = load_mainland_terms(converter)
    preview, corrections, counts, review = dict(previous), {}, Counter(), []
    for key, original in source.items():
        old = previous[key]
        exact = reviewed_translation(key, original)
        text = mainland_terms(old if exact is None else exact, terms, original)
        if text == old:
            continue
        if sorted(PARAMETERS.findall(original)) != sorted(PARAMETERS.findall(text)):
            raise ValueError(f"Correction changes source parameters: {key}")
        if TAGS.findall(old) != TAGS.findall(text):
            raise ValueError(f"Correction changes existing tags: {key}")
        corrections[key] = [{"source_sha256": digest(original),
                             "previous_translation_sha256": digest(old), "translation": text}]
        preview[key] = text
        reason = "reviewed_exact_source" if exact is not None else "terminology"
        counts[reason] += 1
        review.append({"key": key, "reason": reason, "source_sha256": digest(original),
                       "previous_translation_sha256": digest(old), "translation_sha256": digest(text)})
    bundle = {"format": 3, "origin": "reviewed mainland corrections with dual digest binding",
              "entries": entries, "corrections": corrections}
    return bundle, preview, {"corrected_rows": len(corrections), "by_reason": dict(counts), "review": review}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("previous", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--additions", type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise ValueError("Destination must be new")
    from opencc import OpenCC
    raw_source, raw_previous = args.source.read_bytes(), args.previous.read_bytes()
    additions = None
    if args.additions:
        with gzip.open(args.additions, "rt", encoding="utf-8") as stream:
            additions = json.load(stream)
    bundle, preview, report = build(json.loads(raw_source), json.loads(raw_previous), additions, OpenCC("t2s"))
    report["inputs"] = {"source_sha256": hashlib.sha256(raw_source).hexdigest(),
                        "previous_sha256": hashlib.sha256(raw_previous).hexdigest()}
    args.destination.mkdir(parents=True)
    with gzip.open(args.destination / "corrections.json.gz", "xb") as stream:
        stream.write(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    for name, data in (("preview.json", preview), ("review.json", report)):
        with (args.destination / name).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: value for key, value in report.items() if key != "review"}, indent=2))


if __name__ == "__main__":
    main()
