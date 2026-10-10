"""Araç (eklenti) sözleşmesi ve otomatik keşif.

`aracmerkezi/tools/` altındaki her modül veya paket, modül düzeyinde bir `TOOL`
(ToolInfo) tanımlarsa menüye otomatik eklenir. Hub koduna dokunmak gerekmez.
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolInfo:
    id: str
    name: str
    icon: str
    description: str
    build: Callable[[Any, Any], Any]  # (parent, hub) -> widget
    order: int = 100
    start: Callable[[Any], None] | None = None  # uygulama açılınca arka plan işi başlatır


# PyInstaller klasör taramasını (pkgutil) güvenilir desteklemez; paketlenmiş sürümde de
# bulunması gereken yerleşik araçlar bu yüzden açıkça listelenir. Yeni bir araç yalnızca
# geliştirme sırasında klasörden otomatik bulunur; yerleşik yapmak için buraya ekle.
BUILTIN_TOOLS = ("organizer", "clipboard", "search")

load_errors: list[str] = []


def discover() -> list[ToolInfo]:
    from . import tools

    load_errors.clear()
    names = list(BUILTIN_TOOLS)
    try:
        names += [m.name for m in pkgutil.iter_modules(tools.__path__) if m.name not in names]
    except Exception as e:
        load_errors.append(f"klasör taraması başarısız: {e}")
    found: list[ToolInfo] = []
    for name in names:
        try:
            module = importlib.import_module(f"{tools.__name__}.{name}")
        except Exception as e:  # bozuk bir araç tüm uygulamayı düşürmemeli
            load_errors.append(f"{name}: {e!r}")
            print(f"Araç yüklenemedi: {name}: {e}", file=sys.stderr)
            continue
        tool = getattr(module, "TOOL", None)
        if isinstance(tool, ToolInfo):
            found.append(tool)
    return sorted(found, key=lambda t: (t.order, t.name))
