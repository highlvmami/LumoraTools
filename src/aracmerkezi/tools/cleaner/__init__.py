from ...registry import Guide, ToolInfo
from .page import CleanerPage

GUIDE = Guide(
    summary="Geçici dosyaları, artıkları ve önbellekleri boyutlarıyla gösterir; yalnızca seçtiklerini temizler.",
    steps=(
        "Sayfa açılınca otomatik taranır; 'Tara' ile yeniden tarayabilirsin. Her kategorinin ne kadar yer kapladığı yazar.",
        "Bir kategoriye tıklayınca sağda en büyük dosyaları görürsün. Kutuyu işaretleyerek neyin temizleneceğini seç.",
        "'Seçilenleri temizle': onay penceresi neyin KALICI silineceğini, neyin Geri Dönüşüm Kutusu'na taşınacağını açıkça yazar.",
        "Temizlik bitince kaç MB boşaldığı ve kaç dosyanın atlandığı (kullanımdaki dosyalar) gösterilir.",
    ),
    tips=(
        "Geçici dosyalarda 1 günden yeni olanlara, çalışan programların dosyalarına ve bağlantılara dokunulmaz.",
        "İndirilenler'deki yarım kalmış indirmeler kalıcı silinmez, Geri Dönüşüm Kutusu'na gider.",
        "Tarayıcı önbellekleri ve Geri Dönüşüm Kutusu'nu boşaltma kendiliğinden seçili gelmez; bilerek işaretlemen gerekir.",
    ),
)

TOOL = ToolInfo(
    id="temizle",
    name="Sistem Temizleyici",
    icon="🧹",
    description="Geçici dosyaları, yarım indirmeleri, önbellekleri ve Geri Dönüşüm Kutusu'nu boyutlarıyla listeler; seçtiğini temizler.",
    build=lambda parent, hub: CleanerPage(parent, hub),
    order=60,
    guide=GUIDE,
)
