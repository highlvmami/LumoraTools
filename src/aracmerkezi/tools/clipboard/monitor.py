"""Panoyu yoklayan izleyici. Tk ana iş parçacığında `after` ile çalışır.

Windows'ta pano her değiştiğinde artan sayaç (GetClipboardSequenceNumber) izlenir; yalnızca sayaç değişince
içerik okunur. Önce metin, metin yoksa görüntü, o da yoksa kopyalanan dosyalar kaydedilir. Sayaç yoksa
(Windows dışı) yalnızca metin ve eski karşılaştırma yöntemiyle çalışır.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from . import clipboard_io
from .store import ClipStore


class ClipboardMonitor:
    def __init__(self, widget: tk.Misc, store: ClipStore, interval_ms: int = 700, io=clipboard_io) -> None:
        self.widget = widget
        self.store = store
        self.interval = interval_ms
        self.io = io
        self.paused = False
        self.listeners: list[Callable[[], None]] = []
        self._last: str | None = None       # sayaç yokken: son görülen metin
        self._seq: int | None = None        # son işlenen pano sayacı
        self._job: str | None = None

    def start(self) -> None:
        if self._job is None:
            self._poll()

    def resume(self) -> None:
        """Durdurulmuş izleyiciyi yeniden başlatır; durmuşken kopyalananlar kaydedilmez."""
        self._skip_current()
        self.start()

    def stop(self) -> None:
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None

    def set_paused(self, paused: bool) -> None:
        """Duraklatırken kopyalananlar, devam edince geriye dönük kaydedilmez."""
        self.paused = paused
        if not paused:
            self._skip_current()

    def mark_own(self) -> None:
        """Uygulamanın kendi panoya yazdığı içerik (geçmişten 'Kopyala') yeniden kayıt olarak eklenmesin."""
        self._seq = self.io.sequence_number()

    def _skip_current(self) -> None:
        self._last = self._read_text()
        self._seq = self.io.sequence_number()

    def _read_text(self) -> str | None:
        try:
            return self.widget.clipboard_get()
        except tk.TclError:  # pano boş, metin değil ya da başka uygulama tarafından kilitli
            return None

    def _changed(self) -> None:
        for cb in list(self.listeners):   # dinleyici kendini listeden çıkarabilir
            cb()

    def _capture(self) -> None:
        text = self._read_text()
        if text:
            self._last = text
            if self.store.add(text):
                self._changed()
            return
        found = self.io.read_non_text()
        if not found:
            return
        kind, payload = found
        saved = self.store.add_image(payload) if kind == "image" else self.store.add_files(payload)
        if saved:
            self._changed()

    def _poll(self) -> None:
        if not self.paused:
            seq = self.io.sequence_number()
            if seq is None:                      # sayaç yok: yalnızca metin, içerik karşılaştırarak
                text = self._read_text()
                if text and text != self._last:
                    self._last = text
                    if self.store.add(text):
                        self._changed()
            elif seq != self._seq:
                self._seq = seq
                self._capture()
        self._job = self.widget.after(self.interval, self._poll)
