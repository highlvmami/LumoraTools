"""Dosya Düzenleyici aracı: klasörü uzantıya/tarihe göre düzenler, yapısını listeler, izler."""
from __future__ import annotations

import queue
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from duzenle import engine
from duzenle.config import DEFAULT_DATE_FORMAT
from duzenle.watcher import Watcher

from .. import ui
from ..plan_view import Item, PlanView
from ..registry import ToolInfo
from ..structure import build_tree, list_entries
from ..ui import (ACCENT, ACCENT_HOVER, CARD, DANGER, DANGER_HOVER, MUTED, OK, OK_HOVER, Spinner, StatCard,
                  ghost_button)

MODE_LABELS = {"Uzantıya göre": "uzanti", "Tarihe göre": "tarih", "Birleşik": "birlesik",
               "Olduğu gibi": "yapi"}
MODE_HINTS = {
    "uzanti": "Resimler, Belgeler, Videolar… gibi kategorilere ayırır.",
    "tarih": "Dosyayı değiştirilme tarihine göre yıl/ay klasörlerine koyar.",
    "birlesik": "Önce kategori, sonra tarih: Resimler/2026/10",
    "yapi": "Klasör yapısını alt klasörleriyle olduğu gibi listeler; hiçbir dosya taşınmaz.",
}
OPEN_ALL_LIMIT = 400  # bu kadar dosyadan fazlaysa gruplar kapalı başlar
PLAN_COLUMNS = ("size", "here", "dest")


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def fmt_date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


