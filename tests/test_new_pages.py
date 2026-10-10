"""Sistem Temizleyici, Başlangıç Programları ve Pano görüntü/dosya sayfaları (gerçek Tk penceresiyle).

Güvenlik: temizleyici testi gerçek Temp'e dokunmaz (kategoriler sahte klasörlerle değiştirilir) ve
Geri Dönüşüm Kutusu'nu boşaltan çağrı yasaklanır.
"""
import json
import os
import time

import pytest
from PIL import Image

from aracmerkezi import themes, ui

pytestmark = pytest.mark.filterwarnings("ignore:Exception in thread:pytest.PytestUnhandledThreadExceptionWarning")

OLD = time.time() - 5 * 86400


def make_hub(tmp_path):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    from aracmerkezi import __version__
    (data / "settings.json").write_text(json.dumps({"update": {"check_on_start": False},
                                                    "last_seen_version": __version__}), encoding="utf-8")
    try:
        from aracmerkezi.app import Hub
        hub = Hub(data_dir=data)
    except Exception as e:
        pytest.skip(str(e))
    hub.errors = []
    hub.report_callback_exception = lambda exc, val, tb: hub.errors.append(val)
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
    ui.apply_theme(themes.DEFAULT)


def wait_for(hub, cond, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        hub.update()
        if cond():
            return True
        time.sleep(0.03)
    return False


# ---------- Sistem Temizleyici ----------
@pytest.fixture
def fake_cleaner(tmp_path, monkeypatch):
    from aracmerkezi.tools.cleaner import scan as sc
    temp = tmp_path / "SahteTemp"
    for rel, size in (("eski1.tmp", 1000), ("alt/eski2.tmp", 3000)):
        f = temp / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * size)
        os.utime(f, (OLD, OLD))
    young = temp / "yeni.tmp"
    young.write_bytes(b"y" * 500)
    cats = [sc.Category("temp", "Sahte geçici", "deneme", sc.DELETE, (temp,), min_age_days=1),
            sc.Category("bin", "Sahte kutu", "deneme", sc.BIN, default_on=False)]
    monkeypatch.setattr(sc, "default_categories", lambda *a, **k: cats)
    monkeypatch.setattr(sc, "query_recycle_bin", lambda: (7_000, 3))

    def forbidden():
        raise AssertionError("Geri Dönüşüm Kutusu seçilmeden boşaltılmaya çalışıldı!")

    monkeypatch.setattr(sc, "empty_recycle_bin", forbidden)
    return temp, young


def test_cleaner_scans_previews_and_cleans_only_selected(hub, fake_cleaner, monkeypatch):
    temp, young = fake_cleaner
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: True)
    hub.show("temizle")
    page = hub.pages["temizle"]
    assert wait_for(hub, lambda: not page.busy and "temp" in page.items)
    assert page.items["temp"].count == 2 and page.items["temp"].total == 4000 and page.items["temp"].too_young == 1
    assert page.rows["temp"]["size"].cget("text") == "3.9 KB"
    assert page.vars["temp"].get() and not page.vars["bin"].get()          # kutu kendiliğinden seçili değil
    assert page.clean_btn.cget("state") == "normal"
    page.show_detail("temp")
    assert len(page.tree.get_children()) == 2                              # önizleme: dosyalar listelendi
    page.clean()
    assert wait_for(hub, lambda: "boşaltıldı" in page.status.cget("text") and not page.busy)
    assert not (temp / "eski1.tmp").exists() and not (temp / "alt").exists()   # eskiler ve boşalan klasör gitti
    assert young.exists() and temp.exists()                                # genç dosya ve kök kaldı
    assert "3.9 KB" in page.status.cget("text") and not hub.errors


def test_cleaner_does_nothing_when_nothing_is_selected(hub, fake_cleaner, monkeypatch):
    temp, young = fake_cleaner
    asked = []
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: asked.append(1) or True)
    hub.show("temizle")
    page = hub.pages["temizle"]
    assert wait_for(hub, lambda: not page.busy and "temp" in page.items)
    page.vars["temp"].set(False)
    page._selection_changed()
    assert page.clean_btn.cget("state") == "disabled"
    page.clean()
    assert asked == [] and (temp / "eski1.tmp").exists()


def test_cleaner_confirmation_distinguishes_permanent_from_recycle(hub, fake_cleaner, monkeypatch):
    seen = []
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda title, msg, **k: seen.append(msg) or False)
    hub.show("temizle")
    page = hub.pages["temizle"]
    assert wait_for(hub, lambda: not page.busy and "temp" in page.items)
    page.clean()                                                           # onay reddedildi → hiçbir şey silinmez
    assert "KALICI silinecek" in seen[0] and "Sahte geçici" in seen[0] and "BOŞALTILACAK" not in seen[0]
    assert (fake_cleaner[0] / "eski1.tmp").exists()


