"""Ağ araçları çekirdeği: ping, DNS, port kontrolü, bağlantılar, dinleyen portlar, bağdaştırıcılar (Tk'den bağımsız).

Güvenlik: dışarıdan gelen ana bilgisayar adı komuta verilmeden önce katı biçimde doğrulanır ve komutlar
kabuk kullanmadan (argüman listesiyle) çalıştırılır; böylece `8.8.8.8 & calc` gibi girdiler çalıştırılamaz.
Port kontrolü yalnızca TEK bir host:port için bağlantı denemesidir (Test-NetConnection gibi); port taraması yoktur.
"""
from __future__ import annotations

import locale
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field

_HOST = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*\.?$")
_IPV6 = re.compile(r"^[0-9A-Fa-f:]{2,45}$")
_REPLY = re.compile(r"TTL=\d+", re.I)                    # TTL her dilde aynı yazılır: yanıt satırını güvenle ayırt eder
_MS = re.compile(r"[=<]\s*(\d+)\s*ms", re.I)             # "time=12ms", "time<1ms", "süre=12ms"


def valid_host(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    if _IPV6.match(text) and ":" in text:
        try:
            socket.inet_pton(socket.AF_INET6, text)
            return True
        except OSError:
            return False
    return bool(_HOST.match(text))


@dataclass
class PingResult:
    host: str
    sent: int
    times: list[float] = field(default_factory=list)      # yanıt süreleri (ms); "<1ms" 0.5 sayılır
    error: str = ""

    @property
    def received(self) -> int:
        return len(self.times)

    @property
    def loss_percent(self) -> float:
        return 100.0 * (self.sent - self.received) / self.sent if self.sent else 0.0

    @property
    def stats(self) -> tuple[float, float, float] | None:
        return (min(self.times), sum(self.times) / len(self.times), max(self.times)) if self.times else None


def parse_ping(output: str) -> list[float]:
    """Yanıt veren satırlardaki süreler (ms). Dil/yerel ayardan bağımsızdır (TTL ile yanıt satırı ayırt edilir)."""
    times: list[float] = []
    for line in output.splitlines():
        if not _REPLY.search(line):
            continue
        m = _MS.search(line)
        if m:
            ms = float(m.group(1))
            times.append(0.5 if "<" in m.group(0) and ms <= 1 else ms)
    return times


def run_ping(host: str, count: int = 4, timeout_ms: int = 2000, runner=subprocess.run) -> PingResult:
    host = host.strip()
    if not valid_host(host):
        return PingResult(host, count, error="Geçersiz ana bilgisayar adı veya IP adresi.")
    count = max(1, min(int(count), 20))
    cmd = ["ping", "-n", str(count), "-w", str(int(timeout_ms)), host]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        done = runner(cmd, capture_output=True, timeout=count * (timeout_ms / 1000 + 1) + 5, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        return PingResult(host, count, error=f"Ping çalıştırılamadı: {e}")
    text = done.stdout.decode(locale.getpreferredencoding(False), errors="replace")
    return PingResult(host, count, parse_ping(text))


@dataclass(frozen=True)
class DnsResult:
    host: str
    addresses: tuple[str, ...]
    millis: float
    error: str = ""


def resolve(host: str) -> DnsResult:
    host = host.strip()
    if not valid_host(host):
        return DnsResult(host, (), 0.0, "Geçersiz ana bilgisayar adı veya IP adresi.")
    start = time.perf_counter()
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        return DnsResult(host, (), (time.perf_counter() - start) * 1000, f"Çözümlenemedi: {e}")
    ms = (time.perf_counter() - start) * 1000
    seen: dict[str, None] = {}
    for info in infos:
        seen.setdefault(info[4][0], None)
    return DnsResult(host, tuple(seen), ms)


def reverse_lookup(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return None


@dataclass(frozen=True)
class PortResult:
    host: str
    port: int
    open: bool
    millis: float
    error: str = ""


def check_port(host: str, port: int, timeout: float = 2.0) -> PortResult:
    """Tek bir host:port'a TCP bağlantısı denemesi."""
    host = host.strip()
    if not valid_host(host):
        return PortResult(host, port, False, 0.0, "Geçersiz ana bilgisayar adı veya IP adresi.")
    if not 1 <= int(port) <= 65535:
        return PortResult(host, port, False, 0.0, "Port 1-65535 arasında olmalı.")
    start = time.perf_counter()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return PortResult(host, port, True, (time.perf_counter() - start) * 1000)
    except OSError as e:
        return PortResult(host, port, False, (time.perf_counter() - start) * 1000, str(e))


@dataclass(frozen=True)
class Connection:
    proto: str
    local: str
    remote: str
    status: str
    pid: int | None
    process: str


def _addr(a) -> str:
    return f"{a.ip}:{a.port}" if a else ""


def list_connections(ps=None) -> list[Connection]:
    """Etkin TCP/UDP bağlantıları ve dinleyen portlar, süreç adlarıyla. İzin olmayanlarda süreç adı boş kalır."""
    if ps is None:
        import psutil as ps
    names: dict[int, str] = {}
    out: list[Connection] = []
    try:
        conns = ps.net_connections(kind="inet")
    except (ps.AccessDenied, OSError):
        return out
    for c in conns:
        name = ""
        if c.pid:
            if c.pid not in names:
                try:
                    names[c.pid] = ps.Process(c.pid).name()
                except (ps.NoSuchProcess, ps.AccessDenied):
                    names[c.pid] = ""
            name = names[c.pid]
        proto = "TCP" if c.type == socket.SOCK_STREAM else "UDP"
        out.append(Connection(proto + ("6" if c.family == socket.AF_INET6 else ""), _addr(c.laddr), _addr(c.raddr),
                              c.status if c.status and c.status != "NONE" else "", c.pid, name))
    return out


def listening(conns: list[Connection]) -> list[Connection]:
    """Bu bilgisayarda dışarıdan bağlantı bekleyen TCP portları (LISTEN), port numarasına göre sıralı."""
    rows = [c for c in conns if c.proto.startswith("TCP") and c.status == "LISTEN"]
    return sorted(rows, key=lambda c: (int(c.local.rsplit(":", 1)[-1]), c.local))


@dataclass(frozen=True)
class Adapter:
    name: str
    up: bool
    speed_mbps: int
    ipv4: tuple[str, ...]
    ipv6: tuple[str, ...]
    mac: str


def adapters(ps=None) -> list[Adapter]:
    if ps is None:
        import psutil as ps
    stats = ps.net_if_stats()
    out = []
    for name, addrs in ps.net_if_addrs().items():
        v4 = tuple(a.address for a in addrs if a.family == socket.AF_INET)
        v6 = tuple(a.address.split("%")[0] for a in addrs if a.family == socket.AF_INET6)
        mac = next((a.address for a in addrs if a.family == ps.AF_LINK), "")
        st = stats.get(name)
        out.append(Adapter(name, bool(st and st.isup), int(st.speed) if st else 0, v4, v6, mac))
    return sorted(out, key=lambda a: (not a.up, not a.ipv4, a.name.lower()))
