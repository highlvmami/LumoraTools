"""Tarih filtresi (pano geçmişi, ekran görüntüleri) (Tk'den bağımsız, test edilebilir)."""
from __future__ import annotations

from datetime import datetime, timedelta

PRESETS = ["Tümü", "Bugün", "Dün", "Son 7 gün", "Son 30 gün", "Aralık…"]
CUSTOM = "Aralık…"

_FORMATS = ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


def _midnight(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def preset_range(name: str, now: datetime | None = None) -> tuple[float | None, float | None]:
    """Hazır filtrenin (başlangıç, bitiş) zaman damgaları. Bitiş dahil değildir; None = sınırsız."""
    now = now or datetime.now()
    today = _midnight(now)
    if name == "Bugün":
        return today.timestamp(), None
    if name == "Dün":
        return (today - timedelta(days=1)).timestamp(), today.timestamp()
    if name == "Son 7 gün":       # bugün dahil 7 takvim günü
        return (today - timedelta(days=6)).timestamp(), None
    if name == "Son 30 gün":
        return (today - timedelta(days=29)).timestamp(), None
    return None, None


def parse_date(text: str) -> datetime | None:
    """GG.AA.YYYY, GG/AA/YYYY, YYYY-AA-GG veya GG-AA-YYYY. Boşsa None; geçersizse ValueError."""
    text = text.strip()
    if not text:
        return None
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Geçersiz tarih: {text!r} (örnek: 25.12.2026)")


def custom_range(start_text: str, end_text: str) -> tuple[float | None, float | None]:
    """Kullanıcının yazdığı iki tarih arası. Bitiş günü dahildir; ikisi de boşsa sınırsız."""
    start, end = parse_date(start_text), parse_date(end_text)
    if start and end and start > end:
        raise ValueError("Başlangıç tarihi bitişten sonra olamaz.")
    since = _midnight(start).timestamp() if start else None
    until = (_midnight(end) + timedelta(days=1)).timestamp() if end else None
    return since, until
