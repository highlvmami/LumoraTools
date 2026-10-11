import os
import subprocess
import sys
import types

import pytest

from aracmerkezi.tools.health import report as hr

XML = """<?xml version="1.0" encoding="UTF-8"?>
<BatteryReport xmlns="http://schemas.microsoft.com/battery/2012">
  <ReportInformation><ReportVersion>1.1</ReportVersion></ReportInformation>
  <Batteries>
    <Battery>
      <Id>DELL ABC1234</Id><Manufacturer>SMP</Manufacturer><SerialNumber>000</SerialNumber>
      <Chemistry>LIon</Chemistry><DesignCapacity>42067</DesignCapacity>
      <FullChargeCapacity>32954</FullChargeCapacity><CycleCount>307</CycleCount>
    </Battery>
    <Battery><DesignCapacity>1</DesignCapacity><FullChargeCapacity>1</FullChargeCapacity></Battery>
  </Batteries>
</BatteryReport>"""


def test_battery_xml_is_parsed_with_namespace_and_health_computed():
    b = hr.parse_battery_xml(XML)
    assert (b.design_mwh, b.full_mwh, b.cycles, b.chemistry, b.manufacturer) == (42067, 32954, 307, "LIon", "SMP")
    assert round(b.health_percent, 1) == 78.3 and b.verdict == hr.WARN       # ilk pil alınır (ikincisi yok sayılır)


def test_battery_verdict_thresholds():
    assert hr.battery_verdict(100) == hr.GOOD and hr.battery_verdict(80) == hr.GOOD
    assert hr.battery_verdict(79.9) == hr.WARN and hr.battery_verdict(60) == hr.WARN
    assert hr.battery_verdict(59.9) == hr.BAD and hr.battery_verdict(0) == hr.BAD


@pytest.mark.parametrize("text", ["", "bu xml değil", "<a><b/></a>", "<r><Battery><DesignCapacity>x</DesignCapacity></Battery></r>",
                                  "<r><Battery><DesignCapacity>10</DesignCapacity></Battery></r>"])
def test_broken_or_incomplete_reports_give_none(text):
    assert hr.parse_battery_xml(text) is None


def test_missing_cycle_count_is_none_not_a_crash():
    b = hr.parse_battery_xml("<r><Battery><DesignCapacity>100</DesignCapacity><FullChargeCapacity>90</FullChargeCapacity></Battery></r>")
    assert b.cycles is None and b.health_percent == 90.0


def test_zero_design_capacity_does_not_divide_by_zero():
    b = hr.BatteryHealth(0, 0, None, "", "")
    assert b.health_percent == 0.0


def test_battery_report_writes_temp_file_via_runner_and_cleans_it_up():
    seen = {}

    def runner(cmd, **kw):
        seen["cmd"] = cmd
        with open(cmd[cmd.index("/output") + 1], "w", encoding="utf-8") as f:
            f.write(XML)
        return types.SimpleNamespace(returncode=0)

    b = hr.battery_report(runner)
    assert b and b.cycles == 307 and seen["cmd"][:2] == ["powercfg", "/batteryreport"]
    assert not os.path.exists(seen["cmd"][seen["cmd"].index("/output") + 1])      # geçici dosya silindi


def test_battery_report_returns_none_on_desktop_without_battery_or_errors():
    assert hr.battery_report(lambda cmd, **kw: types.SimpleNamespace(returncode=1)) is None      # dosya boş kalır

    def timeout(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    assert hr.battery_report(timeout) is None


def test_disks_json_single_object_list_and_garbage():
    one = '{"FriendlyName":"KINGSTON","MediaType":"SSD","HealthStatus":"Healthy","OperationalStatus":"OK","BusType":"NVMe","Size":500107862016}'
    d = hr.parse_disks(one)
    assert len(d) == 1 and d[0].name == "KINGSTON" and d[0].verdict == hr.GOOD and d[0].size == 500107862016
    two = "[" + one + ',{"FriendlyName":"Eski","HealthStatus":"Warning"},{"FriendlyName":"Bozuk","HealthStatus":"Unhealthy"}]'
    verdicts = [x.verdict for x in hr.parse_disks(two)]
    assert verdicts == [hr.GOOD, hr.WARN, hr.BAD]
    assert hr.parse_disks("") == [] and hr.parse_disks("json değil") == [] and hr.parse_disks("[1, 2]") == []
    assert hr.parse_disks('{"FriendlyName":"X","HealthStatus":"Garip"}')[0].verdict == hr.UNKNOWN


def test_disk_health_and_smart_degrade_gracefully():
    ok = lambda cmd, **kw: types.SimpleNamespace(returncode=0, stdout=b'{"FriendlyName":"D","HealthStatus":"Healthy"}')
    fail = lambda cmd, **kw: types.SimpleNamespace(returncode=1, stdout=b"")
    missing = lambda cmd, **kw: (_ for _ in ()).throw(FileNotFoundError("powershell yok"))
    assert hr.disk_health(ok)[0].name == "D" and hr.disk_health(fail) == [] and hr.disk_health(missing) == []
    assert hr.smart_counters(fail) is None                                           # yönetici izni yoksa: None
    assert hr.smart_counters(lambda c, **k: types.SimpleNamespace(returncode=0, stdout=b'{"Temperature":38}'))[0]["Temperature"] == 38


@pytest.mark.skipif(sys.platform != "win32", reason="yalnızca Windows")
def test_real_disk_health_on_this_machine_is_read_only():
    disks = hr.disk_health()
    assert disks and all(d.name and d.size > 0 for d in disks)


@pytest.mark.skipif(sys.platform != "win32", reason="yalnızca Windows")
def test_real_battery_report_returns_something_sensible_or_none():
    b = hr.battery_report()                                                          # masaüstü bilgisayarda None olabilir
    if b is not None:
        assert b.design_mwh > 0 and 0 < b.health_percent <= 150
