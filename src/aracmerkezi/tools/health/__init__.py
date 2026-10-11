from ...registry import Guide, ToolInfo
from .page import HealthPage

GUIDE = Guide(
    summary="Pilin ne kadar yıprandığını ve disklerinin genel sağlık durumunu gösterir.",
    steps=(
        "Sayfa açılınca ölçüm yapılır (birkaç saniye sürer); 'Yenile' ile tekrarlanır.",
        "Pil: tam şarj kapasitesinin yeni zamanındaki kapasiteye oranı (%), şarj döngüsü ve yorum görünür.",
        "Diskler: her diskin türü (SSD/HDD), bağlantısı, boyutu ve Windows'un bildirdiği sağlık durumu görünür.",
        "Etiketler: İyi (yeşil), Dikkat (sarı), Zayıf (kırmızı). Pil %60'ın altına inerse değişim düşünülmeli.",
    ),
    tips=(
        "Masaüstü bilgisayarlarda pil bölümü 'pil yok' der.",
        "Disk sıcaklığı, aşınması ve çalışma saati için yönetici izni gerekir; yoksa bunu açıkça belirtir.",
        "'Sağlıklı' görünen bir disk bile bozulabilir; önemli verilerin yedeğini almayı unutma.",
    ),
)

TOOL = ToolInfo(
    id="saglik",
    name="Pil ve Disk Sağlığı",
    icon="🔋",
    description="Pil yıpranmasını (kapasite, döngü) ve disklerin sağlık durumunu gösterir.",
    build=lambda parent, hub: HealthPage(parent, hub),
    order=120,
    guide=GUIDE,
)
