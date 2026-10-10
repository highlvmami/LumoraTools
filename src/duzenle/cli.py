from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from . import engine
from .config import DEFAULT_DATE_FORMAT, MODES


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="duzenle", description="Klasörü uzantıya veya tarihe göre düzenler.")
    p.add_argument("klasor", type=Path, help="Düzenlenecek klasör")
    p.add_argument("--mod", choices=MODES, default="uzanti", help="Gruplama biçimi (varsayılan: uzanti)")
    p.add_argument("--tarih-format", default=DEFAULT_DATE_FORMAT,
                   help=f"Tarih klasör biçimi (varsayılan: {DEFAULT_DATE_FORMAT.replace('%', '%%')})")
    p.add_argument("--alt-klasorler", action="store_true", help="Alt klasörlerdeki dosyaları da işle")
    p.add_argument("--dry-run", action="store_true", help="Taşımadan yalnızca planı göster")
    p.add_argument("--geri-al", action="store_true", help="Son işlemi geri al")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    folder: Path = args.klasor
    if not folder.is_dir():
        print(f"Hata: klasör bulunamadı: {folder}", file=sys.stderr)
        return 2

    if args.geri_al:
        restored, skipped = engine.undo(folder)
        print(f"{restored} dosya geri alındı, {skipped} atlandı.")
        return 0

    moves = engine.plan(folder, args.mod, args.tarih_format, args.alt_klasorler)
    if not moves:
        print("Düzenlenecek dosya yok.")
        return 0

    root = folder.resolve()
    summary = Counter(m.dst.parent.relative_to(root) for m in moves)
    for target, count in sorted(summary.items()):
        print(f"  {str(target):<30} {count} dosya")

    if args.dry_run:
        for m in moves:
            print(f"  {m.src.name}  ->  {m.dst.relative_to(root)}")
        print(f"\n[dry-run] {len(moves)} dosya taşınacaktı, hiçbir şey değişmedi.")
        return 0

    done, failed = engine.apply(folder, moves)
    print(f"\n{len(done)} dosya taşındı.")
    for m, err in failed:
        print(f"  ATLANDI {m.src.name}: {err}", file=sys.stderr)
    return 1 if failed else 0
