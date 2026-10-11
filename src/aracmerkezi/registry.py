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
class Guide:
    """Rehberler sayfasında gösterilen kısa kullanım anlatımı."""
    summary: str
    steps: tuple[str, ...]
    tips: tuple[str, ...] = ()


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    icon: str


# Menü kategorileri, bu sırayla gösterilir. Her araç `category` ile birini seçer; bilinmeyen kategori "Diğer"e düşer.
CATEGORIES = (
    Category("dosya", "Dosyalar", "📁"),
    Category("bakim", "Bakım ve temizlik", "🧹"),
    Category("sistem", "Sistem ve ağ", "🖥"),
    Category("uretken", "Üretkenlik", "✍"),
)
OTHER = Category("diger", "Diğer", "🧩")


@dataclass(frozen=True)
class ToolInfo:
    id: str
    name: str
    icon: str
    description: str
    build: Callable[[Any, Any], Any]  # (parent, hub) -> widget
    order: int = 100
    start: Callable[[Any], None] | None = None  # uygulama açılınca arka plan işi başlatır
    stop: Callable[[Any], None] | None = None   # araç menüden gizlenince arka plan işini durdurur
    guide: Guide | None = None                  # Rehberler sayfasındaki kısa anlatım
    category: str = "diger"                     # menü kategorisi (CATEGORIES içindeki kimliklerden biri)


# PyInstaller klasör taramasını (pkgutil) güvenilir desteklemez; paketlenmiş sürümde de
# bulunması gereken yerleşik araçlar bu yüzden açıkça listelenir. Yeni bir araç yalnızca
# geliştirme sırasında klasörden otomatik bulunur; yerleşik yapmak için buraya ekle.
BUILTIN_TOOLS = ("organizer", "clipboard", "search", "diskusage", "screenshots", "cleaner", "startup",
                 "uninstall", "sysinfo", "processes", "network", "health", "todo", "timetrack")

load_errors: list[str] = []


def order_tools(tools: list[ToolInfo], saved_order: list[str] | None,
                hidden: set[str] | None) -> tuple[list[ToolInfo], list[ToolInfo]]:
    """Kullanıcının menü tercihini uygular. (hepsi sıralı, yalnızca görünenler sıralı) döndürür.

    Kayıtlı sırada olmayan (yeni eklenen) araçlar, varsayılan sırayla sona eklenir.
    """
    default = sorted(tools, key=lambda t: (t.order, t.name))
    by_id = {t.id: t for t in default}
    ordered: list[ToolInfo] = []
    for tid in saved_order or []:
        tool = by_id.pop(tid, None)
        if tool:
            ordered.append(tool)
    ordered += [t for t in default if t.id in by_id]
    hidden = hidden or set()
    return ordered, [t for t in ordered if t.id not in hidden]


def group_tools(tools: list[ToolInfo]) -> list[tuple[Category, list[ToolInfo]]]:
    """Araçları kategorilere ayırır. Kategori sırası sabittir (CATEGORIES, sonra Diğer); bir kategorideki araçların
    sırası, gelen sıra korunarak (kullanıcının sürükleyerek verdiği sıra) belirlenir. Boş kategoriler çıkarılır."""
    known = {c.id: c for c in CATEGORIES}
    buckets: dict[str, list[ToolInfo]] = {c.id: [] for c in CATEGORIES}
    buckets[OTHER.id] = []
    for t in tools:
        buckets[t.category if t.category in known else OTHER.id].append(t)
    return [(known.get(cid, OTHER), items) for cid, items in buckets.items() if items]


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
