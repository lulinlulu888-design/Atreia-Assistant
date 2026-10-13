"""Independently decode an isolated generated payload and compare its source.

Requires the local codec dependencies, not the native engine. Reads only; no
game data or full text is printed or written by this audit.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from build_official_additions import PARAMETERS
from locale_codec import decode, read_manifest


def audit(manifest, payload, source, client, baseline=None, corrections=None):
    original = json.loads(source.read_text(encoding="utf-8"))
    generated = decode(payload, read_manifest(manifest), "en-US")
    if list(original) != list(generated):
        raise ValueError("Generated key count or order differs from current source")
    mismatches = [key for key in original
                  if sorted(PARAMETERS.findall(original[key])) != sorted(PARAMETERS.findall(generated[key]))]
    if mismatches:
        raise ValueError(f"Runtime parameter mismatch: {mismatches[:5]}")
    if client == "steam":
        expected = {
            "String_UI_SHOP_ENUM_CATEGORY_VEHICLE_body": "创始者礼包",
            "String_UI_LOGIN_SELECT_GAME_SERVER_MAINTENANCE_body": "该服务器正在维护。",
        }
        if any(generated.get(key) != value for key, value in expected.items()):
            raise ValueError("Reviewed Steam shop/maintenance translations differ")
        wing_key = "String_STR_ITEM_WING_L_DEFAULT_01_B_DESC_body"
        if "Flight Power: 2500" not in original.get(wing_key, "") or "飞行力：2500" not in generated.get(wing_key, ""):
            raise ValueError("Current Steam wing flight power was not preserved")
    if (baseline is None) != (corrections is None):
        raise ValueError("Baseline and corrections must be provided together")
    if baseline is not None:
        previous = json.loads(baseline.read_text(encoding="utf-8"))
        with gzip.open(corrections, "rt", encoding="utf-8") as stream:
            released = json.load(stream)
        for key, variants in released["corrections"].items():
            for variant in variants:
                if (hashlib.sha256(original[key].encode()).hexdigest() == variant["source_sha256"]
                        and hashlib.sha256(previous[key].encode()).hexdigest() == variant["previous_translation_sha256"]):
                    previous[key] = variant["translation"]
                    break
        if list(previous.items()) != list(generated.items()):
            raise ValueError("Generated output differs from the released corrected table")
    return {"client": client, "keys": len(generated), "same_order": True,
            "released_output_unchanged": baseline is not None,
            "parameter_mismatches": len(mismatches),
            "payload_sha256": hashlib.sha256(payload.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("payload", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("client", choices=("steam", "purple"))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--corrections", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.manifest, args.payload, args.source, args.client,
                           args.baseline, args.corrections), ensure_ascii=True))
