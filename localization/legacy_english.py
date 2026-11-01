"""Recover our v2.4.0 English entry before switching to Japanese.

No guessed backup, third-party DAT, or running-game mutation is accepted.
The official English package hashes must come from the reviewed bundle.
"""
import json
import re
from pathlib import Path
from uuid import uuid4
from entry_transaction import JapaneseEntryTransaction, digest

EN_NAMES = tuple('pakchunk502000-Windows_0_P' + ext for ext in ('.pak', '.sig', '.ucas', '.utoc'))


class LegacyEnglishRecovery:
    def __init__(self, root, ensure_closed, official_hashes):
        if set(official_hashes) != set(EN_NAMES) or not all(re.fullmatch('[a-f0-9]{64}', v) for v in official_hashes.values()):
            raise ValueError('Complete reviewed English package hashes required')
        self.io = JapaneseEntryTransaction(root, ensure_closed)
        self.root = self.io.root
        self.hashes = official_hashes
        self.paks = self.root / 'Aion2/Content/Paks/L10N/Text/en-US'
        dat_dir = self.root / 'Aion2/Content/L10N/Text/en-US'
        self.paths = {'pak': self.paks / EN_NAMES[0], 'dat': dat_dir / 'L10NString.dat',
                      'legacy_state': dat_dir / 'Aion2CNTool.state'}
        self.recovery = self.root / 'Atreia_English_Entry_Recovery'
        self.journal = self.recovery / 'state.json'
        self.io.paths, self.io.state = self.paths, self.journal
        for path in (*self.paths.values(), self.journal):
            self.io._check_path(path)

    def _read(self, path):
        self.io._check_path(path)
        return path.read_bytes() if path.is_file() else None

    def _sidecars(self):
        for name in EN_NAMES[1:]:
            data = self._read(self.paks / name)
            if data is None or digest(data) != self.hashes[name]:
                raise ValueError('English sidecar changed; legacy recovery refused')

    def _pending(self):
        data = self._read(self.journal)
        if data is None:
            return None
        if len(data) > 65536:
            raise ValueError('English recovery journal too large')
        plan = json.loads(data.decode('utf-8'))
        if plan.get('format') != 1 or plan.get('entry') != 'en-US' or not re.fullmatch('[a-f0-9]{32}', plan.get('generation', '')):
            raise ValueError('Invalid English recovery journal')
        if plan.get('status') not in ('preparing', 'restored', 'rolled_back'):
            raise ValueError('Unknown English recovery status')
        if plan.get('status') == 'preparing' and plan.get('official_hashes') != self.hashes:
            raise ValueError('English recovery belongs to another game build')
        return plan if plan.get('status') == 'preparing' else None

    def _plan(self):
        pending = self._pending()
        if pending:
            self._sidecars()
            return pending
        pak = self._read(self.paths['pak'])
        self._sidecars()
        if pak is not None and digest(pak) == self.hashes[EN_NAMES[0]]:
            return None
        if not pak or len(pak) > 1024 or not pak.startswith(b'AION2CN 2.4.0 '):
            raise ValueError('Unknown English package; restore refused')
        state_bytes = self._read(self.paths['legacy_state'])
        if state_bytes is None or len(state_bytes) > 65536:
            raise ValueError('Missing or oversized legacy English state')
        state = {}
        for line in state_bytes.decode('utf-8-sig').splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                if key in state:
                    raise ValueError('Duplicate legacy state field')
                state[key] = value
        if state.get('format') != '2' or state.get('status') != 'installed' or state.get('had_dat') not in ('True', 'False'):
            raise ValueError('Unsupported legacy English state')
        if state.get('pre_pak_hash', '').lower() != self.hashes[EN_NAMES[0]]:
            raise ValueError('Legacy English backup is from another build')
        original_pak = self._read(self.paths['pak'].with_name(self.paths['pak'].name + '.aion2cn.v2.backup'))
        if original_pak is None or digest(original_pak) != self.hashes[EN_NAMES[0]]:
            raise ValueError('Legacy English original package hash mismatch')
        current_dat = self._read(self.paths['dat'])
        if current_dat is None or digest(current_dat) != state.get('payload_hash', '').lower():
            raise ValueError('Legacy English translation has changed')
        original_dat = None
        if state['had_dat'] == 'True':
            original_dat = self._read(self.paths['dat'].with_name('L10NString.dat.aion2cn.v2.backup'))
            if original_dat is None or digest(original_dat) != state.get('pre_dat_hash', '').lower():
                raise ValueError('Legacy original loose English table hash mismatch')
        state['status'] = 'restored'
        state['migrated_to'] = 'atreia-ja-JP'
        restored_state = ('\r\n'.join(k + '=' + v for k, v in state.items()) + '\r\n').encode('utf-8')
        return {'before_bytes': {'pak': pak, 'dat': current_dat, 'legacy_state': state_bytes},
                'after_bytes': {'pak': original_pak, 'dat': original_dat, 'legacy_state': restored_state}}

    def _material(self, plan, phase):
        expected = plan.get(phase)
        if not isinstance(expected, dict) or set(expected) != set(self.paths):
            raise ValueError('Invalid English recovery file set')
        result = {}
        for name, hash_value in expected.items():
            path = self.recovery / plan['generation'] / (name + '.' + phase)
            data = self._read(path)
            if hash_value is not None and (data is None or digest(data) != hash_value):
                raise ValueError('English recovery snapshot hash mismatch')
            if hash_value is None and data is not None:
                raise ValueError('Unexpected English recovery snapshot')
            result[name] = data
        return result

    def inspect(self):
        plan = self._plan()
        return {'status': 'restore_required' if plan else 'official_unchanged'}

    def recover(self):
        self.io._closed()
        plan = self._plan()
        if plan is None:
            return {'status': 'official_unchanged'}
        if 'before_bytes' in plan:
            before, after = plan['before_bytes'], plan['after_bytes']
            plan = {'format': 1, 'entry': 'en-US', 'status': 'preparing', 'generation': uuid4().hex,
                    'official_hashes': self.hashes,
                    'before': {k: digest(v) if v is not None else None for k, v in before.items()},
                    'after': {k: digest(v) if v is not None else None for k, v in after.items()}}
            directory = self.recovery / plan['generation']
            self.io._check_path(directory)
            directory.mkdir(parents=True, exist_ok=False)
            for phase, files in (('before', before), ('after', after)):
                for name, data in files.items():
                    if data is not None:
                        with (directory / (name + '.' + phase)).open('xb') as stream:
                            stream.write(data)
        before, after = self._material(plan, 'before'), self._material(plan, 'after')
        if digest(after['pak']) != self.hashes[EN_NAMES[0]]:
            raise ValueError('Recovery target is not the current official English package')
        self.io._closed()
        self._sidecars()
        for name, path in self.paths.items():
            if self._read(path) not in (before[name], after[name]):
                raise ValueError('English files changed during recovery preparation')
        self.io._atomic(self.journal, json.dumps(plan, indent=2).encode('utf-8'))
        try:
            for name, data in after.items():
                if data is None:
                    self.paths[name].unlink(missing_ok=True)
                else:
                    self.io._atomic(self.paths[name], data)
            if any(self._read(path) != after[name] for name, path in self.paths.items()):
                raise ValueError('English restore verification failed')
            plan['status'] = 'restored'
            self.io._atomic(self.journal, json.dumps(plan, indent=2).encode('utf-8'))
        except BaseException:
            for name, data in before.items():
                if data is None:
                    self.paths[name].unlink(missing_ok=True)
                else:
                    self.io._atomic(self.paths[name], data)
            plan['status'] = 'rolled_back'
            self.io._atomic(self.journal, json.dumps(plan, indent=2).encode('utf-8'))
            raise
        return {'status': 'restored'}
