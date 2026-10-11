"""Zaman takibinin arka plan hizmeti: izleme açıksa sayfa kapalı olsa da çalışır; uygulama kapanınca durur."""
from __future__ import annotations

from .tracker import DEFAULT_IGNORE, Tracker, UsageStore, get_foreground_app, get_idle_seconds

INTERVAL_S = 5.0


class TrackService:
    def __init__(self, hub) -> None:
        self.hub = hub
        self.cfg = hub.settings_for("zaman")
        self.store = UsageStore(hub.data_dir / "timetrack.db")
        ignore = set(DEFAULT_IGNORE) | {a.lower() for a in self.cfg.get("ignore", [])}
        self.tracker = Tracker(self.store, get_foreground_app, get_idle_seconds, interval=INTERVAL_S, ignore=ignore)
        self.tracker.paused = not self.enabled
        self._job: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", False))        # gizlilik: varsayılan KAPALI, kullanıcı bilerek açar

    def set_enabled(self, on: bool) -> None:
        self.cfg["enabled"] = on
        self.tracker.paused = not on
        self.tracker.reset()                                # kapalıyken geçen süre sayılmasın
        if on:
            self.start()
        else:
            self.stop()

    def start(self) -> None:
        if self.enabled and self._job is None:
            self.tracker.paused = False
            self.tracker.reset()
            self._schedule()

    def stop(self) -> None:
        if self._job is not None:
            self.hub.after_cancel(self._job)
            self._job = None

    def _schedule(self) -> None:
        self._job = self.hub.after(int(INTERVAL_S * 1000), self._tick)

    def _tick(self) -> None:
        self._job = None
        if not self.enabled:
            return
        try:
            self.tracker.tick()
        except Exception as e:                              # örnekleme hiçbir hatada döngüyü öldürmemeli
            self.hub.log("error", f"zaman takibi: {e}")
        self._schedule()

    def add_ignore(self, app: str) -> None:
        self.cfg["ignore"] = sorted(set(self.cfg.get("ignore", [])) | {app})
        self.tracker.ignore.add(app.lower())

    def close(self) -> None:
        self.stop()
        self.store.close()


def get_service(hub) -> TrackService:
    if "zaman" not in hub.services:
        svc = TrackService(hub)
        hub.services["zaman"] = svc
        hub.on_close.append(svc.close)
    return hub.services["zaman"]
