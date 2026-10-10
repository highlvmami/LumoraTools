import os
from datetime import datetime

from duzenle import engine
from duzenle.cli import main


def touch(path, content="x", when=None):
    path.write_text(content)
    if when:
        ts = when.timestamp()
        os.utime(path, (ts, ts))
    return path


def test_extension_mode_moves_files(tmp_path):
    touch(tmp_path / "a.jpg")
    touch(tmp_path / "b.pdf")
    touch(tmp_path / "c.xyz")
    done, failed = engine.apply(tmp_path, engine.plan(tmp_path, "uzanti"))
    assert not failed and len(done) == 3
    assert (tmp_path / "Resimler" / "a.jpg").exists()
    assert (tmp_path / "Belgeler" / "b.pdf").exists()
    assert (tmp_path / "Diger" / "c.xyz").exists()


def test_date_mode_uses_mtime(tmp_path):
    touch(tmp_path / "a.txt", when=datetime(2025, 3, 14))
    engine.apply(tmp_path, engine.plan(tmp_path, "tarih"))
    assert (tmp_path / "2025" / "03" / "a.txt").exists()


def test_combined_mode(tmp_path):
    touch(tmp_path / "a.png", when=datetime(2024, 12, 1))
    engine.apply(tmp_path, engine.plan(tmp_path, "birlesik"))
    assert (tmp_path / "Resimler" / "2024" / "12" / "a.png").exists()


def test_skips_partial_hidden_and_dirs(tmp_path):
    touch(tmp_path / "yari.crdownload")
    touch(tmp_path / ".gizli")
    (tmp_path / "klasor").mkdir()
    assert engine.plan(tmp_path) == []


def test_name_conflict_gets_suffix(tmp_path):
    (tmp_path / "Resimler").mkdir()
    touch(tmp_path / "Resimler" / "a.jpg", "eski")
    touch(tmp_path / "a.jpg", "yeni")
    engine.apply(tmp_path, engine.plan(tmp_path))
    assert (tmp_path / "Resimler" / "a.jpg").read_text() == "eski"
    assert (tmp_path / "Resimler" / "a (1).jpg").read_text() == "yeni"


def test_dry_run_changes_nothing(tmp_path, capsys):
    touch(tmp_path / "a.jpg")
    assert main([str(tmp_path), "--dry-run"]) == 0
    assert (tmp_path / "a.jpg").exists()
    assert not (tmp_path / "Resimler").exists()


def test_undo_restores_and_prunes(tmp_path):
    touch(tmp_path / "a.jpg")
    touch(tmp_path / "b.pdf")
    engine.apply(tmp_path, engine.plan(tmp_path))
    restored, skipped = engine.undo(tmp_path)
    assert (restored, skipped) == (2, 0)
    assert (tmp_path / "a.jpg").exists() and (tmp_path / "b.pdf").exists()
    assert not (tmp_path / "Resimler").exists()
    assert not (tmp_path / engine.LOG_NAME).exists()


def test_second_run_is_idempotent(tmp_path):
    touch(tmp_path / "a.jpg")
    engine.apply(tmp_path, engine.plan(tmp_path))
    assert engine.plan(tmp_path, recursive=True) == []


def test_skips_windows_system_files(tmp_path):
    touch(tmp_path / "desktop.ini")
    touch(tmp_path / "Thumbs.db")
    touch(tmp_path / "a.jpg")
    assert [m.src.name for m in engine.plan(tmp_path)] == ["a.jpg"]


def test_skips_files_with_hidden_attribute(tmp_path):
    import subprocess
    import sys
    import pytest
    if sys.platform != "win32":
        pytest.skip("yalnızca Windows")
    gizli = touch(tmp_path / "gizli.pdf")
    touch(tmp_path / "gorunur.pdf")
    subprocess.run(["attrib", "+h", str(gizli)], check=True)
    assert [m.src.name for m in engine.plan(tmp_path)] == ["gorunur.pdf"]