class OrganizerPage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.cfg = hub.settings_for("duzenleyici")
        self.folder_var = ctk.StringVar(value=self.cfg.get("folder", str(Path.home() / "Downloads")))
        mode = self.cfg.get("mode", "Uzantıya göre")
        self.mode_var = ctk.StringVar(value=mode if mode in MODE_LABELS else "Uzantıya göre")
        self.date_var = ctk.StringVar(value=self.cfg.get("date_format", DEFAULT_DATE_FORMAT))
        self.recursive_var = ctk.BooleanVar(value=False)
        self.view: PlanView | None = None
        self.struct: tuple | None = None       # ("Olduğu gibi" modu) (kök, dosyalar, klasörler, kesildi)
        self.root: Path | None = None
        self.expanded: dict[str, bool] = {}
        self.is_new: dict[str, bool] = {}      # hedef klasör yeni mi oluşturulacak, zaten var mı
        self._note = ""
        self._scan_id = 0
        self._filter_job: str | None = None
        self.watcher: Watcher | None = None
        self.messages: queue.Queue[str] = queue.Queue()

        ui.page_header(self, "Dosya Düzenleyici", "Önce önizle, istediklerini seç, sonra tek tıkla yerleştir. Her işlem geri alınabilir.")
        self._folder_card()
        tabs = ctk.CTkTabview(self, fg_color="transparent", segmented_button_selected_color=ACCENT,
                              segmented_button_selected_hover_color=ACCENT_HOVER)
        tabs.pack(fill="both", expand=True, pady=(6, 0))
        self._build_organize(tabs.add("Düzenle"))
        self._build_watch(tabs.add("İzle"))
        self._mode_ui()

        hub.on_close.append(self._shutdown)
        self.after(250, self._drain_messages)

    # ---------- ortak klasör kartı ----------
    def _folder_card(self) -> None:
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        card.pack(fill="x")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkEntry(row, textvariable=self.folder_var, height=38, corner_radius=10,
                     placeholder_text="Düzenlenecek klasör").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Gözat", width=84, height=38, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.browse).pack(side="left", padx=(8, 0))
        ghost_button(row, "İndirilenler", lambda: (self.folder_var.set(str(Path.home() / "Downloads")),
                                                   self._reset_preview()), width=104).pack(side="left", padx=(8, 0))
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkSegmentedButton(row2, values=list(MODE_LABELS), variable=self.mode_var, height=34,
                               selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                               command=self._mode_changed).pack(side="left")
        self.hint = ctk.CTkLabel(row2, text=MODE_HINTS[self._mode_key()], text_color=MUTED)
        self.hint.pack(side="left", padx=14)
        self.date_entry = ctk.CTkEntry(row2, textvariable=self.date_var, width=90, height=30)
        self.date_entry.pack(side="right")
        self.date_entry.bind("<FocusOut>", lambda _e: self._reset_preview())
        ctk.CTkLabel(row2, text="Tarih biçimi", text_color=MUTED).pack(side="right", padx=8)

    # ---------- Düzenle sekmesi ----------
    def _build_organize(self, tab) -> None:
        opts = ctk.CTkFrame(tab, fg_color="transparent")
        opts.pack(fill="x", pady=(4, 0))
        self.preview_btn = ctk.CTkButton(opts, text="🔍  Önizle", width=120, height=36, fg_color=ACCENT,
                                         hover_color=ACCENT_HOVER, command=self.preview)
        self.preview_btn.pack(side="left")
        self.rec_switch = ctk.CTkSwitch(opts, text="Alt klasörleri de tara", variable=self.recursive_var,
                                        progress_color=ACCENT)
        self.rec_switch.pack(side="left", padx=16)
        ghost_button(opts, "↩  Geri al", self.undo, width=110, danger=True).pack(side="right")

        # alt çubuk önce paketlenir: pencere küçülünce liste daralır, bu çubuk kaybolmaz
        foot = ctk.CTkFrame(tab, fg_color="transparent")
        foot.pack(side="bottom", fill="x", pady=(8, 0))
        self.status = ctk.CTkLabel(foot, text="", text_color=MUTED, anchor="w", justify="left", wraplength=560)
        self.status.pack(side="left", fill="x", expand=True)
        self.apply_btn = ctk.CTkButton(foot, text="✓  Seçilenleri düzenle", height=40, width=220,
                                       fg_color=OK, hover_color=OK_HOVER, state="disabled", command=self.apply)
        self.apply_btn.pack(side="right")

        # nereye taşınacağını açıkça söyleyen çubuk
        self.dest_info = ctk.CTkLabel(tab, text="", anchor="w", justify="left", wraplength=800,
                                      text_color=("#3730a3", "#a5b4fc"), font=ctk.CTkFont(size=13, weight="bold"))
        self.dest_info.pack(fill="x", pady=(10, 0))

        bar = ctk.CTkFrame(tab, fg_color=CARD, corner_radius=12)
        bar.pack(fill="x", pady=(6, 8))
        self.filter_entry = ctk.CTkEntry(bar, height=34, corner_radius=8,
                                         placeholder_text="🔎  Filtrele: ad, uzantı veya klasör…")
        self.filter_entry.pack(side="left", fill="x", expand=True, padx=(10, 8), pady=8)
        self.filter_entry.bind("<KeyRelease>", lambda _e: self._schedule_filter())
        self.bulk_buttons = [
            ghost_button(bar, "☑ Görünenleri seç", lambda: self._bulk("select"), width=136),
            ghost_button(bar, "☐ Kaldır", lambda: self._bulk("clear"), width=84),
            ghost_button(bar, "⇄ Ters çevir", lambda: self._bulk("invert"), width=104),
        ]
        self.toggle_btn = ghost_button(bar, "⇕ Aç / kapat", self._toggle_all_groups, width=104)
        for b in (*self.bulk_buttons, self.toggle_btn):
            b.pack(side="left", padx=(0, 6), pady=8)
        self.toggle_btn.pack_configure(padx=(0, 10))

        table_card = ctk.CTkFrame(tab, fg_color=CARD, corner_radius=14)
        table_card.pack(fill="both", expand=True)
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table_card, columns=PLAN_COLUMNS, show="tree headings",
                                 style="Duz.Treeview", selectmode="browse")
        self.tree.column("#0", width=380, anchor="w")
        self.tree.column("size", width=80, anchor="e", stretch=False)
        self.tree.column("here", width=130, anchor="w")
        self.tree.column("dest", width=230, anchor="w")
        self._set_headings(structure=False)
        sb = ctk.CTkScrollbar(table_card, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        sb.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=10)
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<space>", self._on_space)
        self.tree.bind("<<TreeviewOpen>>", lambda _e: self._remember_open(True))
        self.tree.bind("<<TreeviewClose>>", lambda _e: self._remember_open(False))
        self.empty_label = ctk.CTkLabel(table_card, text="Önizle'ye basarak neyin nereye taşınacağını gör.",
                                        text_color=MUTED)
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.spinner = Spinner(table_card)
        self._set_toolbar(False)

    def _set_headings(self, structure: bool) -> None:
        self.tree.column("#0", width=560 if structure else 380)
        if structure:
            self.tree.heading("#0", text="Ad", anchor="w")
            self.tree.heading("size", text="Boyut", anchor="e")
            self.tree.heading("here", text="Değiştirilme", anchor="w")
            self.tree.configure(displaycolumns=("size", "here"))
        else:
            self.tree.heading("#0", text="Dosya   (satıra tıkla: seç / kaldır)", anchor="w")
            self.tree.heading("size", text="Boyut", anchor="e")
            self.tree.heading("here", text="Şu anki yeri", anchor="w")
            self.tree.heading("dest", text="Taşınacağı yer  →", anchor="w")
            self.tree.configure(displaycolumns=PLAN_COLUMNS)

    def _set_toolbar(self, enabled: bool, bulk: bool = True) -> None:
        self.filter_entry.configure(state="normal" if enabled else "disabled")
        for b in self.bulk_buttons:
            b.configure(state="normal" if enabled and bulk else "disabled")
        self.toggle_btn.configure(state="normal" if enabled else "disabled")

    def _mode_ui(self) -> None:
        yapi = self._mode_key() == "yapi"
        self.rec_switch.configure(state="disabled" if yapi else "normal")
        self.preview_btn.configure(text="🔍  Listele" if yapi else "🔍  Önizle")

    # ---------- liste: çizim ve eşitleme (taşıma planı) ----------
    def _style_tags(self) -> None:
        dark = ctk.get_appearance_mode() == "Dark"
        self.tree.tag_configure("group", background="#2a2f45" if dark else "#e0e7ff",
                                font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("on", foreground="#e5e7eb" if dark else "#1f2937")
        self.tree.tag_configure("off", foreground="#6b7280" if dark else "#9ca3af")

    def _group_text(self, name: str, items: list[Item], checked: set[int]) -> str:
        on = sum(it.idx in checked for it in items)
        glyph = "☑" if on == len(items) else "☐" if on == 0 else "▣"
        kind = "yeni klasör" if self.is_new.get(name, True) else "mevcut klasör"
        return f"{glyph}  📂 {name}\\  ({kind})  ·  {on} / {len(items)}"

    @staticmethod
    def _here(it: Item) -> str:
        return "(ana klasör)" if it.src_dir == "." else it.src_dir + "\\"

    def _row_values(self, it: Item, on: bool) -> tuple[str, str, str]:
        """Seçili dosya yeni yerini gösterir; seçilmeyen 'yerinde kalacak' der (taşınmayacağı belli olsun)."""
        dest = "→  " + it.new_rel if on else "yerinde kalacak (taşınmaz)"
        return human_size(it.size), self._here(it), dest

    @staticmethod
    def _group_dest(on: int, total: int) -> str:
        if on == 0:
            return f"{total} dosyanın hiçbiri taşınmayacak"
        return f"←  {on} dosya buraya taşınacak" + (f"  ({total - on} yerinde kalır)" if on < total else "")

    def _render(self) -> None:
        """Planı hedef klasörlere göre gruplayıp baştan çizer (plan veya filtre değişince)."""
        view = self.view
        if view is None:
            return
        self._style_tags()
        self._set_headings(structure=False)
        self.tree.delete(*self.tree.get_children())
        groups = view.groups()
        default_open = sum(len(items) for _, items in groups) <= OPEN_ALL_LIMIT
        for name, items in groups:
            gid = f"g:{name}"
            self.is_new.setdefault(name, not (self.root / name).exists())
            size = sum(it.size for it in items)
            self.tree.insert("", "end", iid=gid, text=self._group_text(name, items, view.checked),
                             values=(human_size(size), "", self._group_dest(len(items), len(items))),
                             open=self.expanded.get(gid, default_open), tags=("group",))
            for it in items:
                self.tree.insert(gid, "end", iid=f"f:{it.idx}", text=f"☑  {it.name}",
                                 values=self._row_values(it, True), tags=("on",))
        self._sync()

    def _sync(self) -> None:
        """Seçim değişince yalnızca metin/renk/özetleri günceller (yeniden çizmeden)."""
        view = self.view
        if view is None:
            return
        for name, items in view.groups():
            gid = f"g:{name}"
            if self.tree.exists(gid):
                on_count = sum(it.idx in view.checked for it in items)
                self.tree.item(gid, text=self._group_text(name, items, view.checked),
                               values=(human_size(sum(it.size for it in items)), "",
                                       self._group_dest(on_count, len(items))))
            for it in items:
                on = it.idx in view.checked
                self.tree.item(f"f:{it.idx}", text=f"{'☑' if on else '☐'}  {it.name}",
                               values=self._row_values(it, on), tags=("on" if on else "off",))
        total, sel = len(view.items), len(view.checked)
        groups = {it.group for it in view.selected_items()}
        new = sum(1 for g in groups if self.is_new.get(g, True))
        self.apply_btn.configure(text=f"✓  Seçilen {sel} dosyayı düzenle" if sel else "✓  Dosya seçilmedi",
                                 state="normal" if sel else "disabled")
        if sel:
            self.dest_info.configure(
                text=f"📍 Taşınacağı yer: {self.root}\\   —   seçilen dosyalar bu klasörün içindeki "
                     f"{len(groups)} alt klasöre taşınır ({new} yeni oluşturulur, {len(groups) - new} zaten var)")
        else:
            self.dest_info.configure(text="📍 Hiçbir dosya seçili değil; taşınacak bir şey yok.")
        text = f"{sel} / {total} dosya seçili ({human_size(view.selected_bytes())})"
        if total - sel:
            text += f"   ·   {total - sel} dosya yerinde kalacak"
        hidden = view.hidden_selected()
        if hidden:
            text += f"   ·   {hidden} seçili dosya filtre nedeniyle gizli (yine de taşınır)"
        if view.query.strip():
            text += f"   ·   {len(view.visible())} dosya gösteriliyor"
        self.status.configure(text=(self._note + "   " if self._note else "") + text)

    # ---------- liste: çizim ("Olduğu gibi" modu) ----------
    def _render_structure(self) -> None:
        if self.struct is None:
            return
        root, files, dirs, truncated = self.struct
        self._style_tags()
        self._set_headings(structure=True)
        self.tree.delete(*self.tree.get_children())
        top = build_tree(root, files, dirs, self.filter_entry.get())
        default_open = top.file_count <= OPEN_ALL_LIMIT

        def add(parent: str, node) -> None:
            for ch in node.children:
                if ch.is_dir:
                    iid = f"d:{ch.path}"
                    self.tree.insert(parent, "end", iid=iid, text=f"📂  {ch.name}   ·   {ch.file_count} dosya",
                                     values=(human_size(ch.size), "", ""), tags=("group",),
                                     open=self.expanded.get(iid, default_open))
                    add(iid, ch)
                else:
                    self.tree.insert(parent, "end", iid=f"x:{ch.path}", text=f"📄  {ch.name}",
                                     values=(human_size(ch.size), fmt_date(ch.mtime), ""), tags=("on",))

        add("", top)
        folders = sum(1 for _ in self._all_nodes() if self.tree.get_children(_) or _.startswith("d:"))
        text = f"{top.file_count} dosya, {folders} klasör ({human_size(top.size)})"
        if truncated:
            text += f"   ·   ilk {len(files)} dosya gösteriliyor (klasör çok büyük)"
        if self.filter_entry.get().strip():
            text += "   ·   filtre uygulandı"
        self.dest_info.configure(text=f"📂 {root}   —   olduğu gibi listeleniyor, hiçbir dosya taşınmaz")
        self.status.configure(text=(self._note + "   " if self._note else "") + text)

    # ---------- liste: etkileşim ----------
    def _on_click(self, event):
        if self.view is None:  # listeleme modunda tıklama yalnızca satırı seçer
            return None
        if self.tree.identify_region(event.x, event.y) not in ("tree", "cell"):
            return None  # başlık vb.
        if "indicator" in self.tree.identify_element(event.x, event.y):
            return None  # aç/kapa oku: Tk'nin kendi davranışı
        iid = self.tree.identify_row(event.y)
        if not iid:
            return None
        self._toggle(iid)
        return "break"

    def _on_space(self, _event):
        iid = self.tree.focus()
        if iid and self.view is not None:
            self._toggle(iid)
        return "break"

    def _toggle(self, iid: str) -> None:
        if iid.startswith("g:"):
            self.view.toggle_group(iid[2:])
        else:
            self.view.toggle(int(iid[2:]))
        self._sync()

    def _remember_open(self, is_open: bool) -> None:
        iid = self.tree.focus()
        if iid.startswith(("g:", "d:")):
            self.expanded[iid] = is_open

    def _all_nodes(self, parent: str = ""):
        for iid in self.tree.get_children(parent):
            yield iid
            yield from self._all_nodes(iid)

    def _toggle_all_groups(self) -> None:
        parents = [i for i in self._all_nodes() if self.tree.get_children(i)]
        if not parents:
            return
        target = not any(self.tree.item(i, "open") for i in parents)
        for i in parents:
            self.tree.item(i, open=target)
            self.expanded[i] = target

    def _bulk(self, kind: str) -> None:
        if self.view is None:
            return
        {"select": lambda: self.view.set_visible(True), "clear": lambda: self.view.set_visible(False),
         "invert": self.view.invert_visible}[kind]()
        self._sync()

    def _schedule_filter(self) -> None:
        if self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(180, self._apply_filter)

    def _apply_filter(self) -> None:
        self._filter_job = None
        if self.view is not None:
            self.view.query = self.filter_entry.get()
            self._render()
        elif self.struct is not None:
            self._render_structure()

    # ---------- davranış ----------
    def _mode_key(self) -> str:
        return MODE_LABELS[self.mode_var.get()]

    def _date_format(self) -> str:
        return self.date_var.get().strip() or DEFAULT_DATE_FORMAT

    def _mode_changed(self, _value=None) -> None:
        self.hint.configure(text=MODE_HINTS[self._mode_key()])
        self._mode_ui()
        self._reset_preview()

    def browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if chosen:
            self.folder_var.set(str(Path(chosen)))
            self._reset_preview()

    def _folder(self) -> Path | None:
        folder = Path(self.folder_var.get().strip())
        if not folder.is_dir():
            messagebox.showerror("Klasör bulunamadı", f"Geçerli bir klasör seç:\n{folder}")
            return None
        return folder

    def _reset_preview(self) -> None:
        self._scan_id += 1          # bekleyen taramanın sonucu artık yok sayılır
        self.spinner.stop()
        self.view = None
        self.struct = None
        self.root = None
        self.expanded.clear()
        self.is_new.clear()
        self._note = ""
        self.tree.delete(*self.tree.get_children())
        self._set_headings(structure=False)
        self.empty_label.configure(text="Önizle'ye basarak neyin nereye taşınacağını gör.")
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.apply_btn.configure(text="✓  Seçilenleri düzenle", state="disabled")
        self.filter_entry.delete(0, "end")
        self._set_toolbar(False)
        self.dest_info.configure(text="📍 Taşınacağı klasör, önizlemeden sonra burada görünecek.")
        self.status.configure(text="")

    def preview(self, note: str = "") -> None:
        folder = self._folder()
        if not folder:
            return
        self._reset_preview()
        sid = self._scan_id
        mode, fmt, rec = self._mode_key(), self._date_format(), self.recursive_var.get()
        self.empty_label.place_forget()
        self.spinner.start("Klasör yapısı okunuyor…" if mode == "yapi" else "Dosyalar taranıyor…")

        def work():
            try:
                if mode == "yapi":
                    data = list_entries(folder)
                    self.after(0, lambda: self._show_structure(sid, folder, data, note))
                    return
                plan = engine.plan(folder, mode, fmt, rec)
                sizes = {}
                for m in plan:
                    try:
                        sizes[m.src] = m.src.stat().st_size
                    except OSError:
                        pass
                self.after(0, lambda: self._show_plan(sid, folder, plan, sizes, note))
            except Exception as e:
                self.after(0, lambda: self._scan_failed(sid, e))

        threading.Thread(target=work, daemon=True).start()

    def _scan_failed(self, sid: int, error: Exception) -> None:
        if sid != self._scan_id:
            return
        self.spinner.stop()
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.status.configure(text=f"Hata: {error}")

    def _show_plan(self, sid: int, folder: Path, plan: list[engine.Move], sizes: dict, note: str) -> None:
        if sid != self._scan_id:
            return
        self.spinner.stop()
        if not plan:
            self.empty_label.configure(text="Düzenlenecek dosya yok. Klasör zaten düzenli görünüyor.")
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self.status.configure(text=(note + "   " if note else "") + "Düzenlenecek dosya yok.")
            return
        self.root = folder.resolve()
        self.view = PlanView(folder, plan, sizes)
        self._note = note
        self._set_toolbar(True)
        self._render()

    def _show_structure(self, sid: int, folder: Path, data: tuple, note: str) -> None:
        if sid != self._scan_id:
            return
        self.spinner.stop()
        files, dirs, truncated = data
        if not files and not dirs:
            self.empty_label.configure(text="Klasör boş.")
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
            return
        self.root = folder
        self.struct = (folder, files, dirs, truncated)
        self._note = note
        self._set_toolbar(True, bulk=False)
        self.apply_btn.configure(text="Yalnızca listeleme (taşıma yok)", state="disabled")
        self._render_structure()

    def apply(self) -> None:
        folder = self._folder()
        if not folder or self.view is None:
            return
        view = self.view
        moves = view.selected_moves()
        if not moves:
            return
        by = Counter(it.group for it in view.selected_items())
        lines = "\n".join(f"   •  {g}\\   ←  {n} dosya" for g, n in sorted(by.items())[:10])
        more = f"\n   … ve {len(by) - 10} klasör daha" if len(by) > 10 else ""
        left = len(view.items) - len(moves)
        msg = (f"Şu klasörün içine taşınacak:\n{self.root}\n\n{lines}{more}\n\n"
               f"Toplam {len(moves)} dosya ({human_size(view.selected_bytes())}).")
        if left:
            msg += f"\n{left} dosya yerinde kalacak."
        msg += "\n\nGeri al ile bu işlemi sonra geri alabilirsin.\nDevam edilsin mi?"
        if not messagebox.askyesno("Taşımayı onayla", msg):
            return
        self.apply_btn.configure(state="disabled")
        self.spinner.start("Dosyalar taşınıyor…")

        def work():
            done, failed = engine.apply(folder, moves)
            self.after(0, lambda: self._applied(len(done), failed))

        threading.Thread(target=work, daemon=True).start()

    def _applied(self, done: int, failed: list) -> None:
        note = f"✓ {done} dosya taşındı."
        if failed:
            note += f" {len(failed)} dosya atlandı (kilitli veya izin yok)."
        self.preview(note=note)  # geride kalanları (seçilmeyenleri) yeniden listeler

    def undo(self) -> None:
        folder = self._folder()
        if not folder:
            return
        restored, skipped = engine.undo(folder)
        self._reset_preview()
        if restored == 0 and skipped == 0:
            self.status.configure(text="Geri alınacak işlem yok.")
        else:
            self.status.configure(text=f"↩ {restored} dosya geri alındı, {skipped} atlandı.")

    # ---------- İzle sekmesi ----------
    def _build_watch(self, tab) -> None:
        card = ctk.CTkFrame(tab, fg_color=CARD, corner_radius=14)
        card.pack(fill="x", pady=(4, 0))
        self.watch_label = ctk.CTkLabel(card, text="Klasör ve mod yukarıdaki seçimle aynıdır.", anchor="w")
        self.watch_label.pack(fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(card, text="Dosya boyutu 3 sn sabit kalınca taşınır; inmekte olan dosyalara dokunulmaz. "
                                "İzleme modunda tüm yeni dosyalar yerleştirilir (seçim listesi yalnızca Düzenle sekmesi içindir).",
                     text_color=MUTED, anchor="w", wraplength=760, justify="left").pack(fill="x", padx=18)
        self.watch_btn = ctk.CTkButton(card, text="▶  İzlemeyi başlat", height=40, fg_color=ACCENT,
                                       hover_color=ACCENT_HOVER, command=self.toggle_watch)
        self.watch_btn.pack(anchor="w", padx=18, pady=16)
        self.watch_count = StatCard(tab, "Bu oturumda yerleştirilen dosya", "0")
        self.watch_count.pack(fill="x", pady=12)
        self.log = ctk.CTkTextbox(tab, fg_color=CARD, corner_radius=14, state="disabled",
                                  font=ctk.CTkFont(family="Consolas", size=12))
        self.log.pack(fill="both", expand=True)

    def toggle_watch(self) -> None:
        if self.watcher and self.watcher.running:
            self.watcher.stop()
            self.watcher = None
            self._watch_ui(False)
            return
        if self._mode_key() == "yapi":
            messagebox.showinfo("İzleme", "İzleme dosya taşır. Yukarıdan 'Uzantıya göre', 'Tarihe göre' "
                                          "veya 'Birleşik' modunu seç; 'Olduğu gibi' yalnızca listeler.")
            return
        folder = self._folder()
        if not folder:
            return
        self.watcher = Watcher(folder, self._mode_key(), self._date_format(), on_message=self.messages.put)
        self.watcher.start()
        self._watch_ui(True)

    def _watch_ui(self, on: bool) -> None:
        if on:
            self.watch_btn.configure(text="■  İzlemeyi durdur", fg_color=DANGER, hover_color=DANGER_HOVER)
            self.watch_label.configure(text=f"İzlenen klasör: {self.folder_var.get()}")
        else:
            self.watch_btn.configure(text="▶  İzlemeyi başlat", fg_color=ACCENT, hover_color=ACCENT_HOVER)
            self.watch_label.configure(text="Klasör ve mod yukarıdaki seçimle aynıdır.")

    def _drain_messages(self) -> None:
        wrote = False
        while True:
            try:
                msg = self.messages.get_nowait()
            except queue.Empty:
                break
            if not wrote:
                self.log.configure(state="normal")
                wrote = True
            self.log.insert("end", msg + "\n")
        if wrote:
            self.log.see("end")
            self.log.configure(state="disabled")
        if self.watcher:
            self.watch_count.set(self.watcher.moved_count)
        self.after(250, self._drain_messages)

    def _shutdown(self) -> None:
        if self.watcher:
            self.watcher.stop()
        self.cfg.update(folder=self.folder_var.get(), mode=self.mode_var.get(), date_format=self._date_format())


TOOL = ToolInfo(
    id="duzenleyici",
    name="Dosya Düzenleyici",
    icon="📁",
    description="Klasörü türe veya tarihe göre düzenler, yapısını olduğu gibi listeler; istediğin dosyaları seçip taşır.",
    build=lambda parent, hub: OrganizerPage(parent, hub),
    order=10,
)
