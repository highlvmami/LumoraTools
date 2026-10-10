"""Pano geçmişi deposu (SQLite). Tk'den bağımsızdır, tek başına test edilebilir.

Üç tür kayıt vardır:
  text  : metnin kendisi (`text`)
  image : görüntü PNG olarak `images_dir` altında durur; `text` içeriğin özetidir (SHA-1), `ref` ölçü bilgisidir
  files : kopyalanan dosya yolları (satır satır `text`); dosyaların kendisi kopyalanmaz, yalnızca yolları tutulur
"""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from ...textutil import fold

MAX_LEN = 100_000          # bundan uzun metinler kaydedilmez
MAX_KEEP = 3000            # sabitlenmemiş en fazla bu kadar metin/dosya kaydı tutulur
MAX_IMAGES = 200           # sabitlenmemiş en fazla bu kadar görüntü tutulur (disk dolmasın)
MAX_IMAGE_BYTES = 15_000_000
MAX_PIXELS = 40_000_000
MAX_FILES_PER_CLIP = 500

TEXT, IMAGE, FILES = "text", "image", "files"


def _human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


@dataclass(frozen=True)
class Clip:
    id: int
    text: str
    ts: float
    pinned: bool
    kind: str = TEXT
    ref: str | None = None

    @property
    def meta(self) -> dict:
        try:
            return json.loads(self.ref) if self.ref else {}
        except ValueError:
            return {}

    @property
    def paths(self) -> list[str]:
        return self.text.split("\n") if self.kind == FILES else []

    @property
    def label(self) -> str:
        """Listede görünen tek satırlık özet."""
        if self.kind == IMAGE:
            m = self.meta
            return f"🖼  Görüntü {m.get('w', '?')}×{m.get('h', '?')}  ({_human(m.get('bytes', 0))})"
        if self.kind == FILES:
            names = [Path(p).name or p for p in self.paths]
            shown = ", ".join(names[:3]) + (f" (+{len(names) - 3})" if len(names) > 3 else "")
            return f"📎  {len(names)} dosya: {shown}"
        flat = " ".join(self.text.split())
        return flat if len(flat) <= 140 else flat[:140] + "…"

    @property
    def search_text(self) -> str:
        """Aramanın baktığı metin: metin/dosya yolları; görüntüler 'görüntü', 'resim' ve ölçüyle bulunur."""
        if self.kind == IMAGE:
            m = self.meta
            return f"görüntü resim image {m.get('w', '')}x{m.get('h', '')}"
        return self.text


