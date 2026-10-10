"""Windows panosundan görüntü ve dosya okuma / panoya görüntü ve dosya yazma.

Metin Tk üzerinden okunur (monitor.py); burası metin dışı içerik içindir. Windows dışında okuma
`None` döner, yazma `NotImplementedError` verir.
"""
from __future__ import annotations

import ctypes
import io
import struct
import sys
from ctypes import wintypes
from pathlib import Path

CF_DIB = 8
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002


def sequence_number() -> int | None:
    """Pano her değiştiğinde artan sayaç (ucuz değişiklik algılama). Windows dışında None."""
    if sys.platform != "win32":
        return None
    try:
        return int(ctypes.windll.user32.GetClipboardSequenceNumber())
    except Exception:
        return None


def read_non_text():
    """Panoda görüntü varsa ('image', PIL.Image), dosya varsa ('files', [yollar]); yoksa None."""
    try:
        from PIL import Image, ImageGrab
        data = ImageGrab.grabclipboard()
    except Exception:  # pano başka uygulamada kilitli, desteklenmeyen biçim vb.
        return None
    if isinstance(data, Image.Image):
        return "image", data
    if isinstance(data, (list, tuple)) and data:
        return "files", [str(p) for p in data]
    return None


# ---------- yazma ----------
def _kernel() -> tuple:
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    u32.OpenClipboard.argtypes = [wintypes.HWND]
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u32.SetClipboardData.restype = wintypes.HANDLE
    return k32, u32


def _set(fmt: int, payload: bytes) -> None:
    """Panoyu temizleyip tek bir biçimde `payload`'ı koyar."""
    if sys.platform != "win32":
        raise NotImplementedError("Panoya görüntü/dosya yazma yalnızca Windows'ta desteklenir.")
    k32, u32 = _kernel()
    handle = k32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
    if not handle:
        raise OSError("Bellek ayrılamadı.")
    ptr = k32.GlobalLock(handle)
    ctypes.memmove(ptr, payload, len(payload))
    k32.GlobalUnlock(handle)
    if not u32.OpenClipboard(None):
        k32.GlobalFree(handle)
        raise OSError("Pano başka bir uygulama tarafından kullanılıyor; biraz sonra tekrar dene.")
    try:
        u32.EmptyClipboard()
        if not u32.SetClipboardData(fmt, handle):
            k32.GlobalFree(handle)
            raise OSError("Pano verisi ayarlanamadı.")
        # SetClipboardData başarılıysa belleğin sahibi artık sistemdir; serbest bırakılmaz.
    finally:
        u32.CloseClipboard()


def dib_bytes(image) -> bytes:
    """Görüntüyü CF_DIB biçimine çevirir (BMP dosyasından 14 baytlık dosya başlığı atılır). Saydamlık düşer."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "BMP")
    return buf.getvalue()[14:]


def dropfiles_bytes(paths: list[str | Path]) -> bytes:
    """CF_HDROP: DROPFILES başlığı + çift boş sonlandırmalı geniş karakterli yol listesi."""
    names = "\0".join(str(Path(p).resolve()) for p in paths) + "\0\0"
    header = struct.pack("<IiiII", 20, 0, 0, 0, 1)         # pFiles=20, pt=(0,0), fNC=0, fWide=1
    return header + names.encode("utf-16-le")


def set_image(image) -> None:
    _set(CF_DIB, dib_bytes(image))


def set_files(paths: list[str | Path]) -> None:
    _set(CF_HDROP, dropfiles_bytes(paths))
