"""Araç Merkezi: menüden araç seçilen tek pencereli kabuk."""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from . import __version__, _buildinfo, registry, ui, updater
from .ui import ACCENT, ACCENT_HOVER, BG, CARD, MUTED, OK, SIDEBAR, TEXT


def asset_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "assets" / name

THEMES = {"Koyu": "dark", "Açık": "light", "Sistem": "system"}
NAV_HOVER = ("#d8dbe8", "#1c2030")


class Hub(ctk.CTk):
    def __init__(self, data_dir: Path | None = None, tools: list[registry.ToolInfo] | None = None) -> None:
        super().__init__()
        default_dir = os.environ.get("ARACMERKEZI_HOME") or Path.home() / ".aracmerkezi"
        self.data_dir = Path(data_dir) if data_dir else Path(default_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings = self._load_settings()
        self.tools = tools if tools is not None else registry.discover()
        self.services: dict[str, object] = {}
        self.on_close: list[Callable[[], None]] = []
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.current: str | None = None

        ctk.set_appearance_mode(self.settings.get("theme", "dark"))
        self.title(f"Araç Merkezi  —  v{__version__}")
        self.geometry("1100x720")
        self.minsize(940, 620)
        self.configure(fg_color=BG)
        ui.style_tree()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=26, pady=22)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)  # satır 0: güncelleme çubuğu, satır 1: sayfa
        self._build_update_banner()

        self.upd_events: queue.Queue = queue.Queue()
        self.upd_status = ctk.StringVar(value="")
        self.pending_update: updater.Update | None = None
        self.updating = False

        self.show(self.settings.get("last_page", "home") if self._known(self.settings.get("last_page")) else "home")
        self.after(200, self._start_tools)
        self.after(250, self._set_icon)  # CTk kendi simgesini 200 ms sonra koyar, ondan sonra değiştir
        self.after(300, self._poll_update_events)
        if self.update_cfg.get("check_on_start", True):
            self.after(3000, lambda: self.check_updates(manual=False))
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _set_icon(self) -> None:
        try:
            self.iconbitmap(str(asset_path("icon.ico")))
        except Exception:
            pass  # simge yoksa varsayılan kalır

    # ---------- günlük ----------
    def log(self, name: str, text: str) -> None:
        """Pencereli .exe'de stderr yoktur; hatalar data_dir altındaki günlüğe yazılır."""
        try:
            with open(self.data_dir / f"{name}.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {text}\n")
        except OSError:
            pass

    def report_callback_exception(self, exc, val, tb) -> None:
        import traceback
        self.log("error", "".join(traceback.format_exception(exc, val, tb)))

    # ---------- ayarlar ----------
    def _settings_path(self) -> Path:
        return self.data_dir / "settings.json"

    def _load_settings(self) -> dict:
        try:
            return json.loads(self._settings_path().read_text(encoding="utf-8-sig"))  # BOM'a dayanıklı
        except (OSError, ValueError):
            return {}

    def save_settings(self) -> None:
        try:
            self._settings_path().write_text(json.dumps(self.settings, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
        except OSError:
            pass

    def settings_for(self, tool_id: str) -> dict:
        """Aracın kalıcı ayar sözlüğü (değiştirip kapanışta kaydedilir)."""
        return self.settings.setdefault("tools", {}).setdefault(tool_id, {})

    # ---------- iskelet ----------
    def _known(self, key: str | None) -> bool:
        return key in ("home", "settings") or any(t.id == key for t in self.tools)

    def _build_sidebar(self) -> None:
        bar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=SIDEBAR)
        bar.grid(row=0, column=0, sticky="nsew")
        bar.grid_propagate(False)
        ctk.CTkLabel(bar, text="🧰  Araç Merkezi", font=ctk.CTkFont(size=20, weight="bold")).pack(
            anchor="w", padx=20, pady=(28, 2))
        ctk.CTkLabel(bar, text=f"Sürüm {__version__}", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#3730a3", "#a5b4fc"), fg_color=("#e0e7ff", "#272b4a"), corner_radius=8,
                     height=24).pack(anchor="w", padx=22, pady=(2, 22), ipadx=8)
        self.nav: dict[str, ctk.CTkButton] = {}
        self._nav_button(bar, "home", "🏠  Ana sayfa")
        ctk.CTkLabel(bar, text="ARAÇLAR", text_color=MUTED, font=ctk.CTkFont(size=11, weight="bold")).pack(
            anchor="w", padx=22, pady=(14, 4))
        for t in self.tools:
            self._nav_button(bar, t.id, f"{t.icon}  {t.name}")
        self._nav_button(bar, "settings", "⚙  Ayarlar", bottom=True)

    def _nav_button(self, bar, key: str, label: str, bottom: bool = False) -> None:
        b = ctk.CTkButton(bar, text=label, anchor="w", height=40, corner_radius=10, fg_color="transparent",
                          text_color=TEXT, hover_color=NAV_HOVER, font=ctk.CTkFont(size=14),
                          command=lambda: self.show(key))
        b.pack(fill="x", padx=14, pady=(3, 18) if bottom else 3, side="bottom" if bottom else "top")
        self.nav[key] = b

    def _page_for(self, key: str) -> ctk.CTkFrame:
        if key == "home":
            return self._build_home()
        if key == "settings":
            return self._build_settings()
        tool = next(t for t in self.tools if t.id == key)
        return tool.build(self.content, self)

    def show(self, key: str) -> None:
        if not self._known(key):
            return
        if self.current:
            self.pages[self.current].grid_forget()
            self.nav[self.current].configure(fg_color="transparent", text_color=TEXT)
        if key not in self.pages:
            self.pages[key] = self._page_for(key)
        self.pages[key].grid(row=1, column=0, sticky="nsew")
        self.nav[key].configure(fg_color=ACCENT, text_color="#ffffff")
        self.current = key

    # ---------- sayfalar ----------
    def _build_home(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        ui.page_header(page, "Hoş geldin 👋", "Bir araç seç; hepsi aynı pencerede, aynı temayla çalışır.")
        grid = ctk.CTkFrame(page, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="c")
        for i, t in enumerate(self.tools):
            card = ctk.CTkFrame(grid, fg_color=CARD, corner_radius=16)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=7, pady=7)
            ctk.CTkLabel(card, text=t.icon, font=ctk.CTkFont(size=34)).pack(anchor="w", padx=20, pady=(18, 0))
            ctk.CTkLabel(card, text=t.name, font=ctk.CTkFont(size=18, weight="bold")).pack(
                anchor="w", padx=20, pady=(4, 0))
            ctk.CTkLabel(card, text=t.description, text_color=MUTED, wraplength=360, justify="left").pack(
                anchor="w", padx=20, pady=(2, 10))
            ctk.CTkButton(card, text="Aç", width=90, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          command=lambda k=t.id: self.show(k)).pack(anchor="w", padx=20, pady=(0, 18))
        return page

    def _build_settings(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        ui.page_header(page, "Ayarlar", "Tüm araçlar için ortak görünüm.")
        card = ctk.CTkFrame(page, fg_color=CARD, corner_radius=14)
        card.pack(fill="x")
        ctk.CTkLabel(card, text="Tema").pack(side="left", padx=18, pady=18)
        seg = ctk.CTkSegmentedButton(card, values=list(THEMES), selected_color=ACCENT,
                                     selected_hover_color=ACCENT_HOVER, command=self._theme_changed)
        seg.pack(side="left", padx=8)
        seg.set({v: k for k, v in THEMES.items()}.get(self.settings.get("theme", "dark"), "Koyu"))
        self._build_update_settings(page)
        ctk.CTkLabel(page, text=f"Veriler: {self.data_dir}", text_color=MUTED).pack(anchor="w", pady=12)
        return page

    # ---------- güncelleme ----------
    @property
    def update_cfg(self) -> dict:
        return self.settings.setdefault("update", {})

    def _manifest_url(self) -> str:
        return (self.update_cfg.get("manifest_url") or _buildinfo.UPDATE_URL).strip()

    def _build_update_settings(self, page) -> None:
        card = ctk.CTkFrame(page, fg_color=CARD, corner_radius=14)
        card.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(card, text="Güncelleme", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=18, pady=(16, 2))
        ctk.CTkLabel(card, text=f"Kurulu sürüm: v{__version__}" + ("" if updater.is_frozen()
                     else "   (geliştirme modu: yalnızca denetler, .exe sürümünde kurar)"),
                     text_color=MUTED).pack(anchor="w", padx=18)
        self.url_entry = ctk.CTkEntry(card, height=36, placeholder_text="Manifest adresi (https://…/manifest.json)")
        self.url_entry.pack(fill="x", padx=18, pady=(10, 6))
        if self.update_cfg.get("manifest_url"):
            self.url_entry.insert(0, self.update_cfg["manifest_url"])
        elif _buildinfo.UPDATE_URL:
            self.url_entry.configure(placeholder_text=f"Varsayılan: {_buildinfo.UPDATE_URL}")
        self.url_entry.bind("<FocusOut>", lambda _e: self._save_update_cfg())
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 6))
        self.check_var = ctk.BooleanVar(value=self.update_cfg.get("check_on_start", True))
        self.auto_var = ctk.BooleanVar(value=self.update_cfg.get("auto_install", True))
        ctk.CTkSwitch(row, text="Açılışta denetle", variable=self.check_var, progress_color=ACCENT,
                      command=self._save_update_cfg).pack(side="left")
        ctk.CTkSwitch(row, text="Bulunca otomatik kur", variable=self.auto_var, progress_color=ACCENT,
                      command=self._save_update_cfg).pack(side="left", padx=18)
        ctk.CTkButton(row, text="Şimdi denetle", width=120, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=lambda: (self._save_update_cfg(), self.check_updates(manual=True))).pack(side="right")
        ctk.CTkLabel(card, textvariable=self.upd_status, text_color=MUTED, anchor="w").pack(
            fill="x", padx=18, pady=(0, 14))

    def _save_update_cfg(self) -> None:
        self.update_cfg.update(manifest_url=self.url_entry.get().strip(), check_on_start=self.check_var.get(),
                               auto_install=self.auto_var.get())

    def _build_update_banner(self) -> None:
        self.banner = ctk.CTkFrame(self.content, fg_color=("#e0e7ff", "#272b4a"), corner_radius=12)
        self.banner_label = ctk.CTkLabel(self.banner, text="", anchor="w")
        self.banner_label.pack(side="left", padx=16, pady=10)
        self.banner_btn = ctk.CTkButton(self.banner, text="", width=130, height=30, fg_color=ACCENT,
                                        hover_color=ACCENT_HOVER)
        self.banner_btn.pack(side="right", padx=12)
        # banner başta gizli (grid ile sadece gerektiğinde gösterilir)

    def _show_banner(self, text: str, button: str | None, command=None) -> None:
        self.banner_label.configure(text=text)
        if button:
            self.banner_btn.configure(text=button, command=command)
            self.banner_btn.pack(side="right", padx=12)
        else:
            self.banner_btn.pack_forget()
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 12))

    def check_updates(self, manual: bool) -> None:
        if self.updating:
            return
        url = self._manifest_url()
        if not url:
            if manual:
                self.upd_status.set("Önce bir manifest adresi gir.")
            return
        if manual:
            self.upd_status.set("Denetleniyor…")

        def work():
            try:
                update = updater.check(url, __version__)
                self.upd_events.put(("found", update, manual))
            except Exception as e:
                self.upd_events.put(("error", str(e), manual))

        threading.Thread(target=work, daemon=True).start()

    def install_update(self) -> None:
        update = self.pending_update
        if not update or self.updating:
            return
        if not updater.is_frozen():
            self.upd_status.set(f"v{update.version} bulundu. Geliştirme modunda kurulmaz, .exe sürümü kurar.")
            return
        self.updating = True
        self._show_banner(f"v{update.version} indiriliyor…", None)

        def progress(done: int, total: int) -> None:
            if total:
                self.upd_events.put(("progress", done * 100 // total))

        def work():
            try:
                updater.install(update, progress=progress)
                self.upd_events.put(("installed", update))
            except Exception as e:
                self.upd_events.put(("error", str(e), True))

        threading.Thread(target=work, daemon=True).start()

    def restart_app(self) -> None:
        exe = updater.current_exe()
        self._close()
        updater.restart(exe)

    def _poll_update_events(self) -> None:
        while True:
            try:
                ev = self.upd_events.get_nowait()
            except queue.Empty:
                break
            kind = ev[0]
            if kind == "found":
                _, update, manual = ev
                self.log("update", f"denetim: {'yeni v' + update.version if update else 'güncel'}")
                if update is None:
                    if manual:
                        self.upd_status.set(f"Güncelsin (v{__version__}).")
                    continue
                self.pending_update = update
                self.upd_status.set(f"Yeni sürüm var: v{update.version}")
                if self.auto_var_value() and updater.is_frozen():
                    self.install_update()
                else:
                    self._show_banner(f"Yeni sürüm var: v{update.version}"
                                      + ("" if updater.is_frozen() else "  (.exe sürümünde kurulur)"),
                                      "Güncelle" if updater.is_frozen() else None, self.install_update)
            elif kind == "progress":
                self.banner_label.configure(text=f"v{self.pending_update.version} indiriliyor… %{ev[1]}")
            elif kind == "installed":
                self.log("update", f"v{ev[1].version} kuruldu")
                self.updating = False
                self.upd_status.set(f"v{ev[1].version} kuruldu.")
                self._show_banner(f"v{ev[1].version} kuruldu. Yeniden başlatınca geçerli olur.",
                                  "Şimdi yeniden başlat", self.restart_app)
            elif kind == "error":
                _, msg, manual = ev
                self.log("update", f"hata: {msg}")
                self.updating = False
                self.banner.grid_remove()
                if manual:
                    self.upd_status.set(f"Hata: {msg}")
        self.after(300, self._poll_update_events)

    def auto_var_value(self) -> bool:
        return bool(self.update_cfg.get("auto_install", True))

    def _theme_changed(self, label: str) -> None:
        self.settings["theme"] = THEMES[label]
        ctk.set_appearance_mode(THEMES[label])
        ui.style_tree()

    # ---------- yaşam döngüsü ----------
    def _start_tools(self) -> None:
        for t in self.tools:
            if t.start:
                try:
                    t.start(self)
                except Exception as e:
                    print(f"{t.name} başlatılamadı: {e}")

    def _close(self) -> None:
        for fn in self.on_close:
            try:
                fn()
            except Exception as e:
                print(f"Kapanış hatası: {e}")
        if self.current:
            self.settings["last_page"] = self.current
        self.save_settings()
        self.destroy()


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--selftest"]:
        # Pencere açmadan paketin sağlam olduğunu doğrular (.exe'yi test etmek için).
        tools = registry.discover()
        report = (f"version={__version__}\nfrozen={updater.is_frozen()}\n"
                  f"tools={','.join(t.id for t in tools)}\n"
                  f"errors={' | '.join(registry.load_errors) or '-'}\n")
        if len(argv) > 1:
            Path(argv[1]).write_text(report, encoding="utf-8")
        else:
            print(report)
        return
    if updater.is_frozen():
        updater.cleanup_old(updater.current_exe())  # önceki güncellemeden kalan .old dosyası
    Hub().mainloop()


if __name__ == "__main__":
    main()
