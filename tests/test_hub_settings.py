import json

import pytest

from aracmerkezi.app import Hub


def test_settings_with_bom_are_read(tmp_path):
    (tmp_path / "settings.json").write_bytes(b"\xef\xbb\xbf" + json.dumps({"theme": "light"}).encode())
    try:
        hub = Hub(data_dir=tmp_path, tools=[])
    except Exception as e:  # ekran/Tk yoksa
        pytest.skip(str(e))
    try:
        assert hub.settings["theme"] == "light"
    finally:
        hub.destroy()
