from aracmerkezi.tools.clipboard import store as store_mod
from aracmerkezi.tools.clipboard.store import ClipStore


def test_add_dedupes_and_bumps_to_top(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    s.add("birinci")
    s.add("ikinci")
    s.add("birinci")  # tekrar: yeni kayıt değil, en üste
    assert [c.text for c in s.list()] == ["birinci", "ikinci"]
    assert s.count() == 2


def test_rejects_blank_and_oversized(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    assert not s.add("") and not s.add("   \n ")
    assert not s.add("x" * (store_mod.MAX_LEN + 1))
    assert s.count() == 0


def test_search_is_turkish_insensitive(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    s.add("İstanbul'da ÇALIŞMA toplantısı")
    s.add("başka bir şey")
    assert len(s.list("istanbul")) == 1
    assert len(s.list("calisma")) == 1
    assert len(s.list("SEY")) == 1


def test_pinned_first_and_survive_clear(tmp_path):
    s = ClipStore(tmp_path / "c.db")
    s.add("a")
    s.add("b")
    a = next(c for c in s.list() if c.text == "a")
    s.set_pinned(a.id, True)
    assert s.list()[0].text == "a"  # daha eski ama sabit
    assert s.clear_unpinned() == 1
    assert [c.text for c in s.list()] == ["a"]


def test_prune_keeps_limit_but_not_pinned(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "MAX_KEEP", 3)
    s = ClipStore(tmp_path / "c.db")
    s.add("sabit")
    s.set_pinned(s.list()[0].id, True)
    for i in range(6):
        s.add(f"m{i}")
    texts = [c.text for c in s.list()]
    assert "sabit" in texts and len(texts) == 4


def test_persists_across_connections(tmp_path):
    ClipStore(tmp_path / "c.db").add("kalici")
    assert ClipStore(tmp_path / "c.db").list()[0].text == "kalici"
