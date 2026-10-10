"""İletişim: istek, şikayet, hata ve geri bildirim gönderme.

Mesaj, herkese açık GitHub deposunun "yeni sorun" sayfasına önceden doldurulmuş olarak açılır;
kullanıcı orada gönder düğmesine basana kadar hiçbir yere gönderilmez.
"""
from __future__ import annotations

import webbrowser

import customtkinter as ctk

from . import __version__, about, ui
from .ui import ghost_button


class ContactPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.kind_var = ctk.StringVar(value=next(iter(about.KINDS)))
        self.info_var = ctk.BooleanVar(value=True)
        ui.page_header(self, "İletişim", "İstek, şikayet, hata ya da geri bildirimini yaz; geliştiriciye ulaştıralım.")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        card = ctk.CTkFrame(scroll, fg_color=ui.CARD, corner_radius=14)
        card.pack(fill="x")
        ctk.CTkLabel(card, text="Konu", text_color=ui.MUTED).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkSegmentedButton(card, values=list(about.KINDS), variable=self.kind_var, height=34,
                               selected_color=ui.SEG_ON, selected_hover_color=ui.SEG_ON_HOVER).pack(anchor="w", padx=18)
        self.title_entry = ctk.CTkEntry(card, height=36, placeholder_text="Kısa başlık (isteğe bağlı)")
        self.title_entry.pack(fill="x", padx=18, pady=(12, 8))
        self.message = ctk.CTkTextbox(card, height=170, fg_color=ui.INPUT_BG, wrap="word")
        self.message.pack(fill="x", padx=18)
        ctk.CTkCheckBox(card, text="Sürüm ve sistem bilgisini ekle", variable=self.info_var,
                        fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER).pack(anchor="w", padx=18, pady=(10, 0))
        ctk.CTkLabel(card, text=f"Eklenecek: {about.system_info(__version__)}  —  kişisel bilgi, dosya yolu veya "
                                "içerik yok.", text_color=ui.MUTED, anchor="w", justify="left",
                     wraplength=720).pack(fill="x", padx=46, pady=(0, 10))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 6))
        ctk.CTkButton(row, text="GitHub'da gönder", height=38, fg_color=ui.OK, hover_color=ui.OK_HOVER, text_color=ui.OK_TEXT,
                      command=self.send_github).pack(side="left")
        ghost_button(row, "Mesajı kopyala", self.copy, width=130).pack(side="left", padx=8)
        if about.CONTACT_EMAIL:
            ghost_button(row, "E-posta ile gönder", self.send_mail, width=150).pack(side="left")
        self.status = ctk.CTkLabel(card, text="", anchor="w", justify="left", wraplength=720)
        self.status.pack(fill="x", padx=18, pady=(2, 4))
        ctk.CTkLabel(card, text="ℹ  'GitHub'da gönder' tarayıcıda hazır doldurulmuş bir sayfa açar; mesaj, o sayfada "
                                "'Submit new issue'ya sen basana kadar kimseye gönderilmez. GitHub hesabı gerekir. "
                                "Mesaj herkese açık olur, bu yüzden kişisel bilgi yazma.",
                     text_color=ui.MUTED, anchor="w", justify="left", wraplength=720).pack(fill="x", padx=18, pady=(0, 16))

        links = ctk.CTkFrame(scroll, fg_color=ui.CARD, corner_radius=14)
        links.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(links, text="Bağlantılar", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=18, pady=(14, 6))
        lrow = ctk.CTkFrame(links, fg_color="transparent")
        lrow.pack(fill="x", padx=18, pady=(0, 14))
        for text, url in (("Açık istek ve hatalar", about.ISSUES_URL), ("Yenilikler / sürümler", about.RELEASES_URL),
                          ("Kaynak kod", about.REPO_URL)):
            ghost_button(lrow, text, lambda u=url: webbrowser.open(u), width=170).pack(side="left", padx=(0, 8))

    def _compose(self) -> tuple[str, str] | None:
        try:
            return about.compose(about.KINDS[self.kind_var.get()], self.title_entry.get(),
                                 self.message.get("1.0", "end"), self.info_var.get(), __version__)
        except about.EmptyMessage as e:
            self.status.configure(text=f"⚠ {e}", text_color=ui.WARN)
            return None

    def send_github(self) -> None:
        composed = self._compose()
        if not composed:
            return
        webbrowser.open(about.issue_url(*composed))
        self.status.configure(text="Tarayıcıda GitHub sayfası açıldı. Göndermek için orada 'Submit new issue'ya bas.",
                              text_color=ui.MUTED)

    def send_mail(self) -> None:
        composed = self._compose()
        if composed:
            webbrowser.open(about.mailto_url(about.CONTACT_EMAIL, *composed))
            self.status.configure(text="E-posta uygulaman açıldı.", text_color=ui.MUTED)

    def copy(self) -> None:
        composed = self._compose()
        if not composed:
            return
        self.clipboard_clear()
        self.clipboard_append(f"{composed[0]}\n\n{composed[1]}")
        self.status.configure(text="✓ Mesaj panoya kopyalandı.", text_color=ui.MUTED)
