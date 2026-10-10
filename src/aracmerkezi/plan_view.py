"""Dosya Düzenleyici önizlemesinin seçim modeli (Tk'den bağımsız, test edilebilir).

Plandaki her dosya bir `Item`'dır ve hedef klasörüne göre gruplanır. Seçim durumu
filtreden bağımsızdır: filtre yalnızca neyin *görüneceğini* belirler, toplu işlemler
(seç / kaldır / ters çevir) ise yalnızca *görünen* satırlara uygulanır. Taşıma işlemi ise
filtreden bağımsız olarak işaretli tüm dosyaları kapsar; gizli ama işaretli dosya sayısı
`hidden_selected()` ile arayüzde açıkça gösterilir.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from duzenle.engine import Move

from .textutil import fold


@dataclass(frozen=True)
class Item:
    idx: int
    move: Move
    size: int
    group: str      # hedef klasör (kökten göreli), ör. "Resimler\2026\10"
    new_rel: str    # yeni yerin kökten göreli yolu, ör. "Resimler\2026\10\a.jpg"

    @property
    def name(self) -> str:
        return self.move.src.name


class PlanView:
    def __init__(self, root: Path, moves: list[Move], sizes: dict[Path, int] | None = None) -> None:
        root = root.resolve()
        sizes = sizes or {}
        self.items: list[Item] = []
        for i, m in enumerate(moves):
            self.items.append(Item(
                idx=i, move=m, size=sizes.get(m.src, 0),
                group=str(m.dst.parent.relative_to(root)),
                new_rel=str(m.dst.relative_to(root))))
        self.checked: set[int] = {it.idx for it in self.items}  # varsayılan: hepsi seçili
        self.query = ""

    # ---------- görünüm ----------
    def visible(self) -> list[Item]:
        needle = fold(self.query.strip())
        if not needle:
            return list(self.items)
        return [it for it in self.items if needle in fold(it.name) or needle in fold(it.group)]

    def groups(self) -> list[tuple[str, list[Item]]]:
        """Görünen dosyalar, hedef klasöre göre gruplanmış ve klasör adına göre sıralı."""
        by: dict[str, list[Item]] = {}
        for it in self.visible():
            by.setdefault(it.group, []).append(it)
        return sorted(by.items(), key=lambda kv: fold(kv[0]))

    def group_state(self, group: str) -> str:
        """Görünen satırlara göre 'all' | 'none' | 'some'."""
        members = [it for it in self.visible() if it.group == group]
        on = sum(it.idx in self.checked for it in members)
        return "all" if on == len(members) and members else "none" if on == 0 else "some"

    # ---------- seçim ----------
    def toggle(self, idx: int) -> None:
        self.checked ^= {idx}

    def toggle_group(self, group: str) -> None:
        """Gruptaki görünen dosyalar hepsi seçiliyse kaldırır, değilse hepsini seçer."""
        members = [it.idx for it in self.visible() if it.group == group]
        if all(i in self.checked for i in members):
            self.checked -= set(members)
        else:
            self.checked |= set(members)

    def set_visible(self, on: bool) -> None:
        ids = {it.idx for it in self.visible()}
        self.checked = self.checked | ids if on else self.checked - ids

    def invert_visible(self) -> None:
        self.checked ^= {it.idx for it in self.visible()}

    # ---------- sonuçlar ----------
    def selected_items(self) -> list[Item]:
        return [it for it in self.items if it.idx in self.checked]

    def selected_moves(self) -> list[Move]:
        return [it.move for it in self.selected_items()]

    def selected_bytes(self) -> int:
        return sum(it.size for it in self.selected_items())

    def selected_group_count(self) -> int:
        return len({it.group for it in self.selected_items()})

    def hidden_selected(self) -> int:
        shown = {it.idx for it in self.visible()}
        return sum(1 for i in self.checked if i not in shown)
