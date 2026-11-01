"""Build a self-contained Windows Japanese-entry helper from reviewed bundles.

This does not install localization, launch the game, or publish an artifact.
Each client bundle is fixed by its metadata hash inside the executable.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from entry_bundle import load_bundle, sha
from entry_host import PROTOCOL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundles', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--clients', nargs='+', choices=('steam', 'purple'), default=['steam', 'purple'])
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Build on Windows')
    if args.destination.exists():
        parser.error('Destination must be new')
    bundles = args.bundles.resolve(strict=True)
    destination = args.destination.resolve()
    bindings = {}
    for client in dict.fromkeys(args.clients):
        directory = bundles / client
        binding = sha((directory / 'bundle.json').read_bytes())
        load_bundle(directory, client, binding)
        bindings[client] = binding
    source = Path(__file__).resolve().parent
    destination.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='atreia-entry-build-') as temporary:
        temporary = Path(temporary)
        (temporary / 'entry_bundle_bindings.py').write_text('BINDINGS = ' + repr(bindings) + '\n', encoding='utf-8')
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--console',
                   '--name', 'Atreia-Localization-Bridge', '--distpath', str(destination),
                   '--workpath', str(temporary / 'work'), '--specpath', str(temporary),
                   '--paths', str(source), '--paths', str(temporary)]
        for client in bindings:
            command.extend(['--add-data', str(bundles / client) + ';entry-bundles/' + client])
        command.append(str(source / 'entry_host.py'))
        subprocess.run(command, check=True)
    executable = destination / 'Atreia-Localization-Bridge.exe'
    check = subprocess.run([str(executable), '--protocol'], capture_output=True, timeout=30, check=True)
    if len(check.stdout) > 4096 or json.loads(check.stdout.decode('utf-8-sig')) != PROTOCOL:
        raise ValueError('Frozen helper protocol verification failed')
    dependencies = {name: importlib.metadata.version(name) for name in ('pyinstaller', 'blake3', 'cryptography', 'lz4')}
    source_files = ('entry_host.py', 'entry_bundle.py', 'entry_container.py', 'entry_transaction.py', 'japanese_mapping.py', 'locale_codec.py')
    manifest = {'protocol': PROTOCOL, 'bundle_sha256': bindings, 'dependencies': dependencies,
                'source_sha256': {name: sha((source / name).read_bytes()) for name in source_files},
                'executable_sha256': sha(executable.read_bytes()), 'python': sys.version.split()[0]}
    (destination / 'build.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'clients': list(bindings), 'executable_sha256': manifest['executable_sha256']}))


if __name__ == '__main__':
    main()
