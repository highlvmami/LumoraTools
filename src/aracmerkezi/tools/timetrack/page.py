from __future__ import annotations

from datetime import date, timedelta
from tkinter import messagebox

import customtkinter as ctk

from ... import ui
from ...fmt import duration
from ...ui import StatCard, ghost_button
from . import tracker as tt
from .service import TrackService, get_service

MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
WEEKDAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
REFRESH_MS = 5000
MAX_APPS = 15


def long_date(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}, {WEEKDAYS[d.weekday()]}"


class TimeTrackPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.svc: TrackService = get_service(hub)
        self.day = date.today()
        self.selected_app: str | None = None
        self.enabled_var = ctk.BooleanVar(value=self.svc.enabled)

        ui.page_header(self, "Zaman Takibi", "Hangi programda ne kadar vakit geçirdiğini günlük olarak gör.")
        top = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        top.pack(fill="x")
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkSwitch(row, text="Takibi aç", variable=self.enabled_var, progress_color=ui.OK,
                      command=self.toggle_tracking, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.state = ctk.CTkLabel(row, text="", anchor="w")
        self.state.pack(side="left", padx=14)
        ghost_button(row, "🗑  Verileri sil", self.clear_data, width=120, danger=True).pack(side="right")
        ctk.CTkLabel(top, text="🔒  Yalnızca program adı ve süre bu bilgisayarda saklanır. Pencere başlıkları, belge adları, "
                               "adresler, tuş vuruşları ya da ekran görüntüsü ASLA alınmaz. Takip, LumoraTools açıkken çalışır; "
                               "5 dakika klavye/fare kullanılmazsa 'boşta' sayılır.",
                     text_color=ui.MUTED, anchor="w", justify="left", wraplength=820).pack(fill="x", padx=18, pady=(0, 12))

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", pady=(10, 6))
        ghost_button(nav, "◀", lambda: self.shift(-1), width=40).pack(side="left")
        self.day_label = ctk.CTkLabel(nav, text="", font=ctk.CTkFont(size=15, weight="bold"), width=260)
        self.day_label.pack(side="left", padx=8)
        ghost_button(nav, "▶", lambda: self.shift(1), width=40).pack(side="left")
        ghost_button(nav, "Bugün", self.today, width=80).pack(side="left", padx=10)
        self.ignore_btn = ghost_button(nav, "🚫  Bu programı yok say", self.ignore_selected, width=180)
        self.ignore_btn.pack(side="right")
        self.ignore_btn.configure(state="disabled")

        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x")
        stats.grid_columnconfigure((0, 1, 2), weight=1, uniform="s")
        self.active_card = StatCard(stats, "Aktif süre", "—")
        self.idle_card = StatCard(stats, "Boşta", "—")
        self.top_card = StatCard(stats, "En çok kullanılan", "—")
        self.top_card.value.configure(font=ctk.CTkFont(size=18, weight="bold"))
        for i, c in enumerate((self.active_card, self.idle_card, self.top_card)):
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 7, 0 if i == 2 else 7))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(10, 0))
        body.grid_columnconfigure(0, weight=3, uniform="b")
        body.grid_columnconfigure(1, weight=2, uniform="b")
        body.grid_rowconfigure(0, weight=1)
        self.apps = ctk.CTkScrollableFrame(body, fg_color=ui.CARD, corner_radius=14)
        self.apps.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.apps.grid_columnconfigure(1, weight=1)
        self.week = ctk.CTkScrollableFrame(body, fg_color=ui.CARD, corner_radius=14)
        self.week.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.week.grid_columnconfigure(1, weight=1)

        self.render()
        self.after(REFRESH_MS, self._loop)

    # ---------- döngü ----------
    def _loop(self) -> None:
        if not self.winfo_exists():
            return
        if self.winfo_ismapped() and self.day == date.today():
            self.render()
        self.after(REFRESH_MS, self._loop)

    # ---------- görünüm ----------
    def render(self) -> None:
        self.day_label.configure(text=long_date(self.day) + ("  (bugün)" if self.day == date.today() else ""))
        self.state.configure(text="● Kaydediyor" if self.svc.enabled else "○ Duraklatıldı",
                             text_color=ui.OK if self.svc.enabled else ui.MUTED)
        totals = self.svc.store.totals(self.day.isoformat())
        idle = totals.pop(tt.IDLE, 0.0)
        active = sum(totals.values())
        self.active_card.set(duration(active) if active else "0 dk")
        self.idle_card.set(duration(idle) if idle else "0 dk")
        ranked = sorted(totals.items(), key=lambda kv: -kv[1])
        self.top_card.set(tt.friendly_name(ranked[0][0]) if ranked else "—")
        self._render_apps(ranked, active)
        self._render_week()

    def _clear(self, frame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    def _render_apps(self, ranked, active: float) -> None:
        self._clear(self.apps)
        if not ranked:
            msg = ("Bu gün için kayıt yok." if self.svc.enabled else
                   "Takip kapalı. Üstteki 'Takibi aç' anahtarıyla başlat; veriler birkaç dakika içinde görünmeye başlar.")
            ctk.CTkLabel(self.apps, text=msg, text_color=ui.MUTED, wraplength=380).grid(row=0, column=0, columnspan=3, pady=40, padx=20)
            return
        biggest = ranked[0][1]
        for r, (app, secs) in enumerate(ranked[:MAX_APPS]):
            selected = app == self.selected_app
            widgets = [
                ctk.CTkLabel(self.apps, text=tt.friendly_name(app), anchor="w", width=150,
                             font=ctk.CTkFont(size=13, weight="bold" if selected else "normal")),
                ctk.CTkProgressBar(self.apps, height=12, corner_radius=6,
                                   progress_color=ui.ACCENT if selected else ui.FILE_BAR),
                ctk.CTkLabel(self.apps, text=f"{duration(secs)}  ·  %{secs * 100 / active:.0f}", anchor="e", width=120,
                             text_color=ui.MUTED),
            ]
            widgets[1].set(max(secs / biggest, 0.01))
            for c, w in enumerate(widgets):
                w.grid(row=r, column=c, sticky="ew" if c == 1 else "e" if c == 2 else "w", padx=6, pady=4)
                w.bind("<Button-1>", lambda _e, a=app: self.select(a))
                w.configure(cursor="hand2")

    def _render_week(self) -> None:
        self._clear(self.week)
        ctk.CTkLabel(self.week, text="Son 7 gün (aktif süre)", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 6))
        days = tt.week_days(self.day, 7)
        data = self.svc.store.daily_totals(days[0], days[-1])
        biggest = max(data.values(), default=0.0)
        for r, d in enumerate(days, start=1):
            secs = data.get(d, 0.0)
            day = date.fromisoformat(d)
            ctk.CTkLabel(self.week, text=f"{WEEKDAYS[day.weekday()][:3]} {day.day:02d}.{day.month:02d}", width=70, anchor="w",
                         text_color=ui.TEXT if d == self.day.isoformat() else ui.MUTED).grid(row=r, column=0, padx=(10, 4), pady=3)
            bar = ctk.CTkProgressBar(self.week, height=12, corner_radius=6,
                                     progress_color=ui.ACCENT if d == self.day.isoformat() else ui.FILE_BAR)
            bar.set(secs / biggest if biggest else 0)
            bar.grid(row=r, column=1, sticky="ew", padx=4, pady=3)
            ctk.CTkLabel(self.week, text=duration(secs) if secs else "—", width=70, anchor="e", text_color=ui.MUTED).grid(
                row=r, column=2, padx=(4, 10), pady=3)

    # ---------- eylemler ----------
    def toggle_tracking(self) -> None:
        self.svc.set_enabled(self.enabled_var.get())
        self.render()

    def shift(self, delta: int) -> None:
        self.day = min(date.today(), self.day + timedelta(days=delta))
        self.selected_app = None
        self.ignore_btn.configure(state="disabled")
        self.render()

    def today(self) -> None:
        self.day = date.today()
        self.render()

    def select(self, app: str) -> None:
        self.selected_app = app
        self.ignore_btn.configure(state="normal")
        self.render()

    def ignore_selected(self) -> None:
        app = self.selected_app
        if not app:
            return
        if messagebox.askyesno("Yok say", f"{tt.friendly_name(app)} bundan sonra sayılmasın mı?\n"
                                          "Bu programın şimdiye kadarki kayıtları da silinir."):
            self.svc.add_ignore(app)
            self.svc.store.delete_app(app)
            self.selected_app = None
            self.ignore_btn.configure(state="disabled")
            self.render()

    def clear_data(self) -> None:
        if messagebox.askyesno("Verileri sil", "Tüm zaman takibi kayıtları silinsin mi?\n(Geri alınamaz.)", icon="warning"):
            self.svc.store.clear()
            self.selected_app = None
            self.render()
