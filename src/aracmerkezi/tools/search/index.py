"""Yerel arama dizini: SQLite FTS5 ile dosya içeriği araması. Tk'den bağımsızdır.

Şema:
  files(id, path, mtime, size)   -> hangi dosya hangi sürümde dizinlendi
  docs  (FTS5, rowid = files.id) -> norm: aranan (Türkçe harfleri katlanmış) metin,
                                    body: özgün metin (özet gösterimi için, aranmaz)
Değişmemiş dosyalar (mtime+boyut aynı) yeniden okunmaz; silinenler dizinden düşer.
"""
from __future__ import annotations

import html
import os
import re
import sqlite3
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ...textutil import fold

TEXT_EXTS = {
    ".txt", ".md", ".rst", ".log", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css", ".sql", ".sh", ".bat", ".ps1",
    ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".php", ".rb", ".kt", ".swift", ".tex",
}
DOC_EXTS = {".docx", ".pdf"}
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env", "site-packages", "dist", "build",
    "$recycle.bin", "system volume information", "appdata", "windows", "program files", "program files (x86)",
}
MAX_FILE_BYTES = 5_000_000   # bundan büyük dosyalar atlanır
MAX_CHARS = 200_000          # dosya başına en fazla bu kadar karakter dizinlenir
PDF_MAX_PAGES = 100

Progress = Callable[[int, int, str], None]  # (taranan, dizinlenen, geçerli yol)


@dataclass(frozen=True)
class Hit:
    path: str
    snippet: str
    spans: list[tuple[int, int]]  # snippet içindeki vurgulanacak aralıklar


def _read_text(path: Path) -> str | None:
    with open(path, "rb") as f:
        raw = f.read(MAX_CHARS * 4)
    if b"\x00" in raw[:4096]:
        return None  # ikili dosya
    try:
        return raw.decode("utf-8-sig")[:MAX_CHARS]
    except UnicodeDecodeError:
        return raw.decode("cp1254", errors="replace")[:MAX_CHARS]


def _read_docx(path: Path) -> str | None:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))[:MAX_CHARS]


def _read_pdf(path: Path) -> str | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        return None
    parts, size = [], 0
    for page in reader.pages[:PDF_MAX_PAGES]:
        text = page.extract_text() or ""
        parts.append(text)
        size += len(text)
        if size >= MAX_CHARS:
            break
    return "\n".join(parts)[:MAX_CHARS]


def extract_text(path: Path) -> str | None:
    """Dosyadan düz metin çıkarır; desteklenmiyor/okunamıyorsa None."""
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXTS:
            return _read_text(path)
        if ext == ".docx":
            return _read_docx(path)
        if ext == ".pdf":
            return _read_pdf(path)
    except Exception:  # bozuk/kilitli/şifreli dosya dizini durdurmamalı
        return None
    return None


def make_match(query: str) -> tuple[str, list[str]]:
    """Kullanıcı sorgusundan güvenli FTS5 ifadesi üretir (her kelime ön ek, hepsi AND)."""
    tokens = re.findall(r"\w+", fold(query))
    return " ".join(f'"{t}"*' for t in tokens), tokens


