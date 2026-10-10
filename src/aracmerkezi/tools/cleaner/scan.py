"""Sistem temizleyici çekirdeği: tara → önizle → temizle (Tk'den bağımsız, test edilebilir).

Güvenlik ilkeleri:
  * Yalnızca aşağıda tanımlı klasörlere (kategorilerin `roots`) dokunulur; her silmeden önce yolun bu klasörlerin
    içinde kaldığı yeniden doğrulanır.
  * Sembolik bağlantılar ve junction'lar izlenmez (içindeki başka klasörü silmemek için).
  * Geçici dosyalar için bir yaş sınırı vardır; çalışan programların taze dosyalarına dokunulmaz. Kullanımdaki
    dosyalar zaten silinemez; atlanır ve sayılır.
  * Klasör ağacı silinmez (`rmtree` yok): önce dosyalar, sonra yalnızca boşalmış alt klasörler kaldırılır.
  * Kullanıcı verisine yakın şeyler (indirme artıkları) kalıcı silinmez, Geri Dönüşüm Kutusu'na taşınır.
"""
from __future__ import annotations

import ctypes
import fnmatch
import os
import stat
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ... import recycle
from ...fsutil import is_link

DELETE, RECYCLE, BIN = "delete", "recycle", "bin"
MAX_FILES_PER_CATEGORY = 300_000
DAY = 86_400.0

Progress = Callable[[str], None]


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    description: str
    method: str                              # DELETE (kalıcı sil) | RECYCLE (Geri Dönüşüm Kutusu'na taşı) | BIN (kutuyu boşalt)
    roots: tuple[Path, ...] = ()
    min_age_days: float = 0.0
    patterns: tuple[str, ...] = ()           # boşsa tüm dosyalar; doluysa yalnızca ada uyanlar (küçük harfle)
    recursive: bool = True
    default_on: bool = True


@dataclass(frozen=True)
class FileInfo:
    path: Path
    size: int


@dataclass
class ScanItem:
    category: Category
    files: list[FileInfo] = field(default_factory=list)
    total: int = 0                # bayt
    count: int = 0                # dosya (ya da kutudaki öğe) sayısı
    too_young: int = 0            # yaş sınırı yüzünden atlanan dosya sayısı
    errors: int = 0               # okunamayan klasör/dosya sayısı


@dataclass
class CleanResult:
    freed: int = 0
    deleted: int = 0
    failed: int = 0               # kullanımda ya da izin yok
    skipped_unsafe: int = 0       # izinli klasörlerin dışında kaldığı için dokunulmayanlar


def default_categories(local_appdata: Path | None = None, home: Path | None = None,
                       temp: Path | None = None) -> list[Category]:
    """Bu bilgisayardaki temizlenebilir yerler. Yollar parametre alır (testte sahte klasörlerle denenir)."""
    home = home or Path.home()
    local = local_appdata or Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    temp = temp or Path(tempfile.gettempdir())
    return [
        Category("temp", "Geçici dosyalar", "Kullanıcı Temp klasörü; 1 günden eski olanlar. Çalışan programların dosyaları atlanır.",
                 DELETE, (temp,), min_age_days=1),
        Category("crash", "Çökme dökümleri ve hata raporları", "Programların çökme sırasında bıraktığı döküm ve Windows hata raporları.",
                 DELETE, (local / "CrashDumps", local / "Microsoft" / "Windows" / "WER" / "ReportArchive",
                          local / "Microsoft" / "Windows" / "WER" / "ReportQueue")),
        Category("partial", "Yarım kalmış indirmeler", "İndirilenler'deki .crdownload, .part, .tmp gibi 1 günden eski artıklar. "
                 "Geri Dönüşüm Kutusu'na taşınır.", RECYCLE, (home / "Downloads",), min_age_days=1,
                 patterns=("*.crdownload", "*.part", "*.partial", "*.download", "*.tmp"), recursive=False),
        Category("chrome", "Chrome önbelleği", "Sayfa önbelleği; siteler ilk açılışta biraz yavaş yüklenir.",
                 DELETE, (local / "Google" / "Chrome" / "User Data" / "Default" / "Cache" / "Cache_Data",
                          local / "Google" / "Chrome" / "User Data" / "Default" / "Code Cache"), default_on=False),
        Category("edge", "Edge önbelleği", "Sayfa önbelleği; siteler ilk açılışta biraz yavaş yüklenir.",
                 DELETE, (local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache" / "Cache_Data",
                          local / "Microsoft" / "Edge" / "User Data" / "Default" / "Code Cache"), default_on=False),
        Category("pip", "pip önbelleği", "Python paketlerinin indirme önbelleği; gerektiğinde yeniden iner.",
                 DELETE, (local / "pip" / "Cache",), default_on=False),
        Category("bin", "Geri Dönüşüm Kutusu", "Kutudaki her şey KALICI silinir ve geri alınamaz.", BIN, default_on=False),
    ]


def available(categories: list[Category]) -> list[Category]:
    """Klasörü hiç olmayan kategorileri (ör. Edge kurulu değilse) listeden çıkarır; kutu her zaman vardır."""
    return [c for c in categories if c.method == BIN or any(r.is_dir() for r in c.roots)]


# ---------- Geri Dönüşüm Kutusu (Windows) ----------
class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("i64Size", ctypes.c_int64), ("i64NumItems", ctypes.c_int64)]


