from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ... import ui
from ...ui import Spinner, StatCard, ghost_button, make_tree
from .index import Hit, Index


def open_path(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - kullanıcının kendi dosyası
    else:
        subprocess.Popen(["xdg-open", path])


def reveal_path(path: str) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
    else:
        subprocess.Popen(["xdg-open", str(Path(path).parent)])


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


class SearchPage(ctk.CTkFrame):
    DEBOUNCE_MS = 250

    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.cfg = hub.settings_for("arama")
        self.db_path = hub.data_dir / "search.db"
        self.roots: list[str] = list(self.cfg.get("roots", []))
        self.index = Index(self.db_path)
        self.hits: dict[str, Hit] = {}
        self.events: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.indexing = False
        self._debounce: str | None = None

        ui.page_header(self, "Yerel Arama", "Bilgisayarındaki dosyaların içinde anında ara (SQLite FTS5).")
        self.tabs = ctk.CTkTabview(self, fg_color="transparent", segmented_button_selected_color=ui.SEG_ON,
                                   segmented_button_selected_hover_color=ui.SEG_ON_HOVER)
        self.tabs.pack(fill="both", expand=True)
        self._build_search(self.tabs.add("Ara"))
        self._build_index(self.tabs.add("Dizin"))
        self._refresh_roots()
        self._refresh_stats()
        if not self.roots:
            self.tabs.set("Dizin")
        hub.on_close.append(self._shutdown)

    # ---------- Ara sekmesi ----------
    def _build_search(self, tab) -> None:
        bar = ctk.CTkFrame(tab, fg_color=ui.CARD, corner_radius=14)
        bar.pack(fill="x", pady=(4, 10))
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        # placeholder_text, textvariable ile birlikte çalışmaz; bu yüzden olaya bağlıyız
        self.entry = ctk.CTkEntry(row, height=40, corner_radius=10,
                                  placeholder_text="🔎  Dosya içeriklerinde ara…  (ör. bütçe planı)")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<KeyRelease>", lambda _e: self._schedule_search())
        self.count_label = ctk.CTkLabel(row, text="", text_color=ui.MUTED, width=120)
        self.count_label.pack(side="left", padx=(12, 0))

        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=3)
        body.grid_rowconfigure(1, weight=2)

        table = ctk.CTkFrame(body, fg_color=ui.CARD, corner_radius=14)
        table.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.tree = make_tree(table, {"name": ("Dosya", 240), "folder": ("Klasör", 420)})
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_preview())
        self.tree.bind("<Double-1>", lambda _e: self._act(open_path))
        self.empty = ctk.CTkLabel(table, text="", text_color=ui.MUTED)
        self.empty.place(relx=0.5, rely=0.5, anchor="center")
        self._set_empty("Aramaya başlamak için yukarıya yaz.")

        prev = ctk.CTkFrame(body, fg_color=ui.CARD, corner_radius=14)
        prev.grid(row=1, column=0, sticky="nsew")
        self.preview = ctk.CTkTextbox(prev, fg_color="transparent", wrap="word", state="disabled")
        self.preview.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        self.preview.tag_config("hit", background=ui.HIT_BG, foreground=ui.HIT_FG)
        btns = ctk.CTkFrame(prev, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(btns, text="Dosyayı aç", width=100, fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER,
                      command=lambda: self._act(open_path)).pack(side="left")
        ghost_button(btns, "Klasörde göster", lambda: self._act(reveal_path), width=130).pack(side="left", padx=8)

    def _set_empty(self, text: str) -> None:
        if text:
            self.empty.configure(text=text)
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.empty.place_forget()

    def _schedule_search(self) -> None:
        if self._debounce:
            self.after_cancel(self._debounce)
        self._debounce = self.after(self.DEBOUNCE_MS, self.run_search)

    def run_search(self) -> None:
        self._debounce = None
        query = self.entry.get().strip()
        self.tree.delete(*self.tree.get_children())
        self.hits = {}
        self._show_preview()
        if not query:
            self.count_label.configure(text="")
            self._set_empty("Aramaya başlamak için yukarıya yaz.")
            return
        try:
            hits = self.index.search(query)
        except Exception as e:
            self.count_label.configure(text="")
            self._set_empty(f"Arama hatası: {e}")
            return
        for i, h in enumerate(hits):
            iid = str(i)
            self.hits[iid] = h
            p = Path(h.path)
            self.tree.insert("", "end", iid=iid, values=(p.name, str(p.parent)))
        self.count_label.configure(text=f"{len(hits)} sonuç")
        if hits:
            self._set_empty("")
            self.tree.selection_set("0")
        else:
            self._set_empty("Sonuç yok. Dizinde bu klasör var mı? 'Dizin' sekmesine bak.")

    def _selected(self) -> Hit | None:
        sel = self.tree.selection()
        return self.hits.get(sel[0]) if sel else None

    def _show_preview(self) -> None:
        hit = self._selected()
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if hit:
            self.preview.insert("1.0", hit.snippet)
            for s, e in hit.spans:
                self.preview.tag_add("hit", f"1.0+{s}c", f"1.0+{e}c")
        self.preview.configure(state="disabled")

    def _act(self, fn) -> None:
        hit = self._selected()
        if not hit:
            return
        try:
            fn(hit.path)
        except OSError as e:
            messagebox.showerror("Açılamadı", str(e))

    # ---------- Dizin sekmesi ----------
    def _build_index(self, tab) -> None:
        stats = ctk.CTkFrame(tab, fg_color="transparent")
        stats.pack(fill="x", pady=(4, 10))
        stats.grid_columnconfigure((0, 1, 2), weight=1, uniform="s")
        self.stat_files = StatCard(stats, "Dizinlenen dosya")
        self.stat_text = StatCard(stats, "Aranabilir içerik")
        self.stat_size = StatCard(stats, "Dizin boyutu")
        for i, c in enumerate((self.stat_files, self.stat_text, self.stat_size)):
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 7, 0 if i == 2 else 7))

        card = ctk.CTkFrame(tab, fg_color=ui.CARD, corner_radius=14)
        card.pack(fill="both", expand=True)
        self.spinner = Spinner(card)  # dizinleme sürerken kartın ortasında döner
        ctk.CTkLabel(card, text="Dizinlenecek klasörler", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=18, pady=(16, 6))
        self.roots_frame = ctk.CTkScrollableFrame(card, fg_color="transparent", height=120)
        self.roots_frame.pack(fill="both", expand=True, padx=10)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(8, 4))
        ctk.CTkButton(row, text="＋  Klasör ekle", width=120, fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER,
                      command=self.add_root).pack(side="left")
        self.run_btn = ctk.CTkButton(row, text="⟳  Dizinle / güncelle", width=160, fg_color=ui.OK,
                                     hover_color=ui.OK_HOVER, text_color=ui.OK_TEXT, command=self.toggle_index)
        self.run_btn.pack(side="left", padx=8)
        ghost_button(row, "Dizini sıfırla", self.reset_index, width=120, danger=True).pack(side="left")
        self.progress = ctk.CTkLabel(card, text="", text_color=ui.MUTED, anchor="w")
        self.progress.pack(fill="x", padx=18, pady=(2, 4))
        ctk.CTkLabel(card, text="Metin dosyaları, kod, .docx ve .pdf (en fazla 5 MB) dizinlenir. "
                                "Değişmeyen dosyalar tekrar okunmaz, silinenler dizinden düşer.",
                     text_color=ui.MUTED, anchor="w", wraplength=700, justify="left").pack(
            fill="x", padx=18, pady=(0, 14))

    def _refresh_roots(self) -> None:
        for w in self.roots_frame.winfo_children():
            w.destroy()
        if not self.roots:
            ctk.CTkLabel(self.roots_frame, text="Henüz klasör eklenmedi. 'Klasör ekle' ile başla.",
                         text_color=ui.MUTED).pack(anchor="w", padx=8, pady=8)
        for r in self.roots:
            row = ctk.CTkFrame(self.roots_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"📂  {r}", anchor="w").pack(side="left", padx=8)
            ctk.CTkButton(row, text="✕", width=30, height=26, fg_color="transparent", text_color=ui.DANGER,
                          hover_color=ui.DANGER_SOFT, command=lambda p=r: self.remove_root(p)
                          ).pack(side="right", padx=4)

    def _refresh_stats(self) -> None:
        s = self.index.stats()
        self.stat_files.set(s["files"])
        self.stat_text.set(s["searchable"])
        try:
            self.stat_size.set(_human(self.db_path.stat().st_size))
        except OSError:
            self.stat_size.set("0 B")

    def add_root(self) -> None:
        chosen = filedialog.askdirectory(initialdir=str(Path.home()))
        if not chosen:
            return
        path = str(Path(chosen))
        if path not in self.roots:
            self.roots.append(path)
            self.cfg["roots"] = self.roots
            self._refresh_roots()

    def remove_root(self, path: str) -> None:
        if path in self.roots:
            self.roots.remove(path)
            self.cfg["roots"] = self.roots
            self._refresh_roots()

    def reset_index(self) -> None:
        if self.indexing:
            return
        if messagebox.askyesno("Dizini sıfırla", "Tüm dizin silinsin mi? (Dosyalarına dokunulmaz.)"):
            self.index.clear()
            self._refresh_stats()
            self.progress.configure(text="Dizin sıfırlandı.")
            self.run_search()

    def toggle_index(self) -> None:
        if self.indexing:
            self.stop_event.set()
            self.progress.configure(text="Durduruluyor…")
            return
        if not self.roots:
            messagebox.showinfo("Klasör yok", "Önce dizinlenecek en az bir klasör ekle.")
            return
        self.indexing = True
        self.stop_event.clear()
        self.run_btn.configure(text="■  Durdur", fg_color=ui.DANGER, hover_color=ui.DANGER_HOVER, text_color=ui.DANGER_TEXT)
        self.spinner.start("Dosyalar dizinleniyor…")
        roots, db = list(self.roots), self.db_path

        def work():
            idx = Index(db)  # SQLite bağlantısı iş parçacığına bağlıdır, burada ayrı açılır
            try:
                stats = idx.index_roots(roots, progress=lambda a, b, p: self.events.put(("p", a, b, p)),
                                        stop=self.stop_event)
                self.events.put(("done", stats, self.stop_event.is_set()))
            except Exception as e:
                self.events.put(("err", str(e)))
            finally:
                idx.close()

        threading.Thread(target=work, daemon=True).start()
        self.after(200, self._poll_events)

    def _poll_events(self) -> None:
        if not self.winfo_exists():
            return
        finished = False
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            if ev[0] == "p":
                _, scanned, indexed, path = ev
                tail = f"  —  {Path(path).name}" if path else ""
                self.progress.configure(text=f"{scanned} dosya tarandı, {indexed} yeni/güncel{tail}")
            elif ev[0] == "done":
                _, s, stopped = ev
                head = "Durduruldu" if stopped else "Bitti"
                self.progress.configure(
                    text=f"{head}: {s['scanned']} taranan, {s['indexed']} dizinlenen, {s['removed']} kaldırılan.")
                finished = True
            elif ev[0] == "err":
                self.progress.configure(text=f"Hata: {ev[1]}")
                finished = True
        if finished:
            self.indexing = False
            self.spinner.stop()
            self.run_btn.configure(text="⟳  Dizinle / güncelle", fg_color=ui.OK, hover_color=ui.OK_HOVER, text_color=ui.OK_TEXT)
            self._refresh_stats()
            self.run_search()
        else:
            self.after(200, self._poll_events)

    def _shutdown(self) -> None:
        self.stop_event.set()
        self.index.close()
