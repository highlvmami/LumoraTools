"""Tema değişimi: arayüz yeni renklerle yeniden kurulur; sayfa, ayarlar ve arka plan işleri korunur."""
import json
import time

import pytest

from aracmerkezi import themes, ui

# Sayfalar arka plan iş parçacıklarından Tk'ye `after` ile döner; testte ana döngü olmadığı için
# bu iş parçacıkları "main thread is not in main loop" uyarısı verir. Uygulamada ana döngü hep çalışır.
pytestmark = pytest.mark.filterwarnings("ignore:Exception in thread:pytest.PytestUnhandledThreadExceptionWarning")


def make_hub(tmp_path, settings=None):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    path = data / "settings.json"
    if settings is not None or not path.exists():       # ikinci açılışta kayıtlı ayarlar ezilmesin
        from aracmerkezi import __version__
        cfg = {"update": {"check_on_start": False}, "last_seen_version": __version__} | (settings or {})   # testte ağa çıkma
        path.write_text(json.dumps(cfg), encoding="utf-8")
    try:
        from aracmerkezi.app import Hub
        hub = Hub(data_dir=data)
    except Exception as e:  # ekran / Tk yoksa
        pytest.skip(str(e))
    errors = []

    def record(exc, val, tb):          # özet için hata, tanı için tam iz
        import traceback
        errors.append(val)
        errors_tb.append("".join(traceback.format_exception(exc, val, tb)))

    errors_tb = []
    hub.report_callback_exception = record
    hub.errors = errors
    hub.tracebacks = errors_tb
    hub.geometry("1100x800+10+10")
    hub.update()
    return hub


@pytest.fixture
def hub(tmp_path):
    h = make_hub(tmp_path)
    yield h
    try:
        h.destroy()
    except Exception:
        pass
    ui.apply_theme(themes.DEFAULT)      # sonraki testler varsayılan renklerle başlasın


def test_every_theme_applies_and_rebuilds_without_errors(hub):
    for name in themes.THEMES:
        hub.set_theme(name)
        hub.update()
        assert ui.current.name == name and ui.ACCENT == themes.THEMES[name].colors["ACCENT"]
        assert hub.cget("fg_color") == themes.THEMES[name].colors["BG"]
        for page in ("home", "settings", "guides", "contact", "ekran", "arama"):
            hub.show(page)
            hub.update()
    assert not hub.errors, hub.tracebacks


def test_current_page_is_kept_after_theme_change(hub):
    hub.show("boyut")
    hub.update()
    hub.set_theme("Okyanus")
    hub.update()
    assert hub.current == "boyut" and hub.pages["boyut"].winfo_exists()
    assert hub.nav["boyut"].cget("fg_color") == themes.THEMES["Okyanus"].colors["ACCENT"]   # menüde işaretli
    assert not hub.errors, hub.tracebacks


def test_theme_choice_is_saved_and_restored(tmp_path):
    h = make_hub(tmp_path)
    h.set_theme("Lavanta")
    h._close()
    h2 = make_hub(tmp_path)
    try:
        assert ui.current.name == "Lavanta" and h2.settings["theme"] == "Lavanta"
    finally:
        h2.destroy()
        ui.apply_theme(themes.DEFAULT)


@pytest.mark.parametrize("legacy,expected", [("dark", "Gece"), ("light", "Gündüz")])
def test_legacy_theme_values_still_work(tmp_path, legacy, expected):
    h = make_hub(tmp_path, {"theme": legacy})
    try:
        assert ui.current.name == expected
    finally:
        h.destroy()
        ui.apply_theme(themes.DEFAULT)


def test_unknown_theme_name_is_ignored(hub):
    before = ui.current.name
    hub.set_theme("olmayan-tema")
    assert ui.current.name == before and hub.settings.get("theme") != "olmayan-tema"


def test_folder_watcher_keeps_running_across_theme_change(hub, tmp_path):
    from duzenle.watcher import Watcher
    folder = tmp_path / "izlenen"
    folder.mkdir()
    hub.show("duzenleyici")
    hub.update()
    page = hub.pages["duzenleyici"]
    page.watcher = Watcher(folder, on_message=page.messages.put, interval=0.1, settle=0.2)
    page.watcher.start()
    try:
        hub.set_theme("Nord")
        hub.update()
        new_page = hub.pages["duzenleyici"]
        assert new_page is not page and new_page.watcher is not None and new_page.watcher.running
        assert "durdur" in new_page.watch_btn.cget("text")             # düğme 'çalışıyor' durumunu gösterir
        (folder / "a.jpg").write_text("x")                              # izleme gerçekten sürüyor mu?
        deadline = time.time() + 5
        while time.time() < deadline and not (folder / "Resimler" / "a.jpg").exists():
            hub.update()
            time.sleep(0.05)
        assert (folder / "Resimler" / "a.jpg").exists()
    finally:
        if new_page.watcher:
            new_page.watcher.stop()
    assert not hub.errors, hub.tracebacks


# ---------- Yenilikler penceresi ----------
def _whats_new_windows(hub):
    import customtkinter as ctk
    return [w for w in hub.winfo_children() if isinstance(w, ctk.CTkToplevel)]


def test_whats_new_shows_after_an_upgrade_and_only_once(tmp_path):
    from aracmerkezi import __version__
    h = make_hub(tmp_path, {"last_seen_version": "0.6.0"})
    try:
        h._maybe_show_whats_new()
        h.update()
        assert len(_whats_new_windows(h)) == 1                            # yükseltme: pencere açılır
        assert h.settings["last_seen_version"] == __version__             # görüldü olarak kaydedildi
        for w in _whats_new_windows(h):
            w.destroy()
        h._maybe_show_whats_new()
        h.update()
        assert _whats_new_windows(h) == []                                 # aynı sürümde tekrar açılmaz
        assert not h.errors, h.errors
    finally:
        h.destroy()
        ui.apply_theme(themes.DEFAULT)


def test_whats_new_is_silent_on_a_fresh_install(tmp_path):
    from aracmerkezi.app import Hub
    data = tmp_path / "taze"                                               # ayar dosyası hiç yok: ilk kurulum
    try:
        h = Hub(data_dir=data)
    except Exception as e:
        pytest.skip(str(e))
    try:
        h.update_cfg["check_on_start"] = False
        h._maybe_show_whats_new()
        h.update()
        assert _whats_new_windows(h) == []
    finally:
        h.destroy()
        ui.apply_theme(themes.DEFAULT)


def test_whats_new_can_be_opened_from_settings(hub):
    hub.show_whats_new()
    hub.update()
    assert len(_whats_new_windows(hub)) == 1 and not hub.errors
