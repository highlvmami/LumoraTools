import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from aracmerkezi.tools.cleaner import scan as sc
from aracmerkezi.tools.cleaner.scan import BIN, DELETE, RECYCLE, Category

NOW = time.time()
OLD = NOW - 3 * 86400


def make(path: Path, size=10, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def cat(root, **kw):
    return Category("t", "Deneme", "açıklama", kw.pop("method", DELETE), (root,), **kw)


# ---------- tarama ----------
def test_scan_applies_age_limit_and_counts_young_files(tmp_path):
    make(tmp_path / "eski.tmp", 100, OLD)
    make(tmp_path / "alt" / "eski2.dat", 200, OLD)
    make(tmp_path / "yeni.tmp", 999, NOW)                      # 1 günden genç: dokunulmaz
    item = sc.scan_category(cat(tmp_path, min_age_days=1), NOW)
    assert item.count == 2 and item.total == 300 and item.too_young == 1
    assert [f.path.name for f in item.files] == ["eski2.dat", "eski.tmp"]    # en büyük önce


def test_scan_patterns_and_non_recursive(tmp_path):
    make(tmp_path / "a.crdownload", 5, OLD)
    make(tmp_path / "b.PART", 6, OLD)                           # büyük/küçük harf fark etmez
    make(tmp_path / "belge.pdf", 7, OLD)                        # desene uymaz
    make(tmp_path / "alt" / "c.crdownload", 8, OLD)             # özyinelemeli değil: görülmez
    item = sc.scan_category(cat(tmp_path, patterns=("*.crdownload", "*.part"), recursive=False), NOW)
    assert sorted(f.path.name for f in item.files) == ["a.crdownload", "b.PART"]


def test_scan_missing_root_is_empty_not_an_error(tmp_path):
    item = sc.scan_category(cat(tmp_path / "yok"), NOW)
    assert item.count == 0 and item.errors == 0


def test_scan_does_not_follow_junctions(tmp_path):
    if sys.platform != "win32":
        pytest.skip("yalnızca Windows")
    outside = tmp_path / "disarisi"
    make(outside / "onemli.doc", 50, OLD)
    root = tmp_path / "kok"
    make(root / "a.tmp", 10, OLD)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(root / "baglanti"), str(outside)], check=True, capture_output=True)
    item = sc.scan_category(cat(root), NOW)
    assert [f.path.name for f in item.files] == ["a.tmp"]       # junction'ın içine girilmedi


# ---------- temizlik ----------
def test_clean_deletes_only_old_files_and_prunes_empty_dirs_but_never_the_root(tmp_path):
    root = tmp_path / "temp"
    old = make(root / "a" / "b" / "eski.tmp", 100, OLD)
    young = make(root / "a" / "yeni.tmp", 100, NOW)
    make(root / "bos" / "eski2.tmp", 5, OLD)
    c = cat(root, min_age_days=1)
    item = sc.scan_category(c, NOW)
    res = sc.clean(item, NOW)
    assert res.deleted == 2 and res.freed == 105 and res.failed == 0
    assert not old.exists() and young.exists()                  # genç dosya kaldı
    assert not (root / "bos").exists() and not (root / "a" / "b").exists()      # boşalan klasörler gitti
    assert (root / "a").exists() and root.exists()              # içinde dosya olan klasör ve kök kaldı


def test_clean_removes_read_only_files(tmp_path):
    f = make(tmp_path / "salt.tmp", 10, OLD)
    os.chmod(f, 0o444)
    res = sc.clean(sc.scan_category(cat(tmp_path), NOW), NOW)
    assert res.deleted == 1 and not f.exists()


def test_clean_refuses_paths_outside_the_allowed_roots(tmp_path):
    root = tmp_path / "izinli"
    root.mkdir()
    outside = make(tmp_path / "dis" / "onemli.txt", 10, OLD)
    sneaky = make(root / "a.tmp", 10, OLD)
    item = sc.ScanItem(cat(root), [sc.FileInfo(outside, 10), sc.FileInfo(root / ".." / "dis" / "onemli.txt", 10),
                                   sc.FileInfo(sneaky, 10)], total=30, count=3)
    res = sc.clean(item, NOW)
    assert outside.exists()                                    # dışarıdaki dosyaya dokunulmadı
    assert res.skipped_unsafe == 2 and res.deleted == 1 and not sneaky.exists()


