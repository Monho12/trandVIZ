"""/api/health: санах ой (cgroup v2/v1, /proc/self/status), uptime, refresh, asof. Файл байхгүй бол null.  pytest -q"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SHUUGIAN_REFRESH"] = "0"
import app.main as m  # noqa: E402

MIB = 1024 * 1024


def test_cgroup_v2(tmp_path):
    (tmp_path / "memory.current").write_text(f"{300 * MIB}\n")
    (tmp_path / "memory.peak").write_text(f"{420 * MIB + MIB // 2}\n")
    (tmp_path / "memory.max").write_text(f"{512 * MIB}\n")
    assert m.cgroup_memory(tmp_path) == {"cgroup": "v2", "current_mib": 300.0, "peak_mib": 420.5, "max_mib": 512.0}


def test_cgroup_v2_unlimited_and_no_peak_file(tmp_path):
    (tmp_path / "memory.current").write_text(f"{100 * MIB}\n")
    (tmp_path / "memory.max").write_text("max\n")   # хязгааргүй; memory.peak нь хуучин kernel-д байхгүй
    assert m.cgroup_memory(tmp_path) == {"cgroup": "v2", "current_mib": 100.0, "peak_mib": None, "max_mib": None}


def test_cgroup_v1(tmp_path):
    d = tmp_path / "memory"
    d.mkdir()
    (d / "memory.usage_in_bytes").write_text(str(200 * MIB))
    (d / "memory.max_usage_in_bytes").write_text(str(350 * MIB))
    (d / "memory.limit_in_bytes").write_text("9223372036854771712")   # v1-ийн "хязгааргүй"
    assert m.cgroup_memory(tmp_path) == {"cgroup": "v1", "current_mib": 200.0, "peak_mib": 350.0, "max_mib": None}


def test_no_cgroup_and_no_proc_is_all_null(tmp_path):
    """Windows / local: файл байхгүй бол унахгүй, null."""
    assert m.cgroup_memory(tmp_path / "nope") == {"cgroup": None, "current_mib": None, "peak_mib": None, "max_mib": None}
    assert m.process_memory(tmp_path / "status") == {"rss_mib": None, "hwm_mib": None}


def test_process_memory_from_status(tmp_path):
    f = tmp_path / "status"
    f.write_text("Name:\tpython\nVmHWM:\t  409600 kB\nVmRSS:\t  307200 kB\nThreads:\t3\n")
    assert m.process_memory(f) == {"rss_mib": 300.0, "hwm_mib": 400.0}


fastapi_testclient = pytest.importorskip("fastapi.testclient")


def test_health_endpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "CGROUP", tmp_path / "nope")         # cgroup-гүй орчин
    with fastapi_testclient.TestClient(m.app) as c:
        h = c.get("/api/health").json()
    assert h["status"] == "ok" and h["uptime_s"] >= 0
    assert h["asof"] == m.state.snapshot.asof.strftime("%Y-%m-%d")
    assert h["refresh"]["enabled"] is False
    assert h["memory"]["cgroup"] is None and h["memory"]["current_mib"] is None
    assert set(h["memory"]) == {"cgroup", "current_mib", "peak_mib", "max_mib", "rss_mib", "hwm_mib"}
    if Path("/proc/self/status").exists():
        assert h["memory"]["rss_mib"] > 0 and h["memory"]["hwm_mib"] >= h["memory"]["rss_mib"]
