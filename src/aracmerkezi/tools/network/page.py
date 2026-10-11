from __future__ import annotations

import queue
import threading

import customtkinter as ctk

from ... import ui
from ...ui import ghost_button, make_tree
from . import nettools as nt


class NetworkPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.events: queue.Queue = queue.Queue()
        self.conns: list[nt.Connection] = []
        self.listen_var = ctk.BooleanVar(value=True)

        ui.page_header(self, "Ağ Araçları", "Bağlantılarını gör, ping at, DNS sorgula, port kontrol et.")
        self.tabs = ctk.CTkTabview(self, fg_color="transparent", segmented_button_selected_color=ui.SEG_ON,
                                   segmented_button_selected_hover_color=ui.SEG_ON_HOVER)
        self.tabs.pack(fill="both", expand=True)
        self._build_connections(self.tabs.add("Bağlantılar"))
        self._build_ping(self.tabs.add("Ping"))
        self._build_dns(self.tabs.add("DNS"))
        self._build_port(self.tabs.add("Port kontrol"))
        self._build_info(self.tabs.add("Bilgi"))
        self._poll()
        self.refresh_connections()
        self.refresh_info()

    # ---------- ortak: arka plan işi ----------
    def _run(self, kind: str, fn, *args) -> None:
        """`fn`'i arka planda çalıştırıp sonucu ('kind', sonuç) olarak kuyruğa koyar; arayüz donmaz."""
        def work():
            try:
                self.events.put((kind, fn(*args)))
            except Exception as e:
                self.events.put((kind, e))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            getattr(self, f"_on_{kind}")(value)
        self.after(150, self._poll)

    # ---------- bağlantılar ----------
    def _build_connections(self, tab) -> None:
        row = ctk.CTkFrame(tab, fg_color=ui.CARD, corner_radius=12)
        row.pack(fill="x", pady=(4, 8))
        self.conn_entry = ctk.CTkEntry(row, height=34, placeholder_text="🔎  Program, adres ya da port ara…")
        self.conn_entry.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=10)
        self.conn_entry.bind("<KeyRelease>", lambda _e: self._render_connections())
        ctk.CTkSwitch(row, text="Yalnızca dinleyen portlar", variable=self.listen_var, progress_color=ui.ACCENT,
                      command=self._render_connections).pack(side="left", padx=8)
        ghost_button(row, "⟳  Yenile", self.refresh_connections, width=96).pack(side="left", padx=(0, 12))
        self.conn_count = ctk.CTkLabel(tab, text="", text_color=ui.MUTED, anchor="w")
        self.conn_count.pack(side="bottom", fill="x", pady=(6, 0))
        holder = ctk.CTkFrame(tab, fg_color=ui.CARD, corner_radius=14)
        holder.pack(fill="both", expand=True)
        self.conn_tree = make_tree(holder, {"proc": ("Program", 170), "proto": ("Tür", 56), "local": ("Yerel adres", 170),
                                            "remote": ("Uzak adres", 170), "status": ("Durum", 100)})
        self.conn_tree.column("proto", stretch=False)

    def refresh_connections(self) -> None:
        self._run("conns", nt.list_connections)

    def _on_conns(self, value) -> None:
        self.conns = [] if isinstance(value, Exception) else value
        self._render_connections()

    def _render_connections(self) -> None:
        rows = nt.listening(self.conns) if self.listen_var.get() else self.conns
        q = self.conn_entry.get().strip().lower()
        if q:
            rows = [c for c in rows if q in c.process.lower() or q in c.local.lower() or q in c.remote.lower()]
        self.conn_tree.delete(*self.conn_tree.get_children())
        for i, c in enumerate(rows[:1000]):
            self.conn_tree.insert("", "end", iid=str(i), values=(c.process or (f"PID {c.pid}" if c.pid else "—"), c.proto,
                                                                 c.local, c.remote or "—", c.status or "—"))
        self.conn_count.configure(text=f"{len(rows)} kayıt" + (" (ilk 1000 gösteriliyor)" if len(rows) > 1000 else "")
                                  + ("  ·  başka kullanıcıların programlarının adları için yönetici izni gerekir" if self.conns else ""))

    # ---------- ping ----------
    def _host_row(self, tab, button_text: str, command, with_extra=None):
        row = ctk.CTkFrame(tab, fg_color=ui.CARD, corner_radius=12)
        row.pack(fill="x", pady=(4, 8))
        entry = ctk.CTkEntry(row, height=36, placeholder_text="Ana bilgisayar adı ya da IP (ör. google.com, 8.8.8.8)")
        entry.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=12)
        extra = with_extra(row) if with_extra else None
        btn = ctk.CTkButton(row, text=button_text, width=110, height=36, fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER,
                            text_color=ui.ACCENT_TEXT, command=command)
        btn.pack(side="left", padx=(0, 12))
        entry.bind("<Return>", lambda _e: command())
        return entry, extra, btn

    def _build_ping(self, tab) -> None:
        def extra(row):
            ctk.CTkLabel(row, text="Adet", text_color=ui.MUTED).pack(side="left", padx=(0, 4))
            e = ctk.CTkEntry(row, width=50, height=36)
            e.insert(0, "4")
            e.pack(side="left", padx=(0, 10))
            return e
        self.ping_entry, self.ping_count, self.ping_btn = self._host_row(tab, "▶  Ping at", self.start_ping, extra)
        self.ping_out = ctk.CTkTextbox(tab, fg_color=ui.CARD, corner_radius=14, font=ctk.CTkFont(family="Consolas", size=13))
        self.ping_out.pack(fill="both", expand=True)
        self.ping_out.configure(state="disabled")

    def start_ping(self) -> None:
        host = self.ping_entry.get().strip()
        try:
            count = int(self.ping_count.get() or 4)
        except ValueError:
            count = 4
        self._write(self.ping_out, f"{host or '…'} adresine {count} ping atılıyor…\n")
        self.ping_btn.configure(state="disabled")
        self._run("ping", nt.run_ping, host, count)

    def _on_ping(self, r) -> None:
        self.ping_btn.configure(state="normal")
        if isinstance(r, Exception):
            self._write(self.ping_out, f"Hata: {r}\n")
            return
        if r.error:
            self._write(self.ping_out, f"⚠ {r.error}\n")
            return
        lines = [f"{r.host}: {r.sent} gönderildi, {r.received} yanıt, %{r.loss_percent:.0f} kayıp"]
        if r.stats:
            lo, avg, hi = r.stats
            lines.append(f"En az {lo:.0f} ms  ·  ortalama {avg:.0f} ms  ·  en çok {hi:.0f} ms")
            lines.append("Süreler: " + ", ".join(f"{t:.0f} ms" for t in r.times))
        else:
            lines.append("Hiç yanıt gelmedi: bağlantı yok, adres yanlış ya da hedef ping'e kapalı olabilir.")
        self._write(self.ping_out, "\n".join(lines) + "\n")

    # ---------- DNS ----------
    def _build_dns(self, tab) -> None:
        self.dns_entry, _, self.dns_btn = self._host_row(tab, "🔎  Sorgula", self.start_dns)
        self.dns_out = ctk.CTkTextbox(tab, fg_color=ui.CARD, corner_radius=14, font=ctk.CTkFont(family="Consolas", size=13))
        self.dns_out.pack(fill="both", expand=True)
        self.dns_out.configure(state="disabled")

    def start_dns(self) -> None:
        host = self.dns_entry.get().strip()
        self._write(self.dns_out, f"{host or '…'} sorgulanıyor…\n")
        self.dns_btn.configure(state="disabled")

        def work(h):
            res = nt.resolve(h)
            names = {ip: nt.reverse_lookup(ip) for ip in res.addresses[:4]}
            return res, names
        self._run("dns", work, host)

    def _on_dns(self, value) -> None:
        self.dns_btn.configure(state="normal")
        if isinstance(value, Exception):
            self._write(self.dns_out, f"Hata: {value}\n")
            return
        res, names = value
        if res.error:
            self._write(self.dns_out, f"⚠ {res.error}\n")
            return
        lines = [f"{res.host} → {len(res.addresses)} adres  ({res.millis:.0f} ms)"]
        lines += [f"   {ip}" + (f"   ({names[ip]})" if names.get(ip) else "") for ip in res.addresses]
        self._write(self.dns_out, "\n".join(lines) + "\n")

    # ---------- port kontrol ----------
    def _build_port(self, tab) -> None:
        def extra(row):
            ctk.CTkLabel(row, text="Port", text_color=ui.MUTED).pack(side="left", padx=(0, 4))
            e = ctk.CTkEntry(row, width=70, height=36)
            e.insert(0, "443")
            e.pack(side="left", padx=(0, 10))
            return e
        self.port_entry, self.port_port, self.port_btn = self._host_row(tab, "🔌  Dene", self.start_port, extra)
        self.port_out = ctk.CTkTextbox(tab, fg_color=ui.CARD, corner_radius=14, font=ctk.CTkFont(family="Consolas", size=13))
        self.port_out.pack(fill="both", expand=True)
        self.port_out.configure(state="disabled")
        self._write(self.port_out, "Tek bir ana bilgisayar:port'a bağlanıp açık olup olmadığını dener "
                                   "(bir port taraması değildir).\n")

    def start_port(self) -> None:
        host = self.port_entry.get().strip()
        try:
            port = int(self.port_port.get())
        except ValueError:
            self._write(self.port_out, "⚠ Port bir sayı olmalı.\n")
            return
        self._write(self.port_out, f"{host or '…'}:{port} deneniyor…\n")
        self.port_btn.configure(state="disabled")
        self._run("port", nt.check_port, host, port)

    def _on_port(self, r) -> None:
        self.port_btn.configure(state="normal")
        if isinstance(r, Exception):
            self._write(self.port_out, f"Hata: {r}\n")
        elif r.open:
            self._write(self.port_out, f"✓ {r.host}:{r.port} AÇIK  ({r.millis:.0f} ms)\n")
        else:
            self._write(self.port_out, f"✗ {r.host}:{r.port} kapalı ya da ulaşılamıyor: {r.error}\n")

    # ---------- bilgi ----------
    def _build_info(self, tab) -> None:
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", pady=(4, 8))
        ghost_button(top, "⟳  Yenile", self.refresh_info, width=96).pack(side="left")
        holder = ctk.CTkFrame(tab, fg_color=ui.CARD, corner_radius=14)
        holder.pack(fill="both", expand=True)
        self.info_tree = make_tree(holder, {"name": ("Bağdaştırıcı", 200), "state": ("Durum", 70), "speed": ("Hız", 80),
                                            "ipv4": ("IPv4", 140), "mac": ("MAC", 130)})
        self.info_tree.column("state", stretch=False)
        self.info_tree.column("speed", stretch=False)

    def refresh_info(self) -> None:
        self._run("info", nt.adapters)

    def _on_info(self, value) -> None:
        self.info_tree.delete(*self.info_tree.get_children())
        if isinstance(value, Exception):
            return
        for i, a in enumerate(value):
            self.info_tree.insert("", "end", iid=str(i), values=(a.name, "açık" if a.up else "kapalı",
                                                                 f"{a.speed_mbps} Mb/sn" if a.speed_mbps else "—",
                                                                 ", ".join(a.ipv4) or "—", a.mac or "—"))

    @staticmethod
    def _write(box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

