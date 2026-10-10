"""Klasör yapısını olduğu gibi listeleme (Tk'den bağımsız, test edilebilir).

`list_entries` bir klasörü alt klasörleriyle okur, `build_tree` bunu filtreleyip iç içe bir
ağaca çevirir: önce klasörler, sonra dosyalar; her klasörde dosya sayısı ve toplam boyut.
Gizli (.ile başlayan) dosya ve klasörler atlanır.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .textutil import fold

MAX_FILES = 50_000


@dataclass(frozen=True)
class Entry:
    path: Path
    size: int
    mtime: float


@dataclass
class Node:
    name: str
    path: Path
    is_dir: bool
    size: int = 0
    mtime: float = 0.0
    children: list["Node"] = field(default_factory=list)
    file_count: int = 0


def list_entries(root: Path, limit: int = MAX_FILES) -> tuple[list[Entry], list[Path], bool]:
    """(dosyalar, klasörler, kesildi mi). `limit` dosyaya ulaşınca durur."""
    files: list[Entry] = []
    dirs: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        dirs.extend(Path(dirpath) / d for d in dirnames)
        for name in filenames:
            if name.startswith("."):
                continue
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue
            files.append(Entry(p, st.st_size, st.st_mtime))
            if len(files) >= limit:
                return files, dirs, True
    return files, dirs, False


def build_tree(root: Path, files: list[Entry], dirs: list[Path], query: str = "") -> Node:
    needle = fold(query.strip())
    top = Node(root.name or str(root), root, True)
    index: dict[Path, Node] = {root: top}

    def ensure_dir(p: Path) -> Node:
        node = index.get(p)
        if node is None:
            parent = ensure_dir(p.parent)
            node = Node(p.name, p, True)
            parent.children.append(node)
            index[p] = node
        return node

    if not needle:
        for d in dirs:  # boş klasörler de görünsün
            ensure_dir(d)
    for f in files:
        parts = f.path.relative_to(root).parts
        if needle and not (needle in fold(parts[-1]) or any(needle in fold(p) for p in parts[:-1])):
            continue
        ensure_dir(f.path.parent).children.append(Node(f.path.name, f.path, False, f.size, f.mtime))

    def finish(node: Node) -> None:
        for child in node.children:
            if child.is_dir:
                finish(child)
        node.children.sort(key=lambda c: (not c.is_dir, fold(c.name)))
        node.file_count = sum(c.file_count if c.is_dir else 1 for c in node.children)
        node.size = sum(c.size for c in node.children)

    finish(top)
    return top
