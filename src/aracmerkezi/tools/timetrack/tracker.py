"""Zaman takibi çekirdeği: ön plandaki uygulamayı örnekler, günlük süreleri saklar (Tk'den bağımsız, test edilebilir).

Gizlilik: yalnızca UYGULAMA ADI (ör. chrome.exe) ve süre saklanır; pencere başlıkları, belge adları, adresler,
tuş vuruşları ya da ekran görüntüsü asla alınmaz. Veriler yalnızca bu bilgisayarda, SQLite dosyasında durur.
"""
from __future__ import annotations

import ctypes
import sqlite3
import sys
import time
from ctypes import wintypes
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

IDLE = "__idle__"                 # boşta (klavye/fare kullanılmayan) süre için özel ad
DEFAULT_IGNORE = frozenset({"lockapp.exe", "logonui.exe"})      # kilit ekranı sayılmasın

_FRIENDLY = {
    "chrome.exe": "Google Chrome", "msedge.exe": "Microsoft Edge", "firefox.exe": "Firefox", "opera.exe": "Opera",
    "code.exe": "VS Code", "explorer.exe": "Dosya Gezgini", "windowsterminal.exe": "Windows Terminal",
    "cmd.exe": "Komut İstemi", "powershell.exe": "PowerShell", "notepad.exe": "Not Defteri",
    "winword.exe": "Word", "excel.exe": "Excel", "powerpnt.exe": "PowerPoint", "outlook.exe": "Outlook",
    "olk.exe": "Outlook", "spotify.exe": "Spotify", "discord.exe": "Discord", "whatsapp.exe": "WhatsApp",
    "taskmgr.exe": "Görev Yöneticisi", "aracmerkezi.exe": "LumoraTools", "python.exe": "Python",
    "pythonw.exe": "Python", "teams.exe": "Teams", "slack.exe": "Slack", "vlc.exe": "VLC", "steam.exe": "Steam",
}


def friendly_name(app: str) -> str:
    if app == IDLE:
        return "Boşta (klavye/fare kullanılmadı)"
    low = app.lower()
    if low in _FRIENDLY:
        return _FRIENDLY[low]
    stem = app[:-4] if low.endswith(".exe") else app
    return stem[:1].upper() + stem[1:]


class UsageStore:
    def __init__(self, path: Path | str) -> None:
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS usage (day TEXT NOT NULL, app TEXT NOT NULL, seconds REAL NOT NULL,"
                        " PRIMARY KEY(day, app))")
        self.db.commit()

    def add(self, day: str, app: str, seconds: float) -> None:
        self.db.execute("INSERT INTO usage(day, app, seconds) VALUES(?, ?, ?) "
                        "ON CONFLICT(day, app) DO UPDATE SET seconds = seconds + excluded.seconds", (day, app, seconds))
        self.db.commit()

    def totals(self, day: str) -> dict[str, float]:
        return dict(self.db.execute("SELECT app, seconds FROM usage WHERE day = ?", (day,)))

    def range_totals(self, start: str, end: str) -> dict[str, float]:
        """[start, end] arası (dahil) uygulama toplamları."""
        return dict(self.db.execute("SELECT app, SUM(seconds) FROM usage WHERE day BETWEEN ? AND ? GROUP BY app",
                                    (start, end)))

    def daily_totals(self, start: str, end: str) -> dict[str, float]:
        """Gün gün toplam AKTİF süre (boşta olanlar hariç)."""
        return dict(self.db.execute("SELECT day, SUM(seconds) FROM usage WHERE day BETWEEN ? AND ? AND app != ? "
                                    "GROUP BY day", (start, end, IDLE)))

    def delete_app(self, app: str) -> None:
        self.db.execute("DELETE FROM usage WHERE app = ?", (app,))
        self.db.commit()

    def clear(self) -> int:
        n = self.db.execute("DELETE FROM usage").rowcount
        self.db.commit()
        return n

    def close(self) -> None:
        self.db.close()


def week_days(end: date, count: int = 7) -> list[str]:
    """`end` dahil geriye doğru `count` günün ISO tarihleri, eskiden yeniye."""
    return [(end - timedelta(days=i)).isoformat() for i in range(count - 1, -1, -1)]


class Tracker:
    """Düzenli aralıkla `tick()` çağrılır; geçen süreyi o anda ön planda olan uygulamaya yazar."""

    def __init__(self, store: UsageStore, foreground: Callable[[], str | None], idle_seconds: Callable[[], float],
                 now: Callable[[], float] = time.time, interval: float = 5.0, idle_limit: float = 300.0,
                 ignore=DEFAULT_IGNORE) -> None:
        self.store, self.foreground, self.idle_seconds, self.now = store, foreground, idle_seconds, now
        self.interval, self.idle_limit = interval, idle_limit
        self.ignore = {a.lower() for a in ignore}
        self.paused = False
        self._last: float | None = None

    def reset(self) -> None:
        """Duraklatıp sürdürürken ara verilen süre sayılmasın."""
        self._last = None

    def tick(self) -> None:
        t = self.now()
        if self._last is None:
            self._last = t                       # ilk çağrı yalnızca başlangıç noktasıdır
            return
        # Bilgisayar uykudayken/askıdayken geçen süre sayılmasın: tek adım en çok 3 aralık kadardır.
        dt = min(t - self._last, self.interval * 3)
        self._last = t
        if dt <= 0 or self.paused:
            return
        day = date.fromtimestamp(t).isoformat()
        if self.idle_seconds() >= self.idle_limit:
            self.store.add(day, IDLE, dt)
            return
        app = self.foreground()
        if app and app.lower() not in self.ignore:
            self.store.add(day, app, dt)


# ---------- Windows: ön plan uygulaması ve boşta süresi ----------
class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_idle_seconds() -> float:
    """Son klavye/fare etkinliğinden bu yana geçen saniye (Windows dışında 0)."""
    if sys.platform != "win32":
        return 0.0
    info = _LASTINPUTINFO(ctypes.sizeof(_LASTINPUTINFO), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    millis = (ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF      # 49 günde sarar; maskeleme bunu çözer
    return millis / 1000.0


def get_foreground_app() -> str | None:
    """Ön plandaki pencerenin süreç adı (ör. 'chrome.exe'); alınamazsa None. Pencere başlığı OKUNMAZ."""
    if sys.platform != "win32":
        return None
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    try:
        import psutil
        return psutil.Process(pid.value).name() or None
    except Exception:                            # yönetici yetkisiyle çalışan uygulamalar: erişim yok
        return None
