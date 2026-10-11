from ...registry import Guide, ToolInfo
from .page import ScreenshotsPage
from .service import get_service


def _start(hub) -> None:
    svc = get_service(hub)
    if svc.cfg.get("watch"):  # önceki oturumda otomatik düzenleme açıksa sayfa açılmadan da çalışsın
        svc.start_watch()


def _stop(hub) -> None:
    get_service(hub).stop_watch(remember=False)  # menüden gizlenince izleme durur, tercih saklı kalır


GUIDE = Guide(
    summary="Ekran görüntülerini tarihe göre düzenler, aranabilir yapar ve istediklerini siler.",
    steps=(
        "Klasörü seç (varsayılan: Resimler\\Screenshots) ve klasör düzenini seç: Yıl / Ay ya da Yıl / Ay / Gün.",
        "'Şimdi tarihe göre düzenle' kökteki görüntüleri alt klasörlere taşır; 'Geri al' geri alır.",
        "'Otomatik düzenle' açıkken yeni ekran görüntüleri arka planda kendiliğinden yerleştirilir.",
        "Ara: ad, not, klasör veya tarih (ör. 11.10.2026) yaz; 'Tarih' çubuğuyla daralt. Görüntüyü seçince önizlenir, not ekleyebilirsin.",
        "Ctrl / Shift ile birden çok görüntü seç (ya da 'Tümünü seç'), sonra 'Seçilenleri sil' ya da Delete tuşu: görüntüler Geri Dönüşüm Kutusu'na taşınır.",
    ),
    tips=(
        "Silinen görüntüler kalıcı silinmez; Geri Dönüşüm Kutusu'ndan geri yüklenebilir.",
        "Not, görüntü başka klasöre taşınsa da onunla kalır.",
    ),
)


TOOL = ToolInfo(
    id="ekran",
    name="Ekran Görüntüleri",
    icon="🖼",
    description="Ekran görüntülerini tarihe göre düzenler, ada/nota/tarihe göre aranabilir yapar; yenileri otomatik yerleştirir.",
    build=lambda parent, hub: ScreenshotsPage(parent, hub),
    order=50,
    start=_start,
    stop=_stop,
    guide=GUIDE,
    category="dosya",
)
