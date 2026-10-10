"""Klasör boyut analizi: diskte yeri en çok kimin kapladığını bulur (Tk'den bağımsız).

Tek geçişte tüm ağacı gezer, her klasör için toplam boyutu ve dosya sayısını hesaplar.
Bellek için her klasörde yalnızca en büyük `TOP_FILES_PER_DIR` dosya adı tutulur; ayrıca
tüm ağaç boyunca en büyük `top_files` dosya ayrıca tutulur. Sembolik bağlantılar ve
Windows birleşim noktaları (junction) izlenmez, böylece döngüye girilmez.
"""
from __future__ import annotations

import heapq
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

TOP_FILES_PER_DIR = 30

Progress = Callable[[int, str], None]  # (taranan dosya sayısı, geçerli klasör)


@dataclass
class DirNode:
    path: Path
    name: str
    size: int = 0                 # alt klasörler dahil toplam boyut
    file_count: int = 0           # alt klasörler dahil toplam dosya sayısı
    own_size: int = 0             # yalnızca bu klasörün doğrudan dosyaları
    other_files: int = 0          # `files` listesine sığmayan dosya sayısı
    dirs: list["DirNode"] = field(default_factory=list)     # boyuta göre azalan
    files: list[tuple[str, int]] = field(default_factory=list)  # boyuta göre azalan


@dataclass
class ScanResult:
    root: DirNode
    largest: list[tuple[Path, int]]   # tüm ağaçtaki en büyük dosyalar, azalan
    errors: int                       # okunamayan (izin yok vb.) girdi sayısı
    stopped: bool


class _Context:
    def __init__(self, stop: threading.Event | None, progress: Progress | None, top_files: int) -> None:
        self.stop = stop
        self.progress = progress
        self.top_files = top_files
        self.heap: list[tuple[int, str]] = []   # en küçüğü tepede (min-heap)
        self.files = 0
        self.errors = 0
        self.stopped = False

    def note_file(self, directory: Path, name: str, size: int) -> None:
        self.files += 1
        item = (size, str(directory / name))
        if len(self.heap) < self.top_files:
            heapq.heappush(self.heap, item)
        elif size > self.heap[0][0]:
            heapq.heapreplace(self.heap, item)
        if self.progress and self.files % 1000 == 0:
            self.progress(self.files, str(directory))


def _is_link(entry: os.DirEntry) -> bool:
    if entry.is_symlink():
        return True
    junction = getattr(entry, "is_junction", None)  # Python 3.12+
    return bool(junction and junction())


def _scan_dir(path: Path, ctx: _Context) -> DirNode:
    node = DirNode(path, path.name or str(path))
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError:
        ctx.errors += 1
        return node
    files: list[tuple[str, int]] = []
    for entry in entries:
        if ctx.stop is not None and ctx.stop.is_set():
            ctx.stopped = True
            break
        try:
            if _is_link(entry):
                continue
            if entry.is_dir(follow_symlinks=False):
                child = _scan_dir(Path(entry.path), ctx)
                node.dirs.append(child)
                node.size += child.size
                node.file_count += child.file_count
            elif entry.is_file(follow_symlinks=False):
                size = entry.stat(follow_symlinks=False).st_size
                files.append((entry.name, size))
                node.own_size += size
                node.size += size
                node.file_count += 1
                ctx.note_file(path, entry.name, size)
        except OSError:
            ctx.errors += 1
    files.sort(key=lambda f: -f[1])
    node.files = files[:TOP_FILES_PER_DIR]
    node.other_files = len(files) - len(node.files)
    node.dirs.sort(key=lambda d: -d.size)
    return node


def scan(root: Path, stop: threading.Event | None = None, progress: Progress | None = None,
         top_files: int = 100) -> ScanResult:
    ctx = _Context(stop, progress, top_files)
    node = _scan_dir(Path(root), ctx)
    largest = [(Path(p), s) for s, p in sorted(ctx.heap, reverse=True)]
    if progress:
        progress(ctx.files, "")
    return ScanResult(node, largest, ctx.errors, ctx.stopped)


def rows(node: DirNode, limit: int = 60) -> tuple[list[tuple[str, str, int, DirNode | None]], int, int]:
    """Bir klasörün içeriğini boyuta göre sıralı satırlara çevirir.

    Satır: (tür 'dir'|'file', ad, boyut, alt klasör düğümü ya da None). Sınırı aşan kısım için
    (kalan öğe sayısı, kalan boyut) ayrıca döndürülür; ayrıca listeye sığmayan dosyalar
    `other_files` ile birlikte kalana eklenir.
    """
    items: list[tuple[str, str, int, DirNode | None]] = [("dir", d.name, d.size, d) for d in node.dirs]
    items += [("file", name, size, None) for name, size in node.files]
    items.sort(key=lambda r: -r[2])
    shown, rest = items[:limit], items[limit:]
    kept_files_size = sum(size for _, size in node.files)
    rest_count = len(rest) + node.other_files
    rest_size = sum(r[2] for r in rest) + (node.own_size - kept_files_size)
    return shown, rest_count, rest_size
