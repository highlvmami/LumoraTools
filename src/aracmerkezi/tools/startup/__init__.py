from ...registry import Guide, ToolInfo
from .page import StartupPage

GUIDE = Guide(
    summary="Windows açılırken kendiliğinden başlayan programları gösterir; istediğini kapatıp açmanı sağlar.",
    steps=(
        "Liste, programlar kaynaklarına göre gruplanmış olarak açılır (kayıt defteri, Başlangıç klasörü).",
        "Bir programın anahtarını kapat: bir sonraki oturum açışında artık kendiliğinden başlamaz.",
        "Yeniden açmak için anahtarı geri aç. Hiçbir program silinmez, her şey geri alınabilir.",
        "📂 düğmesi programın dosyasını Explorer'da gösterir; neyin ne olduğunu anlamana yardım eder.",
    ),
    tips=(
        "Değişiklik yalnızca senin hesabın için geçerlidir ve bir sonraki oturum açışında uygulanır.",
        "Ne olduğunu bilmediğin Microsoft, ses veya ekran kartı sürücü programlarını kapatma.",
    ),
)

TOOL = ToolInfo(
    id="baslangic",
    name="Başlangıç Programları",
    icon="🚀",
    description="Windows açılırken çalışan programları gösterir; istediğini silmeden kapatıp açabilirsin.",
    build=lambda parent, hub: StartupPage(parent, hub),
    order=70,
    guide=GUIDE,
)
