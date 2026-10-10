"""Küçük pencereler."""
from __future__ import annotations

import customtkinter as ctk

from . import __version__, ui


class WhatsNewDialog(ctk.CTkToplevel):
    """Güncelleme sonrası 'Yenilikler' penceresi. entries: [(sürüm, (not, not…))], en yeniden eskiye."""

    def __init__(self, master, entries: list[tuple[str, tuple[str, ...]]], title: str | None = None) -> None:
        super().__init__(master)
        self.title("Yenilikler")
        self.geometry("560x520")
        self.minsize(460, 380)
        self.configure(fg_color=ui.BG)
        self.transient(master)
        ctk.CTkLabel(self, text=title or f"LumoraTools v{__version__} 🎉", font=ctk.CTkFont(size=22, weight="bold")
                     ).pack(anchor="w", padx=24, pady=(22, 0))
        ctk.CTkLabel(self, text="Bu sürümde neler değişti:", text_color=ui.MUTED).pack(anchor="w", padx=24, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=14)
        for version, items in entries:
            card = ctk.CTkFrame(scroll, fg_color=ui.CARD, corner_radius=14)
            card.pack(fill="x", padx=6, pady=(0, 10))
            ctk.CTkLabel(card, text=f"v{version}", text_color=ui.ACCENT_SOFT_TEXT, fg_color=ui.ACCENT_SOFT,
                         corner_radius=8, font=ctk.CTkFont(size=12, weight="bold")).pack(
                anchor="w", padx=16, pady=(14, 6), ipadx=8)
            for item in items:
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=16, pady=2)
                ctk.CTkLabel(row, text="•", text_color=ui.ACCENT_FG, width=14).pack(side="left", anchor="n")
                ctk.CTkLabel(row, text=item, anchor="w", justify="left", wraplength=450).pack(
                    side="left", fill="x", expand=True)
            ctk.CTkFrame(card, height=10, fg_color="transparent").pack()
        ctk.CTkButton(self, text="Harika!", height=38, width=140, command=self.destroy).pack(pady=14)
        self.after(150, self._to_front)

    def _to_front(self) -> None:
        if self.winfo_exists():
            self.lift()
            self.focus_force()
