from __future__ import annotations

from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from ... import ui
from ...ui import ACCENT, ACCENT_HOVER, CARD, MUTED, OK, StatCard, ghost_button, make_tree
from .monitor import ClipboardMonitor
from .store import Clip, ClipStore


def get_service(hub) -> tuple[ClipStore, ClipboardMonitor]:
    """Depo ve izleyici hub başına bir kez oluşturulur (sayfa açılmasa da arka planda çalışır)."""
    if "clipboard" not in hub.services:
        store = ClipStore(hub.data_dir / "clipboard.db")
        monitor = ClipboardMonitor(hub, store)
        hub.services["clipboard"] = (store, monitor)

        def close():
            monitor.stop()
            store.close()

        hub.on_close.append(close)
    return hub.services["clipboard"]


def _one_line(text: str, limit: int = 140) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


class ClipboardPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.store, self.monitor = get_service(hub)
        self.clips: dict[str, Clip] = {}

        ui.page_header(self, "Pano Geçmişi", "Kopyaladığın her metin burada saklanır. Çift tıkla, tekrar panoya alınır.")

        top = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        top.pack(fill="x")
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        # placeholder_text, textvariable ile birlikte çalışmaz; bu yüzden olaya bağlıyız
        self.entry = ctk.CTkEntry(row, height=38, corner_radius=10, placeholder_text="🔎  Geçmişte ara…")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<KeyRelease>", lambda _e: self.refresh())
        self.rec_var = ctk.BooleanVar(value=not self.monitor.paused)
        ctk.CTkSwitch(row, text="Kaydediyor", variable=self.rec_var, progress_color=OK,
                      command=self._toggle_recording).pack(side="left", padx=16)
        ghost_button(row, "🗑  Temizle", self._clear, width=100, danger=True).pack(side="left")

        self.stat = StatCard(self, "Kayıtlı öğe", "0")
        self.stat.pack(fill="x", pady=12)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3, uniform="b")
        body.grid_columnconfigure(1, weight=2, uniform="b")
        body.grid_rowconfigure(0, weight=1)

        table = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14)
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.tree = make_tree(table, {"pin": ("", 34), "time": ("Zaman", 96), "text": ("Metin", 340)})
        self.tree.column("pin", stretch=False)
        self.tree.column("time", stretch=False)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_detail())
        self.tree.bind("<Double-1>", lambda _e: self.copy_selected())
        self.tree.bind("<Return>", lambda _e: self.copy_selected())
        self.tree.bind("<Delete>", lambda _e: self.delete_selected())

        side = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14)
        side.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.detail = ctk.CTkTextbox(side, fg_color="transparent", wrap="word", state="disabled")
        self.detail.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        btns = ctk.CTkFrame(side, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(btns, text="Kopyala", width=84, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.copy_selected).pack(side="left")
        self.pin_btn = ghost_button(btns, "📌 Sabitle", self.toggle_pin, width=96)
        self.pin_btn.pack(side="left", padx=8)
        ghost_button(btns, "Sil", self.delete_selected, width=60, danger=True).pack(side="left")
        self.status = ctk.CTkLabel(side, text="", text_color=MUTED, anchor="w")
        self.status.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(self, text="Not: Parola yöneticisinden kopyaladıkların da kaydedilebilir. "
                                "Gerekirse 'Kaydediyor' anahtarını kapat.", text_color=MUTED,
                     anchor="w").pack(fill="x", pady=(8, 0))

        self.monitor.listeners.append(self._on_new_clip)
        self.refresh()

    # ---------- liste ----------
    def _on_new_clip(self) -> None:
        if self.winfo_exists():
            self.refresh()

    def refresh(self) -> None:
        selected = self._selected_id()
        self.tree.delete(*self.tree.get_children())
        self.clips = {}
        for c in self.store.list(self.entry.get()):
            iid = str(c.id)
            self.clips[iid] = c
            when = datetime.fromtimestamp(c.ts).strftime("%d.%m %H:%M")
            self.tree.insert("", "end", iid=iid, values=("📌" if c.pinned else "", when, _one_line(c.text)))
        self.stat.set(self.store.count())
        if selected and selected in self.clips:
            self.tree.selection_set(selected)
        else:
            self._show_detail()

    def _selected_id(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _selected(self) -> Clip | None:
        iid = self._selected_id()
        return self.clips.get(iid) if iid else None

    def _show_detail(self) -> None:
        clip = self._selected()
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        if clip:
            self.detail.insert("1.0", clip.text)
            self.pin_btn.configure(text="📌 Çöz" if clip.pinned else "📌 Sabitle")
        else:
            self.detail.insert("1.0", "Ayrıntı için listeden bir öğe seç.")
        self.detail.configure(state="disabled")

    # ---------- eylemler ----------
    def copy_selected(self) -> None:
        clip = self._selected()
        if not clip:
            return
        self.clipboard_clear()
        self.clipboard_append(clip.text)
        self.status.configure(text="✓ Panoya kopyalandı")

    def toggle_pin(self) -> None:
        clip = self._selected()
        if clip:
            self.store.set_pinned(clip.id, not clip.pinned)
            self.refresh()

    def delete_selected(self) -> None:
        clip = self._selected()
        if clip:
            self.store.delete(clip.id)
            self.refresh()

    def _clear(self) -> None:
        if messagebox.askyesno("Temizle", "Sabitlenmemiş tüm pano kayıtları silinsin mi?\n(Sabitlenenler kalır.)"):
            n = self.store.clear_unpinned()
            self.refresh()
            self.status.configure(text=f"{n} kayıt silindi")

    def _toggle_recording(self) -> None:
        self.monitor.set_paused(not self.rec_var.get())
