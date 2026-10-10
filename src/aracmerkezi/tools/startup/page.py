from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace

import customtkinter as ctk

from ... import ui
from ...ui import ghost_button
from . import entries as st


def reveal(path: str) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])


class StartupPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        try:
            self.backend = st.WinBackend()
        except NotImplementedError:
            self.backend = None
        self.entries: list[st.Entry] = []

        ui.page_header(self, "Başlangıç Programları",
                       "Windows açılırken kendiliğinden başlayan programlar. Anahtarla kapat ya da aç.")
        bar = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        bar.pack(fill="x")
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        self.summary = ctk.CTkLabel(row, text="", anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        self.summary.pack(side="left")
        ghost_button(row, "⟳  Yenile", self.refresh, width=100).pack(side="right")
        ctk.CTkLabel(bar, text="Kapattığın program silinmez; yalnızca Windows açılırken başlamaz. Değişiklik bir sonraki "
                               "oturum açışında geçerli olur ve yalnızca senin hesabın için uygulanır. Ne olduğunu "
                               "bilmediğin, Microsoft veya sürücü (ses, ekran kartı) programlarını kapatma.",
                     text_color=ui.MUTED, anchor="w", justify="left", wraplength=820).pack(fill="x", padx=18, pady=(0, 12))
        self.status = ctk.CTkLabel(self, text="", anchor="w", text_color=ui.MUTED)
        self.status.pack(fill="x", pady=(8, 0))
        self.list = ctk.CTkScrollableFrame(self, fg_color=ui.CARD, corner_radius=14)
        self.list.pack(fill="both", expand=True, pady=(6, 0))
        self.list.grid_columnconfigure(1, weight=1)
        self.refresh()

    def refresh(self) -> None:
        for w in self.list.winfo_children():
            w.destroy()
        if self.backend is None:
            ctk.CTkLabel(self.list, text="Bu araç yalnızca Windows'ta çalışır.", text_color=ui.MUTED).grid(
                row=0, column=0, pady=30, padx=20)
            return
        self.entries = st.list_entries(self.backend)
        self._update_summary()
        if not self.entries:
            ctk.CTkLabel(self.list, text="Açılışta başlayan program bulunamadı.", text_color=ui.MUTED).grid(
                row=0, column=0, pady=30, padx=20)
            return
        last_source = None
        r = 0
        for entry in sorted(self.entries, key=lambda e: (e.source, e.name.lower())):
            if entry.source != last_source:
                ctk.CTkLabel(self.list, text=entry.source.upper(), text_color=ui.MUTED, anchor="w",
                             font=ctk.CTkFont(size=11, weight="bold")).grid(
                    row=r, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 2))
                last_source, r = entry.source, r + 1
            self._row(r, entry)
            r += 1

    def _row(self, r: int, entry: st.Entry) -> None:
        var = ctk.BooleanVar(value=entry.enabled)
        sw = ctk.CTkSwitch(self.list, text="", variable=var, width=46, progress_color=ui.OK,
                           command=lambda: self._toggle(entry, var))
        sw.grid(row=r, column=0, padx=(14, 4), pady=4)
        label = ctk.CTkFrame(self.list, fg_color="transparent")
        label.grid(row=r, column=1, sticky="ew", pady=4)
        ctk.CTkLabel(label, text=entry.name, anchor="w", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        short = entry.command if len(entry.command) <= 90 else entry.command[:90] + "…"
        ctk.CTkLabel(label, text=short, anchor="w", text_color=ui.MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w")
        path = st.command_path(entry.command)
        btn = ghost_button(self.list, "📂", lambda p=path: self._reveal(p), width=40)
        btn.configure(height=30)
        btn.grid(row=r, column=2, padx=(4, 14), pady=4)
        if path is None or not path.exists():
            btn.configure(state="disabled")

    def _reveal(self, path) -> None:
        if path and path.exists():
            reveal(str(path))

    def _toggle(self, entry: st.Entry, var: ctk.BooleanVar) -> None:
        enabled = var.get()
        try:
            st.set_enabled(self.backend, entry, enabled)
        except OSError as e:
            var.set(not enabled)                       # yazılamadı: anahtarı eski haline döndür
            self.status.configure(text=f"Değiştirilemedi: {e}")
            return
        self.status.configure(text=f"{'✓ Açıldı' if enabled else '✓ Kapatıldı'}: {entry.name}   "
                                   "(bir sonraki oturum açışında geçerli olur)")
        key = (entry.source_id, entry.name)
        self.entries = [replace(e, enabled=enabled) if (e.source_id, e.name) == key else e for e in self.entries]
        self._update_summary()

    def _update_summary(self) -> None:
        on = sum(e.enabled for e in self.entries)
        self.summary.configure(text=f"{on} program açılışta başlıyor   ·   {len(self.entries) - on} tanesi kapalı")
