from __future__ import annotations

import queue
import threading
from tkinter import messagebox

import customtkinter as ctk

from ... import ui
from ...fmt import human_size
from ...ui import Spinner, make_tree
from . import scan as sc


class CleanerPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.cfg = hub.settings_for("temizle")
        self.categories = sc.available(sc.default_categories())
        saved = self.cfg.get("selected")
        self.vars = {c.id: ctk.BooleanVar(value=(c.id in saved) if saved is not None else c.default_on)
                     for c in self.categories}
        self.items: dict[str, sc.ScanItem] = {}
        self.rows: dict[str, dict] = {}
        self.current_id: str | None = None
        self.events: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self._token = 0

        ui.page_header(self, "Sistem Temizleyici",
                       "Geçici dosyaları ve artıkları boyutlarıyla gör; yalnızca seçtiklerini temizle.")
        bar = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        bar.pack(fill="x")
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        self.scan_btn = ctk.CTkButton(row, text="🔍  Tara", width=110, height=38, fg_color=ui.ACCENT,
                                      hover_color=ui.ACCENT_HOVER, text_color=ui.ACCENT_TEXT, command=self.scan)
        self.scan_btn.pack(side="left")
        self.total_label = ctk.CTkLabel(row, text="", anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        self.total_label.pack(side="left", padx=16)
        self.clean_btn = ctk.CTkButton(row, text="🧹  Seçilenleri temizle", height=38, fg_color=ui.DANGER,
                                       hover_color=ui.DANGER_HOVER, text_color=ui.DANGER_TEXT, state="disabled",
                                       command=self.clean)
        self.clean_btn.pack(side="right")
        self.status = ctk.CTkLabel(bar, text="", text_color=ui.MUTED, anchor="w", justify="left", wraplength=820)
        self.status.pack(fill="x", padx=18, pady=(0, 12))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(10, 0))
        body.grid_columnconfigure(0, weight=3, uniform="b")
        body.grid_columnconfigure(1, weight=2, uniform="b")
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color=ui.CARD, corner_radius=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.list.pack(fill="both", expand=True, padx=6, pady=6)
        self.list.grid_columnconfigure(0, weight=1)
        self.spinner = Spinner(left)
        for i, cat in enumerate(self.categories):
            self._build_row(i, cat)

        right = ctk.CTkFrame(body, fg_color=ui.CARD, corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.detail_title = ctk.CTkLabel(right, text="Bir kategori seç", anchor="w", justify="left", wraplength=300,
                                         font=ctk.CTkFont(size=14, weight="bold"))
        self.detail_title.pack(fill="x", padx=14, pady=(12, 0))
        holder = ctk.CTkFrame(right, fg_color="transparent")
        holder.pack(fill="both", expand=True)
        self.tree = make_tree(holder, {"name": ("Dosya", 170), "folder": ("Klasör", 190), "size": ("Boyut", 80)})
        self.tree.column("size", stretch=False, anchor="e")

        hub.on_close.append(self._shutdown)
        self._refresh_totals()
        self.after(300, self.scan)            # sayfa ilk açılınca bir kez otomatik tara

    # ---------- satırlar ----------
    def _build_row(self, i: int, cat: sc.Category) -> None:
        card = ctk.CTkFrame(self.list, fg_color=ui.CARD_ALT, corner_radius=12)
        card.grid(row=i, column=0, sticky="ew", padx=4, pady=4)
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkCheckBox(card, text="", variable=self.vars[cat.id], width=24, command=self._selection_changed
                        ).grid(row=0, column=0, rowspan=2, padx=(14, 4), pady=12)
        name = ctk.CTkLabel(card, text=cat.name, anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        name.grid(row=0, column=1, sticky="w", pady=(10, 0))
        desc = ctk.CTkLabel(card, text=cat.description, anchor="w", justify="left", wraplength=290, text_color=ui.MUTED)
        desc.grid(row=1, column=1, sticky="w", pady=(0, 10))
        size = ctk.CTkLabel(card, text="—", anchor="e", font=ctk.CTkFont(size=15, weight="bold"), width=90)
        size.grid(row=0, column=2, padx=(6, 14), pady=(10, 0), sticky="e")
        info = ctk.CTkLabel(card, text="", anchor="e", text_color=ui.MUTED, font=ctk.CTkFont(size=11), width=90)
        info.grid(row=1, column=2, padx=(6, 14), pady=(0, 10), sticky="e")
        for w in (card, name, desc, size, info):
            w.bind("<Button-1>", lambda _e, c=cat.id: self.show_detail(c))
        self.rows[cat.id] = {"card": card, "size": size, "info": info}

    def _update_row(self, item: sc.ScanItem) -> None:
        row = self.rows[item.category.id]
        row["size"].configure(text=human_size(item.total) if item.total or item.count else "0 B")
        if item.category.method == sc.BIN:
            row["info"].configure(text=f"{item.count:,} öğe")
        else:
            extra = f" · {item.too_young} yeni atlandı" if item.too_young else ""
            row["info"].configure(text=f"{item.count:,} dosya{extra}")

    # ---------- ayrıntı ----------
    def show_detail(self, cat_id: str) -> None:
        self.current_id = cat_id
        for cid, row in self.rows.items():
            row["card"].configure(fg_color=ui.ROW_DRAG if cid == cat_id else ui.CARD_ALT)
        self.tree.delete(*self.tree.get_children())
        item = self.items.get(cat_id)
        cat = next(c for c in self.categories if c.id == cat_id)
        if item is None:
            self.detail_title.configure(text=f"{cat.name}\nhenüz taranmadı")
            return
        if cat.method == sc.BIN:
            self.detail_title.configure(text=f"{cat.name}\n{item.count:,} öğe, {human_size(item.total)}")
            return
        shown = item.files[:300]
        self.detail_title.configure(text=f"{cat.name}\nen büyük {len(shown)} / {item.count:,} dosya")
        for i, f in enumerate(shown):
            self.tree.insert("", "end", iid=str(i),
                             values=(f.path.name, self._relative_folder(cat, f.path), human_size(f.size)))

    @staticmethod
    def _relative_folder(cat: sc.Category, path) -> str:
        """Klasörü kategorinin kök klasörüne göre kısa gösterir ('(kök)' = doğrudan kökte)."""
        for root in cat.roots:
            try:
                rel = path.parent.relative_to(root)
                return "(kök)" if str(rel) == "." else str(rel)
            except ValueError:
                continue
        return str(path.parent)

    # ---------- seçim ve toplamlar ----------
    def _chosen(self) -> list[sc.ScanItem]:
        return [self.items[c.id] for c in self.categories
                if self.vars[c.id].get() and c.id in self.items and (self.items[c.id].count or self.items[c.id].total)]

    def _selection_changed(self) -> None:
        self.cfg["selected"] = [cid for cid, v in self.vars.items() if v.get()]
        self._refresh_totals()

    def _refresh_totals(self) -> None:
        chosen = self._chosen()
        total_all = sum(i.total for i in self.items.values())
        total_sel = sum(i.total for i in chosen)
        if not self.items:
            self.total_label.configure(text="")
        else:
            self.total_label.configure(text=f"Temizlenebilir: {human_size(total_all)}   ·   Seçili: {human_size(total_sel)}")
        self.clean_btn.configure(state="normal" if chosen and not self.busy else "disabled")

    # ---------- tarama ----------
    def scan(self) -> None:
        if self.busy:
            return
        self.busy = True
        self._token += 1
        token = self._token
        self.stop_event.clear()
        self.items.clear()
        for row in self.rows.values():
            row["size"].configure(text="…")
            row["info"].configure(text="")
        self.scan_btn.configure(state="disabled")
        self.clean_btn.configure(state="disabled")
        self.status.configure(text="")
        self.spinner.start("Taranıyor…")
        cats = list(self.categories)

        def work():
            for cat in cats:
                if self.stop_event.is_set():
                    break
                item = sc.scan_category(cat, stop=self.stop_event)
                self.events.put(("item", token, item))
            self.events.put(("scanned", token))

        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._poll)

    # ---------- temizlik ----------
    def clean(self) -> None:
        chosen = self._chosen()
        if not chosen or self.busy:
            return
        groups = {sc.DELETE: [], sc.RECYCLE: [], sc.BIN: []}
        for it in chosen:
            groups[it.category.method].append(it)
        lines = []

        def block(title: str, items: list[sc.ScanItem]) -> None:
            if items:
                lines.append(title)
                lines.extend(f"   •  {i.category.name}: {human_size(i.total)} ({i.count:,})" for i in items)
                lines.append("")

        block("KALICI silinecek (geri alınamaz):", groups[sc.DELETE])
        block("Geri Dönüşüm Kutusu'na taşınacak (geri yüklenebilir):", groups[sc.RECYCLE])
        block("Geri Dönüşüm Kutusu BOŞALTILACAK (kutudaki her şey KALICI silinir):", groups[sc.BIN])
        if not messagebox.askyesno("Temizliği onayla", "\n".join(lines) + "Devam edilsin mi?", icon="warning"):
            return
        self.busy = True
        self._token += 1
        token = self._token
        self.stop_event.clear()
        self.scan_btn.configure(state="disabled")
        self.clean_btn.configure(state="disabled")
        self.spinner.start("Temizleniyor…")

        def work():
            total = sc.CleanResult()
            for it in chosen:
                if self.stop_event.is_set():
                    break
                res = sc.clean(it, stop=self.stop_event)
                total.freed += res.freed
                total.deleted += res.deleted
                total.failed += res.failed
                total.skipped_unsafe += res.skipped_unsafe
            self.events.put(("cleaned", token, total))

        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._poll)

    # ---------- olaylar ----------
    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        finished = rescan = False
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            if ev[1] != self._token:
                continue
            if ev[0] == "item":
                item = ev[2]
                self.items[item.category.id] = item
                self._update_row(item)
            elif ev[0] == "scanned":
                finished = True
            elif ev[0] == "cleaned":
                res = ev[2]
                msg = f"✓ {human_size(res.freed)} boşaltıldı  ·  {res.deleted:,} dosya temizlendi"
                if res.failed:
                    msg += f"  ·  {res.failed:,} dosya atlandı (kullanımda ya da izin yok)"
                if res.skipped_unsafe:
                    msg += f"  ·  {res.skipped_unsafe} yol güvenlik nedeniyle atlandı"
                self.status.configure(text=msg)
                finished = rescan = True
        if finished:
            self.busy = False
            self.spinner.stop()
            self.scan_btn.configure(state="normal")
            self._refresh_totals()
            if self.current_id:
                self.show_detail(self.current_id)
            if rescan:                           # temizlikten sonra güncel durumu göster (mesajı koru)
                message = self.status.cget("text")
                self.busy = False
                self.scan()
                self.status.configure(text=message)
        else:
            self.after(100, self._poll)

    def _shutdown(self) -> None:
        self.stop_event.set()
