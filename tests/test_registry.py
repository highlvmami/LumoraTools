from aracmerkezi.registry import discover


def test_discovers_all_tools_in_order():
    tools = discover()
    assert [t.id for t in tools] == ["arama", "duzenleyici", "pano", "boyut", "ekran", "temizle", "baslangic"]   # varsayılan menü sırası
    assert all(t.name and t.icon and callable(t.build) for t in tools)


def test_every_tool_has_a_real_guide():
    for t in discover():
        assert t.guide is not None, f"{t.id} için rehber yok"
        assert t.guide.summary.strip() and len(t.guide.steps) >= 3 and all(s.strip() for s in t.guide.steps), t.id
