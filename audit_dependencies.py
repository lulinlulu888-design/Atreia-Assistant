"""Create a local dependency/license inventory, not a release-compliance claim."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


UPSTREAM_REVISION = "70aade3fef1ef8b15fe5ce3d27cfdbfc5f854b98"


def inventory(metadata):
    packages = metadata.get("packages")
    if not isinstance(packages, list):
        raise ValueError("Cargo metadata must contain packages")
    result = []
    for package in packages:
        license_expression = package.get("license")
        source = package.get("source") or ""
        evidence = "cargo_manifest" if license_expression else "missing"
        # Explicitly documented repository-level license; do not guess by name.
        if (package["name"] == "a2tools-dps-meter"
                and source.split("?", 1)[0].split("#", 1)[0] == "git+https://github.com/taengu/A2Tools-DPS-Meter.git"
                and source.endswith("#" + UPSTREAM_REVISION)):
            license_expression = "GPL-3.0 (repository-level LICENSE)"
            evidence = "pinned_upstream_repository_license"
        result.append({"name": package["name"], "version": package["version"],
                       "license_expression": license_expression,
                       "license_evidence": evidence,
                       "source_kind": "git" if source.startswith("git+") else "registry" if source.startswith("registry+") else "local"})
    return sorted(result, key=lambda item: (item["name"], item["version"]))


def collect_license_files(package, destination):
    root = Path(package["manifest_path"]).parent.resolve()
    requested = package.get("license_file")
    files = set()
    for path in root.iterdir():
        if path.is_file() and path.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE", "UNICODE-LICENSE")):
            files.add(path)
    if requested:
        path = (root / requested).resolve()
        # External repository licenses are handled separately, never copied
        # by following arbitrary ../ paths in third-party manifest data.
        if path.is_relative_to(root) and path.is_file():
            files.add(path)
    copied = []
    for index, path in enumerate(sorted(files)):
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or path.stat().st_size > 2 * 1024 * 1024:
            continue
        destination.mkdir(parents=True, exist_ok=True)
        name = f"{index}-{path.name}"
        shutil.copyfile(path, destination / name)
        copied.append(name)
    return copied


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="New output directory; existing paths are refused")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    completed = subprocess.run(["cargo", "metadata", "--offline", "--locked", "--format-version", "1",
        "--filter-platform", "x86_64-pc-windows-msvc", "--manifest-path", str(root / "backend/Cargo.toml")],
        capture_output=True, timeout=120, check=True)
    metadata = json.loads(completed.stdout)
    records = inventory(metadata)
    args.output.mkdir(parents=True, exist_ok=False)
    packages = {(package["name"], package["version"]): package for package in metadata["packages"]}
    for index, record in enumerate(records):
        destination = args.output / "licenses" / str(index)
        copied = collect_license_files(packages[(record["name"], record["version"])], destination)
        is_project_backend = Path(packages[(record["name"], record["version"])]["manifest_path"]).resolve() == (root / "backend/Cargo.toml").resolve()
        if record["license_evidence"] == "pinned_upstream_repository_license" or is_project_backend:
            # Root LICENSE was compared with the unmodified upstream GPL text;
            # preserve attribution separately in THIRD_PARTY_NOTICES.md.
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / "LICENSE", destination / "repository-GPLv3.txt")
            shutil.copyfile(root / "THIRD_PARTY_NOTICES.md", destination / "source-attribution.md")
            copied += ["repository-GPLv3.txt", "source-attribution.md"]
        record["license_files"] = [f"licenses/{index}/{name}" for name in copied]
    report = {"target": "x86_64-pc-windows-msvc", "packages": records,
              "release_audit_complete": False,
              "remaining_checks": ["corresponding buildable source bundle",
                  "Python/Tcl/Tk and other bundled runtime notices",
                  "full license-expression and binary-distribution review",
                  "real Steam/PURPLE compatibility verification"]}
    (args.output / "dependencies.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"package_count": len(records),
        "missing_license_evidence": sum(record["license_evidence"] == "missing" for record in records),
        "without_copied_license_text": sum(not record["license_files"] for record in records),
        "release_audit_complete": False}))


if __name__ == "__main__":
    main()
