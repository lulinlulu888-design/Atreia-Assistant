"""Collect desktop Cargo notices into a new local packaging directory."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from urllib.request import Request, urlopen
import re

from audit_dependencies import collect_license_files, inventory


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "Atreia-release-notices"}), timeout=30) as response:
        return response.read()


def upstream_notices(package, destination, cache):
    root = Path(package["manifest_path"]).parent
    repository = (package.get("repository") or "").rstrip("/").removesuffix(".git")
    if not re.fullmatch(r"https://github.com/[\w.-]+/[\w.-]+", repository):
        return [], None
    vcs = root / ".cargo_vcs_info.json"
    if not vcs.exists():
        return [], None
    revision = json.loads(vcs.read_text())["git"]["sha1"]
    if (package["name"], package["version"], repository) == ("convert_case", "0.4.0", "https://github.com/rutrum/convert-case"):
        # 0.4.0 declares MIT but omitted its text; retain its author/license
        # declaration alongside the same project's restored MIT license.
        revision = "e58d5ae2ee30e434f1ea19a63e35c7e6abae84ad"
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / "Cargo.toml", destination / "original-Cargo.toml")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid crate source revision")
    identity = repository, revision
    if identity not in cache:
        project = repository.removeprefix("https://github.com/")
        tree = json.loads(fetch(f"https://api.github.com/repos/{project}/git/trees/{revision}"))
        files = {}
        for item in tree["tree"]:
            name = item["path"]
            if item["type"] == "blob" and name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE", "COPYRIGHT")):
                files[name] = fetch(f"https://raw.githubusercontent.com/{project}/{revision}/{name}")
        cache[identity] = files
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in cache[identity].items():
        (destination / name).write_bytes(content)
    return [p.name for p in destination.iterdir() if p.is_file()], repository + "/tree/" + revision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fetch-missing", action="store_true", help="Fetch workspace notices at the crate's pinned source revision")
    parser.add_argument("--upstream-cache", type=Path, help="Previously collected notices directory for offline reuse")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = root / "desktop/src-tauri/Cargo.toml"
    result = subprocess.run(["cargo", "metadata", "--offline", "--locked", "--format-version", "1",
                             "--filter-platform", "x86_64-pc-windows-msvc", "--manifest-path", str(manifest)],
                            capture_output=True, check=True, timeout=120)
    metadata = json.loads(result.stdout)
    records = inventory(metadata)
    packages = {(p["name"], p["version"]): p for p in metadata["packages"]}
    args.output.mkdir(parents=True, exist_ok=False)
    cache = {}
    cached_records = {}
    if args.upstream_cache:
        cached_records = {(p["name"], p["version"]): p for p in json.loads((args.upstream_cache / "dependencies.json").read_text(encoding="utf-8"))}
    for item in records:
        package = packages[item["name"], item["version"]]
        directory = args.output / (item["name"] + "-" + item["version"])
        item["license_files"] = collect_license_files(package, directory)
        cached = cached_records.get((item["name"], item["version"]))
        if not item["license_files"] and cached and cached.get("notice_source"):
            source = args.upstream_cache / directory.name
            directory.mkdir(parents=True, exist_ok=True)
            for name in cached["license_files"]:
                if Path(name).name != name:
                    raise ValueError("Invalid cached notice path")
                shutil.copyfile(source / name, directory / name)
            item["license_files"] = cached["license_files"]
            item["notice_source"] = cached["notice_source"]
        if not item["license_files"] and args.fetch_missing:
            item["license_files"], item["notice_source"] = upstream_notices(package, directory, cache)
        # These old crates publish their Apache option in source/README, but
        # omit standalone license files. Retain that evidence and full text.
        legacy = {("fxhash", "0.2.1"): "lib.rs", ("mac", "0.1.1"): "README.md"}
        if not item["license_files"] and (item["name"], item["version"]) in legacy:
            evidence = Path(package["manifest_path"]).parent / legacy[item["name"], item["version"]]
            apache = next(Path(p["manifest_path"]).parent / "LICENSE-APACHE" for p in metadata["packages"]
                          if (Path(p["manifest_path"]).parent / "LICENSE-APACHE").is_file())
            if "Apache" not in evidence.read_text(encoding="utf-8"):
                raise ValueError("Missing declared Apache license option")
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(evidence, directory / "source-attribution.txt")
            shutil.copyfile(apache, directory / "LICENSE-APACHE")
            item["license_files"] = ["source-attribution.txt", "LICENSE-APACHE"]
            item["selected_license"] = "Apache-2.0"
        if Path(package["manifest_path"]).resolve() == manifest.resolve():
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / "LICENSE", directory / "LICENSE")
            item["license_expression"] = "GPL-3.0"
            item["license_evidence"] = "repository_LICENSE"
            item["license_files"].append("LICENSE")
    shutil.copyfile(root / "LICENSE", args.output / "LICENSE")
    shutil.copyfile(root / "THIRD_PARTY_NOTICES.md", args.output / "THIRD_PARTY_NOTICES.md")
    (args.output / "dependencies.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = [r["name"] + "@" + r["version"] for r in records if not r["license_expression"] or not r["license_files"]]
    frontend = []
    npm_manifest = json.loads((root / "desktop/package.json").read_text(encoding="utf-8"))
    for name in npm_manifest["dependencies"]:
        path = root / "desktop/node_modules" / name / "package.json"
        package = json.loads(path.read_text(encoding="utf-8"))
        files = collect_license_files({"manifest_path": str(path)}, args.output / ("npm-" + name.replace("/", "-")))
        frontend.append({"name": name, "version": package["version"], "license": package.get("license"), "license_files": files})
        if not package.get("license") or not files:
            missing.append(name)
    (args.output / "frontend-dependencies.json").write_text(json.dumps(frontend, indent=2), encoding="utf-8")
    print(json.dumps({"packages": len(records), "missing_notices": missing}))
    if missing:
        raise ValueError("Review missing notices before packaging")


if __name__ == "__main__":
    main()
