"""Program Kaldırıcı, Sistem Bilgisi, İşlem Yöneticisi, Ağ, Pil/Disk, Yapılacaklar ve Zaman Takibi sayfaları.

Güvenlik: gerçek süreç sonlandırma, program kaldırma ve ağ ping'i YAPILMAZ; yalnızca onay akışları ve
komuta verilen argümanlar doğrulanır (ilgili çağrılar yakalanır).
"""
import json
import time
from datetime import date, datetime

import pytest

from aracmerkezi import __version__, themes, ui

pytestmark = pytest.mark.filterwarnings("ignore:Exception in thread:pytest.PytestUnhandledThreadExceptionWarning")


def make_hub(tmp_path):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    (data / "settings.json").write_text(json.dumps({"update": {"check_on_start": False}, "last_seen_version": __version__}),
                                        encoding="utf-8")
    try:
        from aracmerkezi.app import Hub
        hub = Hub(data_dir=data)
    except Exception as e:
        pytest.skip(str(e))
    hub.errors = []
    hub.report_callback_exception = lambda exc, val, tb: hub.errors.append(val)
    hub.geometry("1100x800+10+10")
    hub.update()
    return hub


@pytest.fixture
def hub(tmp_path):
    h = make_hub(tmp_path)
    yield h
    try:
        h.destroy()
    except Exception:
        pass
    ui.apply_theme(themes.DEFAULT)


def wait_for(hub, cond, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        hub.update()
        if cond():
            return True
        time.sleep(0.03)
    return False


def yes(monkeypatch, record=None):
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: (record.append(a) if record is not None else None) or True)


# ---------- Program Kaldırıcı ----------
def test_uninstall_page_lists_filters_sorts_and_launches_only_after_confirmation(hub, monkeypatch):
    from aracmerkezi.tools.uninstall import page as up
    GUID = "{AC76BA86-7AD7-1033-7B44-AC0F074E4100}"

    class Fake:
        def entries(self):
            return [("Tüm kullanıcılar", {"DisplayName": "Küçük Uygulama", "EstimatedSize": 100, "UninstallString": "k.exe /u"}),
                    ("Tüm kullanıcılar", {"DisplayName": "Büyük Uygulama", "EstimatedSize": 900000, "Publisher": "Acme",
                                          "UninstallString": f"MsiExec.exe /I{GUID}"}),
                    ("Tüm kullanıcılar", {"DisplayName": "Silinemez", "UninstallString": "x", "NoRemove": 1})]

    monkeypatch.setattr(up.pr, "WinBackend", lambda: Fake())
    launched = []
    monkeypatch.setattr(up.subprocess, "Popen", lambda cmd, **k: launched.append((cmd, k)))
    hub.show("kaldir")
    page = hub.pages["kaldir"]
    names = lambda: [page.tree.item(i, "values")[0] for i in page.tree.get_children()]
    assert names() == ["Büyük Uygulama", "Küçük Uygulama", "Silinemez"]  or names() == sorted(names(), key=str.lower)
    page.sort_var.set("Boyuta göre")
    page.render()
    assert names()[0] == "Büyük Uygulama"
    page.entry.insert(0, "acme")                                            # yayıncıya göre de arar
    page.render()
    assert names() == ["Büyük Uygulama"]

    page.tree.selection_set(page.tree.get_children()[0])
    hub.update()
    assert page.remove_btn.cget("state") == "normal"
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: False)       # vazgeçti → hiçbir şey çalışmaz
    page.remove()
    assert launched == []
    yes(monkeypatch)
    page.remove()
    assert launched[0][0] == ["msiexec.exe", "/x", GUID] and "shell" not in launched[0][1]   # MSI: kaldır (/x), kabuk yok
    assert "başlatıldı" in page.status.cget("text")

    page.entry.delete(0, "end")
    page.render()
    row = next(i for i in page.tree.get_children() if page.tree.item(i, "values")[0] == "Silinemez")
    page.tree.selection_set(row)
    hub.update()
    assert page.remove_btn.cget("state") == "disabled" and "kaldırıcıya sahip değil" in page.status.cget("text")
    assert not hub.errors, hub.errors


