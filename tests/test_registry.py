from aracmerkezi.registry import discover


def test_discovers_all_tools_in_order():
    tools = discover()
    assert [t.id for t in tools] == ["duzenleyici", "pano", "arama"]
    assert all(t.name and t.icon and callable(t.build) for t in tools)
