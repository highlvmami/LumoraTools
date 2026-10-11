import os
import subprocess
import sys
import time

import psutil
import pytest

from aracmerkezi.tools.processes import procs as pc
from aracmerkezi.tools.processes.procs import Proc


def P(pid, name, cpu=0.0, rss=0):
    return Proc(pid, name, cpu, rss)


def test_grouping_sums_and_keeps_all_pids():
    rows = [P(10, "chrome.exe", 1.0, 300), P(11, "Chrome.exe", 2.0, 500), P(12, "chrome.exe", 0.5, 200),
            P(20, "code.exe", 3.0, 100)]
    g = {p.name.lower(): p for p in pc.group(rows)}
    c = g["chrome.exe"]
    assert c.count == 3 and c.cpu == 3.5 and c.rss == 1000 and c.all_pids == (10, 11, 12)
    assert c.pid == 11                                              # en büyük bellekli süreç
    assert g["code.exe"].count == 1 and g["code.exe"].all_pids == (20,)


def test_sort_and_filter():
    rows = [P(1, "b.exe", 5, 100), P(2, "A.exe", 1, 900), P(3, "c.exe", 9, 50)]
    assert [p.name for p in pc.sort_procs(rows, "bellek")] == ["A.exe", "b.exe", "c.exe"]
    assert [p.name for p in pc.sort_procs(rows, "cpu")] == ["c.exe", "b.exe", "A.exe"]
    assert [p.name for p in pc.sort_procs(rows, "ad")] == ["A.exe", "b.exe", "c.exe"]
    assert [p.pid for p in pc.filter_procs(rows, "EXE")] == [1, 2, 3] and [p.pid for p in pc.filter_procs(rows, "a.")] == [2]
    assert [p.pid for p in pc.filter_procs(rows, "3")] == [3] and pc.filter_procs(rows, "yok") == []


@pytest.mark.parametrize("name", ["csrss.exe", "WININIT.EXE", "lsass.exe", "services.exe", "svchost.exe", "System",
                                  "winlogon.exe", "dwm.exe", "Registry"])
def test_critical_system_processes_are_always_blocked(name):
    level, reason = pc.risk(name, 1234, set())
    assert level == "block" and "sistem süreci" in reason


def test_pid_0_and_4_and_own_chain_are_blocked_and_explorer_warns():
    assert pc.risk("bir.exe", 0, set())[0] == "block" and pc.risk("bir.exe", 4, set())[0] == "block"
    level, reason = pc.risk("LumoraTools.exe", 77, {77, 5})
    assert level == "block" and "bu uygulamanın kendisi" in reason
    assert pc.risk("explorer.exe", 99, set())[0] == "warn"
    assert pc.risk("notepad.exe", 99, set()) == ("ok", "")


def test_own_pids_contains_self_and_parents_and_children():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        mine = pc.own_pids()
        assert os.getpid() in mine and child.pid in mine
        assert psutil.Process().ppid() in mine                      # üst süreç (PyInstaller önyükleyicisi gibi)
    finally:
        child.kill()
        child.wait()


class FakePs:
    """terminate()'in psutil'e bağımlılığını denemek için."""
    NoSuchProcess = psutil.NoSuchProcess
    AccessDenied = psutil.AccessDenied
    Error = psutil.Error

    def __init__(self, behaviours):
        self.behaviours = behaviours
        self.touched = []

    def Process(self, pid):                                          # noqa: N802 (psutil API'si)
        self.touched.append(pid)
        b = self.behaviours[pid]
        if b == "gone":
            raise psutil.NoSuchProcess(pid)
        if b == "denied":
            raise psutil.AccessDenied(pid)
        return type("Proc", (), {"pid": pid, "terminate": lambda s: None, "kill": lambda s: None})()

    def wait_procs(self, procs, timeout):
        stubborn = [p for p in procs if self.behaviours[p.pid] == "stubborn"]
        return [p for p in procs if p not in stubborn], stubborn


def test_terminate_never_touches_blocked_processes_and_reports_each_outcome():
    ps = FakePs({10: "ok", 11: "gone", 12: "denied", 13: "stubborn"})
    names = {10: "a.exe", 11: "b.exe", 12: "c.exe", 13: "d.exe", 4: "System", 20: "csrss.exe", 77: "Lumora.exe"}
    res = pc.terminate([10, 11, 12, 13, 4, 20, 77], names, protected={77}, ps=ps)
    assert sorted(res.closed) == [10, 11] and [p for p, _ in res.failed] == [12] and res.still_running == [13]
    assert sorted(p for p, _ in res.blocked) == [4, 20, 77]
    assert 4 not in ps.touched and 20 not in ps.touched and 77 not in ps.touched      # engelliler hiç açılmadı


def test_real_sampler_sees_this_python_process():
    s = pc.ProcessSampler()
    first = s.sample()
    second = s.sample()                                               # ikinci ölçüm: önbellekle CPU anlamlı
    me = [p for p in second if p.pid == os.getpid()]
    assert me and me[0].rss > 0 and 0 <= me[0].cpu <= 100
    assert len(first) > 20 and all(p.name for p in second)


def test_real_terminate_of_our_own_harmless_child_process():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        protected = pc.own_pids() - {child.pid}                       # kendi çocuğumuz hedef; kendimiz ve üst süreçler korunur
        res = pc.terminate([child.pid], {child.pid: "python.exe"}, protected)
        assert child.pid in res.closed and not res.blocked and not res.still_running
        time.sleep(0.2)
        assert child.poll() is not None                               # gerçekten kapandı
    finally:
        if child.poll() is None:
            child.kill()


def test_real_terminate_refuses_the_test_process_itself():
    res = pc.terminate([os.getpid()], {os.getpid(): "python.exe"}, pc.own_pids())
    assert res.blocked and not res.closed                             # kendi kendini öldürmeyi reddeder
