"""Independently verify the installed fixture against the reviewed Steam update."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from audit_generated_payload import audit
from build_steam_26077854 import SOURCE_HASH
from locale_codec import decode, read_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "payload", "source"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError("Unreviewed Steam source snapshot")
    report = audit(args.manifest, args.payload, args.source, "steam")
    generated = decode(args.payload, read_manifest(args.manifest), "en-US")
    reviews = json.loads(Path(__file__).with_name("steam_26077854_global_reviewed.json").read_text(encoding="utf-8"))["records"]
    missing = [row["key"] for row in reviews if generated[row["key"]] != row["translation"]]
    if missing:
        raise ValueError("Reviewed global corrections did not apply: " + ", ".join(missing[:5]))
    # Test/song assets, key names and brands are not narrative paragraphs.
    # This catches whole-English prose; mixed-language semantic review remains
    # explicit in the source-bound records and is not inferred from this regex.
    remaining = []
    for key, text in generated.items():
        if not key.startswith(("QuestString_", "NoteData_Note_", "String_STR_ITEM_", "String_STR_Desc_Map_")):
            continue
        visible = re.sub(r"<[^>]*>|\{[^}]*\}", "", text)
        if (not re.search(r"[\u3400-\u9fff]", visible)
                and re.search(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}\s+[A-Za-z]{3,}", visible)):
            remaining.append(key)
    if remaining:
        raise ValueError("Whole-English narrative/chest/dungeon prose remains: " + ", ".join(remaining[:5]))
    report.update({"verified_global_reviews": len(reviews),
                   "global_reviews_by_type": dict(Counter(row["key"].split("_", 1)[0] for row in reviews)),
                   "whole_english_target_paragraphs": len(remaining)})
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
