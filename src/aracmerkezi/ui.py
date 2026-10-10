"""Ortak arayüz parçaları ve renk paleti."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

ACCENT = ("#4f46e5", "#6366f1")
ACCENT_HOVER = ("#4338ca", "#4f46e5")
DANGER = ("#dc2626", "#ef4444")
DANGER_HOVER = ("#b91c1c", "#dc2626")
CARD = ("#ffffff", "#1e2130")
BG = ("#f3f4f8", "#13151f")
SIDEBAR = ("#e8eaf2", "#0e1018")
MUTED = ("#6b7280", "#9aa0b4")
OK = ("#16a34a", "#22c55e")
OK_HOVER = ("#15803d", "#16a34a")
TEXT = ("#1f2937", "#e5e7eb")
GHOST_HOVER = ("#e5e7eb", "#2a2f45")


class StatCard(ctk.CTkFrame):
    def __init__(self, master, title: str, value: str = "—"):
        super().__init__(master, fg_color=CARD, corner_radius=14)
        ctk.CTkLabel(self, text=title, text_color=MUTED, font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=18, pady=(14, 0))
        self.value = ctk.CTkLabel(self, text=value, font=ctk.CTkFont(size=28, weight="bold"))
        self.value.pack(anchor="w", padx=18, pady=(0, 14))

    def set(self, value) -> None:
        self.value.configure(text=str(value))


class Spinner(ctk.CTkFrame):
    """Üst widget'ın ortasında dönen yükleme göstergesi (start/stop ile gösterilir/gizlenir)."""
    SIZE = 56

    def __init__(self, master, text: str = "Yükleniyor…") -> None:
        super().__init__(master, fg_color=("#eef0fb", "#2a2f45"), corner_radius=16)
        self._canvas = tk.Canvas(self, width=self.SIZE, height=self.SIZE, highlightthickness=0, bd=0)
        self._canvas.pack(padx=40, pady=(24, 8))
        pad = 6
        box = (pad, pad, self.SIZE - pad, self.SIZE - pad)
        self._track = self._canvas.create_oval(*box, width=5)
        self._arc = self._canvas.create_arc(*box, start=90, extent=100, style="arc", width=5)
        self._label = ctk.CTkLabel(self, text=text, text_color=MUTED)
        self._label.pack(padx=40, pady=(0, 22))
        self._angle = 90
        self._job: str | None = None

    def _paint(self) -> None:
        dark = ctk.get_appearance_mode() == "Dark"
        self._canvas.configure(bg="#2a2f45" if dark else "#eef0fb")
        self._canvas.itemconfigure(self._track, outline="#3d4466" if dark else "#d3d8f0")
        self._canvas.itemconfigure(self._arc, outline="#818cf8" if dark else "#4f46e5")

    def start(self, text: str | None = None) -> None:
        if text:
            self._label.configure(text=text)
        self._paint()
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        if self._job is None:
            self._tick()

    def stop(self) -> None:
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        self.place_forget()

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        self._angle = (self._angle - 14) % 360
        self._canvas.itemconfigure(self._arc, start=self._angle)
        self._job = self.after(30, self._tick)


def page_header(parent, title: str, subtitle: str) -> None:
    ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=26, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(parent, text=subtitle, text_color=MUTED).pack(anchor="w", pady=(0, 14))


def ghost_button(parent, text: str, command, width: int = 100, danger: bool = False) -> ctk.CTkButton:
    color = DANGER if danger else TEXT
    return ctk.CTkButton(parent, text=text, width=width, height=36, fg_color="transparent", border_width=1,
                         text_color=color, border_color=color if danger else ("#9ca3af", "#4b5563"),
                         hover_color=("#fee2e2", "#3a1d24") if danger else GHOST_HOVER, command=command)


def style_tree() -> None:
    """Treeview'i geçerli temaya (koyu/açık) uydurur."""
    dark = ctk.get_appearance_mode() == "Dark"
    bg, fg, head = ("#1e2130", "#e5e7eb", "#2a2f45") if dark else ("#ffffff", "#1f2937", "#eceef6")
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Duz.Treeview", background=bg, fieldbackground=bg, foreground=fg, borderwidth=0,
                    rowheight=30, font=("Segoe UI", 10), bordercolor=bg, lightcolor=bg, darkcolor=bg)
    style.configure("Duz.Treeview.Heading", background=head, foreground=fg, relief="flat",
                    font=("Segoe UI", 10, "bold"), padding=(8, 6))
    style.map("Duz.Treeview", background=[("selected", "#4f46e5")], foreground=[("selected", "#ffffff")])
    style.map("Duz.Treeview.Heading", background=[("active", head)])


def make_tree(parent, columns: dict[str, tuple[str, int]], height: int | None = None) -> ttk.Treeview:
    """Kaydırma çubuklu, temalı tablo. columns: {id: (başlık, genişlik)}. Frame içinde grid kullanır."""
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)
    kw = {"height": height} if height else {}
    tree = ttk.Treeview(parent, columns=list(columns), show="headings", style="Duz.Treeview", **kw)
    for cid, (title, width) in columns.items():
        tree.heading(cid, text=title, anchor="w")
        tree.column(cid, width=width, anchor="w")
    sb = ctk.CTkScrollbar(parent, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
    sb.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=10)
    return tree
