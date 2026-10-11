"""Ortak arayüz parçaları ve tema renkleri.

Renkler `themes.py`'deki seçili temadan gelir ve burada modül değişkenleri olarak durur (ACCENT, CARD…).
Başka modüller bunları `ui.ACCENT` biçiminde, kullanım anında okumalıdır (`from .ui import ACCENT` DEĞİL);
böylece tema değişince yeniden kurulan arayüz yeni renkleri alır.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from . import themes

# Aşağıdaki adlar apply_theme() ile gerçek renklere atanır (burada yalnızca tanımlıdırlar).
BG = SIDEBAR = CARD = CARD_ALT = INPUT_BG = TEXT = MUTED = ""
ACCENT = ACCENT_HOVER = ACCENT_TEXT = ACCENT_SOFT = ACCENT_SOFT_TEXT = ""
SEG_BG = SEG_ON = SEG_ON_HOVER = ""
OK = OK_HOVER = OK_TEXT = DANGER = DANGER_HOVER = DANGER_TEXT = DANGER_SOFT = WARN = ""
GHOST_HOVER = NAV_HOVER = BORDER = TOGGLE_OFF = TOGGLE_KNOB = SCROLL = SCROLL_HOVER = ""
TREE_HEAD = TREE_SELECT = TREE_SELECT_TEXT = TREE_DIM = TREE_GROUP = ""
SPINNER_PANEL = SPINNER_TRACK = SPINNER_ARC = HIT_BG = HIT_FG = FILE_BAR = ROW_DRAG = ""

current: themes.Theme = themes.THEMES[themes.DEFAULT]


def system_is_dark() -> bool:
    try:
        import darkdetect
        return bool(darkdetect.isDark())
    except Exception:
        return True


def _set_widget_defaults(c: dict[str, str]) -> None:
    """customtkinter'ın varsayılan bileşen renklerini temaya çeker (bundan sonra kurulan bileşenler alır)."""
    t = ctk.ThemeManager.theme
    updates = {
        "CTk": {"fg_color": c["BG"]},
        "CTkToplevel": {"fg_color": c["BG"]},
        "CTkFrame": {"fg_color": c["CARD"], "top_fg_color": c["CARD_ALT"], "border_color": c["BORDER"]},
        "CTkButton": {"fg_color": c["ACCENT"], "hover_color": c["ACCENT_HOVER"], "border_color": c["BORDER"],
                      "text_color": c["ACCENT_TEXT"], "text_color_disabled": c["MUTED"]},
        "CTkLabel": {"text_color": c["TEXT"], "border_color": c["BORDER"]},
        "CTkEntry": {"fg_color": c["INPUT_BG"], "border_color": c["BORDER"], "text_color": c["TEXT"],
                     "placeholder_text_color": c["MUTED"]},
        "CTkTextbox": {"fg_color": c["INPUT_BG"], "border_color": c["BORDER"], "text_color": c["TEXT"],
                       "scrollbar_button_color": c["SCROLL"], "scrollbar_button_hover_color": c["SCROLL_HOVER"]},
        "CTkSwitch": {"fg_color": c["TOGGLE_OFF"], "progress_color": c["ACCENT"], "button_color": c["TOGGLE_KNOB"],
                      "button_hover_color": c["TEXT"], "text_color": c["TEXT"], "text_color_disabled": c["MUTED"]},
        "CTkCheckBox": {"fg_color": c["ACCENT"], "border_color": c["BORDER"], "hover_color": c["ACCENT_HOVER"],
                        "checkmark_color": c["ACCENT_TEXT"], "text_color": c["TEXT"],
                        "text_color_disabled": c["MUTED"]},
        "CTkSegmentedButton": {"fg_color": c["SEG_BG"], "selected_color": c["SEG_ON"],
                               "selected_hover_color": c["SEG_ON_HOVER"], "unselected_color": c["SEG_BG"],
                               "unselected_hover_color": c["GHOST_HOVER"], "text_color": c["TEXT"],
                               "text_color_disabled": c["MUTED"]},
        "CTkProgressBar": {"fg_color": c["TOGGLE_OFF"], "progress_color": c["ACCENT"]},
        "CTkScrollbar": {"button_color": c["SCROLL"], "button_hover_color": c["SCROLL_HOVER"]},
        "CTkScrollableFrame": {"label_fg_color": c["CARD_ALT"]},
    }
    for widget, colors in updates.items():
        if widget in t:
            t[widget].update(colors)