# ---------- Sistem Bilgisi ----------
def test_sysinfo_page_updates_live_and_copies_a_private_summary(hub, monkeypatch):
    import os
    hub.show("sistem")
    page = hub.pages["sistem"]
    page._update(page.sampler.sample())
    hub.update()
    assert page.cpu_card.value.cget("text").startswith("%") and page.mem_card.value.cget("text").startswith("%")
    assert page.disk_rows and page.last is not None
    page.copy_summary()
    text = hub.clipboard_get()
    assert "CPU kullanımı" in text and "Bellek" in text
    for private in (os.environ.get("USERNAME", "\0"), os.environ.get("COMPUTERNAME", "\0")):
        assert private not in text
    assert not hub.errors, hub.errors


# ---------- İşlem Yöneticisi ----------
class FakeSampler:
    def __init__(self, rows):
        self.rows = rows

    def sample(self):
        return list(self.rows)


def test_process_page_groups_blocks_critical_and_asks_before_terminating(hub, monkeypatch):
    from aracmerkezi.tools.processes import page as pp
    from aracmerkezi.tools.processes.procs import KillResult, Proc
    rows = [Proc(10, "chrome.exe", 1.0, 500), Proc(11, "chrome.exe", 2.0, 700), Proc(20, "notepad.exe", 0.1, 100),
            Proc(30, "csrss.exe", 0.0, 300)]
    killed = []
    monkeypatch.setattr(pp.pc, "terminate",
                        lambda pids, names, protected, force=False: (killed.append((tuple(pids), force)),
                                                                     KillResult(closed=list(pids)))[1])
    warned = []
    monkeypatch.setattr("tkinter.messagebox.showwarning", lambda *a, **k: warned.append(a))
    hub.show("islem")
    page = hub.pages["islem"]
    page.live_var.set(False)                                                # gerçek ölçüm yapma
    page.events.put(("sample", rows))
    page._drain()
    names = [page.tree.item(i, "values")[0] for i in page.tree.get_children()]
    assert "chrome.exe  (2 süreç)" in names and len(names) == 3             # chrome tek satırda toplandı

    chrome = next(i for i in page.tree.get_children() if "chrome" in page.tree.item(i, "values")[0])
    page.tree.selection_set(chrome)
    hub.update()
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: False)
    page.terminate_selected()                                               # vazgeçti
    time.sleep(0.2)
    assert killed == []
    yes(monkeypatch)
    page.terminate_selected()
    assert wait_for(hub, lambda: killed)
    assert killed[0][0] == (10, 11) and killed[0][1] is False               # grubun iki PID'i, nazikçe

    critical = next(i for i in page.tree.get_children() if "csrss" in page.tree.item(i, "values")[0])
    page.tree.selection_set(critical)
    hub.update()
    assert "sistem süreci" in page.status.cget("text")
    before = len(killed)
    page.terminate_selected()
    assert warned and len(killed) == before                                 # korumalı: uyarı, sonlandırma yok
    assert not hub.errors, hub.errors


def test_process_page_sampling_runs_in_background_and_renders_real_data(hub):
    hub.show("islem")
    page = hub.pages["islem"]
    assert wait_for(hub, lambda: len(page.tree.get_children()) > 5, timeout=20)
    assert "süreç" in page.summary.cget("text") and not hub.errors


# ---------- Ağ Araçları ----------
def test_network_page_validates_input_and_shows_results(hub, monkeypatch):
    from aracmerkezi.tools.network import page as np
    from aracmerkezi.tools.network.nettools import PingResult
    hub.show("ag")
    page = hub.pages["ag"]
    assert wait_for(hub, lambda: page.conn_count.cget("text") != "", timeout=15)          # bağlantılar yüklendi

    calls = []
    monkeypatch.setattr(np.nt.subprocess, "run", lambda *a, **k: calls.append(a))
    page.ping_entry.insert(0, "8.8.8.8 & calc")
    page.start_ping()
    assert wait_for(hub, lambda: "Geçersiz" in page.ping_out.get("1.0", "end"))
    assert calls == []                                                                     # geçersiz girdiyle komut çalışmadı

    page._on_ping(PingResult("x.com", 4, [10.0, 20.0, 30.0]))
    out = page.ping_out.get("1.0", "end")
    assert "3 yanıt" in out and "%25 kayıp" in out and "ortalama 20 ms" in out
    page._on_ping(PingResult("x.com", 4))
    assert "Hiç yanıt gelmedi" in page.ping_out.get("1.0", "end")

    page.dns_entry.insert(0, "localhost")
    page.start_dns()
    assert wait_for(hub, lambda: "adres" in page.dns_out.get("1.0", "end"))

    page.port_entry.insert(0, "127.0.0.1")
    page.port_port.delete(0, "end")
    page.port_port.insert(0, "abc")
    page.start_port()
    assert "sayı olmalı" in page.port_out.get("1.0", "end")
    assert not hub.errors, hub.errors


