"""Atreia Assistant development desktop UI. No automatic live capture."""
import argparse
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
import ctypes
import os
import subprocess
import sys
from pipeline import BackendBridge, ConnectionRouter, ScopedConnectionRouter, replay_capture
from capture_live import Npcap, capture_filter
from connections import find_game_discovery
from auto_capture import AutoCapturePlan, prepare_auto_capture
from capture_windivert import WinDivertReader
from localization_paths import discover_steam, windows_steam_roots, inspect_installation


class AssistantApp:
    def __init__(self, root, backend_path=None):
        self.root = root
        self.backend_path = backend_path
        self.events = queue.Queue()
        self.snapshot_lock = threading.Lock()
        self.latest_event = None
        self.cancelled = threading.Event()
        self.bridge = None
        self.running = False
        self.last_snapshot = None
        self.last_diagnostics = {}
        self.row_skills = {}
        self.npcap = None
        self.windivert = None
        self.localization_game = None
        self.localization_busy = False
        self.devices = []
        self.connections = []
        self.selected_connection = None
        self.detecting = False
        self.is_live = False
        self.resetting = False
        self.history = []
        self.report_state = "not_started"
        self.guided_check = False
        self.pending_auto_start = False
        self.advanced_visible = False
        root.title("亚特雷亚助手")
        dpi_scale = max(1.0, root.winfo_fpixels("1i") / 96)
        root.geometry(f"{round(780 * dpi_scale)}x{round(620 * dpi_scale)}")
        root.minsize(round(740 * dpi_scale), round(590 * dpi_scale))
        root.configure(background="#101827")
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#101827")
        style.configure("TLabel", background="#101827", foreground="#d5e0ee", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"), foreground="#e5d2a2")
        style.configure("Muted.TLabel", foreground="#92a4bf")
        style.configure("Card.TFrame", background="#182337")
        style.configure("Card.TLabel", background="#182337", foreground="#d5e0ee")
        style.configure("Empty.TLabel", background="#1c293c", foreground="#92a4bf")
        style.configure("Warning.TLabel", foreground="#f1c66e")
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(10, 6),
                        background="#24344c", foreground="#e4edf7", borderwidth=0,
                        lightcolor="#24344c", darkcolor="#24344c", bordercolor="#24344c")
        style.map("TButton", background=[("disabled", "#192438"), ("active", "#344b69")],
                  foreground=[("disabled", "#62738b")])
        style.configure("Accent.TButton", background="#54d4c4", foreground="#082b30",
                        font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Accent.TButton", background=[("disabled", "#253c43"), ("active", "#84e4d8")],
                  foreground=[("disabled", "#718f93"), ("!disabled", "#082b30")])
        style.configure("TEntry", fieldbackground="#1c293c", foreground="#e4edf7",
                        insertcolor="#e4edf7", bordercolor="#34455d", padding=6)
        style.configure("TCombobox", fieldbackground="#1c293c", background="#24344c",
                        foreground="#e4edf7", arrowcolor="#7ad9ee", bordercolor="#34455d", padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", "#1c293c"), ("disabled", "#192438")],
                  foreground=[("disabled", "#62738b"), ("readonly", "#e4edf7")],
                  selectbackground=[("readonly", "#1c293c")], selectforeground=[("readonly", "#e4edf7")])
        root.option_add("*TCombobox*Listbox.background", "#1c293c")
        root.option_add("*TCombobox*Listbox.foreground", "#e4edf7")
        style.configure("TCheckbutton", background="#101827", foreground="#aebed4",
                        font=("Microsoft YaHei UI", 9))
        style.map("TCheckbutton", background=[("active", "#101827")],
                  foreground=[("disabled", "#62738b")])
        style.configure("TNotebook", background="#101827", borderwidth=0)
        style.configure("TNotebook.Tab", background="#1c293c", foreground="#92a4bf", padding=(14, 7))
        style.map("TNotebook.Tab", background=[("selected", "#24344c")],
                  foreground=[("selected", "#7ad9ee")])
        style.configure("Vertical.TScrollbar", background="#34455d", troughcolor="#182337",
                        arrowcolor="#92a4bf", bordercolor="#182337")
        style.configure("Treeview", background="#1c293c", fieldbackground="#1c293c", foreground="#e4edf7", rowheight=25)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), padding=6,
                        background="#24344c", foreground="#aebed4", relief="flat")
        style.map("Treeview.Heading", background=[("active", "#344b69")])
        style.map("Treeview", background=[("selected", "#235367")], foreground=[("selected", "#ffffff")])
        body = ttk.Frame(root, padding=14)
        body.pack(fill="both", expand=True)
        header = ttk.Frame(body)
        header.pack(fill="x")
        crest = tk.Canvas(header, width=48, height=50, bg="#101827", highlightthickness=0)
        crest.pack(side="left", padx=(0, 10))
        # Original code-drawn wing/gem emblem, not an official game asset.
        crest.create_oval(8, 7, 40, 43, outline="#587590", width=1)
        for direction in (-1, 1):
            for step in range(3):
                crest.create_line(24 + direction * 4, 27 + step * 4,
                                  24 + direction * (20 - step * 3), 10 + step * 4,
                                  24 + direction * (13 - step * 2), 28 + step * 4,
                                  fill="#7ad9ee", width=2)
        crest.create_polygon(24, 13, 30, 25, 24, 39, 18, 25,
                             fill="#1d4c64", outline="#e5d2a2", width=2)
        crest.scale("all", 0, 0, dpi_scale, dpi_scale)
        crest.configure(width=round(48 * dpi_scale), height=round(50 * dpi_scale))
        ttk.Label(header, text="亚特雷亚助手", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="ATREIA\n开发测试版", style="Muted.TLabel", justify="right").pack(side="right")
        tk.Frame(body, height=1, bg="#756d56").pack(fill="x", pady=(8, 0))
        self.compatibility = ttk.Label(body, text="战斗统计 · 当前客户端兼容性未验证", style="Warning.TLabel")
        self.compatibility.pack(anchor="w", pady=(7, 0))
        controls = ttk.Frame(body)
        controls.pack(fill="x", pady=10)
        self.client = tk.StringVar(value="Steam / Global")
        self.client_box = ttk.Combobox(controls, textvariable=self.client,
            values=("Steam / Global", "PURPLE"), state="readonly", width=16)
        self.client_box.pack(side="left", padx=(0, 10))
        self.auto_start_button = ttk.Button(controls, text="开启战斗统计", style="Accent.TButton", command=self.begin_auto)
        self.auto_start_button.pack(side="left", padx=4)
        self.stop_button = ttk.Button(controls, text="停止", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=4)
        self.advanced_button = ttk.Button(controls, text="设置", command=self.toggle_advanced)
        self.advanced_button.pack(side="right")
        self.settings_window = tk.Toplevel(root)
        self.settings_window.withdraw()
        self.settings_window.title("亚特雷亚助手 · 设置与诊断")
        self.settings_window.geometry(f"{round(820 * dpi_scale)}x{round(390 * dpi_scale)}")
        self.settings_window.resizable(True, False)
        self.settings_window.transient(root)
        self.settings_window.protocol("WM_DELETE_WINDOW", self.toggle_advanced)
        self.advanced = ttk.Frame(self.settings_window, padding=12, style="Card.TFrame")
        tools = ttk.Frame(self.advanced, style="Card.TFrame")
        tools.pack(fill="x", pady=(0, 12))
        self.detect_button = ttk.Button(tools, text="检查环境", command=self.check_setup)
        self.detect_button.pack(side="left")
        ttk.Button(tools, text="以管理员权限重开", command=self.relaunch_admin).pack(side="right")
        settings = ttk.Frame(self.advanced, style="Card.TFrame")
        settings.pack(fill="x")
        ttk.Label(settings, text="TCP 端口", style="Card.TLabel").pack(side="left")
        self.port = tk.StringVar()
        self.port_box = ttk.Entry(settings, textvariable=self.port, width=8)
        self.port_box.pack(side="left", padx=8)
        ttk.Label(settings, text="服务器 IPv4", style="Card.TLabel").pack(side="left", padx=(8, 4))
        self.server_ip = tk.StringVar()
        self.ip_box = ttk.Entry(settings, textvariable=self.server_ip, width=17)
        self.ip_box.pack(side="left", padx=6)
        self.open_button = ttk.Button(settings, text="导入离线 PCAP", command=self.open_capture)
        self.open_button.pack(side="right")
        detected = ttk.Frame(self.advanced, style="Card.TFrame")
        detected.pack(fill="x", pady=(0, 8))
        ttk.Label(detected, text="2  游戏连接").pack(side="left", padx=(0, 8))
        self.connection_box = ttk.Combobox(detected, state="readonly", width=62)
        self.connection_box.pack(side="left", fill="x", expand=True)
        self.apply_button = ttk.Button(detected, text="确认连接", command=self.apply_connection)
        self.apply_button.pack(side="left")
        live = ttk.Frame(self.advanced, style="Card.TFrame")
        live.pack(fill="x", pady=(8, 0))
        self.device_box = ttk.Combobox(live, state="readonly", width=29)
        self.device_box.pack(side="left")
        self.refresh_button = ttk.Button(live, text="检测驱动/网卡", command=self.refresh_devices)
        self.refresh_button.pack(side="left", padx=6)
        self.live_button = ttk.Button(live, text="按手动设置开始", command=self.start_live, state="disabled")
        self.live_button.pack(side="left", padx=6)
        ttk.Button(live, text="重新检测游戏连接", command=self.detect_connections).pack(side="right")
        self.scope_summary = tk.StringVar(value="尚未确认连接范围。")
        ttk.Label(self.advanced, textvariable=self.scope_summary, style="Card.TLabel", wraplength=920).pack(anchor="w", pady=(8, 0))
        self.install_guide_button = ttk.Button(self.advanced, text="安装 Npcap（备用手动采集）", command=self.open_npcap_guide)
        self.install_guide_button.pack(anchor="w", pady=(8, 0))
        self.consent = tk.BooleanVar(value=False)
        self.consent_box = ttk.Checkbutton(self.advanced, text="我同意仅采集所选游戏连接并在本地分析，理解第三方工具及未验证版本的风险。",
            variable=self.consent, command=self.update_live_state)
        self.consent_box.pack(anchor="w", pady=(0, 8))
        self.status = tk.StringVar(value="进入游戏，点击开启统计。连接由助手自动识别。")
        ttk.Label(body, textvariable=self.status, wraplength=730).pack(anchor="w", pady=(0, 6))
        self.integrity = tk.StringVar(value="")
        ttk.Label(body, textvariable=self.integrity, style="Warning.TLabel", wraplength=730).pack(anchor="w", pady=(0, 4))
        results = ttk.Frame(body)
        results.pack(fill="both", expand=True)
        footer = ttk.Frame(results)
        footer.pack(side="bottom", fill="x", pady=(10, 0))
        self.diagnostics = tk.StringVar(value="仅本地分析 · 不上传数据 · 不修改游戏")
        ttk.Label(footer, textvariable=self.diagnostics, style="Muted.TLabel", wraplength=420).pack(side="left")
        self.export_button = ttk.Button(footer, text="导出报告", command=self.export_report, state="disabled")
        self.export_button.pack(side="right")
        self.reset_button = ttk.Button(footer, text="新的一场", command=self.reset_encounter, state="disabled")
        self.reset_button.pack(side="right", padx=6)
        tabs = ttk.Notebook(results)
        tabs.pack(fill="both", expand=True)
        damage_tab, healing_tab, localization_tab = ttk.Frame(tabs), ttk.Frame(tabs), ttk.Frame(tabs, padding=20)
        tabs.add(damage_tab, text="伤害与技能")
        tabs.add(healing_tab, text="治疗统计")
        tabs.add(localization_tab, text="游戏汉化")
        ttk.Label(localization_tab, text="简体中文 · 国服风味", style="Title.TLabel").pack(anchor="w", pady=(12, 10))
        ttk.Label(localization_tab, text="汉化安装功能正在整合。当前可使用原版汉化工具。\nSteam / Global 可前往正式下载页；PURPLE 暂未验证。",
                  wraplength=650).pack(anchor="w", pady=(0, 18))
        self.localization_status = tk.StringVar(value="先检测游戏目录；这里只读检查，不会修改游戏文件。")
        ttk.Label(localization_tab, textvariable=self.localization_status, wraplength=650).pack(anchor="w", pady=(0, 12))
        localization_actions = ttk.Frame(localization_tab)
        localization_actions.pack(fill="x", pady=(0, 16))
        ttk.Button(localization_actions, text="检测游戏目录", command=self.detect_localization).pack(side="left")
        ttk.Button(localization_actions, text="选择游戏目录", command=self.choose_localization).pack(side="left", padx=8)
        ttk.Button(localization_tab, text="打开现有汉化工具下载页", command=lambda: webbrowser.open(
            "https://github.com/lulinlulu888-design/Aion2-Steam-CN/releases/latest")).pack(anchor="w")
        self.damage = self.table(damage_tab,
            ("目标", "玩家", "总伤害", "DPS", "贡献", "暴击命中率"), height=4)
        self.damage.bind("<<TreeviewSelect>>", self.select_player)
        ttk.Label(damage_tab, text="选中玩家查看技能分解；数字 ID 表示名称尚未识别。", padding=8).pack(anchor="w")
        self.skills = self.table(damage_tab, ("技能 ID", "持续伤害", "伤害", "命中次数", "暴击命中"), height=3)
        self.healing = self.table(healing_tab, ("玩家 ID", "技能 ID", "持续治疗", "治疗总量", "记录次数"), height=10)
        self.empty_hint = ttk.Label(self.damage, text="等待战斗数据\n进入游戏后，点击开启统计", style="Empty.TLabel", justify="center")
        self.empty_hint.place(relx=.5, rely=.55, anchor="center")
        root.after(100, self.poll)

    def detect_localization(self):
        if self.localization_busy:
            return
        client = self.client.get()
        if client != "Steam / Global":
            self.localization_game = None
            self.localization_status.set("PURPLE 目录请先手动选择；目前不会猜测安装位置，也未启用汉化安装。")
            return
        self.localization_busy = True
        self.localization_game = None
        self.localization_status.set("正在读取 Steam 游戏库，检查语言包与安装标记……")
        def discover():
            try:
                records = discover_steam(windows_steam_roots())
                self.notify(("localization", client, records, None))
            except Exception as error:
                self.notify(("localization", client, [], str(error)))
        threading.Thread(target=discover, daemon=True).start()

    def choose_localization(self):
        if self.localization_busy:
            return
        path = filedialog.askdirectory(parent=self.root, title="选择 AION2 游戏目录（只读检测）")
        if not path:
            return
        try:
            self.localization_game = inspect_installation(path, "steam" if self.client.get() == "Steam / Global" else "purple")
            self.localization_status.set(str(self.localization_game.root) + "\n" + self.localization_game.status)
        except (OSError, ValueError) as error:
            self.localization_game = None
            self.localization_status.set("目录检查失败：" + str(error))

    def toggle_advanced(self):
        self.advanced_visible = not self.advanced_visible
        if self.advanced_visible:
            self.advanced.pack(fill="both", expand=True)
            self.settings_window.deiconify()
            self.settings_window.lift()
        else:
            self.settings_window.withdraw()
            self.advanced.pack_forget()
        self.advanced_button.configure(text="收起设置" if self.advanced_visible else "设置")

    def check_setup(self):
        if self.running or self.detecting:
            return
        self.windivert = None
        self.consent.set(False)
        try:
            self.windivert = WinDivertReader(Path(__file__).resolve().parent / "vendor/windivert")
        except Exception as error:
            self.pending_auto_start = False
            self.status.set("内置采集组件未就绪：" + str(error))
            return
        self.guided_check = True
        self.detect_connections()

    def begin_auto(self):
        if self.running or self.detecting:
            return
        self.consent.set(False)
        self.windivert = None
        try:
            self.windivert = WinDivertReader(Path(__file__).resolve().parent / "vendor/windivert")
        except Exception as error:
            self.status.set("内置采集组件未就绪：" + str(error))
            return
        if not self.is_admin():
            self.status.set("请在设置中点“以管理员权限重开”，确认 Windows 提示后再开启统计。")
            return
        self.pending_auto_start = True
        self.detect_connections()

    @staticmethod
    def is_admin():
        return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())

    def relaunch_admin(self):
        if self.running or self.detecting:
            return
        if self.is_admin():
            self.status.set("已有管理员权限，可以点击开启战斗统计。")
            return
        if os.name != "nt":
            self.status.set("实时统计目前只支持 Windows。")
            return
        if not messagebox.askyesno("Windows 权限", "采集组件需要管理员权限。将重开工具，Windows 提示请自行确认。"
                                  "\n不会自动开始采集，重开后仍需点击开启统计。", parent=self.root):
            return
        arguments = [] if getattr(sys, "frozen", False) else [str(Path(__file__).resolve())]
        if self.backend_path:
            arguments += ["--backend", str(Path(self.backend_path).resolve())]
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        shell.ShellExecuteW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                       ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
        shell.ShellExecuteW.restype = ctypes.c_void_p
        result = shell.ShellExecuteW(None, "runas", sys.executable,
                                    subprocess.list2cmdline(arguments), str(Path(__file__).resolve().parent), 1)
        if result and result > 32:
            self.close()
        else:
            self.status.set("重开未完成或权限被取消；没有开始采集。")

    def confirm_auto_start(self, report):
        try:
            plan = prepare_auto_capture(report, self.devices,
                                        provider="windivert" if self.windivert is not None else "npcap")
            executable = self.backend_executable()
        except (ValueError, FileNotFoundError) as error:
            self.status.set(str(error))
            return
        self.scope_summary.set("自动范围：" + "；".join(
            f"{s.local_ip}:{s.local_port} → {s.remote_ip}:{s.remote_port}" for s in plan.scopes))
        text = (f"将分析当前 {self.client.get()} 游戏进程的 {len(plan.scopes)} 条精确网络连接，"
                "其中可能包含非战斗服务。\n\n仅在本机分析，不保存或上传原始封包，不修改游戏。"
                "\n第三方工具风险及真实游戏兼容性尚未验证。")
        if plan.identity_restricted:
            text += "\n程序路径读取受限，请确认所选 Steam/PURPLE 客户端正确。"
        if plan.device == "windivert":
            text += "\n将启用随包 WinDivert 驱动，仅复制接收封包，不阻断或重发流量。"
        if not messagebox.askyesno("确认开启战斗统计", text + "\n精确范围可在高级设置查看。\n\n确认采集这些游戏连接并开始？", parent=self.root):
            self.consent.set(False)
            self.status.set("已取消，没有开始采集。")
            return
        self.consent.set(True)  # Only after the human confirms this exact plan.
        self.start_replay(None, executable, "steam" if self.client.get() == "Steam / Global" else "purple", 0, plan)

    def update_live_state(self):
        self.auto_start_button.configure(state="disabled" if self.running or self.detecting else "normal")
        ready = False
        if not self.running and not self.detecting and self.npcap is not None and self.consent.get():
            try:
                port = int(self.port.get())
                candidate = self.selected_connection
                if candidate and (candidate.server_ip, candidate.server_port) != (self.server_ip.get(), port):
                    raise ValueError("Connection changed")
                scope = candidate.scope if candidate else None
                capture_filter(self.server_ip.get(), port, scope)
                index = self.device_box.current()
                ready = 0 <= index < len(self.devices)
                if ready and scope and scope.remote_ip.startswith("127."):
                    ready = self.devices[index][0] == r"\Device\NPF_Loopback"
            except ValueError:
                pass
        self.live_button.configure(state="normal" if ready else "disabled")

    @staticmethod
    def table(parent, columns, height):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=105, minwidth=60, anchor="center")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        return tree

    def backend_executable(self):
        base = Path(__file__).resolve().parent
        for candidate in (self.backend_path, base / "bin/atreia-combat-backend.exe",
                          base / "backend/target/release/atreia-combat-backend.exe",
                          base / "backend/target/debug/atreia-combat-backend.exe"):
            if candidate and Path(candidate).is_file():
                return Path(candidate)
        raise FileNotFoundError("尚未找到解析后端。请先运行 cargo build --release --manifest-path backend/Cargo.toml。")

    def open_capture(self):
        try:
            port = int(self.port.get())
            if not 1 <= port <= 65535:
                raise ValueError()
            executable = self.backend_executable()
        except (ValueError, FileNotFoundError) as error:
            messagebox.showerror("无法开始", str(error) or "请填写 1—65535 的游戏 TCP 端口。", parent=self.root)
            return
        path = filedialog.askopenfilename(parent=self.root, title="打开已授权采集的离线封包",
            filetypes=(("Classic PCAP", "*.pcap"),))
        if not path:
            return
        self.start_replay(path, executable, "steam" if self.client.get() == "Steam / Global" else "purple", port)

    def open_npcap_guide(self):
        if self.running or self.detecting:
            return
        self.status.set("请在 Npcap 官网下载安装；许可和管理员提示需自行确认。安装后点“检查环境”，不会自动开始采集。")
        try:
            if not webbrowser.open("https://npcap.com/#download"):
                self.status.set("浏览器未能打开，请手动访问 https://npcap.com/#download；安装后点“检查环境”。")
        except Exception:
            self.status.set("浏览器未能打开，请手动访问 https://npcap.com/#download；安装后点“检查环境”。")

    def refresh_devices(self, show_error=True):
        if self.running or self.detecting:
            return False
        self.npcap = None
        self.devices = []
        self.device_box["values"] = ()
        self.device_box.set("")
        self.consent.set(False)
        try:
            reader = Npcap()
            devices = reader.devices()
            self.npcap, self.devices = reader, devices
            self.device_box["values"] = tuple(f"{index + 1}. {description}" for index, (_, description) in enumerate(self.devices))
            self.device_box.set("")
            self.status.set("Npcap 可加载。请手动选择网卡及游戏连接，再确认采集范围；检测不会启动采集。"
                            if self.devices else "Npcap 可加载但未发现接口，请检查驱动与权限；尚未开始采集。")
            return bool(self.devices)
        except Exception as error:
            self.status.set("Npcap 检测失败；可点“Npcap 官网安装”，完成后重新检测。尚未开始采集。")
            if show_error:
                messagebox.showerror("实时采集尚不可用", str(error), parent=self.root)
            return False

    def detect_connections(self):
        if self.running or self.detecting:
            return
        self.detecting = True
        self.auto_start_button.configure(state="disabled")
        self.detect_button.configure(state="disabled")
        self.apply_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.live_button.configure(state="disabled")
        self.status.set("正在读取 AION2.exe 的已建立 TCP 连接；不会启动采集。")
        def discover():
            try:
                self.notify(("discovery", find_game_discovery()))
            except Exception as error:
                self.notify(("connections_error", str(error)))
        threading.Thread(target=discover, daemon=True).start()

    def apply_connection(self):
        if self.running or self.detecting:
            return
        index = self.connection_box.current()
        if not 0 <= index < len(self.connections):
            self.status.set("请先检测并选择候选游戏连接，或手动填写 IP 和端口。")
            return
        candidate = self.connections[index]
        self.selected_connection = candidate
        self.consent.set(False)
        self.server_ip.set(candidate.server_ip)
        self.port.set(str(candidate.server_port))
        self.scope_summary.set(f"PID {candidate.pid} · " +
            (f"{candidate.scope.local_ip}:{candidate.scope.local_port} → " if candidate.scope else "") +
            f"{candidate.server_ip}:{candidate.server_port} · 客户端身份仍需确认")
        if candidate.scope and candidate.scope.remote_ip.startswith("127."):
            loopbacks = [index for index, (name, _) in enumerate(self.devices) if name == r"\Device\NPF_Loopback"]
            if len(loopbacks) == 1:
                self.device_box.current(loopbacks[0])
        elif len(self.devices) == 1:
            self.device_box.current(0)
        self.status.set("已选择候选连接，请确认客户端及采集范围；尚未启动采集，连接可能不是战斗服务。"
                        + (" 程序路径读取受限，客户端身份未由路径验证。"
                           if candidate.client_hint == "path_restricted" else ""))

    def start_live(self):
        if not self.consent.get():
            messagebox.showwarning("需要明确同意", "实时分析前请确认采集范围和风险。", parent=self.root)
            return
        try:
            port = int(self.port.get())
            candidate = self.selected_connection
            if candidate and (candidate.server_ip, candidate.server_port) != (self.server_ip.get(), port):
                raise ValueError("IP/端口已改变，请重新检测并选择连接，以确认精确采集范围")
            scope = candidate.scope if candidate else None
            capture_filter(self.server_ip.get(), port, scope)
            executable = self.backend_executable()
            index = self.device_box.current()
            if self.npcap is None or not 0 <= index < len(self.devices):
                raise ValueError("请先刷新并选择网卡")
            device = self.devices[index][0]
            if scope and scope.remote_ip.startswith("127.") and device != r"\Device\NPF_Loopback":
                raise ValueError("本地代理连接请选择 Npcap Loopback 回环接口")
        except (ValueError, FileNotFoundError) as error:
            messagebox.showerror("无法开始", str(error), parent=self.root)
            return
        self.start_replay(None, executable, "steam" if self.client.get() == "Steam / Global" else "purple",
                          port, (device, self.server_ip.get(), candidate))

    def start_replay(self, path, executable, client, port, live_options=None):
        if self.running or self.detecting or self.resetting:
            return
        self.running = True
        self.is_live = live_options is not None
        self.cancelled.clear()
        self.last_snapshot = None
        self.report_state = "running"
        self.render({"targets": [], "healing": []}, {})
        self.export_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.client_box.configure(state="disabled")
        self.port_box.configure(state="disabled")
        self.stop_button.configure(state="normal")
        for control in (self.device_box, self.ip_box, self.refresh_button, self.install_guide_button, self.live_button, self.auto_start_button, self.consent_box,
                        self.connection_box, self.detect_button, self.apply_button):
            control.configure(state="disabled")
        self.status.set("正在实时分析所选游戏连接；兼容性未验证。" if live_options else "正在离线解析；当前客户端兼容性仍为未验证……")
        threading.Thread(target=self.work, args=(path, executable, client, port, live_options), daemon=True).start()

    def notify(self, event):
        if event[0] == "snapshot":
            with self.snapshot_lock:
                self.latest_event = event
        else:
            # Low-volume lifecycle events must not be evicted by snapshots.
            self.events.put_nowait(event)

    def work(self, path, executable, client, port, live_options):
        try:
            with BackendBridge(executable, client) as bridge:
                self.bridge = bridge
                self.notify(("ready",))
                if live_options:
                    if isinstance(live_options, AutoCapturePlan):
                        live_options.verify(find_game_discovery())
                        router = ScopedConnectionRouter(bridge, live_options.scopes)
                        if live_options.device == "windivert":
                            if self.windivert is None:
                                raise ValueError("内置采集组件未就绪")
                            packets = self.windivert.packets_for_scopes(live_options.scopes, self.cancelled)
                        else:
                            packets = self.npcap.packets_for_scopes(live_options.device, live_options.scopes, self.cancelled)
                    else:
                        device, server_ip, candidate = live_options
                        scope = candidate.scope if candidate else None
                        if scope is not None:
                            current = find_game_discovery()
                            if not any(c.pid == candidate.pid and c.scope == scope for c in current.connections):
                                raise ValueError("所选游戏连接已变化或关闭，请重新检测；没有开始采集")
                        router = ConnectionRouter(bridge, port, server_ip=server_ip, scope=scope)
                        packets = self.npcap.packets(device, server_ip, port, self.cancelled, scope=scope)
                    try:
                        for packet in packets:
                            snapshot = router.feed(packet)
                            if snapshot is not None:
                                self.notify(("snapshot", snapshot, router.diagnostics()))
                    finally:
                        packets.close()
                    diagnostics = router.diagnostics()
                else:
                    diagnostics = replay_capture(path, bridge, port,
                        lambda snapshot, diagnostics: self.notify(("snapshot", snapshot, diagnostics)), self.cancelled)
            self.notify(("done", diagnostics))
        except Exception as error:
            self.notify(("error", str(error)))
        finally:
            self.bridge = None

    def poll(self):
        with self.snapshot_lock:
            latest, self.latest_event = self.latest_event, None
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "localization":
                self.localization_busy = False
                self.localization_game = None
                if event[1] != self.client.get():
                    self.localization_status.set("客户端选择已变化，请重新检测目录。")
                elif event[3]:
                    self.localization_status.set("目录检测失败：" + event[3])
                elif len(event[2]) == 1:
                    self.localization_game = event[2][0]
                    self.localization_status.set(str(self.localization_game.root) + "\n" + self.localization_game.status)
                elif event[2]:
                    self.localization_status.set("找到多个游戏安装目录，请手动选择；不会自动修改任一目录。")
                else:
                    self.localization_status.set("未找到游戏目录，可点“选择游戏目录”；尚未修改任何文件。")
                continue
            if event[0] == "ready":
                self.reset_button.configure(state="normal" if self.running and self.is_live else "disabled")
                continue
            if event[0] in ("reset", "reset_error"):
                self.resetting = False
                self.reset_button.configure(state="normal" if self.running and self.is_live else "disabled")
                if latest is not None:
                    self.render(latest[1], latest[2])
                    latest = None
                if event[0] == "reset":
                    snapshot = event[1]
                    previous = snapshot.pop("previous_encounter", None)
                    if previous and previous.get("status") == "combat_detected":
                        self.history.append(previous)
                        self.history = self.history[-20:]
                    self.render(snapshot, self.last_diagnostics)
                    self.status.set(f"已开始新一场；内存中保留最近 {len(self.history)} 场手动结束的战斗，可导出。实战兼容性未验证。")
                else:
                    self.status.set("开始新一场失败：" + event[1])
                continue
            if event[0] in ("discovery", "connections", "connections_error"):
                self.detecting = False
                self.detect_button.configure(state="normal")
                self.apply_button.configure(state="normal")
                self.open_button.configure(state="normal")
                self.live_button.configure(state="normal")
                self.connections = (event[1].connections if event[0] == "discovery" else
                    event[1] if event[0] == "connections" else [])
                self.selected_connection = None
                self.consent.set(False)
                self.connection_box["values"] = tuple(
                    f'连接 {index + 1} · '
                    + ("本地代理" if candidate.server_ip.startswith("127.") else "网络连接") + " · "
                    + ("Steam 路径" if candidate.client_hint == "steam" else
                       "路径受限，客户端需确认" if candidate.client_hint == "path_restricted" else "客户端需确认")
                    for index, candidate in enumerate(self.connections))
                self.connection_box.set("")
                self.status.set(event[1].message() if event[0] == "discovery" else
                    f"找到 {len(self.connections)} 条候选连接，请手动选择；检测不会启动采集。"
                    if event[0] == "connections" else "检测失败：" + event[1])
                if self.pending_auto_start:
                    self.pending_auto_start = False
                    self.guided_check = False
                    if event[0] == "discovery":
                        self.confirm_auto_start(event[1])
                elif self.guided_check:
                    self.guided_check = False
                    if self.windivert is not None:
                        self.status.set("内置组件已就绪。点击“开启战斗统计”将自动准备游戏连接并请求确认。"
                                        if self.connections else event[1].message() if event[0] == "discovery" else self.status.get())
                    elif len(self.connections) == 1:
                        self.connection_box.current(0)
                        self.apply_connection()
                        if self.device_box.current() >= 0:
                            self.status.set("环境已就绪。请确认游戏客户端与采集范围，勾选同意后点“开始统计”；实战兼容性仍未验证。")
                        else:
                            self.status.set("已找到游戏连接，但无法确定采集网卡。请在高级设置中选择；不会自动猜测或开始采集。")
                    elif self.connections:
                        self.status.set(f"找到 {len(self.connections)} 个候选连接，尚不能确定战斗通道。请选择后点“确认连接”；不要把无事件当成零伤害。")
                continue
            if event[0] == "snapshot":
                latest = event
            else:
                if latest is not None:
                    self.render(latest[1], latest[2])
                    latest = None
                self.running = False
                self.open_button.configure(state="normal")
                self.client_box.configure(state="readonly")
                self.port_box.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.reset_button.configure(state="disabled")
                self.device_box.configure(state="readonly")
                self.connection_box.configure(state="readonly")
                for control in (self.ip_box, self.refresh_button, self.install_guide_button, self.live_button, self.consent_box,
                                self.detect_button, self.apply_button):
                    control.configure(state="normal")
                self.report_state = "cancelled" if self.cancelled.is_set() else "error" if event[0] == "error" else "finished"
                if event[0] == "done":
                    self.render(self.last_snapshot or {"targets": [], "healing": []}, event[1])
                if event[0] == "error":
                    self.status.set("解析已停止：" + event[1] + "。现有数据可能不完整。")
                elif self.cancelled.is_set():
                    self.status.set("已停止，当前报告为部分数据；未完成实战兼容性验证。")
                elif self.last_snapshot and self.last_snapshot.get("status") == "combat_detected":
                    self.status.set("解析完成。识别到候选战斗记录，客户端兼容性仍未验证；请查看缺口诊断。")
                else:
                    self.status.set("未识别到战斗事件：可能是端口、协议或封包不完整；不表示真实零伤害。")
        if latest is not None:
            self.render(latest[1], latest[2])
        self.update_live_state()
        self.root.after(100, self.poll)

    def render(self, snapshot, diagnostics):
        old_encounter = (self.last_snapshot or {}).get("encounter_id", 0)
        new_encounter = snapshot.get("encounter_id", 0)
        if new_encounter < old_encounter:
            return  # A queued pre-reset snapshot must not restore old totals.
        if snapshot.get("revision", 0) < (self.last_snapshot or {}).get("revision", 0):
            return  # A delayed reset reply must not replace newer post-reset data.
        selection = self.damage.selection()
        selected = selection[0] if selection and new_encounter == old_encounter else None
        self.last_snapshot, self.last_diagnostics = snapshot, diagnostics
        for table in (self.damage, self.skills, self.healing):
            table.delete(*table.get_children())
        self.row_skills.clear()
        for target in snapshot.get("targets", []):
            for player in target["players"]:
                skills = player["skills"]
                hits = sum(s["hits"] for s in skills)
                critical = sum(s["critical_hits"] for s in skills)
                row = self.damage.insert("", "end", iid=f'{target["target_id"]}:{player["actor_id"]}', values=(target["target_id"],
                    player.get("name") or f'#{player["actor_id"]}', f'{player["damage"]:,}',
                    f'{player["dps"]:,.1f}', f'{player["contribution"]:.1%}',
                    f'{critical / hits:.1%}' if hits else "—"))
                self.row_skills[row] = skills
        if self.damage.get_children():
            self.empty_hint.place_forget()
        else:
            self.empty_hint.place(relx=.5, rely=.55, anchor="center")
        if selected and self.damage.exists(selected):
            self.damage.selection_set(selected)
            self.select_player()
        for heal in snapshot.get("healing", []):
            self.healing.insert("", "end", values=(heal["actor_id"], heal["skill_id"],
                "是" if heal["hot"] else "否", f'{heal["healing"]:,}', heal["ticks"]))
        self.diagnostics.set(f'载荷 {diagnostics.get("payload_bytes", 0):,} 字节 · '
            f'中途开始 {diagnostics.get("partial_streams", 0)} 条 · '
            f'未补齐缺口 {diagnostics.get("closed_gaps", 0)} 条')
        warnings = []
        if diagnostics.get("partial_streams", 0):
            warnings.append("采集中途开始，可能缺少此前战斗或身份信息")
        if diagnostics.get("closed_gaps", 0) or diagnostics.get("pending_bytes", 0):
            warnings.append("TCP 数据存在未补齐缺口，统计可能偏低")
        if snapshot.get("pending_bytes", 0):
            warnings.append("仍有协议字节待解析，当前快照不是完整结果")
        if snapshot.get("discarded_protocol_bytes", 0):
            warnings.append("连接关闭时丢弃了残帧，部分记录可能未计入")
        self.integrity.set("；".join(warnings))
        self.export_button.configure(state="normal" if snapshot.get("status") == "combat_detected" or self.history else "disabled")

    def select_player(self, _=None):
        self.skills.delete(*self.skills.get_children())
        selection = self.damage.selection()
        for skill in self.row_skills.get(selection[0], []) if selection else []:
            self.skills.insert("", "end", values=(skill["skill_id"], "是" if skill["dot"] else "否",
                f'{skill["damage"]:,}', skill["hits"], skill["critical_hits"]))

    def export_report(self):
        if not self.last_snapshot:
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="导出本地报告（可能包含玩家昵称）",
            defaultextension=".json", filetypes=(("JSON 报告", "*.json"),))
        if path:
            try:
                Path(path).write_text(json.dumps({"compatibility": "unverified", "report_state": self.report_state,
                    "diagnostics": self.last_diagnostics, "snapshot": self.last_snapshot,
                    "history": self.history},
                    ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError as error:
                messagebox.showerror("导出失败", str(error), parent=self.root)

    def reset_encounter(self):
        if not self.running or not self.is_live or self.bridge is None or self.resetting:
            return
        if not messagebox.askyesno("开始新一场", "将当前伤害和治疗归档到内存历史（最近 20 场），清空本场数值。\n不会断开采集；未解析残帧会丢弃。继续吗？", parent=self.root):
            return
        self.resetting = True
        self.reset_button.configure(state="disabled")
        bridge = self.bridge
        def reset():
            try:
                self.notify(("reset", bridge.reset_encounter()))
            except Exception as error:
                self.notify(("reset_error", str(error)))
        threading.Thread(target=reset, daemon=True).start()

    def stop(self):
        self.cancelled.set()
        if self.bridge:
            threading.Thread(target=self.bridge.close, daemon=True).start()

    def close(self):
        self.stop()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path)
    parser.add_argument("--self-test-report", type=Path,
        help="Hidden synthetic bundle smoke test; does not capture game traffic")
    args = parser.parse_args()
    if args.self_test_report:
        from healthcheck import check_backend
        root = None
        result = {"status": "failed", "real_game_tested": False, "packet_capture_started": False}
        try:
            root = tk.Tk()
            root.withdraw()
            app = AssistantApp(root, args.backend)
            result.update(check_backend(app.backend_executable()))
            if getattr(sys, "frozen", False):
                from connection_scope import ConnectionScope
                reader = WinDivertReader(Path(__file__).resolve().parent / "vendor/windivert")
                reader.validate_filter((ConnectionScope("127.0.0.1", 50000, "127.0.0.1", 1111),
                                        ConnectionScope("10.0.0.1", 50001, "10.0.0.2", 7777)))
                result["windivert_dll_filter_check"] = "passed_without_driver_open"
            if app.consent.get() or app.running or app.npcap is not None:
                raise RuntimeError("启动状态不能自动采集")
            result["status"] = "passed"
        except Exception as error:
            result["error"] = str(error)
        finally:
            if root is not None:
                root.destroy()
        with args.self_test_report.open("x", encoding="utf-8") as report:
            json.dump(result, report, ensure_ascii=False, indent=2)
        raise SystemExit(0 if result["status"] == "passed" else 1)
    root = tk.Tk()
    root.withdraw()
    AssistantApp(root, args.backend)
    root.after(150, root.deiconify)
    root.mainloop()


if __name__ == "__main__":
    main()