class ClipStore:
    def __init__(self, path: Path | str, images_dir: Path | str | None = None) -> None:
        path = Path(path)
        self.images_dir = Path(images_dir) if images_dir else path.parent / "clipboard_images"
        self.db = sqlite3.connect(str(path))
        self._migrate()

    # ---------- şema ----------
    def _migrate(self) -> None:
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(clips)")]
        if cols and "kind" not in cols:      # eski (yalnızca metin) veritabanı: veriyi koruyarak yeni şemaya taşı
            self.db.execute("ALTER TABLE clips RENAME TO clips_old")
            cols = []
        if not cols:
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS clips ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " kind TEXT NOT NULL DEFAULT 'text',"
                " text TEXT NOT NULL,"
                " ref TEXT,"
                " ts REAL NOT NULL,"
                " pinned INTEGER NOT NULL DEFAULT 0,"
                " UNIQUE(kind, text))")
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name = 'clips_old'").fetchone():
            self.db.execute("INSERT INTO clips(id, kind, text, ts, pinned) "
                            "SELECT id, 'text', text, ts, pinned FROM clips_old")
            self.db.execute("DROP TABLE clips_old")
        self.db.commit()

    # ---------- ekleme ----------
    def _upsert(self, kind: str, text: str, ref: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO clips(kind, text, ref, ts) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(kind, text) DO UPDATE SET ts = excluded.ts",
            (kind, text, ref, time.time()))
        self._prune()
        self.db.commit()

    def add(self, text: str) -> bool:
        """Metni kaydeder; zaten varsa en üste taşır. Kaydedildiyse True."""
        if not text or not text.strip() or len(text) > MAX_LEN:
            return False
        self._upsert(TEXT, text)
        return True

    def add_files(self, paths: list[str]) -> bool:
        paths = [str(p) for p in paths if str(p).strip()]
        if not paths or len(paths) > MAX_FILES_PER_CLIP:
            return False
        self._upsert(FILES, "\n".join(paths))
        return True

    def add_image(self, image) -> bool:
        """Pillow görüntüsünü PNG olarak saklar. Çok büyükse ya da zaten varsa (aynı içerik) yeni dosya yazılmaz."""
        try:
            w, h = image.size
            if w * h > MAX_PIXELS:
                return False
            if image.mode not in ("RGB", "RGBA", "L", "LA"):
                image = image.convert("RGBA")
            buf = io.BytesIO()
            image.save(buf, "PNG")
        except Exception:
            return False
        data = buf.getvalue()
        if len(data) > MAX_IMAGE_BYTES:
            return False
        digest = hashlib.sha1(data).hexdigest()[:20]
        self.images_dir.mkdir(parents=True, exist_ok=True)
        file = self.images_dir / f"{digest}.png"
        if not file.exists():
            file.write_bytes(data)
        self._upsert(IMAGE, digest, json.dumps({"file": file.name, "w": w, "h": h, "bytes": len(data)}))
        return True

    def image_path(self, clip: Clip) -> Path | None:
        name = clip.meta.get("file") if clip.kind == IMAGE else None
        if not name or Path(name).name != name:        # yalnızca images_dir içindeki düz dosya adı
            return None
        path = self.images_dir / name
        return path if path.exists() else None

    # ---------- temizlik ----------
    def _unlink_images(self, refs: list[str | None]) -> None:
        for ref in refs:
            try:
                name = json.loads(ref or "{}").get("file")
            except ValueError:
                continue
            if name and Path(name).name == name:
                (self.images_dir / name).unlink(missing_ok=True)

    def _prune(self) -> None:
        """Sabitlenmemiş kayıtlar sınırı aşınca en eskiler silinir (görüntü dosyalarıyla birlikte)."""
        for kinds, limit in (((TEXT, FILES), MAX_KEEP), ((IMAGE,), MAX_IMAGES)):
            marks = ",".join("?" * len(kinds))
            old = self.db.execute(
                f"SELECT id, kind, ref FROM clips WHERE pinned = 0 AND kind IN ({marks}) "
                f"ORDER BY ts DESC LIMIT -1 OFFSET ?", (*kinds, limit)).fetchall()
            if old:
                self.db.executemany("DELETE FROM clips WHERE id = ?", [(r[0],) for r in old])
                self._unlink_images([r[2] for r in old if r[1] == IMAGE])

    # ---------- okuma ----------
    def list(self, query: str = "", limit: int = 500, since: float | None = None,
             until: float | None = None) -> list[Clip]:
        """Sabitlenenler önce, sonra en yeniden eskiye. Türkçe harf duyarsız arama.

        `since` (dahil) ve `until` (dahil değil) zaman damgalarıyla tarihe göre daraltır.
        """
        needle = fold(query.strip())
        out: list[Clip] = []
        for id_, kind, text, ref, ts, pinned in self.db.execute(
                "SELECT id, kind, text, ref, ts, pinned FROM clips "
                "WHERE (?1 IS NULL OR ts >= ?1) AND (?2 IS NULL OR ts < ?2) "
                "ORDER BY pinned DESC, ts DESC", (since, until)):
            clip = Clip(id_, text, ts, bool(pinned), kind, ref)
            if needle and needle not in fold(clip.search_text):
                continue
            out.append(clip)
            if len(out) >= limit:
                break
        return out

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM clips").fetchone()[0]

    # ---------- değiştirme ----------
    def set_pinned(self, clip_id: int, pinned: bool) -> None:
        self.db.execute("UPDATE clips SET pinned = ? WHERE id = ?", (int(pinned), clip_id))
        self.db.commit()

    def delete(self, clip_id: int) -> None:
        row = self.db.execute("SELECT kind, ref FROM clips WHERE id = ?", (clip_id,)).fetchone()
        self.db.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
        self.db.commit()
        if row and row[0] == IMAGE:
            self._unlink_images([row[1]])

    def clear_unpinned(self) -> int:
        refs = [r[0] for r in self.db.execute("SELECT ref FROM clips WHERE pinned = 0 AND kind = 'image'")]
        n = self.db.execute("DELETE FROM clips WHERE pinned = 0").rowcount
        self.db.commit()
        self._unlink_images(refs)
        return n

    def close(self) -> None:
        self.db.close()