# ---------- Pil ve Disk Sağlığı ----------
def test_health_page_renders_battery_and_disk_verdicts(hub, monkeypatch):
    from aracmerkezi.tools.health import page as hp
    from aracmerkezi.tools.health.report import BatteryHealth, DiskHealth
    monkeypatch.setattr(hp.hr, "battery_report", lambda: BatteryHealth(42067, 32954, 307, "LIon", "SMP"))
    monkeypatch.setattr(hp.hr, "disk_health", lambda: [DiskHealth("KINGSTON", "SSD", "NVMe", "Healthy", "OK", 500107862016),
                                                       DiskHealth("ESKİ", "HDD", "SATA", "Warning", "OK", 1000204886016)])
    monkeypatch.setattr(hp.hr, "smart_counters", lambda: None)
    hub.show("saglik")
    page = hub.pages["saglik"]
    assert wait_for(hub, lambda: not page.loading and page.scroll.winfo_children(), timeout=15)

    def texts(w):
        out = []
        for c in w.winfo_children():
            try:
                out.append(c.cget("text"))
            except Exception:
                pass
            out += texts(c)
        return out

    all_text = " | ".join(t for t in texts(page.scroll) if isinstance(t, str))
    assert "%78" in all_text and "307" in all_text and "Dikkat" in all_text           # pil %78 → dikkat
    assert "KINGSTON" in all_text and "İyi" in all_text and "ESKİ" in all_text
    assert "yönetici" in all_text                                                      # SMART alınamadı: dürüstçe söylenir
    assert not hub.errors, hub.errors


def test_health_page_says_when_there_is_no_battery(hub, monkeypatch):
    from aracmerkezi.tools.health import page as hp
    monkeypatch.setattr(hp.hr, "battery_report", lambda: None)
    monkeypatch.setattr(hp.hr, "disk_health", lambda: [])
    monkeypatch.setattr(hp.hr, "smart_counters", lambda: None)
    monkeypatch.setattr("psutil.sensors_battery", lambda: None)
    hub.show("saglik")
    page = hub.pages["saglik"]
    assert wait_for(hub, lambda: not page.loading and page.scroll.winfo_children(), timeout=15)
    labels = [getattr(c, "cget", lambda *_: "")("text") for c in page.scroll.winfo_children()[0].winfo_children()]
    assert any("pil yok" in str(t) for t in labels)


# ---------- Yapılacaklar ----------
def test_todo_page_add_filter_complete_edit_and_clear(hub, monkeypatch):
    hub.show("gorev")
    page = hub.pages["gorev"]
    page.title_entry.insert(0, "Fatura öde")
    page.due_entry.insert(0, "01.01.2020")                                           # geçmiş tarih → gecikmiş
    page.prio_var.set("Acil")
    page.add_task()
    page.title_entry.insert(0, "Süt al")
    page.add_task()
    assert [t.title for t in page.store.list("open")] == ["Fatura öde", "Süt al"]    # acil önce
    assert page.title_entry.get() == "" and page.due_entry.get() == ""                # form temizlendi
    page.filter_var.set("Geciken")
    page.refresh()
    assert [t.title for t in page.store.list("overdue")] == ["Fatura öde"]

    page.title_entry.insert(0, "   ")                                                 # boş başlık reddedilir
    page.add_task()
    assert "boş olamaz" in page.message.cget("text")
    page.title_entry.delete(0, "end")
    page.due_entry.insert(0, "yarın")
    page.title_entry.insert(0, "Geçersiz tarihli")
    page.add_task()
    assert len(page.store.list("all")) == 2 and "Geçersiz tarih" in page.message.cget("text")

    first = page.store.list("open")[0]
    page.toggle(first.id)
    assert [t.title for t in page.store.list("done")] == ["Fatura öde"]
    page.edit(page.store.list("open")[0].id)
    from aracmerkezi.tools.todo.page import TaskDialog
    dlg = next(w for w in hub.winfo_children() if isinstance(w, TaskDialog))
    dlg.title_entry.delete(0, "end")
    dlg.title_entry.insert(0, "Süt ve ekmek al")
    dlg.due_entry.insert(0, "25.12.2030")
    dlg.prio.set("Yüksek")
    dlg._save()
    t = page.store.list("open")[0]
    assert t.title == "Süt ve ekmek al" and t.due == "2030-12-25" and t.priority == 1
    yes(monkeypatch)
    page.clear_done()
    assert page.store.list("done") == [] and len(page.store.list("open")) == 1
    assert not hub.errors, hub.errors


