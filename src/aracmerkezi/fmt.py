"""Biçimlendirme yardımcıları."""
from __future__ import annotations


def human_size(n: int | float) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def duration(seconds: int | float) -> str:
    """Süreyi okunur yazar: 45 sn, 12 dk, 3 sa 05 dk, 2 gün 4 sa."""
    s = int(max(0, seconds))
    days, rem = divmod(s, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days} gün {hours} sa"
    if hours:
        return f"{hours} sa {minutes:02d} dk"
    if minutes:
        return f"{minutes} dk"
    return f"{secs} sn"
