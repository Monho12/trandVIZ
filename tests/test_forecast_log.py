"""Хадгалсан таамгийн өдөр тутмын log (ADR 0016, #46): src/forecast_log.run_day-ийг бодит data/processed + app/model дээр,
хуурамч Wikimedia ба Render-ээр (сүлжээгүй) end-to-end шалгана.  pytest -q"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import forecast_log, live, train  # noqa: E402

BASE_END = pd.Timestamp("2026-11-10")      # data/processed-ийн сүүлийн өдөр
D = pd.Timestamp("2026-11-11")             # 2026-11-12-нд ажиллахад asof = өчигдөр
RUN = pd.Timestamp("2026-11-12 06:41")     # эхний cron (UTC)
RETRY = pd.Timestamp("2026-11-12 09:41")   # дахин оролдлого


@pytest.fixture(scope="module")
def base() -> live.RawCache:
    raw = live.RawCache.load(ROOT / "data" / "processed")
    assert raw.end == BASE_END
    return raw


@pytest.fixture(scope="module")
def model():
    return train.load()


class FakeWikimedia:
    """Wikimedia-ийн оронд: d өдрийн уншилт = data/processed-ийн d − 7 өдрийнх (бодит хэлбэртэй),
    `published_through`-аас хойшхи өдрийг буцаахгүй. `missing`-ийн сэдвүүд D өдөр мөргүй (хоцорсон эсвэл 0 уншилт)."""

    def __init__(self, base: live.RawCache, published_through: pd.Timestamp, missing=(), fail=False):
        self.base, self.published_through, self.missing, self.fail = base, published_through, set(missing), fail
        self.calls = []
        self._pv = pd.concat([base.pageviews[["date", "article", "views"]],
                              base.alias[["date", "old_title", "views"]].rename(columns={"old_title": "article"})])

    def _days(self, start, end):
        return pd.date_range(start, min(pd.Timestamp(end), self.published_through))

    def total(self, start, end):
        self.calls.append(("total", None, pd.Timestamp(start), pd.Timestamp(end)))
        if self.fail:
            raise ConnectionError("Wikimedia унасан")
        t = self.base.total.set_index("date")["total_views"]
        days = self._days(start, end)
        return pd.DataFrame({"date": days, "total_views": [int(t[d - pd.Timedelta(days=7)]) for d in days]})

    def article(self, title, start, end):
        self.calls.append(("article", title, pd.Timestamp(start), pd.Timestamp(end)))
        if self.fail:
            raise ConnectionError("Wikimedia унасан")
        rows = self._pv[self._pv["article"] == title].set_index("date")["views"]
        out = [(d, int(rows[d - pd.Timedelta(days=7)])) for d in self._days(start, end)
               if d - pd.Timedelta(days=7) in rows.index and not (title in self.missing and d == D)]
        return pd.DataFrame(out, columns=["date", "views"])


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def attempts(log_dir: Path) -> list[dict]:
    return [json.loads(line) for line in (log_dir / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]


def test_published_day_is_stored_with_model_version_topics_and_missing_flags(tmp_path, base, model):
    wiki = FakeWikimedia(base, published_through=D, missing={"ChatGPT"})
    att = forecast_log.run_day(tmp_path, base, wiki, model, RUN)
    assert att["status"] == forecast_log.LOGGED and att["asof"] == "2026-11-11"

    rec = read_json(tmp_path / "forecasts" / "2026-11-11.json")
    assert rec["asof"] == "2026-11-11" and rec["run_at"] == "2026-11-12T06:41:00Z"
    assert rec["model_hash"] == train.model_hash() and rec["model_version"] == train.short_version(train.model_hash())
    assert rec["libs"]["catboost"] == "1.2.10" and rec["libs"]["python"].startswith("3.13")
    topics = {t["article"]: t for t in rec["topics"]}
    assert len(topics) == 301
    assert topics["ChatGPT"]["was_missing"] is True
    assert sum(t["was_missing"] for t in topics.values()) == 1
    h1 = topics["Taylor_Swift"]["h1"]
    assert set(h1) == {"delta_hat", "pct", "lo", "hi", "y"}
    assert h1["lo"] <= h1["pct"] <= h1["hi"]
    assert [a["status"] for a in attempts(tmp_path)] == [forecast_log.LOGGED]


def test_unpublished_day_writes_only_status_and_is_never_backfilled(tmp_path, base, model):
    """D гараагүй: таамаг бичихгүй, not_published. Маргааш D+1 бичигдэнэ, D цоорхой хэвээр (хожим нөхөхгүй)."""
    att = forecast_log.run_day(tmp_path, base, FakeWikimedia(base, published_through=BASE_END), model, RUN)
    assert att["status"] == forecast_log.NOT_PUBLISHED and att["asof"] == "2026-11-11"
    assert not list(tmp_path.glob("forecasts/*.json"))

    nxt = pd.Timestamp("2026-11-13 06:41")
    att = forecast_log.run_day(tmp_path, base, FakeWikimedia(base, published_through=nxt.normalize() - pd.Timedelta(days=1)),
                               model, nxt)
    assert att["status"] == forecast_log.LOGGED and att["asof"] == "2026-11-12"
    assert [p.name for p in sorted(tmp_path.glob("forecasts/*.json"))] == ["2026-11-12.json"]
    assert [a["status"] for a in attempts(tmp_path)] == [forecast_log.NOT_PUBLISHED, forecast_log.LOGGED]


def test_next_run_replays_base_plus_deltas_and_fetches_only_new_days(tmp_path, base, model):
    """2-р өдөр: суурь + delta-аас эхэлж зөвхөн 11-12-ыг татна. Таамаг нь сервер суурийн дээр 11-11…11-12-ыг нэг дор
    татаж тооцсонтой ЯГ ижил (delta CSV нь өгөгдлийг алдагдалгүй хадгална)."""
    forecast_log.run_day(tmp_path, base, FakeWikimedia(base, published_through=D), model, RUN)
    assert (tmp_path / "deltas" / "2026-11-11.csv").exists()

    nxt, d2 = pd.Timestamp("2026-11-13 06:41"), pd.Timestamp("2026-11-12")
    wiki = FakeWikimedia(base, published_through=d2)
    forecast_log.run_day(tmp_path, base, wiki, model, nxt)
    assert {(s, e) for _, _, s, e in wiki.calls} == {(d2, d2)}

    server = live.update_cache(base, FakeWikimedia(base, published_through=d2), nxt.normalize()).cache
    assert server.end == d2
    from src import serve
    want = serve.predict(model, serve.Snapshot.from_raw(server).universe).set_index("article")
    got = {t["article"]: t for t in read_json(tmp_path / "forecasts" / "2026-11-12.json")["topics"]}
    for h in (1, 2, 3):
        assert [got[a][f"h{h}"]["delta_hat"] for a in want.index] == want[f"delta_hat_h{h}"].tolist()


def test_retry_after_logged_day_fetches_nothing_and_keeps_the_record(tmp_path, base, model):
    forecast_log.run_day(tmp_path, base, FakeWikimedia(base, published_through=D), model, RUN)
    first = (tmp_path / "forecasts" / "2026-11-11.json").read_bytes()
    wiki = FakeWikimedia(base, published_through=D)
    att = forecast_log.run_day(tmp_path, base, wiki, model, RETRY)
    assert att["status"] == forecast_log.ALREADY_LOGGED and wiki.calls == []
    assert (tmp_path / "forecasts" / "2026-11-11.json").read_bytes() == first
    assert [a["run_at"] for a in attempts(tmp_path)] == ["2026-11-12T06:41:00Z", "2026-11-12T09:41:00Z"]


@pytest.fixture(scope="module")
def render_response(base, tmp_path_factory):
    """Render-ийн /api/trending: жинхэнэ сервер (app.main) ижил өгөгдөл дээр (D хүртэл татсан cache нь data/live/-д)."""
    import os
    from fastapi.testclient import TestClient
    os.environ["SHUUGIAN_REFRESH"] = "0"
    import app.main as m
    live_dir = tmp_path_factory.mktemp("render_live")
    live.update_cache(base, FakeWikimedia(base, published_through=D, missing={"ChatGPT"}), RUN.normalize()).cache.save(live_dir)
    old, m.LIVE_DIR = m.LIVE_DIR, live_dir
    try:
        with TestClient(m.app) as c:
            return c.get("/api/trending").json()
    finally:
        m.LIVE_DIR = old


def run_with_render(tmp_path, base, model, render):
    wiki = FakeWikimedia(base, published_through=D, missing={"ChatGPT"})
    forecast_log.run_day(tmp_path, base, wiki, model, RUN, render=render)
    return read_json(tmp_path / "forecasts" / "2026-11-11.json")["render"]


def test_render_with_same_asof_matches_exactly(tmp_path, base, model, render_response):
    assert render_response["asof"] == "2026-11-11"
    seen = []
    cmp = run_with_render(tmp_path, base, model, lambda asof: seen.append(asof) or render_response)
    assert seen == [D]
    assert cmp["status"] == "compared" and cmp["n_compared"] == 301
    assert cmp["n_mismatch"] == 0 and cmp["max_pct_diff"] == 0 and cmp["max_y_diff"] == 0


def test_render_difference_is_counted_with_largest_gap_and_missing_flag(tmp_path, base, model, render_response):
    """Render хоёр сэдвийг өөрөөр харуулсан: ChatGPT-ийн D өдрийн мөр log-д ирээгүй (was_missing, Render-д ирсэн байж болно),
    Taylor_Swift-ийн h2 нь +15 п.п. Хоёулаа тоологдож, хамгийн их зөрүү бичигдэнэ."""
    import copy
    theirs = copy.deepcopy(render_response)
    items = {i["article"]: i for i in theirs["items"]}
    items["ChatGPT"]["forecast"][0]["y"] += 40
    ts = items["Taylor_Swift"]["forecast"][1]
    ts["pct"] = round(ts["pct"] + 0.15, 2)
    cmp = run_with_render(tmp_path, base, model, lambda asof: theirs)
    assert cmp["status"] == "compared" and cmp["n_mismatch"] == 2 and cmp["n_mismatch_was_missing"] == 1
    assert cmp["max_pct_diff"] == pytest.approx(0.15) and cmp["max_y_diff"] == 40
    assert [(m["article"], m["h"], m["was_missing"]) for m in cmp["mismatched"]] == [("ChatGPT", 1, True),
                                                                                    ("Taylor_Swift", 2, False)]


def test_render_skipped_when_asleep_or_on_other_asof_but_forecast_is_kept(tmp_path, base, model, render_response):
    def asleep(asof):
        raise TimeoutError("Render унтаж байна")

    cmp = run_with_render(tmp_path / "a", base, model, asleep)
    assert cmp["status"] == "skipped" and "унтаж" in cmp["reason"]
    cmp = run_with_render(tmp_path / "b", base, model, lambda asof: {**render_response, "asof": "2026-11-10"})
    assert cmp["status"] == "skipped" and "2026-11-10" in cmp["reason"]
    cmp = run_with_render(tmp_path / "c", base, model, None)
    assert cmp["status"] == "skipped"
    for d in "abc":
        assert len(read_json(tmp_path / d / "forecasts" / "2026-11-11.json")["topics"]) == 301


def test_wikimedia_outage_is_an_error_attempt_without_forecast(tmp_path, base, model):
    att = forecast_log.run_day(tmp_path, base, FakeWikimedia(base, published_through=D, fail=True), model, RUN)
    assert att["status"] == forecast_log.ERROR and "унасан" in att["message"]
    assert not (tmp_path / "forecasts").exists() and not (tmp_path / "deltas").exists()


def test_golden_test_outcome_is_stored_with_the_forecast(tmp_path, base, model):
    """Action-ийн golden test (Render-тэй ижил сангийн орчин) бүтэлгүйтсэн ч таамаг хадгалагдана, үр дүн нь хамт бичигдэнэ."""
    forecast_log.run_day(tmp_path, base, FakeWikimedia(base, published_through=D), model, RUN, golden="failure")
    assert read_json(tmp_path / "forecasts" / "2026-11-11.json")["golden_test"] == "failure"
    assert attempts(tmp_path)[-1]["golden_test"] == "failure"


# ---------------------------------------------------------------- цоорхойн мэдэгдэл (gap_alert)

def fake_log(log_dir: Path, logged: list[str], tried: dict[str, list[str]]) -> Path:
    """logged: forecasts/<өдөр>.json байгаа өдрүүд; tried: asof -> оролдлогуудын статус (attempts.jsonl-ийн дарааллаар)."""
    (log_dir / "forecasts").mkdir(parents=True)
    for d in logged:
        (log_dir / "forecasts" / f"{d}.json").write_text("{}", encoding="utf-8")
    lines = [json.dumps({"asof": d, "status": s, "run_at": f"{d}T06:41:00Z"}) for d, ss in tried.items() for s in ss]
    (log_dir / "attempts.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_dir


def test_two_consecutive_gap_days_after_the_last_retry_raise_an_alert(tmp_path):
    log = fake_log(tmp_path, ["2026-11-08", "2026-11-09"],
                   {"2026-11-08": ["logged"], "2026-11-09": ["logged"],
                    "2026-11-10": ["not_published", "not_published"], "2026-11-11": ["error", "not_published"]})
    body = forecast_log.gap_alert(log, RETRY)
    assert body is not None and "2026-11-10" in body and "2026-11-11" in body and "not_published" in body


def test_no_alert_while_yesterday_still_has_a_retry_or_for_a_single_gap(tmp_path):
    log = fake_log(tmp_path, ["2026-11-08", "2026-11-09"],
                   {"2026-11-08": ["logged"], "2026-11-09": ["logged"], "2026-11-10": ["not_published"] * 2,
                    "2026-11-11": ["not_published"]})
    assert forecast_log.gap_alert(log, RUN) is None              # 11-11-ийн 09:41-ийн оролдлого хараахан болоогүй
    (log / "forecasts" / "2026-11-11.json").write_text("{}", encoding="utf-8")
    assert forecast_log.gap_alert(log, RETRY) is None            # ганц цоорхой (11-10)


def test_days_before_the_log_started_are_not_gaps(tmp_path):
    log = fake_log(tmp_path, [], {"2026-11-11": ["not_published", "not_published"]})
    assert forecast_log.gap_alert(log, RETRY) is None
    assert forecast_log.gap_alert(tmp_path / "empty", RETRY) is None
