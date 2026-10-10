"""Varsayılan kategori eşlemeleri ve atlanacak dosya kuralları."""

CATEGORIES: dict[str, tuple[str, ...]] = {
    "Resimler": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", ".tiff", ".ico"),
    "Belgeler": (".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".csv",
                 ".ppt", ".pptx", ".md"),
    "Videolar": (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"),
    "Muzik": (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"),
    "Arsivler": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"),
    "Kurulumlar": (".exe", ".msi", ".iso", ".apk", ".dmg"),
    "Kod": (".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql"),
}

FALLBACK_CATEGORY = "Diger"

# Henüz inmekte olan veya geçici dosyalar: dokunulmaz.
PARTIAL_EXTENSIONS = {".crdownload", ".part", ".tmp", ".download", ".partial"}

LOG_NAME = ".duzenle_log.json"

MODES = ("uzanti", "tarih", "birlesik")
DEFAULT_DATE_FORMAT = "%Y/%m"


def category_for(extension: str) -> str:
    ext = extension.lower()
    for name, exts in CATEGORIES.items():
        if ext in exts:
            return name
    return FALLBACK_CATEGORY
