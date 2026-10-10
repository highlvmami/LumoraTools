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
