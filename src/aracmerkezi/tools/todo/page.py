from __future__ import annotations

from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from ... import themes, ui
from ...ui import ghost_button
from . import store as st

FILTERS = {"Bekleyen": "open", "Bugün": "today", "Geciken": "overdue", "Biten": "done", "Hepsi": "all"}
PRIORITY_LABELS = {"Normal": 0, "Yüksek": 1, "Acil": 2}
PRIORITY_MARK = {0: "", 1: "❗", 2: "🔥"}


def get_store(hub) -> st.TodoStore:
    if "todo" not in hub.services:
        store = st.TodoStore(hub.data_dir / "todo.db")
        hub.services["todo"] = store
        hub.on_close.append(store.close)
    return hub.services["todo"]


class TaskDialog(ctk.CTkToplevel):
    """Görevi düzenleme penceresi. Kaydedince `on_save(başlık, son_tarih, öncelik, not)` çağrılır."""

    def __init__(self, master, task: st.Task, on_save) -> None:
        super().__init__(master)
        self.on_save = on_save
        self.title("Görevi düzenle")
        self.geometry("460x420")
        self.configure(fg_color=ui.BG)
        self.transient(master)
        ctk.CTkLabel(self, text="Görevi düzenle", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=(18, 8))
        self.title_entry = ctk.CTkEntry(self, height=36)
        self.title_entry.insert(0, task.title)
        self.title_entry.pack(fill="x", padx=20)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(10, 0))
        self.due_entry = ctk.CTkEntry(row, width=130, height=34, placeholder_text="GG.AA.YYYY")
        if task.due:
            self.due_entry.insert(0, st.format_due(task.due))
        self.due_entry.pack(side="left")
        self.prio = ctk.CTkSegmentedButton(row, values=list(PRIORITY_LABELS), selected_color=ui.SEG_ON,
                                           selected_hover_color=ui.SEG_ON_HOVER)
        self.prio.set(st.PRIORITIES[task.priority])
        self.prio.pack(side="left", padx=12)
        self.notes = ctk.CTkTextbox(self, height=140, wrap="word")
        self.notes.insert("1.0", task.notes)
        self.notes.pack(fill="x", padx=20, pady=12)
        self.error = ctk.CTkLabel(self, text="", text_color=ui.WARN, anchor="w")
        self.error.pack(fill="x", padx=20)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=10)
        ctk.CTkButton(btns, text="Kaydet", width=110, command=self._save).pack(side="left", padx=6)
        ghost_button(btns, "Vazgeç", self.destroy, width=100).pack(side="left", padx=6)
        self.after(150, lambda: self.winfo_exists() and (self.lift(), self.title_entry.focus_set()))

    def _save(self) -> None:
        title = self.title_entry.get().strip()
        if not title:
            self.error.configure(text="Başlık boş olamaz.")
            return
        try:
            due = st.parse_due(self.due_entry.get())
        except ValueError as e:
            self.error.configure(text=str(e))
            return
        self.on_save(title, due, PRIORITY_LABELS[self.prio.get()], self.notes.get("1.0", "end").strip())
        self.destroy()


class TodoPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.store = get_store(hub)
        self.filter_var = ctk.StringVar(value="Bekleyen")
        self.prio_var = ctk.StringVar(value="Normal")

        ui.page_header(self, "Yapılacaklar", "Görevlerini yaz, son tarih ve öncelik ver, bitenleri işaretle.")
        add = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        add.pack(fill="x")
        row = ctk.CTkFrame(add, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 6))
        self.title_entry = ctk.CTkEntry(row, height=38, corner_radius=10, placeholder_text="➕  Yeni görev… (Enter ile ekle)")
        self.title_entry.pack(side="left", fill="x", expand=True)
        self.title_entry.bind("<Return>", lambda _e: self.add_task())
        self.due_entry = ctk.CTkEntry(row, width=120, height=38, placeholder_text="GG.AA.YYYY")
        self.due_entry.pack(side="left", padx=(8, 0))
        self.due_entry.bind("<Return>", lambda _e: self.add_task())
        ctk.CTkButton(row, text="Ekle", width=80, height=38, command=self.add_task).pack(side="left", padx=(8, 0))
        row2 = ctk.CTkFrame(add, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(row2, text="Öncelik", text_color=ui.MUTED).pack(side="left", padx=(0, 8))
        ctk.CTkSegmentedButton(row2, values=list(PRIORITY_LABELS), variable=self.prio_var, height=30,
                               selected_color=ui.SEG_ON, selected_hover_color=ui.SEG_ON_HOVER).pack(side="left")
        self.message = ctk.CTkLabel(row2, text="", text_color=ui.WARN, anchor="w")
        self.message.pack(side="left", padx=14)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(10, 6))
        ctk.CTkSegmentedButton(bar, values=list(FILTERS), variable=self.filter_var, height=32, selected_color=ui.SEG_ON,
                               selected_hover_color=ui.SEG_ON_HOVER, command=lambda _v: self.refresh()).pack(side="left")
        self.search = ctk.CTkEntry(bar, width=220, height=32, placeholder_text="🔎  Ara…")
        self.search.pack(side="left", padx=12)
        self.search.bind("<KeyRelease>", lambda _e: self.refresh())
        self.clear_btn = ghost_button(bar, "Bitenleri temizle", self.clear_done, width=140, danger=True)
        self.clear_btn.pack(side="right")

        self.counts = ctk.CTkLabel(self, text="", text_color=ui.MUTED, anchor="w")
        self.counts.pack(side="bottom", fill="x", pady=(6, 0))
        self.list = ctk.CTkScrollableFrame(self, fg_color=ui.CARD, corner_radius=14)
        self.list.pack(fill="both", expand=True)
        self.list.grid_columnconfigure(0, weight=1)
        self.refresh()

    # ---------- liste ----------
    def refresh(self) -> None:
        for w in self.list.winfo_children():
            w.destroy()
        tasks = self.store.list(FILTERS[self.filter_var.get()], self.search.get())
        if not tasks:
            ctk.CTkLabel(self.list, text="Burada gösterilecek görev yok.", text_color=ui.MUTED).grid(row=0, column=0, pady=40)
        for r, t in enumerate(tasks):
            self._row(r, t)
        c = self.store.counts()
        self.counts.configure(text=f"{c['open']} bekleyen  ·  {c['today']} bugün  ·  {c['overdue']} geciken  ·  {c['done']} biten")
        self.clear_btn.configure(state="normal" if c["done"] else "disabled")

    def _row(self, r: int, t: st.Task) -> None:
        card = ctk.CTkFrame(self.list, fg_color=ui.CARD_ALT, corner_radius=10)
        card.grid(row=r, column=0, sticky="ew", padx=6, pady=3)
        card.grid_columnconfigure(1, weight=1)
        var = ctk.BooleanVar(value=t.done)
        ctk.CTkCheckBox(card, text="", variable=var, width=26, command=lambda: self.toggle(t.id)).grid(
            row=0, column=0, rowspan=2, padx=(12, 4), pady=10)
        title = f"{PRIORITY_MARK[t.priority]} {t.title}".strip()
        ctk.CTkLabel(card, text=title, anchor="w", justify="left", wraplength=480, text_color=ui.MUTED if t.done else ui.TEXT,
                     font=ctk.CTkFont(size=14, overstrike=t.done)).grid(row=0, column=1, sticky="w", pady=(8, 0 if t.notes else 8))
        if t.notes:
            ctk.CTkLabel(card, text=t.notes, anchor="w", justify="left", wraplength=480, text_color=ui.MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=1, column=1, sticky="w", pady=(0, 8))
        status = st.due_status(t, date.today())
        if t.due:
            color = {"overdue": ui.DANGER, "today": ui.WARN, "soon": ui.ACCENT}.get(status, ui.TOGGLE_OFF)
            text = st.format_due(t.due) + {"overdue": "  · gecikti", "today": "  · bugün"}.get(status, "")
            ctk.CTkLabel(card, text=text, fg_color=color, corner_radius=8, height=24,
                         text_color=themes.readable_on(color) if status else ui.TEXT,
                         font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=2, rowspan=2, padx=8)
        ghost_button(card, "✎", lambda: self.edit(t.id), width=34).grid(row=0, column=3, rowspan=2, padx=2)
        ghost_button(card, "✕", lambda: self.delete(t.id), width=34, danger=True).grid(row=0, column=4, rowspan=2, padx=(2, 10))

    # ---------- eylemler ----------
    def add_task(self) -> None:
        try:
            due = st.parse_due(self.due_entry.get())
            self.store.add(self.title_entry.get(), due=due, priority=PRIORITY_LABELS[self.prio_var.get()])
        except ValueError as e:
            self.message.configure(text=str(e))
            return
        self.message.configure(text="")
        self.title_entry.delete(0, "end")
        self.due_entry.delete(0, "end")
        self.prio_var.set("Normal")
        self.refresh()

    def toggle(self, task_id: int) -> None:
        self.store.toggle(task_id)
        self.refresh()

    def delete(self, task_id: int) -> None:
        self.store.delete(task_id)
        self.refresh()

    def edit(self, task_id: int) -> None:
        task = self.store.get(task_id)
        if task is None:
            return

        def save(title, due, priority, notes):
            self.store.update(task_id, title=title, due=due, priority=priority, notes=notes)
            self.refresh()

        TaskDialog(self.winfo_toplevel(), task, save)

    def clear_done(self) -> None:
        n = self.store.counts()["done"]
        if n and messagebox.askyesno("Bitenleri temizle", f"{n} biten görev silinsin mi?\n(Bekleyen görevlere dokunulmaz.)"):
            self.store.clear_done()
            self.refresh()
