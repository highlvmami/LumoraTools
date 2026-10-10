from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from ... import ui
from ...ui import ImageLabel, StatCard, ghost_button, make_tree
from ...date_bar import DateFilterBar
from . import clipboard_io
from .monitor import ClipboardMonitor
from .store import FILES, IMAGE, TEXT, Clip, ClipStore, _human


def get_service(hub) -> tuple[ClipStore, ClipboardMonitor]:
    """Depo ve izleyici hub başına bir kez oluşturulur (sayfa açılmasa da arka planda çalışır)."""
    if "clipboard" not in hub.services:
        store = ClipStore(hub.data_dir / "clipboard.db")
        monitor = ClipboardMonitor(hub, store)
        hub.services["clipboard"] = (store, monitor)

        def close():
            monitor.stop()
            store.close()

        hub.on_close.append(close)
    return hub.services["clipboard"]


class ClipboardPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.store, self.monitor = get_service(hub)
        self.clips: dict[str, Clip] = {}

        ui.page_header(self, "Pano Geçmişi",
                       "Kopyaladığın metinler, görüntüler ve dosyalar burada saklanır. Çift tıkla, tekrar panoya alınır.")

        top = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        top.pack(fill="x")
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 8))
        # placeholder_text, textvariable ile birlikte çalışmaz; bu yüzden olaya bağlıyız
        self.entry = ctk.CTkEntry(row, height=38, corner_radius=10, placeholder_text="🔎  Geçmişte ara…")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<KeyRelease>", lambda _e: self.refresh())
        self.rec_var = ctk.BooleanVar(value=not self.monitor.paused)
        ctk.CTkSwitch(row, text="Kaydediyor", variable=self.rec_var, progress_color=ui.OK,
                      command=self._toggle_recording).pack(side="left", padx=16)
        ghost_button(row, "🗑  Temizle", self._clear, width=100, danger=True).pack(side="left")

        self.date_bar = DateFilterBar(top, on_change=self.refresh)
        self.date_bar.pack(fill="x", padx=16, pady=(0, 14))

        self.stat = StatCard(self, "Kayıtlı öğe", "0")
        self.stat.pack(fill="x", pady=12)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3, uniform="b")
        body.grid_columnconfigure(1, weight=2, uniform="b")
        body.grid_rowconfigure(0, weight=1)

        table = ctk.CTkFrame(body, fg_color=ui.CARD, corner_radius=14)
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.tree = make_tree(table, {"pin": ("", 34), "time": ("Zaman", 96), "text": ("İçerik", 340)})
        self.tree.column("pin", stretch=False)
        self.tree.column("time", stretch=False)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_detail())
        self.tree.bind("<Double-1>", lambda _e: self.copy_selected())
        self.tree.bind("<Return>", lambda _e: self.copy_selected())
        self.tree.bind("<Delete>", lambda _e: self.delete_selected())

        side = ctk.CTkFrame(body, fg_color=ui.CARD, corner_radius=14)
        side.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        # alttan yukarı paketlenir: pencere küçülünce ayrıntı küçülür, düğmeler kırpılmaz
        self.status = ctk.CTkLabel(side, text="", text_color=ui.MUTED, anchor="w", justify="left", wraplength=360)
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 8))
        btns = ctk.CTkFrame(side, fg_color="transparent")
        btns.pack(side="bottom", fill="x", padx=12, pady=(0, 6))
        ctk.CTkButton(btns, text="Kopyala", width=84, fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER,
                      command=self.copy_selected).pack(side="left")
        self.pin_btn = ghost_button(btns, "📌 Sabitle", self.toggle_pin, width=96)
        self.pin_btn.pack(side="left", padx=8)
        ghost_button(btns, "Sil", self.delete_selected, width=60, danger=True).pack(side="left")
        self.image_view = ImageLabel(side, box=(360, 210))      # yalnızca görüntü kayıtlarında gösterilir
        self.detail = ctk.CTkTextbox(side, fg_color="transparent", wrap="word", state="disabled")
        self.detail.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 4))

        ctk.CTkLabel(self, text="Not: Parola yöneticisinden kopyaladıkların ve panodaki görüntüler de kaydedilebilir. "
                                "Gerekirse 'Kaydediyor' anahtarını kapat.", text_color=ui.MUTED,
                     anchor="w").pack(fill="x", pady=(8, 0))

        self.monitor.listeners.append(self._on_new_clip)
        self.refresh()

    # ---------- liste ----------
    def _on_new_clip(self) -> None:
        if self.winfo_exists():
            self.refresh()
        elif self._on_new_clip in self.monitor.listeners:   # sayfa yıkıldı (tema değişimi): kendini çıkar
            self.monitor.listeners.remove(self._on_new_clip)

    def refresh(self) -> None:
        selected = self._selected_id()
        self.tree.delete(*self.tree.get_children())
        self.clips = {}
        since, until = self.date_bar.range()
        for c in self.store.list(self.entry.get(), since=since, until=until):
            iid = str(c.id)
            self.clips[iid] = c
            when = datetime.fromtimestamp(c.ts).strftime("%d.%m %H:%M")
            self.tree.insert("", "end", iid=iid, values=("📌" if c.pinned else "", when, c.label))
        self.stat.set(f"{len(self.clips)} / {self.store.count()}" if len(self.clips) != self.store.count() else self.store.count())
        if selected and selected in self.clips:
            self.tree.selection_set(selected)
        else:
            self._show_detail()

    def _selected_id(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _selected(self) -> Clip | None:
        iid = self._selected_id()
        return self.clips.get(iid) if iid else None

    def _show_detail(self) -> None:
        clip = self._selected()
        self._show_image(clip)
        if clip is None:
            text = "Ayrıntı için listeden bir öğe seç."
        elif clip.kind == IMAGE:
            m = clip.meta
            text = (f"Görüntü  {m.get('w', '?')}×{m.get('h', '?')} px  ·  {_human(m.get('bytes', 0))}\n\n"
                    "'Kopyala' ile görüntüyü panoya geri alıp bir yere yapıştırabilirsin.")
        elif clip.kind == FILES:
            text = "\n".join(p if Path(p).exists() else f"{p}   ⚠ artık yok" for p in clip.paths)
        else:
            text = clip.text
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")
        if clip:
            self.pin_btn.configure(text="📌 Çöz" if clip.pinned else "📌 Sabitle")

    def _show_image(self, clip: Clip | None) -> None:
        """Görüntü kayıtlarında önizlemeyi metnin üstünde gösterir, diğerlerinde gizler."""
        if clip is not None and clip.kind == IMAGE:
            path = self.store.image_path(clip)
            try:
                if path is None:
                    raise OSError("görüntü dosyası yok")
                from PIL import Image
                with Image.open(path) as im:
                    im.load()
                    self.image_view.show(im)
            except Exception:
                self.image_view.clear("Önizlenemiyor (dosya silinmiş olabilir)")
            self.image_view.pack(side="top", fill="x", padx=10, pady=(10, 0), before=self.detail)
        else:
            self.image_view.pack_forget()

    # ---------- eylemler ----------
    def copy_selected(self) -> None:
        clip = self._selected()
        if not clip:
            return
        try:
            if clip.kind == TEXT:
                self.clipboard_clear()
                self.clipboard_append(clip.text)
                note = "✓ Panoya kopyalandı"
            elif clip.kind == IMAGE:
                path = self.store.image_path(clip)
                if path is None:
                    self.status.configure(text="Görüntü dosyası bulunamadı (silinmiş olabilir).")
                    return
                from PIL import Image
                with Image.open(path) as im:
                    im.load()
                    clipboard_io.set_image(im.copy())
                self.monitor.mark_own()               # geçmişe ikinci kez kaydedilmesin
                note = "✓ Görüntü panoya kopyalandı"
            else:
                existing = [p for p in clip.paths if Path(p).exists()]
                if not existing:
                    self.status.configure(text="Dosyalar artık yerlerinde değil.")
                    return
                clipboard_io.set_files(existing)
                self.monitor.mark_own()
                missing = len(clip.paths) - len(existing)
                note = f"✓ {len(existing)} dosya panoya kopyalandı" + (f" ({missing} tanesi artık yok)" if missing else "")
        except (OSError, NotImplementedError) as e:
            self.status.configure(text=f"Kopyalanamadı: {e}")
            return
        self.status.configure(text=note)

    def toggle_pin(self) -> None:
        clip = self._selected()
        if clip:
            self.store.set_pinned(clip.id, not clip.pinned)
            self.refresh()

    def delete_selected(self) -> None:
        clip = self._selected()
        if clip:
            self.store.delete(clip.id)
            self.refresh()

    def _clear(self) -> None:
        if messagebox.askyesno("Temizle", "Sabitlenmemiş tüm pano kayıtları (görüntüler dahil) silinsin mi?\n"
                                          "(Sabitlenenler kalır.)"):
            n = self.store.clear_unpinned()
            self.refresh()
            self.status.configure(text=f"{n} kayıt silindi")

    def _toggle_recording(self) -> None:
        self.monitor.set_paused(not self.rec_var.get())
