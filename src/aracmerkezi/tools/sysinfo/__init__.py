from ...registry import Guide, ToolInfo
from .page import SysInfoPage

GUIDE = Guide(
    summary="İşlemci, bellek, disk, ağ hızı ve pil durumunu canlı gösterir.",
    steps=(
        "Sayfa açılınca her saniye güncellenir; üstteki kartlar anlık işlemci, bellek ve pil durumunu gösterir.",
        "Grafikler son 60 saniyeyi çizer: bilgisayarın ne zaman yorulduğunu görürsün.",
        "'Diskler' bölümünde her sürücünün doluluğu görünür; %75'ten sonra sarı, %90'dan sonra kırmızı olur.",
        "'Özeti kopyala' destek isterken paylaşabileceğin bir özet çıkarır.",
    ),
    tips=(
        "Başka bir sayfadayken ölçüm yapılmaz, yani bu araç arka planda işlemciyi yormaz.",
        "Özete bilgisayar adı ve kullanıcı adı eklenmez.",
    ),
)

TOOL = ToolInfo(
    id="sistem",
    name="Sistem Bilgisi",
    icon="💻",
    description="İşlemci, bellek, disk, ağ hızı ve pil durumunu canlı grafiklerle gösterir.",
    build=lambda parent, hub: SysInfoPage(parent, hub),
    order=90,
    guide=GUIDE,
    category="sistem",
)
