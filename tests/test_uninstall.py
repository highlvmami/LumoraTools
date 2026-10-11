import sys

import pytest

from aracmerkezi.tools.uninstall import programs as pr

MSI_GUID = "{AC76BA86-7AD7-1033-7B44-AC0F074E4100}"


class Fake:
    def __init__(self, rows):
        self.rows = rows

    def entries(self):
        return self.rows


def row(name, scope="Tüm kullanıcılar", **kw):
    return (scope, {"DisplayName": name, **kw})


def names(programs):
    return [p.name for p in programs]


def test_hides_system_components_updates_and_unnamed_entries():
    rows = [row("Uygulama A", UninstallString="a.exe /u"),
            row("Gizli Bileşen", SystemComponent=1, UninstallString="x"),
            row("Güvenlik Düzeltmesi", ParentKeyName="Windows", UninstallString="x"),
            row("Hotfix", ReleaseType="Hotfix", UninstallString="x"),
            row("KB5031234", UninstallString="x"),
            row("Security Update for Foo", UninstallString="x"),
            ("Tüm kullanıcılar", {"UninstallString": "adsiz.exe"})]
    assert names(pr.list_programs(Fake(rows))) == ["Uygulama A"]
    assert len(pr.list_programs(Fake(rows), include_updates=True)) == 5                 # sistem bileşeni ve adsız yine yok


def test_fields_size_date_and_removable_flags():
    rows = [row("Büyük", EstimatedSize=2048, InstallDate="20260211", DisplayVersion="1.2", Publisher="Acme",
                UninstallString="u.exe", InstallLocation='"C:\\Prog"'),
            row("Silinemez", UninstallString="u.exe", NoRemove=1),
            row("Kaldırıcısız")]
    big, norem, nouninst = pr.list_programs(Fake(rows))
    assert big.size == 2048 * 1024 and big.install_date == "2026-02-11" and big.location == "C:\\Prog" and big.removable
    assert not norem.removable and not nouninst.removable and nouninst.size is None
    assert pr.parse_date("2026") == "" and pr.parse_date("") == "" and pr.parse_date(None) == "" and pr.parse_date("18991231") == ""


def test_duplicates_are_merged_preferring_the_one_with_a_size():
    rows = [row("Aynı", DisplayVersion="1", UninstallString="a"),
            row("aynı", DisplayVersion="1", EstimatedSize=100, UninstallString="a"),
            row("Aynı", DisplayVersion="2", UninstallString="a")]
    progs = pr.list_programs(Fake(rows))
    assert len(progs) == 2 and next(p for p in progs if p.version == "1").size == 102400


def test_msi_uninstall_uses_remove_not_modify():
    p = pr.list_programs(Fake([row("Reader", UninstallString=f"MsiExec.exe /I{MSI_GUID}")]))[0]
    assert pr.uninstall_command(p) == ["msiexec.exe", "/x", MSI_GUID]                    # /I (değiştir) → /x (kaldır)
    p2 = pr.list_programs(Fake([row("Reader2", UninstallString=f"msiexec /x {MSI_GUID} /qb")]))[0]
    assert pr.uninstall_command(p2) == ["msiexec.exe", "/x", MSI_GUID]                   # fazladan bayraklar atılır


def test_non_msi_uses_registered_command_verbatim_and_unremovable_gives_none():
    p = pr.list_programs(Fake([row("Spotify", UninstallString='"C:\\S\\uninstall.exe" /silent')]))[0]
    assert pr.uninstall_command(p) == '"C:\\S\\uninstall.exe" /silent'
    q = pr.list_programs(Fake([row("Sabit", UninstallString="x.exe", NoRemove=1)]))[0]
    assert pr.uninstall_command(q) is None


def test_msi_guid_without_msiexec_is_not_treated_as_msi():
    p = pr.list_programs(Fake([row("Garip", UninstallString=f'"C:\\g\\kaldir.exe" --id {MSI_GUID}')]))[0]
    assert pr.uninstall_command(p) == p.uninstall


def test_sorting():
    rows = [row("B", EstimatedSize=10, InstallDate="20240101", UninstallString="x"),
            row("A", UninstallString="x"),
            row("C", EstimatedSize=500, InstallDate="20260101", UninstallString="x")]
    progs = pr.list_programs(Fake(rows))
    assert names(pr.sort_programs(progs, "ad")) == ["A", "B", "C"]
    assert names(pr.sort_programs(progs, "boyut")) == ["C", "B", "A"]                   # bilinmeyen boyut sonda
    assert names(pr.sort_programs(progs, "tarih")) == ["C", "B", "A"]                   # en yeni önce, tarihsiz sonda


@pytest.mark.skipif(sys.platform != "win32", reason="yalnızca Windows")
def test_real_read_only_listing_on_this_machine():
    progs = pr.list_programs(pr.WinBackend())
    assert progs and all(p.name for p in progs)
    assert all(p.size is None or p.size > 0 for p in progs)