def test_clean_does_not_escape_through_a_junction(tmp_path):
    if sys.platform != "win32":
        pytest.skip("yalnızca Windows")
    outside = tmp_path / "disarisi"
    precious = make(outside / "onemli.doc", 50, OLD)
    root = tmp_path / "kok"
    make(root / "a.tmp", 10, OLD)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(root / "baglanti"), str(outside)], check=True, capture_output=True)
    item = sc.scan_category(cat(root), NOW)
    forged = sc.ScanItem(item.category, item.files + [sc.FileInfo(root / "baglanti" / "onemli.doc", 50)],
                         item.total, item.count)              # biri listeye junction üstünden bir yol sokmuş olsa bile
    res = sc.clean(forged, NOW)
    assert precious.exists() and res.skipped_unsafe == 1       # gerçek yol izinli klasörün dışında: reddedildi


def test_file_changed_after_preview_is_not_deleted(tmp_path):
    f = make(tmp_path / "a.tmp", 10, OLD)
    item = sc.scan_category(cat(tmp_path, min_age_days=1), NOW)
    os.utime(f, (NOW, NOW))                                     # önizlemeden sonra program dosyayı yeniden yazdı
    res = sc.clean(item, NOW)
    assert f.exists() and res.deleted == 0


def test_stop_event_halts_cleaning(tmp_path):
    for i in range(5):
        make(tmp_path / f"{i}.tmp", 1, OLD)
    stop = threading.Event()
    stop.set()
    res = sc.clean(sc.scan_category(cat(tmp_path), NOW), NOW, stop=stop)
    assert res.deleted == 0 and len(list(tmp_path.iterdir())) == 5


def test_recycle_method_moves_to_bin_instead_of_deleting(tmp_path, monkeypatch):
    a, b = make(tmp_path / "a.crdownload", 10, OLD), make(tmp_path / "b.part", 20, OLD)
    seen = []
    monkeypatch.setattr(sc.recycle, "move_to_trash", lambda paths: (seen.extend(paths), [paths[0]])[1])  # biri başarısız
    c = cat(tmp_path, method=RECYCLE, patterns=("*.crdownload", "*.part"), recursive=False)
    res = sc.clean(sc.scan_category(c, NOW), NOW)
    assert sorted(p.name for p in seen) == ["a.crdownload", "b.part"]
    assert res.deleted == 1 and res.failed == 1 and a.exists() and b.exists()    # sahte kutu hiçbir şeyi silmedi


def test_bin_method_empties_the_bin_only_through_the_dedicated_call(monkeypatch):
    calls = []
    monkeypatch.setattr(sc, "query_recycle_bin", lambda: (5_000, 7))
    monkeypatch.setattr(sc, "empty_recycle_bin", lambda: calls.append(1) or True)
    c = Category("bin", "Kutu", "x", BIN, default_on=False)
    item = sc.scan_category(c)
    assert (item.total, item.count) == (5_000, 7) and calls == []           # taramak boşaltmaz
    res = sc.clean(item)
    assert calls == [1] and res.freed == 5_000 and res.deleted == 7


def test_real_recycle_bin_query_is_read_only_and_returns_numbers():
    size, items = sc.query_recycle_bin()                                    # salt okunur
    assert isinstance(size, int) and isinstance(items, int) and size >= 0 and items >= 0


# ---------- kategoriler ----------
def test_default_categories_are_safe_by_default(tmp_path):
    cats = sc.default_categories(local_appdata=tmp_path / "L", home=tmp_path / "H", temp=tmp_path / "T")
    by = {c.id: c for c in cats}
    assert by["temp"].min_age_days >= 1 and by["temp"].roots == (tmp_path / "T",)
    assert by["partial"].method == RECYCLE and by["partial"].recursive is False         # indirmelere kalıcı silme yok
    assert by["bin"].method == BIN and by["bin"].default_on is False                    # kutuyu boşaltmak kendiliğinden seçili değil
    assert not by["chrome"].default_on and not by["edge"].default_on                    # önbellekler isteğe bağlı
    for c in cats:
        for r in c.roots:                                                               # kökler yalnızca bilinen yerlerde
            assert tmp_path in r.parents, c.id


def test_available_hides_categories_whose_folders_do_not_exist(tmp_path):
    (tmp_path / "T").mkdir()
    cats = sc.default_categories(local_appdata=tmp_path / "L", home=tmp_path / "H", temp=tmp_path / "T")
    ids = {c.id for c in sc.available(cats)}
    assert "temp" in ids and "bin" in ids and "edge" not in ids and "chrome" not in ids
