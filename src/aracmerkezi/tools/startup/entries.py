"""Windows başlangıç programları: listeleme ve açma/kapatma (Tk'den bağımsız, test edilebilir).

Kaynaklar (Görev Yöneticisi'ndeki "Başlangıç" sekmesiyle aynı):
  * HKCU\\...\\Run, HKLM\\...\\Run ve HKLM\\...\\WOW6432Node\\...\\Run kayıt defteri değerleri
  * Kullanıcı ve ortak "Başlangıç" klasörlerindeki kısayollar
Açma/kapatma programı SİLMEZ: Windows'un kullandığı HKCU\\...\\Explorer\\StartupApproved anahtarına
"etkin/devre dışı" işareti yazılır (Görev Yöneticisi'nin yaptığı gibi). Böylece her zaman geri alınabilir.
Kayıt defteri erişimi bir arka uç nesnesinin arkasındadır; testler sahte arka uçla çalışır.
"""
from __future__ import annotations

import os
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

APPROVED_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN32 = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"

# (anahtar kimliği, kovan, alt anahtar, StartupApproved alt anahtarı, görünen kaynak adı)
RUN_SOURCES = [
    ("hkcu-run", "HKCU", RUN, "Run", "Kayıt defteri (yalnızca ben)"),
    ("hklm-run", "HKLM", RUN, "Run", "Kayıt defteri (tüm kullanıcılar)"),
    ("hklm-run32", "HKLM", RUN32, "Run32", "Kayıt defteri (32 bit, tüm kullanıcılar)"),
]
FOLDER_SOURCES = [
    ("startup-user", False, "Başlangıç klasörü (yalnızca ben)"),
    ("startup-common", True, "Başlangıç klasörü (tüm kullanıcılar)"),
]
_EPOCH_DIFF = 11_644_473_600          # 1601 → 1970, saniye


@dataclass(frozen=True)
class Entry:
    name: str             # kayıt değeri adı ya da kısayol dosya adı
    command: str          # çalıştırılan komut / dosya yolu
    source: str           # görünen kaynak adı
    source_id: str
    approved_key: str     # StartupApproved alt anahtarı: Run | Run32 | StartupFolder
    enabled: bool


class Backend(Protocol):
    def run_values(self, hive: str, subkey: str) -> dict[str, str]: ...
    def approved(self, hive: str, key: str) -> dict[str, bytes]: ...
    def set_approved(self, key: str, name: str, data: bytes) -> None: ...
    def startup_files(self, common: bool) -> list[tuple[str, str]]: ...


# ---------- ikili durum biçimi ----------
def parse_state(data: bytes | None) -> bool:
    """StartupApproved değeri: ilk bayt çiftse (02, 06…) etkin, tekse (03, 07…) devre dışı. Kayıt yoksa etkin."""
    if not data:
        return True
    return (data[0] & 1) == 0


def make_state(enabled: bool, now: float | None = None) -> bytes:
    """12 baytlık değer: etkin → 02 + sıfırlar; devre dışı → 03 00 00 00 + FILETIME (kapatıldığı an)."""
    if enabled:
        return b"\x02" + b"\x00" * 11
    ticks = int(((time.time() if now is None else now) + _EPOCH_DIFF) * 10_000_000)
    return b"\x03\x00\x00\x00" + struct.pack("<Q", ticks)


# ---------- listeleme ve değiştirme ----------
def list_entries(backend: Backend) -> list[Entry]:
    """Tüm başlangıç girdileri; her biri için etkin/devre dışı durumu (kullanıcı ve makine işaretleri birlikte)."""
    approved = {}
    for key in ("Run", "Run32", "StartupFolder"):
        merged: dict[str, bool] = {}
        for hive in ("HKLM", "HKCU"):            # kullanıcı işareti makine işaretini geçersiz kılar
            for name, data in backend.approved(hive, key).items():
                merged[name.lower()] = parse_state(data)
        approved[key] = merged

    entries: list[Entry] = []
    for source_id, hive, subkey, key, label in RUN_SOURCES:
        for name, command in backend.run_values(hive, subkey).items():
            entries.append(Entry(name, command, label, source_id, key, approved[key].get(name.lower(), True)))
    for source_id, common, label in FOLDER_SOURCES:
        for name, path in backend.startup_files(common):
            entries.append(Entry(name, path, label, source_id, "StartupFolder",
                                 approved["StartupFolder"].get(name.lower(), True)))
    return sorted(entries, key=lambda e: (e.name.lower(), e.source_id))


def set_enabled(backend: Backend, entry: Entry, enabled: bool) -> None:
    """Girdiyi silmeden açar/kapatır; yalnızca bu kullanıcı için geçerlidir (yönetici yetkisi gerekmez)."""
    backend.set_approved(entry.approved_key, entry.name, make_state(enabled))


def command_path(command: str) -> Path | None:
    """Komut satırından çalıştırılan dosyanın yolunu çıkarır (tırnaklı ya da tırnaksız, argümanlı)."""
    command = os.path.expandvars(command.strip())
    if not command:
        return None
    if command.startswith('"'):
        end = command.find('"', 1)
        candidate = command[1:end] if end > 0 else command[1:]
    else:
        lower = command.lower()
        cut = min((i for i in (lower.find(ext) + len(ext) for ext in (".exe", ".lnk", ".bat", ".cmd", ".com", ".msc"))
                   if i >= len(".com")), default=len(command))
        candidate = command[:cut]
    return Path(candidate.strip()) if candidate.strip() else None


# ---------- gerçek arka uç (Windows) ----------
class WinBackend:
    def __init__(self, approved_root: str = APPROVED_ROOT) -> None:
        if sys.platform != "win32":
            raise NotImplementedError("Başlangıç programları yalnızca Windows'ta desteklenir.")
        self.approved_root = approved_root

    @staticmethod
    def _hive(name: str):
        import winreg
        return winreg.HKEY_CURRENT_USER if name == "HKCU" else winreg.HKEY_LOCAL_MACHINE

    def _read_values(self, hive: str, subkey: str, binary: bool = False) -> dict:
        import winreg
        out: dict = {}
        try:
            with winreg.OpenKey(self._hive(hive), subkey, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, value, kind = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    if binary:
                        if kind == winreg.REG_BINARY:
                            out[name] = bytes(value)
                    elif kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                        out[name] = str(value)
        except OSError:
            pass  # anahtar yok ya da okunamıyor: boş say
        return out

    def run_values(self, hive: str, subkey: str) -> dict[str, str]:
        return self._read_values(hive, subkey)

    def approved(self, hive: str, key: str) -> dict[str, bytes]:
        return self._read_values(hive, f"{self.approved_root}\\{key}", binary=True)

    def set_approved(self, key: str, name: str, data: bytes) -> None:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, f"{self.approved_root}\\{key}", 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_BINARY, data)

    def startup_files(self, common: bool) -> list[tuple[str, str]]:
        base = os.environ.get("ProgramData" if common else "APPDATA")
        if not base:
            return []
        folder = Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        try:
            return [(p.name, str(p)) for p in sorted(folder.iterdir())
                    if p.is_file() and p.name.lower() != "desktop.ini"]
        except OSError:
            return []
