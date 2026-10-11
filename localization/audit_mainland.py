"""Read-only whole-table review. Candidates are not confirmed player-visible bugs.

Reports contain keys and digests, not complete game text. No game files are edited.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from build_official_additions import PARAMETERS, TOKENS, load_mainland_terms, mainland_terms
from mainland_names import MAINLAND_NAMES, source_names

LATIN = re.compile(r"[A-Za-z]{3,}")
TAGS = re.compile(r"<[^>]*>")
CONTEXT_TERMS = ("刺客", "牧师", "吟游诗人", "古文石", "奥德尔", "奥代尔",
                 "组合包", "捆绑包", "公会", "深渊", "档案", "天界之主")


def family(key):
    return "String_UI" if key.startswith("String_UI_") else key.split("_", 1)[0]


def audit(source, translated, converter=None):
    terms = load_mainland_terms(converter)
    rows, counts, groups = [], Counter(), {}
    for key, original in source.items():
        issues, details = [], {}
        if key not in translated:
            issues.append("missing_key")
        else:
            text = translated[key]
            prose = TOKENS.sub("", text)
            if LATIN.search(prose):
                issues.append("unchanged_latin" if text == original else "mixed_latin")
            if sorted(PARAMETERS.findall(original)) != sorted(PARAMETERS.findall(text)):
                issues.append("parameter_mismatch")
            # Different emphasis and translated bracket prose can be intentional.
            if TAGS.findall(original) != TAGS.findall(text):
                issues.append("tag_difference_review")
            normalized = mainland_terms(text, terms, original)
            if normalized != text:
                issues.append("terminology_candidate")
            if converter and converter.convert(prose) != prose:
                issues.append("traditional_candidate")
            context = [term for term in CONTEXT_TERMS if term in prose]
            if context:
                issues.append("context_review")
                details["context_terms"] = context
            names = source_names(TOKENS.sub("", original))
            missing_names = [MAINLAND_NAMES[name] for name in names if MAINLAND_NAMES[name] not in prose]
            if key.startswith("ServerName_"):
                if original in MAINLAND_NAMES and text != MAINLAND_NAMES[original]:
                    issues.append("server_name_mismatch")
                    details["expected_name"] = MAINLAND_NAMES[original]
                elif original not in MAINLAND_NAMES:
                    issues.append("server_name_unreviewed")
            elif missing_names:
                issues.append("lore_name_review")
                details["expected_names"] = missing_names
            if "\ufffd" in text:
                issues.append("replacement_character")
        if issues:
            rows.append({"key": key, "issues": issues,
                         "source_sha256": hashlib.sha256(original.encode()).hexdigest(), **details})
            counts.update(issues)
            groups.setdefault(family(key), Counter()).update(issues)
    extra = sorted(translated.keys() - source.keys())
    return {"source_keys": len(source), "translated_keys": len(translated),
            "same_key_order": list(source) == list(translated), "extra_keys": extra,
            "candidate_rows": len(rows), "counts": dict(sorted(counts.items())),
            "by_family": {key: dict(value) for key, value in sorted(groups.items())},
            "review": rows,
            "note": "Overlapping candidate categories; visibility and semantics need review, not a completion rate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("translation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--label", required=True, help="Identify snapshot/candidate/installed input")
    args = parser.parse_args()
    from opencc import OpenCC
    raw_source, raw_translation = args.source.read_bytes(), args.translation.read_bytes()
    report = audit(json.loads(raw_source), json.loads(raw_translation), OpenCC("t2s"))
    report["inputs"] = {"label": args.label,
                        "source_sha256": hashlib.sha256(raw_source).hexdigest(),
                        "translation_sha256": hashlib.sha256(raw_translation).hexdigest()}
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ("review", "by_family", "extra_keys")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
