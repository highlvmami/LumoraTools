"""İşlem yöneticisi çekirdeği: örnekleme, gruplama ve GÜVENLİ sonlandırma (Tk'den bağımsız, test edilebilir).

Güvenlik ilkeleri:
  * Kritik Windows süreçleri (csrss, wininit, winlogon, services, lsass, smss, dwm…) ve sistem süreçleri (PID 0, 4)
    asla sonlandırılmaz; sonlandırılırsa Windows çöker ya da yeniden başlar.
  * Uygulamanın kendi süreci, üst süreçleri ve alt süreçleri korunur (kendi altındaki dalı kesmesin).
  * Explorer.exe gibi "çalışır ama dikkat" süreçleri uyarıyla sonlandırılabilir.
  * Önce nazikçe kapatma istenir (terminate); kapanmazsa ikinci bir adımla zorla (kill) denenir.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

CRITICAL = {
    "system", "system idle process", "registry", "memory compression", "secure system", "smss.exe", "csrss.exe",
    "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "lsm.exe", "dwm.exe", "fontdrvhost.exe",
    "sihost.exe", "ctfmon.exe", "svchost.exe", "audiodg.exe", "wudfhost.exe",
}
WARN = {"explorer.exe": "Windows kabuğu (görev çubuğu, masaüstü); kapanırsa ekran bir an kaybolur, "
                        "Görev Yöneticisi'nden yeniden başlatman gerekebilir."}


@dataclass(frozen=True)
class Proc:
    pid: int
    name: str
    cpu: float                     # yüzde (çekirdek başına değil toplam sisteme göre)
    rss: int                       # bayt
    status: str = ""
    pids: tuple[int, ...] = ()     # gruplu görünümde gruptaki tüm PID'ler
    count: int = 1

    @property
    def all_pids(self) -> tuple[int, ...]:
        return self.pids or (self.pid,)


class ProcessSampler:
    """psutil.Process nesnelerini önbellekte tutar; böylece cpu_percent anlamlı (iki ölçüm arası) çıkar."""

    def __init__(self, ps=None) -> None:
        if ps is None:
            import psutil as ps
        self.ps = ps
        self._cache: dict[tuple[int, float], object] = {}
        self._cpus = ps.cpu_count(logical=True) or 1

    def sample(self) -> list[Proc]:
        seen: dict[tuple[int, float], object] = {}
        out: list[Proc] = []
        for p in self.ps.process_iter():
            try:
                key = (p.pid, p.create_time())
                proc = self._cache.get(key, p)
                seen[key] = proc
                with proc.oneshot():
                    name = proc.name() or f"(adsız {proc.pid})"   # bazı sistem süreçleri boş ad döndürür
                    cpu = proc.cpu_percent(None) / self._cpus
                    mem = proc.memory_info().rss
                    status = proc.status()
                out.append(Proc(proc.pid, name, cpu, mem, status))
            except (self.ps.NoSuchProcess, self.ps.AccessDenied, self.ps.ZombieProcess):
                continue
        self._cache = seen
        return out


def group(procs: list[Proc]) -> list[Proc]:
    """Aynı adlı süreçleri tek satırda toplar (ör. Chrome'un 30 süreci). pid = gruptaki en büyük bellekli sürecin PID'i."""
    by: dict[str, list[Proc]] = {}
    for p in procs:
        by.setdefault(p.name.lower(), []).append(p)
    out = []
    for members in by.values():
        top = max(members, key=lambda m: m.rss)
        out.append(Proc(top.pid, top.name, sum(m.cpu for m in members), sum(m.rss for m in members),
                        top.status, tuple(sorted(m.pid for m in members)), len(members)))
    return out


def sort_procs(procs: list[Proc], by: str) -> list[Proc]:
    if by == "cpu":
        return sorted(procs, key=lambda p: (-p.cpu, -p.rss, p.name.lower()))
    if by == "ad":
        return sorted(procs, key=lambda p: (p.name.lower(), p.pid))
    return sorted(procs, key=lambda p: (-p.rss, p.name.lower()))      # varsayılan: bellek


def filter_procs(procs: list[Proc], query: str) -> list[Proc]:
    q = query.strip().lower()
    return [p for p in procs if q in p.name.lower() or q == str(p.pid)] if q else list(procs)


def own_pids(ps=None) -> set[int]:
    """Bu uygulamanın kendisi, üst süreçleri (PyInstaller önyükleyici dahil) ve tüm alt süreçleri."""
    if ps is None:
        import psutil as ps
    me = ps.Process(os.getpid())
    pids = {me.pid}
    try:
        pids |= {p.pid for p in me.parents()}
    except ps.Error:
        pass
    try:
        pids |= {p.pid for p in me.children(recursive=True)}
    except ps.Error:
        pass
    return pids


def risk(name: str, pid: int, protected_pids: set[int]) -> tuple[str, str]:
    """('block' | 'warn' | 'ok', gerekçe). 'block' ise sonlandırılmaz."""
    low = name.lower()
    if pid in (0, 4) or low in CRITICAL:
        return "block", f"{name} Windows'un çalışması için gerekli bir sistem süreci; sonlandırılamaz."
    if pid in protected_pids:
        return "block", f"{name} bu uygulamanın kendisi (ya da bağlı olduğu bir süreç); sonlandırılamaz."
    if low in WARN:
        return "warn", WARN[low]
    return "ok", ""


@dataclass
class KillResult:
    closed: list[int] = field(default_factory=list)
    blocked: list[tuple[int, str]] = field(default_factory=list)      # (pid, gerekçe)
    failed: list[tuple[int, str]] = field(default_factory=list)
    still_running: list[int] = field(default_factory=list)            # nazikçe kapanmayanlar: zorla kapatma önerilir


def terminate(pids: list[int], names: dict[int, str], protected: set[int], ps=None, force: bool = False,
              timeout: float = 3.0) -> KillResult:
    """Süreçleri sonlandırır. Engelli olanlara hiç dokunmaz. force=False: nazikçe iste, kapanmayanları bildir."""
    if ps is None:
        import psutil as ps
    result = KillResult()
    targets = []
    for pid in pids:
        level, reason = risk(names.get(pid, ""), pid, protected)
        if level == "block":
            result.blocked.append((pid, reason))
            continue
        try:
            proc = ps.Process(pid)
            proc.kill() if force else proc.terminate()
            targets.append(proc)
        except ps.NoSuchProcess:
            result.closed.append(pid)                                  # zaten kapanmış
        except ps.AccessDenied:
            result.failed.append((pid, "İzin yok (yönetici yetkisi gerekebilir)."))
        except ps.Error as e:
            result.failed.append((pid, str(e)))
    gone, alive = ps.wait_procs(targets, timeout=timeout)
    result.closed += [p.pid for p in gone]
    result.still_running += [p.pid for p in alive]
    return result
