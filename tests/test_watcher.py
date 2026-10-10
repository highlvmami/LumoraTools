from duzenle.watcher import Watcher


def test_waits_until_file_is_stable(tmp_path):
    msgs = []
    w = Watcher(tmp_path, on_message=msgs.append, settle=3.0)
    f = tmp_path / "a.jpg"
    f.write_text("x")
    w.tick(now=0)          # ilk görüldü
    w.tick(now=2)          # henüz yerleşmedi
    assert f.exists()
    w.tick(now=3.5)        # 3 sn sabit kaldı
    assert (tmp_path / "Resimler" / "a.jpg").exists()
    assert w.moved_count == 1


def test_growing_file_resets_timer(tmp_path):
    w = Watcher(tmp_path, on_message=lambda m: None, settle=3.0)
    f = tmp_path / "a.zip"
    f.write_text("x")
    w.tick(now=0)
    f.write_text("xxxxxxxx")   # boyut değişti
    w.tick(now=2.5)            # sayaç sıfırlandı
    w.tick(now=4)
    assert f.exists()
    w.tick(now=6)
    assert (tmp_path / "Arsivler" / "a.zip").exists()


def test_extension_filter_leaves_other_files_alone(tmp_path):
    w = Watcher(tmp_path, on_message=lambda m: None, settle=1.0, extensions={".png", ".JPG"})
    (tmp_path / "ekran.png").write_text("x")
    (tmp_path / "belge.pdf").write_text("x")
    (tmp_path / "foto.jpg").write_text("x")
    w.tick(now=0)
    w.tick(now=2)
    assert (tmp_path / "belge.pdf").exists()                      # filtre dışı: yerinde
    assert (tmp_path / "Resimler" / "ekran.png").exists() and (tmp_path / "Resimler" / "foto.jpg").exists()
    assert w.moved_count == 2