def query_recycle_bin() -> tuple[int, int]:
    """(bayt, öğe sayısı). Salt okunur. Windows dışında (0, 0)."""
    if sys.platform != "win32":
        return 0, 0
    info = _SHQUERYRBINFO(ctypes.sizeof(_SHQUERYRBINFO))
    if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) != 0:
        return 0, 0
    return int(info.i64Size), int(info.i64NumItems)


def empty_recycle_bin() -> bool:
    """Geri Dönüşüm Kutusu'nu KALICI olarak boşaltır (onay penceresi göstermez; çağıran onay almış olmalı)."""
    if sys.platform != "win32":
        raise NotImplementedError("Geri Dönüşüm Kutusu yalnızca Windows'ta desteklenir.")
    flags = 0x1 | 0x2 | 0x4          # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    return ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags) == 0


# ---------- tarama ----------
def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    return not patterns or any(fnmatch.fnmatch(name.lower(), p) for p in patterns)


def _walk(root: Path, recursive: bool, stop: threading.Event | None, errors: list[int]):
    """(dosya yolu, boyut, mtime) üretir. Bağlantılara girmez."""
    stack = [root]
    while stack:
        current = stack.pop()
        if stop is not None and stop.is_set():
            return
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:
            errors[0] += 1
            continue
        for e in entries:
            try:
                if is_link(e):
                    continue
                if e.is_dir(follow_symlinks=False):
                    if recursive:
                        stack.append(Path(e.path))
                elif e.is_file(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False)
                    yield Path(e.path), st.st_size, st.st_mtime
            except OSError:
                errors[0] += 1


def scan_category(cat: Category, now: float | None = None, stop: threading.Event | None = None,
                  progress: Progress | None = None) -> ScanItem:
    item = ScanItem(cat)
    if cat.method == BIN:
        item.total, item.count = query_recycle_bin()
        return item
    now = time.time() if now is None else now
    cutoff = now - cat.min_age_days * DAY
    errors = [0]
    for root in cat.roots:
        if not root.is_dir():
            continue
        for path, size, mtime in _walk(root, cat.recursive, stop, errors):
            if not _matches(path.name, cat.patterns):
                continue
            if mtime > cutoff:
                item.too_young += 1
                continue
            item.files.append(FileInfo(path, size))
            item.total += size
            item.count += 1
            if progress and item.count % 500 == 0:
                progress(f"{cat.name}: {item.count:,} dosya")
            if item.count >= MAX_FILES_PER_CATEGORY:
                item.errors = errors[0]
                return item
    item.errors = errors[0]
    item.files.sort(key=lambda f: -f.size)       # en büyükler önce (önizleme için)
    return item


# ---------- temizlik ----------
def _inside(path: Path, roots: tuple[Path, ...]) -> bool:
    """`path` izinli klasörlerden birinin içinde mi? (.. ve bağlantılarla kaçış engellenir)"""
    try:
        real = Path(os.path.realpath(path))
    except OSError:
        return False
    for root in roots:
        try:
            real.relative_to(Path(os.path.realpath(root)))
            return True
        except ValueError:
            continue
    return False


def _remove_file(path: Path) -> bool:
    try:
        os.remove(path)
        return True
    except PermissionError:
        try:                                     # salt okunur özniteliği yüzünden olabilir; kullanımdaysa yine başarısız olur
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)
            return True
        except OSError:
            return False
    except OSError:
        return False


def _prune_empty_dirs(roots: tuple[Path, ...]) -> None:
    """Dosyalar silindikten sonra yalnızca BOŞ kalan alt klasörleri kaldırır; kök klasörlere dokunmaz."""
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, _files in os.walk(root, topdown=False):
            current = Path(dirpath)
            if current == root or not _inside(current, (root,)):
                continue
            try:
                if not os.path.islink(current) and not os.listdir(current):
                    os.rmdir(current)             # yalnızca boşsa başarılı olur
            except OSError:
                pass


def still_eligible(path: Path, cat: Category, now: float) -> bool:
    """Önizlemeden sonra dosya değişmiş olabilir: hâlâ yaş sınırını ve desen koşulunu sağlıyor mu?"""
    try:
        st = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and _matches(path.name, cat.patterns) and st.st_mtime <= now - cat.min_age_days * DAY


def clean(item: ScanItem, now: float | None = None, stop: threading.Event | None = None,
          progress: Progress | None = None) -> CleanResult:
    cat, result = item.category, CleanResult()
    now = time.time() if now is None else now
    if cat.method == BIN:
        if empty_recycle_bin():
            result.freed, result.deleted = item.total, item.count
        else:
            result.failed = 1
        return result

    safe: list[FileInfo] = []
    for f in item.files:
        if not _inside(f.path, cat.roots):
            result.skipped_unsafe += 1            # izinli klasörlerin dışı: asla dokunma
        elif still_eligible(f.path, cat, now):
            safe.append(f)
    if cat.method == RECYCLE:
        gone = set(recycle.move_to_trash([f.path for f in safe]))
        for f in safe:
            if f.path in gone:
                result.freed += f.size
                result.deleted += 1
            else:
                result.failed += 1
        return result

    for i, f in enumerate(safe, 1):
        if stop is not None and stop.is_set():
            break
        if _remove_file(f.path):
            result.freed += f.size
            result.deleted += 1
        else:
            result.failed += 1
        if progress and i % 200 == 0:
            progress(f"{cat.name}: {i:,} / {len(safe):,}")
    _prune_empty_dirs(cat.roots)
    return result
