# LumoraTools

Tek pencerede çalışan, küçük bir masaüstü araç seti (Windows). Soldaki menüden araç seçilir.

## Araçlar

### 📁 Dosya Düzenleyici
Bir klasörü (ör. İndirilenler) uzantıya veya tarihe göre alt klasörlere ayırır.
1. Klasörü seç (**Gözat** ya da **İndirilenler**), modu seç: *Uzantıya göre*, *Tarihe göre*, *Birleşik*.
2. **Önizle** ile neyin nereye taşınacağını gör; hiçbir dosyaya dokunulmaz.
3. **Düzenle** ile taşı. **Geri al** son işlemi geri alır.
4. **İzle** sekmesi klasöre yeni gelen dosyaları otomatik yerleştirir (inmekte olan dosyalara dokunmaz).

Dosyalar silinmez, yalnızca taşınır. Aynı isimli dosya `ad (1).uzantı` olarak kaydedilir.

### 📋 Pano Geçmişi
Uygulama açıkken kopyaladığın metinleri saklar.
- Üstteki kutuyla ara (Türkçe harflere duyarsız).
- Çift tıklayınca metin tekrar panoya alınır; **Sabitle** ile listenin başında tutulur.
- **Kaydediyor** anahtarı kaydı duraklatır. Parola gibi hassas bir şey kopyalayacaksan kapat.

### 🔎 Yerel Arama
Seçtiğin klasörlerdeki dosyaların içeriğinde anında arar (SQLite FTS5).
1. **Dizin** sekmesinde **Klasör ekle** → **Dizinle / güncelle**.
2. **Ara** sekmesinde yaz; eşleşen kelimeler vurgulanır. **Dosyayı aç** / **Klasörde göster** ile ulaş.

Metin, kod, `.docx` ve `.pdf` dosyaları dizinlenir. Değişmeyenler tekrar okunmaz.

### 📊 Boyut Analizcisi
Diskte yeri en çok kimin kapladığını gösterir. Klasörü seç, **Analiz et**; klasörler boyuta göre çubuklarla listelenir,
çubuğa tıklayınca içine girersin (**Üst klasör** ile geri çıkarsın). **En büyük dosyalar** sekmesi tüm ağaçtaki en büyük
dosyaları sıralar. Araç hiçbir şey silmez.

### 🖼 Ekran Görüntüleri
Ekran görüntüleri klasörünü (varsayılan: Resimler\Screenshots) tarihe göre `Yıl\Ay` veya `Yıl\Ay\Gün` klasörlerine düzenler.
- **Şimdi tarihe göre düzenle** mevcut görüntüleri taşır (**Geri al** ile geri alınır); yalnızca görüntü dosyalarına dokunur.
- **Otomatik düzenle** anahtarı, uygulama açıkken yeni ekran görüntülerini arka planda yerleştirir.
- Ada, nota, klasöre ve tarihe (ör. `11.10.2026`) göre ara; tarih filtresiyle daralt; önizle; her görüntüye not ekle.

### Menü ve tarih filtresi
**Ayarlar → Menüyü düzenle:** araçları ⠿ tutamacından sürükleyerek sırala, anahtarla gizle/göster (gizlenen aracın arka plan işi de durur).
Pano Geçmişi ve Ekran Görüntüleri'nde tarih filtresi: Bugün, Dün, Son 7/30 gün veya elle yazılan aralık.

### 🧹 Sistem Temizleyici
Geçici dosyaları, çökme dökümlerini, yarım kalmış indirmeleri, tarayıcı/pip önbelleklerini ve Geri Dönüşüm Kutusu'nu
boyutlarıyla listeler; yalnızca işaretlediklerini temizler. Güvenlik: yalnızca tanımlı klasörlere dokunur, geçici
dosyalarda 1 günden yenilere ve bağlantılara (junction/symlink) dokunmaz, yarım indirmeleri kalıcı silmek yerine
Geri Dönüşüm Kutusu'na taşır. Onay penceresi neyin KALICI silineceğini açıkça yazar; kutuyu boşaltmak kendiliğinden seçili gelmez.

### 🚀 Başlangıç Programları
Windows açılırken çalışan programları (kayıt defteri ve Başlangıç klasörleri) listeler; her birini silmeden kapatıp
açabilirsin (Görev Yöneticisi'nin kullandığı StartupApproved işareti). Değişiklik bir sonraki oturum açışında geçerli olur.

### 📋 Pano: görüntü ve dosya
Pano Geçmişi artık kopyalanan görüntüleri ve dosyaları da saklar; seçip tekrar panoya alabilirsin.

### 🎨 Temalar ve Yenilikler
Ayarlar'dan 12 temadan birini seç (Gece, Gündüz, Okyanus, Orman, Gün Batımı, Kahve, Nord, Kömür, AMOLED, Lavanta, Şeker, Kağıt);
tüm renkler okunabilirlik oranları testle doğrulanmıştır. Uygulama güncellenince **Yenilikler** penceresi değişenleri gösterir.

### Rehberler ve İletişim
**Rehberler** (Ayarlar'ın hemen üstünde) her aracın kısa kullanım anlatımını içerir. **İletişim** sayfasından istek,
şikayet, hata ya da geri bildirim yazabilirsin: mesaj tarayıcıda hazır doldurulmuş bir GitHub sayfası olarak açılır ve
sen orada gönder düğmesine basana kadar kimseye gönderilmez.

Ekran Görüntüleri'nde Ctrl / Shift ile birden çok görüntü seçip silebilirsin; silinenler kalıcı yok olmaz,
Geri Dönüşüm Kutusu'na taşınır.

## Kurulum
[Releases](../../releases/latest) sayfasından `AracMerkezi.exe` dosyasını indirip çalıştır.
Uygulama açılışta yeni sürüm olup olmadığına bakar ve otomatik günceller (Ayarlar'dan kapatılabilir).
Kod imzalı olmadığı için Windows SmartScreen ilk açılışta uyarı gösterebilir.

## Geliştirme
```
py -m pip install -e .[dev]
py -m aracmerkezi          # uygulamayı çalıştır
py -m pytest               # testler
py build.py                # dist/AracMerkezi.exe + dist/manifest.json
```
Yeni sürüm: `src/aracmerkezi/__init__.py` içindeki `__version__` değerini artır, `py build.py` çalıştır,
`dist/` içindeki iki dosyayı yeni bir GitHub sürümüne ekle.
