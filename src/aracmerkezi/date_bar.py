"""Tarih filtresi çubuğu: hazır aralıklar (Bugün, Dün…) ve elle yazılan aralık."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .datefilter import CUSTOM, PRESETS, custom_range, preset_range
from .ui import ACCENT, ACCENT_HOVER, MUTED


class DateFilterBar(ctk.CTkFrame):
    def __init__(self, master, on_change: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self.on_change = on_change
        ctk.CTkLabel(self, text="📅  Tarih", text_color=MUTED).pack(side="left", padx=(0, 10))
        self.seg = ctk.CTkSegmentedButton(self, values=PRESETS, command=self._preset_changed, height=32,
                                          selected_color=ACCENT, selected_hover_color=ACCENT_HOVER)
        self.seg.set("Tümü")
        self.seg.pack(side="left")
        self.hint = ctk.CTkLabel(self, text="", text_color=MUTED, anchor="w")
        self.hint.pack(side="left", padx=14)
        self.range_box = ctk.CTkFrame(self, fg_color="transparent")
        self.from_entry = ctk.CTkEntry(self.range_box, width=108, height=32, placeholder_text="GG.AA.YYYY")
        self.to_entry = ctk.CTkEntry(self.range_box, width=108, height=32, placeholder_text="GG.AA.YYYY")
        self.from_entry.pack(side="left")
        ctk.CTkLabel(self.range_box, text="–", text_color=MUTED).pack(side="left", padx=6)
        self.to_entry.pack(side="left")
        for e in (self.from_entry, self.to_entry):
            e.bind("<KeyRelease>", lambda _e: self.on_change())

    def _preset_changed(self, value: str) -> None:
        if value == CUSTOM:
            self.range_box.pack(side="left", padx=(12, 0), before=self.hint)
        else:
            self.range_box.pack_forget()
        self.on_change()

    def range(self) -> tuple[float | None, float | None]:
        """Seçili filtrenin (başlangıç, bitiş) zaman damgası; bitiş dahil değil. Geçersiz yazımda filtre uygulanmaz."""
        self.hint.configure(text="")
        name = self.seg.get()
        if name != CUSTOM:
            return preset_range(name)
        try:
            return custom_range(self.from_entry.get(), self.to_entry.get())
        except ValueError as e:
            self.hint.configure(text=f"⚠ {e}", text_color=("#b45309", "#fbbf24"))
            return None, None
