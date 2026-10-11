import pytest

from aracmerkezi import registry
from aracmerkezi.app import Hub


def make_hub(tmp_path):
    try:
        hub = Hub(data_dir=tmp_path, tools=registry.discover())
    except Exception as e:  # ekran/Tk yoksa
        pytest.skip(str(e))
    hub.update_idletasks()
    return hub


def test_sidebar_is_grouped_and_collapse_persists(tmp_path):
    hub = make_hub(tmp_path)
    try:
        assert set(hub.cat_headers) == {"dosya", "bakim", "sistem", "uretken"}
        assert "arama" in hub.nav
        hub.toggle_category("sistem")
        assert "islem" not in hub.nav and "arama" in hub.nav          # kapanan kategorinin araçları gizlenir
        assert hub.settings["menu"]["collapsed"] == ["sistem"]
    finally:
        hub.destroy()
    hub2 = make_hub(tmp_path)                                         # kapalı durum yeniden açılışta korunur
    try:
        assert "islem" not in hub2.nav
    finally:
        hub2.destroy()


def test_opening_tool_in_collapsed_category_expands_it_and_current_cannot_hide(tmp_path):
    hub = make_hub(tmp_path)
    try:
        hub.toggle_category("sistem")
        hub.show("islem")
        assert "islem" in hub.nav                                     # ana sayfadan açılınca kategori görünür olur
        hub.toggle_category("sistem")                                  # (açık sayfanın kategorisi kapanmış görünmez)
        assert "islem" in hub.nav
    finally:
        hub.destroy()


def test_flat_mode_has_no_headers_and_keeps_fixed_buttons(tmp_path):
    hub = make_hub(tmp_path)
    try:
        hub.set_grouped(False)
        assert hub.cat_headers == {} and len(hub.tools) == len([k for k in hub.nav if k not in
                                                                ("home", "settings", "guides", "contact")])
        assert all(k in hub.nav for k in ("home", "settings", "guides", "contact"))
        assert hub.settings["menu"]["grouped"] is False
    finally:
        hub.destroy()


def test_bottom_buttons_stay_visible_when_grouped_at_small_height(tmp_path):
    hub = make_hub(tmp_path)
    try:
        hub.geometry("1100x720")
        hub.update()
        bottom = hub.nav["settings"]
        assert bottom.winfo_ismapped() and bottom.winfo_rooty() + bottom.winfo_height() <= hub.winfo_rooty() + 720
    finally:
        hub.destroy()


def test_home_builds_in_both_modes(tmp_path):
    hub = make_hub(tmp_path)
    try:
        hub.show("home")
        hub.set_grouped(False)
        assert "home" in hub.pages
        hub.set_grouped(True)
        assert hub.current == "home"
    finally:
        hub.destroy()
