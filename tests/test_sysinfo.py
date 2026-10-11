import os
import types

from aracmerkezi.tools.sysinfo import sampler as sm


class FakePsutil:
    """Kontrol edilebilir sahte psutil."""

    def __init__(self):
        self.cores = [10.0, 30.0]
        self.sent, self.recv = 1_000, 2_000
        self.battery = types.SimpleNamespace(percent=80, secsleft=3600, power_plugged=False)
        self.parts = [types.SimpleNamespace(mountpoint="C:\\", opts="rw,fixed", fstype="NTFS"),
                      types.SimpleNamespace(mountpoint="D:\\", opts="cdrom", fstype="CDFS"),
                      types.SimpleNamespace(mountpoint="E:\\", opts="rw", fstype=""),
                      types.SimpleNamespace(mountpoint="F:\\", opts="rw,removable", fstype="FAT32")]
        self.calls = 0

    def cpu_percent(self, interval=None, percpu=False):
        self.calls += 1
        return list(self.cores)

    def cpu_count(self, logical=True):
        return 4 if logical else 2

    def virtual_memory(self):
        return types.SimpleNamespace(used=4 * 2**30, total=8 * 2**30, percent=50.0)

    def swap_memory(self):
        return types.SimpleNamespace(percent=12.5)

    def net_io_counters(self):
        return types.SimpleNamespace(bytes_sent=self.sent, bytes_recv=self.recv)

    def sensors_battery(self):
        return self.battery

    def disk_partitions(self, all=False):
        return self.parts

    def disk_usage(self, mount):
        if mount.startswith("F"):
            raise PermissionError("sürücü hazır değil")
        return types.SimpleNamespace(total=100, used=40, percent=40.0)

    def boot_time(self):
        return 1_000.0


def test_sampler_primes_cpu_and_aggregates_values():
    ps = FakePsutil()
    s = sm.Sampler(ps, clock=lambda: 0.0)
    assert ps.calls == 1                                      # ilk (anlamsız) okuma ısındırma için yapıldı
    sample = s.sample()
    assert sample.cpu == 20.0 and sample.cores == (10.0, 30.0)
    assert sample.mem_percent == 50.0 and sample.swap_percent == 12.5 and sample.mem_total == 8 * 2**30
    assert [d.mount for d in sample.disks] == ["C:\\"]        # cdrom, dosya sistemsiz ve hazır olmayan sürücü atlanır
    assert sample.battery.percent == 80 and sample.battery.seconds_left == 3600


def test_network_rate_is_bytes_per_second_and_never_negative():
    ps, t = FakePsutil(), [0.0]
    s = sm.Sampler(ps, clock=lambda: t[0])
    assert (s.sample().net_up, s.sample().net_down) == (0.0, 0.0)    # ilk ölçümde hız yok
    t[0], ps.sent, ps.recv = 2.0, 1_000 + 4_000, 2_000 + 10_000
    r = s.sample()
    assert r.net_up == 2_000 and r.net_down == 5_000
    t[0], ps.sent = 3.0, 10                                          # sayaç sıfırlandı (ör. bağdaştırıcı yenilendi)
    assert s.sample().net_up == 0.0


def test_missing_battery_and_unknown_time_left():
    ps = FakePsutil()
    ps.battery = None
    assert sm.Sampler(ps).sample().battery is None
    ps.battery = types.SimpleNamespace(percent=55, secsleft=-2, power_plugged=True)     # psutil: -2 = bilinmiyor
    b = sm.Sampler(ps).sample().battery
    assert b.seconds_left is None and sm.format_battery(b) == "%55 (şarjda)"
    assert sm.format_battery(None) == "Pil yok"
    assert "yaklaşık 1 sa 00 dk kaldı" in sm.format_battery(sm.BatteryInfo(80, False, 3600))


def test_history_keeps_only_the_latest_values():
    h = sm.History(size=3)
    s = sm.Sampler(FakePsutil()).sample()
    for cpu in (1, 2, 3, 4, 5):
        h.add(sm.Sample(s.ts, cpu, s.cores, 0, 1, cpu * 10.0, 0, 0, 0, (), None))
    assert list(h.cpu) == [3, 4, 5] and list(h.mem) == [30.0, 40.0, 50.0]


def test_static_info_and_summary_contain_no_personal_identifiers():
    ps = FakePsutil()
    info = sm.static_info(ps, now=1_000.0 + 3 * 86_400 + 4 * 3_600)
    assert info["Çekirdek"] == "2 fiziksel / 4 mantıksal" and info["Açık kalma süresi"] == "3 gün 4 sa"
    assert info["Bellek (RAM)"] == "8.0 GB"
    text = sm.summary_text(info, sm.Sampler(ps).sample())
    assert "CPU kullanımı: %20" in text and "Disk C:\\" in text and "Pil: %80" in text
    for private in (os.environ.get("USERNAME", "\0"), os.environ.get("COMPUTERNAME", "\0")):
        assert private not in text                                 # kullanıcı/bilgisayar adı sızmaz


def test_real_psutil_sample_is_sane():
    s = sm.Sampler().sample()
    assert 0 <= s.cpu <= 100 and 0 <= s.mem_percent <= 100 and s.mem_total > 0 and s.disks
    assert sm.static_info()["İşlemci"]
