<div align="center">

<img src="assets/logo.png" alt="LumoraTools logosu" width="88">

# LumoraTools

Windows için tek pencerede çalışan, tamamen yerel bir araç seti.

[Son sürümü indir](../../releases/latest) · [Sürüm notları](../../releases) · [Hata bildir](../../issues)

Türkçe · [English](README.en.md)

<img src="https://img.shields.io/github/v/release/highlvmami/LumoraTools?label=s%C3%BCr%C3%BCm" alt="Son sürüm">
<img src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D4" alt="Platform">
<img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+">
<img src="https://img.shields.io/github/license/highlvmami/LumoraTools?label=lisans" alt="Lisans">

</div>

<br>

<p align="center">
  <img src="docs/screenshots/ana-sayfa.jpg" alt="LumoraTools ana sayfa" width="100%">
</p>

## Genel bakış

LumoraTools; dosya düzenleme, içerik arama, disk temizliği, sistem izleme ve görev takibi gibi günlük işleri tek bir masaüstü uygulamasında toplar. Her araç aynı pencerede, aynı tema ve ayarlarla çalışır.

Uygulama hesap gerektirmez ve hiçbir veriyi dışarı göndermez. Tüm ayarlar ve kayıtlar yalnızca kullanıcının bilgisayarında tutulur. Tek bir `.exe` dosyası olarak dağıtılır, kurulum gerektirmez ve yeni sürümleri GitHub Releases üzerinden kendisi yükler.

## Araçlar

Araçlar menüde dört başlık altında toplanır. Sıralama ve görünürlük Ayarlar ekranından değiştirilebilir.

### Dosyalar

| Araç | Ne yapar |
|---|---|
| Yerel Arama | Seçilen klasörlerdeki dosyaların içeriğini SQLite FTS5 ile dizinler ve anında arar. Düz metin, kaynak kodu, `.docx` ve `.pdf` desteklenir. Değişmeyen dosyalar yeniden okunmaz. |
| Dosya Düzenleyici | Bir klasörü uzantıya, tarihe veya ikisine göre alt klasörlere ayırır. Her dosyanın nereye taşınacağı önceden gösterilir; dosyalar tek tek ya da toplu seçilebilir. Hiçbir dosya silinmez ve her işlem geri alınabilir. İzleme modu, klasöre yeni gelen dosyaları otomatik yerleştirir. |
| Boyut Analizcisi | Diskte en çok yer kaplayan klasörleri oransal çubuklarla gösterir, alt klasörlere inilebilir. En büyük dosyaları ayrıca listeler. |
| Ekran Görüntüleri | Ekran görüntüleri klasörünü yıl ve aya göre düzenler, yeni görüntüleri otomatik yerleştirir. Ad, not ve tarihe göre arama ile önizleme sunar. |

### Bakım ve temizlik

| Araç | Ne yapar |
|---|---|
| Sistem Temizleyici | Geçici dosyaları, çökme dökümlerini, yarım kalmış indirmeleri, tarayıcı önbelleklerini ve Geri Dönüşüm Kutusu'nu boyutlarıyla listeler; yalnızca seçilenleri temizler. |
| Başlangıç Programları | Windows açılışında çalışan programları listeler. Girdiler silinmeden, Görev Yöneticisi'nin kullandığı yöntemle devre dışı bırakılır. |
| Program Kaldırıcı | Yüklü programları boyut ve kurulum tarihiyle listeler. Kaldırma işlemini programın kendi kaldırıcısı yapar. |
| Pil ve Disk Sağlığı | Pil yıpranmasını (tasarım kapasitesine oran, şarj döngüsü) ve disklerin sağlık durumunu gösterir. |

### Sistem ve ağ

| Araç | Ne yapar |
|---|---|
| Sistem Bilgisi | İşlemci, bellek, disk, ağ hızı ve pil durumunu canlı grafiklerle gösterir. Bilgisayar ve kullanıcı adı içermeyen bir donanım özeti kopyalanabilir. |
| İşlem Yöneticisi | Çalışan süreçleri bellek ve işlemci kullanımına göre listeler, aynı programın süreçlerini gruplar. Kritik Windows süreçleri sonlandırılamaz. |
| Ağ Araçları | Etkin bağlantıları ve dinlenen portları ilgili programla birlikte gösterir. Ping, DNS sorgusu ve tek port kontrolü sunar. |

### Üretkenlik

| Araç | Ne yapar |
|---|---|
| Pano Geçmişi | Kopyalanan metin, görüntü ve dosyaları saklar. Arama, sabitleme ve tarih filtresi sunar; kayıt istenildiğinde duraklatılabilir. |
| Yapılacaklar | Son tarih ve öncelik destekli görev listesi; bekleyen, bugün, geciken ve biten görevler için filtreler. |
| Zaman Takibi | Hangi programda ne kadar süre geçirildiğini günlük olarak raporlar. Varsayılan olarak kapalıdır. |

