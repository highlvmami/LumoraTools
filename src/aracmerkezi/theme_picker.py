"""Ayarlar'daki tema seçici: her tema küçük bir arayüz örneğiyle gösterilir, tıklayınca uygulanır."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from . import themes, ui

W, H = 150, 74


def _scene(canvas: tk.Canvas, c: dict[str, str], x0: int = 0, x1: int = W) -> None:
    """Temanın küçük bir arayüz resmini [x0, x1] aralığına çizer (Sistem temasında yarı yarıya karıştırmak için)."""
    def rect(a, b, cc, d, color):
        left, right = max(a, x0), min(cc, x1)
        if left < right:
            canvas.create_rectangle(left, b, right, d, fill=color, outline="")

    rect(0, 0, W, H, c["BG"])
    rect(0, 0, 30, H, c["SIDEBAR"])
    rect(7, 10, 23, 14, c["ACCENT"])
    rect(7, 20, 23, 23, c["MUTED"])
    rect(7, 28, 23, 31, c["MUTED"])
    rect(38, 10, 140, 42, c["CARD"])
    rect(46, 17, 86, 25, c["ACCENT"])
    rect(46, 31, 124, 34, c["MUTED"])
    rect(38, 50, 140, 66, c["CARD"])
    rect(46, 56, 74, 60, c["TEXT"])
    rect(110, 55, 132, 61, c["OK"])


class ThemePicker(ctk.CTkFrame):
    """choices: temalar (Sistem dahil). `on_select(ad)` tıklanınca çağrılır."""

    def __init__(self, master, current: str, on_select: Callable[[str], None], columns: int = 4) -> None:
        super().__init__(master, fg_color="transparent")
        self.on_select = on_select
        for i in range(columns):
            self.grid_columnconfigure(i, weight=1, uniform="t")
        for i, name in enumerate(themes.choices()):
            self._swatch(name, selected=name == current).grid(row=i // columns, column=i % columns,
                                                              padx=5, pady=5, sticky="nsew")

    def _swatch(self, name: str, selected: bool) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, fg_color=ui.CARD_ALT, corner_radius=12, cursor="hand2",
                             border_width=3 if selected else 1,
                             border_color=ui.ACCENT if selected else ui.BORDER)
        canvas = tk.Canvas(frame, width=W, height=H, highlightthickness=0, bd=0, bg=ui.CARD_ALT, cursor="hand2")
        canvas.pack(padx=8, pady=(8, 4))
        if name == themes.SYSTEM:
            _scene(canvas, themes.THEMES["Gece"].colors, 0, W // 2)
            _scene(canvas, themes.THEMES["Gündüz"].colors, W // 2, W)
        else:
            _scene(canvas, themes.THEMES[name].colors)
        label = ctk.CTkLabel(frame, text=("✓ " if selected else "") + name, cursor="hand2",
                             font=ctk.CTkFont(size=12, weight="bold" if selected else "normal"))
        label.pack(pady=(0, 8))
        for w in (frame, canvas, label):
            w.bind("<Button-1>", lambda _e, n=name: self.on_select(n))
        return frame
