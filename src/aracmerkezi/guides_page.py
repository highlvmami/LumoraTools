"""Rehberler: her araç için kısa kullanım anlatımı."""
from __future__ import annotations

import customtkinter as ctk

from . import ui
from .registry import Guide

GENERAL = Guide(
    summary="LumoraTools'un menü, tema ve güncelleme ayarları.",
    steps=(
        "Soldaki menüden araç seçersin; hepsi aynı pencerede, aynı temayla çalışır.",
        "Ayarlar → 'Menüyü düzenle': araçları ⠿ tutamacından sürükleyerek sırala, anahtarla menüden gizle veya göster.",
        "Ayarlar → 'Tema': 12 temadan birine tıkla (Gece, Gündüz, Okyanus, Orman, Lavanta, AMOLED…); uygulama hemen yeni renklere geçer. 'Sistem' Windows'un koyu/açık ayarını izler.",
        "Uygulama güncellenince 'Yenilikler' penceresi neyin değiştiğini gösterir; Ayarlar → Güncelleme → 'Yenilikler' ile istediğin zaman açabilirsin.",
        "Güncellemeler açılışta denetlenir ve otomatik kurulur; Ayarlar → 'Güncelleme' bölümünden kapatabilirsin. "
        "Pencere başlığında ve kenar çubuğunda kurulu sürümü görürsün.",
        "Bir isteğin, şikayetin ya da hatan varsa 'İletişim' sayfasından bildirebilirsin.",
    ),
)


class GuidesPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        ui.page_header(self, "Rehberler", "Her aracın kısa kullanım anlatımı. İlgili araca tek tıkla geçebilirsin.")
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        for tool in hub.tools:
            guide = tool.guide or Guide(summary=tool.description, steps=())
            self._card(scroll, f"{tool.icon}  {tool.name}", guide, open_key=tool.id)
        self._card(scroll, "🧭  Menü ve ayarlar", GENERAL, open_key="settings", open_text="Ayarları aç")

    def _card(self, parent, title: str, guide: Guide, open_key: str, open_text: str = "Aracı aç") -> None:
        card = ctk.CTkFrame(parent, fg_color=ui.CARD, corner_radius=14)
        card.pack(fill="x", pady=(0, 12))
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(14, 0))
        ctk.CTkLabel(head, text=title, font=ctk.CTkFont(size=17, weight="bold")).pack(side="left")
        ctk.CTkButton(head, text=f"{open_text} →", width=110, height=30, fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER,
                      command=lambda: self.hub.show(open_key)).pack(side="right")
        ctk.CTkLabel(card, text=guide.summary, text_color=ui.MUTED, anchor="w", justify="left",
                     wraplength=720).pack(fill="x", padx=18, pady=(2, 8))
        for i, step in enumerate(guide.steps, 1):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=2)
            ctk.CTkLabel(row, text=str(i), width=24, height=24, corner_radius=12, fg_color=ui.ACCENT,
                         text_color=ui.ACCENT_TEXT, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", anchor="n")
            ctk.CTkLabel(row, text=step, anchor="w", justify="left", wraplength=690).pack(
                side="left", fill="x", expand=True, padx=(10, 0))
        for tip in guide.tips:
            ctk.CTkLabel(card, text=f"💡  {tip}", text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=720).pack(fill="x", padx=18, pady=(4, 0))
        ctk.CTkFrame(card, height=12, fg_color="transparent").pack()
