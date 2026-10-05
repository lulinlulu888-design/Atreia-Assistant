"""Original topmost desktop combat panel; no injection or capture side effects."""
import tkinter as tk
from tkinter import ttk, font


class CombatOverlay:
    def __init__(self, root):
        self.root, self.snapshot, self.history = root, {}, ()
        self.target_ids, self.ranking = [], []
        self.locked, self.details = False, None
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.title("亚特雷亚助手 · 战斗悬浮窗")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", .98)
        self.window.configure(background="#0d1620")
        # Physical-pixel HUD budget. Do not multiply by desktop DPI again:
        # the previous 380x290 panel became 570x435 at 150% scaling.
        self.scale = 1.0
        self.collapsed = False
        self.window.geometry("280x84+40+80")
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        body = tk.Frame(self.window, background="#0d1620", padx=8, pady=3)
        body.pack(fill="both", expand=True)
        bar = tk.Frame(body, background="#0d1620", height=24)
        bar.pack(fill="x")
        self.title = tk.Label(bar, text="ATREIA", background="#0d1620", foreground="#cfc3a5",
                              font=("Segoe UI", -11, "bold"), cursor="fleur")
        self.title.pack(side="left", fill="x", expand=True)
        for widget in (bar, self.title):
            widget.bind("<ButtonPress-1>", self.begin_drag)
            widget.bind("<B1-Motion>", self.drag)
        def icon(text, command):
            label = tk.Label(bar, text=text, background="#0d1620", foreground="#82909f",
                             font=("Segoe UI", -12), cursor="hand2", padx=5)
            label.pack(side="right")
            label.bind("<Button-1>", lambda _: command())
            label.bind("<Enter>", lambda _: label.configure(foreground="#e7dec9"))
            label.bind("<Leave>", lambda _: label.configure(foreground="#82909f"))
            return label
        icon("×", self.hide)
        self.collapse_button = icon("−", self.toggle_collapse)
        icon("···", self.show_menu)
        self.lock_button = tk.Label(body)  # state mirror; not a visible HUD button
        self.mode_label = tk.Label(bar, text="伤害", background="#0d1620", foreground="#76bcc9",
                                   font=("Microsoft YaHei UI", -11), padx=8, cursor="hand2")
        self.mode_label.pack(side="right")
        self.mode_label.bind("<Button-1>", lambda _: self.show_menu())
        filters = ttk.Frame(body)
        # Selection models remain available, but large input widgets are never
        # packed into the HUD. Their choices live in the contextual menu.
        self.metric = ttk.Combobox(filters, values=("伤害", "治疗"), state="readonly", width=6)
        self.metric.current(0)
        self.source = ttk.Combobox(filters, values=("本场",), state="readonly", width=15)
        self.source.current(0)
        for widget in (self.metric, self.source):
            widget.bind("<<ComboboxSelected>>", lambda _: self.refresh_targets())
        self.target = ttk.Combobox(body, state="readonly", width=20)
        self.target.bind("<<ComboboxSelected>>", lambda _: self.render_rows())
        self.area = tk.Frame(body, background="#0d1620")
        self.area.pack(fill="both", expand=True, pady=(3, 0))
        self.canvas = tk.Canvas(self.area, background="#0d1620", highlightthickness=0, height=48)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _: self.draw())
        self.canvas.bind("<MouseWheel>", self.scroll)
        self.text_font = font.Font(root=root, family="Microsoft YaHei UI", size=-11)
        self.note = tk.StringVar(value="等待战斗数据 · 兼容性待验证")
        self.note_label = tk.Label(body, textvariable=self.note, background="#0d1620", foreground="#687b8e",
                                   font=("Microsoft YaHei UI", -10), anchor="w")
        self.note_label.pack(fill="x", pady=(2, 0))

    def toggle_collapse(self):
        self.collapsed = not self.collapsed
        self.collapse_button.configure(text="+" if self.collapsed else "−")
        if self.collapsed:
            self.area.pack_forget()
            self.note_label.pack_forget()
        else:
            self.note_label.pack_forget()
            self.area.pack(fill="both", expand=True, pady=(3, 0))
            self.note_label.pack(fill="x", pady=(2, 0))
        self.resize_hud()

    def resize_hud(self):
        rows = min(5, max(1, len(self.ranking)))
        height = 28 if self.collapsed else (48 + rows * 22 if self.ranking else 84)
        self.window.geometry(f"280x{height}")

    def show_menu(self):
        menu = tk.Menu(self.window, tearoff=False, background="#14212e", foreground="#d5e0ee",
                       activebackground="#24394a", activeforeground="#ffffff", borderwidth=0)
        for value in ("伤害", "治疗"):
            menu.add_command(label=("✓ " if self.metric.get() == value else "") + value,
                             command=lambda v=value: self.choose_metric(v))
        menu.add_separator()
        menu.add_command(label="本场", command=lambda: self.choose_source(0))
        for index in range(len(self.history)):
            menu.add_command(label=f"历史战斗 {index+1}", command=lambda i=index+1: self.choose_source(i))
        if self.metric.get() == "伤害":
            menu.add_separator()
            for index,target in enumerate(self.target_ids):
                menu.add_command(label=f"目标 #{target}", command=lambda i=index: self.choose_target(i))
        menu.add_separator()
        menu.add_command(label="解锁位置" if self.locked else "锁定位置", command=self.toggle_lock)
        menu.add_command(label="打开主窗口", command=self.show_main)
        try:
            menu.tk_popup(self.window.winfo_x()+80, self.window.winfo_y()+24)
        finally:
            menu.grab_release()

    def choose_metric(self, value):
        self.metric.set(value)
        self.refresh_targets()

    def choose_source(self, index):
        self.source.current(index)
        self.refresh_targets()

    def choose_target(self, index):
        self.target.current(index)
        self.render_rows()

    def show(self):
        self.window.deiconify()
        self.window.lift()

    def hide(self):
        self.window.withdraw()
        if self.details is not None and self.details.winfo_exists():
            self.details.withdraw()

    def show_main(self):
        self.root.deiconify()
        self.root.lift()

    def toggle_lock(self):
        self.locked = not self.locked
        self.lock_button.configure(text="解锁" if self.locked else "锁定")
        self.title.configure(cursor="arrow" if self.locked else "fleur")

    def begin_drag(self, event):
        if not self.locked:
            self.drag_offset = (event.x_root-self.window.winfo_x(), event.y_root-self.window.winfo_y())

    def drag(self, event):
        if self.locked or not hasattr(self, "drag_offset"):
            return
        x, y = event.x_root-self.drag_offset[0], event.y_root-self.drag_offset[1]
        self.window.geometry(f"+{max(0,x)}+{max(0,y)}")

    def scroll(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def selected_snapshot(self):
        index = self.source.current()
        return self.history[index-1] if 0 < index <= len(self.history) else self.snapshot

    def update(self, snapshot, incomplete=False, history=()):
        index = self.source.current()
        previous = self.history[index-1] if 0 < index <= len(self.history) else None
        self.snapshot, self.history = snapshot, tuple(history)
        self.source["values"] = ("本场",) + tuple(f"历史战斗 {i+1}" for i in range(len(self.history)))
        retained = next((i+1 for i,item in enumerate(self.history) if item is previous), 0) if previous else 0
        self.source.current(retained)
        self.note.set(("数据可能不完整" if incomplete else "本地统计") + " · 兼容性待验证")
        self.refresh_targets()

    def refresh_targets(self):
        self.mode_label.configure(text=self.metric.get() + (" · 历史" if self.source.current() > 0 else ""))
        old = self.target.current()
        selected = self.target_ids[old] if 0 <= old < len(self.target_ids) else None
        self.target_ids = [target["target_id"] for target in self.selected_snapshot().get("targets", [])]
        healing = self.metric.get() == "治疗"
        self.target.configure(state="disabled" if healing else "readonly")
        self.target["values"] = tuple(f"目标 #{target_id}" for target_id in self.target_ids)
        if healing:
            self.target.set("治疗记录汇总（非有效治疗）")
        elif self.target_ids:
            self.target.current(self.target_ids.index(selected) if selected in self.target_ids else 0)
        else:
            self.target.set("等待战斗目标")
        self.render_rows()

    def render_rows(self):
        snapshot = self.selected_snapshot()
        self.ranking = []
        if self.metric.get() == "治疗":
            names = {p["actor_id"]: p.get("name") for t in snapshot.get("targets", []) for p in t["players"]}
            grouped = {}
            for heal in snapshot.get("healing", []):
                actor = heal["actor_id"]
                row = grouped.setdefault(actor, {"actor_id":actor, "name":names.get(actor), "total":0, "skills":[]})
                row["total"] += heal["healing"]
                row["skills"].append(heal)
            self.ranking = list(grouped.values())
        else:
            index, targets = self.target.current(), snapshot.get("targets", [])
            if 0 <= index < len(targets):
                # Per-target DPS is never added together.
                self.ranking = [dict(p, total=p["damage"]) for p in targets[index]["players"]]
        self.ranking.sort(key=lambda row: row["total"], reverse=True)
        self.resize_hud()
        self.draw()

    def draw(self):
        canvas = self.canvas
        canvas.delete("all")
        width, height = max(1, canvas.winfo_width()), 22
        maximum = max((row["total"] for row in self.ranking), default=0)
        total = sum(row["total"] for row in self.ranking)
        for index,row in enumerate(self.ranking):
            y, tag = index*height, f"player-{index}"
            canvas.create_rectangle(0,y,width,y+height-3,fill="#111f2c",outline="",tags=tag)
            fraction = row["total"]/maximum if maximum else 0
            canvas.create_rectangle(0,y,width*fraction,y+height-3,fill="#203b4b" if self.metric.get()=="伤害" else "#234238",outline="",tags=tag)
            name = row.get("name") or f'#{row["actor_id"]}'
            while name and self.text_font.measure(name) > width*.32:
                name = name[:-1]
            canvas.create_text(6,y+height/2-1,text=f"{index+1}. {name}",anchor="w",fill="#e4edf7",font=self.text_font,tags=tag)
            share = row["total"]/total if total else 0
            def compact(value):
                return f'{value/1_000_000:.1f}m' if value >= 1_000_000 else f'{value/1000:.1f}k' if value >= 1000 else f'{value:.0f}'
            value = f'{compact(row["total"])}  {share:.0%}'
            if "dps" in row:
                value = f'{compact(row["dps"])}/s  ·  ' + value
            canvas.create_text(width-6,y+height/2-1,text=value,anchor="e",fill="#e4edf7",font=self.text_font,tags=tag)
            canvas.tag_bind(tag,"<Button-1>",lambda _,i=index:self.show_details(i))
        if not self.ranking:
            canvas.create_text(width/2,17,text="等待战斗数据",fill="#687b8e",font=self.text_font)
        canvas.configure(scrollregion=(0,0,width,max(height*len(self.ranking),1)))

    def show_details(self, index):
        if not 0 <= index < len(self.ranking):
            return
        if self.details is not None and self.details.winfo_exists():
            self.details.destroy()
        row = self.ranking[index]
        self.details = tk.Toplevel(self.window)
        self.details.title((row.get("name") or f'#{row["actor_id"]}') + " · 技能明细（当前快照）")
        self.details.attributes("-topmost",True)
        self.details.geometry(f"{round(430*self.scale)}x{round(240*self.scale)}")
        tree = ttk.Treeview(self.details,columns=("skill","amount","count"),show="headings")
        healing = self.metric.get()=="治疗"
        for column,label in (("skill","技能 ID"),("amount","治疗记录总量" if healing else "伤害"),("count","记录次数" if healing else "命中次数")):
            tree.heading(column,text=label)
            tree.column(column,width=120,minwidth=60)
        tree.pack(fill="both",expand=True)
        for skill in row["skills"]:
            tree.insert("","end",values=(skill["skill_id"],f'{skill["healing" if healing else "damage"]:,}',skill["ticks" if healing else "hits"]))
