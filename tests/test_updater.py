import hashlib
import json

import pytest

from aracmerkezi import updater
from aracmerkezi.updater import UpdateError


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_release(folder, version, payload=b"YENI-EXE", **over):
    folder.mkdir(exist_ok=True)
    (folder / "App.exe").write_bytes(payload)
    manifest = {"version": version, "url": "App.exe", "sha256": sha(payload), "notes": "n"} | over
    path = folder / "manifest.json"
    path.write_text(json.dumps(manifest))
    return str(path)


def test_version_comparison():
    assert updater.is_newer("0.3.1", "0.3.0")
    assert updater.is_newer("0.10.0", "0.9.9")      # sayısal, metin değil
    assert updater.is_newer("1.0", "0.9.9")
    assert not updater.is_newer("0.3.0", "0.3.0")
    assert not updater.is_newer("0.3", "0.3.0")      # eksik sıfırlar eşit sayılır
    assert not updater.is_newer("0.2.9", "0.3.0")
    with pytest.raises(UpdateError):
        updater.parse_version("sürüm")


def test_check_returns_update_only_when_newer(tmp_path):
    src = write_release(tmp_path, "0.4.0")
    assert updater.check(src, "0.3.0").version == "0.4.0"
    assert updater.check(src, "0.4.0") is None
    assert updater.check(src, "1.0.0") is None


def test_relative_url_resolves_next_to_manifest(tmp_path):
    update = updater.fetch_manifest(write_release(tmp_path, "0.4.0"))
    assert update.url == str(tmp_path / "App.exe")


def test_rejects_bad_manifests(tmp_path):
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({"version": "1.0"}))
    with pytest.raises(UpdateError):
        updater.fetch_manifest(str(bad))
    bad.write_text(json.dumps({"version": "1.0", "url": "x", "sha256": "abc"}))
    with pytest.raises(UpdateError, match="sha256"):
        updater.fetch_manifest(str(bad))
    bad.write_text("json değil")
    with pytest.raises(UpdateError):
        updater.fetch_manifest(str(bad))
    with pytest.raises(UpdateError):
        updater.fetch_manifest(str(tmp_path / "yok.json"))


def test_refuses_plain_http():
    with pytest.raises(UpdateError, match="https"):
        updater.fetch_manifest("http://example.com/manifest.json")


def test_download_verifies_hash_and_reports_progress(tmp_path):
    update = updater.fetch_manifest(write_release(tmp_path / "rel", "0.4.0", payload=b"x" * 3000))
    seen = []
    out = updater.download(update, tmp_path / "dl.bin", lambda d, t: seen.append(d))
    assert out.read_bytes() == b"x" * 3000 and seen[-1] == 3000


def test_download_rejects_tampered_file(tmp_path):
    src = write_release(tmp_path / "rel", "0.4.0")
    (tmp_path / "rel" / "App.exe").write_bytes(b"KOTU-NIYETLI")  # manifestten sonra değiştirildi
    with pytest.raises(UpdateError, match="SHA-256"):
        updater.download(updater.fetch_manifest(src), tmp_path / "dl.bin")
    assert not (tmp_path / "dl.bin").exists()  # reddedilen dosya bırakılmaz


def test_install_swaps_executable_and_cleanup(tmp_path):
    exe = tmp_path / "AracMerkezi.exe"
    exe.write_bytes(b"ESKI")
    update = updater.fetch_manifest(write_release(tmp_path / "rel", "0.4.0", payload=b"YENI"))
    updater.install(update, exe)
    assert exe.read_bytes() == b"YENI"
    assert updater.old_path(exe).read_bytes() == b"ESKI"
    assert not updater.new_path(exe).exists()
    updater.cleanup_old(exe)
    assert not updater.old_path(exe).exists()


def test_failed_download_leaves_current_exe_untouched(tmp_path):
    exe = tmp_path / "AracMerkezi.exe"
    exe.write_bytes(b"ESKI")
    src = write_release(tmp_path / "rel", "0.4.0")
    (tmp_path / "rel" / "App.exe").write_bytes(b"bozuk")
    with pytest.raises(UpdateError):
        updater.install(updater.fetch_manifest(src), exe)
    assert exe.read_bytes() == b"ESKI" and not updater.old_path(exe).exists()


def test_replace_rolls_back_when_new_missing(tmp_path):
    exe = tmp_path / "A.exe"
    exe.write_bytes(b"ESKI")
    with pytest.raises(OSError):
        updater.replace_executable(exe, tmp_path / "yok.new")
    assert exe.read_bytes() == b"ESKI"
