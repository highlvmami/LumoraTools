"""Klasör izleyici: yeni gelen dosyalar boyutu sabitlenince otomatik yerleştirilir.

Yoklama (polling) tabanlıdır; ek bağımlılık gerektirmez. Bir dosya, boyutu ve
değişiklik zamanı `settle` saniye boyunca değişmediyse "yerleşti" sayılır, böylece
henüz inmekte olan dosyalara dokunulmaz.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

from . import engine
from .config import DEFAULT_DATE_FORMAT

Callback = Callable[[str], None]


class Watcher:
    def __init__(
        self,
        folder: Path,
        mode: str = "uzanti",
        date_format: str = DEFAULT_DATE_FORMAT,
        on_message: Callback = print,
        interval: float = 1.5,
        settle: float = 3.0,
        extensions: set[str] | None = None,
    ) -> None:
        self.folder = folder.resolve()
        self.mode = mode
        self.date_format = date_format
        self.on_message = on_message
        self.interval = interval
        self.settle = settle
        self.extensions = {e.lower() for e in extensions} if extensions else None  # None = tüm dosyalar
        self.moved_count = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # dosya -> (boyut, mtime, ilk görüldüğü/son değiştiği an)
        self._seen: dict[Path, tuple[int, float, float]] = {}

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="duzenle-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval * 2)

    def tick(self, now: float | None = None) -> None:
        """Tek yoklama turu (testlerde doğrudan çağrılabilir)."""
        now = time.monotonic() if now is None else now
        current: dict[Path, tuple[int, float, float]] = {}
        settled: set[Path] = set()
        for f in engine.scan(self.folder):
            try:
                st = f.stat()
            except OSError:
                continue
            sig = (st.st_size, st.st_mtime)
            prev = self._seen.get(f)
            since = prev[2] if prev and prev[:2] == sig else now
            current[f] = (*sig, since)
            if now - since >= self.settle:
                settled.add(f)
        self._seen = current
        if self.extensions:
            settled = {p for p in settled if p.suffix.lower() in self.extensions}
        if not settled:
            return
        moves = engine.plan(self.folder, self.mode, self.date_format, only=settled)
        done, failed = engine.apply(self.folder, moves)
        self.moved_count += len(done)
        for m in done:
            self.on_message(f"{m.src.name}  →  {m.dst.parent.relative_to(self.folder)}")
        for m, err in failed:
            self.on_message(f"Atlandı (sonra denenecek): {m.src.name} — {err}")

    def _loop(self) -> None:
        self.on_message(f"İzleme başladı: {self.folder}")
        while not self._stop.wait(self.interval):
            try:
                self.tick()
            except Exception as e:  # izleyici hiçbir hatada ölmemeli
                self.on_message(f"Hata: {e}")
        self.on_message("İzleme durdu.")
