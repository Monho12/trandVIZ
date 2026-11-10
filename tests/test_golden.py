"""Санах ойн оновчлол (ADR 0012) /api/*-ийн хариуг ЯГ хэвээр үлдээсэн эсэх: data/processed + app/model дээрх
хариуны sha256 нь оновчлолоос ӨМНӨХ кодоор бичсэн tests/golden/api_sha256.json-тэй ижил байх ёстой.
Model, data/processed, scoring-ийг зориудаар өөрчилбөл `python tests/golden/make_golden.py`-аар шинэчилнэ.  pytest -q"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"
pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def digests() -> dict:
    # Тусдаа process: test_api-ийн module-level state, monkeypatch-ээс хамааралгүй
    code = ("import json, sys; sys.path.insert(0, 'tests/golden'); import make_golden as g; "
            "print(json.dumps(g.digests(g.responses())))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


@pytest.mark.parametrize("endpoint", ["trending", "topic_ChatGPT", "map", "categories", "model"])
def test_api_response_is_identical_to_golden(digests, endpoint):
    want = json.loads((GOLDEN / "api_sha256.json").read_text(encoding="utf-8"))["sha256"]
    assert digests[endpoint] == want[endpoint], (
        f"/api/{endpoint} өөрчлөгдсөн. Зөрүүг харах: өмнөх commit дээр ба одоо `python tests/golden/make_golden.py --dump`, "
        "tests/golden/_dump/-ийг diff хий.")
