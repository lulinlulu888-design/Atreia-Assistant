"""Transactional Japanese-entry files only; no translation downloads or DAT reuse.

The native caller must provide its fail-closed game-process check. Payloads must
already have passed source/parameter/container validation. Recovery originals are
immutable, and a game update is never overwritten by restoring stale backups.
"""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

STEM = 'pakchunk503000-Windows_0_P'
EXTENSIONS = ('.pak', '.sig', '.ucas', '.utoc')
NAMES = tuple(STEM + extension for extension in EXTENSIONS)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class JapaneseEntryTransaction:
    def __init__(self, root, ensure_closed):
        self.root = Path(root).resolve(strict=True)
        self.ensure_closed = ensure_closed
        if not callable(ensure_closed):
            raise ValueError('A native game-closed check is required')
        self.paks = self.root / 'Aion2/Content/Paks/L10N/Text/ja-JP'
        self.dat = self.root / 'Aion2/Content/L10N/Text/ja-JP/L10NString.dat'
        self.recovery = self.root / 'Atreia_Japanese_Entry_Backup'
        self.state = self.recovery / 'state.json'
        self.paths = {name: self.paks / name for name in NAMES}
        self.paths['L10NString.dat'] = self.dat
        for path in (*self.paths.values(), self.state):
            self._check_path(path)

    def _check_path(self, path):
        path = Path(path)
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('Entry path escapes game root')
        relative = path.relative_to(self.root)
        current = self.root
        for part in relative.parts:
            current /= part
            if current.exists() and (current.is_symlink() or current.is_junction()):
                raise ValueError('Reparse paths are not supported')

    def _closed(self):
        self.ensure_closed()
        # Revalidate paths immediately before mutation, not only on discovery.
        for path in (*self.paths.values(), self.state):
            self._check_path(path)

    def _atomic(self, path, data):
        self._check_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_name(path.name + '.atreia-' + uuid4().hex + '.pending')
        try:
            with pending.open('xb') as stream:
                stream.write(data)
                stream.flush()
                import os
                os.fsync(stream.fileno())
            pending.replace(path)
        finally:
            if pending.exists():
                pending.unlink()

    def _save(self, state):
        self._atomic(self.state, json.dumps(state, ensure_ascii=False, indent=2).encode('utf-8'))

    def _read_state(self):
        if not self.state.exists():
            return None
        if self.state.stat().st_size > 65536:
            raise ValueError('Entry state too large')
        state = json.loads(self.state.read_text(encoding='utf-8'))
        if state.get('format') != 1 or state.get('entry') != 'ja-JP':
            raise ValueError('Unknown entry state')
        generation = state.get('generation', '')
        if len(generation) != 32 or any(c not in '0123456789abcdef' for c in generation):
            raise ValueError('Invalid recovery generation')
        if set(state.get('originals', {})) != set(self.paths):
            raise ValueError('Invalid original file set')
        return state

    def _backup_path(self, directory, name):
        raw, safe = directory / name, directory / (name + '.bak')
        for path in (raw, safe):
            self._check_path(path)
        if raw.exists() and safe.exists() and raw.read_bytes() != safe.read_bytes():
            raise ValueError('Conflicting backup copies: ' + name)
        return safe if safe.exists() else raw

    def original_paths(self, state):
        directory = self.recovery / state['generation']
        return {name: self._backup_path(directory, name) for name in state['originals']}

    def _originals(self, state):
        paths = self.original_paths(state)
        result = {}
        for name, expected in state['originals'].items():
            path = paths[name]
            self._check_path(path)
            if expected is None:
                if path.exists():
                    raise ValueError('Unexpected original file')
                result[name] = None
            else:
                data = path.read_bytes()
                if digest(data) != expected:
                    raise ValueError('Recovery original hash mismatch: ' + name)
                result[name] = data
        return result

    def _isolate_backups(self):
        """Rename only known backup package names; live resources are excluded.

        Both names remain readable during an interrupted migration. All conflicts
        are checked before the first rename, and no bytes are changed.
        """
        directories = [(self.root / 'Aion2_Japanese_Backup_Safe', NAMES),
                       (self.root / 'Aion2_English_Backup_Safe',
                        tuple(name.replace('503000', '502000') for name in NAMES))]
        self._check_path(self.recovery)
        if self.recovery.exists():
            for directory in self.recovery.iterdir():
                if len(directory.name) == 32 and all(c in '0123456789abcdef' for c in directory.name):
                    self._check_path(directory)
                    if directory.is_dir():
                        directories.append((directory, NAMES))
        pending = []
        for directory, names in directories:
            for name in names:
                self._backup_path(directory, name)  # validate both names, including conflicts
                raw, safe = directory / name, directory / (name + '.bak')
                if raw.is_file():
                    pending.append((raw, safe, digest(raw.read_bytes())))
        for raw, safe, expected in pending:
            self._closed()
            self._check_path(raw)
            self._check_path(safe)
            if digest(raw.read_bytes()) != expected or (safe.exists() and digest(safe.read_bytes()) != expected):
                raise ValueError('Backup changed during extension migration')
            if safe.exists():
                raw.unlink()  # identical .bak copy remains
            else:
                raw.rename(safe)
            if digest(safe.read_bytes()) != expected:
                raise ValueError('Backup migration verification failed')

    def _matches_installed(self, state):
        if not self.paths[NAMES[0]].is_file() or self.paths[NAMES[0]].stat().st_size:
            return False
        if any(self.paths[name].exists() for name in NAMES[1:]):
            return False
        return self.dat.is_file() and digest(self.dat.read_bytes()) == state.get('payload_sha256')

    def inspect(self):
        state = self._read_state()
        if state is None:
            return {'entry': 'ja-JP', 'status': 'not_managed', 'text_language': '日本語'}
        if state['status'] in ('preparing', 'restoring'):
            status = 'recovery_required'
        elif state['status'] == 'installed':
            status = 'installed' if self._matches_installed(state) else 'files_changed'
        else:
            status = state['status']
        return {'entry': 'ja-JP', 'status': status, 'text_language': '日本語'}

    def legacy_originals(self, expected_hashes):
        """Recognize the former Safe layout only against embedded official hashes.

        No legacy metadata or translation is trusted as an original. This is
        read-only so detection remains usable while the game is running.
        """
        if self._read_state() is not None or set(expected_hashes) != set(NAMES):
            raise ValueError('Legacy adoption requires an unmanaged entry and complete official bindings')
        if not self.paths[NAMES[0]].is_file() or self.paths[NAMES[0]].stat().st_size:
            raise ValueError('Not a legacy empty Japanese package')
        if any(self.paths[name].exists() for name in NAMES[1:]) or not self.dat.is_file():
            raise ValueError('Legacy Japanese layout is incomplete or has changed')
        paths = {name: self._backup_path(self.root / 'Aion2_Japanese_Backup_Safe', name) for name in NAMES}
        for name, path in paths.items():
            self._check_path(path)
            if not path.is_file() or digest(path.read_bytes()) != expected_hashes[name]:
                raise ValueError('Legacy original does not match the reviewed official package: ' + name)
        return paths

    def adopt_legacy(self, expected_hashes):
        """Create verified recovery state without changing any live game file."""
        self._closed()
        paths = self.legacy_originals(expected_hashes)
        original_bytes = {name: path.read_bytes() for name, path in paths.items()}
        legacy_payload = self.dat.read_bytes()
        state = {'format': 1, 'entry': 'ja-JP', 'generation': uuid4().hex,
                 'status': 'installed', 'payload_sha256': digest(legacy_payload),
                 'originals': dict(expected_hashes, **{'L10NString.dat': None}),
                 'migration': 'verified_safe_backup'}
        directory = self.recovery / state['generation']
        self._check_path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        for name, data in original_bytes.items():
            with (directory / (name + '.bak')).open('xb') as stream:
                stream.write(data)
        # Preserve the pre-migration translation for diagnostics/rollback; it
        # must never become the "original" restored into the game.
        with (directory / 'legacy-L10NString.dat').open('xb') as stream:
            stream.write(legacy_payload)
        self._originals(state)
        self._closed()
        self.legacy_originals(expected_hashes)
        if not self._matches_installed(state):
            raise ValueError('Legacy game files changed during migration preparation')
        self._save(state)
        return self.inspect()

    def install(self, payload):
        self._closed()
        if not isinstance(payload, bytes) or len(payload) < 68 or payload[:4] != bytes((2, 0, 0, 0)):
            raise ValueError('Expected an audited Japanese DAT container')
        previous = self._read_state()
        if previous and previous['status'] in ('preparing', 'restoring'):
            raise ValueError('Recover the interrupted transaction before reinstalling')
        if previous and previous['status'] == 'installed' and not self._matches_installed(previous):
            raise ValueError('Game files changed; reconcile updated originals before installation')
        before = {name: path.read_bytes() if path.is_file() else None for name, path in self.paths.items()}
        if previous and previous['status'] == 'installed':
            self._originals(previous)
            state = dict(previous)
        else:
            if any(before[name] is None for name in NAMES) or not before[NAMES[0]]:
                raise ValueError('Complete official Japanese package required; legacy empty packages need recovery first')
            state = {'format': 1, 'entry': 'ja-JP', 'generation': uuid4().hex,
                     'originals': {name: digest(data) if data is not None else None for name, data in before.items()}}
            directory = self.recovery / state['generation']
            directory.mkdir(parents=True, exist_ok=False)
            for name, data in before.items():
                if data is not None:
                    with (directory / (name + '.bak')).open('xb') as stream:
                        stream.write(data)
            self._originals(state)
        self._closed()
        if any((path.read_bytes() if path.is_file() else None) != before[name] for name, path in self.paths.items()):
            raise ValueError('Game resources changed during preparation')
        self._isolate_backups()
        state.update(status='preparing', payload_sha256=digest(payload),
                     previous_payload_sha256=previous.get('payload_sha256') if previous else None)
        self._save(state)
        try:
            self._atomic(self.dat, payload)
            self._atomic(self.paths[NAMES[0]], b'')
            for name in NAMES[1:]:
                self.paths[name].unlink(missing_ok=True)
            if not self._matches_installed(state):
                raise ValueError('Installed files failed verification')
            state['status'] = 'installed'
            self._save(state)
        except BaseException:
            # Preserve the pre-operation installation on an ordinary failure.
            # If rollback itself fails, preparing state and originals survive.
            self._write_files(before)
            if previous:
                self._save(previous)
            else:
                state['status'] = 'rolled_back'
                self._save(state)
            raise
        return self.inspect()

    def _write_files(self, files):
        for name, data in files.items():
            path = self.paths[name]
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                self._atomic(path, data)

    def restore(self):
        self._closed()
        state = self._read_state()
        if not state:
            raise ValueError('No managed Japanese-entry backup')
        if state['status'] == 'restored':
            return self.inspect()
        if state['status'] == 'installed' and not self._matches_installed(state):
            raise ValueError('Game update detected; stale restore refused')
        originals = self._originals(state)
        self._closed()
        if state['status'] in ('preparing', 'restoring'):
            for name, path in self.paths.items():
                actual = digest(path.read_bytes()) if path.is_file() else None
                allowed = {state['originals'][name]}
                if name == NAMES[0]:
                    allowed.add(digest(b''))
                elif name == 'L10NString.dat':
                    allowed.update((state.get('payload_sha256'), state.get('previous_payload_sha256')))
                else:
                    allowed.add(None)
                if actual not in allowed:
                    raise ValueError('Unrelated file change during interrupted transaction; refusing stale recovery')
        self._isolate_backups()
        state['status'] = 'restoring'
        self._save(state)
        self._write_files(originals)
        if any((path.read_bytes() if path.is_file() else None) != originals[name] for name, path in self.paths.items()):
            raise ValueError('Restored files failed verification')
        state['status'] = 'restored'
        self._save(state)
        return self.inspect()
