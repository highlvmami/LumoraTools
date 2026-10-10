from __future__ import annotations

import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from duzenle import engine

from ... import recycle, ui
from ...date_bar import DateFilterBar
from ...ui import ACCENT, ACCENT_HOVER, CARD, MUTED, OK, Spinner, ghost_button, make_tree
from . import library as lib
from .service import ShotService, get_service

SHOW_LIMIT = 3000
PREVIEW_BOX = (400, 220)


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def open_file(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - kullanıcının kendi dosyası
    else:
        subprocess.Popen(["xdg-open", path])


def reveal_file(path: str) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
    else:
        subprocess.Popen(["xdg-open", str(Path(path).parent)])


class ScreenshotsPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.svc: ShotService = get_service(hub)
        self.folder_var = ctk.StringVar(value=str(self.svc.folder))
        fmt_label = next((k for k, v in lib.FORMATS.items() if v == self.svc.date_format), "Yıl / Ay")
        self.format_var = ctk.StringVar(value=fmt_label)
        self.watch_var = ctk.BooleanVar(value=self.svc.watching)
        self.shots: list[lib.Shot] = []
        self.notes: dict[str, str] = self.svc.notes.all()
        self.visible: dict[str, lib.Shot] = {}
        self._token = 0
        self._img = None            # CTkImage referansı (silinmesin)
        self._filter_job: str | None = None
        self._reload_job: str | None = None

        ui.page_header(self, "Ekran Görüntüsü Yöneticisi",
                       "Ekran görüntülerini tarihe göre düzenler; ada, nota ve tarihe göre aranabilir yapar.")
        self._build_top()
        self._build_browser()
        hub.on_close.append(self._shutdown)
        self.after(600, self._poll)
        self.reload()

    # ---------- üst kart: klasör, düzenleme, izleme ----------
    def _build_top(self) -> None:
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        card.pack(fill="x")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkEntry(row, textvariable=self.folder_var, height=36, corner_radius=10,
                     placeholder_text="Ekran görüntüleri klasörü").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Gözat", width=80, height=36, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.browse).pack(side="left", padx=(8, 0))
        ghost_button(row, "Varsayılan klasör", self.use_default, width=130).pack(side="left", padx=(8, 0))
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(row2, text="Klasör düzeni", text_color=MUTED).pack(side="left", padx=(0, 8))
        ctk.CTkSegmentedButton(row2, values=list(lib.FORMATS), variable=self.format_var, height=32,
                               selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                               command=lambda _v: self._settings_changed()).pack(side="left")
        ctk.CTkButton(row2, text="📅  Şimdi tarihe göre düzenle", height=32, fg_color=OK,
                      hover_color=ui.OK_HOVER, command=self.organize_now).pack(side="left", padx=12)
        ghost_button(row2, "↩  Geri al", self.undo, width=100, danger=True).pack(side="left")
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkSwitch(row3, text="Yeni ekran görüntülerini otomatik düzenle (uygulama açıkken arka planda)",
                      variable=self.watch_var, progress_color=OK, command=self.toggle_watch).pack(side="left")
        self.status = ctk.CTkLabel(card, text="", text_color=MUTED, anchor="w", justify="left", wraplength=800)
        self.status.pack(fill="x", padx=18, pady=(0, 12))

    # ---------- arama ve liste ----------
    def _build_browser(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        bar.pack(fill="x", pady=(10, 8))
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(12, 6))
        self.entry = ctk.CTkEntry(row, height=36, corner_radius=10,
                                  placeholder_text="🔎  Ad, not, klasör veya tarih ara  (ör. 11.10.2026)")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<KeyRelease>", lambda _e: self._schedule_filter())
        self.count = ctk.CTkLabel(row, text="", text_color=MUTED, width=170, anchor="e")
        self.count.pack(side="left", padx=(10, 0))
        self.date_bar = DateFilterBar(bar, on_change=self.render)
        self.date_bar.pack(fill="x", padx=16, pady=(0, 8))
        row3 = ctk.CTkFrame(bar, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=(0, 12))
        ghost_button(row3, "☑ Tümünü seç", self.select_all, width=116).pack(side="left")
        ghost_button(row3, "☐ Seçimi kaldır", self.clear_selection, width=126).pack(side="left", padx=6)
        self.sel_label = ctk.CTkLabel(row3, text="Ctrl / Shift ile birden çok görüntü seçebilirsin", text_color=MUTED)
        self.sel_label.pack(side="left", padx=10)
        self.delete_btn = ghost_button(row3, "🗑  Seçilenleri sil", self.delete_selected, width=150, danger=True)
        self.delete_btn.pack(side="right")
        self.delete_btn.configure(state="disabled")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3, uniform="b")
        body.grid_columnconfigure(1, weight=2, uniform="b")
        body.grid_rowconfigure(0, weight=1)

        table = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14)
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.tree = make_tree(table, {"name": ("Ad", 230), "date": ("Tarih", 112), "size": ("Boyut", 70),
                                      "note": ("Not", 150)})
        self.tree.column("date", stretch=False)
        self.tree.column("size", stretch=False, anchor="e")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_preview())
        self.tree.bind("<Double-1>", lambda _e: self._act(open_file))
        self.tree.bind("<Delete>", lambda _e: self.delete_selected())
        self.tree.bind("<Control-a>", lambda _e: (self.select_all(), "break")[1])
        self.empty = ctk.CTkLabel(table, text="", text_color=MUTED)
        self.empty.place(relx=0.5, rely=0.5, anchor="center")
        self.spinner = Spinner(table)

        side = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14)
        side.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        # alttan yukarı paketlenir: pencere küçülünce önizleme küçülür, not ve düğmeler kırpılmaz
        btns = ctk.CTkFrame(side, fg_color="transparent")
        btns.pack(side="bottom", fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(btns, text="Notu kaydet", width=96, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.save_note).pack(side="left")
        ghost_button(btns, "Aç", lambda: self._act(open_file), width=56).pack(side="left", padx=6)
        ghost_button(btns, "Klasörde göster", lambda: self._act(reveal_file), width=120).pack(side="left")
        self.note_entry = ctk.CTkEntry(side, height=34, placeholder_text="📝  Bu görüntü için not…")
        self.note_entry.pack(side="bottom", fill="x", padx=12, pady=(8, 8))
        self.note_entry.bind("<Return>", lambda _e: self.save_note())
        self.detail = ctk.CTkLabel(side, text="", text_color=MUTED, anchor="w", justify="left", wraplength=380)
        self.detail.pack(side="bottom", fill="x", padx=14)
        self.preview = ctk.CTkLabel(side, text="Bir görüntü seç", text_color=MUTED, width=PREVIEW_BOX[0],
                                    height=120)
        self.preview.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 4))

    def _set_empty(self, text: str) -> None:
        if text:
            self.empty.configure(text=text)
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.empty.place_forget()

    def _schedule_filter(self) -> None:
        if self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(200, self.render)

    def reload(self) -> None:
        """Klasörü arka planda yeniden tarar (büyük klasörlerde arayüz donmasın)."""
        folder = self._folder(quiet=True)
        self._token += 1
        token = self._token
        self.tree.delete(*self.tree.get_children())
        self._set_empty("")
        if not folder:
            self.shots = []
            self._set_empty("Geçerli bir klasör seç.")
            self.count.configure(text="")
            return
        self.spinner.start("Görüntüler taranıyor…")

        def work():
            shots = lib.list_shots(folder)
            self.after(0, lambda: self._loaded(token, shots))

        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, token: int, shots: list[lib.Shot]) -> None:
        if token != self._token:
            return
        self.spinner.stop()
        self.shots = shots
        self.notes = self.svc.notes.all()
        self.render()

    def render(self) -> None:
        folder = self._folder(quiet=True)
        if not folder:
            return
        since, until = self.date_bar.range()
        found = lib.filter_shots(self.shots, self.entry.get(), self.notes, folder, since, until)
        self.tree.delete(*self.tree.get_children())
        self.visible = {}
        for i, s in enumerate(found[:SHOW_LIMIT]):
            iid = str(i)
            self.visible[iid] = s
            self.tree.insert("", "end", iid=iid, values=(
                s.path.name, datetime.fromtimestamp(s.mtime).strftime("%d.%m.%Y %H:%M"), human_size(s.size),
                self.notes.get(s.key, "")))
        total = len(self.shots)
        self.count.configure(text=f"{len(found)} / {total} görüntü" if len(found) != total else f"{total} görüntü")
        if not self.shots:
            self._set_empty("Bu klasörde ekran görüntüsü yok.")
        elif not found:
            self._set_empty("Aramaya uyan görüntü yok.")
        else:
            self._set_empty("")
            if len(found) > SHOW_LIMIT:
                self.count.configure(text=f"{len(found)} görüntü (ilk {SHOW_LIMIT})")
            # Kendiliğinden seçim yapılmaz: kullanıcı seçmediği görüntü silinmeye hazır olmasın.
        self._show_preview()

    # ---------- önizleme ve not ----------
    def _selected_list(self) -> list[lib.Shot]:
        return [self.visible[i] for i in self.tree.selection() if i in self.visible]

    def _selected(self) -> lib.Shot | None:
        """Yalnızca tek görüntü seçiliyken o görüntü (not/aç/klasörde göster tek görüntüye uygulanır)."""
        shots = self._selected_list()
        return shots[0] if len(shots) == 1 else None

    def _update_selection_ui(self, shots: list[lib.Shot]) -> None:
        n = len(shots)
        if n:
            self.sel_label.configure(text=f"{n} görüntü seçili ({human_size(sum(s.size for s in shots))})")
        else:
            self.sel_label.configure(text="Ctrl / Shift ile birden çok görüntü seçebilirsin")
        self.delete_btn.configure(text=f"🗑  Seçilenleri sil ({n})" if n else "🗑  Seçilenleri sil",
                                  state="normal" if n else "disabled")

    def select_all(self) -> None:
        self.tree.selection_set(self.tree.get_children())

    def clear_selection(self) -> None:
        self.tree.selection_remove(self.tree.selection())

    def _show_preview(self) -> None:
        shots = self._selected_list()
        self._update_selection_ui(shots)
        shot = self._selected()
        self.note_entry.delete(0, "end")
        if len(shots) > 1:  # çoklu seçim: görüntü yerine özet göster
            self._img = None
            self.preview.configure(image=None, text=f"{len(shots)} görüntü seçili")
            self.detail.configure(text=f"Toplam {human_size(sum(s.size for s in shots))}\n"
                                       "🗑 ile hepsini Geri Dönüşüm Kutusu'na taşıyabilirsin.")
            return
        if not shot:
            self._img = None
            self.preview.configure(image=None, text="Bir görüntü seç")
            self.detail.configure(text="")
            return
        self.note_entry.insert(0, self.notes.get(shot.key, ""))
        try:
            from PIL import Image
            with Image.open(shot.path) as im:
                im.load()
                img = im.convert("RGBA") if im.mode not in ("RGB", "RGBA") else im.copy()
                w, h = img.size
                img.thumbnail(PREVIEW_BOX)
            self._img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.preview.configure(image=self._img, text="")
            dims = f"{w}×{h} px   ·   "
        except Exception:
            self._img = None
            self.preview.configure(image=None, text="Önizlenemiyor")
            dims = ""
        folder = self._folder(quiet=True)
        try:
            where = shot.path.parent.relative_to(folder) if folder else shot.path.parent
        except ValueError:
            where = shot.path.parent
        where_text = "(ana klasör)" if str(where) == "." else str(where)
        self.detail.configure(text=f"{shot.path.name}\n{dims}{human_size(shot.size)}   ·   "
                                   f"{datetime.fromtimestamp(shot.mtime):%d.%m.%Y %H:%M}\n📁 {where_text}")

    def delete_selected(self) -> None:
        """Seçili görüntüleri kalıcı silmek yerine Geri Dönüşüm Kutusu'na taşır (geri yüklenebilir)."""
        shots = self._selected_list()
        if not shots:
            self.status.configure(text="Önce silinecek görüntüleri seç (Ctrl / Shift ile çoklu seçebilirsin).")
            return
        total = human_size(sum(s.size for s in shots))
        if not messagebox.askyesno(
                "Geri Dönüşüm Kutusu'na taşı",
                f"{len(shots)} görüntü ({total}) Geri Dönüşüm Kutusu'na taşınacak.\n\n"
                "Geri Dönüşüm Kutusu'ndan istediğin zaman geri yükleyebilirsin.\nDevam edilsin mi?",
                icon="warning"):
            return
        paths = [s.path for s in shots]
        self.spinner.start("Geri Dönüşüm Kutusu'na taşınıyor…")

        def work():
            try:
                gone, error = recycle.move_to_trash(paths), ""
            except Exception as e:  # Windows dışı, erişim hatası vb.
                gone, error = [], str(e)
            self.after(0, lambda: self._deleted(shots, gone, error))

        threading.Thread(target=work, daemon=True).start()

    def _deleted(self, shots: list[lib.Shot], gone: list[Path], error: str) -> None:
        self.spinner.stop()
        gone_set = set(gone)
        for s in shots:
            if s.path in gone_set:
                self.svc.notes.set(s.key, "")  # silinen görüntünün notu da kalkar
        if error:
            self.status.configure(text=f"Silinemedi: {error}")
        elif len(gone) == len(shots):
            self.status.configure(text=f"🗑 {len(gone)} görüntü Geri Dönüşüm Kutusu'na taşındı "
                                       "(oradan geri yüklenebilir).")
        else:
            self.status.configure(text=f"🗑 {len(gone)} görüntü taşındı; {len(shots) - len(gone)} tanesi "
                                       "taşınamadı (kullanımda olabilir ya da işlem iptal edildi).")
        self.reload()

    def save_note(self) -> None:
        shot = self._selected()
        if not shot:
            return
        text = self.note_entry.get().strip()
        self.svc.notes.set(shot.key, text)
        if text:
            self.notes[shot.key] = text
        else:
            self.notes.pop(shot.key, None)
        sel = self.tree.selection()
        if sel:
            self.tree.set(sel[0], "note", text)
        self.status.configure(text="✓ Not kaydedildi" if text else "Not silindi")

    def _act(self, fn) -> None:
        shot = self._selected()
        if not shot:
            return
        try:
            fn(str(shot.path))
        except OSError as e:
            messagebox.showerror("Açılamadı", str(e))

    # ---------- klasör, düzenleme, izleme ----------
    def _folder(self, quiet: bool = False) -> Path | None:
        folder = Path(self.folder_var.get().strip())
        if folder.is_dir():
            return folder
        if not quiet:
            messagebox.showerror("Klasör bulunamadı", f"Geçerli bir klasör seç:\n{folder}")
        return None

    def browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if chosen:
            self.folder_var.set(str(Path(chosen)))
            self._settings_changed()

    def use_default(self) -> None:
        self.folder_var.set(str(lib.default_folder()))
        self._settings_changed()

    def _settings_changed(self) -> None:
        """Klasör veya düzen değişti: ayarları kaydet, izleme açıksa yeni ayarla yeniden başlat, listeyi yenile."""
        self.svc.cfg["folder"] = self.folder_var.get().strip()
        self.svc.cfg["format"] = lib.FORMATS[self.format_var.get()]
        if self.watch_var.get():
            if not self.svc.start_watch():
                self.watch_var.set(False)
                self.status.configure(text="İzleme başlatılamadı: klasör bulunamadı.")
        self.reload()

    def toggle_watch(self) -> None:
        if self.watch_var.get():
            self.svc.cfg["folder"] = self.folder_var.get().strip()
            self.svc.cfg["format"] = lib.FORMATS[self.format_var.get()]
            if self.svc.start_watch():
                self.status.configure(text=f"İzleniyor: {self.svc.folder}. Yeni görüntüler tarihe göre yerleştirilecek.")
            else:
                self.watch_var.set(False)
                messagebox.showerror("Klasör bulunamadı", f"Geçerli bir klasör seç:\n{self.folder_var.get()}")
        else:
            self.svc.stop_watch()
            self.status.configure(text="Otomatik düzenleme kapatıldı.")

    def organize_now(self) -> None:
        folder = self._folder()
        if not folder:
            return
        fmt = lib.FORMATS[self.format_var.get()]
        moves = lib.plan_organize(folder, fmt)
        if not moves:
            self.status.configure(text="Düzenlenecek yeni görüntü yok: kökteki görüntüler zaten düzenli.")
            return
        root = folder.resolve()
        targets = sorted({str(m.dst.parent.relative_to(root)) for m in moves})
        sample = "\n".join(f"   •  {t}\\" for t in targets[:8]) + (f"\n   … ve {len(targets) - 8} klasör daha" if len(targets) > 8 else "")
        if not messagebox.askyesno("Tarihe göre düzenle",
                                   f"{len(moves)} görüntü şu klasörün içine taşınacak:\n{root}\n\n{sample}\n\n"
                                   "Geri al ile bu işlemi sonra geri alabilirsin.\nDevam edilsin mi?"):
            return
        self.spinner.start("Görüntüler taşınıyor…")

        def work():
            done, failed = engine.apply(folder, moves)
            self.after(0, lambda: self._organized(len(done), len(failed)))

        threading.Thread(target=work, daemon=True).start()

    def _organized(self, done: int, failed: int) -> None:
        self.status.configure(text=f"✓ {done} görüntü taşındı." + (f" {failed} tanesi atlandı (kilitli)." if failed else ""))
        self.reload()

    def undo(self) -> None:
        folder = self._folder()
        if not folder:
            return
        restored, skipped = engine.undo(folder)
        self.status.configure(text="Geri alınacak işlem yok." if not (restored or skipped)
                              else f"↩ {restored} dosya geri alındı, {skipped} atlandı.")
        self.reload()

    # ---------- arka plan izlemenin haberleri ----------
    def _poll(self) -> None:
        got = None
        while True:
            try:
                got = self.svc.messages.get_nowait()
            except Exception:
                break
        if got:
            self.status.configure(text=f"🆕 {got}")
            if self._reload_job:
                self.after_cancel(self._reload_job)
            self._reload_job = self.after(400, self.reload)
        self.after(600, self._poll)

    def _shutdown(self) -> None:
        self._token += 1
