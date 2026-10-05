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
        self.window.attributes("-alpha", .94)
        self.window.configure(background="#756d56")
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96)
        self.window.geometry(f"{round(380*self.scale)}x{round(290*self.scale)}+40+80")
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        body = tk.Frame(self.window, background="#101827", padx=8, pady=6)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        bar = ttk.Frame(body)
        bar.pack(fill="x")
        self.title = tk.Label(bar, text="亚特雷亚 · 战斗", background="#101827", foreground="#e5d2a2",
                              font=("Microsoft YaHei UI", 10, "bold"), cursor="fleur")
        self.title.pack(side="left", fill="x", expand=True)
        for widget in (bar, self.title):
            widget.bind("<ButtonPress-1>", self.begin_drag)
            widget.bind("<B1-Motion>", self.drag)
        ttk.Button(bar, text="×", width=2, command=self.hide).pack(side="right")
        self.lock_button = ttk.Button(bar, text="锁定", width=4, command=self.toggle_lock)
        self.lock_button.pack(side="right", padx=3)
        ttk.Button(bar, text="主窗", width=4, command=self.show_main).pack(side="right")
        filters = ttk.Frame(body)
        filters.pack(fill="x", pady=(6, 3))
        self.metric = ttk.Combobox(filters, values=("伤害", "治疗"), state="readonly", width=6)
        self.metric.current(0)
        self.metric.pack(side="left", padx=(0, 6))
        self.source = ttk.Combobox(filters, values=("本场",), state="readonly", width=15)
        self.source.current(0)
        self.source.pack(side="left", fill="x", expand=True)
        for widget in (self.metric, self.source):
            widget.bind("<<ComboboxSelected>>", lambda _: self.refresh_targets())
        self.target = ttk.Combobox(body, state="readonly", width=20)
        self.target.pack(fill="x", pady=(0, 5))
        self.target.bind("<<ComboboxSelected>>", lambda _: self.render_rows())
        area = ttk.Frame(body)
        area.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(area, background="#101827", highlightthickness=0, height=120)
        scroll = ttk.Scrollbar(area, command=self.canvas.yview)
        scroll.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _: self.draw())
        self.canvas.bind("<MouseWheel>", self.scroll)
        self.text_font = font.Font(root=root, family="Microsoft YaHei UI", size=9)
        self.note = tk.StringVar(value="等待战斗数据 · 兼容性待验证")
        ttk.Label(body, textvariable=self.note, style="Muted.TLabel").pack(anchor="w", pady=(5, 0))

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
        self.draw()

    def draw(self):
        canvas = self.canvas
        canvas.delete("all")
        width, height = max(1, canvas.winfo_width()), round(29*self.scale)
        maximum = max((row["total"] for row in self.ranking), default=0)
        total = sum(row["total"] for row in self.ranking)
        for index,row in enumerate(self.ranking):
            y, tag = index*height, f"player-{index}"
            canvas.create_rectangle(0,y,width,y+height-3,fill="#1c293c",outline="",tags=tag)
            fraction = row["total"]/maximum if maximum else 0
            canvas.create_rectangle(0,y,width*fraction,y+height-3,fill="#245667" if self.metric.get()=="伤害" else "#285849",outline="",tags=tag)
            name = row.get("name") or f'#{row["actor_id"]}'
            while name and self.text_font.measure(name) > width*.32:
                name = name[:-1]
            canvas.create_text(6,y+height/2-1,text=f"{index+1}. {name}",anchor="w",fill="#e4edf7",font=self.text_font,tags=tag)
            share = row["total"]/total if total else 0
            value = f'{row["total"]:,}  {share:.0%}'
            if "dps" in row:
                value = f'{row["dps"]:,.0f}/s  ·  ' + value
            canvas.create_text(width-6,y+height/2-1,text=value,anchor="e",fill="#e4edf7",font=self.text_font,tags=tag)
            canvas.tag_bind(tag,"<Button-1>",lambda _,i=index:self.show_details(i))
        if not self.ranking:
            canvas.create_text(width/2,45*self.scale,text="等待战斗数据",fill="#92a4bf",font=self.text_font)
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
