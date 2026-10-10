"""Dosyaları kalıcı silmek yerine Windows Geri Dönüşüm Kutusu'na taşır."""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

FO_DELETE = 0x3
FOF_SILENT = 0x4
FOF_NOCONFIRMATION = 0x10
FOF_ALLOWUNDO = 0x40          # kalıcı silme yerine Geri Dönüşüm Kutusu
FOF_NOERRORUI = 0x400
FOF_WANTNUKEWARNING = 0x4000  # dosya kutuya sığmayıp KALICI silinecekse uyarı göster (kullanıcı vazgeçebilir)


def build_pfrom(paths: list[Path]) -> str:
    """SHFileOperation'ın beklediği biçim: 'yol1\0yol2\0\0' (mutlak yollar)."""
    return "\0".join(str(Path(p).resolve()) for p in paths) + "\0\0"


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _pack_ = 1 if ctypes.sizeof(ctypes.c_void_p) == 4 else 0
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]


def move_to_trash(paths: list[Path]) -> list[Path]:
    """Dosyaları Geri Dönüşüm Kutusu'na taşır; gerçekten kaybolanların listesini döndürür.

    Windows dışında desteklenmez (NotImplementedError). Sonuç, dönüş koduna değil dosyaların
    gerçekten yok olup olmadığına bakılarak belirlenir; böylece kısmi başarı doğru raporlanır.
    """
    if sys.platform != "win32":
        raise NotImplementedError("Geri Dönüşüm Kutusu yalnızca Windows'ta desteklenir.")
    paths = [Path(p) for p in paths]
    if not paths:
        return []
    buffer = ctypes.create_unicode_buffer(build_pfrom(paths))
    op = _SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = ctypes.cast(buffer, wintypes.LPCWSTR)
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT | FOF_WANTNUKEWARNING
    ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return [p for p in paths if not p.exists()]