# ---------- Başlangıç Programları ----------
def test_startup_page_lists_and_toggles_without_touching_the_real_registry(hub, monkeypatch):
    from aracmerkezi.tools.startup import entries as st
    from aracmerkezi.tools.startup import page as sp

    class Fake:
        def __init__(self):
            self.run = {("HKCU", st.RUN): {"Uygulama A": r'"C:\A\a.exe" -x', "Uygulama B": r"C:\B\b.exe"}}
            self.marks = {}

        def run_values(self, hive, subkey):
            return dict(self.run.get((hive, subkey), {}))

        def approved(self, hive, key):
            return dict(self.marks.get((hive, key), {})) if hive == "HKCU" else {}

        def set_approved(self, key, name, data):
            self.marks.setdefault(("HKCU", key), {})[name] = data

        def startup_files(self, common):
            return []

    fake = Fake()
    monkeypatch.setattr(sp.st, "WinBackend", lambda: fake)
    hub.show("baslangic")
    page = hub.pages["baslangic"]
    assert "2 program açılışta başlıyor" in page.summary.cget("text")
    entry = next(e for e in page.entries if e.name == "Uygulama A")
    import customtkinter as ctk
    var = ctk.BooleanVar(value=False)
    page._toggle(entry, var)                                               # kapat
    assert not st.parse_state(fake.marks[("HKCU", "Run")]["Uygulama A"])
    assert "1 program açılışta başlıyor" in page.summary.cget("text") and "Kapatıldı" in page.status.cget("text")
    assert fake.run[("HKCU", st.RUN)]["Uygulama A"]                        # girdi silinmedi
    page._toggle(entry, ctk.BooleanVar(value=True))                        # geri aç
    assert "2 program açılışta başlıyor" in page.summary.cget("text") and not hub.errors


def test_startup_toggle_failure_reverts_the_switch(hub, monkeypatch):
    import customtkinter as ctk
    from aracmerkezi.tools.startup import entries as st
    from aracmerkezi.tools.startup import page as sp

    class Broken:
        def run_values(self, hive, subkey):
            return {"X": "x.exe"} if (hive, subkey) == ("HKCU", st.RUN) else {}

        def approved(self, hive, key):
            return {}

        def set_approved(self, key, name, data):
            raise PermissionError("yazılamıyor")

        def startup_files(self, common):
            return []

    monkeypatch.setattr(sp.st, "WinBackend", lambda: Broken())
    hub.show("baslangic")
    page = hub.pages["baslangic"]
    var = ctk.BooleanVar(value=False)
    page._toggle(page.entries[0], var)
    assert var.get() is True and "Değiştirilemedi" in page.status.cget("text")


# ---------- Pano: görüntü ve dosya ----------
def test_clipboard_page_shows_image_and_file_clips(hub, tmp_path, monkeypatch):
    from aracmerkezi.tools.clipboard import clipboard_io
    from aracmerkezi.tools.clipboard.page import get_service
    store, monitor = get_service(hub)
    monitor.stop()
    real = tmp_path / "gercek.txt"
    real.write_text("x")
    store.add("düz metin")
    store.add_image(Image.new("RGB", (120, 60), (10, 200, 90)))
    store.add_files([str(real), str(tmp_path / "silinmis.pdf")])
    sets = []
    monkeypatch.setattr(clipboard_io, "set_image", lambda im: sets.append(("image", im.size)))
    monkeypatch.setattr(clipboard_io, "set_files", lambda paths: sets.append(("files", [os.path.basename(str(p)) for p in paths])))
    hub.show("pano")
    page = hub.pages["pano"]
    by_kind = {c.kind: iid for iid, c in page.clips.items()}
    assert set(by_kind) == {"text", "image", "files"}

    page.tree.selection_set(by_kind["image"])
    hub.update()
    assert page.image_view.winfo_manager() and page.image_view.has_image          # önizleme görünüyor
    assert "120×60" in page.detail.get("1.0", "end")
    page.copy_selected()
    assert sets[-1] == ("image", (120, 60)) and "Görüntü panoya kopyalandı" in page.status.cget("text")

    page.tree.selection_set(by_kind["files"])
    hub.update()
    assert not page.image_view.winfo_manager()                                     # dosyalarda görüntü alanı gizlenir
    detail = page.detail.get("1.0", "end")
    assert "gercek.txt" in detail and "artık yok" in detail                        # olmayan dosya işaretlenir
    page.copy_selected()
    assert sets[-1] == ("files", ["gercek.txt"]) and "1 dosya" in page.status.cget("text")

    page.tree.selection_set(by_kind["text"])
    hub.update()
    assert not page.image_view.winfo_manager() and "düz metin" in page.detail.get("1.0", "end")
    assert not hub.errors
