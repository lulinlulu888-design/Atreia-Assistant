"""Build a source-bound update only after every candidate has been reviewed."""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re

from build_official_additions import PARAMETERS
from steam_26077854_review import replacement

SOURCE_HASH = "6cff77bce26125541e7bc7999b8e4a43e859db2d8d3b09bed8eeffa0d648638d"
BASE_JSON_HASH = "94569d872871395d3e74fe0a43a4099ab8250dece33cd4d11a275e5df5797339"
REPORT_HASH = "bf856c067b9eb6b6594d32f3903a6b07fcff6959bb64d607c27ce0699576c469"
SERVER_CODES = frozenset(("RUT", "TAS", "RED", "HIT", "GAU", "LAM", "TIE", "HEL"))


def build(source, baseline, keys, reviewed=None):
    if baseline.get("format") != 3 or len(keys) != len(set(keys)):
        raise ValueError("Invalid baseline or duplicate review keys")
    result = deepcopy(baseline)
    remaining, translated, identifiers = [], 0, 0
    for key in keys:
        original = source[key]
        if re.fullmatch(r"ServerName_[0-9]+_short_desc", key) and original in SERVER_CODES:
            identifiers += 1
            continue
        text = replacement(key, original)
        if text is None and reviewed is not None:
            text = reviewed.get(hashlib.sha256(original.encode("utf-8")).hexdigest())
        if text is None:
            remaining.append(key)
            continue
        if sorted(PARAMETERS.findall(original)) != sorted(PARAMETERS.findall(text)):
            raise ValueError("Runtime parameter mismatch: " + key)
        variant = {"source_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(), "translation": text}
        variants = result["entries"].setdefault(key, [])
        if any(item["source_sha256"] == variant["source_sha256"] and item["translation"] != text for item in variants):
            raise ValueError("Conflicting source-bound translation: " + key)
        if variant not in variants:
            variants.append(variant)
        translated += 1
    return result, remaining, translated, identifiers


def apply_global_review(source, baseline, records):
    result = deepcopy(baseline)
    if len({record["key"] for record in records}) != len(records):
        raise ValueError("Duplicate global review keys")
    for record in records:
        key = record["key"]
        if hashlib.sha256(source[key].encode("utf-8")).hexdigest() != record["source_sha256"]:
            raise ValueError("Global review source mismatch: " + key)
        if sorted(PARAMETERS.findall(source[key])) != sorted(PARAMETERS.findall(record["translation"])):
            raise ValueError("Global review parameter mismatch: " + key)
        if record["previous_translation_sha256"] == record["source_sha256"]:
            entries = result["entries"].setdefault(key, [])
            entries[:] = [item for item in entries if item["source_sha256"] != record["source_sha256"]]
            entries.append({name: record[name] for name in ("source_sha256", "translation")})
        else:
            corrections = result["corrections"].setdefault(key, [])
            chained = [item for item in corrections if item["source_sha256"] == record["source_sha256"] and hashlib.sha256(item["translation"].encode("utf-8")).hexdigest() == record["previous_translation_sha256"]]
            previous = {item["previous_translation_sha256"] for item in chained} or {record["previous_translation_sha256"]}
            # The native correction pass selects once, so compose a reviewed
            # revision with the original previous-text binding at build time.
            corrections[:] = [item for item in corrections if not (item["source_sha256"] == record["source_sha256"] and item["previous_translation_sha256"] in previous)]
            for previous_digest in sorted(previous):
                corrections.append({"source_sha256": record["source_sha256"], "previous_translation_sha256": previous_digest, "translation": record["translation"]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "baseline", "report", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    for path, expected in ((args.source, SOURCE_HASH), (args.report, REPORT_HASH)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Unreviewed input snapshot: " + str(path))
    source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    raw_baseline = gzip.decompress(args.baseline.read_bytes())
    if hashlib.sha256(raw_baseline).hexdigest() != BASE_JSON_HASH:
        raise ValueError("Unreviewed released dual-client baseline")
    baseline = json.loads(raw_baseline)
    review = json.loads(Path(__file__).with_name("steam_26077854_reviewed.json").read_text(encoding="utf-8"))
    if review["source_snapshot_sha256"] != SOURCE_HASH:
        raise ValueError("Review belongs to a different source snapshot")
    result, remaining, translated, identifiers = build(source, baseline, report["RemainingEnglishCandidateKeys"], review["translations"])
    print(json.dumps({"reviewed": translated, "identifiers": identifiers, "remaining": len(remaining),
                      "remaining_by_type": dict(Counter(key.split("_", 1)[0] for key in remaining))}, ensure_ascii=False))
    if remaining:
        raise ValueError("Unreviewed text remains; no installable resource was written")
    global_review = json.loads(Path(__file__).with_name("steam_26077854_global_reviewed.json").read_text(encoding="utf-8"))
    if global_review["source_snapshot_sha256"] != SOURCE_HASH:
        raise ValueError("Global review belongs to a different source snapshot")
    result = apply_global_review(source, result, global_review["records"])
    print("Global narrative, chest and dungeon reviews:", len(global_review["records"]))
    result["origin"] = "reviewed Steam 26077854 additions with source-bound mainland corrections"
    with args.output.open("xb") as stream:
        stream.write(gzip.compress(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), mtime=0))


if __name__ == "__main__":
    main()
