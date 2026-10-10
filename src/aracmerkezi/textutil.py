"""Arama için metin normalizasyonu.

Türkçe harfler tek karakterle ASCII karşılıklarına çevrilir (ç→c, ı→i, İ→i ...),
böylece "çalışma" için "calisma" yazmak da sonuç verir. Dönüşüm karakter başına
1'e 1 olduğu için normalize metindeki konumlar özgün metinde de geçerlidir.
"""

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def fold(text: str) -> str:
    return text.translate(_TR).lower()