def apply_theme(setting: str | None) -> themes.Theme:
    """Seçili temayı (ya da eski 'dark/light/system' değerini) uygular. Ardından arayüz yeniden kurulmalıdır."""
    global current
    theme = themes.resolve(setting, system_is_dark())
    current = theme
    globals().update(theme.colors)
    _set_widget_defaults(theme.colors)
    ctk.set_appearance_mode(theme.mode)
    return theme


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
        super().__init__(master, fg_color=SPINNER_PANEL, corner_radius=16)
        self._canvas = tk.Canvas(self, width=self.SIZE, height=self.SIZE, highlightthickness=0, bd=0,
                                 bg=SPINNER_PANEL)
        self._canvas.pack(padx=40, pady=(24, 8))
        pad = 6
        box = (pad, pad, self.SIZE - pad, self.SIZE - pad)
        self._track = self._canvas.create_oval(*box, width=5, outline=SPINNER_TRACK)
        self._arc = self._canvas.create_arc(*box, start=90, extent=100, style="arc", width=5, outline=SPINNER_ARC)
        self._label = ctk.CTkLabel(self, text=text, text_color=MUTED)
        self._label.pack(padx=40, pady=(0, 22))
        self._angle = 90
        self._job: str | None = None

    def start(self, text: str | None = None) -> None:
        if text:
            self._label.configure(text=text)
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


class ImageLabel(ctk.CTkLabel):
    """Görüntü gösteren etiket; temizlenince ya da değişince çökmez.

    CTkLabel'e `image=None` verilirse eski görüntü bellekten atılınca etiket yok olmuş görüntüye bakmaya devam eder
    (`image "pyimageN" does not exist`). Bu yüzden her zaman canlı bir görüntüye (gerekirse görünmez bir yer
    tutucuya) geçilir ve eski görüntü ancak ondan sonra bırakılır.
    """

    def __init__(self, master, box: tuple[int, int] = (360, 200), **kw) -> None:
        super().__init__(master, text="", **kw)
        self.box = box
        self._img: ctk.CTkImage | None = None
        self._blank: ctk.CTkImage | None = None

    def _blank_image(self) -> ctk.CTkImage:
        if self._blank is None:
            from PIL import Image
            self._blank = ctk.CTkImage(light_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1))
        return self._blank

    def show(self, pil_image) -> None:
        img = pil_image.copy()
        img.thumbnail(self.box)
        shown = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self.configure(image=shown, text="")
        self._img = shown

    def clear(self, text: str = "") -> None:
        blank = self._blank_image()
        self.configure(image=blank, text=text)
        self._img = blank

    @property
    def has_image(self) -> bool:
        return self._img is not None and self._img is not self._blank


class Sparkline(tk.Canvas):
    """Küçük canlı çizgi grafik (0..maximum aralığında değerler). Boyut değişince yeniden çizilir."""

    def __init__(self, master, height: int = 56, maximum: float = 100.0, **kw) -> None:
        super().__init__(master, height=height, highlightthickness=0, bd=0, bg=CARD, **kw)
        self.maximum = maximum
        self._values: list[float] = []
        self.bind("<Configure>", lambda _e: self._draw())

    def set_values(self, values) -> None:
        self._values = [float(v) for v in values]
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = max(self.winfo_width(), 2), max(self.winfo_height(), 2)
        for frac in (0.25, 0.5, 0.75):                      # soluk yatay kılavuz çizgileri
            self.create_line(0, h * frac, w, h * frac, fill=SCROLL, dash=(2, 4))
        v = self._values
        if len(v) < 2:
            return
        top = self.maximum or 1.0
        step = w / max(len(v) - 1, 1)
        pts = [(i * step, h - 2 - (min(max(x, 0.0), top) / top) * (h - 4)) for i, x in enumerate(v)]
        flat = [c for p in pts for c in p]
        self.create_polygon([0, h, *flat, w, h], fill=ACCENT_SOFT, outline="")
        self.create_line(*flat, fill=ACCENT, width=2, smooth=True)


def page_header(parent, title: str, subtitle: str) -> None:
    ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=26, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(parent, text=subtitle, text_color=MUTED).pack(anchor="w", pady=(0, 14))


def ghost_button(parent, text: str, command, width: int = 100, danger: bool = False) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, width=width, height=36, fg_color="transparent", border_width=1,
                         text_color=DANGER if danger else TEXT, border_color=DANGER if danger else BORDER,
                         hover_color=DANGER_SOFT if danger else GHOST_HOVER, command=command)


def style_tree() -> None:
    """Treeview'i seçili temaya uydurur."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Duz.Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, borderwidth=0,
                    rowheight=30, font=("Segoe UI", 10), bordercolor=CARD, lightcolor=CARD, darkcolor=CARD)
    style.configure("Duz.Treeview.Heading", background=TREE_HEAD, foreground=TEXT, relief="flat",
                    font=("Segoe UI", 10, "bold"), padding=(8, 6))
    style.map("Duz.Treeview", background=[("selected", TREE_SELECT)], foreground=[("selected", TREE_SELECT_TEXT)])
    style.map("Duz.Treeview.Heading", background=[("active", TREE_HEAD)])


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


apply_theme(themes.DEFAULT)  # içe aktarılır aktarılmaz renkler tanımlı olsun (testler, tek başına modüller)
