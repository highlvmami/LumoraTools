from aracmerkezi import __version__
from aracmerkezi.changelog import CHANGELOG, entries_between, recent


def versions(entries):
    return [v for v, _ in entries]


def test_current_version_has_release_notes():
    """Her yayında sürüm notu yazılmak zorunda: güncel sürüm CHANGELOG'da olmalı."""
    assert __version__ in CHANGELOG, f"{__version__} için changelog.py'ye not ekle"


def test_every_entry_is_nonempty_text():
    for version, items in CHANGELOG.items():
        assert items and all(i.strip() for i in items), version


def test_upgrade_shows_only_versions_in_between_newest_first():
    got = entries_between("0.5.0", "0.6.2")
    assert versions(got) == ["0.6.2", "0.6.1", "0.6.0"]            # 0.5.0'ın kendisi dahil değil
    assert versions(entries_between("0.6.1", "0.6.2")) == ["0.6.2"]


def test_versions_newer_than_current_are_never_shown():
    assert versions(entries_between("0.4.0", "0.5.0")) == ["0.5.0", "0.4.2", "0.4.1"]


def test_same_version_shows_nothing():
    assert entries_between(__version__, __version__) == []


def test_fresh_install_shows_nothing():
    assert entries_between(None, __version__, fresh_install=True) == []


def test_unknown_previous_shows_only_current():
    assert versions(entries_between(None, "0.6.2")) == ["0.6.2"]


def test_garbage_previous_value_does_not_crash():
    assert versions(entries_between("sacma", "0.6.2")) == ["0.6.2"]


def test_limit_and_recent():
    assert len(entries_between("0.0.1", __version__, limit=3)) == 3
    r = recent(3)
    assert len(r) == 3 and versions(r) == sorted(versions(r), key=lambda v: tuple(map(int, v.split("."))), reverse=True)
