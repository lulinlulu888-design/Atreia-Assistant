"""Version-pinned legacy engine adapter. Writes require explicit caller consent.

No silent download, elevation, process termination, or game changes on import.
Install/restore are not killed on a timeout: the engine must finish or roll back.
"""
import hashlib
import json
from pathlib import Path
import subprocess
from localization_paths import inspect_installation

ENGINE_SHA256 = "1d01a3ab4c9604296da6b2265fd0a5a1247d628d31fd4ab02eb8bac539340e58"


def verify_engine(path):
    with Path(path).open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != ENGINE_SHA256:
        raise ValueError("汉化组件版本或校验值不匹配，不能启动")


class LocalizationEngine:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.helper = self.directory / "Atreia-Localization-Bridge.exe"
        self.engine = self.directory / "Aion2-Steam-CN-v2.4.0.exe"
        if not self.helper.is_file() or not self.engine.is_file():
            raise FileNotFoundError("尚未打包汉化引擎组件；不会自动下载或运行未知程序")
        verify_engine(self.engine)

    def execute(self, operation, installation, consented=False):
        if operation not in ("inspect", "install", "restore"):
            raise ValueError("未知汉化操作")
        if installation.client != "steam":
            raise ValueError("PURPLE 汉化安装尚未验证，不能套用 Steam 安装引擎")
        if operation != "inspect" and consented is not True:
            raise ValueError("修改游戏文件之前需要明确确认")
        # Revalidate the selected directory and engine immediately before use.
        current = inspect_installation(installation.root, installation.client)
        verify_engine(self.engine)
        args = [str(self.helper), str(self.engine), operation, str(current.root), "steam"]
        options = {"capture_output": True, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
                   "cwd": str(self.directory)}
        # Read-only inspection can time out; transactional writes must not be
        # interrupted by automatically killing their helper process.
        if operation == "inspect":
            options["timeout"] = 30
        completed = subprocess.run(args, **options)
        if len(completed.stdout) > 1024 * 1024:
            raise ValueError("汉化引擎返回的信息过大；请检查安装状态后再操作")
        response = json.loads(completed.stdout.decode("utf-8-sig"))
        if (not isinstance(response, dict) or type(response.get("ok")) is not bool or
                response.get("operation") != operation or not isinstance(response.get("message"), str)):
            raise ValueError("汉化引擎返回了无效状态，不能宣称操作成功")
        if completed.returncode != 0 or not response["ok"]:
            if response.get("cancelled") is True:
                return response
            raise RuntimeError(response["message"])
        return response
