"""Yüklü programlar: kayıt defterinden listeleme ve kaldırma komutu üretme (Tk'den bağımsız, test edilebilir).

Kaynak: HKLM/HKCU ...\\Uninstall anahtarları (Ayarlar > Uygulamalar'ın da kullandığı yer). Programı kaldırma işini
programın KENDİ kaldırıcısı yapar (kayıtlı UninstallString); bu araç kendisi hiçbir şey silmez.
Kayıt defteri erişimi bir arka uç nesnesinin arkasındadır; testler sahte arka uçla çalışır.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Protocol

UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
UNINSTALL32 = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
SOURCES = [("HKLM", UNINSTALL, "Tüm kullanıcılar"), ("HKLM", UNINSTALL32, "Tüm kullanıcılar (32 bit)"),
           ("HKCU", UNINSTALL, "Yalnızca ben")]
_GUID = re.compile(r"\{[0-9A-Fa-f]{8}-(?:[0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}\}")
_UPDATE_NAME = re.compile(r"^(KB\d{6,}|(Security|Hotfix|Update) (Update|for))", re.I)
_UPDATE_TYPES = {"update", "hotfix", "security update", "service pack", "update rollup"}


@dataclass(frozen=True)
class Program:
    name: str
    version: str
    publisher: str
    install_date: str          # YYYY-AA-GG ya da boş
    size: int | None           # bayt; bilinmiyorsa None
    uninstall: str             # kayıtlı kaldırma komutu (boş olabilir)
    location: str
    removable: bool
    scope: str                 # "Tüm kullanıcılar" / "Yalnızca ben"


class Backend(Protocol):
    def entries(self) -> list[tuple[str, dict]]: ...   # [(kapsam adı, {değer adı: değer})]


def parse_date(raw: str | None) -> str:
    """'20260211' → '2026-02-11'; biçim tutmuyorsa boş."""
    raw = (raw or "").strip()
    if re.fullmatch(r"\d{8}", raw) and raw[:4] >= "1990":
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return ""


def list_programs(backend: Backend, include_updates: bool = False) -> list[Program]:
    """Kaldırılabilir/görünür programlar (sistem bileşenleri ve güncellemeler varsayılan olarak gizli), ada göre sıralı."""
    seen: dict[tuple[str, str], Program] = {}
    for scope, v in backend.entries():
        name = str(v.get("DisplayName") or "").strip()
        if not name or v.get("SystemComponent") == 1:
            continue
        release = str(v.get("ReleaseType") or "").strip().lower()
        if not include_updates and (v.get("ParentKeyName") or release in _UPDATE_TYPES or _UPDATE_NAME.match(name)):
            continue
        uninstall = str(v.get("UninstallString") or "").strip()
        size = v.get("EstimatedSize")
        prog = Program(
            name=name, version=str(v.get("DisplayVersion") or "").strip(),
            publisher=str(v.get("Publisher") or "").strip(), install_date=parse_date(v.get("InstallDate")),
            size=int(size) * 1024 if isinstance(size, int) and size > 0 else None,    # EstimatedSize KB cinsindendir
            uninstall=uninstall, location=str(v.get("InstallLocation") or "").strip().strip('"'),
            removable=bool(uninstall) and v.get("NoRemove") != 1, scope=scope)
        key = (name.lower(), prog.version)
        if key not in seen or (seen[key].size is None and prog.size):       # aynı program birden çok yerde olabilir
            seen[key] = prog
    return sorted(seen.values(), key=lambda p: p.name.lower())


def uninstall_command(p: Program) -> list[str] | str | None:
    """Kaldırma için çalıştırılacak komut. MSI programları 'değiştir' (/I) yerine 'kaldır' (/X) ile başlatılır.

    MSI için argüman listesi, diğerleri için kayıttaki komut satırı olduğu gibi döner (programın kendi kaldırıcısı).
    Kaldırılamayanlar için None.
    """
    if not p.removable:
        return None
    guid = _GUID.search(p.uninstall)
    if guid and re.search(r"msiexec", p.uninstall, re.I):
        return ["msiexec.exe", "/x", guid.group(0)]
    return p.uninstall


def sort_programs(programs: list[Program], by: str) -> list[Program]:
    """by: 'ad' | 'boyut' (büyükten küçüğe, bilinmeyenler sonda) | 'tarih' (yeniden eskiye, bilinmeyenler sonda)."""
    if by == "boyut":
        return sorted(programs, key=lambda p: (p.size is None, -(p.size or 0), p.name.lower()))
    if by == "tarih":
        return sorted(programs, key=lambda p: (p.install_date == "", _invert(p.install_date), p.name.lower()))
    return sorted(programs, key=lambda p: p.name.lower())


def _invert(date: str) -> tuple:
    return tuple(-ord(c) for c in date)


class WinBackend:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise NotImplementedError("Program listesi yalnızca Windows'ta desteklenir.")

    def entries(self) -> list[tuple[str, dict]]:
        import winreg
        out: list[tuple[str, dict]] = []
        for hive_name, subkey, scope in SOURCES:
            hive = winreg.HKEY_CURRENT_USER if hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
            try:
                root = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
            except OSError:
                continue
            with root:
                i = 0
                while True:
                    try:
                        child = winreg.EnumKey(root, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(root, child, 0, winreg.KEY_READ) as k:
                            values: dict = {}
                            j = 0
                            while True:
                                try:
                                    name, value, _kind = winreg.EnumValue(k, j)
                                except OSError:
                                    break
                                j += 1
                                values[name] = value
                    except OSError:
                        continue
                    out.append((scope, values))
        return out
