from datetime import datetime

import pytest

from aracmerkezi.datefilter import custom_range, parse_date, preset_range
from aracmerkezi.tools.clipboard.store import ClipStore

NOW = datetime(2026, 10, 11, 15, 30)


def ts(*a):
    return datetime(*a).timestamp()


def test_presets():
    assert preset_range("Tümü", NOW) == (None, None)
    assert preset_range("Bugün", NOW) == (ts(2026, 10, 11), None)
    assert preset_range("Dün", NOW) == (ts(2026, 10, 10), ts(2026, 10, 11))
    assert preset_range("Son 7 gün", NOW) == (ts(2026, 10, 5), None)    # bugün dahil 7 gün
    assert preset_range("Son 30 gün", NOW) == (ts(2026, 9, 12), None)


def test_parse_date_formats_and_errors():
    assert parse_date("25.12.2026") == datetime(2026, 12, 25)
    assert parse_date("2026-12-25") == datetime(2026, 12, 25)
    assert parse_date("25/12/2026") == datetime(2026, 12, 25)
    assert parse_date("  ") is None
    with pytest.raises(ValueError):
        parse_date("32.13.2026")
    with pytest.raises(ValueError):
        parse_date("dün")


def test_custom_range_end_is_inclusive():
    since, until = custom_range("10.10.2026", "11.10.2026")
    assert since == ts(2026, 10, 10) and until == ts(2026, 10, 12)      # 11'i tamamen kapsar
    assert custom_range("", "") == (None, None)
    assert custom_range("10.10.2026", "") == (ts(2026, 10, 10), None)
    assert custom_range("", "10.10.2026") == (None, ts(2026, 10, 11))
    with pytest.raises(ValueError):
        custom_range("12.10.2026", "11.10.2026")


def test_store_filters_by_date_range(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    for text, when in (("eski", ts(2026, 10, 1, 12)), ("dün", ts(2026, 10, 10, 9)), ("bugün", ts(2026, 10, 11, 8))):
        s.db.execute("INSERT INTO clips(text, ts) VALUES(?, ?)", (text, when))
    s.db.commit()
    texts = lambda **kw: [c.text for c in s.list(**kw)]
    assert texts() == ["bugün", "dün", "eski"]
    assert texts(since=ts(2026, 10, 11)) == ["bugün"]
    assert texts(since=ts(2026, 10, 10), until=ts(2026, 10, 11)) == ["dün"]    # bitiş dahil değil
    assert texts(until=ts(2026, 10, 5)) == ["eski"]
    assert texts(query="BUGUN", since=ts(2026, 10, 10)) == ["bugün"]           # metin + tarih birlikte
