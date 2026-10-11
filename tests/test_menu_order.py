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


# ---------- kategoriler ----------
def cat_tool(id, order, category):
    return ToolInfo(id, id.title(), "x", "d", build=lambda p, h: None, order=order, category=category)


def test_group_tools_uses_fixed_category_order_and_keeps_incoming_order_inside():
    from aracmerkezi.registry import group_tools
    tools = [cat_tool("uretken1", 1, "uretken"), cat_tool("dosya2", 2, "dosya"), cat_tool("dosya1", 3, "dosya"),
             cat_tool("bakim1", 4, "bakim")]
    grouped = group_tools(tools)
    assert [c.id for c, _ in grouped] == ["dosya", "bakim", "uretken"]            # sabit kategori sırası
    assert [t.id for t in grouped[0][1]] == ["dosya2", "dosya1"]                  # gelen (kullanıcı) sırası korunur


def test_group_tools_drops_empty_categories_and_puts_unknown_in_other():
    from aracmerkezi.registry import group_tools
    grouped = group_tools([cat_tool("x", 1, "olmayan-kategori"), cat_tool("y", 2, "sistem")])
    assert [c.id for c, _ in grouped] == ["sistem", "diger"] and grouped[1][1][0].id == "x"
    assert group_tools([]) == []


def test_every_real_tool_belongs_to_a_known_category():
    from aracmerkezi.registry import CATEGORIES, discover, group_tools
    known = {c.id for c in CATEGORIES}
    tools = discover()
    assert all(t.category in known for t in tools), [t.id for t in tools if t.category not in known]
    assert [c.id for c, _ in group_tools(tools)] == [c.id for c in CATEGORIES]    # hiçbiri "Diğer"e düşmüyor


def test_default_categories_group_the_tools_sensibly():
    from aracmerkezi.registry import discover, group_tools
    got = {c.id: [t.id for t in items] for c, items in group_tools(discover())}
    assert got == {"dosya": ["arama", "duzenleyici", "boyut", "ekran"],
                   "bakim": ["temizle", "baslangic", "kaldir", "saglik"],
                   "sistem": ["sistem", "islem", "ag"],
                   "uretken": ["pano", "gorev", "zaman"]}
