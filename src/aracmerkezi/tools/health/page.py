from __future__ import annotations

import queue
import threading

import customtkinter as ctk

from ... import themes, ui
from ...fmt import human_size
from ...ui import Spinner, ghost_button
from . import report as hr

VERDICT_TEXT = {hr.GOOD: "İyi", hr.WARN: "Dikkat", hr.BAD: "Zayıf", hr.UNKNOWN: "Bilinmiyor"}


def verdict_color(verdict: str) -> str:
    return {hr.GOOD: ui.OK, hr.WARN: ui.WARN, hr.BAD: ui.DANGER}.get(verdict, ui.MUTED)


def chip(parent, verdict: str) -> ctk.CTkLabel:
    color = verdict_color(verdict)
    return ctk.CTkLabel(parent, text=VERDICT_TEXT.get(verdict, verdict), fg_color=color, corner_radius=8, height=24,
                        text_color=themes.readable_on(color), font=ctk.CTkFont(size=12, weight="bold"))


def battery_advice(b: hr.BatteryHealth) -> str:
    pct = b.health_percent
    if b.verdict == hr.GOOD:
        return f"Pil, yeni zamanındaki kapasitesinin %{pct:.0f}'ini koruyor: sağlıklı."
    if b.verdict == hr.WARN:
        return (f"Pil, yeni zamanındaki kapasitesinin %{pct:.0f}'ine düşmüş. Günlük kullanıma yeter ama süre kısalıyor; "
                "%60'ın altına inerse pil değişimini düşün.")
    return f"Pil kapasitesi %{pct:.0f}'e inmiş: şarj çabuk bitecektir, değişim önerilir."


class HealthPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.events: queue.Queue = queue.Queue()
        self.loading = False

        ui.page_header(self, "Pil ve Disk Sağlığı", "Pilin ne kadar yıprandığını ve disklerinin sağlık durumunu gör.")
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        ghost_button(top, "⟳  Yenile", self.reload, width=100).pack(side="left")
        self.note = ctk.CTkLabel(top, text="", text_color=ui.MUTED, anchor="w")
        self.note.pack(side="left", padx=12)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, pady=(8, 0))
        self.spinner = Spinner(self)
        self.reload()

    def reload(self) -> None:
        if self.loading:
            return
        self.loading = True
        self.spinner.start("Ölçülüyor… (birkaç saniye sürebilir)")

        def work():
            try:
                import psutil
                try:
                    live = psutil.sensors_battery()
                except Exception:
                    live = None
                self.events.put(("loaded", (hr.battery_report(), live, hr.disk_health(), hr.smart_counters())))
            except Exception as e:
                self.events.put(("error", e))

        threading.Thread(target=work, daemon=True).start()
        self.after(150, self._poll)

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        try:
            kind, value = self.events.get_nowait()
        except queue.Empty:
            self.after(150, self._poll)
            return
        self.loading = False
        self.spinner.stop()
        if kind == "error":
            self.note.configure(text=f"Ölçüm başarısız: {value}")
            return
        self._show(*value)

    # ---------- görünüm ----------
    def _card(self, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self.scroll, fg_color=ui.CARD, corner_radius=14)
        card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(14, 6))
        return card

    @staticmethod
    def _line(parent, key: str, value: str) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=1)
        ctk.CTkLabel(row, text=key, text_color=ui.MUTED, width=180, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=value, anchor="w").pack(side="left")

    def _show(self, battery, live, disks, smart) -> None:
        for w in self.scroll.winfo_children():
            w.destroy()
        self.note.configure(text="")

        card = self._card("🔋  Pil")
        if battery is None:
            msg = ("Bu bilgisayarda pil yok (masaüstü bilgisayar)." if live is None
                   else "Pil raporu alınamadı (Windows raporu üretemedi).")
            ctk.CTkLabel(card, text=msg, text_color=ui.MUTED).pack(anchor="w", padx=18, pady=(0, 16))
        else:
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=18)
            ctk.CTkLabel(head, text=f"%{battery.health_percent:.0f}", font=ctk.CTkFont(size=34, weight="bold")).pack(side="left")
            ctk.CTkLabel(head, text="  sağlık (yeni zamanına göre kapasite)", text_color=ui.MUTED).pack(side="left", pady=(10, 0))
            chip(head, battery.verdict).pack(side="right")
            bar = ctk.CTkProgressBar(card, height=14, corner_radius=7, progress_color=verdict_color(battery.verdict))
            bar.pack(fill="x", padx=18, pady=(6, 8))
            bar.set(min(battery.health_percent, 100) / 100)
            self._line(card, "Tasarım kapasitesi", f"{battery.design_mwh / 1000:.1f} Wh")
            self._line(card, "Şu anki tam şarj kapasitesi", f"{battery.full_mwh / 1000:.1f} Wh")
            self._line(card, "Şarj döngüsü", f"{battery.cycles}" if battery.cycles is not None else "bilinmiyor")
            self._line(card, "Kimya / üretici", f"{battery.chemistry or '—'} / {battery.manufacturer or '—'}")
            if live is not None:
                state = "şarjda" if live.power_plugged else "pilde"
                self._line(card, "Şu anki şarj", f"%{live.percent:.0f} ({state})")
            ctk.CTkLabel(card, text=battery_advice(battery), text_color=ui.MUTED, anchor="w", justify="left",
                         wraplength=700).pack(fill="x", padx=18, pady=(8, 16))

        card = self._card("💽  Diskler")
        if not disks:
            ctk.CTkLabel(card, text="Disk bilgisi alınamadı.", text_color=ui.MUTED).pack(anchor="w", padx=18, pady=(0, 16))
        for i, d in enumerate(disks):
            row = ctk.CTkFrame(card, fg_color=ui.CARD_ALT, corner_radius=10)
            row.pack(fill="x", padx=14, pady=4)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(left, text=d.name, font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(anchor="w")
            extra = ""
            if smart and i < len(smart):
                s = smart[i]
                bits = []
                if s.get("Temperature") is not None:
                    bits.append(f"{s['Temperature']} °C")
                if s.get("Wear") is not None:
                    bits.append(f"aşınma %{s['Wear']}")
                if s.get("PowerOnHours") is not None:
                    bits.append(f"{s['PowerOnHours']:,} saat çalıştı")
                extra = "  ·  " + "  ·  ".join(bits) if bits else ""
            ctk.CTkLabel(left, anchor="w", text_color=ui.MUTED, text=f"{d.media or '—'} · {d.bus or '—'} · "
                                                                       f"{human_size(d.size)} · durum: {d.status or '—'}{extra}").pack(anchor="w")
            chip(row, d.verdict).pack(side="right", padx=12)
        if disks:
            note = ("Ayrıntılı SMART bilgisi (sıcaklık, aşınma, çalışma saati) için LumoraTools'u yönetici olarak çalıştırman "
                    "gerekir; şu an yalnızca genel sağlık durumu okunabiliyor." if not smart else
                    "Sıcaklık, aşınma ve çalışma saati diskin kendi SMART sayaçlarından okundu.")
            ctk.CTkLabel(card, text=note, text_color=ui.MUTED, anchor="w", justify="left", wraplength=700).pack(
                fill="x", padx=18, pady=(8, 16))
