"""Collect licenses for the frozen Japanese helper and its build dependencies."""
import argparse
from importlib import metadata
import json
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=False)
    records = []
    # Include transitive dependencies in the build environment as well as the
    # frozen runtime. Package metadata licenses do not contain local secrets.
    for distribution in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
        name, version = distribution.metadata['Name'], distribution.version
        destination = args.destination / (name + '-' + version)
        files = []
        for relative in distribution.files or ():
            if relative.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE')):
                source = distribution.locate_file(relative)
                if source.is_file():
                    destination.mkdir(exist_ok=True)
                    target = destination / (str(len(files)) + '-' + source.name)
                    shutil.copyfile(source, target)
                    files.append(target.name)
        records.append({'name': name, 'version': version, 'license': distribution.metadata.get('License-Expression') or distribution.metadata.get('License'), 'files': files})
    for required in ('blake3', 'cryptography', 'lz4', 'pyinstaller'):
        record = next((r for r in records if r['name'].lower() == required), None)
        if not record or not record['files']:
            raise ValueError('Missing required runtime notice: ' + required)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise ValueError('Python runtime license is missing')
    shutil.copyfile(python_license, args.destination / 'PYTHON-LICENSE.txt')
    (args.destination / 'dependencies.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Collected Python helper dependency notices')


if __name__ == '__main__':
    main()
