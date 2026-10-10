from ...registry import ToolInfo
from .page import ScreenshotsPage
from .service import get_service


def _start(hub) -> None:
    svc = get_service(hub)
    if svc.cfg.get("watch"):  # önceki oturumda otomatik düzenleme açıksa sayfa açılmadan da çalışsın
        svc.start_watch()


def _stop(hub) -> None:
    get_service(hub).stop_watch(remember=False)  # menüden gizlenince izleme durur, tercih saklı kalır


TOOL = ToolInfo(
    id="ekran",
    name="Ekran Görüntüleri",
    icon="🖼",
    description="Ekran görüntülerini tarihe göre düzenler, ada/nota/tarihe göre aranabilir yapar; yenileri otomatik yerleştirir.",
    build=lambda parent, hub: ScreenshotsPage(parent, hub),
    order=50,
    start=_start,
    stop=_stop,
)
