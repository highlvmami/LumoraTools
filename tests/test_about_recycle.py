import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from aracmerkezi import about, recycle


def test_compose_builds_prefixed_title_and_appends_info():
    title, body = about.compose("İstek", "Karanlık tema", "Daha koyu bir tema olsun.", True, "0.6.0")
    assert title == "[İstek] Karanlık tema"
    assert body.startswith("Daha koyu bir tema olsun.") and "LumoraTools v0.6.0" in body
    t2, b2 = about.compose("Hata", "", "Pano açılmıyor\nikinci satır", False, "0.6.0")
    assert t2 == "[Hata] Pano açılmıyor" and "LumoraTools" not in b2     # başlık boşsa ilk satırdan


def test_empty_message_is_rejected():
    with pytest.raises(about.EmptyMessage):
        about.compose("İstek", "x", "   \n ", True, "1.0")


def test_issue_url_roundtrips_special_characters():
    title, body = "[Hata] Çökme & donma", "satır 1\nsatır 2 — 100% ğüşiöç #1"
    url = about.issue_url(title, body)
    parsed = urlparse(url)
    assert url.startswith(about.NEW_ISSUE_URL + "?") and parsed.netloc == "github.com"
    qs = parse_qs(parsed.query)
    assert qs["title"] == [title] and qs["body"] == [body]


def test_issue_url_truncates_huge_bodies():
    url = about.issue_url("t", "x" * 20_000)
    assert len(parse_qs(urlparse(url).query)["body"][0]) == about.MAX_BODY


def test_system_info_has_no_personal_data():
    info = about.system_info("0.6.0")
    assert "0.6.0" in info and os.path.expanduser("~") not in info
    assert os.environ.get("USERNAME", "\0") not in info


def test_mailto_url():
    url = about.mailto_url("a@b.c", "[İstek] x", "mesaj")
    assert url.startswith("mailto:a@b.c?") and parse_qs(urlparse(url).query)["subject"] == ["[İstek] x"]


def test_pfrom_is_double_null_terminated_absolute_paths(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    s = recycle.build_pfrom([a, b])
    assert s.endswith("\0\0") and s.count("\0") == 3
    assert s.split("\0")[:2] == [str(a.resolve()), str(b.resolve())]


def test_move_to_trash_empty_list_is_noop():
    if sys.platform == "win32":
        assert recycle.move_to_trash([]) == []


@pytest.mark.skipif(sys.platform != "win32" or not os.environ.get("LUMORA_TEST_RECYCLE"),
                    reason="Gerçek Geri Dönüşüm Kutusu'na öğe bırakır; LUMORA_TEST_RECYCLE=1 ile açılır")
def test_move_to_trash_really_removes_files(tmp_path):
    files = [tmp_path / f"lumora-test-silinebilir-{i}.png" for i in range(2)]
    for f in files:
        f.write_bytes(b"x")
    assert sorted(recycle.move_to_trash(files)) == sorted(files)
    assert not any(f.exists() for f in files)
