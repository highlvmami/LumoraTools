"""Ayarlar'daki menü düzenleyici: araçları sürükleyerek sırala, anahtarla gizle/göster."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .ui import ACCENT, MUTED

ROW_H = 50
ROW_COLOR = ("#f3f4f8", "#272b45")
DRAG_COLOR = ("#e0e7ff", "#343a63")


class MenuEditor(ctk.CTkFrame):
    """entries: [(id, etiket)]. Değişince on_change(sıra: list[str], gizliler: set[str]) çağrılır."""

    def __init__(self, master, entries: list[tuple[str, str]], order: list[str], hidden: set[str],
                 on_change: Callable[[list[str], set[str]], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self.labels = dict(entries)
        self.order = [i for i in order if i in self.labels]
        self.on_change = on_change
        self._drag: str | None = None
        self._grab_dy = 0
        self.vars: dict[str, ctk.BooleanVar] = {}
        self.rows: dict[str, ctk.CTkFrame] = {}

        self.box = ctk.CTkFrame(self, fg_color="transparent", height=max(1, len(self.order)) * ROW_H)
        self.box.pack(fill="x")
        self.box.pack_propagate(False)
        for tid in self.order:
            self._make_row(tid, visible=tid not in hidden)
        self._layout()

    # ---------- dışarıdan ----------
    def hidden(self) -> set[str]:
        return {tid for tid, var in self.vars.items() if not var.get()}

    def set_state(self, order: list[str], hidden: set[str]) -> None:
        """Satırların sırasını ve anahtarlarını dışarıdan günceller (ör. 'Varsayılana dön')."""
        self.order = [i for i in order if i in self.rows] + [i for i in self.rows if i not in order]
        for tid, var in self.vars.items():
            var.set(tid not in hidden)
        self._layout()

    # ---------- satırlar ----------
    def _make_row(self, tid: str, visible: bool) -> None:
        row = ctk.CTkFrame(self.box, fg_color=ROW_COLOR, corner_radius=10, height=ROW_H - 6)
        row.pack_propagate(False)  # yükseklik sabit kalsın (CTk, place() ile yükseklik verilmesine izin vermez)
        handle = ctk.CTkLabel(row, text="⠿", width=34, font=ctk.CTkFont(size=20), text_color=MUTED, cursor="fleur")
        handle.pack(side="left", padx=(8, 0))
        name = ctk.CTkLabel(row, text=self.labels[tid], anchor="w", cursor="fleur")
        name.pack(side="left", fill="x", expand=True, padx=6)
        var = ctk.BooleanVar(value=visible)
        ctk.CTkSwitch(row, text="Görünür", variable=var, progress_color=ACCENT, width=90,
                      command=self._changed).pack(side="right", padx=14)
        for w in (row, handle, name):
            w.bind("<ButtonPress-1>", lambda e, t=tid: self._press(t, e))
            w.bind("<B1-Motion>", lambda e, t=tid: self._motion(t, e))
            w.bind("<ButtonRelease-1>", lambda e, t=tid: self._release(t, e))
        self.vars[tid] = var
        self.rows[tid] = row

    def _slot_y(self, tid: str) -> int:
        return self.order.index(tid) * ROW_H

    def _layout(self) -> None:
        for tid in self.order:
            if tid != self._drag:  # sürüklenen satır imleci izler
                self.rows[tid].place(x=0, y=self._slot_y(tid), relwidth=1)

    # ---------- sürükle-bırak ----------
    def _press(self, tid: str, event) -> None:
        self._drag = tid
        self._grab_dy = event.y_root - self.rows[tid].winfo_rooty()
        self.rows[tid].configure(fg_color=DRAG_COLOR)
        self.rows[tid].lift()

    def _motion(self, tid: str, event) -> None:
        if self._drag != tid:
            return
        top = event.y_root - self.box.winfo_rooty() - self._grab_dy
        top = max(0, min(top, (len(self.order) - 1) * ROW_H))
        self.rows[tid].place(x=0, y=top, relwidth=1)
        target = max(0, min(len(self.order) - 1, int((top + ROW_H / 2) // ROW_H)))
        if target != self.order.index(tid):
            self.order.remove(tid)
            self.order.insert(target, tid)
            self._layout()

    def _release(self, tid: str, _event) -> None:
        if self._drag != tid:
            return
        self._drag = None
        self.rows[tid].configure(fg_color=ROW_COLOR)
        self._layout()
        self._changed()

    def _changed(self) -> None:
        self.on_change(list(self.order), self.hidden())
