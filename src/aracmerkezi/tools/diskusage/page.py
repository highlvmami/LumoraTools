from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ... import ui
from ...ui import Spinner, ghost_button, make_tree
from . import scan as du



def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def reveal(path: str, select: bool) -> None:
    if sys.platform == "win32":
        if select:
            subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
        else:
            os.startfile(path)  # noqa: S606 - kullanıcının kendi klasörü
    else:
        subprocess.Popen(["xdg-open", path if not select else str(Path(path).parent)])


class DiskUsagePage(ctk.CTkFrame):
    def __init__(self, parent, hub) -> None:
        super().__init__(parent, fg_color="transparent")
        self.hub = hub
        self.cfg = hub.settings_for("boyut")
        self.folder_var = ctk.StringVar(value=self.cfg.get("folder", str(Path.home())))
        self.result: du.ScanResult | None = None
        self.stack: list[du.DirNode] = []        # açılan klasörlerin yolu (son eleman geçerli klasör)
        self.events: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.scanning = False
        self._scan_token = 0

        ui.page_header(self, "Klasör Boyut Analizcisi",
                       "Diskte yeri en çok kimin kapladığını gör. Çubuğa tıklayarak klasörün içine gir. Hiçbir şey silinmez.")
        card = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=14)
        card.pack(fill="x")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        ctk.CTkEntry(row, textvariable=self.folder_var, height=38, corner_radius=10,
                     placeholder_text="Analiz edilecek klasör").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Gözat", width=84, height=38, fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER,
                      command=self.browse).pack(side="left", padx=(8, 0))
        ghost_button(row, "Ev klasörüm", lambda: self.folder_var.set(str(Path.home())), width=110
                     ).pack(side="left", padx=(8, 0))
        self.run_btn = ctk.CTkButton(row, text="📊  Analiz et", width=120, height=38, fg_color=ui.ACCENT,
                                     hover_color=ui.ACCENT_HOVER, command=self.toggle_scan)
        self.run_btn.pack(side="left", padx=(8, 0))
        self.progress = ctk.CTkLabel(card, text="", text_color=ui.MUTED, anchor="w")
        self.progress.pack(fill="x", padx=18, pady=(0, 12))

        self.tabs = ctk.CTkTabview(self, fg_color="transparent", segmented_button_selected_color=ui.SEG_ON,
                                   segmented_button_selected_hover_color=ui.SEG_ON_HOVER)
        self.tabs.pack(fill="both", expand=True, pady=(6, 0))
        self._build_folders(self.tabs.add("Klasörler"))
        self._build_largest(self.tabs.add("En büyük dosyalar"))
        hub.on_close.append(self._shutdown)

    # ---------- Klasörler sekmesi ----------
    def _build_folders(self, tab) -> None:
        nav = ctk.CTkFrame(tab, fg_color="transparent")
        nav.pack(fill="x", pady=(2, 6))
        self.up_btn = ghost_button(nav, "⬆  Üst klasör", self.go_up, width=120)
        self.up_btn.pack(side="left")
        self.up_btn.configure(state="disabled")
        self.crumb = ctk.CTkLabel(nav, text="", anchor="w", font=ctk.CTkFont(size=13, weight="bold"),
                                  wraplength=520, justify="left")
        self.crumb.pack(side="left", padx=12, fill="x", expand=True)
        self.open_btn = ghost_button(nav, "📂  Explorer'da aç", self.open_current, width=140)
        self.open_btn.pack(side="right")
        self.open_btn.configure(state="disabled")
        self.summary = ctk.CTkLabel(tab, text="", text_color=ui.MUTED, anchor="w")
        self.summary.pack(fill="x", pady=(0, 6))
        holder = ctk.CTkFrame(tab, fg_color=ui.CARD, corner_radius=14)
        holder.pack(fill="both", expand=True)
        self.list = ctk.CTkScrollableFrame(holder, fg_color="transparent")
        self.list.pack(fill="both", expand=True, padx=6, pady=6)
        self.list.grid_columnconfigure(1, weight=1)
        self.empty = ctk.CTkLabel(self.list, text="Bir klasör seçip 'Analiz et'e bas.", text_color=ui.MUTED)
        self.empty.grid(row=0, column=0, columnspan=4, pady=40)
        self.spinner = Spinner(holder)

    def _clear_rows(self) -> None:
        for w in self.list.winfo_children():
            w.destroy()

    def _show_node(self) -> None:
        """Geçerli klasörün içeriğini boyuta göre sıralı çubuklarla çizer."""
        self._clear_rows()
        node = self.stack[-1]
        self.up_btn.configure(state="normal" if len(self.stack) > 1 else "disabled")
        self.open_btn.configure(state="normal")
        self.crumb.configure(text=str(node.path))
        self.summary.configure(
            text=f"Toplam {human_size(node.size)}   ·   {node.file_count:,} dosya   ·   {len(node.dirs)} alt klasör")
        shown, rest_count, rest_size = du.rows(node)
        if not shown and not rest_count:
            ctk.CTkLabel(self.list, text="Bu klasör boş.", text_color=ui.MUTED).grid(row=0, column=0, pady=30, padx=20)
            return
        biggest = max([s for _, _, s, _ in shown] + [rest_size, 1])
        total = max(node.size, 1)
        for i, (kind, name, size, child) in enumerate(shown):
            self._row(i, "📂" if kind == "dir" else "📄", name, size, size / biggest, size * 100 / total,
                      ui.ACCENT if kind == "dir" else ui.FILE_BAR, child)
        if rest_count:
            self._row(len(shown), "…", f"diğer {rest_count:,} öğe", rest_size, rest_size / biggest,
                      rest_size * 100 / total, ui.FILE_BAR, None)

    def _row(self, i: int, icon: str, name: str, size: int, ratio: float, percent: float, color, child) -> None:
        clickable = child is not None
        widgets = [
            ctk.CTkLabel(self.list, text=f"{icon}  {name}", anchor="w", width=300,
                         font=ctk.CTkFont(size=13, weight="bold" if clickable else "normal")),
            ctk.CTkProgressBar(self.list, height=14, progress_color=color, corner_radius=7),
            ctk.CTkLabel(self.list, text=human_size(size), anchor="e", width=84),
            ctk.CTkLabel(self.list, text=f"%{percent:.1f}" if percent >= 0.1 else "<%0.1", anchor="e", width=56,
                         text_color=ui.MUTED),
        ]
        widgets[1].set(max(ratio, 0.004))
        for col, w in enumerate(widgets):
            w.grid(row=i, column=col, sticky="ew" if col == 1 else "e" if col > 1 else "w", padx=6, pady=3)
            if clickable:
                w.bind("<Button-1>", lambda _e, c=child: self._enter(c))
                w.configure(cursor="hand2")

    def _enter(self, node: du.DirNode) -> None:
        self.stack.append(node)
        self._show_node()

    def go_up(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop()
            self._show_node()

    def open_current(self) -> None:
        if self.stack:
            reveal(str(self.stack[-1].path), select=False)

    # ---------- En büyük dosyalar sekmesi ----------
    def _build_largest(self, tab) -> None:
        holder = ctk.CTkFrame(tab, fg_color=ui.CARD, corner_radius=14)
        holder.pack(fill="both", expand=True)
        self.big_tree = make_tree(holder, {"name": ("Dosya", 280), "folder": ("Klasör", 420), "size": ("Boyut", 90)})
        self.big_tree.column("size", anchor="e", stretch=False)
        self.big_tree.heading("size", anchor="e")
        self.big_tree.bind("<Double-1>", lambda _e: self._reveal_big())
        self.big_paths: dict[str, str] = {}
        foot = ctk.CTkFrame(tab, fg_color="transparent")
        foot.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(foot, text="Klasörde göster", width=130, fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER,
                      command=self._reveal_big).pack(side="left")
        ctk.CTkLabel(foot, text="Çift tıklayınca da açılır. Bu araç dosya silmez; silmek istersen Explorer'da yap.",
                     text_color=ui.MUTED).pack(side="left", padx=12)

    def _reveal_big(self) -> None:
        sel = self.big_tree.selection()
        if sel and sel[0] in self.big_paths:
            reveal(self.big_paths[sel[0]], select=True)

    def _fill_largest(self) -> None:
        self.big_tree.delete(*self.big_tree.get_children())
        self.big_paths = {}
        for i, (path, size) in enumerate(self.result.largest):
            iid = str(i)
            self.big_paths[iid] = str(path)
            self.big_tree.insert("", "end", iid=iid, values=(path.name, str(path.parent), human_size(size)))

    # ---------- tarama ----------
    def browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if chosen:
            self.folder_var.set(str(Path(chosen)))

    def toggle_scan(self) -> None:
        if self.scanning:
            self.stop_event.set()
            self.progress.configure(text="Durduruluyor…")
            return
        folder = Path(self.folder_var.get().strip())
        if not folder.is_dir():
            self.progress.configure(text="Geçerli bir klasör seç.")
            return
        self.scanning = True
        self._scan_token += 1
        token = self._scan_token
        self.stop_event.clear()
        self.run_btn.configure(text="■  Durdur", fg_color=ui.DANGER, hover_color=ui.DANGER_HOVER, text_color=ui.DANGER_TEXT)
        self._clear_rows()
        self.spinner.start("Klasör taranıyor…")

        def work():
            try:
                res = du.scan(folder, stop=self.stop_event,
                              progress=lambda n, d: self.events.put(("p", token, n, d)))
                self.events.put(("done", token, folder, res))
            except Exception as e:
                self.events.put(("err", token, str(e)))

        threading.Thread(target=work, daemon=True).start()
        self.after(150, self._poll)

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        finished = False
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            if ev[1] != self._scan_token:
                continue
            if ev[0] == "p":
                tail = f"  —  {Path(ev[3]).name}" if ev[3] else ""
                self.progress.configure(text=f"{ev[2]:,} dosya tarandı{tail}")
            elif ev[0] == "done":
                self._finish(ev[2], ev[3])
                finished = True
            elif ev[0] == "err":
                self.progress.configure(text=f"Hata: {ev[2]}")
                finished = True
        if finished:
            self.scanning = False
            self.spinner.stop()
            self.run_btn.configure(text="📊  Analiz et", fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER, text_color=ui.ACCENT_TEXT)
            if self.result is None:
                ctk.CTkLabel(self.list, text="Analiz tamamlanamadı.", text_color=ui.MUTED).grid(row=0, column=0, pady=30)
        else:
            self.after(150, self._poll)

    def _finish(self, folder: Path, res: du.ScanResult) -> None:
        self.result = res
        self.stack = [res.root]
        self.cfg["folder"] = str(folder)
        note = f"Bitti: {res.root.file_count:,} dosya, {human_size(res.root.size)}."
        if res.stopped:
            note = "Durduruldu (sonuçlar kısmi): " + note[6:]
        if res.errors:
            note += f"  {res.errors} klasör/dosya okunamadı (izin yok)."
        self.progress.configure(text=note)
        self._show_node()
        self._fill_largest()

    def _shutdown(self) -> None:
        self.stop_event.set()
