import os
from datetime import datetime

from duzenle import engine
from aracmerkezi.tools.screenshots import library as lib


def make(path, when=None, size=10):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if when:
        ts = when.timestamp()
        os.utime(path, (ts, ts))
    return path


def test_lists_only_images_newest_first_recursively(tmp_path):
    make(tmp_path / "eski.png", datetime(2026, 1, 5))
    make(tmp_path / "2026" / "03" / "yeni.jpg", datetime(2026, 3, 9))
    make(tmp_path / "belge.pdf", datetime(2026, 4, 1))
    make(tmp_path / ".gizli" / "x.png", datetime(2026, 4, 1))
    shots = lib.list_shots(tmp_path)
    assert [s.path.name for s in shots] == ["yeni.jpg", "eski.png"]


def test_filter_by_name_note_folder_and_date_text(tmp_path):
    a = make(tmp_path / "Ekran görüntüsü 1.png", datetime(2026, 10, 11, 9))
    b = make(tmp_path / "2026" / "09" / "hata.png", datetime(2026, 9, 3, 18))
    shots = lib.list_shots(tmp_path)
    notes = {shots[0].key: "Fatura sayfası"}      # en yenisi a
    f = lambda q, **kw: [s.path.name for s in lib.filter_shots(shots, q, notes, tmp_path, **kw)]
    assert f("") == ["Ekran görüntüsü 1.png", "hata.png"]
    assert f("EKRAN GORUNTUSU") == ["Ekran görüntüsü 1.png"]        # Türkçe harf duyarsız
    assert f("fatura") == ["Ekran görüntüsü 1.png"]                  # nottan
    assert f("2026\\09") == ["hata.png"]                              # klasörden
    assert f("11.10.2026") == ["Ekran görüntüsü 1.png"]              # tarih metninden
    assert f("2026-09-03") == ["hata.png"]
    assert f("hata fatura") == []                                     # tek bir görüntüde ikisi yok


def test_filter_by_date_range(tmp_path):
    make(tmp_path / "a.png", datetime(2026, 10, 10, 12))
    make(tmp_path / "b.png", datetime(2026, 10, 11, 12))
    shots = lib.list_shots(tmp_path)
    since, until = datetime(2026, 10, 11).timestamp(), datetime(2026, 10, 12).timestamp()
    assert [s.path.name for s in lib.filter_shots(shots, "", {}, tmp_path, since, until)] == ["b.png"]


def test_plan_organize_only_moves_root_images_by_date(tmp_path):
    make(tmp_path / "a.png", datetime(2026, 10, 11, 8))
    make(tmp_path / "b.jpg", datetime(2026, 9, 2, 8))
    make(tmp_path / "belge.pdf", datetime(2026, 10, 11, 8))                 # görüntü değil: dokunma
    make(tmp_path / "2025" / "12" / "zaten.png", datetime(2025, 12, 1))     # zaten düzenli: dokunma
    moves = lib.plan_organize(tmp_path)
    got = sorted((m.src.name, str(m.dst.parent.relative_to(tmp_path.resolve()))) for m in moves)
    assert got == [("a.png", os.path.join("2026", "10")), ("b.jpg", os.path.join("2026", "09"))]
    engine.apply(tmp_path, moves)
    assert (tmp_path / "belge.pdf").exists() and (tmp_path / "2025" / "12" / "zaten.png").exists()
    day = lib.plan_organize(tmp_path, "%Y/%m/%d")                           # gün biçimi: artık düzenli dosyaları yok
    assert day == []


def test_day_format(tmp_path):
    make(tmp_path / "a.png", datetime(2026, 10, 11, 8))
    (m,) = lib.plan_organize(tmp_path, "%Y/%m/%d")
    assert m.dst.parent.relative_to(tmp_path.resolve()).parts == ("2026", "10", "11")


def test_note_key_survives_move_and_store_roundtrip(tmp_path):
    f = make(tmp_path / "a.png", datetime(2026, 10, 11, 8), size=42)
    (shot,) = lib.list_shots(tmp_path)
    store = lib.NoteStore(tmp_path / "n.db")
    store.set(shot.key, "  önemli  ")
    engine.apply(tmp_path, lib.plan_organize(tmp_path))
    (moved,) = lib.list_shots(tmp_path)
    assert moved.path != f and moved.key == shot.key
    assert store.all()[moved.key] == "önemli"
    store.set(moved.key, "   ")                    # boş not siler
    assert store.all() == {}
