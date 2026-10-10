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
