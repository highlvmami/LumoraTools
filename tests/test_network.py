import socket
import subprocess
import threading
import types

import pytest

from aracmerkezi.tools.network import nettools as nt

EN = """
Pinging 8.8.8.8 with 32 bytes of data:
Reply from 8.8.8.8: bytes=32 time=12ms TTL=117
Reply from 8.8.8.8: bytes=32 time=18ms TTL=117
Request timed out.
Reply from 8.8.8.8: bytes=32 time<1ms TTL=117

Ping statistics for 8.8.8.8:
    Packets: Sent = 4, Received = 3, Lost = 1 (25% loss),
Approximate round trip times in milli-seconds:
    Minimum = 12ms, Maximum = 18ms, Average = 15ms
"""
TR = """
8.8.8.8 ile 32 bayt veri ile Ping yapılıyor:
8.8.8.8 yanıtı: bayt=32 süre=21ms TTL=117
8.8.8.8 yanıtı: bayt=32 süre=19ms TTL=117
İstek zaman aşımına uğradı.
Hedef ana bilgisayara ulaşılamıyor.
"""


@pytest.mark.parametrize("host", ["8.8.8.8", "google.com", "sub.domain-1.example.org", "localhost", "a", "example.com.",
                                  "2001:4860:4860::8888", "::1", "xn--bcher-kva.example"])
def test_valid_hosts(host):
    assert nt.valid_host(host)


@pytest.mark.parametrize("host", ["", "   ", "8.8.8.8 & calc", "a; rm -rf /", "x | dir", "`whoami`", "$(id)", "a b",
                                  "host\nname", "-n 9999", "evil.com/../x", "a" * 300, "-bad.com", "bad-.com", "..", "a..b",
                                  "http://x.com", "1.1.1.1 -t", "zz::zz::1"])
def test_command_injection_and_garbage_are_rejected(host):
    assert not nt.valid_host(host)


def test_parse_ping_is_language_independent():
    assert nt.parse_ping(EN) == [12.0, 18.0, 0.5]                      # "<1ms" → 0.5
    assert nt.parse_ping(TR) == [21.0, 19.0]
    assert nt.parse_ping("Request timed out.") == []


def test_ping_result_statistics_and_loss():
    r = nt.PingResult("x", 4, [10.0, 20.0, 30.0])
    assert r.received == 3 and r.loss_percent == 25.0 and r.stats == (10.0, 20.0, 30.0)
    assert nt.PingResult("x", 4).stats is None and nt.PingResult("x", 4).loss_percent == 100.0


def test_run_ping_uses_argument_list_never_a_shell_and_clamps_count():
    seen = {}

    def fake(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return types.SimpleNamespace(stdout=EN.encode("cp1254"))

    r = nt.run_ping("8.8.8.8", count=999, runner=fake)
    assert seen["cmd"][:3] == ["ping", "-n", "20"] and seen["cmd"][-1] == "8.8.8.8"      # en çok 20
    assert "shell" not in seen["kw"] and r.sent == 20 and r.received == 3


def test_run_ping_never_runs_for_an_invalid_host():
    def boom(*a, **k):
        raise AssertionError("geçersiz girdiyle komut çalıştırıldı!")

    r = nt.run_ping("8.8.8.8 & calc", runner=boom)
    assert r.error and r.received == 0


def test_run_ping_reports_os_errors_and_timeouts():
    def missing(*a, **k):
        raise FileNotFoundError("ping yok")

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("ping", 1)

    assert "çalıştırılamadı" in nt.run_ping("1.1.1.1", runner=missing).error
    assert "çalıştırılamadı" in nt.run_ping("1.1.1.1", runner=slow).error


def test_resolve_localhost_and_failures():
    ok = nt.resolve("localhost")
    assert ok.addresses and not ok.error and ok.millis >= 0
    assert nt.resolve("bu-alan-adi-kesinlikle-yok.invalid").error
    assert nt.resolve("a; calc").error == "Geçersiz ana bilgisayar adı veya IP adresi."


def test_check_port_against_a_real_local_listener_and_a_closed_port():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    t = threading.Thread(target=lambda: srv.accept()[0].close(), daemon=True)
    t.start()
    try:
        r = nt.check_port("127.0.0.1", port)
        assert r.open and r.millis >= 0 and not r.error
    finally:
        srv.close()
    closed = nt.check_port("127.0.0.1", port, timeout=0.5)                 # artık kimse dinlemiyor
    assert not closed.open and closed.error


def test_check_port_validates_input():
    assert nt.check_port("127.0.0.1", 0).error and nt.check_port("127.0.0.1", 70000).error
    assert nt.check_port("a & b", 80).error


def test_connections_and_listening_see_a_real_listener():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        conns = nt.list_connections()
        mine = [c for c in nt.listening(conns) if c.local == f"127.0.0.1:{port}"]
        assert mine and mine[0].process.lower().startswith("python") and mine[0].proto == "TCP"
        ports = [int(c.local.rsplit(":", 1)[-1]) for c in nt.listening(conns)]
        assert ports == sorted(ports)                                      # port numarasına göre sıralı
    finally:
        srv.close()


def test_adapters_have_names_and_are_sorted_up_first():
    rows = nt.adapters()
    assert rows and all(a.name for a in rows)
    ups = [a.up for a in rows]
    assert ups == sorted(ups, reverse=True)
