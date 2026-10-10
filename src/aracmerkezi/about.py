"""Proje bağlantıları ve geri bildirim mesajının hazırlanması (Tk'den bağımsız, test edilebilir).

Geri bildirim, herkese açık GitHub deposunun "yeni sorun" sayfasına önceden doldurulmuş olarak
açılır; mesaj, kullanıcı o sayfada gönder düğmesine basana kadar hiçbir yere gönderilmez.
"""
from __future__ import annotations

import platform
import urllib.parse

REPO_URL = "https://github.com/highlvmami/LumoraTools"
ISSUES_URL = REPO_URL + "/issues"
NEW_ISSUE_URL = ISSUES_URL + "/new"
RELEASES_URL = REPO_URL + "/releases"
CONTACT_EMAIL = ""  # doldurulursa İletişim sayfasında "E-posta ile gönder" düğmesi çıkar; boşsa gösterilmez

KINDS = {"💡 İstek": "İstek", "⚠ Şikayet": "Şikayet", "🐞 Hata": "Hata", "💬 Geri bildirim": "Geri bildirim",
         "Diğer": "Diğer"}
MAX_BODY = 5000  # çok uzun bağlantılar tarayıcıda/sunucuda kesilebilir


class EmptyMessage(ValueError):
    pass


def system_info(version: str) -> str:
    """Kişisel bilgi içermeyen sürüm ve işletim sistemi satırı."""
    return f"LumoraTools v{version} · {platform.platform()}"


def compose(kind: str, title: str, message: str, include_info: bool, version: str) -> tuple[str, str]:
    """(başlık, gövde) üretir. Mesaj boşsa EmptyMessage fırlatır."""
    message = message.strip()
    if not message:
        raise EmptyMessage("Önce mesajını yaz.")
    full_title = f"[{kind}] {title.strip() or message.splitlines()[0][:60]}"
    body = message
    if include_info:
        body += f"\n\n---\n{system_info(version)}"
    return full_title, body


def issue_url(title: str, body: str) -> str:
    query = urllib.parse.urlencode({"title": title, "body": body[:MAX_BODY]}, quote_via=urllib.parse.quote)
    return f"{NEW_ISSUE_URL}?{query}"


def mailto_url(email: str, title: str, body: str) -> str:
    query = urllib.parse.urlencode({"subject": title, "body": body[:MAX_BODY]}, quote_via=urllib.parse.quote)
    return f"mailto:{email}?{query}"
