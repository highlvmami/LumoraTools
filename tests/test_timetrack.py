import sqlite3
import sys
from datetime import date, datetime

import pytest

from aracmerkezi.tools.timetrack import tracker as tt
from aracmerkezi.tools.timetrack.tracker import IDLE, Tracker, UsageStore


class Clock:
    def __init__(self, start=None):
        self.t = start if start is not None else datetime(2026, 10, 11, 10, 0, 0).timestamp()

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def make(tmp_path, app="chrome.exe", idle=0.0, **kw):
    store = UsageStore(tmp_path / "u.db")
    state = {"app": app, "idle": idle}
    clock = Clock()
    tr = Tracker(store, lambda: state["app"], lambda: state["idle"], now=clock, **kw)
    return store, tr, clock, state


DAY = "2026-10-11"


def test_first_tick_is_only_a_baseline_then_time_accumulates_per_app(tmp_path):
    store, tr, clock, state = make(tmp_path)
    tr.tick()
    assert store.totals(DAY) == {}                                  # başlangıç noktası: süre yazılmaz
    clock.advance(5)
    tr.tick()
    state["app"] = "code.exe"
    clock.advance(5)
    tr.tick()
    clock.advance(4)
    tr.tick()
    assert store.totals(DAY) == {"chrome.exe": 5.0, "code.exe": 9.0}


def test_idle_time_goes_to_the_idle_bucket_not_to_the_app(tmp_path):
    store, tr, clock, state = make(tmp_path, idle_limit=300.0)
    tr.tick()
    clock.advance(5)
    state["idle"] = 301.0                                           # 5 dakikadır boşta
    tr.tick()
    assert store.totals(DAY) == {IDLE: 5.0}
    assert store.daily_totals(DAY, DAY) == {}                      # boşta olanlar aktif süreye girmez


def test_sleep_or_suspend_gap_is_capped_not_counted(tmp_path):
    store, tr, clock, _ = make(tmp_path, interval=5.0)
    tr.tick()
    clock.advance(3 * 3600)                                         # bilgisayar 3 saat uykuda kaldı
    tr.tick()
    assert store.totals(DAY) == {"chrome.exe": 15.0}                # en çok 3 aralık (15 sn) sayılır


def test_paused_tracker_records_nothing_and_reset_drops_the_gap(tmp_path):
    store, tr, clock, _ = make(tmp_path)
    tr.tick()
    tr.paused = True
    clock.advance(5)
    tr.tick()
    assert store.totals(DAY) == {}
    tr.paused = False
    tr.reset()                                                      # sürdürürken ara verilen süre sayılmaz
    clock.advance(5)
    tr.tick()                                                       # yalnızca yeni başlangıç noktası
    assert store.totals(DAY) == {}
    clock.advance(5)
    tr.tick()
    assert store.totals(DAY) == {"chrome.exe": 5.0}


def test_ignored_apps_and_missing_foreground_are_skipped_case_insensitively(tmp_path):
    store, tr, clock, state = make(tmp_path, app="LockApp.exe")     # varsayılan yok sayılanlar: kilit ekranı
    tr.tick()
    clock.advance(5)
    tr.tick()
    state["app"] = None                                             # ön plan alınamadı
    clock.advance(5)
    tr.tick()
    state["app"] = "Spotify.exe"
    tr.ignore.add("spotify.exe")
    clock.advance(5)
    tr.tick()
    assert store.totals(DAY) == {}


def test_day_rollover_uses_the_date_of_each_tick(tmp_path):
    store = UsageStore(tmp_path / "u.db")
    clock = Clock(datetime(2026, 10, 11, 23, 59, 58).timestamp())
    tr = Tracker(store, lambda: "a.exe", lambda: 0.0, now=clock)
    tr.tick()
    clock.advance(4)                                                # gece yarısını aştı → yeni güne yazılır
    tr.tick()
    assert store.totals("2026-10-12") == {"a.exe": 4.0}


def test_store_aggregates_ranges_and_daily_totals_and_clears(tmp_path):
    s = UsageStore(tmp_path / "u.db")
    s.add("2026-10-09", "a.exe", 60)
    s.add("2026-10-10", "a.exe", 30)
    s.add("2026-10-10", "b.exe", 10)
    s.add("2026-10-10", IDLE, 500)
    s.add("2026-10-11", "a.exe", 5)
    s.add("2026-10-11", "a.exe", 5)                                 # aynı gün/uygulama toplanır
    assert s.totals("2026-10-11") == {"a.exe": 10.0}
    assert s.range_totals("2026-10-09", "2026-10-10") == {"a.exe": 90.0, "b.exe": 10.0, IDLE: 500.0}
    assert s.daily_totals("2026-10-09", "2026-10-11") == {"2026-10-09": 60.0, "2026-10-10": 40.0, "2026-10-11": 10.0}
    s.delete_app("b.exe")
    assert "b.exe" not in s.totals("2026-10-10")
    assert s.clear() == 4 and s.totals("2026-10-09") == {}


def test_no_window_titles_or_other_personal_data_in_the_schema(tmp_path):
    UsageStore(tmp_path / "u.db")
    cols = [r[1] for r in sqlite3.connect(tmp_path / "u.db").execute("PRAGMA table_info(usage)")]
    assert cols == ["day", "app", "seconds"]                        # başlık, URL, kullanıcı adı gibi sütun YOK


def test_friendly_names_and_week_days():
    assert tt.friendly_name("chrome.exe") == "Google Chrome" and tt.friendly_name("CODE.EXE") == "VS Code"
    assert tt.friendly_name("bilinmeyenprogram.exe") == "Bilinmeyenprogram" and tt.friendly_name("Foo") == "Foo"
    assert "Boşta" in tt.friendly_name(IDLE)
    days = tt.week_days(date(2026, 10, 11), 3)
    assert days == ["2026-10-09", "2026-10-10", "2026-10-11"]


@pytest.mark.skipif(sys.platform != "win32", reason="yalnızca Windows")
def test_real_foreground_and_idle_readers_do_not_crash():
    app = tt.get_foreground_app()
    assert app is None or (isinstance(app, str) and app)
    idle = tt.get_idle_seconds()
    assert isinstance(idle, float) and 0 <= idle < 10 * 365 * 86400
