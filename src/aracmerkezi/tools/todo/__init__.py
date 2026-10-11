from ...registry import Guide, ToolInfo
from .page import TodoPage

GUIDE = Guide(
    summary="Görevlerini yaz, son tarih ve öncelik ver, bitenleri işaretle.",
    steps=(
        "Üstteki kutuya görevi yaz, istersen son tarih (GG.AA.YYYY) ve öncelik seç, Enter'a bas.",
        "Kutucuğu işaretleyince görev biter; 'Biten' sekmesinde görünür ve istediğin zaman geri alabilirsin.",
        "Listeyi 'Bekleyen / Bugün / Geciken / Biten / Hepsi' ile süz, arama kutusuyla ara.",
        "✎ ile başlığı, tarihi, önceliği ve notu düzenle; ✕ ile görevi sil.",
    ),
    tips=(
        "Bekleyen görevler öncelik sırasına (acil önce), sonra son tarihe göre dizilir.",
        "Son tarihi geçen görevler kırmızı 'gecikti', bugün biten sarı 'bugün' etiketiyle görünür.",
        "'Bitenleri temizle' yalnızca biten görevleri siler, bekleyenlere dokunmaz.",
    ),
)

TOOL = ToolInfo(
    id="gorev",
    name="Yapılacaklar",
    icon="✅",
    description="Görev listesi: son tarih, öncelik, süzgeçler ve arama.",
    build=lambda parent, hub: TodoPage(parent, hub),
    order=130,
    guide=GUIDE,
    category="uretken",
)
