import pytest

from aracmerkezi import themes
from aracmerkezi.themes import THEMES, TOKENS, contrast, mix, readable_on, resolve

ALL = list(THEMES.values())


def test_there_are_many_varied_themes():
    assert len(THEMES) >= 10
    assert {t.mode for t in ALL} == {"dark", "light"}
    assert len({t.colors["ACCENT"] for t in ALL}) >= 10          # her temanın kendi vurgu rengi var
    assert len({t.colors["BG"] for t in ALL}) == len(ALL)        # zeminler birbirinden farklı


@pytest.mark.parametrize("theme", ALL, ids=lambda t: t.name)
def test_every_theme_defines_every_token_as_hex(theme):
    assert set(theme.colors) == set(TOKENS)
    for token, value in theme.colors.items():
        assert len(value) == 7 and value.startswith("#"), (theme.name, token, value)
        int(value[1:], 16)


@pytest.mark.parametrize("theme", ALL, ids=lambda t: t.name)
def test_text_is_readable_on_every_surface(theme):
    c = theme.colors
    for surface in ("BG", "CARD", "CARD_ALT", "SIDEBAR", "INPUT_BG", "SEG_BG", "GHOST_HOVER"):
        assert contrast(c["TEXT"], c[surface]) >= 4.5, (theme.name, surface)
    assert contrast(c["MUTED"], c["CARD"]) >= 4.5, theme.name          # soluk yazı da okunur kalır
    assert contrast(c["MUTED"], c["BG"]) >= 3.0, theme.name


@pytest.mark.parametrize("theme", ALL, ids=lambda t: t.name)
def test_text_on_colored_fills_is_readable(theme):
    c = theme.colors
    pairs = [("ACCENT_TEXT", "ACCENT"), ("ACCENT_TEXT", "ACCENT_HOVER"), ("OK_TEXT", "OK"),
             ("DANGER_TEXT", "DANGER"), ("TREE_SELECT_TEXT", "TREE_SELECT"), ("TEXT", "SEG_ON"),
             ("TEXT", "SEG_ON_HOVER"), ("ACCENT_SOFT_TEXT", "ACCENT_SOFT"), ("TEXT", "TREE_GROUP"),
             ("TEXT", "ROW_DRAG"), ("TEXT", "NAV_HOVER"), ("HIT_FG", "HIT_BG"), ("TEXT", "ACCENT_SOFT"),
             ("ACCENT_FG", "BG"), ("ACCENT_FG", "CARD")]
    for fg, bg in pairs:
        assert contrast(c[fg], c[bg]) >= 4.5, (theme.name, fg, bg, round(contrast(c[fg], c[bg]), 2))


@pytest.mark.parametrize("theme", ALL, ids=lambda t: t.name)
def test_ui_elements_are_visible_against_their_background(theme):
    c = theme.colors
    assert contrast(c["ACCENT"], c["CARD"]) >= 2.0, theme.name          # vurgu kartın üstünde seçilir
    assert contrast(c["SPINNER_ARC"], c["SPINNER_PANEL"]) >= 3.0, theme.name
    assert contrast(c["TREE_DIM"], c["CARD"]) >= 3.0, theme.name        # 'yerinde kalacak' soluk satırlar okunur
    assert contrast(c["DANGER"], c["CARD"]) >= 3.0, theme.name          # kırmızı sil düğmesi/yazısı
    assert c["BG"] != c["CARD"] and c["CARD"] != c["SIDEBAR"]           # katmanlar ayırt edilir


def test_resolve_handles_legacy_values_unknown_and_system():
    assert resolve("dark").name == "Gece" and resolve("light").name == "Gündüz"
    assert resolve("Okyanus").name == "Okyanus"
    assert resolve("silinmis-tema").name == themes.DEFAULT and resolve(None).name == themes.DEFAULT
    assert resolve("system", system_is_dark=True).name == "Gece"
    assert resolve(themes.SYSTEM, system_is_dark=False).name == "Gündüz"
    assert themes.choices()[0] == themes.SYSTEM and len(themes.choices()) == len(THEMES) + 1


def test_color_math():
    assert mix("#000000", "#ffffff", 0.5) == "#808080"
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert readable_on("#ffffff") == "#111827" and readable_on("#000000") == "#ffffff"
