from aracmerkezi.registry import ToolInfo, order_tools


def tool(id, order):
    return ToolInfo(id, id.title(), "x", "d", build=lambda p, h: None, order=order)


TOOLS = [tool("duzenleyici", 20), tool("arama", 10), tool("pano", 30)]


def ids(tools):
    return [t.id for t in tools]


def test_default_order_follows_tool_order_attribute():
    allt, vis = order_tools(TOOLS, None, None)
    assert ids(allt) == ["arama", "duzenleyici", "pano"] and ids(vis) == ids(allt)


def test_saved_order_and_hidden_applied():
    allt, vis = order_tools(TOOLS, ["pano", "arama", "duzenleyici"], {"arama"})
    assert ids(allt) == ["pano", "arama", "duzenleyici"]
    assert ids(vis) == ["pano", "duzenleyici"]          # gizli olan listeden düşer ama allt'te durur


def test_new_tools_not_in_saved_order_are_appended_in_default_order():
    tools = TOOLS + [tool("yeni_b", 50), tool("yeni_a", 40)]
    allt, _ = order_tools(tools, ["pano", "duzenleyici", "arama"], None)
    assert ids(allt) == ["pano", "duzenleyici", "arama", "yeni_a", "yeni_b"]


def test_unknown_ids_in_saved_order_are_ignored():
    allt, _ = order_tools(TOOLS, ["silinmis_arac", "pano"], None)
    assert ids(allt) == ["pano", "arama", "duzenleyici"]


def test_hiding_everything_is_allowed():
    _, vis = order_tools(TOOLS, None, {"arama", "duzenleyici", "pano"})
    assert vis == []
