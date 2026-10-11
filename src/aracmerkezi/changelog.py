"""Sürüm notları ve "Yenilikler" penceresinin hangi notları göstereceği (Tk'den bağımsız, test edilebilir).

Her yayında en üste yeni sürümün notları eklenir (bir test, güncel sürümün burada olmasını zorunlu kılar).
Uygulama, kullanıcının en son hangi sürümü gördüğünü saklar; yükseltme sonrası ilk açılışta aradaki
sürümlerin notları gösterilir. Notlar uygulamanın içinde durur, bu yüzden güncelleme elle de yapılsa çalışır.
"""
from __future__ import annotations

from .updater import UpdateError, is_newer, parse_version

CHANGELOG: dict[str, tuple[str, ...]] = {
    "0.9.0": (
        "Menü artık kategorilere ayrıldı: Dosyalar, Bakım ve temizlik, Sistem ve ağ, Üretkenlik. Başlığa tıklayınca kategori açılıp kapanır, tercihin hatırlanır.",
        "Ana sayfadaki araç kartları da kategorilere göre gruplanır.",
        "Ayarlar → Menüyü düzenle'deki anahtarla gruplamayı kapatıp eski düz listeye dönebilirsin; sürükleyerek verdiğin sıra kategori içinde korunur.",
    ),
    "0.8.0": (
        "Program Kaldırıcı: yüklü programları boyut ve tarihleriyle listeler, seçtiğinin kendi kaldırıcısını başlatır.",
        "Sistem Bilgisi: işlemci, bellek, disk, ağ hızı ve pil durumunu canlı grafiklerle gösterir.",
        "İşlem Yöneticisi: çalışan programların bellek/işlemci kullanımını gösterir; takılanı korumalı şekilde kapatır.",
        "Ağ Araçları: etkin bağlantılar ve dinleyen portlar, ping, DNS sorgusu, port kontrolü, ağ bağdaştırıcıları.",
        "Pil ve Disk Sağlığı: pil yıpranması (kapasite, döngü) ve disklerin sağlık durumu.",
        "Yapılacaklar: son tarihli, öncelikli görev listesi.",
        "Zaman Takibi: hangi programda ne kadar vakit geçirdiğini günlük gösterir (varsayılan kapalı; yalnızca program adı saklanır).",
    ),
    "0.7.0": (
        "Sistem Temizleyici: geçici dosyaları, indirme artıklarını, önbellekleri ve Geri Dönüşüm Kutusu'nu boyutlarıyla listeler, seçtiğini temizler.",
        "Başlangıç Programları: Windows açılırken çalışan programları gösterir, istediğini kapatıp açmanı sağlar.",
        "Pano Geçmişi artık görüntüleri ve kopyalanan dosyaları da saklıyor; tekrar panoya alabilirsin.",
        "12 yeni tema: Ayarlar'dan tek tıkla değiştir (Gece, Gündüz, Okyanus, Orman, Gün Batımı, Kahve, Nord, Kömür, AMOLED, Lavanta, Şeker, Kağıt).",
        "Yenilikler penceresi: uygulama güncellenince neyin değiştiğini gösterir.",
    ),
    "0.6.2": (
        "Ekran Görüntüleri: Ctrl / Shift ile çoklu seçimde önizleme artık son tıkladığın görüntüyü gösterir.",
    ),
    "0.6.1": (
        "Düzeltme: Ekran Görüntüleri'nde bir görüntü silindikten sonra önizleme güncellenmiyordu.",
    ),
    "0.6.0": (
        "Yeni logo (TL monogramı) ve LumoraTools adı.",
        "Rehberler: her aracın kısa kullanım anlatımı.",
        "İletişim: istek, şikayet, hata ve geri bildirimini GitHub üzerinden ilet.",
        "Ekran Görüntüleri: çoklu seçim ve silme (Geri Dönüşüm Kutusu'na taşır).",
    ),
    "0.5.0": (
        "Yeni araçlar: Boyut Analizcisi ve Ekran Görüntüleri.",
        "Pano Geçmişi ve Ekran Görüntüleri'nde tarih filtresi.",
        "Ayarlar'da menüyü düzenleme: araçları sürükleyerek sırala, gizle / göster.",
    ),
    "0.4.2": (
        "Dosya Düzenleyici: seçilmeyen dosyalar 'yerinde kalacak' olarak gösterilir; desktop.ini ve gizli/sistem dosyaları taşınmaz.",
    ),
    "0.4.1": (
        "Sürüm numarası pencere başlığında, kenar çubuğunda ve .exe dosya özelliklerinde görünür.",
    ),
    "0.4.0": (
        "Dosya Düzenleyici: dosyaları tek tek veya toplu seçme, hedef klasöre göre gruplama, filtre, 'Olduğu gibi' modu ve yükleme göstergesi.",
    ),
}


def _ordered() -> list[str]:
    return sorted(CHANGELOG, key=parse_version, reverse=True)


def entries_between(previous: str | None, current: str, fresh_install: bool = False,
                    limit: int = 5) -> list[tuple[str, tuple[str, ...]]]:
    """Yükseltme sonrası gösterilecek (sürüm, notlar) listesi, en yeniden eskiye.

    - `previous` biliniyorsa: previous'tan yeni ve current'a eşit ya da küçük sürümler.
    - `previous` bilinmiyorsa (bu özellikten önceki bir sürümden geliniyor): yalnızca current.
    - `fresh_install` ise (ilk kurulum): hiçbir şey.
    """
    if fresh_install:
        return []
    try:
        if previous is None:
            picked = [current] if current in CHANGELOG else []
        else:
            picked = [v for v in _ordered() if is_newer(v, previous) and not is_newer(v, current)]
    except UpdateError:
        picked = [current] if current in CHANGELOG else []
    return [(v, CHANGELOG[v]) for v in picked[:limit]]


def recent(count: int = 4) -> list[tuple[str, tuple[str, ...]]]:
    """Ayarlar'dan açılan pencere için en son `count` sürümün notları."""
    return [(v, CHANGELOG[v]) for v in _ordered()[:count]]
