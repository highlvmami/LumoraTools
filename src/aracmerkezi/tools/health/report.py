"""Pil ve disk sağlığı (Tk'den bağımsız, test edilebilir).

Pil: Windows'un `powercfg /batteryreport /xml` raporundan tasarım kapasitesi, tam şarj kapasitesi ve döngü sayısı okunur.
Disk: PowerShell `Get-PhysicalDisk` çıktısı (yönetici izni gerektirmez). Ayrıntılı SMART sayaçları
(sıcaklık, aşınma) yönetici izni ister; alınamazsa dürüstçe belirtilir.
Dış komutlar `runner` parametresiyle verilir; testler sahte komut çalıştırıcıyla çalışır.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass

GOOD, WARN, BAD, UNKNOWN = "iyi", "dikkat", "zayıf", "bilinmiyor"


def _flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


# ---------- pil ----------
@dataclass(frozen=True)
class BatteryHealth:
    design_mwh: int
    full_mwh: int
    cycles: int | None
    chemistry: str
    manufacturer: str

    @property
    def health_percent(self) -> float:
        return 100.0 * self.full_mwh / self.design_mwh if self.design_mwh else 0.0

    @property
    def verdict(self) -> str:
        return battery_verdict(self.health_percent)


def battery_verdict(percent: float) -> str:
    return GOOD if percent >= 80 else WARN if percent >= 60 else BAD


def parse_battery_xml(text: str) -> BatteryHealth | None:
    """powercfg raporundaki ilk pil. Ad alanlarına bakılmaksızın (namespace'siz) okunur; bozuksa None."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    battery = next((el for el in root.iter() if local(el.tag) == "Battery"), None)
    if battery is None:
        return None
    fields = {local(c.tag): (c.text or "").strip() for c in battery}
    try:
        design, full = int(fields["DesignCapacity"]), int(fields["FullChargeCapacity"])
    except (KeyError, ValueError):
        return None
    cycles = int(fields["CycleCount"]) if fields.get("CycleCount", "").isdigit() else None
    return BatteryHealth(design, full, cycles, fields.get("Chemistry", ""), fields.get("Manufacturer", ""))


def battery_report(runner=subprocess.run) -> BatteryHealth | None:
    """Pil raporunu geçici bir dosyaya yazdırıp okur ve dosyayı siler. Pil yoksa/okunamazsa None."""
    fd, path = tempfile.mkstemp(suffix=".xml", prefix="lumora_pil_")
    os.close(fd)
    try:
        runner(["powercfg", "/batteryreport", "/output", path, "/xml"], capture_output=True, timeout=60,
               creationflags=_flags())
        with open(path, "rb") as f:
            raw = f.read()
        return parse_battery_xml(raw.decode("utf-8-sig", errors="replace")) if raw else None
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------- disk ----------
@dataclass(frozen=True)
class DiskHealth:
    name: str
    media: str            # SSD / HDD / Unspecified
    bus: str              # NVMe, SATA, USB…
    health: str           # Healthy / Warning / Unhealthy
    status: str
    size: int

    @property
    def verdict(self) -> str:
        return {"healthy": GOOD, "warning": WARN, "unhealthy": BAD}.get(self.health.lower(), UNKNOWN)


_DISK_CMD = ("Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,OperationalStatus,BusType,Size"
             " | ConvertTo-Json -Compress")
_SMART_CMD = ("Get-PhysicalDisk | Get-StorageReliabilityCounter -ErrorAction Stop | "
              "Select-Object Temperature,Wear,PowerOnHours,ReadErrorsTotal,WriteErrorsTotal | ConvertTo-Json -Compress")


def parse_disks(text: str) -> list[DiskHealth]:
    """PowerShell'in JSON çıktısı: tek disk için nesne, birden çok için liste."""
    text = text.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = data if isinstance(data, list) else [data]
    return [DiskHealth(str(r.get("FriendlyName") or "Disk"), str(r.get("MediaType") or ""), str(r.get("BusType") or ""),
                       str(r.get("HealthStatus") or ""), str(r.get("OperationalStatus") or ""), int(r.get("Size") or 0))
            for r in rows if isinstance(r, dict)]


def _powershell(command: str, runner) -> str | None:
    try:
        done = runner(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True,
                      timeout=30, creationflags=_flags())
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.decode("utf-8", errors="replace")


def disk_health(runner=subprocess.run) -> list[DiskHealth]:
    out = _powershell(_DISK_CMD, runner)
    return parse_disks(out) if out else []


def smart_counters(runner=subprocess.run) -> list[dict] | None:
    """Sıcaklık/aşınma gibi ayrıntılar. Yönetici izni yoksa None (arayüz bunu açıkça söyler)."""
    out = _powershell(_SMART_CMD, runner)
    if not out or not out.strip():
        return None
    try:
        data = json.loads(out)
    except ValueError:
        return None
    rows = data if isinstance(data, list) else [data]
    return [r for r in rows if isinstance(r, dict)] or None
