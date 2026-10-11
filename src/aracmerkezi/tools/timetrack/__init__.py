from ...registry import Guide, ToolInfo
from .page import TimeTrackPage
from .service import get_service

GUIDE = Guide(
    summary="Hangi programda ne kadar vakit geçirdiğini günlük olarak gösterir.",
    steps=(
        "'Takibi aç' anahtarını aç (varsayılan olarak kapalıdır). LumoraTools açıkken, 5 saniyede bir ön plandaki programın adı örneklenir.",
        "Üstte o günün aktif ve boşta süresi, en çok kullanılan program görünür; altta programlar süreye göre sıralanır.",
        "◀ ▶ ile geçmiş günlere bak; sağdaki panel son 7 günün toplam aktif süresini gösterir.",
        "Takip etmek istemediğin bir programı seçip 'Bu programı yok say'a bas: o program bundan sonra sayılmaz.",
    ),
    tips=(
        "Gizlilik: yalnızca program adı ve süre saklanır; pencere başlığı, belge adı, adres ya da tuş vuruşu ASLA alınmaz.",
        "Veriler yalnızca bu bilgisayarda durur; 'Verileri sil' hepsini siler.",
        "5 dakika klavye/fare kullanılmazsa 'boşta' sayılır; bilgisayar uykudayken geçen süre sayılmaz.",
        "Takip yalnızca LumoraTools açıkken çalışır (pencereyi kapatınca durur).",
    ),
)


def _start(hub) -> None:
    get_service(hub).start()


def _stop(hub) -> None:
    get_service(hub).stop()        # menüden gizlenince izleme de durur (tercih saklı kalır)


TOOL = ToolInfo(
    id="zaman",
    name="Zaman Takibi",
    icon="⏱",
    description="Hangi programda ne kadar vakit geçirdiğini günlük gösterir. Yalnızca program adı saklanır; varsayılan kapalı.",
    build=lambda parent, hub: TimeTrackPage(parent, hub),
    order=140,
    start=_start,
    stop=_stop,
    guide=GUIDE,
    category="uretken",
)
