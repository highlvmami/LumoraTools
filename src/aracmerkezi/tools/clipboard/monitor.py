"""Panoyu yoklayan izleyici. Tk ana iş parçacığında `after` ile çalışır."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from .store import ClipStore


class ClipboardMonitor:
    def __init__(self, widget: tk.Misc, store: ClipStore, interval_ms: int = 700) -> None:
        self.widget = widget
        self.store = store
        self.interval = interval_ms
        self.paused = False
        self.listeners: list[Callable[[], None]] = []
        self._last: str | None = None
        self._job: str | None = None

    def start(self) -> None:
        if self._job is None:
            self._poll()

    def resume(self) -> None:
        """Durdurulmuş izleyiciyi yeniden başlatır; durmuşken kopyalananlar kaydedilmez."""
        self._last = self._read()
        self.start()

    def stop(self) -> None:
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None

    def set_paused(self, paused: bool) -> None:
        """Duraklatırken kopyalananlar, devam edince geriye dönük kaydedilmez."""
        self.paused = paused
        if not paused:
            self._last = self._read()

    def _read(self) -> str | None:
        try:
            return self.widget.clipboard_get()
        except tk.TclError:  # pano boş, metin değil ya da başka uygulama tarafından kilitli
            return None

    def _poll(self) -> None:
        if not self.paused:
            text = self._read()
            if text and text != self._last:
                self._last = text
                if self.store.add(text):
                    for cb in self.listeners:
                        cb()
        self._job = self.widget.after(self.interval, self._poll)
