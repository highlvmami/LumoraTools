import json
import sqlite3

from PIL import Image

from aracmerkezi.tools.clipboard import store as store_mod
from aracmerkezi.tools.clipboard.store import FILES, IMAGE, TEXT, ClipStore


def img(color=(200, 30, 30), size=(64, 32)):
    return Image.new("RGB", size, color)


def test_old_text_only_database_is_migrated_without_losing_data(tmp_path):
    db = tmp_path / "c.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE clips (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL UNIQUE, "
                "ts REAL NOT NULL, pinned INTEGER NOT NULL DEFAULT 0)")
    con.execute("INSERT INTO clips(text, ts, pinned) VALUES('eski kayit', 100.0, 1)")
    con.execute("INSERT INTO clips(text, ts, pinned) VALUES('ikinci', 200.0, 0)")
    con.commit()
    con.close()
    s = ClipStore(db)
    clips = s.list()
    assert [(c.text, c.kind, c.pinned) for c in clips] == [("eski kayit", TEXT, True), ("ikinci", TEXT, False)]
    assert s.add("yeni") and s.count() == 3
    assert ClipStore(db).count() == 3                       # ikinci açılışta tekrar taşıma yok, veri duruyor


def test_image_is_stored_deduped_and_labelled(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    assert s.add_image(img()) and s.add_image(img())       # aynı içerik: tek kayıt
    assert s.add_image(img((10, 200, 10)))
    clips = s.list()
    assert len(clips) == 2 and {c.kind for c in clips} == {IMAGE}
    c = clips[0]
    assert "64×32" in c.label and c.meta["w"] == 64
    path = s.image_path(c)
    assert path and path.suffix == ".png" and path.parent == s.images_dir
    assert Image.open(path).size == (64, 32)               # diske gerçek PNG yazıldı
    assert len(list(s.images_dir.iterdir())) == 2


def test_images_are_searchable_by_word(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    s.add("sadece metin")
    s.add_image(img())
    assert [c.kind for c in s.list("görüntü")] == [IMAGE]
    assert [c.kind for c in s.list("RESIM")] == [IMAGE]
    assert [c.kind for c in s.list("64x32")] == [IMAGE]
    assert [c.kind for c in s.list("metin")] == [TEXT]


def test_files_are_stored_with_names_searchable(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    assert s.add_files([r"C:\Belgeler\Rapor Ekim.pdf", r"C:\Belgeler\foto.png", r"C:\x\c.txt", r"C:\x\d.txt"])
    (c,) = s.list()
    assert c.kind == FILES and len(c.paths) == 4
    assert "4 dosya" in c.label and "Rapor Ekim.pdf" in c.label and "(+1)" in c.label
    assert len(s.list("rapor ekim")) == 1                   # dosya adıyla bulunur
    assert len(s.list("belgeler")) == 1                     # klasör adıyla da
    assert not s.add_files([]) and not s.add_files(["  "])


def test_same_files_copied_again_bump_instead_of_duplicate(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    s.add_files(["a.txt"])
    s.add("araya giren")
    s.add_files(["a.txt"])
    assert s.count() == 2 and s.list()[0].kind == FILES


def test_oversized_images_are_rejected(tmp_path, monkeypatch):
    s = ClipStore(tmp_path / "c.db")
    monkeypatch.setattr(store_mod, "MAX_PIXELS", 100)
    assert not s.add_image(img(size=(20, 20)))
    monkeypatch.setattr(store_mod, "MAX_PIXELS", 40_000_000)
    monkeypatch.setattr(store_mod, "MAX_IMAGE_BYTES", 10)
    assert not s.add_image(img(size=(50, 50)))
    assert s.count() == 0
    assert not s.images_dir.exists() or not list(s.images_dir.iterdir())


def test_delete_and_clear_remove_image_files_but_not_pinned(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    s.add_image(img((1, 2, 3)))
    s.add_image(img((4, 5, 6)))
    s.add_image(img((7, 8, 9)))
    a, b, c = s.list()
    s.set_pinned(a.id, True)
    s.delete(b.id)
    assert s.image_path(b) is None and s.image_path(a) and s.image_path(c)
    assert s.clear_unpinned() == 1
    assert s.image_path(c) is None and s.image_path(a) is not None      # sabitlenen görüntü dosyasıyla kalır
    assert len(list(s.images_dir.iterdir())) == 1


def test_image_limit_prunes_oldest_unpinned_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "MAX_IMAGES", 2)
    s = ClipStore(tmp_path / "c.db")
    for i in range(4):
        s.add_image(img((i * 40, 0, 0)))
    assert s.count() == 2 and len(list(s.images_dir.iterdir())) == 2


def test_image_path_rejects_path_traversal(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    s.db.execute("INSERT INTO clips(kind, text, ref, ts) VALUES('image', 'x', ?, 1)",
                 (json.dumps({"file": "..\\..\\gizli.png"}),))
    (c,) = s.list()
    assert s.image_path(c) is None                          # images_dir dışına çıkamaz
