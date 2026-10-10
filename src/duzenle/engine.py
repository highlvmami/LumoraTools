"""Düzenleme motoru: tara -> planla -> uygula -> geri al.

Dosyalar asla silinmez, yalnızca taşınır. Her uygulama bir günlüğe yazılır.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import (
    DEFAULT_DATE_FORMAT,
    LOG_NAME,
    MODES,
    PARTIAL_EXTENSIONS,
    category_for,
)


@dataclass(frozen=True)
class Move:
    src: Path
    dst: Path


SYSTEM_FILES = {"desktop.ini", "thumbs.db"}   # Windows'un klasör görünümü için kullandığı dosyalar
_HIDDEN_OR_SYSTEM = 0x2 | 0x4                  # FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM


def _is_system(p: Path) -> bool:
    if p.name.lower() in SYSTEM_FILES:
        return True
    try:
        return bool(getattr(p.stat(), "st_file_attributes", 0) & _HIDDEN_OR_SYSTEM)
    except OSError:
        return True  # okunamayan dosyaya dokunma


def scan(folder: Path, recursive: bool = False) -> list[Path]:
    """Taşınabilir dosyaları döndürür (gizli/sistem, kısmi ve günlük dosyası hariç)."""
    it = folder.rglob("*") if recursive else folder.iterdir()
    files = []
    for p in it:
        if not p.is_file() or p.name.startswith(".") or p.name == LOG_NAME:
            continue
        if p.suffix.lower() in PARTIAL_EXTENSIONS or _is_system(p):
            continue
        files.append(p)
    return sorted(files)


def _target_dir(root: Path, file: Path, mode: str, date_format: str) -> Path:
    if mode not in MODES:
        raise ValueError(f"Geçersiz mod: {mode!r} (seçenekler: {', '.join(MODES)})")
    parts: list[str] = []
    if mode in ("uzanti", "birlesik"):
        parts.append(category_for(file.suffix))
    if mode in ("tarih", "birlesik"):
        stamp = datetime.fromtimestamp(file.stat().st_mtime)
        parts.append(stamp.strftime(date_format))
    return root.joinpath(*parts)


def _unique(dst: Path, taken: set[Path]) -> Path:
    candidate, n = dst, 1
    while candidate.exists() or candidate in taken:
        candidate = dst.with_name(f"{dst.stem} ({n}){dst.suffix}")
        n += 1
    return candidate


def plan(
    folder: Path,
    mode: str = "uzanti",
    date_format: str = DEFAULT_DATE_FORMAT,
    recursive: bool = False,
    only: set[Path] | None = None,
) -> list[Move]:
    """Dosyaya dokunmadan taşıma planını üretir (dry-run).

    `only` verilirse yalnızca bu dosyalar planlanır (izleme modu için).
    """
    folder = folder.resolve()
    moves: list[Move] = []
    taken: set[Path] = set()
    for f in scan(folder, recursive):
        if only is not None and f not in only:
            continue
        target = _target_dir(folder, f, mode, date_format)
        if f.parent == target:
            continue  # zaten yerinde
        dst = _unique(target / f.name, taken)
        taken.add(dst)
        moves.append(Move(f, dst))
    return moves


def apply(folder: Path, moves: list[Move]) -> tuple[list[Move], list[tuple[Move, str]]]:
    """Planı uygular. (başarılılar, hatalılar) döndürür ve günlüğe yazar."""
    done: list[Move] = []
    failed: list[tuple[Move, str]] = []
    for m in moves:
        try:
            m.dst.parent.mkdir(parents=True, exist_ok=True)
            final = _unique(m.dst, set()) if m.dst.exists() else m.dst
            shutil.move(str(m.src), str(final))
            done.append(Move(m.src, final))
        except OSError as e:  # kilitli dosya, izin hatası vb.
            failed.append((m, str(e)))
    if done:
        _append_log(folder.resolve(), done)
    return done, failed


def _log_path(folder: Path) -> Path:
    return folder / LOG_NAME


def _read_log(folder: Path) -> list[dict]:
    p = _log_path(folder)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _append_log(folder: Path, done: list[Move]) -> None:
    runs = _read_log(folder)
    runs.append({
        "time": datetime.now().isoformat(timespec="seconds"),
        "moves": [{"src": str(m.src), "dst": str(m.dst)} for m in done],
    })
    _log_path(folder).write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")


def undo(folder: Path) -> tuple[int, int]:
    """Son işlemi geri alır. (geri alınan, atlanan) döndürür."""
    folder = folder.resolve()
    runs = _read_log(folder)
    if not runs:
        return 0, 0
    last = runs.pop()
    restored = skipped = 0
    for mv in reversed(last["moves"]):
        src, dst = Path(mv["src"]), Path(mv["dst"])
        if not dst.exists() or src.exists():
            skipped += 1  # dosya taşınmış/silinmiş ya da eski yer dolu
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(src))
        restored += 1
        _prune_empty(dst.parent, folder)
    if runs:
        _log_path(folder).write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        _log_path(folder).unlink(missing_ok=True)
    return restored, skipped


def _prune_empty(directory: Path, stop: Path) -> None:
    """Geri almadan sonra boşalan kategori klasörlerini temizler."""
    while directory != stop and stop in directory.parents:
        try:
            directory.rmdir()  # yalnızca boşsa başarılı olur
        except OSError:
            break
        directory = directory.parent
