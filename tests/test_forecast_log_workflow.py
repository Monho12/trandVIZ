""".github/workflows/forecast-log.yml (ADR 0016, #46): хуваарь, Render-тэй ижил орчин, golden test, зөвхөн forecast-log
branch-д push, мэдэгдлийн issue. Текстээр шалгана (PyYAML хамааралгүй), tests/test_deploy.py-тэй адил.  pytest -q"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github" / "workflows" / "forecast-log.yml").read_text(encoding="utf-8")
CI_REQS = (ROOT / "requirements-ci.txt").read_text(encoding="utf-8")


def run_lines() -> list[str]:
    """Shell мөрүүд (тайлбаргүй)."""
    return [line.strip() for line in WF.splitlines() if line.strip() and not line.strip().startswith("#")]


def test_runs_daily_at_0641_and_0941_utc_and_by_hand():
    assert sorted(re.findall(r'cron:\s*"([^"]+)"', WF)) == ["41 6 * * *", "41 9 * * *"]
    assert re.search(r"^\s*workflow_dispatch:", WF, re.M)
    assert re.search(r"^concurrency:", WF, re.M)          # хоёр ажиллагаа зэрэг log-д бичихгүй


def test_uses_python_313_and_the_server_pins_not_requirements_txt():
    assert re.search(r"python-version:\s*[\"']?3\.13[\"']?\s*$", WF, re.M)
    assert "pip install -r requirements-ci.txt" in WF and "requirements.txt" not in WF.replace("requirements-ci.txt", "")
    reqs = [line.strip() for line in CI_REQS.splitlines() if line.strip() and not line.startswith("#")]
    assert "-r requirements-app.txt" in reqs
    assert all(r.startswith("-r ") or "==" in r for r in reqs)   # бүгд pin
    assert not any(r.startswith("-r requirements.txt") for r in reqs)


def test_golden_test_runs_and_its_outcome_reaches_the_log():
    assert re.search(r"python -m pytest\b.*tests/test_golden\.py", WF)
    assert "--golden \"${{ steps.golden.outcome }}\"" in WF
    assert re.search(r"if:\s*steps\.golden\.outcome == 'failure'", WF)   # golden бүтэлгүйтвэл workflow бүтэлгүйтнэ


def test_logs_and_pushes_only_to_the_forecast_log_branch():
    assert re.search(r"python -m src\.forecast_log run --log-dir \S+ --render-url", WF)
    assert re.search(r"^\s*LOG_BRANCH:\s*forecast-log\s*$", WF, re.M)
    pushes = [line for line in run_lines() if line.startswith("git") and " push" in line]
    assert pushes and all(line.endswith('"HEAD:$LOG_BRANCH"') for line in pushes)
    assert not re.search(r"\bmain\b", "\n".join(pushes))
    assert re.search(r"^\s*contents:\s*write", WF, re.M) and re.search(r"^\s*issues:\s*write", WF, re.M)


def test_opens_issue_on_failure_and_on_two_gap_days():
    assert re.search(r"python -m src\.forecast_log alert --log-dir \S+ --out (\S+)", WF)
    issue_calls = re.findall(r"python3? -m src\.gh_issue --title \"([^\"]+)\"", WF)
    assert len(set(issue_calls)) == 2                        # цоорхой ба бүтэлгүйтэл: тус бүр нэг гарчиг (давхардахгүй)
    assert re.search(r"if:\s*failure\(\)", WF)