# ---------- Zaman Takibi ----------
def test_timetrack_is_off_by_default_records_only_app_names_and_can_be_cleared(hub, monkeypatch):
    from aracmerkezi.tools.timetrack import page as tp
    from aracmerkezi.tools.timetrack import tracker as tt
    from aracmerkezi.tools.timetrack.service import get_service
    svc = get_service(hub)
    assert svc.enabled is False and svc.tracker.paused is True                      # varsayılan: kapalı
    hub.show("zaman")
    page = hub.pages["zaman"]
    assert "Takip kapalı" in " ".join(str(getattr(w, "cget", lambda *_: "")("text")) for w in page.apps.winfo_children())

    today = date.today().isoformat()
    svc.store.add(today, "chrome.exe", 3600)
    svc.store.add(today, "code.exe", 1800)
    svc.store.add(today, tt.IDLE, 600)
    page.render()
    assert page.active_card.value.cget("text") == "1 sa 30 dk" and page.idle_card.value.cget("text") == "10 dk"
    assert page.top_card.value.cget("text") == "Google Chrome"

    clock = {"t": datetime.now().replace(hour=12).timestamp()}
    svc.tracker.now = lambda: clock["t"]
    svc.tracker.foreground = lambda: "spotify.exe"
    svc.tracker.idle_seconds = lambda: 0.0
    page.enabled_var.set(True)
    page.toggle_tracking()
    assert svc.enabled and svc.tracker.paused is False and "Kaydediyor" in page.state.cget("text")
    svc.stop()                                                                       # gerçek zamanlayıcıyı durdur, elle sür
    svc.tracker.tick()
    clock["t"] += 5
    svc.tracker.tick()
    assert svc.store.totals(today).get("spotify.exe") == 5.0

    page.select("spotify.exe")
    yes(monkeypatch)
    page.ignore_selected()
    assert "spotify.exe" not in svc.store.totals(today) and "spotify.exe" in svc.tracker.ignore
    assert "spotify.exe" in svc.cfg["ignore"]
    cols = [r[1] for r in svc.store.db.execute("PRAGMA table_info(usage)")]
    assert cols == ["day", "app", "seconds"]                                         # başlık/URL gibi sütun yok
    page.clear_data()
    assert svc.store.totals(today) == {} and not hub.errors, hub.errors
    assert tp.long_date(date(2026, 10, 11)) == "11 Ekim 2026, Pazar"


# ---------- kenar çubuğu: çok araç olsa da sabit düğmeler görünür kalır ----------
def test_sidebar_keeps_settings_guides_and_contact_visible_with_many_tools(hub):
    hub.geometry("1100x720+10+10")                                  # uygulamanın varsayılan (en küçük) yüksekliği
    hub.update()
    assert len(hub.tools) >= 14
    bottom = hub.winfo_rooty() + hub.winfo_height()
    for key in ("settings", "guides", "contact"):
        btn = hub.nav[key]
        assert btn.winfo_ismapped()
        assert btn.winfo_rooty() + btn.winfo_height() <= bottom, f"{key} penceren dışına taşıyor"
    ys = [hub.nav[k].winfo_rooty() for k in ("contact", "guides", "settings")]
    assert ys == sorted(ys)                                         # sıra: İletişim, Rehberler, Ayarlar (yukarıdan aşağı)
    first_tool = hub.nav[hub.tools[0].id]
    assert first_tool.winfo_rooty() < hub.nav["contact"].winfo_rooty()
    hub.show("settings")                                            # Ayarlar'a ulaşılabiliyor
    hub.update()
    assert hub.current == "settings"
