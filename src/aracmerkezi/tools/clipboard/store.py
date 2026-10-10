"""Pano geçmişi deposu (SQLite). Tk'den bağımsızdır, tek başına test edilebilir."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from ...textutil import fold

MAX_LEN = 100_000   # bundan uzun metinler kaydedilmez
MAX_KEEP = 3000     # sabitlenmemiş en fazla bu kadar kayıt tutulur


@dataclass(frozen=True)
class Clip:
    id: int
    text: str
    ts: float
    pinned: bool


class ClipStore:
    def __init__(self, path: Path | str) -> None:
        self.db = sqlite3.connect(str(path))
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS clips ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " text TEXT NOT NULL UNIQUE,"
            " ts REAL NOT NULL,"
            " pinned INTEGER NOT NULL DEFAULT 0)")
        self.db.commit()

    def add(self, text: str) -> bool:
        """Metni kaydeder; zaten varsa en üste taşır. Kaydedildiyse True."""
        if not text or not text.strip() or len(text) > MAX_LEN:
            return False
        self.db.execute(
            "INSERT INTO clips(text, ts) VALUES(?, ?) "
            "ON CONFLICT(text) DO UPDATE SET ts = excluded.ts",
            (text, time.time()))
        self.db.execute(
            "DELETE FROM clips WHERE pinned = 0 AND id NOT IN "
            "(SELECT id FROM clips WHERE pinned = 0 ORDER BY ts DESC LIMIT ?)", (MAX_KEEP,))
        self.db.commit()
        return True

    def list(self, query: str = "", limit: int = 500) -> list[Clip]:
        """Sabitlenenler önce, sonra en yeniden eskiye. Türkçe harf duyarsız arama."""
        needle = fold(query.strip())
        out: list[Clip] = []
        for id_, text, ts, pinned in self.db.execute(
                "SELECT id, text, ts, pinned FROM clips ORDER BY pinned DESC, ts DESC"):
            if needle and needle not in fold(text):
                continue
            out.append(Clip(id_, text, ts, bool(pinned)))
            if len(out) >= limit:
                break
        return out

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM clips").fetchone()[0]

    def set_pinned(self, clip_id: int, pinned: bool) -> None:
        self.db.execute("UPDATE clips SET pinned = ? WHERE id = ?", (int(pinned), clip_id))
        self.db.commit()

    def delete(self, clip_id: int) -> None:
        self.db.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
        self.db.commit()

    def clear_unpinned(self) -> int:
        n = self.db.execute("DELETE FROM clips WHERE pinned = 0").rowcount
        self.db.commit()
        return n

    def close(self) -> None:
        self.db.close()
