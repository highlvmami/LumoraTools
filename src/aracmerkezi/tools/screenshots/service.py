"""Ekran görüntüsü yöneticisinin arka plan hizmeti: klasör izleme ve notlar (sayfa açık olmasa da çalışır)."""
from __future__ import annotations

import queue
from pathlib import Path

from duzenle.watcher import Watcher

from .library import FORMATS, IMG_EXTS, NoteStore, default_folder


class ShotService:
    def __init__(self, hub) -> None:
        self.cfg = hub.settings_for("ekran")
        self.messages: queue.Queue[str] = queue.Queue(maxsize=200)
        self.watcher: Watcher | None = None
        self.notes = NoteStore(hub.data_dir / "screenshots.db")

    @property
    def folder(self) -> Path:
        return Path(self.cfg.get("folder") or default_folder())

    @property
    def date_format(self) -> str:
        fmt = self.cfg.get("format", "%Y/%m")
        return fmt if fmt in FORMATS.values() else "%Y/%m"

    @property
    def watching(self) -> bool:
        return self.watcher is not None and self.watcher.running

    def _message(self, text: str) -> None:
        try:
            self.messages.put_nowait(text)  # sayfa kapalıyken kuyruk dolmasın
        except queue.Full:
            pass

    def start_watch(self) -> bool:
        """Klasörü izlemeye başlar (yeni görüntüler tarihe göre yerleştirilir). Klasör yoksa False."""
        self.stop_watch(remember=False)
        folder = self.folder
        if not folder.is_dir():
            return False
        self.watcher = Watcher(folder, "tarih", self.date_format, on_message=self._message,
                               extensions=IMG_EXTS)
        self.watcher.start()
        self.cfg["watch"] = True
        return True

    def stop_watch(self, remember: bool = True) -> None:
        """`remember=False` ise tercih ('izleme açık') saklı kalır; kapanış/gizlemede böyle çağrılır."""
        if self.watcher:
            self.watcher.stop()
            self.watcher = None
        if remember:
            self.cfg["watch"] = False

    def close(self) -> None:
        self.stop_watch(remember=False)
        self.notes.close()


def get_service(hub) -> ShotService:
    if "ekran" not in hub.services:
        svc = ShotService(hub)
        hub.services["ekran"] = svc
        hub.on_close.append(svc.close)
    return hub.services["ekran"]
