from __future__ import annotations

import queue
import threading
from tkinter import messagebox

import customtkinter as ctk

from ... import ui
from ...fmt import human_size
from ...ui import make_tree
from . import procs as pc

SORTS = {"Belleğe göre": "bellek", "İşlemciye göre": "cpu", "Ada göre": "ad"}
SAMPLE_EVERY = 2.0          # saniye
MAX_ROWS = 400


class ProcessesPage(ctk.CTkFrame):
    def __init__(self, parent, hub, sampler=None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.sampler = sampler or pc.ProcessSampler()
        self.protected = pc.own_pids()
        self.raw: list[pc.Proc] = []
        self.shown: dict[str, pc.Proc] = {}
        self.events: queue.Queue = queue.Queue()
        self._sampling = False
        self._since = SAMPLE_EVERY               # ilk turda hemen ölç
        self.sort_var = ctk.StringVar(value="Belleğe göre")
        self.group_var = ctk.BooleanVar(value=True)
        self.live_var = ctk.BooleanVar(value=True)

        ui.page_header(self, "İşlem Yöneticisi", "Çalışan programların bellek ve işlemci kullanımı; takılanı kapatabilirsin.")
        bar = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        bar.pack(fill="x")
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 6))
        self.entry = ctk.CTkEntry(row, height=36, corner_radius=10, placeholder_text="🔎  Ad ya da PID ara…")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<KeyRelease>", lambda _e: self._render())
        self.kill_btn = ctk.CTkButton(row, text="⏹  Sonlandır", width=120, height=36, fg_color=ui.DANGER,
                                      hover_color=ui.DANGER_HOVER, text_color=ui.DANGER_TEXT, state="disabled",
                                      command=self.terminate_selected)
        self.kill_btn.pack(side="left", padx=(10, 0))
        row2 = ctk.CTkFrame(bar, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkSegmentedButton(row2, values=list(SORTS), variable=self.sort_var, height=32, selected_color=ui.SEG_ON,
                               selected_hover_color=ui.SEG_ON_HOVER, command=lambda _v: self._render()).pack(side="left")
        ctk.CTkSwitch(row2, text="Aynı programı grupla", variable=self.group_var, progress_color=ui.ACCENT,
                      command=self._render).pack(side="left", padx=16)
        ctk.CTkSwitch(row2, text="Canlı", variable=self.live_var, progress_color=ui.OK).pack(side="left")
        self.summary = ctk.CTkLabel(row2, text="", text_color=ui.MUTED)
        self.summary.pack(side="right")

        self.status = ctk.CTkLabel(self, text="", anchor="w", justify="left", text_color=ui.MUTED, wraplength=820)
        self.status.pack(side="bottom", fill="x", pady=(6, 0))
        holder = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        holder.pack(fill="both", expand=True, pady=(10, 0))
        self.tree = make_tree(holder, {"name": ("Program", 280), "pid": ("PID", 70), "cpu": ("İşlemci", 80),
                                       "mem": ("Bellek", 90), "status": ("Durum", 90)})
        for col in ("pid", "cpu", "mem"):
            self.tree.column(col, anchor="e", stretch=False)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._selection_changed())
        self.tree.bind("<Delete>", lambda _e: self.terminate_selected())
        self._loop()

    # ---------- ölçüm döngüsü ----------
    def _loop(self) -> None:
        if not self.winfo_exists():                       # tema değişiminde sayfa yıkıldıysa döngü durur
            return
        self._drain()
        self._since += 0.3
        if self.live_var.get() and self.winfo_ismapped() and not self._sampling and self._since >= SAMPLE_EVERY:
            self._since = 0.0
            self._sampling = True
            threading.Thread(target=self._sample_worker, daemon=True).start()
        self.after(300, self._loop)

    def _sample_worker(self) -> None:
        try:
            self.events.put(("sample", self.sampler.sample()))
        except Exception as e:                            # ölçüm hiçbir hatada döngüyü öldürmemeli
            self.events.put(("error", str(e)))

    def _drain(self) -> None:
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                return
            if ev[0] == "sample":
                self._sampling = False
                self.raw = ev[1]
                self._render()
            elif ev[0] == "error":
                self._sampling = False
                self.status.configure(text=f"Ölçüm hatası: {ev[1]}")
            elif ev[0] == "killed":
                self._killed(ev[1], ev[2], ev[3])

    # ---------- liste ----------
    def _render(self) -> None:
        rows = pc.group(self.raw) if self.group_var.get() else list(self.raw)
        rows = pc.sort_procs(pc.filter_procs(rows, self.entry.get()), SORTS[self.sort_var.get()])[:MAX_ROWS]
        selected = self._selected_iid()
        top = self.tree.yview()[0]
        self.tree.delete(*self.tree.get_children())
        self.shown = {}
        for p in rows:
            iid = f"p{p.pid}"
            self.shown[iid] = p
            name = f"{p.name}  ({p.count} süreç)" if p.count > 1 else p.name
            self.tree.insert("", "end", iid=iid, values=(name, p.pid if p.count == 1 else "—", f"%{p.cpu:.1f}",
                                                         human_size(p.rss), p.status))
        if selected in self.shown:
            self.tree.selection_set(selected)
        self.tree.yview_moveto(top)
        total = sum(p.rss for p in self.raw)
        self.summary.configure(text=f"{len(self.raw)} süreç  ·  toplam bellek {human_size(total)}")
        self._selection_changed()

    def _selected_iid(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _selected(self) -> pc.Proc | None:
        iid = self._selected_iid()
        return self.shown.get(iid) if iid else None

    def _selection_changed(self) -> None:
        p = self._selected()
        self.kill_btn.configure(state="normal" if p else "disabled")
        if p:
            level, reason = pc.risk(p.name, p.pid, self.protected)
            if level != "ok":
                self.status.configure(text=("⛔ " if level == "block" else "⚠ ") + reason)
            elif p.count > 1:
                self.status.configure(text=f"{p.name}: {p.count} süreç, toplam {human_size(p.rss)}. "
                                           "'Sonlandır' hepsini kapatır.")
            else:
                self.status.configure(text="")

    # ---------- sonlandırma ----------
    def terminate_selected(self, force: bool = False) -> None:
        p = self._selected()
        if not p:
            return
        pids = list(p.all_pids)
        names = {pid: p.name for pid in pids}
        levels = [pc.risk(p.name, pid, self.protected) for pid in pids]
        if all(level == "block" for level, _ in levels):
            messagebox.showwarning("Sonlandırılamaz", levels[0][1])
            return
        warn = next((reason for level, reason in levels if level == "warn"), "")
        what = f"{p.name}" + (f" ({len(pids)} süreç)" if len(pids) > 1 else f" (PID {p.pid})")
        text = (f"{what} sonlandırılsın mı?\n\nKaydedilmemiş çalışmalar kaybolabilir."
                + (f"\n\n⚠ {warn}" if warn else "") + ("\n\nZORLA kapatılacak." if force else ""))
        if not messagebox.askyesno("Sonlandır", text, icon="warning"):
            return
        self.kill_btn.configure(state="disabled")
        self.status.configure(text="Sonlandırılıyor…")

        def work():
            res = pc.terminate(pids, names, self.protected, force=force)
            self.events.put(("killed", res, p.name, force))

        threading.Thread(target=work, daemon=True).start()

    def _killed(self, res: pc.KillResult, name: str, force: bool) -> None:
        parts = []
        if res.closed:
            parts.append(f"✓ {len(res.closed)} süreç kapandı")
        if res.blocked:
            parts.append(f"{len(res.blocked)} süreç korumalı olduğu için atlandı")
        if res.failed:
            parts.append(f"{len(res.failed)} süreç kapatılamadı ({res.failed[0][1]})")
        self.status.configure(text="  ·  ".join(parts) or "Hiçbir süreç kapatılmadı.")
        self._since = SAMPLE_EVERY                         # listeyi hemen yenile
        if res.still_running and not force:
            if messagebox.askyesno("Kapanmadı", f"{len(res.still_running)} süreç nazikçe kapanmadı. "
                                                f"Zorla kapatılsın mı?\n(Kaydedilmemiş çalışmalar kaybolur.)", icon="warning"):
                self.terminate_selected(force=True)
