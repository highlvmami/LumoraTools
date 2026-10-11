from __future__ import annotations

import customtkinter as ctk

from ... import ui
from ...fmt import human_size
from ...ui import Sparkline, StatCard, ghost_button
from . import sampler as sm

INTERVAL_MS = 1000


class SysInfoPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.sampler = sm.Sampler()
        self.history = sm.History(60)
        self.info = sm.static_info()
        self.last: sm.Sample | None = None
        self.disk_rows: dict[str, tuple[ctk.CTkProgressBar, ctk.CTkLabel]] = {}

        ui.page_header(self, "Sistem Bilgisi", "İşlemci, bellek, disk, ağ ve pil durumunu canlı izle.")
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        stats = ctk.CTkFrame(scroll, fg_color="transparent")
        stats.pack(fill="x")
        stats.grid_columnconfigure((0, 1, 2), weight=1, uniform="s")
        self.cpu_card = StatCard(stats, "İşlemci kullanımı", "—")
        self.mem_card = StatCard(stats, "Bellek kullanımı", "—")
        self.bat_card = StatCard(stats, "Pil", "—")
        for i, c in enumerate((self.cpu_card, self.mem_card, self.bat_card)):
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 7, 0 if i == 2 else 7))
        self.bat_card.value.configure(font=ctk.CTkFont(size=18, weight="bold"), wraplength=230, justify="left")

        charts = ctk.CTkFrame(scroll, fg_color="transparent")
        charts.pack(fill="x", pady=10)
        charts.grid_columnconfigure((0, 1), weight=1, uniform="c")
        self.cpu_chart = self._chart(charts, 0, "İşlemci (son 60 sn)")
        self.mem_chart = self._chart(charts, 1, "Bellek (son 60 sn)")

        card = ctk.CTkFrame(scroll, fg_color=ui.CARD, corner_radius=14)
        card.pack(fill="x")
        ctk.CTkLabel(card, text="Diskler", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=18, pady=(14, 4))
        self.disks = ctk.CTkFrame(card, fg_color="transparent")
        self.disks.pack(fill="x", padx=18, pady=(0, 6))
        self.disks.grid_columnconfigure(1, weight=1)
        self.net_label = ctk.CTkLabel(card, text="", anchor="w", text_color=ui.MUTED)
        self.net_label.pack(fill="x", padx=18, pady=(4, 14))

        details = ctk.CTkFrame(scroll, fg_color=ui.CARD, corner_radius=14)
        details.pack(fill="x", pady=(10, 0))
        head = ctk.CTkFrame(details, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(head, text="Bu bilgisayar", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        self.copy_btn = ghost_button(head, "📋  Özeti kopyala", self.copy_summary, width=140)
        self.copy_btn.pack(side="right")
        for key, value in self.info.items():
            row = ctk.CTkFrame(details, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=1)
            ctk.CTkLabel(row, text=key, text_color=ui.MUTED, width=150, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, anchor="w", justify="left", wraplength=520).pack(side="left", fill="x", expand=True)
        self.status = ctk.CTkLabel(details, text="Bilgisayar ve kullanıcı adı özete eklenmez; paylaşmak güvenlidir.",
                                   text_color=ui.MUTED, anchor="w")
        self.status.pack(fill="x", padx=18, pady=(8, 14))

        self._tick()

    def _chart(self, parent, col: int, title: str) -> Sparkline:
        card = ctk.CTkFrame(parent, fg_color=ui.CARD, corner_radius=14)
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 7, 7 if col == 0 else 0))
        ctk.CTkLabel(card, text=title, text_color=ui.MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(12, 0))
        chart = Sparkline(card, height=70)
        chart.pack(fill="x", padx=12, pady=(4, 12))
        return chart

    # ---------- canlı güncelleme ----------
    def _tick(self) -> None:
        if not self.winfo_exists():                  # tema değişiminde sayfa yıkıldıysa döngü durur
            return
        if self.winfo_ismapped():                    # başka sayfadayken ölçüm yapma
            self._update(self.sampler.sample())
        self.after(INTERVAL_MS, self._tick)

    def _update(self, s: sm.Sample) -> None:
        self.last = s
        self.history.add(s)
        self.cpu_card.set(f"%{s.cpu:.0f}")
        self.mem_card.set(f"%{s.mem_percent:.0f}")
        self.bat_card.set(sm.format_battery(s.battery))
        self.cpu_chart.set_values(self.history.cpu)
        self.mem_chart.set_values(self.history.mem)
        self.net_label.configure(text=f"Ağ:  ↑ {human_size(s.net_up)}/sn      ↓ {human_size(s.net_down)}/sn"
                                      f"      ·   Bellek: {human_size(s.mem_used)} / {human_size(s.mem_total)}"
                                      f"      ·   Takas: %{s.swap_percent:.0f}")
        self._update_disks(s.disks)

    def _update_disks(self, disks) -> None:
        mounts = [d.mount for d in disks]
        if mounts != list(self.disk_rows):           # sürücü kümesi değiştiyse satırları yeniden kur
            for w in self.disks.winfo_children():
                w.destroy()
            self.disk_rows = {}
            for r, d in enumerate(disks):
                ctk.CTkLabel(self.disks, text=d.mount, width=60, anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                    row=r, column=0, sticky="w", pady=3)
                bar = ctk.CTkProgressBar(self.disks, height=14, corner_radius=7)
                bar.grid(row=r, column=1, sticky="ew", padx=10, pady=3)
                label = ctk.CTkLabel(self.disks, text="", width=230, anchor="e", text_color=ui.MUTED)
                label.grid(row=r, column=2, pady=3)
                self.disk_rows[d.mount] = (bar, label)
        for d in disks:
            bar, label = self.disk_rows[d.mount]
            bar.set(d.percent / 100)
            bar.configure(progress_color=ui.DANGER if d.percent >= 90 else ui.WARN if d.percent >= 75 else ui.ACCENT)
            label.configure(text=f"{human_size(d.used)} / {human_size(d.total)}  (%{d.percent:.0f})")

    def copy_summary(self) -> None:
        if self.last is None:
            return
        self.clipboard_clear()
        self.clipboard_append(sm.summary_text(self.info, self.last))
        self.status.configure(text="✓ Özet panoya kopyalandı (bilgisayar ve kullanıcı adı içermez).")
