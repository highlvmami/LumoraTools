import struct
import sys
from pathlib import Path

import pytest

from aracmerkezi.tools.startup import entries as st

NOW = 1_700_000_000.0


class FakeBackend:
    """Bellekte sahte kayıt defteri ve başlangıç klasörleri."""

    def __init__(self):
        self.run = {("HKCU", st.RUN): {"Spotify": r'"C:\Spotify\Spotify.exe" --autostart'},
                    ("HKLM", st.RUN): {"SecurityHealth": r"%windir%\system32\SecurityHealthSystray.exe"},
                    ("HKLM", st.RUN32): {"Eski": r"C:\Eski\eski.exe"}}
        self.approved_store = {("HKLM", "Run"): {}, ("HKCU", "Run"): {}, ("HKCU", "Run32"): {},
                               ("HKLM", "Run32"): {}, ("HKCU", "StartupFolder"): {}, ("HKLM", "StartupFolder"): {}}
        self.files = {False: [("OneNote.lnk", r"C:\u\Startup\OneNote.lnk")], True: []}

    def run_values(self, hive, subkey):
        return dict(self.run.get((hive, subkey), {}))

    def approved(self, hive, key):
        return dict(self.approved_store.get((hive, key), {}))

    def set_approved(self, key, name, data):
        self.approved_store[("HKCU", key)][name] = data

    def startup_files(self, common):
        return list(self.files[common])


def by_name(entries):
    return {e.name: e for e in entries}


def test_state_format_matches_what_task_manager_writes():
    assert st.parse_state(b"\x02" + b"\0" * 11) and st.parse_state(b"\x06" + b"\0" * 11)          # etkin
    assert not st.parse_state(b"\x03" + b"\0" * 11) and not st.parse_state(b"\x07" + b"\0" * 11)  # devre dışı
    assert st.parse_state(None) and st.parse_state(b"")                                           # kayıt yok: etkin
    on, off = st.make_state(True), st.make_state(False, NOW)
    assert len(on) == len(off) == 12 and on[0] == 2 and off[:4] == b"\x03\x00\x00\x00"
    ticks = struct.unpack("<Q", off[4:])[0]
    assert ticks == int((NOW + 11_644_473_600) * 10_000_000)                                      # geçerli FILETIME
    assert st.parse_state(on) and not st.parse_state(off)


def test_lists_all_sources_and_defaults_to_enabled():
    entries = st.list_entries(FakeBackend())
    e = by_name(entries)
    assert set(e) == {"Spotify", "SecurityHealth", "Eski", "OneNote.lnk"}
    assert all(x.enabled for x in entries)
    assert e["Spotify"].approved_key == "Run" and e["Eski"].approved_key == "Run32"
    assert e["OneNote.lnk"].approved_key == "StartupFolder" and "Başlangıç klasörü" in e["OneNote.lnk"].source


def test_disabled_state_is_read_from_user_and_machine_marks_user_wins():
    b = FakeBackend()
    b.approved_store[("HKCU", "Run")]["spotify"] = st.make_state(False, NOW)          # ad büyük/küçük harf fark etmez
    b.approved_store[("HKLM", "Run")]["SecurityHealth"] = st.make_state(False, NOW)   # makine düzeyinde kapalı
    e = by_name(st.list_entries(b))
    assert not e["Spotify"].enabled and not e["SecurityHealth"].enabled and e["Eski"].enabled
    b.approved_store[("HKCU", "Run")]["SecurityHealth"] = st.make_state(True)         # kullanıcı yeniden açtı
    assert by_name(st.list_entries(b))["SecurityHealth"].enabled


def test_toggling_never_deletes_the_entry_and_is_reversible():
    b = FakeBackend()
    spotify = by_name(st.list_entries(b))["Spotify"]
    st.set_enabled(b, spotify, False)
    assert b.run[("HKCU", st.RUN)]["Spotify"]                                         # program girdisi duruyor
    assert not by_name(st.list_entries(b))["Spotify"].enabled
    st.set_enabled(b, by_name(st.list_entries(b))["Spotify"], True)
    assert by_name(st.list_entries(b))["Spotify"].enabled
    folder_item = by_name(st.list_entries(b))["OneNote.lnk"]
    st.set_enabled(b, folder_item, False)
    assert ("HKCU", "StartupFolder") in b.approved_store and not by_name(st.list_entries(b))["OneNote.lnk"].enabled


def test_command_path_extracts_the_executable():
    assert st.command_path(r'"C:\Program Files\App\app.exe" --flag x') == Path(r"C:\Program Files\App\app.exe")
    assert st.command_path(r"C:\Eski\eski.exe -silent") == Path(r"C:\Eski\eski.exe")
    assert st.command_path(r"C:\x\run.bat /min") == Path(r"C:\x\run.bat")
    assert st.command_path("") is None and st.command_path("   ") is None


@pytest.mark.skipif(sys.platform != "win32", reason="yalnızca Windows")
def test_real_read_only_listing_works_on_this_machine():
    entries = st.list_entries(st.WinBackend())                                        # salt okunur
    assert isinstance(entries, list)
    for e in entries:
        assert e.name and e.source and isinstance(e.enabled, bool)


@pytest.mark.skipif(sys.platform != "win32", reason="yalnızca Windows")
def test_real_registry_toggle_roundtrip_in_an_isolated_test_key():
    """Gerçek winreg çağrılarını, kullanıcının gerçek StartupApproved anahtarına DOKUNMADAN, ayrı bir deneme
    anahtarında sınar ve sonunda deneme anahtarını siler."""
    import winreg
    root = r"Software\LumoraToolsTest\StartupApproved"
    backend = st.WinBackend(approved_root=root)
    entry = st.Entry("lumora-deneme", "x.exe", "deneme", "hkcu-run", "Run", True)
    try:
        st.set_enabled(backend, entry, False)
        assert not st.parse_state(backend.approved("HKCU", "Run")["lumora-deneme"])
        st.set_enabled(backend, entry, True)
        assert st.parse_state(backend.approved("HKCU", "Run")["lumora-deneme"])
    finally:
        for sub in (root + r"\Run", root, r"Software\LumoraToolsTest"):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except OSError:
                pass
    with pytest.raises(OSError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\LumoraToolsTest")        # deneme anahtarı kalmadı
