"""Uygulama temaları (Tk'den bağımsız, test edilebilir).

Her tema yalnızca birkaç ana renk tanımlar (zemin, kart, yazı, vurgu); geri kalan tüm renkler
(kenar çubuğu, kenarlık, vurgu üstü yazı, seçili satır, soluk yazı…) bunlardan hesaplanır. Böylece
yeni tema eklemek tek satırdır ve okunabilirlik (kontrast) hesapla güvence altındadır.
"""
from __future__ import annotations

from dataclasses import dataclass

SYSTEM = "Sistem (otomatik)"
DEFAULT = "Gece"
LEGACY = {"dark": "Gece", "light": "Gündüz", "system": SYSTEM}   # eski ayar değerleri


# ---------- renk matematiği ----------
def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(c: tuple[float, float, float]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(v))) for v in c))


def mix(a: str, b: str, t: float) -> str:
    """a ile b arasında doğrusal karışım (t=0 → a, t=1 → b)."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def luminance(h: str) -> float:
    def lin(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG kontrast oranı (1–21)."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(bg: str, light: str = "#ffffff", dark: str = "#111827") -> str:
    """`bg` üzerinde daha okunaklı olan yazı rengi (beyaz ya da koyu)."""
    return light if contrast(light, bg) >= contrast(dark, bg) else dark


def _ensure(color: str, bg: str, ratio: float, toward: str) -> str:
    """`color`, `bg` üzerinde en az `ratio` kontrasta ulaşana dek `toward` rengine yaklaştırılır."""
    for step in range(0, 21):
        candidate = mix(color, toward, step / 20)
        if contrast(candidate, bg) >= ratio:
            return candidate
    return toward


def _tint(base: str, tint: str, t: float, text: str, ratio: float = 4.5) -> str:
    """`base`'i `tint`'e `t` kadar karıştırır; `text` üstünde okunaklı kalana dek `t`yi azaltır."""
    while t > 0 and contrast(text, mix(base, tint, t)) < ratio:
        t -= 0.01
    return mix(base, tint, max(t, 0))


def _fill(accent: str) -> tuple[str, str]:
    """Vurgu dolgusu ve üstündeki yazı rengi. Marka rengi okunaklılık eşiğini geçmiyorsa en az ölçüde ayarlanır."""
    text = readable_on(accent)
    if contrast(text, accent) < 4.5:
        accent = _ensure_fill(accent, text)
    return accent, text


def _ensure_fill(accent: str, text: str) -> str:
    away = "#000000" if text == "#ffffff" else "#ffffff"          # beyaz yazı: rengi koyulaştır; koyu yazı: açıklaştır
    for step in range(0, 41):
        candidate = mix(accent, away, step / 40)
        if contrast(text, candidate) >= 4.5:
            return candidate
    return away


# ---------- tema ----------
@dataclass(frozen=True)
class Theme:
    name: str
    mode: str                 # 'dark' | 'light' (pencere başlığı ve CTk iç renkleri için)
    colors: dict[str, str]


def build(name: str, mode: str, bg: str, card: str, text: str, accent: str) -> Theme:
    dark = mode == "dark"
    black, white = "#000000", "#ffffff"
    sidebar = mix(bg, black, 0.35 if dark else 0.05)
    accent, accent_text = _fill(accent)
    accent_hover = mix(accent, black, 0.2) if accent_text == white else mix(accent, white, 0.18)
    ok = "#22c55e" if dark else "#15803d"
    danger = "#f87171" if dark else "#dc2626"
    seg_on = _tint(card, accent, 0.50 if dark else 0.28, text)
    seg_on_hover = _tint(seg_on, text, 0.12, text)
    accent_soft = mix(card, accent, 0.22 if dark else 0.14)
    c = {
        "BG": bg, "SIDEBAR": sidebar, "CARD": card, "CARD_ALT": mix(card, text, 0.06),
        "INPUT_BG": mix(bg, black, 0.12) if dark else mix(bg, white, 0.5),
        "TEXT": text,
        "MUTED": _ensure(mix(text, card, 0.40), card, 4.5, text),
        "ACCENT": accent, "ACCENT_HOVER": accent_hover, "ACCENT_TEXT": accent_text,
        "ACCENT_SOFT": accent_soft,
        "ACCENT_FG": _ensure(_ensure(accent, bg, 4.5, white if dark else black), card, 4.5, white if dark else black),
        "ACCENT_SOFT_TEXT": _ensure(mix(accent, white if dark else black, 0.45), accent_soft, 4.5,
                                    white if dark else black),
        "SEG_BG": mix(card, text, 0.10), "SEG_ON": seg_on, "SEG_ON_HOVER": seg_on_hover,
        "OK": ok, "OK_HOVER": mix(ok, black, 0.18), "OK_TEXT": readable_on(ok),
        "DANGER": danger, "DANGER_HOVER": mix(danger, black, 0.2), "DANGER_TEXT": readable_on(danger),
        "DANGER_SOFT": mix(card, danger, 0.18),
        "WARN": "#fbbf24" if dark else "#b45309",
        "GHOST_HOVER": mix(card, text, 0.10), "NAV_HOVER": mix(sidebar, text, 0.10),
        "BORDER": mix(card, text, 0.30), "TOGGLE_OFF": mix(card, text, 0.25), "TOGGLE_KNOB": mix(text, card, 0.1),
        "SCROLL": mix(card, text, 0.30), "SCROLL_HOVER": mix(card, text, 0.50),
        "TREE_HEAD": mix(card, text, 0.10), "TREE_SELECT": accent, "TREE_SELECT_TEXT": accent_text,
        "TREE_DIM": _ensure(mix(text, card, 0.55), card, 3.0, text), "TREE_GROUP": mix(card, accent, 0.22 if dark else 0.16),
        "SPINNER_PANEL": mix(card, text, 0.08), "SPINNER_TRACK": mix(card, text, 0.22),
        "SPINNER_ARC": _ensure(accent, mix(card, text, 0.08), 3.0, white if dark else black),
        "HIT_BG": "#fde68a", "HIT_FG": "#111827",
        "FILE_BAR": mix(text, card, 0.5), "ROW_DRAG": mix(card, accent, 0.30),
    }
    return Theme(name, mode, c)


TOKENS = tuple(build("x", "dark", "#000000", "#111111", "#ffffff", "#6366f1").colors)

_SPECS = [
    # ad,            mod,     zemin,     kart,      yazı,      vurgu
    ("Gece",         "dark",  "#13151f", "#1e2130", "#e5e7eb", "#6366f1"),
    ("Gündüz",       "light", "#f3f4f8", "#ffffff", "#1f2937", "#4f46e5"),
    ("Okyanus",      "dark",  "#0b1b26", "#12293a", "#e2f1f8", "#06b6d4"),
    ("Orman",        "dark",  "#0f1b14", "#172a1f", "#e6f2ea", "#22c55e"),
    ("Gün Batımı",   "dark",  "#1f1318", "#2e1b24", "#fde8e3", "#fb7185"),
    ("Kahve",        "dark",  "#1c1511", "#2a1f19", "#f1e6dc", "#d6a26e"),
    ("Nord",         "dark",  "#2e3440", "#3b4252", "#eceff4", "#88c0d0"),
    ("Kömür",        "dark",  "#161616", "#232323", "#ececec", "#a3a3a3"),
    ("AMOLED",       "dark",  "#000000", "#0d0d0d", "#f5f5f5", "#00e5a0"),
    ("Lavanta",      "light", "#f4f0fb", "#ffffff", "#2e2342", "#8b5cf6"),
    ("Şeker",        "light", "#fdf2f8", "#ffffff", "#4a1d3a", "#db2777"),
    ("Kağıt",        "light", "#f6f1e7", "#fffdf8", "#3b3226", "#b45309"),
]
THEMES: dict[str, Theme] = {name: build(name, mode, bg, card, text, accent) for name, mode, bg, card, text, accent in _SPECS}


def choices() -> list[str]:
    """Seçici sırası: önce Sistem, sonra temalar."""
    return [SYSTEM, *THEMES]


def resolve(setting: str | None, system_is_dark: bool = True) -> Theme:
    """Kayıtlı ayardan (eski 'dark/light/system' değerleri dahil) temayı bulur; bilinmiyorsa varsayılan."""
    name = LEGACY.get(setting or "", setting or DEFAULT)
    if name == SYSTEM:
        name = "Gece" if system_is_dark else "Gündüz"
    return THEMES.get(name, THEMES[DEFAULT])
