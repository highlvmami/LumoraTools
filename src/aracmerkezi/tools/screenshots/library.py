"""Ekran görüntüleri kütüphanesi: listeleme, arama, tarihe göre düzenleme planı, notlar (Tk'den bağımsız)."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from duzenle import engine

from ...textutil import fold

IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
FORMATS = {"Yıl / Ay": "%Y/%m", "Yıl / Ay / Gün": "%Y/%m/%d"}
MAX_SHOTS = 20_000


@dataclass(frozen=True)
class Shot:
    path: Path
    size: int
    mtime: float

    @property
    def key(self) -> str:
        """Not anahtarı: dosya taşınınca da aynı kalır (ad + boyut + değiştirilme saniyesi)."""
        return f"{self.path.name}|{self.size}|{int(self.mtime)}"


def default_folder() -> Path:
    """Windows'un ekran görüntülerini koyduğu klasör; bulunamazsa Resimler, o da yoksa ev klasörü."""
    home = Path.home()
    for rel in ("Pictures/Screenshots", "OneDrive/Pictures/Screenshots", "OneDrive/Resimler/Ekran Görüntüleri",
                "Pictures/Ekran Görüntüleri", "Resimler/Ekran Görüntüleri", "Pictures", "OneDrive/Pictures"):
        if (home / rel).is_dir():
            return home / rel
    return home


def list_shots(folder: Path, limit: int = MAX_SHOTS) -> list[Shot]:
    """Klasördeki (alt klasörler dahil) görüntüleri en yeniden eskiye döndürür."""
    shots: list[Shot] = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.startswith(".") or Path(name).suffix.lower() not in IMG_EXTS:
                continue
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue
            shots.append(Shot(p, st.st_size, st.st_mtime))
    shots.sort(key=lambda s: -s.mtime)
    return shots[:limit]


def _matches(shot: Shot, needle: str, note: str, root: Path) -> bool:
    when = datetime.fromtimestamp(shot.mtime)
    try:
        rel_dir = str(shot.path.parent.relative_to(root))
    except ValueError:
        rel_dir = str(shot.path.parent)
    haystack = " ".join([fold(shot.path.name), fold(note), fold(rel_dir),
                         when.strftime("%d.%m.%Y"), when.strftime("%Y-%m-%d")])
    return needle in haystack


def filter_shots(shots: list[Shot], query: str, notes: dict[str, str], root: Path,
                 since: float | None = None, until: float | None = None) -> list[Shot]:
    """Ad, not, klasör (ör. 2026\\10) ve tarih metnine (11.10.2026 / 2026-10-11) göre süzer."""
    needle = fold(query.strip())
    out = []
    for s in shots:
        if since is not None and s.mtime < since:
            continue
        if until is not None and s.mtime >= until:
            continue
        if needle and not _matches(s, needle, notes.get(s.key, ""), root):
            continue
        out.append(s)
    return out


def plan_organize(folder: Path, date_format: str = "%Y/%m") -> list[engine.Move]:
    """Klasörün kökündeki görüntüleri tarihe göre alt klasörlere taşıma planı.

    Yalnızca doğrudan klasördeki görüntüler alınır; zaten düzenlenmiş alt klasörlere ve
    görüntü olmayan dosyalara dokunulmaz.
    """
    only = {p for p in engine.scan(folder) if p.suffix.lower() in IMG_EXTS}
    return engine.plan(folder, "tarih", date_format, only=only)


class NoteStore:
    def __init__(self, path: Path | str) -> None:
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS notes (key TEXT PRIMARY KEY, note TEXT NOT NULL)")
        self.db.commit()

    def all(self) -> dict[str, str]:
        return dict(self.db.execute("SELECT key, note FROM notes"))

    def set(self, key: str, note: str) -> None:
        note = note.strip()
        if note:
            self.db.execute("INSERT INTO notes(key, note) VALUES(?, ?) "
                            "ON CONFLICT(key) DO UPDATE SET note = excluded.note", (key, note))
        else:
            self.db.execute("DELETE FROM notes WHERE key = ?", (key,))
        self.db.commit()

    def close(self) -> None:
        self.db.close()
