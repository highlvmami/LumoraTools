"""Dosya Düzenleyici aracı: klasörü uzantıya/tarihe göre düzenler, izler."""
from __future__ import annotations

import queue
import threading
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from duzenle import engine
from duzenle.config import DEFAULT_DATE_FORMAT
from duzenle.watcher import Watcher

from .. import ui
from ..registry import ToolInfo
from ..ui import (ACCENT, ACCENT_HOVER, CARD, DANGER, DANGER_HOVER, MUTED, OK, OK_HOVER, StatCard,
                  ghost_button, make_tree)

MODE_LABELS = {"Uzantıya göre": "uzanti", "Tarihe göre": "tarih", "Birleşik": "birlesik"}
MODE_HINTS = {
    "uzanti": "Resimler, Belgeler, Videolar… gibi kategorilere ayırır.",
    "tarih": "Dosyayı değiştirilme tarihine göre yıl/ay klasörlerine koyar.",
    "birlesik": "Önce kategori, sonra tarih: Resimler/2026/10",
}


class OrganizerPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.cfg = hub.settings_for("duzenleyici")
        self.folder_var = ctk.StringVar(value=self.cfg.get("folder", str(Path.home() / "Downloads")))
        mode = self.cfg.get("mode", "Uzantıya göre")
        self.mode_var = ctk.StringVar(value=mode if mode in MODE_LABELS else "Uzantıya göre")
        self.date_var = ctk.StringVar(value=self.cfg.get("date_format", DEFAULT_DATE_FORMAT))
        self.recursive_var = ctk.BooleanVar(value=False)
        self.plan: list[engine.Move] = []
        self.watcher: Watcher | None = None
        self.messages: queue.Queue[str] = queue.Queue()

        ui.page_header(self, "Dosya Düzenleyici", "Önce önizle, sonra tek tıkla yerleştir. Her işlem geri alınabilir.")
        self._folder_card()
        tabs = ctk.CTkTabview(self, fg_color="transparent", segmented_button_selected_color=ACCENT,
                              segmented_button_selected_hover_color=ACCENT_HOVER)
        tabs.pack(fill="both", expand=True, pady=(6, 0))
        self._build_organize(tabs.add("Düzenle"))
        self._build_watch(tabs.add("İzle"))

        hub.on_close.append(self._shutdown)
        self.after(250, self._drain_messages)

    # ---------- ortak klasör kartı ----------
    def _folder_card(self) -> None:
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        card.pack(fill="x")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkEntry(row, textvariable=self.folder_var, height=38, corner_radius=10,
                     placeholder_text="Düzenlenecek klasör").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Gözat", width=84, height=38, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.browse).pack(side="left", padx=(8, 0))
        ghost_button(row, "İndirilenler", lambda: self.folder_var.set(str(Path.home() / "Downloads")),
                     width=104).pack(side="left", padx=(8, 0))
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkSegmentedButton(row2, values=list(MODE_LABELS), variable=self.mode_var, height=34,
                               selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                               command=self._mode_changed).pack(side="left")
        self.hint = ctk.CTkLabel(row2, text=MODE_HINTS[self._mode_key()], text_color=MUTED)
        self.hint.pack(side="left", padx=14)
        date = ctk.CTkEntry(row2, textvariable=self.date_var, width=90, height=30)
        date.pack(side="right")
        date.bind("<FocusOut>", lambda _e: self._reset_preview())
        ctk.CTkLabel(row2, text="Tarih biçimi", text_color=MUTED).pack(side="right", padx=8)

    # ---------- Düzenle sekmesi ----------
    def _build_organize(self, tab) -> None:
        opts = ctk.CTkFrame(tab, fg_color="transparent")
        opts.pack(fill="x", pady=(4, 0))
        ctk.CTkSwitch(opts, text="Alt klasörleri de tara", variable=self.recursive_var,
                      progress_color=ACCENT).pack(side="left")
        ghost_button(opts, "↩  Geri al", self.undo, width=110, danger=True).pack(side="right")
        self.apply_btn = ctk.CTkButton(opts, text="✓  Düzenle", width=130, height=36, fg_color=OK,
                                       hover_color=OK_HOVER, state="disabled", command=self.apply)
        self.apply_btn.pack(side="right", padx=8)
        ctk.CTkButton(opts, text="🔍  Önizle", width=120, height=36, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=self.preview).pack(side="right")

        stats = ctk.CTkFrame(tab, fg_color="transparent")
        stats.pack(fill="x", pady=12)
        stats.grid_columnconfigure((0, 1, 2), weight=1, uniform="s")
        self.stat_files = StatCard(stats, "Taşınacak dosya")
        self.stat_dirs = StatCard(stats, "Hedef klasör")
        self.stat_top = StatCard(stats, "En kalabalık kategori")
        for i, c in enumerate((self.stat_files, self.stat_dirs, self.stat_top)):
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 7, 0 if i == 2 else 7))

        table_card = ctk.CTkFrame(tab, fg_color=CARD, corner_radius=14)
        table_card.pack(fill="both", expand=True)
        self.tree = make_tree(table_card, {"src": ("Dosya", 360), "dst": ("Yeni konum", 300)})
        self.empty_label = ctk.CTkLabel(table_card, text="Önizle'ye basarak neyin nereye taşınacağını gör.",
                                        text_color=MUTED)
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.status = ctk.CTkLabel(tab, text="", text_color=MUTED, anchor="w")
        self.status.pack(fill="x", pady=(8, 0))

    # ---------- İzle sekmesi ----------
    def _build_watch(self, tab) -> None:
        card = ctk.CTkFrame(tab, fg_color=CARD, corner_radius=14)
        card.pack(fill="x", pady=(4, 0))
        self.watch_label = ctk.CTkLabel(card, text="Klasör ve mod yukarıdaki seçimle aynıdır.", anchor="w")
        self.watch_label.pack(fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(card, text="Dosya boyutu 3 sn sabit kalınca taşınır; inmekte olan dosyalara dokunulmaz.",
                     text_color=MUTED, anchor="w").pack(fill="x", padx=18)
        self.watch_btn = ctk.CTkButton(card, text="▶  İzlemeyi başlat", height=40, fg_color=ACCENT,
                                       hover_color=ACCENT_HOVER, command=self.toggle_watch)
        self.watch_btn.pack(anchor="w", padx=18, pady=16)
        self.watch_count = StatCard(tab, "Bu oturumda yerleştirilen dosya", "0")
        self.watch_count.pack(fill="x", pady=12)
        self.log = ctk.CTkTextbox(tab, fg_color=CARD, corner_radius=14, state="disabled",
                                  font=ctk.CTkFont(family="Consolas", size=12))
        self.log.pack(fill="both", expand=True)

    # ---------- davranış ----------
    def _mode_key(self) -> str:
        return MODE_LABELS[self.mode_var.get()]

    def _date_format(self) -> str:
        return self.date_var.get().strip() or DEFAULT_DATE_FORMAT

    def _mode_changed(self, _value=None) -> None:
        self.hint.configure(text=MODE_HINTS[self._mode_key()])
        self._reset_preview()

    def browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if chosen:
            self.folder_var.set(str(Path(chosen)))
            self._reset_preview()

    def _folder(self) -> Path | None:
        folder = Path(self.folder_var.get().strip())
        if not folder.is_dir():
            messagebox.showerror("Klasör bulunamadı", f"Geçerli bir klasör seç:\n{folder}")
            return None
        return folder

    def _reset_preview(self) -> None:
        self.plan = []
        self.tree.delete(*self.tree.get_children())
        self.apply_btn.configure(state="disabled")
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        for c in (self.stat_files, self.stat_dirs, self.stat_top):
            c.set("—")

    def preview(self) -> None:
        folder = self._folder()
        if not folder:
            return
        self._reset_preview()
        self.status.configure(text="Taranıyor…")
        mode, fmt, rec = self._mode_key(), self._date_format(), self.recursive_var.get()

        def work():
            try:
                plan = engine.plan(folder, mode, fmt, rec)
                self.after(0, lambda: self._show_plan(folder, plan))
            except Exception as e:
                self.after(0, lambda: self.status.configure(text=f"Hata: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def _show_plan(self, folder: Path, plan: list[engine.Move]) -> None:
        self.plan = plan
        root = folder.resolve()
        if not plan:
            self.status.configure(text="Düzenlenecek dosya yok. Klasör zaten düzenli görünüyor.")
            return
        self.empty_label.place_forget()
        limit = 5000
        for m in plan[:limit]:
            self.tree.insert("", "end", values=(m.src.name, str(m.dst.parent.relative_to(root)) + "\\"))
        counts = Counter(m.dst.parent.relative_to(root) for m in plan)
        top, n = counts.most_common(1)[0]
        self.stat_files.set(len(plan))
        self.stat_dirs.set(len(counts))
        self.stat_top.set(f"{top} ({n})")
        extra = f" (ilk {limit} gösteriliyor)" if len(plan) > limit else ""
        self.status.configure(text=f"{len(plan)} dosya taşınmaya hazır{extra}.")
        self.apply_btn.configure(state="normal")

    def apply(self) -> None:
        folder = self._folder()
        if not folder or not self.plan:
            return
        if not messagebox.askyesno(
                "Onay", f"{len(self.plan)} dosya taşınacak.\nGeri al ile bu işlemi sonra geri alabilirsin.\n\nDevam edilsin mi?"):
            return
        plan = self.plan
        self.apply_btn.configure(state="disabled")
        self.status.configure(text="Taşınıyor…")

        def work():
            done, failed = engine.apply(folder, plan)
            self.after(0, lambda: self._applied(len(done), failed))

        threading.Thread(target=work, daemon=True).start()

    def _applied(self, done: int, failed: list) -> None:
        self._reset_preview()
        msg = f"✓ {done} dosya taşındı."
        if failed:
            msg += f"  {len(failed)} dosya atlandı (kilitli veya izin yok)."
        self.status.configure(text=msg)

    def undo(self) -> None:
        folder = self._folder()
        if not folder:
            return
        restored, skipped = engine.undo(folder)
        self._reset_preview()
        if restored == 0 and skipped == 0:
            self.status.configure(text="Geri alınacak işlem yok.")
        else:
            self.status.configure(text=f"↩ {restored} dosya geri alındı, {skipped} atlandı.")

    # ---------- izleme ----------
    def toggle_watch(self) -> None:
        if self.watcher and self.watcher.running:
            self.watcher.stop()
            self.watcher = None
            self._watch_ui(False)
            return
        folder = self._folder()
        if not folder:
            return
        self.watcher = Watcher(folder, self._mode_key(), self._date_format(), on_message=self.messages.put)
        self.watcher.start()
        self._watch_ui(True)

    def _watch_ui(self, on: bool) -> None:
        if on:
            self.watch_btn.configure(text="■  İzlemeyi durdur", fg_color=DANGER, hover_color=DANGER_HOVER)
            self.watch_label.configure(text=f"İzlenen klasör: {self.folder_var.get()}")
        else:
            self.watch_btn.configure(text="▶  İzlemeyi başlat", fg_color=ACCENT, hover_color=ACCENT_HOVER)
            self.watch_label.configure(text="Klasör ve mod yukarıdaki seçimle aynıdır.")

    def _drain_messages(self) -> None:
        wrote = False
        while True:
            try:
                msg = self.messages.get_nowait()
            except queue.Empty:
                break
            if not wrote:
                self.log.configure(state="normal")
                wrote = True
            self.log.insert("end", msg + "\n")
        if wrote:
            self.log.see("end")
            self.log.configure(state="disabled")
        if self.watcher:
            self.watch_count.set(self.watcher.moved_count)
        self.after(250, self._drain_messages)

    def _shutdown(self) -> None:
        if self.watcher:
            self.watcher.stop()
        self.cfg.update(folder=self.folder_var.get(), mode=self.mode_var.get(), date_format=self._date_format())


TOOL = ToolInfo(
    id="duzenleyici",
    name="Dosya Düzenleyici",
    icon="📁",
    description="Klasörü uzantıya veya tarihe göre otomatik düzenler; yeni gelen dosyaları anında yerleştirir.",
    build=lambda parent, hub: OrganizerPage(parent, hub),
    order=10,
)
