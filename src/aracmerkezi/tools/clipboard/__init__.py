from ...registry import Guide, ToolInfo
from .page import ClipboardPage, get_service


def _start(hub) -> None:
    _, monitor = get_service(hub)
    monitor.resume()  # yeniden görünür olunca, gizliyken kopyalananlar kaydedilmez


def _stop(hub) -> None:
    """Araç menüden gizlenince pano kaydı da durur (gizli araç arka planda kayıt tutmasın)."""
    _, monitor = get_service(hub)
    monitor.stop()


GUIDE = Guide(
    summary="Kopyaladığın metinleri saklar; arayıp tekrar kullanmanı sağlar.",
    steps=(
        "Uygulama açıkken kopyaladığın her metin listeye eklenir (bu sayfa açık olmasa da, arka planda).",
        "Üstteki kutuyla ara; 'Tarih' çubuğuyla Bugün, Dün, Son 7/30 gün ya da kendi yazdığın aralığa daralt.",
        "Bir öğeyi seçince sağda tamamı görünür. Çift tıklayınca ya da 'Kopyala' ile tekrar panoya alırsın.",
        "'Sabitle' önemli öğeleri listenin başında tutar ve 'Temizle'den korur.",
    ),
    tips=(
        "Parola gibi gizli bir şey kopyalayacaksan 'Kaydediyor' anahtarını kapat.",
        "Aynı metin tekrar kopyalanırsa kopya oluşmaz, listenin başına çıkar.",
    ),
)


TOOL = ToolInfo(
    id="pano",
    name="Pano Geçmişi",
    icon="📋",
    description="Kopyaladığın her metni saklar, aranabilir hale getirir. Sabitle, tekrar kopyala, sil.",
    build=lambda parent, hub: ClipboardPage(parent, hub),
    order=30,
    start=_start,
    stop=_stop,
    guide=GUIDE,
    category="uretken",
)
