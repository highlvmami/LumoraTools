from ...registry import ToolInfo
from .page import ClipboardPage, get_service


def _start(hub) -> None:
    _, monitor = get_service(hub)
    monitor.resume()  # yeniden görünür olunca, gizliyken kopyalananlar kaydedilmez


def _stop(hub) -> None:
    """Araç menüden gizlenince pano kaydı da durur (gizli araç arka planda kayıt tutmasın)."""
    _, monitor = get_service(hub)
    monitor.stop()


TOOL = ToolInfo(
    id="pano",
    name="Pano Geçmişi",
    icon="📋",
    description="Kopyaladığın her metni saklar, aranabilir hale getirir. Sabitle, tekrar kopyala, sil.",
    build=lambda parent, hub: ClipboardPage(parent, hub),
    order=30,
    start=_start,
    stop=_stop,
)
