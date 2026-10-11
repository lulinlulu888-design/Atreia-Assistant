"""Build Steam additions from the pinned local review, never from key similarity."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re

from build_client_variants import steam_update_replacement
from build_official_additions import PARAMETERS
from steam_release_review import EXACT, KEYED, patterned
from steam_skill_review import SKILLS

SOURCE_HASH = "f8c79eb669613ba68aaff45a22395b9cd12138631253d5789f96b023330254bf"
PREVIOUS_HASH = "c2cd40df54ac864e7a8526c6f0adf1057c173656699661d2438ede79160c9b41"
SERVER_CODES = frozenset(("RUT", "TAS", "RED", "HIT", "GAU", "LAM", "TIE", "HEL"))
VARIABLES = re.compile(r"\{[^}]*\}")
MARKERS = re.compile(r"@(\d+)@")


def mask(text):
    tokens = []
    def replace(match):
        tokens.append(match[0])
        return "@" + str(len(tokens) - 1) + "@"
    return VARIABLES.sub(replace, text), tokens


def restore(template, tokens):
    indices = [int(index) for index in MARKERS.findall(template)]
    if sorted(indices) != list(range(len(tokens))):
        raise ValueError("Template must retain every runtime expression exactly once")
    return MARKERS.sub(lambda match: tokens[int(match[1])], template)


def templates(source):
    result = {}
    for key, translation in {**SKILLS, **KEYED}.items():
        text, tokens = mask(source[key])
        category = key.split("_", 1)[0]
        identity = category, text
        if identity in result and result[identity] != translation:
            raise ValueError("Conflicting reviewed templates")
        restore(translation, tokens)
        result[identity] = translation
    return result


def replacement(key, source, reviewed):
    masked, tokens = mask(source)
    template = reviewed.get((key.split("_", 1)[0], masked))
    if template is not None:
        return restore(template, tokens)
    if source in EXACT:
        return EXACT[source]
    text = patterned(key, source)
    return text if text is not None else steam_update_replacement(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "previous", "existing", "report", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError("Unreviewed Steam source snapshot")
    if hashlib.sha256(args.previous.read_bytes()).hexdigest() != PREVIOUS_HASH:
        raise ValueError("Unreviewed baseline translation snapshot")
    source = json.loads(args.source.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    with gzip.open(args.existing, "rt", encoding="utf-8") as stream:
        bundle = json.load(stream)
    if bundle["format"] != 1:
        raise ValueError("Expected original source-bound baseline additions")
    reviewed = templates(source)
    missing, replaced, codes = [], 0, 0
    for key in report["RemainingEnglishCandidateKeys"]:
        text = replacement(key, source[key], reviewed)
        if text is None:
            if re.fullmatch(r"ServerName_[0-9]+_short_desc", key) and source[key] in SERVER_CODES:
                codes += 1
                continue
            missing.append({"key": key, "source": source[key]})
            continue
        if sorted(PARAMETERS.findall(source[key])) != sorted(PARAMETERS.findall(text)):
            raise ValueError("Runtime parameter mismatch: " + key)
        bundle["entries"][key] = {"source_sha256": hashlib.sha256(source[key].encode()).hexdigest(), "translation": text}
        replaced += 1
    if missing:
        print(json.dumps(missing, ensure_ascii=False, indent=2))
        raise ValueError(f"{len(missing)} rows still require review; no release resource written")
    bundle["origin"] = "reviewed Steam 25800038 baseline and manually reviewed source-bound additions"
    with gzip.open(args.output, "xb") as stream:
        stream.write(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode())
    print(json.dumps({"reviewed_translations": replaced, "preserved_server_identifiers": codes}))


if __name__ == "__main__":
    main()