def make_snippet(body: str, tokens: list[str], width: int = 200) -> tuple[str, list[tuple[int, int]]]:
    """İlk eşleşmenin çevresinden özet ve vurgu aralıkları döndürür."""
    norm = fold(body)  # 1'e 1 dönüşüm: konumlar özgün metinle aynı
    pattern = re.compile("|".join(r"(?<!\w)" + re.escape(t) + r"\w*" for t in tokens)) if tokens else None
    first = pattern.search(norm) if pattern else None
    start = max(0, (first.start() if first else 0) - width // 3)
    end = min(len(body), start + width)
    text = body[start:end]
    prefix = "…" if start > 0 else ""
    spans = []
    if pattern:
        for m in pattern.finditer(norm, start, end):
            spans.append((m.start() - start + len(prefix), min(m.end(), end) - start + len(prefix)))
    clean = prefix + text + ("…" if end < len(body) else "")
    # satır sonlarını boşluğa çevir (uzunluk korunur, aralıklar bozulmaz)
    clean = clean.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return clean, spans


class Index:
    def __init__(self, path: Path | str) -> None:
        self.db = sqlite3.connect(str(path), timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS files ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL UNIQUE, mtime REAL, size INTEGER)")
        self.db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5("
            " norm, body UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
        self.db.commit()

    # ---------- dizinleme ----------
    def _walk(self, root: Path):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in SKIP_DIRS]
            for name in filenames:
                p = Path(dirpath) / name
                if p.suffix.lower() in TEXT_EXTS or p.suffix.lower() in DOC_EXTS:
                    yield p

    def index_roots(self, roots: list[Path | str], progress: Progress | None = None,
                    stop: threading.Event | None = None) -> dict[str, int]:
        stats = {"scanned": 0, "indexed": 0, "removed": 0, "skipped": 0}
        for root in map(Path, roots):
            seen: set[str] = set()
            completed = True
            for p in self._walk(root):
                if stop and stop.is_set():
                    completed = False
                    break
                stats["scanned"] += 1
                key = str(p)
                seen.add(key)
                try:
                    st = p.stat()
                except OSError:
                    stats["skipped"] += 1
                    continue
                if st.st_size > MAX_FILE_BYTES:
                    stats["skipped"] += 1
                    continue
                row = self.db.execute("SELECT id, mtime, size FROM files WHERE path = ?", (key,)).fetchone()
                if row and row[1] == st.st_mtime and row[2] == st.st_size:
                    continue
                text = extract_text(p)
                self._upsert(row[0] if row else None, key, st.st_mtime, st.st_size, text)
                stats["indexed"] += 1
                if stats["scanned"] % 25 == 0:
                    self.db.commit()
                    if progress:
                        progress(stats["scanned"], stats["indexed"], key)
            if completed:
                stats["removed"] += self._remove_missing(root, seen)
            self.db.commit()
        if progress:
            progress(stats["scanned"], stats["indexed"], "")
        return stats

    def _upsert(self, file_id: int | None, path: str, mtime: float, size: int, text: str | None) -> None:
        if file_id is None:
            file_id = self.db.execute(
                "INSERT INTO files(path, mtime, size) VALUES(?, ?, ?)", (path, mtime, size)).lastrowid
        else:
            self.db.execute("UPDATE files SET mtime = ?, size = ? WHERE id = ?", (mtime, size, file_id))
            self.db.execute("DELETE FROM docs WHERE rowid = ?", (file_id,))
        if text and text.strip():
            self.db.execute("INSERT INTO docs(rowid, norm, body) VALUES(?, ?, ?)", (file_id, fold(text), text))

    def _remove_missing(self, root: Path, seen: set[str]) -> int:
        prefix = str(root).rstrip("\\/") + os.sep
        gone = [(i, p) for i, p in self.db.execute("SELECT id, path FROM files") if p.startswith(prefix) and p not in seen]
        for file_id, _ in gone:
            self.db.execute("DELETE FROM docs WHERE rowid = ?", (file_id,))
            self.db.execute("DELETE FROM files WHERE id = ?", (file_id,))
        return len(gone)

    def clear(self) -> None:
        self.db.execute("DELETE FROM docs")
        self.db.execute("DELETE FROM files")
        self.db.commit()

    # ---------- arama ----------
    def search(self, query: str, limit: int = 100) -> list[Hit]:
        match, tokens = make_match(query)
        if not match:
            return []
        rows = self.db.execute(
            "SELECT files.path, docs.body FROM docs JOIN files ON files.id = docs.rowid "
            "WHERE docs MATCH ? ORDER BY bm25(docs) LIMIT ?", (match, limit)).fetchall()
        hits = []
        for path, body in rows:
            snippet, spans = make_snippet(body, tokens)
            hits.append(Hit(path, snippet, spans))
        return hits

    def stats(self) -> dict[str, int]:
        files = self.db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        docs = self.db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        return {"files": files, "searchable": docs}

    def close(self) -> None:
        self.db.close()
