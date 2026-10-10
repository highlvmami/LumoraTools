"""Ekran Görüntüleri sayfasının önizleme davranışı (gerçek Tk penceresiyle)."""
import os
from datetime import datetime

import pytest
from PIL import Image

from aracmerkezi.tools.screenshots import library as lib


@pytest.fixture
def page(tmp_path, monkeypatch):
    from aracmerkezi.tools.screenshots.page import ScreenshotsPage
    # Arka plan taraması ana döngü olmadan Tk'ye erişemez; testte listeyi elle dolduruyoruz.
    monkeypatch.setattr(ScreenshotsPage, "reload", lambda self: None)
    try:
        from aracmerkezi.app import Hub
        hub = Hub(data_dir=tmp_path / "data", tools=[])
    except Exception as e:  # ekran / Tk yoksa
        pytest.skip(str(e))
    shots = tmp_path / "shots"
    shots.mkdir()
    for i in range(3):
        p = shots / f"g{i}.png"
        Image.new("RGB", (320, 180), (40 + i * 60, 90, 150)).save(p)
        ts = datetime(2026, 10, 11, 8 + i).timestamp()
        os.utime(p, (ts, ts))
    from aracmerkezi.tools.screenshots import TOOL
    sp = TOOL.build(hub.content, hub)
    sp.folder_var.set(str(shots))
    sp.shots = lib.list_shots(shots)   # arka plan taramasını beklemeden: ana iş parçacığında doldur
    sp.render()
    errors = []
    hub.report_callback_exception = lambda *a: errors.append(a[1])
    sp.errors = errors
    yield sp
    hub.destroy()


def test_preview_survives_clearing_and_reselecting(page):
    """Görüntü gösterilirken seçim kalkıp yeniden seçilince önizleme çökmemeli (silme sonrası yaşanan hata)."""
    sp = page
    sp.tree.selection_set("0")
    sp.update()
    assert sp.preview.cget("text") == "" and sp._img is not sp._blank_image()          # görüntü gösteriliyor
    sp.clear_selection()                                                   # silme/yenileme sonrası durum
    sp.update()
    sp.tree.selection_set("1")
    sp.update()
    assert not sp.errors, sp.errors
    assert sp.preview.cget("text") == "" and sp._img is not sp._blank_image()          # yeniden görüntü gösterildi


def test_preview_survives_multi_select_then_single(page):
    sp = page
    sp.tree.selection_set("0")
    sp.update()
    sp.select_all()
    sp.update()
    assert "3 görüntü seçili" in sp.preview.cget("text")
    sp.tree.selection_set("2")
    sp.update()
    assert not sp.errors, sp.errors
    assert sp.preview.cget("text") == "" and sp._img is not sp._blank_image()


def test_preview_of_unreadable_image_does_not_break_next_one(page):
    sp = page
    bad = sp.visible["0"].path
    bad.write_bytes(b"bozuk")                                              # görüntü değil
    sp.tree.selection_set("0")
    sp.update()
    assert sp.preview.cget("text") == "Önizlenemiyor"
    sp.tree.selection_set("1")
    sp.update()
    assert not sp.errors, sp.errors
    assert sp.preview.cget("text") == "" and sp._img is not sp._blank_image()
