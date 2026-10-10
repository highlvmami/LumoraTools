from ...registry import Guide, ToolInfo
from .page import DiskUsagePage

GUIDE = Guide(
    summary="Diskte yeri en çok neyin kapladığını gösterir.",
    steps=(
        "Klasörü seç ('Gözat' ya da 'Ev klasörüm') ve 'Analiz et'e bas. Büyük klasörler birkaç dakika sürebilir; 'Durdur' ile kesebilirsin.",
        "Klasörler boyuta göre çubuklarla sıralanır: çubuk uzunluğu en büyük öğeye, yüzde ise klasörün toplamına göredir.",
        "Bir klasör çubuğuna tıklayınca içine girersin; 'Üst klasör' ile geri çıkarsın.",
        "'En büyük dosyalar' sekmesi tüm ağaçtaki ilk 100 dosyayı listeler; çift tıklayınca Explorer'da gösterir.",
    ),
    tips=(
        "Araç hiçbir şey silmez; yer açmak için dosyaları Explorer'da kendin silersin.",
        "Erişim izni olmayan klasörler atlanır ve sayısı bildirilir.",
    ),
)


TOOL = ToolInfo(
    id="boyut",
    name="Boyut Analizcisi",
    icon="📊",
    description="Diskte yeri en çok kimin kapladığını gösterir: klasörlere inen çubuk grafik ve en büyük dosyalar.",
    build=lambda parent, hub: DiskUsagePage(parent, hub),
    order=40,
    guide=GUIDE,
)
