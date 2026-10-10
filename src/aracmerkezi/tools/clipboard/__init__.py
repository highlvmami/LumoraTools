from ...registry import ToolInfo
from .page import ClipboardPage, get_service


def _start(hub) -> None:
    _, monitor = get_service(hub)
    monitor.start()


TOOL = ToolInfo(
    id="pano",
    name="Pano Geçmişi",
    icon="📋",
    description="Kopyaladığın her metni saklar, aranabilir hale getirir. Sabitle, tekrar kopyala, sil.",
    build=lambda parent, hub: ClipboardPage(parent, hub),
    order=20,
    start=_start,
)
