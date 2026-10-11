from datetime import date

import pytest

from aracmerkezi.tools.todo import store as td
from aracmerkezi.tools.todo.store import TodoStore, due_status, format_due, parse_due

TODAY = date(2026, 10, 11)


@pytest.fixture
def s(tmp_path):
    return TodoStore(tmp_path / "t.db")


def titles(tasks):
    return [t.title for t in tasks]


def test_add_get_update_and_validation(s):
    i = s.add("  Fatura öde  ", due="2026-10-15", priority=1, notes=" banka ")
    t = s.get(i)
    assert (t.title, t.notes, t.priority, t.due, t.done) == ("Fatura öde", "banka", 1, "2026-10-15", False)
    s.update(i, title="Faturayı öde", priority=2, due=None)
    t = s.get(i)
    assert t.title == "Faturayı öde" and t.priority == 2 and t.due is None and t.notes == "banka"   # yalnızca verilenler değişir
    with pytest.raises(ValueError):
        s.add("   ")
    with pytest.raises(ValueError):
        s.add("x", priority=7)
    with pytest.raises(ValueError):
        s.update(i, title="  ")
    assert s.get(9999) is None


def test_toggle_sets_and_clears_done_time(s):
    i = s.add("a")
    assert s.toggle(i) is True and s.get(i).done and s.get(i).done_at
    assert s.toggle(i) is False and not s.get(i).done and s.get(i).done_at is None
    with pytest.raises(KeyError):
        s.toggle(404)


def test_open_list_order_priority_then_due_then_created(s):
    s.add("normal-geç", due="2026-10-20")
    s.add("normal-yakın", due="2026-10-12")
    s.add("normal-tarihsiz")
    s.add("acil-tarihsiz", priority=2)
    s.add("yüksek", priority=1, due="2026-10-30")
    assert titles(s.list("open", today=TODAY)) == ["acil-tarihsiz", "yüksek", "normal-yakın", "normal-geç", "normal-tarihsiz"]


def test_filters_today_overdue_done_all(s):
    a = s.add("gecikmiş", due="2026-10-01")
    s.add("bugün", due="2026-10-11")
    s.add("gelecek", due="2026-12-01")
    done = s.add("bitti", due="2026-10-01")
    s.toggle(done)
    assert titles(s.list("overdue", today=TODAY)) == ["gecikmiş"]            # biten gecikmiş sayılmaz
    assert titles(s.list("today", today=TODAY)) == ["bugün"]
    assert titles(s.list("done", today=TODAY)) == ["bitti"]
    assert len(s.list("all", today=TODAY)) == 4 and len(s.list("open", today=TODAY)) == 3
    assert s.counts(TODAY) == {"open": 3, "today": 1, "overdue": 1, "done": 1}
    with pytest.raises(ValueError):
        s.list("garip")
    assert a


def test_search_is_turkish_insensitive_over_title_and_notes(s):
    s.add("ÇAMAŞIR yıka")
    s.add("alışveriş", notes="Süt ve yumurta")
    assert titles(s.list("open", "camasir")) == ["ÇAMAŞIR yıka"]
    assert titles(s.list("open", "SUT")) == ["alışveriş"]
    assert s.list("open", "yok") == []


def test_done_list_shows_latest_completed_first(s, monkeypatch):
    clock = [0.0]

    def fake_time():                                                          # her çağrıda ilerleyen sahte saat
        clock[0] += 100.0
        return clock[0]

    monkeypatch.setattr(td.time, "time", fake_time)
    a = s.add("a")
    s.add("b")
    c = s.add("c")
    s.toggle(a)
    s.toggle(c)
    assert titles(s.list("done")) == ["c", "a"]


def test_clear_done_and_delete(s):
    a, b = s.add("a"), s.add("b")
    s.toggle(a)
    assert s.clear_done() == 1 and titles(s.list("all")) == ["b"]
    s.delete(b)
    assert s.list("all") == [] and s.clear_done() == 0


def test_due_status_levels():
    mk = lambda due, done=False: td.Task(1, "x", "", done, 0, due, 0.0, None)
    assert due_status(mk("2026-10-10"), TODAY) == "overdue"
    assert due_status(mk("2026-10-11"), TODAY) == "today"
    assert due_status(mk("2026-10-13"), TODAY) == "soon" and due_status(mk("2026-10-14"), TODAY) == ""
    assert due_status(mk(None), TODAY) == "" and due_status(mk("2026-10-10", done=True), TODAY) == ""


def test_parse_and_format_due():
    assert parse_due("25.12.2026") == "2026-12-25" and parse_due("2026-12-25") == "2026-12-25"
    assert parse_due("") is None and parse_due(None) is None and parse_due("  ") is None
    with pytest.raises(ValueError):
        parse_due("yarın")
    assert format_due("2026-12-25") == "25.12.2026" and format_due(None) == ""


def test_persistence_across_connections(tmp_path):
    TodoStore(tmp_path / "t.db").add("kalıcı")
    assert titles(TodoStore(tmp_path / "t.db").list("open")) == ["kalıcı"]
