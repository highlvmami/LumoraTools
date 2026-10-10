"""Dosya sistemi yardımcıları."""
from __future__ import annotations

import os


def is_link(entry: os.DirEntry) -> bool:
    """Sembolik bağlantı ya da Windows birleşim noktası (junction) mı? Bunlar izlenmez: döngüye girmemek ve
    (temizlikte) bağlantının işaret ettiği başka bir klasörün içini silmemek için."""
    if entry.is_symlink():
        return True
    junction = getattr(entry, "is_junction", None)  # Python 3.12+
    return bool(junction and junction())
