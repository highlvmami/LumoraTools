from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from ... import ui
from ...fmt import human_size
from ...ui import ghost_button, make_tree
from . import programs as pr

SORTS = {"Ada göre": "ad", "Boyuta göre": "boyut", "Yeni yüklenen": "tarih"}


def open_folder(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - kullanıcının kendi klasörü
    else:
        subprocess.Popen(["xdg-open", path])


class UninstallPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        try:
            self.backend = pr.WinBackend()
        except NotImplementedError:
            self.backend = None
        self.all: list[pr.Program] = []
        self.visible: dict[str, pr.Program] = {}
        self.sort_var = ctk.StringVar(value="Ada göre")
        self.updates_var = ctk.BooleanVar(value=False)

        ui.page_header(self, "Program Kaldırıcı",
                       "Yüklü programları boyutları ve yüklenme tarihleriyle gör; kaldırmayı programın kendi kaldırıcısı yapar.")
        bar = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        bar.pack(fill="x")
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 6))
        self.entry = ctk.CTkEntry(row, height=36, corner_radius=10, placeholder_text="🔎  Program veya yayıncı ara…")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<KeyRelease>", lambda _e: self.render())
        ghost_button(row, "⟳  Yenile", self.reload, width=96).pack(side="left", padx=(10, 0))
        row2 = ctk.CTkFrame(bar, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkSegmentedButton(row2, values=list(SORTS), variable=self.sort_var, height=32, selected_color=ui.SEG_ON,
                               selected_hover_color=ui.SEG_ON_HOVER, command=lambda _v: self.render()).pack(side="left")
        ctk.CTkSwitch(row2, text="Güncellemeleri göster", variable=self.updates_var, progress_color=ui.ACCENT,
                      command=self.reload).pack(side="left", padx=18)
        self.count = ctk.CTkLabel(row2, text="", text_color=ui.MUTED)
        self.count.pack(side="right")

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(side="bottom", fill="x", pady=(8, 0))
        self.remove_btn = ctk.CTkButton(foot, text="🗑  Kaldır…", width=130, height=38, fg_color=ui.DANGER,
                                        hover_color=ui.DANGER_HOVER, text_color=ui.DANGER_TEXT, state="disabled",
                                        command=self.remove)
        self.remove_btn.pack(side="left")
        self.folder_btn = ghost_button(foot, "📂  Klasörü aç", self.open_location, width=130)
        self.folder_btn.pack(side="left", padx=8)
        self.folder_btn.configure(state="disabled")
        ghost_button(foot, "⚙  Windows Uygulamalar", self.open_settings, width=170).pack(side="left")
        self.status = ctk.CTkLabel(foot, text="", text_color=ui.MUTED, anchor="e")
        self.status.pack(side="right")

        holder = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        holder.pack(fill="both", expand=True, pady=(10, 0))
        self.tree = make_tree(holder, {"name": ("Program", 260), "version": ("Sürüm", 90), "publisher": ("Yayıncı", 150),
                                       "size": ("Boyut", 80), "date": ("Yüklenme", 90)})
        self.tree.column("size", anchor="e", stretch=False)
        self.tree.column("date", stretch=False)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._selection_changed())
        self.reload()

    # ---------- liste ----------
    def reload(self) -> None:
        if self.backend is None:
            self.count.configure(text="Bu araç yalnızca Windows'ta çalışır.")
            return
        self.all = pr.list_programs(self.backend, include_updates=self.updates_var.get())
        self.render()

    def render(self) -> None:
        q = self.entry.get().strip().lower()
        shown = [p for p in self.all if not q or q in p.name.lower() or q in p.publisher.lower()]
        shown = pr.sort_programs(shown, SORTS[self.sort_var.get()])
        self.tree.delete(*self.tree.get_children())
        self.visible = {}
        for i, p in enumerate(shown):
            iid = str(i)
            self.visible[iid] = p
            self.tree.insert("", "end", iid=iid, values=(p.name, p.version, p.publisher,
                                                         human_size(p.size) if p.size else "—", p.install_date or "—"))
        known = sum(p.size or 0 for p in shown)
        self.count.configure(text=f"{len(shown)} program" + (f"  ·  bilinen boyut toplamı {human_size(known)}" if known else ""))
        self._selection_changed()

    def _selected(self) -> pr.Program | None:
        sel = self.tree.selection()
        return self.visible.get(sel[0]) if sel else None

    def _selection_changed(self) -> None:
        p = self._selected()
        self.remove_btn.configure(state="normal" if p and p.removable else "disabled")
        self.folder_btn.configure(state="normal" if p and p.location and Path(p.location).is_dir() else "disabled")
        if p and not p.removable:
            self.status.configure(text="Bu program Windows'a kayıtlı bir kaldırıcıya sahip değil ya da kaldırılması engelli.")
        elif p:
            self.status.configure(text="")

    # ---------- eylemler ----------
    def remove(self) -> None:
        p = self._selected()
        cmd = pr.uninstall_command(p) if p else None
        if not p or cmd is None:
            return
        who = f"{p.name}" + (f" ({p.version})" if p.version else "") + (f"\nYayıncı: {p.publisher}" if p.publisher else "")
        if not messagebox.askyesno("Programı kaldır",
                                   f"{who}\n\nBu programın KENDİ kaldırıcısı başlatılacak; kaldırma işlemi onun "
                                   "penceresinde onaylanır ve tamamlanır.\nDevam edilsin mi?", icon="warning"):
            return
        try:
            if isinstance(cmd, list):
                subprocess.Popen(cmd)                        # MSI: argüman listesi, kabuk yok
            else:
                subprocess.Popen(cmd, shell=True)            # programın kayıtlı kaldırma komutu (Windows Ayarları'yla aynı)
        except OSError as e:
            self.status.configure(text=f"Kaldırıcı başlatılamadı: {e}")
            return
        self.status.configure(text=f"{p.name} kaldırıcısı başlatıldı. İşlem bitince 'Yenile'ye bas.")

    def open_location(self) -> None:
        p = self._selected()
        if p and p.location and Path(p.location).is_dir():
            open_folder(p.location)

    def open_settings(self) -> None:
        try:
            os.startfile("ms-settings:appsfeatures")  # noqa: S606
        except (OSError, AttributeError):
            self.status.configure(text="Windows Ayarları açılamadı.")
