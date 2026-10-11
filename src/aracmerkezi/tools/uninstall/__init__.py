from ...registry import Guide, ToolInfo
from .page import UninstallPage

GUIDE = Guide(
    summary="Yüklü programları boyutları ve yüklenme tarihleriyle listeler; kaldırmayı programın kendi kaldırıcısı yapar.",
    steps=(
        "Listede ara, 'Ada göre / Boyuta göre / Yeni yüklenen' ile sırala. En çok yer kaplayanları bulmak için boyuta göre sırala.",
        "Bir programı seç; 'Kaldır…' düğmesi etkinleşir (kaldırıcısı olmayanlar için etkin olmaz).",
        "Onaydan sonra programın KENDİ kaldırıcısı açılır; kaldırma işlemi onun penceresinde tamamlanır.",
        "İşlem bitince 'Yenile'ye basarak listeyi güncelle. 'Klasörü aç' programın kurulu olduğu klasörü gösterir.",
    ),
    tips=(
        "Bu araç hiçbir şeyi kendisi silmez; yalnızca Windows'un kayıtlı kaldırıcısını başlatır.",
        "Sistem bileşenleri ve Windows güncellemeleri varsayılan olarak gizlidir ('Güncellemeleri göster' ile açılır).",
        "Boyut bilgisi programın kendi bildirdiği tahmindir; bazı programlar bildirmez ('—').",
        "Microsoft Store uygulamaları bu listede değildir; onlar için 'Windows Uygulamalar' düğmesini kullan.",
    ),
)

TOOL = ToolInfo(
    id="kaldir",
    name="Program Kaldırıcı",
    icon="📦",
    description="Yüklü programları boyut ve tarihleriyle listeler; seçtiğinin kendi kaldırıcısını başlatır.",
    build=lambda parent, hub: UninstallPage(parent, hub),
    order=80,
    guide=GUIDE,
    category="bakim",
)
