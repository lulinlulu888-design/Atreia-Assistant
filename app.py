"""Atreia Assistant development desktop UI. No automatic live capture."""
import argparse
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
from pipeline import BackendBridge, ConnectionRouter, replay_capture
from capture_live import Npcap, capture_filter
from connections import find_game_discovery


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
        self.devices = []
        self.connections = []
        self.detecting = False
        self.is_live = False
        self.resetting = False
        self.history = []
        self.report_state = "not_started"
        root.title("亚特雷亚助手 · 战斗统计（开发版）")
        root.geometry("1040x700")
        root.minsize(850, 570)
        root.configure(background="#101827")
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#101827")
        style.configure("TLabel", background="#101827", foreground="#d5e0ee", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 25, "bold"), foreground="#7ad9ee")
        style.configure("Warning.TLabel", foreground="#f1c66e")
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=7)
        style.configure("Treeview", background="#1c293c", fieldbackground="#1c293c", foreground="#e4edf7", rowheight=29)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), padding=7)
        body = ttk.Frame(root, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="亚特雷亚助手", style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text="AION2 · 汉化与战斗分析 · Steam / Global & PURPLE").pack(anchor="w", pady=(3, 8))
        self.compatibility = ttk.Label(body, text="开发版：当前游戏兼容性未验证。离线解析不等于实战验证；无事件不等于零伤害。", style="Warning.TLabel")
        self.compatibility.pack(anchor="w")
        controls = ttk.Frame(body)
        controls.pack(fill="x", pady=14)
        ttk.Label(controls, text="客户端").pack(side="left")
        self.client = tk.StringVar(value="Steam / Global")
        self.client_box = ttk.Combobox(controls, textvariable=self.client,
            values=("Steam / Global", "PURPLE"), state="readonly", width=17)
        self.client_box.pack(side="left", padx=(8, 16))
        ttk.Label(controls, text="游戏 TCP 端口").pack(side="left")
        self.port = tk.StringVar()
        self.port_box = ttk.Entry(controls, textvariable=self.port, width=8)
        self.port_box.pack(side="left", padx=8)
        self.open_button = ttk.Button(controls, text="打开离线封包", command=self.open_capture)
        self.open_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(controls, text="停止", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        ttk.Button(controls, text="汉化工具下载", command=lambda: webbrowser.open(
            "https://github.com/lulinlulu888-design/Aion2-Steam-CN/releases/latest")).pack(side="right")
        detected = ttk.Frame(body)
        detected.pack(fill="x", pady=(0, 8))
        self.connection_box = ttk.Combobox(detected, state="readonly", width=62)
        self.connection_box.pack(side="left", fill="x", expand=True)
        self.detect_button = ttk.Button(detected, text="检测游戏连接", command=self.detect_connections)
        self.detect_button.pack(side="left", padx=6)
        self.apply_button = ttk.Button(detected, text="使用所选连接", command=self.apply_connection)
        self.apply_button.pack(side="left")
        live = ttk.Frame(body)
        live.pack(fill="x", pady=(0, 8))
        self.device_box = ttk.Combobox(live, state="readonly", width=29)
        self.device_box.pack(side="left")
        self.refresh_button = ttk.Button(live, text="刷新网卡", command=self.refresh_devices)
        self.refresh_button.pack(side="left", padx=6)
        ttk.Label(live, text="游戏服务器 IPv4").pack(side="left", padx=(8, 4))
        self.server_ip = tk.StringVar()
        self.ip_box = ttk.Entry(live, textvariable=self.server_ip, width=17)
        self.ip_box.pack(side="left", padx=6)
        self.live_button = ttk.Button(live, text="开始实时统计", command=self.start_live)
        self.live_button.pack(side="right")
        self.consent = tk.BooleanVar(value=False)
        self.consent_box = ttk.Checkbutton(body, text="我同意仅采集所选游戏连接并在本地分析，理解第三方工具及未验证版本的风险。",
            variable=self.consent)
        self.consent_box.pack(anchor="w", pady=(0, 8))
        self.status = tk.StringVar(value="准备就绪。请选择客户端、填写游戏端口，再打开已授权采集的 .pcap 文件。")
        ttk.Label(body, textvariable=self.status, wraplength=960).pack(anchor="w", pady=(0, 8))
        self.integrity = tk.StringVar(value="")
        ttk.Label(body, textvariable=self.integrity, style="Warning.TLabel", wraplength=960).pack(anchor="w", pady=(0, 6))
        tabs = ttk.Notebook(body)
        tabs.pack(fill="both", expand=True)
        damage_tab, healing_tab = ttk.Frame(tabs), ttk.Frame(tabs)
        tabs.add(damage_tab, text="伤害与技能")
        tabs.add(healing_tab, text="治疗统计")
        self.damage = self.table(damage_tab,
            ("目标", "玩家", "总伤害", "DPS", "贡献", "暴击命中率"), height=8)
        self.damage.bind("<<TreeviewSelect>>", self.select_player)
        ttk.Label(damage_tab, text="选中玩家查看技能分解；数字 ID 表示名称尚未识别。", padding=8).pack(anchor="w")
        self.skills = self.table(damage_tab, ("技能 ID", "持续伤害", "伤害", "命中次数", "暴击命中"), height=5)
        self.healing = self.table(healing_tab, ("玩家 ID", "技能 ID", "持续治疗", "治疗总量", "记录次数"), height=10)
        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(10, 0))
        self.diagnostics = tk.StringVar(value="不自动采集网络，不上传战斗数据，不修改游戏。")
        ttk.Label(footer, textvariable=self.diagnostics).pack(side="left")
        self.export_button = ttk.Button(footer, text="导出本地报告", command=self.export_report, state="disabled")
        self.export_button.pack(side="right")
        self.reset_button = ttk.Button(footer, text="开始新一场", command=self.reset_encounter, state="disabled")
        self.reset_button.pack(side="right", padx=6)
        root.after(100, self.poll)

    @staticmethod
    def table(parent, columns, height):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=120, minwidth=70, anchor="center")
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

    def refresh_devices(self):
        try:
            self.npcap = Npcap()
            self.devices = self.npcap.devices()
            self.device_box["values"] = tuple(f"{index + 1}. {description}" for index, (_, description) in enumerate(self.devices))
            self.device_box.set("")
            self.status.set("请手动选择网卡并填写游戏服务器 IPv4；刷新网卡不会启动采集。")
        except Exception as error:
            messagebox.showerror("实时采集尚不可用", str(error), parent=self.root)

    def detect_connections(self):
        if self.running or self.detecting:
            return
        self.detecting = True
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
        self.server_ip.set(candidate.server_ip)
        self.port.set(str(candidate.server_port))
        self.status.set("已填入候选 IP/端口，请确认 Steam 或 PURPLE 客户端；尚未启动采集，连接可能不是战斗服务。")

    def start_live(self):
        if not self.consent.get():
            messagebox.showwarning("需要明确同意", "实时分析前请确认采集范围和风险。", parent=self.root)
            return
        try:
            port = int(self.port.get())
            capture_filter(self.server_ip.get(), port)
            executable = self.backend_executable()
            index = self.device_box.current()
            if self.npcap is None or not 0 <= index < len(self.devices):
                raise ValueError("请先刷新并选择网卡")
            device = self.devices[index][0]
        except (ValueError, FileNotFoundError) as error:
            messagebox.showerror("无法开始", str(error), parent=self.root)
            return
        self.start_replay(None, executable, "steam" if self.client.get() == "Steam / Global" else "purple",
                          port, (device, self.server_ip.get()))

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
        for control in (self.device_box, self.ip_box, self.refresh_button, self.live_button, self.consent_box,
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
                    router = ConnectionRouter(bridge, port, server_ip=live_options[1])
                    for packet in self.npcap.packets(*live_options, port, self.cancelled):
                        snapshot = router.feed(packet)
                        if snapshot is not None:
                            self.notify(("snapshot", snapshot, router.diagnostics()))
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
                self.connection_box["values"] = tuple(
                    f'PID {candidate.pid} → {candidate.server_ip}:{candidate.server_port} · '
                    + ("Steam 路径" if candidate.client_hint == "steam" else "客户端需确认")
                    for candidate in self.connections)
                self.connection_box.set("")
                self.status.set(event[1].message() if event[0] == "discovery" else
                    f"找到 {len(self.connections)} 条候选连接，请手动选择；检测不会启动采集。"
                    if event[0] == "connections" else "检测失败：" + event[1])
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
                for control in (self.ip_box, self.refresh_button, self.live_button, self.consent_box,
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
