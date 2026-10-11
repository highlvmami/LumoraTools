from ...registry import Guide, ToolInfo
from .page import ProcessesPage

GUIDE = Guide(
    summary="Çalışan programların bellek ve işlemci kullanımını gösterir; takılanı güvenle kapatmanı sağlar.",
    steps=(
        "Liste her 2 saniyede yenilenir (açık olmayan sayfada yenilenmez). Belleğe, işlemciye ya da ada göre sırala.",
        "'Aynı programı grupla' açıkken tarayıcı gibi çok süreçli programlar tek satırda toplam kullanımıyla görünür.",
        "Bir satırı seçip 'Sonlandır'a (ya da Delete tuşuna) bas; onaydan sonra program kapatılır.",
        "Program nazikçe kapanmazsa 'Zorla kapatılsın mı?' diye sorulur.",
    ),
    tips=(
        "Windows'un çalışması için gerekli sistem süreçleri (csrss, lsass, svchost…) ve bu uygulamanın kendisi korunur; sonlandırılamaz.",
        "Kaydedilmemiş çalışmalar kapatılan programda kaybolabilir; önce programda kaydetmeyi dene.",
        "Başka kullanıcıya ya da yönetici yetkisiyle çalışan programlar için izin gerekebilir.",
    ),
)

TOOL = ToolInfo(
    id="islem",
    name="İşlem Yöneticisi",
    icon="📈",
    description="Çalışan programların bellek ve işlemci kullanımını gösterir; takılanı korumalı şekilde kapatır.",
    build=lambda parent, hub: ProcessesPage(parent, hub),
    order=100,
    guide=GUIDE,
    category="sistem",
)
