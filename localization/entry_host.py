"""Offline Japanese-entry helper protocol for the desktop application.

Frozen builds embed entry_bundle_bindings.BINDINGS and matching reviewed bundles.
Development may call execute() with explicit test bindings; the CLI never accepts
an arbitrary translation path or downloads a payload.
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys

from entry_bundle import load_bundle, verify_original_packages
from entry_transaction import JapaneseEntryTransaction, NAMES
from legacy_english import LegacyEnglishRecovery

PROTOCOL = {'protocol': 1, 'entry': 'ja-JP', 'operations': ['inspect', 'install', 'restore']}


def ensure_game_closed():
    if os.name != 'nt':
        raise RuntimeError('此汉化安装程序仅支持 Windows。')
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
                    ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ('Process32FirstW', 'Process32NextW'):
        function = getattr(kernel, name)
        function.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
        function.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise RuntimeError('无法确认游戏进程状态，未修改游戏。')
    try:
        process = ProcessEntry()
        process.dwSize = ctypes.sizeof(process)
        found = kernel.Process32FirstW(snapshot, ctypes.byref(process))
        if not found:
            raise RuntimeError('无法读取游戏进程状态，未修改游戏。')
        while found:
            if process.szExeFile.casefold() in {'aion2.exe', 'aion2-win64-shipping.exe'}:
                raise RuntimeError('请先正常退出 AION2，再安装或还原汉化。')
            ctypes.set_last_error(0)
            found = kernel.Process32NextW(snapshot, ctypes.byref(process))
        if ctypes.get_last_error() != 18:
            raise RuntimeError('游戏进程检查未完整完成，未修改游戏。')
    finally:
        kernel.CloseHandle(snapshot)


def execute(operation, root, client, bundle_root, bindings, closed_check=ensure_game_closed):
    if operation not in PROTOCOL['operations'] or client not in ('steam', 'purple'):
        raise ValueError('未知汉化操作或客户端。')
    root = Path(root).resolve(strict=True)
    if not (root / 'Aion2/Content').is_dir():
        raise ValueError('请选择包含 Aion2/Content 的游戏根目录。')
    transaction = JapaneseEntryTransaction(root, closed_check)
    if operation == 'restore':
        if transaction._read_state() is None and client in bindings:
            metadata, _ = load_bundle(Path(bundle_root) / client, client, bindings[client])
            transaction.adopt_legacy(metadata['package_sha256'])
        result = transaction.restore()
        message = '已还原原始日文语言资源。'
    else:
        if client not in bindings:
            raise ValueError('安装包尚未包含此客户端已审核的日文入口组件。')
        metadata, payload = load_bundle(Path(bundle_root) / client, client, bindings[client])
        state = transaction._read_state()
        legacy = False
        if state and state['status'] == 'installed':
            transaction._originals(state)
            originals = {name: path for name, path in transaction.original_paths(state).items() if name in NAMES}
        else:
            originals = {name: transaction.paths[name] for name in NAMES}
            if not state and originals[NAMES[0]].is_file() and originals[NAMES[0]].stat().st_size == 0:
                originals = transaction.legacy_originals(metadata['package_sha256'])
                legacy = True
        try:
            verify_original_packages(metadata, originals)
        except FileNotFoundError:
            raise ValueError('缺少完整的官方日文语言包，请先安装日文文字资源或还原旧入口备份。') from None
        english = None
        if 'legacy_english_package_sha256' in metadata:
            english = LegacyEnglishRecovery(root, closed_check, metadata['legacy_english_package_sha256'])
            english.inspect()
        if operation == 'install':
            if english:
                english.recover()
            if legacy:
                transaction.adopt_legacy(metadata['package_sha256'])
            result = transaction.install(payload)
            message = '日文入口汉化安装完成。请将游戏文字语言设为“日本語”并重启客户端；语音保持原设置。'
        else:
            result = transaction.inspect()
            if legacy:
                result['status'] = 'legacy_ready_to_migrate'
            message = '已核对官方日文语言包及国服风格译文组件。安装后文字语言请选择“日本語”；语音保持原设置。'
    return {'ok': True, 'cancelled': False, 'operation': operation, 'client': client,
            'game_root': str(root), 'entry': 'ja-JP', 'state': result['status'], 'message': message}


def main():
    if sys.argv[1:] == ['--protocol']:
        print(json.dumps(PROTOCOL))
        return 0
    operation = sys.argv[2] if len(sys.argv) == 5 else 'invalid'
    client = sys.argv[4] if len(sys.argv) == 5 else None
    try:
        if len(sys.argv) != 5:
            raise ValueError('汉化组件参数无效。')
        # The first argument is retained for the existing desktop bridge ABI;
        # it is never executed and is not a translation input.
        from entry_bundle_bindings import BINDINGS
        bundle_root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'entry-bundles'
        result = execute(operation, sys.argv[3], client, bundle_root, BINDINGS)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps({'ok': False, 'cancelled': False, 'operation': operation,
                          'client': client, 'entry': 'ja-JP', 'message': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
