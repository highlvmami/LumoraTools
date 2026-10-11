"""Sistem bilgisi: CPU, bellek, disk, ağ hızı, pil ve sabit bilgiler (Tk'den bağımsız, test edilebilir).

`psutil` parametre olarak alınır; testler sahte bir nesneyle çalışır.
"""
from __future__ import annotations

import platform
import sys
import time
from collections import deque
from dataclasses import dataclass

from ...fmt import duration, human_size


@dataclass(frozen=True)
class DiskInfo:
    mount: str
    total: int
    used: int
    percent: float


@dataclass(frozen=True)
class BatteryInfo:
    percent: float
    plugged: bool | None
    seconds_left: int | None      # bilinmiyorsa ya da şarjdaysa None


@dataclass(frozen=True)
class Sample:
    ts: float
    cpu: float
    cores: tuple[float, ...]
    mem_used: int
    mem_total: int
    mem_percent: float
    swap_percent: float
    net_up: float                 # bayt/sn
    net_down: float
    disks: tuple[DiskInfo, ...]
    battery: BatteryInfo | None


class History:
    """Son N ölçümü tutar (grafik için)."""

    def __init__(self, size: int = 60) -> None:
        self.cpu: deque[float] = deque(maxlen=size)
        self.mem: deque[float] = deque(maxlen=size)

    def add(self, sample: Sample) -> None:
        self.cpu.append(sample.cpu)
        self.mem.append(sample.mem_percent)


class Sampler:
    def __init__(self, ps=None, clock=time.monotonic) -> None:
        if ps is None:
            import psutil as ps
        self.ps = ps
        self.clock = clock
        self._net: tuple[float, int, int] | None = None
        self.ps.cpu_percent(None, percpu=True)      # ilk çağrı anlamsızdır; ısındırılır

    def _disks(self) -> tuple[DiskInfo, ...]:
        out = []
        for part in self.ps.disk_partitions(all=False):
            if "cdrom" in (part.opts or "").lower() or not part.fstype:
                continue
            try:
                u = self.ps.disk_usage(part.mountpoint)
            except OSError:                          # boş sürücü, izin yok
                continue
            out.append(DiskInfo(part.mountpoint, u.total, u.used, u.percent))
        return tuple(out)

    def _battery(self) -> BatteryInfo | None:
        try:
            b = self.ps.sensors_battery()
        except Exception:
            return None
        if b is None:
            return None
        left = b.secsleft if isinstance(b.secsleft, int) and b.secsleft >= 0 else None
        return BatteryInfo(float(b.percent), b.power_plugged, left)

    def sample(self) -> Sample:
        now = self.clock()
        cores = tuple(float(c) for c in self.ps.cpu_percent(None, percpu=True))
        cpu = sum(cores) / len(cores) if cores else 0.0
        mem, swap = self.ps.virtual_memory(), self.ps.swap_memory()
        io = self.ps.net_io_counters()
        up = down = 0.0
        if io is not None:
            if self._net is not None:
                dt = max(now - self._net[0], 1e-6)
                up = max(0.0, (io.bytes_sent - self._net[1]) / dt)
                down = max(0.0, (io.bytes_recv - self._net[2]) / dt)
            self._net = (now, io.bytes_sent, io.bytes_recv)
        return Sample(time.time(), cpu, cores, mem.used, mem.total, float(mem.percent), float(swap.percent),
                      up, down, self._disks(), self._battery())


def cpu_name() -> str:
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    return platform.processor() or "bilinmiyor"


def static_info(ps=None, now: float | None = None) -> dict[str, str]:
    """Değişmeyen bilgiler (bilgisayar adı ve kullanıcı adı kasıtlı olarak YOK: kopyalanıp paylaşılabilir)."""
    if ps is None:
        import psutil as ps
    up = (time.time() if now is None else now) - ps.boot_time()
    return {
        "İşletim sistemi": platform.platform(),
        "İşlemci": cpu_name(),
        "Çekirdek": f"{ps.cpu_count(logical=False) or '?'} fiziksel / {ps.cpu_count(logical=True) or '?'} mantıksal",
        "Bellek (RAM)": human_size(ps.virtual_memory().total),
        "Açık kalma süresi": duration(up),
    }


def format_battery(b: BatteryInfo | None) -> str:
    if b is None:
        return "Pil yok"
    state = "şarjda" if b.plugged else "pilde"
    left = f", yaklaşık {duration(b.seconds_left)} kaldı" if b.seconds_left and not b.plugged else ""
    return f"%{b.percent:.0f} ({state}{left})"


def summary_text(info: dict[str, str], s: Sample) -> str:
    """Destek isterken kopyalanıp yapıştırılabilecek özet (kişisel bilgi içermez)."""
    lines = [f"{k}: {v}" for k, v in info.items()]
    lines += [f"CPU kullanımı: %{s.cpu:.0f}",
              f"Bellek: {human_size(s.mem_used)} / {human_size(s.mem_total)} (%{s.mem_percent:.0f})",
              f"Pil: {format_battery(s.battery)}"]
    lines += [f"Disk {d.mount}: {human_size(d.used)} / {human_size(d.total)} (%{d.percent:.0f})" for d in s.disks]
    return "\n".join(lines)
