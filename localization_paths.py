"""Read-only localization installation discovery. No game files are changed."""
from dataclasses import dataclass
import os
from pathlib import Path
import re

PAK = Path("Aion2/Content/Paks/L10N/Text/en-US/pakchunk502000-Windows_0_P.pak")
DAT = Path("Aion2/Content/L10N/Text/en-US/L10NString.dat")


@dataclass(frozen=True)
class LocalizationInstallation:
    root: Path
    client: str
    original_pak_present: bool
    tool_marker_present: bool
    backup_present: bool
    state_present: bool

    @property
    def status(self):
        if self.tool_marker_present:
            return "检测到原汉化工具的安装标记；备份完整性仍需安装引擎校验"
        if self.original_pak_present:
            return "找到英文语言包；尚未检查版本与译文兼容性"
        return "缺少英文语言包，不能开始汉化"


def normalize_game_root(selected):
    root = Path(selected).resolve()
    if root.is_file():
        root = root.parent
    for _ in range(7):
        if (root / "Aion2/Content").is_dir():
            return root
        child = root / "AION2"
        if (child / "Aion2/Content").is_dir():
            return child
        if root.parent == root:
            break
        root = root.parent
    raise ValueError("所选位置不是可识别的 AION2 游戏目录")


def inspect_installation(selected, client):
    if client not in ("steam", "purple"):
        raise ValueError("未知游戏客户端")
    root = normalize_game_root(selected)
    pak = root / PAK
    marker = False
    if pak.is_file():
        with pak.open("rb") as stream:
            marker = stream.read(8) == b"AION2CN "
    # A backup's presence does not prove its hash, generation, or completeness.
    backup = Path(str(pak) + ".aion2cn.v2.backup").is_file() or Path(str(pak) + ".tool_bak").is_file()
    return LocalizationInstallation(root, client, pak.is_file() and not marker, marker,
                                    backup, (root / DAT.parent / "Aion2CNTool.state").is_file())


def library_paths(text):
    if not isinstance(text, str) or len(text) > 2 * 1024 * 1024:
        raise ValueError("Steam 库配置过大或无效")
    result = []
    # Only read Steam's path values; never execute VDF data or expand variables.
    for value in re.findall(r'"path"\s+"((?:[^"\\]|\\.)*)"', text, re.IGNORECASE):
        value = value.replace("\\\\", "\\").replace('\\"', '"')
        if value and "\x00" not in value:
            result.append(Path(value))
    return result


def discover_steam(roots):
    libraries = list(roots)
    for root in roots:
        config = Path(root) / "steamapps/libraryfolders.vdf"
        try:
            if config.stat().st_size <= 2 * 1024 * 1024:
                libraries.extend(library_paths(config.read_text(encoding="utf-8-sig")))
        except (OSError, UnicodeError, ValueError):
            continue
    result, seen = [], set()
    for library in libraries:
        try:
            candidate = Path(library) / "steamapps/common/AION2"
            record = inspect_installation(candidate, "steam")
            key = os.path.normcase(str(record.root))
            if key not in seen:
                result.append(record)
                seen.add(key)
        except (OSError, ValueError):
            continue
    return result


def windows_steam_roots():
    if os.name != "nt":
        return []
    import winreg
    result = []
    for hive, key, name in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")):
        try:
            with winreg.OpenKey(hive, key) as handle:
                value, _ = winreg.QueryValueEx(handle, name)
                if isinstance(value, str) and value:
                    result.append(Path(value))
        except OSError:
            pass
    result.extend((Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam")))
    return result
