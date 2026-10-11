from ...registry import Guide, ToolInfo
from .page import SearchPage

GUIDE = Guide(
    summary="Seçtiğin klasörlerdeki dosyaların içinde anında arar.",
    steps=(
        "'Dizin' sekmesinde 'Klasör ekle' ile aranacak klasörleri seç.",
        "'Dizinle / güncelle'ye bas; ilk seferde klasör büyüklüğüne göre biraz sürer.",
        "'Ara' sekmesine dön ve kelimeleri yaz. Türkçe harfler fark etmez: 'calisma' yazınca 'çalışma' da bulunur.",
        "Sonuçta eşleşen kelimeler vurgulanır. 'Dosyayı aç' ya da 'Klasörde göster' ile dosyaya ulaşırsın.",
    ),
    tips=(
        "Metin, kod, .docx ve .pdf dosyaları dizinlenir.",
        "Dosyalar değiştikçe 'Dizinle / güncelle'ye tekrar bas; yalnızca değişenler okunur.",
    ),
)


TOOL = ToolInfo(
    id="arama",
    name="Yerel Arama",
    icon="🔎",
    description="Seçtiğin klasörlerdeki dosyaların içeriğini dizinler ve anında arar. Metin, kod, Word ve PDF.",
    build=lambda parent, hub: SearchPage(parent, hub),
    order=10,
    guide=GUIDE,
    category="dosya",
)
