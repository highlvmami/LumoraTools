import os
import threading

from aracmerkezi.tools.diskusage import scan as du


def build(tmp_path):
    (tmp_path / "A" / "alt").mkdir(parents=True)
    (tmp_path / "B").mkdir()
    (tmp_path / "bos").mkdir()
    (tmp_path / "A" / "buyuk.bin").write_bytes(b"x" * 5000)
    (tmp_path / "A" / "alt" / "orta.bin").write_bytes(b"x" * 2000)
    (tmp_path / "A" / "alt" / "kucuk.txt").write_bytes(b"x" * 10)
    (tmp_path / "B" / "b.dat").write_bytes(b"x" * 300)
    (tmp_path / "kok.txt").write_bytes(b"x" * 7)
    return tmp_path


def test_sizes_counts_and_sorting(tmp_path):
    res = du.scan(build(tmp_path))
    root = res.root
    assert root.size == 5000 + 2000 + 10 + 300 + 7 and root.file_count == 5
    assert [d.name for d in root.dirs] == ["A", "B", "bos"]               # boyuta göre azalan
    a = root.dirs[0]
    assert a.size == 7010 and a.own_size == 5000 and a.file_count == 3
    assert [d.name for d in a.dirs] == ["alt"] and a.dirs[0].size == 2010
    assert root.dirs[2].size == 0 and root.dirs[2].file_count == 0        # boş klasör
    assert not res.stopped and res.errors == 0


def test_largest_files_overall(tmp_path):
    res = du.scan(build(tmp_path), top_files=3)
    assert [(p.name, s) for p, s in res.largest] == [("buyuk.bin", 5000), ("orta.bin", 2000), ("b.dat", 300)]


def test_files_per_dir_are_capped_with_remainder_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(du, "TOP_FILES_PER_DIR", 2)
    for i in range(5):
        (tmp_path / f"f{i}.bin").write_bytes(b"x" * (100 * (i + 1)))
    root = du.scan(tmp_path).root
    assert [n for n, _ in root.files] == ["f4.bin", "f3.bin"] and root.other_files == 3
    assert root.size == 1500


def test_stop_event_halts_scan(tmp_path):
    build(tmp_path)
    stop = threading.Event()
    stop.set()
    res = du.scan(tmp_path, stop=stop)
    assert res.stopped and res.root.size == 0


def test_unreadable_dir_counts_as_error_not_crash(tmp_path, monkeypatch):
    build(tmp_path)
    real = os.scandir

    def flaky(path):
        if str(path).endswith("B"):
            raise PermissionError("erişim yok")
        return real(path)

    monkeypatch.setattr(du.os, "scandir", flaky)
    res = du.scan(tmp_path)
    assert res.errors == 1 and res.root.size == 5000 + 2000 + 10 + 7


def test_symlinked_dirs_are_not_followed(tmp_path):
    build(tmp_path)
    link = tmp_path / "baglanti"
    try:
        os.symlink(tmp_path / "A", link, target_is_directory=True)
    except (OSError, NotImplementedError):
        import pytest
        pytest.skip("sembolik bağlantı oluşturulamadı (yetki yok)")
    assert du.scan(tmp_path).root.file_count == 5     # A iki kez sayılmaz


def test_rows_sorted_with_remainder(tmp_path, monkeypatch):
    monkeypatch.setattr(du, "TOP_FILES_PER_DIR", 2)
    for i in range(4):
        (tmp_path / f"f{i}.bin").write_bytes(b"x" * (10 * (i + 1)))
    (tmp_path / "D").mkdir()
    (tmp_path / "D" / "d.bin").write_bytes(b"x" * 25)
    root = du.scan(tmp_path).root
    shown, rest_count, rest_size = du.rows(root, limit=60)
    assert [(k, n, s) for k, n, s, _ in shown] == [("file", "f3.bin", 40), ("file", "f2.bin", 30),
                                                    ("dir", "D", 25)]
    assert rest_count == 2 and rest_size == 10 + 20          # sığmayan f0 ve f1
    shown, rest_count, rest_size = du.rows(root, limit=1)
    assert len(shown) == 1 and rest_count == 2 + 2 and rest_size == 30 + 25 + 30


def test_junctions_are_not_followed(tmp_path):
    import subprocess
    import sys
    import pytest
    if sys.platform != "win32":
        pytest.skip("yalnızca Windows")
    build(tmp_path)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(tmp_path / "j"), str(tmp_path / "A")],
                   check=True, capture_output=True)
    assert du.scan(tmp_path).root.file_count == 5     # junction izlenmez: A iki kez sayılmaz