## Ekran görüntüleri

<p align="center">
  <img src="docs/screenshots/dosya-duzenleyici.jpg" alt="Dosya Düzenleyici" width="49%">
  <img src="docs/screenshots/boyut-analizcisi.jpg" alt="Boyut Analizcisi" width="49%">
</p>
<p align="center">
  <img src="docs/screenshots/yapilacaklar.jpg" alt="Yapılacaklar" width="49%">
  <img src="docs/screenshots/sistem-bilgisi.jpg" alt="Sistem Bilgisi" width="49%">
</p>
<p align="center">
  <img src="docs/screenshots/ayarlar.jpg" alt="Ayarlar ve tema seçimi" width="49%">
  <img src="docs/screenshots/tema-gunduz.jpg" alt="Açık tema" width="49%">
</p>

<p align="center"><sub>Görüntüler örnek verilerle alınmıştır.</sub></p>

## Gizlilik ve güvenlik

- Uygulama hiçbir kullanıcı verisini bir sunucuya göndermez. Kullanıcı bir işlem başlatmadıkça yapılan tek ağ isteği yeni sürüm kontrolüdür ve Ayarlar'dan kapatılabilir.
- Güncellemeler yalnızca HTTPS üzerinden indirilir ve SHA-256 özeti doğrulanmadan uygulanmaz.
- Dosya Düzenleyici dosya silmez, yalnızca taşır. Ad çakışmalarında mevcut dosyanın üzerine yazılmaz.
- Sistem Temizleyici yalnızca önceden tanımlı klasörlerde çalışır; son 24 saatte değişen geçici dosyalara ve sembolik bağlantılara dokunmaz. Kalıcı silinecek öğeler onay penceresinde açıkça belirtilir.
- Ekran görüntüsü ve yarım indirme silme işlemleri dosyaları Geri Dönüşüm Kutusu'na taşır.
- Zaman Takibi yalnızca program adını ve süreyi kaydeder. Pencere başlıkları, adresler veya tuş vuruşları kaydedilmez.
- Ağ Araçları port taraması yapmaz ve tüm girdileri doğrular.

## Kurulum

1. [Releases](../../releases/latest) sayfasından `AracMerkezi.exe` dosyasını indirin.
2. Dosyayı istediğiniz bir klasöre koyup çalıştırın. Kurulum adımı yoktur.

Dosya kod imzalı olmadığından Windows SmartScreen ilk çalıştırmada uyarı gösterebilir. Bu durumda "Ek bilgi" ve ardından "Yine de çalıştır" seçilerek devam edilebilir.

Uygulama verileri `%USERPROFILE%\.aracmerkezi` klasöründe tutulur. Farklı bir konum için `ARACMERKEZI_HOME` ortam değişkeni kullanılabilir.

## Kaynaktan çalıştırma

Python 3.10 veya üzeri gerekir.

```bash
git clone https://github.com/highlvmami/LumoraTools.git
cd LumoraTools
py -m pip install -e .[dev]
py -m aracmerkezi
```

Testleri çalıştırmak ve tek dosyalık sürümü derlemek için:

```bash
py -m pytest
py build.py
```

`build.py`, PyInstaller ile `dist/AracMerkezi.exe` dosyasını ve güncelleme denetiminin kullandığı `dist/manifest.json` dosyasını üretir.

## Proje yapısı

```
src/
  aracmerkezi/
    app.py           Ana pencere, menü, ayarlar ve güncelleme akışı
    registry.py      Araç kaydı, kategoriler ve araç keşfi
    updater.py       Sürüm denetimi, indirme ve doğrulama
    themes.py        Tema tanımları ve kontrast hesaplamaları
    ui.py            Ortak arayüz bileşenleri
    tools/           Her araç ayrı bir paket olarak
  duzenle/           Dosya düzenleme motoru (planlama, taşıma, geri alma)
tests/               pytest test paketi
build.py             PyInstaller derleme betiği
```

## Yeni araç ekleme

Her araç `src/aracmerkezi/tools/` altında bağımsız bir pakettir. Paketin `__init__.py` dosyası bir `ToolInfo` nesnesi tanımlar: kimlik, ad, açıklama, menü kategorisi, sayfayı oluşturan fonksiyon ve gerekiyorsa arka plan işini başlatıp durduran fonksiyonlar. Paket adı, tek dosyalık derlemeye dahil edilmesi için `registry.py` içindeki `BUILTIN_TOOLS` listesine eklenir.

## Katkı

Hata bildirimleri ve öneriler için [Issues](../../issues) bölümü kullanılabilir. Uygulama içindeki İletişim sayfası da önceden doldurulmuş bir bildirim formu açar. Büyük değişiklikler için pull request göndermeden önce bir issue açılması önerilir.

## Lisans

[MIT](LICENSE)
